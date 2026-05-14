"""
Creator Agent — executes a validated LayoutPlan to produce the final 1080x1080 PNG.

The Creator makes NO creative decisions. The Planner already made them.
All resolved values (colors, asset paths, dimensions) come from the LayoutPlan.
The Creator executes the plan literally, pixel by pixel.
"""

import json

from backend.core.agents.base import Agent
from backend.core.skills.creator_skills import (
    GenerateBackground,
    ValidateBackgroundLuminance,
    RenderGlassEffect,
    RenderTextElement,
    PlaceLogo,
    CompositeFinal,
)


CREATOR_SYSTEM_PROMPT = """You are the Creator Agent for NowPurchase's AI Design Studio.
You receive a validated LayoutPlan and execute it exactly.
You do NOT make creative decisions. The Planner already made them.
The LayoutPlan contains all resolved values (colors, logo path, dimensions).
You execute the plan literally, pixel by pixel.

MANDATORY EXECUTION SEQUENCE:
1. generate_background — use prompt, mood_modifier, theme, library_path from plan.
   Pass force_generate=false (use library if available).
2. validate_background_luminance — must pass. If it fails AND no library fallback
   is available, call generate_background again with force_generate=true.
   Maximum 3 background attempts.
3. render_glass_effect — pass background bytes, glass_card spec, theme.
4. For each element in layout_plan.elements (in z_order):
   render_text_element — pass current canvas + element spec.
   Include card_bounds in each element_spec before calling.
5. place_logo — pass canvas + logo_pill spec from layout plan.
6. composite_final — save to disk, return image path.

IMPORTANT:
- Pass canvas bytes forward through each step (each skill returns updated canvas)
- Never skip validate_background_luminance
- Render elements in z_order (lowest number first)
- If divider is present in layout plan, render it as a text element with
  type="line" after the last text element but before place_logo
"""


class CreatorAgent(Agent):
    """Executes a LayoutPlan into a 1080x1080 PNG via the six creator skills."""

    SYSTEM_PROMPT = CREATOR_SYSTEM_PROMPT

    def __init__(self, db_logger, llm_client, config):
        self.config = config
        skills = [
            GenerateBackground(db_logger=db_logger, agent_name="creator"),
            ValidateBackgroundLuminance(db_logger=db_logger, agent_name="creator"),
            RenderGlassEffect(db_logger=db_logger, agent_name="creator"),
            RenderTextElement(db_logger=db_logger, agent_name="creator"),
            PlaceLogo(db_logger=db_logger, agent_name="creator"),
            CompositeFinal(db_logger=db_logger, agent_name="creator"),
        ]
        super().__init__(
            name="creator",
            system_prompt=self.SYSTEM_PROMPT,
            skills=skills,
            llm_client=llm_client,
        )

    def create(self, session_id: str, layout_plan: dict) -> "AgentResult":
        """Entry point. Executes the LayoutPlan and returns the final image path."""
        context = f"""Execute this layout plan to produce the final 1080x1080 PNG.
Session ID: {session_id}

Layout plan:
{json.dumps(layout_plan, indent=2)}

Follow the mandatory execution sequence exactly.
Return the final image path after composite_final.
"""
        return self.run(session_id=session_id, context=context)


def build_creator_agent(db_logger, llm_client, config) -> CreatorAgent:
    return CreatorAgent(db_logger=db_logger, llm_client=llm_client, config=config)
