"""
Critic Skills — six skills used exclusively by the Critic Agent.

1. AnalyzeVisualCompliance — score image vs the 14-point checklist (Claude vision)
2. CheckTextLegibility     — WCAG AA contrast check for every text element
3. CheckLuminanceZones     — verify luminance inside the glass card zone
4. ScoreAndReport          — aggregate everything into a final compliance report
5. WriteCorrectsBrief      — produce a correction brief for failed evaluations
6. LogCompliancePattern    — record the result in agent_memory
"""

import base64
import io
import json
import os
import re
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from backend.core.skills.base import Skill


# Session-scoped registry — score_and_report writes here, the Pipeline reads
# it back without round-tripping through the LLM's free-text output.
_compliance_store: dict[str, dict] = {}


def get_compliance(session_id: str) -> dict | None:
    return _compliance_store.get(session_id)


def _project_root() -> Path:
    candidate = Path(__file__).resolve()
    for _ in range(6):
        candidate = candidate.parent
        if (candidate / "brand_config.json").exists():
            return candidate
    return Path(__file__).resolve().parent.parent.parent.parent


def _parse_color(s: str) -> tuple:
    s = s.strip()
    if s.startswith("#"):
        s = s.lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
    m = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)", s
    )
    if m:
        r, g, b = int(m[1]), int(m[2]), int(m[3])
        a = int(float(m[4]) * 255) if m[4] else 255
        return (r, g, b, a)
    return (255, 255, 255, 255)


def _relative_luminance(rgb: tuple) -> float:
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    R, G, B = lin(rgb[0]), lin(rgb[1]), lin(rgb[2])
    return 0.2126 * R + 0.7152 * G + 0.0722 * B


def _contrast_ratio(l1: float, l2: float) -> float:
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ── 1. AnalyzeVisualCompliance ───────────────────────────────────────────────

class AnalyzeVisualCompliance(Skill):
    """Score the image against the 14-point compliance checklist via Claude vision."""

    @property
    def name(self) -> str:
        return "analyze_visual_compliance"

    @property
    def description(self) -> str:
        return (
            "Analyze a generated post image against the 14-point compliance "
            "checklist using Claude vision. Returns per-criterion scores and notes."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "layout_plan": {"type": "object"},
                "theme": {"type": "string", "enum": ["dark", "light"]},
            },
            "required": ["image_path", "layout_plan", "theme"],
        }

    def _execute(self, image_path: str, layout_plan: dict, theme: str) -> dict:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("ascii")

        if theme == "dark":
            bg_theme_desc = "Background is industrial/foundry/factory imagery"
            bg_mood_desc = "Background is dark/moody, not bright/cheerful"
            palette_desc = "Color palette: navy/dark + blue accent only"
            hierarchy_desc = "Visual hierarchy clear on dark glass surface"
        else:
            bg_theme_desc = "Background is clean minimal industrial imagery"
            bg_mood_desc = "Background is light/airy, not dark/heavy"
            palette_desc = "Color palette: white/grey + blue accent only"
            hierarchy_desc = "Visual hierarchy clear on light glass surface"

        prompt = f"""You are analyzing a NowPurchase social media post for brand compliance.
Theme: {theme}

Score each criterion below from 0 to its max score.
Be precise — low scores need specific reasons.
Return ONLY valid JSON in this exact structure:
{{
  "criteria": {{
    "logo_present":        {{"score": X, "max": 7,  "notes": "..."}},
    "logo_in_glass_pill":  {{"score": X, "max": 6,  "notes": "..."}},
    "logo_variant_correct":{{"score": X, "max": 5,  "notes": "..."}},
    "text_in_glass":       {{"score": X, "max": 10, "notes": "..."}},
    "glass_depth_visible": {{"score": X, "max": 5,  "notes": "..."}},
    "no_bare_text":        {{"score": X, "max": 5,  "notes": "..."}},
    "brand_blue_used":     {{"score": X, "max": 5,  "notes": "..."}},
    "headline_readable":   {{"score": X, "max": 7,  "notes": "..."}},
    "no_element_overlap":  {{"score": X, "max": 5,  "notes": "..."}},
    "text_contrast_wcag":  {{"score": X, "max": 5,  "notes": "..."}},
    "bg_theme_correct":    {{"score": X, "max": 10, "notes": "{bg_theme_desc}"}},
    "bg_mood_correct":     {{"score": X, "max": 8,  "notes": "{bg_mood_desc}"}},
    "color_palette":       {{"score": X, "max": 12, "notes": "{palette_desc}"}},
    "visual_hierarchy":    {{"score": X, "max": 10, "notes": "{hierarchy_desc}"}}
  }}
}}"""

        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )

        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        },
                    ],
                }
            ],
        )
        raw = response.choices[0].message.content or "{}"
        # Strip code fences if present
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        json_text = m.group(0) if m else raw
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            parsed = {"criteria": {}}

        if "criteria" not in parsed:
            parsed = {"criteria": parsed}
        parsed["theme"] = theme
        return parsed


# ── 2. CheckTextLegibility ───────────────────────────────────────────────────

class CheckTextLegibility(Skill):
    """Sample text-vs-background contrast at each text element. WCAG AA check."""

    @property
    def name(self) -> str:
        return "check_text_legibility"

    @property
    def description(self) -> str:
        return (
            "Sample contrast ratios between text elements and their glass card "
            "background. Validates WCAG AA compliance (>=4.5:1 normal, >=3.0:1 large)."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "text_elements": {"type": "array", "items": {"type": "object"}},
                "theme": {"type": "string", "enum": ["dark", "light"]},
            },
            "required": ["image_path", "text_elements", "theme"],
        }

    def _execute(
        self,
        image_path: str,
        text_elements: list,
        theme: str,
    ) -> dict:
        img = np.asarray(Image.open(image_path).convert("RGB"))
        h, w = img.shape[:2]
        results: dict = {}

        for el in text_elements:
            eid = el.get("id", "unknown")
            pos = el.get("position", {})
            card = el.get("card_bounds") or {}
            rel = pos.get("relative_to")
            rx = pos.get("x", 0)
            ry = pos.get("y", 0)

            if rel == "glass_card":
                px = int(card.get("x", 0)) + (int(rx) if rx != "center" else card.get("width", 0) // 2)
                py = int(card.get("y", 0)) + int(ry)
            else:
                px = w // 2 if rx == "center" else int(rx)
                py = int(ry)

            px = max(2, min(w - 3, px))
            py = max(2, min(h - 3, py))
            patch = img[py - 2 : py + 3, px - 2 : px + 3]
            bg_color = tuple(int(c) for c in patch.reshape(-1, 3).mean(axis=0))

            text_rgba = _parse_color(el.get("color") or "#FFFFFF")
            text_rgb = text_rgba[:3]
            l_text = _relative_luminance(text_rgb)
            l_bg = _relative_luminance(bg_color)
            ratio = _contrast_ratio(l_text, l_bg)

            try:
                font_size = int(el.get("size") or 16)
            except (TypeError, ValueError):
                font_size = 16
            large_text = font_size >= 24
            threshold = 3.0 if large_text else 4.5
            passes = ratio >= threshold

            results[eid] = {
                "contrast_ratio": round(ratio, 2),
                "passes_wcag_aa": passes,
                "text_color_sample": list(text_rgb),
                "bg_color_sample": list(bg_color),
                "threshold": threshold,
                "large_text": large_text,
            }

        return results


# ── 3. CheckLuminanceZones ───────────────────────────────────────────────────

class CheckLuminanceZones(Skill):
    """Verify the luminance inside the glass card region matches the theme target."""

    @property
    def name(self) -> str:
        return "check_luminance_zones"

    @property
    def description(self) -> str:
        return (
            "Verify background luminance in the glass card zone meets theme "
            "requirements. Dark mode card zone must be <= 0.50; light mode >= 0.65."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "image_path": {"type": "string"},
                "glass_card_bounds": {"type": "object"},
                "theme": {"type": "string", "enum": ["dark", "light"]},
            },
            "required": ["image_path", "glass_card_bounds", "theme"],
        }

    def _execute(
        self,
        image_path: str,
        glass_card_bounds: dict,
        theme: str,
    ) -> dict:
        img = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.float32) / 255.0
        x = int(glass_card_bounds.get("x", 108))
        y = int(glass_card_bounds.get("y", 300))
        ww = int(glass_card_bounds.get("width", 864))
        hh = int(glass_card_bounds.get("height", 500))

        H, W = img.shape[:2]
        x = max(0, min(W - 1, x))
        y = max(0, min(H - 1, y))
        x2 = max(x + 1, min(W, x + ww))
        y2 = max(y + 1, min(H, y + hh))

        crop = img[y:y2, x:x2]
        lum = 0.299 * crop[:, :, 0] + 0.587 * crop[:, :, 1] + 0.114 * crop[:, :, 2]
        card_luminance = float(np.mean(lum))

        if theme == "dark":
            threshold = 0.50
            passed = card_luminance <= threshold
        else:
            threshold = 0.65
            passed = card_luminance >= threshold

        return {
            "passed": passed,
            "card_luminance": round(card_luminance, 3),
            "threshold": threshold,
            "theme": theme,
        }


# ── 4. ScoreAndReport ────────────────────────────────────────────────────────

class ScoreAndReport(Skill):
    """Aggregate criterion scores + zones + legibility into a final report."""

    @property
    def name(self) -> str:
        return "score_and_report"

    @property
    def description(self) -> str:
        return (
            "Aggregate criterion scores, luminance, and legibility results into a "
            "final 0-100 compliance report with pass/fail and issues list."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "criteria_results": {"type": "object"},
                "luminance_results": {"type": "object"},
                "legibility_results": {"type": "object"},
            },
            "required": ["criteria_results", "luminance_results", "legibility_results"],
        }

    def _execute(
        self,
        criteria_results: dict | None = None,
        luminance_results: dict | None = None,
        legibility_results: dict | None = None,
    ) -> dict:
        # Defensive: LLMs sometimes pass primitives (bool/str) for these args.
        if not isinstance(criteria_results, dict):
            criteria_results = {}
        if not isinstance(luminance_results, dict):
            luminance_results = {"passed": True}
        if not isinstance(legibility_results, dict):
            legibility_results = {}

        criteria = criteria_results.get("criteria", criteria_results)
        if not isinstance(criteria, dict):
            criteria = {}

        def _score(c):
            if isinstance(c, dict):
                try:
                    return int(c.get("score", 0))
                except (TypeError, ValueError):
                    return 0
            return 0

        def _max(c):
            if isinstance(c, dict):
                try:
                    return int(c.get("max", 0))
                except (TypeError, ValueError):
                    return 0
            return 0

        total_score = sum(_score(c) for c in criteria.values())
        max_score = sum(_max(c) for c in criteria.values()) or 100

        passed = total_score >= 80

        issues: list[str] = [
            f"{name}: {data.get('notes', '')}"
            for name, data in criteria.items()
            if isinstance(data, dict) and _score(data) < _max(data) * 0.7
        ]

        if not luminance_results.get("passed", True):
            issues.append(f"Background luminance out of range: {luminance_results}")

        wcag_failures = []
        for eid, v in legibility_results.items():
            if not isinstance(v, dict):
                continue
            if not v.get("passes_wcag_aa", True):
                ratio = v.get("contrast_ratio", 0)
                try:
                    ratio = float(ratio)
                except (TypeError, ValueError):
                    ratio = 0.0
                wcag_failures.append(f"Text legibility: {eid} contrast={ratio:.1f}:1")
        issues.extend(wcag_failures)

        report = {
            "total_score": total_score,
            "max_score": max_score,
            "passed": passed,
            "issues": issues,
            "criteria_detail": criteria,
            "summary": f"Score: {total_score}/{max_score} ({'PASS' if passed else 'FAIL'})",
        }
        if self._current_session_id:
            _compliance_store[self._current_session_id] = report
        return report


# ── 5. WriteCorrectsBrief ────────────────────────────────────────────────────

class WriteCorrectsBrief(Skill):
    """Produce a correction brief from a failed compliance report."""

    @property
    def name(self) -> str:
        return "write_correction_brief"

    @property
    def description(self) -> str:
        return (
            "Generate a correction brief from a failed compliance report to guide "
            "the next Planner iteration. Lists specific, actionable corrections."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "compliance_report": {"type": "object"},
                "original_layout_plan": {"type": "object"},
            },
            "required": ["compliance_report", "original_layout_plan"],
        }

    def _execute(
        self,
        compliance_report: dict,
        original_layout_plan: dict,
    ) -> dict:
        criteria = compliance_report.get("criteria_detail", {})
        instructions: list[str] = []

        def score(key: str) -> int:
            return int(criteria.get(key, {}).get("score", 0))

        if score("logo_in_glass_pill") < 4:
            instructions.append(
                "LOGO: Ensure logo pill is centered at top. "
                "Pill must use glass blur + border. Logo must not touch pill edges."
            )
        if score("glass_depth_visible") < 3:
            instructions.append(
                "GLASS: Increase glass depth. Reduce fill opacity. "
                "Ensure background blur is visible through card."
            )
        if score("bg_theme_correct") < 7:
            instructions.append(
                "BACKGROUND: Regenerate background. "
                f"Theme: {original_layout_plan.get('theme', 'dark')}. "
                "Must match industrial foundry or factory environment."
            )
        if score("headline_readable") < 5:
            instructions.append(
                "HEADLINE: Increase font size or reduce text length. "
                "Headline must be readable at 200px preview."
            )
        if score("text_in_glass") < 7:
            instructions.append(
                "LAYOUT: All text must be inside glass card. "
                "No text may appear directly on background."
            )

        if instructions:
            brief = "\n".join(f"- {i}" for i in instructions)
        else:
            brief = "Minor refinements only. Focus on improving overall polish."

        return {"correction_brief": brief, "issue_count": len(instructions)}


# ── 6. LogCompliancePattern ──────────────────────────────────────────────────

class LogCompliancePattern(Skill):
    """Log a compliance result into agent_memory after critique scoring."""

    @property
    def name(self) -> str:
        return "log_compliance_pattern"

    @property
    def description(self) -> str:
        return (
            "Store a compliance pattern in agent_memory after scoring. "
            "Records theme + logo_type + post_type tags for filtered future retrieval."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "score": {"type": "integer"},
                "post_type": {"type": "string"},
                "theme": {"type": "string", "enum": ["dark", "light"]},
                "logo_type": {
                    "type": "string",
                    "enum": ["nowpurchase", "metalcloud", "combined"],
                },
                "issues": {"type": "array", "items": {"type": "string"}},
                "session_id": {
                    "type": "string",
                    "description": "Optional. Defaults to the current session.",
                },
            },
            "required": ["score", "post_type", "theme", "logo_type", "issues"],
        }

    def _execute(
        self,
        score: int,
        post_type: str,
        theme: str,
        logo_type: str,
        issues: list,
        session_id: str | None = None,
    ) -> dict:
        from backend.storage.chromadb_client import get_chroma_client
        session_id = session_id or self._current_session_id

        client = get_chroma_client()
        joined = "; ".join(issues[:3]) if issues else "none"
        doc = (
            f"For {theme} mode {post_type} post with {logo_type} logo, "
            f"compliance score was {score}/100. Main issues: {joined}."
        )
        doc_id = client.add_document(
            collection="agent_memory",
            document=doc,
            metadata={
                "memory_type": "compliance_pattern",
                "post_type": post_type,
                "theme": theme,
                "logo_type": logo_type,
                "compliance_score": score,
                "session_id": session_id,
                "added_by": "agent:critic_agent",
            },
        )
        return {"logged": True, "score": score, "id": doc_id}
