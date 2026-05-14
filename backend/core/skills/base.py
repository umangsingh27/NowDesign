"""
Skill — the atomic unit of all agent capabilities in NowPurchase Design Studio.

Every capability the system has is a Skill subclass.
The Skill base class guarantees:
  - Every invocation is logged to SQLite automatically (Law 2)
  - Skills are independently testable without an agent
  - Skills are swappable via the SkillRegistry
  - The LLM can call any skill via OpenAI-format tool definitions

To add a new capability:
  1. Subclass Skill
  2. Implement name, description, _execute, get_parameters_schema
  3. Register it in the relevant agent's skill list
"""

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel


class SkillResult(BaseModel):
    """Returned by every skill invocation. Success or failure, always structured."""
    success: bool
    data: Any
    error: Optional[str] = None
    duration_ms: int


class Skill(ABC):
    """
    Abstract base class for all Skills.

    Constructor injection pattern — every Skill receives:
      db_logger:  SQLiteLogger instance (for auto-logging)
      agent_name: Name of the agent that owns this skill (for log attribution)

    Never instantiate a Skill without a db_logger — logging is not optional.
    """

    def __init__(self, db_logger, agent_name: str):
        self.db_logger = db_logger
        self.agent_name = agent_name
        self._current_session_id: str = ""

    # ── Abstract interface ─────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique snake_case identifier.
        Must match what the LLM will use in tool_call.function.name.
        Examples: 'query_brand_knowledge', 'render_glass_effect'
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """
        One or two sentences describing what this skill does and when to use it.
        This text goes directly into the LLM's tool definition — write it for the model.
        """

    @abstractmethod
    def _execute(self, **kwargs) -> Any:
        """
        The actual implementation. Receives named arguments matching get_parameters_schema.
        May raise — exceptions are caught by __call__ and logged as failures.
        Should NOT call db_logger directly — the base class handles that.
        """

    @abstractmethod
    def get_parameters_schema(self) -> dict:
        """
        JSON Schema object describing this skill's parameters.
        Used in OpenAI tool definition format.
        Must include 'type': 'object', 'properties', and 'required'.
        """

    # ── Callable interface (auto-logs every invocation) ────────────────────

    def __call__(self, session_id: str, **kwargs) -> SkillResult:
        """
        Public entry point. Call skills as:
            result = skill(session_id=session_id, query="...", n_results=3)

        Wraps _execute with:
          - Precise millisecond timing
          - Automatic SQLite logging (success or failure)
          - Exception isolation (never propagates — always returns SkillResult)
        """
        self._current_session_id = session_id
        start_ms = time.monotonic_ns() // 1_000_000
        result: SkillResult

        try:
            result_data = self._execute(**kwargs)
            duration = (time.monotonic_ns() // 1_000_000) - start_ms
            result = SkillResult(success=True, data=result_data, duration_ms=duration)
        except Exception as exc:
            duration = (time.monotonic_ns() // 1_000_000) - start_ms
            result = SkillResult(
                success=False,
                data=None,
                error=str(exc),
                duration_ms=duration
            )

        # Auto-log — always fires, even on failure, even if logging itself errors
        try:
            self.db_logger.log_skill_invocation(
                invocation_id=f"si_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                agent_name=self.agent_name,
                skill_name=self.name,
                input_json=str(kwargs)[:2000],
                output_json=str(result.data)[:2000],
                duration_ms=result.duration_ms,
                success=result.success,
                error_message=result.error,
                invoked_at=datetime.now(timezone.utc).isoformat()
            )
        except Exception:
            pass  # Never let logging failure break the pipeline

        return result

    # ── LLM tool definition ────────────────────────────────────────────────

    def as_tool_definition(self) -> dict:
        """
        Returns the OpenAI function-calling format tool definition.
        This is what gets passed to the LLM in the 'tools' parameter.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema()
            }
        }
