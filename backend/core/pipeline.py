"""
NowPurchase Design Studio — Pipeline Orchestrator

Sequences: PlannerAgent -> CreatorAgent -> CriticAgent
Post-approval (non-blocking): LearningAgent

The pipeline runs synchronously in a background thread.
Progress events are pushed to a queue.Queue and consumed
by the FastAPI SSE endpoint via an async generator.

Session states (written to SQLite after each transition):
  BRIEF -> GENERATING -> REVIEW -> APPROVED
  BRIEF -> DIALOGUE  -> GENERATING (when Planner asks questions)
"""

import glob
import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path

import openai

from backend.core.agents import (
    PlannerAgent,
    CreatorAgent,
    CriticAgent,
    LearningAgent,
)
from backend.storage.chromadb_client import get_chroma_client
from backend.storage.sqlite_logger import get_sqlite_logger


# ── Revision classification keyword lists (from plan Section 7) ──────────────

LAYOUT_CHANGE_KEYWORDS = [
    "bigger", "smaller", "font", "size", "move", "position", "spacing",
    "opacity", "darker", "lighter", "color", "align", "padding", "margin",
    "bold", "weight", "centered", "left", "right", "wider", "narrower",
    "shift", "push", "pull", "resize", "scale",
]

CONTENT_CHANGE_KEYWORDS = [
    "headline", "text", "copy", "write", "change the message", "different stat",
    "add a line", "remove", "replace the background", "different background",
    "new image", "regenerate", "rewrite", "update the", "change the text",
    "different photo", "another background",
    "background image", "change the background", "swap the background",
]

LOGO_CHANGE_KEYWORDS = [
    "logo", "metalcloud", "metal cloud", "nowpurchase", "now purchase",
    "combined", "switch logo", "use metalcloud", "use nowpurchase",
    "change logo", "different logo",
]

THEME_CHANGE_KEYWORDS = [
    "light mode", "dark mode", "switch to light", "switch to dark",
    "make it lighter", "make it darker", "white background", "dark background",
    "bright version", "dark version", "flip the theme", "change theme",
]


def classify_revision(message: str) -> str:
    """
    Classify a feedback message. Priority: theme > logo > layout > content.

    Layout signals (bigger/smaller/position) are checked before content because
    phrasings like "make the headline bigger" mention a content word
    ("headline") but are really about visual sizing, not editing the copy.
    """
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in THEME_CHANGE_KEYWORDS):
        return "theme_change"
    if any(kw in msg_lower for kw in LOGO_CHANGE_KEYWORDS):
        return "logo_change"
    if any(kw in msg_lower for kw in LAYOUT_CHANGE_KEYWORDS):
        return "layout_change"
    if any(kw in msg_lower for kw in CONTENT_CHANGE_KEYWORDS):
        return "content_change"
    return "layout_change"


class Pipeline:
    """Orchestrates the full Planner->Creator->Critic loop for a session."""

    def __init__(self):
        self.config = self._load_config()
        self.db = get_sqlite_logger()
        self.llm = openai.OpenAI(
            base_url=os.getenv(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ),
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
        )
        self.planner = PlannerAgent(self.db, self.llm, self.config)
        self.creator = CreatorAgent(self.db, self.llm, self.config)
        self.critic = CriticAgent(self.db, self.llm, self.config)
        self.learner = LearningAgent(self.db, self.llm, self.config)

    def _load_config(self) -> dict:
        config_path = Path("brand_config.json")
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
        return {}

    # ── Event helpers ─────────────────────────────────────────────────────

    def _emit(self, q: queue.Queue, event_type: str, data: dict):
        q.put({"event": event_type, "data": data})

    def _progress(
        self, q: queue.Queue, step: str, pct: int, message: str, theme: str = "dark"
    ):
        self._emit(q, "status_update", {
            "step": step,
            "progress_pct": pct,
            "message": message,
            "theme": theme,
        })

    # ── Session management ────────────────────────────────────────────────

    def _create_session(self, brief: dict) -> str:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        self.db.create_session(
            session_id=session_id,
            brief_json=json.dumps(brief),
            logo_type=brief.get("logo_type", "nowpurchase"),
            theme=brief.get("theme", "dark"),
            requested_by=brief.get("requested_by"),
        )
        return session_id

    def _update_state(self, session_id: str, state: str):
        self.db.update_session_state(session_id, state)

    # ── Core pipeline execution ───────────────────────────────────────────

    def _execute(
        self,
        session_id: str,
        brief: dict,
        q: queue.Queue,
        attempt: int = 1,
        correction_brief: str = None,
        force_bg: bool = False,
    ):
        """Run Planner -> Creator -> Critic once. Emits SSE events throughout."""
        theme = brief.get("theme", "dark")
        logo_type = brief.get("logo_type", "nowpurchase")

        # ── PLANNER ──────────────────────────────────────────────────────
        self._progress(q, "planner", 10,
                       f"Querying brand knowledge (theme: {theme})...", theme)

        planner_context = dict(brief)
        if correction_brief:
            planner_context["_correction_brief"] = correction_brief
        if force_bg:
            planner_context["_force_regenerate_background"] = True

        self._progress(q, "planner", 20,
                       f"Planning pixel-perfect layout ({logo_type} · {theme})...",
                       theme)

        planner_result = self.planner.plan(session_id, planner_context)

        layout_plan = self.db.get_session_layout_plan(session_id)
        if not layout_plan:
            layout_plan = self._extract_layout_from_result(planner_result)

        self._progress(q, "planner", 30, "Layout plan complete.", theme)

        # ── CREATOR ──────────────────────────────────────────────────────
        self._progress(q, "creator", 35,
                       f"Generating background ({theme} industrial · Gemini Imagen 4)...",
                       theme)
        self._progress(q, "creator", 50, "Rendering glass effect...", theme)
        self._progress(q, "creator", 65, "Compositing elements...", theme)

        creator_result = self.creator.create(session_id, layout_plan)
        image_path = self._extract_image_path(creator_result)

        self._progress(q, "creator", 75, "Image composited.", theme)

        # ── CRITIC ───────────────────────────────────────────────────────
        self._progress(q, "critic", 80, "Running quality review...", theme)

        try:
            critic_result = self.critic.critique(
                session_id=session_id,
                image_path=image_path,
                layout_plan=layout_plan,
                theme=theme,
                logo_type=logo_type,
            )
        except Exception as exc:
            print(f"[Critic] critique() raised: {exc}")
            critic_result = None

        # Prefer the structured report the score_and_report skill stored in its
        # session-scoped registry. Fall back to parsing the agent's final text
        # for older flows where the skill didn't persist a report.
        from backend.core.skills.critic_skills import get_compliance
        compliance = get_compliance(session_id)
        if not compliance and critic_result is not None:
            compliance = self._extract_compliance(critic_result)
        if not compliance:
            compliance = {
                "total_score": 75,
                "passed": False,
                "issues": ["Critic produced no parseable report — accepting attempt as-is."],
                "criteria_detail": {},
            }
        score = compliance.get("total_score", 0)

        self._progress(q, "critic", 95,
                       f"Quality review complete. Score: {score}/100", theme)

        self.db.update_session_image(session_id, image_path, score, attempt)

        return {
            "layout_plan": layout_plan,
            "image_path": image_path,
            "compliance": compliance,
            "score": score,
        }

    # ── Public API ────────────────────────────────────────────────────────

    def start(self, brief: dict, event_queue: queue.Queue) -> str:
        """Create a session and start the pipeline in a background thread."""
        session_id = self._create_session(brief)
        self._update_state(session_id, "GENERATING")

        thread = threading.Thread(
            target=self._pipeline_thread,
            args=(session_id, brief, event_queue),
            daemon=True,
        )
        thread.start()
        return session_id

    def _pipeline_thread(
        self, session_id: str, brief: dict, q: queue.Queue
    ):
        """Background thread: runs the full Planner->Creator->Critic loop."""
        theme = brief.get("theme", "dark")
        logo_type = brief.get("logo_type", "nowpurchase")
        max_attempts = int(os.getenv("MAX_PIPELINE_ATTEMPTS", "3"))
        min_score = int(os.getenv("MIN_COMPLIANCE_SCORE", "80"))

        try:
            correction_brief: str | None = None
            best_result: dict | None = None
            best_score = 0

            for attempt in range(1, max_attempts + 1):
                if attempt > 1:
                    self._emit(q, "status_update", {
                        "step": "retry",
                        "progress_pct": 5,
                        "message": (
                            f"Attempt {attempt}/{max_attempts} — "
                            f"applying corrections..."
                        ),
                        "theme": theme,
                    })

                result = self._execute(
                    session_id=session_id,
                    brief=brief,
                    q=q,
                    attempt=attempt,
                    correction_brief=correction_brief,
                    force_bg=(attempt > 1),
                )

                if result["score"] > best_score:
                    best_score = result["score"]
                    best_result = result

                if result["score"] >= min_score:
                    break

                correction_brief = result["compliance"].get("correction_brief")

            image_url = f"/api/assets/image/{session_id}"
            self._emit(q, "image_ready", {
                "image_url": image_url,
                "compliance_score": best_score,
                "attempt": 1 if best_result else max_attempts,
                "theme": theme,
                "logo_type": logo_type,
                "passed": best_score >= min_score,
                "issues": (best_result["compliance"].get("issues", [])
                           if best_result else []),
                "report": (best_result["compliance"]
                           if best_result else {}),
            })

            self._update_state(session_id, "REVIEW")
            self._emit(q, "state_change", {"new_state": "REVIEW"})

        except Exception as exc:
            self._emit(q, "error", {
                "message": str(exc),
                "recoverable": False,
            })
            self._update_state(session_id, "ERROR")
        finally:
            q.put(None)

    def handle_feedback(
        self, session_id: str, message: str, event_queue: queue.Queue
    ):
        """Classify feedback and re-run the pipeline with adjusted brief."""
        revision_type = classify_revision(message)

        self.db.log_conversation_message(
            session_id=session_id,
            phase="REVIEW",
            role="user",
            content=message,
            metadata={"revision_type": revision_type},
        )

        session = self.db.get_session(session_id) or {}
        try:
            brief = json.loads(session.get("brief_json") or "{}")
        except json.JSONDecodeError:
            brief = {}

        msg_lower = message.lower()
        if revision_type == "theme_change":
            if "light" in msg_lower:
                brief["theme"] = "light"
            elif "dark" in msg_lower:
                brief["theme"] = "dark"

        if revision_type == "logo_change":
            if "metalcloud" in msg_lower or "metal cloud" in msg_lower:
                brief["logo_type"] = "metalcloud"
            elif "combined" in msg_lower:
                brief["logo_type"] = "combined"
            elif "nowpurchase" in msg_lower or "now purchase" in msg_lower:
                brief["logo_type"] = "nowpurchase"

        self._update_state(session_id, "GENERATING")

        thread = threading.Thread(
            target=self._pipeline_thread,
            args=(session_id, brief, event_queue),
            daemon=True,
        )
        thread.start()

    def approve(self, session_id: str, user_rating: int) -> dict:
        """Mark session APPROVED and kick off LearningAgent in background."""
        self._update_state(session_id, "APPROVED")
        self.db.update_session_rating(session_id, user_rating)

        thread = threading.Thread(
            target=self._run_learning_agent,
            args=(session_id,),
            daemon=True,
        )
        thread.start()

        return {
            "status": "approved",
            "final_image_url": f"/api/assets/image/{session_id}",
            "learning_agent_status": "running_in_background",
        }

    def _run_learning_agent(self, session_id: str):
        try:
            delay = int(os.getenv("LEARNING_AGENT_DELAY_SECONDS", "2"))
            time.sleep(delay)
            self.learner.learn(session_id)
        except Exception as exc:
            print(f"[LearningAgent] Error in session {session_id}: {exc}")

    # ── Private helpers ───────────────────────────────────────────────────

    def _extract_layout_from_result(self, result) -> dict:
        output = result.output if hasattr(result, "output") else str(result)
        if not output:
            return {}
        try:
            start = output.find("{")
            end = output.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(output[start:end])
        except Exception:
            pass
        return {}

    def _extract_image_path(self, result) -> str:
        output = result.output if hasattr(result, "output") else str(result)
        output = output or ""
        images_path = os.getenv(
            "IMAGES_PATH",
            str(Path("backend") / "storage_data" / "generated_posts"),
        )
        if images_path in output:
            for token in output.replace("\n", " ").split():
                if images_path in token:
                    return token.strip('",\'')
        pattern = os.path.join(images_path, "*_latest.png")
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
        return files[0] if files else ""

    def _extract_compliance(self, result) -> dict:
        output = result.output if hasattr(result, "output") else str(result)
        if not output:
            return {"total_score": 0, "passed": False, "issues": []}
        try:
            start = output.find("{")
            end = output.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(output[start:end])
        except Exception:
            pass
        return {
            "total_score": 0,
            "passed": False,
            "issues": ["Could not parse critic output"],
        }
