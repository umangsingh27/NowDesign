"""
Critic Agent — evaluates a generated post against the 14-point compliance checklist.

Runs after the Creator produces an image. Outputs a 0-100 score, a structured
issues list, and (on failure) a correction brief that guides the next iteration.
"""

import json

from backend.core.agents.base import Agent
from backend.core.skills.knowledge_skills import QueryAgentMemory
from backend.core.skills.critic_skills import (
    AnalyzeVisualCompliance,
    CheckTextLegibility,
    CheckLuminanceZones,
    ScoreAndReport,
    WriteCorrectsBrief,
    LogCompliancePattern,
)


CRITIC_SYSTEM_PROMPT = """You are the Critic Agent for NowPurchase's AI Design Studio.
You evaluate generated social media posts against the Brand Design Language.
You score each criterion explicitly. You NEVER say "looks good" without a score.

MANDATORY EVALUATION SEQUENCE:
1. query_agent_memory — search for past compliance patterns for this exact
   theme + logo_type combination. Use results to calibrate your scoring.
2. analyze_visual_compliance — send image + layout_plan + theme.
   This is the primary scoring step.
3. check_text_legibility — verify WCAG AA contrast for all text elements.
4. check_luminance_zones — verify background luminance in card area.
5. score_and_report — aggregate all results into final compliance report.
6. If score < 80: call write_correction_brief with the report + original plan.
7. log_compliance_pattern — always log the score to agent_memory.

THE 14-POINT CHECKLIST (100 points total):
Shared criteria (criteria 1-10, 60 pts):
  logo_present (7), logo_in_glass_pill (6), logo_variant_correct (5),
  text_in_glass (10), glass_depth_visible (5), no_bare_text (5),
  brand_blue_used (5), headline_readable (7), no_element_overlap (5),
  text_contrast_wcag (5)

Theme-conditional (criteria 11-14, 40 pts):
  Dark:  bg_theme_correct (10) - industrial/foundry imagery
         bg_mood_correct  (8)  - dark/moody, not bright
         color_palette    (12) - navy/dark + blue accent
         visual_hierarchy (10) - clear on dark glass
  Light: bg_theme_correct (10) - clean/minimal industrial
         bg_mood_correct  (8)  - light/airy, not heavy
         color_palette    (12) - white/grey + blue accent
         visual_hierarchy (10) - clear on light glass

PASS THRESHOLD: 80/100
You must score all 14 criteria before reporting.
Vague notes like "looks good" are not acceptable — be specific.
"""


class CriticAgent(Agent):
    """Scores the generated image and emits a structured compliance report."""

    SYSTEM_PROMPT = CRITIC_SYSTEM_PROMPT

    def __init__(self, db_logger, llm_client, config, chroma_client=None):
        if chroma_client is None:
            from backend.storage.chromadb_client import get_chroma_client
            chroma_client = get_chroma_client()
        self.config = config
        skills = [
            QueryAgentMemory(db_logger=db_logger, chroma_client=chroma_client),
            AnalyzeVisualCompliance(db_logger=db_logger, agent_name="critic"),
            CheckTextLegibility(db_logger=db_logger, agent_name="critic"),
            CheckLuminanceZones(db_logger=db_logger, agent_name="critic"),
            ScoreAndReport(db_logger=db_logger, agent_name="critic"),
            WriteCorrectsBrief(db_logger=db_logger, agent_name="critic"),
            LogCompliancePattern(db_logger=db_logger, agent_name="critic"),
        ]
        super().__init__(
            name="critic",
            system_prompt=self.SYSTEM_PROMPT,
            skills=skills,
            llm_client=llm_client,
        )

    def critique(
        self,
        session_id: str,
        image_path: str,
        layout_plan: dict,
        theme: str,
        logo_type: str,
    ) -> "AgentResult":
        """Entry point. Returns the compliance report."""
        context = f"""Evaluate this generated post for brand compliance.
Session: {session_id}
Image: {image_path}
Theme: {theme}
Logo type: {logo_type}

Layout plan summary:
{json.dumps(layout_plan, indent=2)}

Run the full 14-point compliance evaluation.
"""
        return self.run(session_id=session_id, context=context)


def build_critic_agent(db_logger, llm_client, config) -> CriticAgent:
    return CriticAgent(db_logger=db_logger, llm_client=llm_client, config=config)
