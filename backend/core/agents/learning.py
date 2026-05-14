"""
Learning Agent — runs after a user approves a post. Reads the completed
session, classifies statements, and writes durable knowledge to ChromaDB.

Non-blocking by design: this agent's work is invisible to the user but
calibrates future Planner and Critic behaviour.
"""

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
        """Entry point. Reads session, classifies, writes learnings."""
        context = f"""Process the completed session and extract learnings.
Session ID: {session_id}

Read the conversation, classify each valuable statement,
extract design patterns, and write to the appropriate knowledge stores.
Always tag agent_memory with theme and logo_type from the session record.
"""
        return self.run(session_id=session_id, context=context)


def build_learning_agent(db_logger, llm_client, config) -> LearningAgent:
    return LearningAgent(db_logger=db_logger, llm_client=llm_client, config=config)
