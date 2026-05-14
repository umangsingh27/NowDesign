"""
Agent — a reasoning loop with a SkillRegistry.

The Agent base class implements the while-loop pattern:
  1. Send context + tool definitions to LLM
  2. If LLM calls a tool -> execute via SkillRegistry -> append result -> loop
  3. If LLM returns final answer (finish_reason='stop') -> return AgentResult

This is the same pattern Claude Code itself uses internally.
Agents do not implement business logic — they reason about which skills to call.

Uses openai SDK pointed at OpenRouter. LLM model: anthropic/claude-sonnet-4.
"""

import json
import os
from typing import Any

from openai import OpenAI


_LLM_OPAQUE_KEYS = {
    "image_bytes",
    "image_bytes_b64",
    "result_bytes_b64",
    "background_bytes_b64",
    "canvas_bytes_b64",
}


def _trim_for_llm(obj: Any, max_str: int = 600) -> Any:
    """Replace large opaque payloads with summaries before serializing to the LLM.

    The Creator skills pass full base64 PNGs through their return values so the
    next skill in the chain can pick up the canvas. The LLM, however, never needs
    to see those bytes — it just needs to know the call succeeded. Including the
    raw bytes blows past the 200k-token Anthropic limit after a few iterations.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in _LLM_OPAQUE_KEYS and isinstance(v, str) and len(v) > max_str:
                out[k] = f"<{k}:{len(v)}_chars_omitted>"
            else:
                out[k] = _trim_for_llm(v, max_str)
        return out
    if isinstance(obj, list):
        return [_trim_for_llm(x, max_str) for x in obj]
    if isinstance(obj, str) and len(obj) > max_str * 4:
        return obj[: max_str * 2] + f"<...{len(obj) - max_str * 2}_chars_trimmed>"
    return obj


class AgentResult:
    """Returned by Agent.run() when the LLM produces its final answer."""
    def __init__(self, output: Any, skills_used: list[str], total_tokens: int):
        self.output = output
        self.skills_used = skills_used
        self.total_tokens = total_tokens

    def __repr__(self) -> str:
        return (
            f"AgentResult(skills_used={self.skills_used}, "
            f"total_tokens={self.total_tokens}, "
            f"output_preview='{str(self.output)[:80]}...')"
        )


class Agent:
    """
    Abstract agent. Subclasses configure:
      - name: str
      - system_prompt: str
      - skills: list[Skill]

    The run() method is inherited and must NOT be overridden.
    All customisation happens through the system_prompt and the skills list.
    """

    def __init__(self, name: str, system_prompt: str, skills: list, llm_client: OpenAI):
        self.name = name
        self.system_prompt = system_prompt
        self.skill_registry = {s.name: s for s in skills}
        self.llm = llm_client
        self.tool_definitions = [s.as_tool_definition() for s in skills]

    def run(
        self,
        session_id: str,
        context: str,
        max_iterations: int = 20
    ) -> AgentResult:
        """
        The reasoning loop.

        session_id is passed through to every skill call for logging.
        context is the user-facing input (brief, feedback message, etc.)
        max_iterations prevents runaway loops — raises RuntimeError if exceeded.
        """
        messages = [{"role": "user", "content": context}]
        skills_used: list[str] = []
        total_tokens: int = 0
        iteration: int = 0

        while iteration < max_iterations:
            iteration += 1

            response = self.llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4"),
                messages=[
                    {"role": "system", "content": self.system_prompt}
                ] + messages,
                tools=self.tool_definitions if self.tool_definitions else None,
                tool_choice="auto" if self.tool_definitions else None
            )

            total_tokens += response.usage.total_tokens if response.usage else 0
            choice = response.choices[0]

            # LLM is done — no more tool calls
            if choice.finish_reason == "stop":
                return AgentResult(
                    output=choice.message.content,
                    skills_used=skills_used,
                    total_tokens=total_tokens
                )

            # LLM wants to call tools
            if not choice.message.tool_calls:
                # Finish reason was not 'stop' but no tool calls — treat as done
                return AgentResult(
                    output=choice.message.content or "",
                    skills_used=skills_used,
                    total_tokens=total_tokens
                )

            messages.append(choice.message.model_dump(exclude_unset=True))
            tool_results = []

            for tool_call in choice.message.tool_calls:
                skill_name = tool_call.function.name
                try:
                    skill_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    skill_args = {}

                skills_used.append(skill_name)

                if skill_name in self.skill_registry:
                    skill = self.skill_registry[skill_name]
                    # The base Skill.__call__ already consumes session_id; if the
                    # LLM also passed it in the tool args, strip it to avoid
                    # "got multiple values for keyword argument 'session_id'".
                    skill_args.pop("session_id", None)
                    result = skill(session_id=session_id, **skill_args)
                    if result.success:
                        # Strip large opaque payloads (image bytes) before sending
                        # back to the LLM — they balloon context and the model only
                        # needs to know the skill succeeded.
                        content = json.dumps(
                            _trim_for_llm(result.data), default=str,
                        )
                    else:
                        content = f"ERROR executing {skill_name}: {result.error}"
                else:
                    content = f"ERROR: skill '{skill_name}' not found in registry. Available: {list(self.skill_registry.keys())}"

                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": content
                })

            messages.extend(tool_results)

        raise RuntimeError(
            f"Agent '{self.name}' exceeded max_iterations={max_iterations}. "
            f"Skills called so far: {skills_used}"
        )

    @classmethod
    def create_llm_client(cls) -> OpenAI:
        """Factory for the shared OpenAI/OpenRouter client."""
        return OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        )
