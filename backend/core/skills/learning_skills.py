"""
Learning Skills — six skills used by the Learning Agent.

1. ReadSessionConversation — pull all messages + session row from SQLite
2. ClassifyKnowledge       — decide brand_knowledge vs agent_memory vs discard
3. WriteBrandKnowledge     — write to brand_knowledge collection
4. WriteAgentMemory        — write to agent_memory collection (theme + logo_type required)
5. ExtractDesignPatterns   — LLM extracts 2-3 actionable patterns from a session
6. LogSessionOutcome       — finalize the SQLite session row with rating + score
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone

from backend.core.skills.base import Skill


def _llm_call(system: str, user: str) -> str:
    """Single-shot LLM call via OpenRouter. Returns text content."""
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )
    resp = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


def _extract_json(text: str) -> dict | list:
    """Pull the first JSON object/array out of a text blob."""
    text = text.strip()
    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    arr_match = re.search(r"\[.*\]", text, re.DOTALL)
    if obj_match and arr_match:
        # Pick whichever appears first
        candidate = obj_match.group(0) if obj_match.start() < arr_match.start() else arr_match.group(0)
    elif obj_match:
        candidate = obj_match.group(0)
    elif arr_match:
        candidate = arr_match.group(0)
    else:
        return {}
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {}


# ── 1. ReadSessionConversation ───────────────────────────────────────────────

class ReadSessionConversation(Skill):
    """Read all conversation rows + the session row for a given session_id."""

    @property
    def name(self) -> str:
        return "read_session_conversation"

    @property
    def description(self) -> str:
        return (
            "Read the full conversation log and session metadata for a session_id. "
            "Returns messages, session row, theme, and logo_type."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        }

    def _execute(self, session_id: str) -> dict:
        session = self.db_logger.get_session(session_id) or {}
        messages = self.db_logger.get_conversations(session_id) or []
        return {
            "messages": messages,
            "session": session,
            "theme": session.get("theme", ""),
            "logo_type": session.get("logo_type", ""),
        }


# ── 2. ClassifyKnowledge ─────────────────────────────────────────────────────

class ClassifyKnowledge(Skill):
    """LLM classifies a statement as brand_knowledge / agent_memory / discard."""

    @property
    def name(self) -> str:
        return "classify_knowledge"

    @property
    def description(self) -> str:
        return (
            "Classify a statement as brand_knowledge, agent_memory, or discard. "
            "Use during a learning pass to triage conversation content for storage."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "statement": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["statement", "context"],
        }

    def _execute(self, statement: str, context: str) -> dict:
        system = (
            "You classify design-system statements for storage. "
            "Return only valid JSON."
        )
        user = f"""Classify this statement for storage in a design knowledge system.
Statement: '{statement}'
Context: '{context}'

Return JSON: {{
  "type": "brand_knowledge" | "agent_memory" | "discard",
  "confidence": 0.0-1.0,
  "reasoning": "one sentence"
}}

brand_knowledge = facts about NowPurchase, products, customers, team, voice
agent_memory    = design patterns, what worked/failed in a specific session
discard         = chitchat, filler, irrelevant"""
        raw = _llm_call(system, user)
        parsed = _extract_json(raw)
        if not isinstance(parsed, dict):
            parsed = {"type": "discard", "confidence": 0.0, "reasoning": "parse failed"}
        return parsed


# ── 3. WriteBrandKnowledge ───────────────────────────────────────────────────

class WriteBrandKnowledge(Skill):
    """Write a single entry into the brand_knowledge collection."""

    @property
    def name(self) -> str:
        return "write_brand_knowledge"

    @property
    def description(self) -> str:
        return (
            "Add a fact to brand_knowledge. Use for company/product/team/voice/customer facts. "
            "Do NOT use for design patterns — those go to write_agent_memory."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "category": {"type": "string"},
                "topic": {"type": "string"},
            },
            "required": ["content", "category", "topic"],
        }

    def _execute(self, content: str, category: str, topic: str) -> dict:
        from backend.storage.chromadb_client import get_chroma_client

        client = get_chroma_client()
        doc_id = client.add_document(
            collection="brand_knowledge",
            document=content,
            metadata={
                "category": category,
                "topic": topic,
                "added_by": "agent:learning_agent",
                "added_at": datetime.now(timezone.utc).isoformat(),
                "verified": False,
                "source": "learning_agent",
            },
        )
        return {"id": doc_id, "status": "written"}


# ── 4. WriteAgentMemory ──────────────────────────────────────────────────────

class WriteAgentMemory(Skill):
    """Write a design pattern into agent_memory with mandatory theme+logo_type tags."""

    @property
    def name(self) -> str:
        return "write_agent_memory"

    @property
    def description(self) -> str:
        return (
            "Store a design pattern in agent_memory. theme and logo_type are REQUIRED — "
            "they tag the memory for filtered retrieval. Never call without both."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "memory_type": {"type": "string"},
                "post_type": {"type": "string"},
                "theme": {"type": "string", "enum": ["dark", "light"]},
                "logo_type": {
                    "type": "string",
                    "enum": ["nowpurchase", "metalcloud", "combined"],
                },
                "compliance_score": {"type": "integer", "default": 0},
                "user_rating": {"type": "integer", "default": 0},
                "session_id": {"type": "string", "default": ""},
            },
            "required": ["content", "memory_type", "post_type", "theme", "logo_type"],
        }

    def _execute(
        self,
        content: str,
        memory_type: str,
        post_type: str,
        theme: str,
        logo_type: str,
        compliance_score: int = 0,
        user_rating: int = 0,
        session_id: str = "",
    ) -> dict:
        from backend.storage.chromadb_client import get_chroma_client

        client = get_chroma_client()
        doc_id = client.add_document(
            collection="agent_memory",
            document=content,
            metadata={
                "memory_type": memory_type,
                "post_type": post_type,
                "theme": theme,
                "logo_type": logo_type,
                "compliance_score": compliance_score,
                "user_rating": user_rating,
                "session_id": session_id or self._current_session_id,
                "added_by": "agent:learning_agent",
                "added_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"id": doc_id, "status": "written"}


# ── 5. ExtractDesignPatterns ─────────────────────────────────────────────────

class ExtractDesignPatterns(Skill):
    """LLM extracts 2-3 actionable design patterns from a session conversation."""

    @property
    def name(self) -> str:
        return "extract_design_patterns"

    @property
    def description(self) -> str:
        return (
            "Extract 2-3 actionable design patterns from a session conversation + "
            "its layout plan. Returns a list of pattern dicts."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "conversation": {"type": "array", "items": {"type": "object"}},
                "layout_plan": {"type": "object"},
                "theme": {"type": "string", "enum": ["dark", "light"]},
                "logo_type": {
                    "type": "string",
                    "enum": ["nowpurchase", "metalcloud", "combined"],
                },
                "compliance_score": {"type": "integer"},
                "user_rating": {"type": "integer"},
            },
            "required": [
                "conversation",
                "layout_plan",
                "theme",
                "logo_type",
                "compliance_score",
                "user_rating",
            ],
        }

    def _execute(
        self,
        conversation: list,
        layout_plan: dict,
        theme: str,
        logo_type: str,
        compliance_score: int,
        user_rating: int,
    ) -> dict:
        convo_text = "\n".join(
            f"[{m.get('role','?')}] {m.get('content','')[:200]}" for m in conversation
        )[:6000]

        system = "You extract durable, reusable design patterns. Return only JSON array."
        user = f"""Extract 2-3 concrete design patterns from this session.
Theme: {theme}, Logo: {logo_type}, Score: {compliance_score}/100, Rating: {user_rating}/5

Session conversation summary:
{convo_text}

Return JSON array of patterns:
[
  {{
    "pattern": "one sentence describing what worked or failed",
    "type": "layout_pattern|failure_pattern|approval_pattern",
    "specificity": "high|medium|low"
  }}
]

Only extract patterns with high or medium specificity.
Pattern must be actionable for future generations."""

        raw = _llm_call(system, user)
        parsed = _extract_json(raw)
        if isinstance(parsed, list):
            patterns = [
                p for p in parsed
                if isinstance(p, dict) and p.get("specificity") in ("high", "medium")
            ]
        else:
            patterns = []
        return {"patterns": patterns, "count": len(patterns)}


# ── 6. LogSessionOutcome ─────────────────────────────────────────────────────

class LogSessionOutcome(Skill):
    """Update the SQLite sessions row with final outcome, rating, score."""

    @property
    def name(self) -> str:
        return "log_session_outcome"

    @property
    def description(self) -> str:
        return (
            "Finalize the session in SQLite: write state, user_rating, "
            "compliance_score, and learnings_written count."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "outcome": {"type": "string"},
                "user_rating": {"type": "integer"},
                "compliance_score": {"type": "integer"},
                "learnings_written": {"type": "integer"},
            },
            "required": [
                "session_id",
                "outcome",
                "user_rating",
                "compliance_score",
                "learnings_written",
            ],
        }

    def _execute(
        self,
        session_id: str,
        outcome: str,
        user_rating: int,
        compliance_score: int,
        learnings_written: int,
    ) -> dict:
        try:
            self.db_logger.log_session_update(
                session_id,
                state=outcome,
                user_rating=user_rating,
                compliance_score=compliance_score,
            )
        except TypeError:
            # log_session_update might not accept all kwargs — fall back gracefully
            self.db_logger.log_session_update(session_id, state=outcome)
        return {
            "status": "logged",
            "session_id": session_id,
            "outcome": outcome,
            "learnings_written": learnings_written,
        }
