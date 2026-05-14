"""
Planner Agent — translates a user brief into a pixel-exact LayoutPlan.

Reasoning loop (inherits Agent.run()):
  1. query_brand_knowledge  — retrieve design rules for the given theme
  2. query_agent_memory     — retrieve past patterns filtered by theme + logo_type
  3. ask_clarification      — (if needed) pause for user answers
  4. estimate_text_dimensions — measure each text element
  5. resolve_logo_asset     — get exact logo path for logo_type + theme
  6. calculate_layout       — validate placement, check overlaps
  7. write_layout_plan      — validate and persist the final plan

The Planner NEVER hardcodes colour values.
It resolves all colours from brand_config.themes[theme] retrieved via query_brand_knowledge.
It resolves the logo path via resolve_logo_asset before writing the plan.
"""

import json
import os
from pathlib import Path

from backend.core.agents.base import Agent
from backend.core.skills.knowledge_skills import QueryBrandKnowledge, QueryAgentMemory
from backend.core.skills.planner_skills import (
    AskClarification,
    EstimateTextDimensions,
    ResolveLogoAsset,
    CalculateLayout,
    WriteLayoutPlan
)

PLANNER_SYSTEM_PROMPT = """You are the Planner Agent for NowPurchase's AI Design Studio.
Your job is to translate a creative brief into a precise, pixel-level layout plan
for a 1080×1080 PNG social media post.

ALWAYS follow this exact sequence of steps:

STEP 1 — QUERY BRAND KNOWLEDGE
Call query_brand_knowledge twice:
  a) For company/product context relevant to the brief content
  b) For design rules for the specified theme, e.g.:
     "dark mode glassmorphism design rules NowPurchase" OR
     "light mode glass card design language NowPurchase"

STEP 2 — QUERY AGENT MEMORY
Call query_agent_memory with:
  - query: a description of this post type and content
  - theme: the brief's theme (dark or light)
  - logo_type: the brief's logo_type
This retrieves past patterns for this exact theme + logo_type combination.
If agent_memory returns empty, proceed with brand_knowledge rules.

STEP 3 — ASK CLARIFICATION (if needed)
If the brief is missing critical information (industry context, tone, specific metric details),
call ask_clarification with a list of 1-3 specific questions.
ONLY ask if truly needed. Do NOT ask about theme or logo_type — those are already set.

STEP 4 — RESOLVE LOGO ASSET
Call resolve_logo_asset with the brief's logo_type and theme.
Store the returned asset_path — it goes into logo_pill.logo.asset in the layout plan.

STEP 5 — ESTIMATE TEXT DIMENSIONS
For every text element you plan to include, call estimate_text_dimensions.
Use the appropriate font from brand_config:
  - Headlines: assets/fonts/Urbanist-ExtraBold.ttf (size 52-72)
  - Stats: assets/fonts/Urbanist-ExtraBold.ttf (size 60-96)
  - Body: assets/fonts/Oxanium-Regular.ttf or Oxanium-Medium.ttf (size 18-28)

STEP 6 — CALCULATE LAYOUT
Call calculate_layout with all elements and their estimated_dimensions.
If warnings contain overlaps: adjust element positions and recalculate.
If warnings contain safe-zone violations: shift elements inward by the reported amount.
Proceed when valid=True OR when remaining warnings are acceptable (e.g. intentional bleeds).

STEP 7 — WRITE LAYOUT PLAN
Call write_layout_plan with the complete layout_json dict.

COLOUR RULES — NEVER HARDCODE:
Retrieve all colour values from brand_knowledge (the design rules entries you queried in Step 1).
For dark theme:
  - Glass fill: rgba(0,0,0,0.62)
  - Border top: rgba(255,255,255,0.28), sides: rgba(255,255,255,0.08)
  - Inner highlight: rgba(255,255,255,0.18)
  - Text primary: #FFFFFF, secondary: rgba(255,255,255,0.75)
  - Pill fill: rgba(0,0,0,0.60), pill border: rgba(255,255,255,0.20)
For light theme:
  - Glass fill: rgba(255,255,255,0.78)
  - Border top: rgba(0,0,0,0.12), sides: rgba(0,0,0,0.05)
  - Inner highlight: rgba(255,255,255,0.90)
  - Text primary: #0D0D0D, secondary: rgba(0,0,0,0.65)
  - Pill fill: rgba(255,255,255,0.75), pill border: rgba(0,0,0,0.10)
Accent colour (both themes): #1579BE

LOGO RULES:
- Dark theme → white/light logo (use asset_path from resolve_logo_asset)
- Light theme → dark logo (use asset_path from resolve_logo_asset)
- Logo always placed in glass pill at top-centre, y=72px from canvas top

CANVAS SPECS:
- Size: 1080×1080px
- Safe zone: 72px inset on all sides (elements should not enter this zone)
- Base unit: 8px grid (all positions and sizes should be multiples of 8)
- Glass card: typically x=108, y=300-400, width=864, height=480-560

BACKGROUND SPEC:
- Dark theme: library_path="assets/backgrounds/dark/", luminance_target=0.35
- Light theme: library_path="assets/backgrounds/light/", luminance_target=0.80
- Include a specific mood_modifier relevant to the brief content

TYPOGRAPHY:
- Headline: Urbanist-ExtraBold.ttf, 52-72pt
- Stat (large number): Urbanist-ExtraBold.ttf, 60-96pt
- Subheading: Urbanist-Bold.ttf, 36-48pt
- Body: Oxanium-Regular.ttf or Oxanium-Medium.ttf, 18-28pt
- Caption/label: Oxanium-Medium.ttf, 14-16pt
- All font paths are relative: assets/fonts/[filename].ttf

OUTPUT FORMAT:
After write_layout_plan returns with state=GENERATING, output a brief human-readable
summary of the plan (2-3 sentences maximum).
"""


class PlannerAgent(Agent):
    """
    Planner Agent — translates a brief into a pixel-exact LayoutPlan.

    Constructor signature: (db_logger, llm_client, config).
    The ChromaDB singleton is acquired internally.
    """

    SYSTEM_PROMPT = PLANNER_SYSTEM_PROMPT

    def __init__(self, db_logger, llm_client, config, chroma_client=None):
        if chroma_client is None:
            from backend.storage.chromadb_client import get_chroma_client
            chroma_client = get_chroma_client()

        self.config = config
        skills = [
            QueryBrandKnowledge(db_logger=db_logger, chroma_client=chroma_client),
            QueryAgentMemory(db_logger=db_logger, chroma_client=chroma_client),
            AskClarification(db_logger=db_logger, agent_name="planner"),
            EstimateTextDimensions(db_logger=db_logger, agent_name="planner"),
            ResolveLogoAsset(db_logger=db_logger, agent_name="planner"),
            CalculateLayout(db_logger=db_logger, agent_name="planner"),
            WriteLayoutPlan(db_logger=db_logger, agent_name="planner"),
        ]
        super().__init__(
            name="planner",
            system_prompt=self.SYSTEM_PROMPT,
            skills=skills,
            llm_client=llm_client,
        )

    def plan(self, session_id: str, brief: dict) -> "AgentResult":
        """Entry point. Runs the reasoning loop with the user brief."""
        context = f"""Brief for new social post:
Theme: {brief.get('theme', 'dark')}
Logo type: {brief.get('logo_type', 'nowpurchase')}
Post type: {brief.get('purpose', 'announcement')}
Emotion: {brief.get('emotion', 'neutral')}
Headline: {brief.get('headline', '')}
Body copy: {brief.get('body_copy', 'None')}
Stat: {brief.get('stat', 'None')}
Attribution: {brief.get('attribution', 'None')}
CTA: {brief.get('cta', 'None')}

Produce the complete pixel-level layout plan following your mandatory sequence.
"""
        return self.run(session_id=session_id, context=context)


# Keep factory alias for pipeline code that already uses it
def build_planner_agent(db_logger, llm_client, config, chroma_client=None) -> PlannerAgent:
    return PlannerAgent(
        db_logger=db_logger,
        llm_client=llm_client,
        config=config,
        chroma_client=chroma_client,
    )
