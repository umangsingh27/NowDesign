"""
Knowledge Skills — ChromaDB read/write interface for all agents.

Four skills:
  QueryBrandKnowledge  — semantic search on brand_knowledge (all agents can use)
  QueryAgentMemory     — semantic search on agent_memory with theme+logo_type filtering
  WriteBrandKnowledge  — add entry to brand_knowledge (Learning Agent + humans)
  WriteAgentMemory     — add entry to agent_memory (Learning Agent only)
                         REQUIRES theme and logo_type — enforced in schema

Every write is also logged to kb_operations in SQLite via the base Skill logger.
"""

import uuid
from datetime import datetime, timezone

from backend.core.skills.base import Skill
from backend.storage.chromadb_client import ChromaDBClient


class QueryBrandKnowledge(Skill):
    """Semantic search on the brand_knowledge collection."""

    def __init__(self, db_logger, chroma_client: ChromaDBClient):
        super().__init__(db_logger=db_logger, agent_name="knowledge")
        self.chroma = chroma_client

    @property
    def name(self) -> str:
        return "query_brand_knowledge"

    @property
    def description(self) -> str:
        return (
            "Search the brand knowledge base for information about NowPurchase, MetalCloud, "
            "products, team, customers, raw materials, brand voice, and design rules. "
            "Use this before planning any post to retrieve relevant company context. "
            "Include theme context in the query for design rules, e.g. 'dark mode glass card spec'."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query. Include theme context for design rule queries."
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return. Default 3, max 8.",
                    "default": 3
                }
            },
            "required": ["query"]
        }

    def _execute(self, query: str, n_results: int = 3) -> list[dict]:
        results = self.chroma.query_collection(
            name="brand_knowledge",
            query=query,
            n=min(n_results, 8)
        )
        self.db_logger.log_kb_operation(
            op_id=f"kbo_{uuid.uuid4().hex[:10]}",
            session_id=self._current_session_id or None,
            collection="brand_knowledge",
            operation="read",
            query=query,
            result_count=len(results),
            agent_name=self.agent_name
        )
        return results


class QueryAgentMemory(Skill):
    """
    Semantic search on agent_memory with mandatory theme + logo_type filtering.
    Dark-mode learnings must never influence light-mode generation.
    """

    def __init__(self, db_logger, chroma_client: ChromaDBClient):
        super().__init__(db_logger=db_logger, agent_name="knowledge")
        self.chroma = chroma_client

    @property
    def name(self) -> str:
        return "query_agent_memory"

    @property
    def description(self) -> str:
        return (
            "Search the agent memory for past design patterns, corrections, and learnings. "
            "Always pass theme and logo_type to retrieve context-specific patterns — "
            "dark-mode and light-mode patterns are stored separately and must not be mixed. "
            "Use before planning to find what worked (or failed) for similar past posts."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query describing what pattern to find."
                },
                "theme": {
                    "type": "string",
                    "enum": ["dark", "light"],
                    "description": "Filter to only this theme's learnings. Always provide."
                },
                "logo_type": {
                    "type": "string",
                    "enum": ["nowpurchase", "metalcloud", "combined"],
                    "description": "Filter to only this logo type's learnings. Always provide."
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return. Default 3, max 6.",
                    "default": 3
                }
            },
            "required": ["query", "theme", "logo_type"]
        }

    def _execute(
        self,
        query: str,
        theme: str,
        logo_type: str,
        n_results: int = 3
    ) -> list[dict]:
        # Return empty list rather than error when collection is empty
        if self.chroma.agent_memory.count() == 0:
            return []

        filters = {
            "$and": [
                {"theme": {"$eq": theme}},
                {"logo_type": {"$eq": logo_type}}
            ]
        }
        results = self.chroma.query_collection(
            name="agent_memory",
            query=query,
            n=min(n_results, 6),
            filters=filters
        )
        self.db_logger.log_kb_operation(
            op_id=f"kbo_{uuid.uuid4().hex[:10]}",
            session_id=self._current_session_id or None,
            collection="agent_memory",
            operation="read",
            query=f"{query} [theme={theme}, logo_type={logo_type}]",
            result_count=len(results),
            agent_name=self.agent_name
        )
        return results


class WriteBrandKnowledge(Skill):
    """
    Add a new entry to brand_knowledge.
    Used by: Learning Agent (auto), and humans via the /api/knowledge endpoint.
    """

    def __init__(self, db_logger, chroma_client: ChromaDBClient):
        super().__init__(db_logger=db_logger, agent_name="learning")
        self.chroma = chroma_client

    @property
    def name(self) -> str:
        return "write_brand_knowledge"

    @property
    def description(self) -> str:
        return (
            "Add a new fact or rule to the brand knowledge base. "
            "Use this when the conversation reveals new information about NowPurchase products, "
            "team, customers, brand voice, or design rules that should be remembered permanently. "
            "Do NOT use this for design patterns or layout learnings — use write_agent_memory instead."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The factual content to store. Write as a complete, self-contained statement."
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "company_info", "product_info", "team_info", "material_info",
                        "customer_info", "brand_voice", "design_rules_dark",
                        "design_rules_light", "logo_guidelines"
                    ],
                    "description": "Category for this knowledge entry."
                },
                "topic": {
                    "type": "string",
                    "description": "Short topic label, e.g. 'MetalCloud WhatsApp feature' or 'dark mode glass spec'."
                }
            },
            "required": ["content", "category", "topic"]
        }

    def _execute(self, content: str, category: str, topic: str) -> dict:
        doc_id = self.chroma.add_document(
            collection="brand_knowledge",
            document=content,
            metadata={
                "category": category,
                "topic": topic,
                "added_by": "agent:learning_agent",
                "added_at": datetime.now(timezone.utc).isoformat(),
                "verified": False,
                "source": "learning_agent"
            }
        )
        self.db_logger.log_kb_operation(
            op_id=f"kbo_{uuid.uuid4().hex[:10]}",
            session_id=self._current_session_id or None,
            collection="brand_knowledge",
            operation="write",
            document_id=doc_id,
            agent_name=self.agent_name
        )
        return {"id": doc_id, "status": "written", "collection": "brand_knowledge", "topic": topic}


class WriteAgentMemory(Skill):
    """
    Add a design pattern or learning to agent_memory.
    REQUIRES theme and logo_type — stored as metadata for filtered retrieval.
    Dark-mode and light-mode learnings are always stored separately.
    """

    def __init__(self, db_logger, chroma_client: ChromaDBClient):
        super().__init__(db_logger=db_logger, agent_name="learning")
        self.chroma = chroma_client

    @property
    def name(self) -> str:
        return "write_agent_memory"

    @property
    def description(self) -> str:
        return (
            "Store a design pattern or correction in agent memory. "
            "Use after a session is approved to record what layout decisions worked, "
            "what corrections were made, and what the user preferred. "
            "theme and logo_type are REQUIRED — never omit them. "
            "These tags ensure future Planner and Critic calls retrieve only relevant patterns."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The learned pattern or correction, written as a reusable rule."
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["layout_pattern", "correction", "approval_pattern", "failure_pattern", "user_preference"],
                    "description": "Classification of this memory entry."
                },
                "post_type": {
                    "type": "string",
                    "description": "The post_type this learning applies to, e.g. 'product_feature'."
                },
                "theme": {
                    "type": "string",
                    "enum": ["dark", "light"],
                    "description": "REQUIRED. The theme this pattern applies to. Never mix."
                },
                "logo_type": {
                    "type": "string",
                    "enum": ["nowpurchase", "metalcloud", "combined"],
                    "description": "REQUIRED. The logo type this pattern applies to."
                },
                "compliance_score": {
                    "type": "integer",
                    "description": "Final Critic compliance score for the session (0-100)."
                },
                "user_rating": {
                    "type": "integer",
                    "description": "User's star rating (1-5)."
                }
            },
            "required": ["content", "memory_type", "post_type", "theme", "logo_type", "compliance_score", "user_rating"]
        }

    def _execute(
        self,
        content: str,
        memory_type: str,
        post_type: str,
        theme: str,
        logo_type: str,
        compliance_score: int,
        user_rating: int
    ) -> dict:
        doc_id = self.chroma.add_document(
            collection="agent_memory",
            document=content,
            metadata={
                "memory_type": memory_type,
                "post_type": post_type,
                "theme": theme,
                "logo_type": logo_type,
                "compliance_score": compliance_score,
                "user_rating": user_rating,
                "added_by": "agent:learning_agent",
                "added_at": datetime.now(timezone.utc).isoformat()
            }
        )
        self.db_logger.log_kb_operation(
            op_id=f"kbo_{uuid.uuid4().hex[:10]}",
            session_id=self._current_session_id or None,
            collection="agent_memory",
            operation="write",
            document_id=doc_id,
            agent_name=self.agent_name
        )
        return {
            "id": doc_id,
            "status": "written",
            "collection": "agent_memory",
            "theme": theme,
            "logo_type": logo_type
        }
