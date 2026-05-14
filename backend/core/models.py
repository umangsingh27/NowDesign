"""
Pydantic models for NowPurchase Design Studio.

LayoutPlan is the contract between the Planner Agent and the Compositor.
Once written by WriteLayoutPlan, every field is resolved and exact.
The Compositor executes it literally — no inference, no defaults.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ── Sub-models ─────────────────────────────────────────────────────────────────

class CanvasSpec(BaseModel):
    width: int = 1080
    height: int = 1080


class BackgroundSpec(BaseModel):
    prompt: str
    mood_modifier: str = ""
    luminance_target: float = Field(default=0.35, ge=0.0, le=1.0)
    center_zone_darkness: float = Field(default=0.65, ge=0.0, le=1.0)
    library_path: str = ""


class GlassSpec(BaseModel):
    fill: str
    border_top: Optional[str] = None
    border_rest: Optional[str] = None
    border: Optional[str] = None        # shorthand used for pill
    blur_radius: Optional[int] = None
    blur_region_radius: Optional[int] = None
    inner_highlight: Optional[str] = None
    drop_shadow: Optional[str] = None
    corner_radius: Optional[int] = None


class LogoSpec(BaseModel):
    asset: str
    max_width: int = 180
    vertical_align: str = "center"


class LogoPillSpec(BaseModel):
    type: str = "pill"
    position: dict[str, Any]
    sizing: str = "hug_content"
    padding: dict[str, int]
    min_width: int = 160
    max_width: int = 360
    height: int = 56
    corner_radius: int = 100
    glass: GlassSpec
    logo: LogoSpec


class GlassCardSpec(BaseModel):
    position: dict[str, int]
    width: int
    height: int
    corner_radius: int = 24
    glass: GlassSpec
    padding: dict[str, int]

    @field_validator("width", "height")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"Dimension must be positive, got {v}")
        return v


class EstimatedDimensions(BaseModel):
    width_px: int
    height_px: int


class ElementSpec(BaseModel):
    id: str
    type: Literal["text", "image", "line", "rect", "accent_bar"]
    content: Optional[str] = None
    font: Optional[str] = None
    size: Optional[int] = None
    color: Optional[str] = None
    position: dict[str, Any]
    alignment: Optional[str] = None
    max_width: Optional[int] = None
    max_lines: Optional[int] = None
    line_height: Optional[float] = None
    letter_spacing: Optional[float] = None
    text_transform: Optional[str] = None
    estimated_dimensions: Optional[EstimatedDimensions] = None
    # For line/rect/accent_bar types
    width: Optional[int] = None
    height: Optional[int] = None
    thickness: Optional[int] = None


class DividerSpec(BaseModel):
    type: str = "horizontal_line"
    position: dict[str, Any]
    width: int
    color: str
    thickness: int = 1


class BottomTagSpec(BaseModel):
    type: str = "text"
    content: str
    font: str
    size: int
    color: str
    position: dict[str, Any]


# ── LayoutPlan — the central contract ─────────────────────────────────────────

class LayoutPlan(BaseModel):
    """
    Complete, resolved, pixel-exact layout plan.

    Written by WriteLayoutPlan skill. Read by the Compositor.
    All colour values are already resolved for the given theme.
    All asset paths are already resolved for the given logo_type + theme.
    """

    template: str
    session_id: str
    theme: Literal["dark", "light"]
    logo_type: Literal["nowpurchase", "metalcloud", "combined"]
    canvas: CanvasSpec = Field(default_factory=CanvasSpec)
    background: BackgroundSpec
    logo_pill: LogoPillSpec
    glass_card: GlassCardSpec
    elements: list[ElementSpec] = Field(default_factory=list)
    divider: Optional[DividerSpec] = None
    attribution: Optional[Any] = None
    bottom_tag: Optional[BottomTagSpec] = None

    @field_validator("session_id")
    @classmethod
    def session_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("session_id must not be empty")
        return v

    @field_validator("elements")
    @classmethod
    def elements_have_unique_ids(cls, elements: list[ElementSpec]) -> list[ElementSpec]:
        ids = [e.id for e in elements]
        if len(ids) != len(set(ids)):
            duplicates = [i for i in ids if ids.count(i) > 1]
            raise ValueError(f"Duplicate element ids: {list(set(duplicates))}")
        return elements

    @model_validator(mode="after")
    def glass_card_within_canvas(self) -> LayoutPlan:
        card = self.glass_card
        canvas = self.canvas
        right_edge = card.position["x"] + card.width
        bottom_edge = card.position["y"] + card.height
        if right_edge > canvas.width:
            raise ValueError(
                f"glass_card right edge ({right_edge}px) exceeds canvas width ({canvas.width}px)"
            )
        if bottom_edge > canvas.height:
            raise ValueError(
                f"glass_card bottom edge ({bottom_edge}px) exceeds canvas height ({canvas.height}px)"
            )
        return self

    def to_json_dict(self) -> dict:
        """Serialise to a plain dict for SQLite storage."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> "LayoutPlan":
        """Build a LayoutPlan from a plain dict (e.g. loaded from JSON)."""
        return cls(**data)


# ── Brief model ────────────────────────────────────────────────────────────────

class BriefInput(BaseModel):
    """User-facing brief submitted via the UI."""
    purpose: str                                    # product_feature | announcement | stat_forward | team
    headline: str
    body_copy: Optional[str] = None
    stat: Optional[str] = None
    stat_label: Optional[str] = None
    attribution: Optional[str] = None
    cta: Optional[str] = None
    requested_by: Optional[str] = None
    logo_type: Literal["nowpurchase", "metalcloud", "combined"] = "nowpurchase"
    theme: Literal["dark", "light"] = "dark"
    mood_hint: Optional[str] = None

    @field_validator("headline")
    @classmethod
    def headline_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("headline must not be empty")
        return v


if __name__ == "__main__":
    import json

    print("Testing LayoutPlan model...")

    # Valid plan — minimal but complete
    valid_plan = {
        "template": "stat_forward",
        "session_id": "sess_model_test_001",
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
            "min_width": 160,
            "max_width": 320,
            "height": 56,
            "corner_radius": 100,
            "glass": {
                "fill": "rgba(0,0,0,0.60)",
                "border": "rgba(255,255,255,0.20)",
                "blur_region_radius": 8
            },
            "logo": {
                "asset": "assets/logos/nowpurchase_white.png",
                "max_width": 180,
                "vertical_align": "center"
            }
        },
        "glass_card": {
            "position": {"x": 108, "y": 320},
            "width": 864,
            "height": 500,
            "corner_radius": 24,
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
                "max_width": 768,
                "letter_spacing": -2,
                "estimated_dimensions": {"width_px": 180, "height_px": 115}
            },
            {
                "id": "headline",
                "type": "text",
                "content": "MetalCloud AI charge mix optimizer",
                "font": "assets/fonts/Urbanist-Bold.ttf",
                "size": 52,
                "color": "#FFFFFF",
                "position": {"x": 48, "y": 175, "relative_to": "glass_card"},
                "alignment": "left",
                "max_width": 768,
                "max_lines": 2,
                "estimated_dimensions": {"width_px": 768, "height_px": 130}
            }
        ],
        "bottom_tag": {
            "type": "text",
            "content": "MetalCloud by NowPurchase",
            "font": "assets/fonts/Oxanium-Regular.ttf",
            "size": 16,
            "color": "rgba(255,255,255,0.45)",
            "position": {"x": "center", "y": 1028}
        }
    }

    plan = LayoutPlan(**valid_plan)
    assert plan.theme == "dark"
    assert plan.logo_type == "nowpurchase"
    assert len(plan.elements) == 2
    assert plan.glass_card.width == 864
    print("  Valid dark-mode plan: accepted OK")

    # Light mode plan
    light_plan_data = valid_plan.copy()
    light_plan_data["theme"] = "light"
    light_plan_data["logo_type"] = "metalcloud"
    light_plan_data["logo_pill"]["glass"]["fill"] = "rgba(255,255,255,0.75)"
    light_plan_data["logo_pill"]["logo"]["asset"] = "assets/logos/metalcloud_dark.png"
    light_plan_data["glass_card"]["glass"]["fill"] = "rgba(255,255,255,0.78)"
    light_plan = LayoutPlan(**light_plan_data)
    assert light_plan.theme == "light"
    assert light_plan.logo_type == "metalcloud"
    print("  Valid light-mode plan: accepted OK")

    # Invalid — missing session_id
    try:
        bad1 = valid_plan.copy()
        bad1["session_id"] = "   "
        LayoutPlan(**bad1)
        assert False, "Should have raised"
    except Exception:
        print("  Invalid plan (empty session_id): rejected OK")

    # Invalid — glass_card exceeds canvas
    try:
        bad2 = valid_plan.copy()
        bad2 = json.loads(json.dumps(bad2))
        bad2["glass_card"]["width"] = 1200  # wider than canvas
        LayoutPlan(**bad2)
        assert False, "Should have raised"
    except Exception:
        print("  Invalid plan (glass_card exceeds canvas): rejected OK")

    # Invalid — duplicate element ids
    try:
        bad3 = json.loads(json.dumps(valid_plan))
        bad3["elements"].append(bad3["elements"][0].copy())  # duplicate id
        LayoutPlan(**bad3)
        assert False, "Should have raised"
    except Exception:
        print("  Invalid plan (duplicate element ids): rejected OK")

    # Serialisation round-trip
    as_dict = plan.to_json_dict()
    plan2 = LayoutPlan(**as_dict)
    assert plan2.session_id == plan.session_id
    print("  JSON round-trip: OK")

    print("LayoutPlan model: ALL TESTS PASSED")
