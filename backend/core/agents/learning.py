"""
Learning Agent — runs after a user approves a post. Reads the completed
session, classifies statements, and writes durable knowledge to ChromaDB.

Non-blocking by design: this agent's work is invisible to the user but
calibrates future Planner and Critic behaviour.
"""

import json

from backend.core.agents.base import Agent
from backend.core.skills.learning_skills import (
    ReadSessionConversation,
    ClassifyKnowledge,
    WriteBrandKnowledge,
    WriteAgentMemory,
    ExtractDesignPatterns,
    LogSessionOutcome,
)


LEARNING_SYSTEM_PROMPT = """You are the Learning Agent for NowPurchase's AI Design Studio.
You are activated AFTER a user approves a post (non-blocking — runs in background).
You read the completed session conversation and extract durable knowledge.

MANDATORY SEQUENCE:
1. read_session_conversation — get all messages + session metadata.
   Extract theme and logo_type from session metadata.
2. For each substantive statement in the conversation:
   classify_knowledge -> decide: brand_knowledge | agent_memory | discard
3. For brand_knowledge items: write_brand_knowledge
4. Call extract_design_patterns on the full conversation.
5. For each extracted pattern: write_agent_memory
   ALWAYS include theme and logo_type from step 1 in every write_agent_memory call.
6. log_session_outcome

CLASSIFICATION RULES:
- brand_knowledge: facts about NowPurchase, MetalCloud, customers, products, team, brand voice
- agent_memory: design decisions, layout patterns, what the user approved or corrected
- discard: pleasantries, vague statements, questions without answers

CRITICAL: Every write_agent_memory call MUST include theme and logo_type.
This is non-negotiable — theme-tagged memories enable precise future retrieval.
Never write to agent_memory without both tags.

QUALITY OVER QUANTITY: Write 2-5 high-quality memories per session.
Do not write generic observations like "the post looked good."
"""


class LearningAgent(Agent):
    """Post-approval learning pass: writes brand_knowledge and agent_memory entries."""

    SYSTEM_PROMPT = LEARNING_SYSTEM_PROMPT

    def __init__(self, db_logger, llm_client, config):
        self.config = config
        skills = [
            ReadSessionConversation(db_logger=db_logger, agent_name="learning"),
            ClassifyKnowledge(db_logger=db_logger, agent_name="learning"),
            WriteBrandKnowledge(db_logger=db_logger, agent_name="learning"),
            WriteAgentMemory(db_logger=db_logger, agent_name="learning"),
            ExtractDesignPatterns(db_logger=db_logger, agent_name="learning"),
            LogSessionOutcome(db_logger=db_logger, agent_name="learning"),
        ]
        super().__init__(
            name="learning",
            system_prompt=self.SYSTEM_PROMPT,
            skills=skills,
            llm_client=llm_client,
        )

    def learn(self, session_id: str) -> "AgentResult":
        """Entry point. Orchestrates learning skills directly.

        The tool-use reasoning loop is overkill for a deterministic post-process —
        we know the exact sequence we want: read session, extract patterns,
        write each pattern to agent_memory, log outcome.
        """
        from backend.core.agents.base import AgentResult

        skills_used: list[str] = []
        learnings_written = 0
        outputs: list[str] = []

        # 1. Read the session
        read_skill = self.skill_registry["read_session_conversation"]
        read_result = read_skill(session_id=session_id)
        skills_used.append("read_session_conversation")
        if not read_result.success or not read_result.data:
            return AgentResult(
                output=f"Failed to read session: {read_result.error}",
                skills_used=skills_used,
                total_tokens=0,
            )

        data = read_result.data
        session = data.get("session", {})
        theme = data.get("theme", "") or session.get("theme", "")
        logo_type = data.get("logo_type", "") or session.get("logo_type", "")
        messages = data.get("messages", [])

        if not theme or not logo_type:
            return AgentResult(
                output=f"Session missing theme/logo_type — cannot tag memories",
                skills_used=skills_used,
                total_tokens=0,
            )

        compliance_score = int(session.get("compliance_score") or 0)
        user_rating = int(session.get("user_rating") or 0)

        # 2. Extract layout plan
        layout_plan: dict = {}
        layout_raw = session.get("layout_plan_json", "")
        if layout_raw:
            try:
                layout_plan = json.loads(layout_raw) if isinstance(layout_raw, str) else layout_raw
            except (json.JSONDecodeError, TypeError):
                layout_plan = {}

        # 3. Extract design patterns via LLM
        extract_skill = self.skill_registry["extract_design_patterns"]
        extract_result = extract_skill(
            session_id=session_id,
            conversation=messages,
            layout_plan=layout_plan,
            theme=theme,
            logo_type=logo_type,
            compliance_score=compliance_score,
            user_rating=user_rating,
        )
        skills_used.append("extract_design_patterns")
        patterns: list[dict] = []
        if extract_result.success and extract_result.data:
            patterns = extract_result.data.get("patterns", []) or []

        # 4. Write each pattern to agent_memory
        write_skill = self.skill_registry["write_agent_memory"]
        post_type = (session.get("brief_json") or "")
        purpose = "social_post"
        try:
            brief = json.loads(post_type) if isinstance(post_type, str) else (post_type or {})
            purpose = brief.get("purpose") or brief.get("post_type") or "social_post"
        except (json.JSONDecodeError, TypeError):
            pass

        for p in patterns:
            content = p.get("pattern") or ""
            if not content:
                continue
            ptype = p.get("type") or "layout_pattern"
            write_result = write_skill(
                session_id=session_id,
                content=content,
                memory_type=ptype,
                post_type=purpose,
                theme=theme,
                logo_type=logo_type,
                compliance_score=compliance_score,
                user_rating=user_rating,
            )
            skills_used.append("write_agent_memory")
            if write_result.success:
                learnings_written += 1
                outputs.append(f"  + [{ptype}] {content[:80]}")

        # 5. Log session outcome
        log_skill = self.skill_registry["log_session_outcome"]
        log_skill(
            session_id=session_id,
            outcome="APPROVED" if user_rating > 0 else session.get("state", "REVIEW"),
            user_rating=user_rating,
            compliance_score=compliance_score,
            learnings_written=learnings_written,
        )
        skills_used.append("log_session_outcome")

        summary = (
            f"Learning complete for {session_id}: "
            f"{learnings_written} patterns written to agent_memory "
            f"(theme={theme}, logo={logo_type}, score={compliance_score}, rating={user_rating})\n"
            + "\n".join(outputs)
        )
        return AgentResult(output=summary, skills_used=skills_used, total_tokens=0)


def build_learning_agent(db_logger, llm_client, config) -> LearningAgent:
    return LearningAgent(db_logger=db_logger, llm_client=llm_client, config=config)
