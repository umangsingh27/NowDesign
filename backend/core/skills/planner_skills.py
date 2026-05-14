"""
Planner Skills — the five skills used exclusively by the Planner Agent.

1. AskClarification       — suspend pipeline, emit questions via SSE, return to resume
2. EstimateTextDimensions — measure rendered text with Pillow (fallback if fonts absent)
3. ResolveLogoAsset       — look up brand_config.logos[logo_type][theme], validate file
4. CalculateLayout        — validate element placement: overlaps + safe-zone violations
5. WriteLayoutPlan        — validate plan dict against LayoutPlan model, persist to SQLite
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

from PIL import ImageFont, Image, ImageDraw

from backend.core.skills.base import Skill
from backend.core.models import LayoutPlan
from backend.core.session_events import EventBusRegistry


# ── Utility: locate brand_config.json ─────────────────────────────────────────

def _load_brand_config() -> dict:
    """
    Find and load brand_config.json.
    Searches from this file's location upward until found.
    """
    candidate = Path(__file__).resolve()
    for _ in range(6):
        candidate = candidate.parent
        config_path = candidate / "brand_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        "brand_config.json not found in any ancestor directory of planner_skills.py"
    )


# ── 1. AskClarification ───────────────────────────────────────────────────────

class AskClarification(Skill):
    """
    Suspend the pipeline and ask the user clarifying questions.

    Behaviour:
      1. Emits a 'dialogue' SSE event via the session's EventBus.
      2. Updates the session state to DIALOGUE in SQLite.
      3. Returns immediately with status='dialogue_triggered'.
         The pipeline orchestrator is responsible for blocking on the dialogue gate.

    The skill does NOT block — that keeps it independently testable.
    The pipeline calls EventBus.wait_for_dialogue_answers() after this skill returns.
    """

    @property
    def name(self) -> str:
        return "ask_clarification"

    @property
    def description(self) -> str:
        return (
            "Ask the user clarifying questions before producing a layout plan. "
            "Use when the brief is ambiguous about content, context, or target audience. "
            "Pass a list of specific, answerable questions. "
            "The pipeline will pause and resume once the user answers. "
            "Only call this once per session — bundle all questions into one call."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of specific questions to ask the user.",
                    "minItems": 1,
                    "maxItems": 5
                }
            },
            "required": ["questions"]
        }

    def _execute(self, questions: list[str]) -> dict:
        session_id = self._current_session_id

        # Update session state to DIALOGUE in SQLite
        self.db_logger.log_session_update(session_id, state="DIALOGUE")

        # Log the conversation messages (one per question)
        import uuid
        for q in questions:
            self.db_logger.log_conversation_message(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                phase="DIALOGUE",
                role="agent",
                content=q,
                metadata={"skill": "ask_clarification"}
            )

        # Emit SSE event to frontend (if bus exists)
        bus = EventBusRegistry.get(session_id)
        if bus is not None:
            bus.emit("dialogue", {
                "questions": questions,
                "count": len(questions),
                "session_id": session_id
            })

        return {
            "status": "dialogue_triggered",
            "questions": questions,
            "count": len(questions),
            "session_id": session_id
        }


# ── 2. EstimateTextDimensions ─────────────────────────────────────────────────

class EstimateTextDimensions(Skill):
    """
    Measure the rendered pixel dimensions of a text string using Pillow.

    Uses ImageFont.getbbox() for accurate measurement when the font file exists.
    Falls back to a character-count heuristic when the font is not yet installed
    (fonts are manually placed by the team after Day 1 setup).

    The Planner uses this to set estimated_dimensions on text elements, enabling
    CalculateLayout to detect overlaps before the Compositor runs.
    """

    @property
    def name(self) -> str:
        return "estimate_text_dimensions"

    @property
    def description(self) -> str:
        return (
            "Estimate the pixel width and height of rendered text. "
            "Pass the exact text string, font file path (relative to project root), "
            "font size in points, and the maximum container width. "
            "Returns width_px, height_px, line_count, and actual_font_size. "
            "Call this for every text element before calling calculate_layout."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The exact text string to measure."
                },
                "font_path": {
                    "type": "string",
                    "description": "Path to the .ttf font file, e.g. 'assets/fonts/Urbanist-ExtraBold.ttf'."
                },
                "font_size": {
                    "type": "integer",
                    "description": "Font size in points."
                },
                "max_width": {
                    "type": "integer",
                    "description": "Maximum container width in pixels. Used to calculate line wrapping."
                }
            },
            "required": ["text", "font_path", "font_size", "max_width"]
        }

    def _execute(
        self,
        text: str,
        font_path: str,
        font_size: int,
        max_width: int
    ) -> dict:
        # Resolve font path relative to project root (where brand_config.json lives)
        project_root = self._find_project_root()
        abs_font_path = os.path.join(project_root, font_path)

        try:
            font = ImageFont.truetype(abs_font_path, font_size)
            return self._measure_with_font(text, font, font_size, max_width)
        except (OSError, IOError):
            # Font not yet installed — use heuristic fallback
            return self._measure_with_fallback(text, font_size, max_width)

    def _measure_with_font(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        font_size: int,
        max_width: int
    ) -> dict:
        """Measure using real Pillow font metrics."""
        img = Image.new("RGB", (max_width * 2, font_size * 10))
        draw = ImageDraw.Draw(img)

        # Word-wrap the text
        words = text.split()
        lines: list[str] = []
        current_line = ""
        for word in words:
            test_line = (current_line + " " + word).strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] > max_width and current_line:
                lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)

        if not lines:
            lines = [text]

        # Measure each line
        max_line_width = 0
        line_height = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            max_line_width = max(max_line_width, bbox[2] - bbox[0])
            line_height = max(line_height, bbox[3] - bbox[1])

        total_height = int(line_height * len(lines) * 1.25)  # 1.25 line spacing

        return {
            "width_px": min(int(max_line_width), max_width),
            "height_px": total_height,
            "line_count": len(lines),
            "actual_font_size": font_size,
            "source": "pillow_measured"
        }

    def _measure_with_fallback(
        self,
        text: str,
        font_size: int,
        max_width: int
    ) -> dict:
        """
        Character-count heuristic for when font files aren't installed yet.
        Approximately 0.6 × font_size per character width for sans-serif Latin fonts.
        """
        avg_char_width = font_size * 0.6
        chars_per_line = max(1, int(max_width / avg_char_width))
        line_count = max(1, -(-len(text) // chars_per_line))  # ceiling division
        line_height = int(font_size * 1.3)
        estimated_width = min(int(len(text) * avg_char_width), max_width)
        total_height = int(line_height * line_count * 1.25)

        return {
            "width_px": estimated_width,
            "height_px": total_height,
            "line_count": line_count,
            "actual_font_size": font_size,
            "source": "fallback_estimate"
        }

    def _find_project_root(self) -> str:
        candidate = Path(__file__).resolve()
        for _ in range(6):
            candidate = candidate.parent
            if (candidate / "brand_config.json").exists():
                return str(candidate)
        return str(Path(__file__).resolve().parent.parent.parent.parent)


# ── 3. ResolveLogoAsset ───────────────────────────────────────────────────────

class ResolveLogoAsset(Skill):
    """
    Resolve the correct logo file path from brand_config for the given logo_type + theme.

    Returns:
      - asset_path: the relative path from brand_config (e.g. 'assets/logos/nowpurchase_white.png')
      - exists: True if the file is present on disk, False otherwise
      - width_px / height_px: actual dimensions if file exists, 0 if not (logo not yet exported)

    A missing logo file is NOT an error — logos are exported from Figma by the design team
    and may not yet be present. The Compositor will substitute a text fallback in that case.
    """

    @property
    def name(self) -> str:
        return "resolve_logo_asset"

    @property
    def description(self) -> str:
        return (
            "Resolve the logo file path for the given logo_type and theme from brand_config. "
            "Returns the asset_path, whether the file exists on disk, and its dimensions. "
            "Always call this before writing the layout plan to get the correct logo path. "
            "logo_type: 'nowpurchase' | 'metalcloud' | 'combined'. "
            "theme: 'dark' (use white/light logo) | 'light' (use dark logo)."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "logo_type": {
                    "type": "string",
                    "enum": ["nowpurchase", "metalcloud", "combined"],
                    "description": "Which logo to use."
                },
                "theme": {
                    "type": "string",
                    "enum": ["dark", "light"],
                    "description": "Post theme — determines which variant (white vs dark) to use."
                }
            },
            "required": ["logo_type", "theme"]
        }

    def _execute(self, logo_type: str, theme: str) -> dict:
        config = _load_brand_config()
        logos = config.get("logos", {})

        if logo_type not in logos:
            raise ValueError(
                f"Unknown logo_type '{logo_type}'. "
                f"Valid options: {list(logos.keys())}"
            )

        theme_logos = logos[logo_type]
        if theme not in theme_logos:
            raise ValueError(
                f"No '{theme}' variant for logo_type '{logo_type}'. "
                f"Available: {list(theme_logos.keys())}"
            )

        asset_path = theme_logos[theme]

        # Resolve absolute path
        project_root = self._find_project_root()
        abs_path = os.path.join(project_root, "backend", asset_path)

        # Check existence and get dimensions
        if os.path.exists(abs_path):
            try:
                from PIL import Image as PILImage
                with PILImage.open(abs_path) as img:
                    width_px, height_px = img.size
                status = "found"
            except Exception:
                width_px, height_px = 0, 0
                status = "found_unreadable"
        else:
            width_px, height_px = 0, 0
            status = "logo not yet exported (expected)"

        return {
            "asset_path": asset_path,
            "logo_type": logo_type,
            "theme": theme,
            "exists": status == "found",
            "status": status,
            "width_px": width_px,
            "height_px": height_px,
            "note": "Place logo files in backend/assets/logos/ — see LOGOS_REQUIRED.md" if width_px == 0 else ""
        }

    def _find_project_root(self) -> str:
        candidate = Path(__file__).resolve()
        for _ in range(6):
            candidate = candidate.parent
            if (candidate / "brand_config.json").exists():
                return str(candidate)
        return str(Path(__file__).resolve().parent.parent.parent.parent)


# ── 4. CalculateLayout ────────────────────────────────────────────────────────

class CalculateLayout(Skill):
    """
    Validate element placement on the canvas.

    Checks:
      1. All elements are within the safe zone (72px inset by default)
      2. No two text/image elements have overlapping bounding boxes
      3. Glass card is within canvas bounds

    Returns warnings (not errors) — the Planner can adjust or accept.
    The Compositor will render whatever the final plan contains.
    """

    @property
    def name(self) -> str:
        return "calculate_layout"

    @property
    def description(self) -> str:
        return (
            "Validate element placement: safe zone compliance and overlap detection. "
            "Pass all elements with their estimated_dimensions populated. "
            "Returns {valid, warnings, elements} — warnings describe specific violations. "
            "If valid=False, adjust element positions and call again before writing the plan."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "canvas_w": {
                    "type": "integer",
                    "description": "Canvas width in pixels. Default 1080.",
                    "default": 1080
                },
                "canvas_h": {
                    "type": "integer",
                    "description": "Canvas height in pixels. Default 1080.",
                    "default": 1080
                },
                "safe_zone": {
                    "type": "integer",
                    "description": "Safe zone inset in pixels. Default 72.",
                    "default": 72
                },
                "elements": {
                    "type": "array",
                    "description": "List of element specs. Each must have position and estimated_dimensions.",
                    "items": {"type": "object"}
                },
                "glass_card": {
                    "type": "object",
                    "description": "The glass card spec with position, width, height."
                }
            },
            "required": ["elements"]
        }

    def _execute(
        self,
        elements: list[dict],
        canvas_w: int = 1080,
        canvas_h: int = 1080,
        safe_zone: int = 72,
        glass_card: Optional[dict] = None
    ) -> dict:
        warnings: list[str] = []

        # Build absolute bounding boxes for elements that have estimated_dimensions
        element_boxes: list[tuple[str, int, int, int, int]] = []  # (id, x1, y1, x2, y2)

        card_x = glass_card["position"]["x"] if glass_card else 0
        card_y = glass_card["position"]["y"] if glass_card else 0

        for el in elements:
            pos = el.get("position", {})
            dims = el.get("estimated_dimensions")
            if not dims:
                continue

            # Resolve position (handle relative_to glass_card)
            raw_x = pos.get("x", 0)
            raw_y = pos.get("y", 0)
            relative_to = pos.get("relative_to", "canvas")

            if relative_to == "glass_card" and glass_card:
                abs_x = card_x + (raw_x if isinstance(raw_x, (int, float)) else 0)
                abs_y = card_y + (raw_y if isinstance(raw_y, (int, float)) else 0)
            elif isinstance(raw_x, str) and raw_x == "center":
                abs_x = canvas_w // 2 - dims["width_px"] // 2
                abs_y = int(raw_y)
            else:
                abs_x = int(raw_x)
                abs_y = int(raw_y)

            x2 = abs_x + dims["width_px"]
            y2 = abs_y + dims["height_px"]
            element_boxes.append((el.get("id", "?"), abs_x, abs_y, x2, y2))

            # Safe zone check
            if abs_x < safe_zone:
                warnings.append(
                    f"Element '{el.get('id')}' left edge ({abs_x}px) is inside safe zone ({safe_zone}px)"
                )
            if abs_y < safe_zone:
                warnings.append(
                    f"Element '{el.get('id')}' top edge ({abs_y}px) is inside safe zone ({safe_zone}px)"
                )
            if x2 > canvas_w - safe_zone:
                warnings.append(
                    f"Element '{el.get('id')}' right edge ({x2}px) exceeds safe zone boundary ({canvas_w - safe_zone}px)"
                )
            if y2 > canvas_h - safe_zone:
                warnings.append(
                    f"Element '{el.get('id')}' bottom edge ({y2}px) exceeds safe zone boundary ({canvas_h - safe_zone}px)"
                )

        # Overlap detection (O(n²) — fine for ≤ 20 elements)
        for i in range(len(element_boxes)):
            for j in range(i + 1, len(element_boxes)):
                id_a, x1a, y1a, x2a, y2a = element_boxes[i]
                id_b, x1b, y1b, x2b, y2b = element_boxes[j]
                if x1a < x2b and x2a > x1b and y1a < y2b and y2a > y1b:
                    warnings.append(
                        f"Elements '{id_a}' and '{id_b}' overlap"
                    )

        # Glass card bounds check
        if glass_card:
            gx = glass_card["position"]["x"]
            gy = glass_card["position"]["y"]
            gw = glass_card.get("width", 0)
            gh = glass_card.get("height", 0)
            if gx + gw > canvas_w:
                warnings.append(
                    f"glass_card right edge ({gx + gw}px) exceeds canvas width ({canvas_w}px)"
                )
            if gy + gh > canvas_h:
                warnings.append(
                    f"glass_card bottom edge ({gy + gh}px) exceeds canvas height ({canvas_h}px)"
                )

        return {
            "valid": len(warnings) == 0,
            "warnings": warnings,
            "elements_checked": len(element_boxes),
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "safe_zone": safe_zone
        }


# ── 5. WriteLayoutPlan ────────────────────────────────────────────────────────

class WriteLayoutPlan(Skill):
    """
    Validate a layout plan dict against the LayoutPlan Pydantic model
    and persist it to the session record in SQLite.

    On success:
      - Session state is updated to GENERATING
      - layout_plan_json is written to the sessions table
      - Returns the validated plan as a dict

    On failure (validation error):
      - Raises ValueError with the Pydantic error details
      - Session state is NOT changed
    """

    @property
    def name(self) -> str:
        return "write_layout_plan"

    @property
    def description(self) -> str:
        return (
            "Validate and persist the completed layout plan. "
            "Pass the full layout plan as a JSON-serialisable dict. "
            "The plan will be validated against the LayoutPlan schema — "
            "any missing required fields or constraint violations will be reported. "
            "On success, the session transitions to GENERATING state. "
            "Call this only once per attempt, after calculate_layout reports valid=True."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "layout_json": {
                    "type": "object",
                    "description": "The complete layout plan as a JSON object. "
                                   "Must include: template, session_id, theme, logo_type, "
                                   "canvas, background, logo_pill, glass_card, elements."
                }
            },
            "required": ["layout_json"]
        }

    def _execute(self, layout_json: dict) -> dict:
        # Ensure session_id is set (inject from _current_session_id if missing)
        if not layout_json.get("session_id"):
            layout_json = dict(layout_json)
            layout_json["session_id"] = self._current_session_id

        # Validate against Pydantic model — raises on invalid input
        try:
            plan = LayoutPlan(**layout_json)
        except Exception as e:
            raise ValueError(f"LayoutPlan validation failed: {e}") from e

        # Persist to SQLite
        plan_json_str = json.dumps(plan.to_json_dict())
        self.db_logger.log_session_update(
            self._current_session_id,
            state="GENERATING",
            layout_plan_json=plan_json_str
        )

        return {
            "status": "persisted",
            "session_id": plan.session_id,
            "template": plan.template,
            "theme": plan.theme,
            "logo_type": plan.logo_type,
            "element_count": len(plan.elements),
            "state": "GENERATING"
        }


if __name__ == "__main__":
    import sys
    import uuid
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
    from dotenv import load_dotenv
    load_dotenv()
    from backend.storage.sqlite_logger import SQLiteLogger
    from backend.storage.chromadb_client import get_chroma_client
    from backend.core.session_events import EventBusRegistry

    logger = SQLiteLogger()
    SID = f"sess_planner_test_{uuid.uuid4().hex[:8]}"

    # Create session record first
    logger.log_session_create(SID, "BRIEF", {"headline": "test"}, "nowpurchase", "dark", "test")

    print("Testing planner skills...\n")

    # ── AskClarification ────────────────────────────────────────────────
    bus = EventBusRegistry.create(SID)
    ask = AskClarification(db_logger=logger, agent_name="planner")
    result = ask(session_id=SID, questions=["What sector?", "What tone?"])
    assert result.success, f"AskClarification failed: {result.error}"
    assert result.data["status"] == "dialogue_triggered"
    assert result.data["count"] == 2
    events = bus.drain()
    assert len(events) == 1 and events[0].event == "dialogue"
    # Verify state saved to SQLite
    session = logger.get_session(SID)
    assert session["state"] == "DIALOGUE", f"Expected DIALOGUE, got {session['state']}"
    print("AskClarification: dialogue_triggered, 2 questions — state saved to SQLite: OK")

    # ── EstimateTextDimensions ─────────────────────────────────────────
    est = EstimateTextDimensions(db_logger=logger, agent_name="planner")
    result2 = est(
        session_id=SID,
        text="MetalCloud AI reduces scrap by 23%",
        font_path="backend/assets/fonts/Urbanist-ExtraBold.ttf",
        font_size=52,
        max_width=768
    )
    assert result2.success, f"EstimateTextDimensions failed: {result2.error}"
    assert result2.data["width_px"] > 0
    assert result2.data["height_px"] > 0
    print(f"EstimateTextDims: width={result2.data['width_px']}px height={result2.data['height_px']}px "
          f"source={result2.data['source']}: OK")

    # ── ResolveLogoAsset ───────────────────────────────────────────────
    resolve = ResolveLogoAsset(db_logger=logger, agent_name="planner")
    result3 = resolve(session_id=SID, logo_type="nowpurchase", theme="dark")
    assert result3.success, f"ResolveLogoAsset failed: {result3.error}"
    assert result3.data["asset_path"] == "assets/logos/nowpurchase_white.png"
    # Status is either "found" (if logo exported) or "logo not yet exported (expected)"
    print(f"ResolveLogoAsset: status='{result3.data['status']}' asset_path='{result3.data['asset_path']}': OK")

    # Test light mode resolves dark variant
    result3b = resolve(session_id=SID, logo_type="metalcloud", theme="light")
    assert result3b.success
    assert "dark" in result3b.data["asset_path"], "Light mode should resolve dark logo variant"
    print(f"ResolveLogoAsset (light mode): '{result3b.data['asset_path']}': OK")

    # ── CalculateLayout ────────────────────────────────────────────────
    calc = CalculateLayout(db_logger=logger, agent_name="planner")

    # Sub-test 1: valid layout
    result4a = calc(
        session_id=SID,
        elements=[
            {
                "id": "stat",
                "type": "text",
                "position": {"x": 48, "y": 48, "relative_to": "glass_card"},
                "estimated_dimensions": {"width_px": 200, "height_px": 120}
            }
        ],
        glass_card={"position": {"x": 108, "y": 320}, "width": 864, "height": 500}
    )
    assert result4a.success
    assert result4a.data["valid"] is True
    assert len(result4a.data["warnings"]) == 0
    print(f"CalculateLayout (valid): {len(result4a.data['warnings'])} warnings: OK")

    # Sub-test 2: overlapping elements
    result4b = calc(
        session_id=SID,
        elements=[
            {
                "id": "elem_a",
                "type": "text",
                "position": {"x": 108, "y": 320},
                "estimated_dimensions": {"width_px": 500, "height_px": 200}
            },
            {
                "id": "elem_b",
                "type": "text",
                "position": {"x": 200, "y": 380},
                "estimated_dimensions": {"width_px": 400, "height_px": 150}
            }
        ]
    )
    assert result4b.success
    overlap_warnings = [w for w in result4b.data["warnings"] if "overlap" in w.lower()]
    assert len(overlap_warnings) >= 1, f"Expected overlap warning, got: {result4b.data['warnings']}"
    print(f"CalculateLayout (overlap): warns correctly — {overlap_warnings[0][:60]}...: OK")

    # Sub-test 3: safe-zone violation
    result4c = calc(
        session_id=SID,
        elements=[
            {
                "id": "edge_elem",
                "type": "text",
                "position": {"x": 10, "y": 10},
                "estimated_dimensions": {"width_px": 200, "height_px": 100}
            }
        ]
    )
    assert result4c.success
    sz_warnings = [w for w in result4c.data["warnings"] if "safe zone" in w.lower()]
    assert len(sz_warnings) >= 1, f"Expected safe-zone warning, got: {result4c.data['warnings']}"
    print(f"CalculateLayout (safe zone): warns correctly — {sz_warnings[0][:60]}...: OK")

    # ── WriteLayoutPlan ────────────────────────────────────────────────
    write = WriteLayoutPlan(db_logger=logger, agent_name="planner")
    valid_plan = {
        "template": "stat_forward",
        "session_id": SID,
        "theme": "dark",
        "logo_type": "nowpurchase",
        "canvas": {"width": 1080, "height": 1080},
        "background": {
            "prompt": "abstract dark industrial environment",
            "mood_modifier": "blue steel cool tones",
            "luminance_target": 0.35,
            "library_path": "assets/backgrounds/dark/"
        },
        "logo_pill": {
            "type": "pill",
            "position": {"x": "center", "y": 72},
            "sizing": "hug_content",
            "padding": {"horizontal": 24, "vertical": 12},
            "min_width": 160, "max_width": 320, "height": 56, "corner_radius": 100,
            "glass": {"fill": "rgba(0,0,0,0.60)", "border": "rgba(255,255,255,0.20)", "blur_region_radius": 8},
            "logo": {"asset": "assets/logos/nowpurchase_white.png", "max_width": 180, "vertical_align": "center"}
        },
        "glass_card": {
            "position": {"x": 108, "y": 320},
            "width": 864, "height": 500, "corner_radius": 24,
            "glass": {
                "fill": "rgba(0,0,0,0.62)",
                "border_top": "rgba(255,255,255,0.28)",
                "border_rest": "rgba(255,255,255,0.08)",
                "blur_radius": 16,
                "inner_highlight": "rgba(255,255,255,0.18)",
                "drop_shadow": "0 8px 32px rgba(0,0,0,0.45)"
            },
            "padding": {"top": 48, "right": 48, "bottom": 48, "left": 48}
        },
        "elements": [
            {
                "id": "stat_main",
                "type": "text",
                "content": "23%",
                "font": "assets/fonts/Urbanist-ExtraBold.ttf",
                "size": 96,
                "color": "#FFFFFF",
                "position": {"x": 48, "y": 48, "relative_to": "glass_card"},
                "alignment": "left",
                "max_width": 768
            }
        ]
    }
    result5 = write(session_id=SID, layout_json=valid_plan)
    assert result5.success, f"WriteLayoutPlan failed: {result5.error}"
    assert result5.data["state"] == "GENERATING"
    session = logger.get_session(SID)
    assert session["state"] == "GENERATING", f"Expected GENERATING, got {session['state']}"
    assert session["layout_plan_json"] is not None
    print(f"WriteLayoutPlan: persisted to SQLite, state=GENERATING: OK")

    # Invalid plan — rejected
    result5b = write(session_id=SID, layout_json={"template": "bad", "session_id": SID})
    assert not result5b.success
    assert "validation" in result5b.error.lower() or "LayoutPlan" in result5b.error
    print(f"WriteLayoutPlan: invalid plan rejected: OK")

    print("\nLine counts (approximate):")
    print(f"  planner_skills.py: {Path(__file__).read_text(encoding='utf-8').count(chr(10))} lines")
    print("\nAll planner skills: ALL TESTS PASSED")
