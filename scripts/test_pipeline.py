"""
Integration test suite for NowPurchase AI Design Studio.

  python scripts/test_pipeline.py                      # all tests
  python scripts/test_pipeline.py --level 1            # component only
  python scripts/test_pipeline.py --level 2            # agents
  python scripts/test_pipeline.py --level 3            # full pipeline
  python scripts/test_pipeline.py --theme dark --logo nowpurchase
  python scripts/test_pipeline.py --run-all-combinations
"""

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()


PASS = "[OK]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

results: list = []


def check(name: str, fn, skip_if_no_key: str | None = None):
    if skip_if_no_key and not os.getenv(skip_if_no_key):
        print(f"  {SKIP} {name} (skipped - {skip_if_no_key} not set)")
        results.append(("skip", name))
        return None
    try:
        t0 = time.monotonic()
        val = fn()
        elapsed = time.monotonic() - t0
        print(f"  {PASS} {name}  [{elapsed:.1f}s]")
        results.append(("pass", name))
        return val
    except Exception as e:
        print(f"  {FAIL} {name}")
        print(f"       {e}")
        if os.getenv("VERBOSE"):
            traceback.print_exc()
        results.append(("fail", name))
        return None


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)
    return True


# ── LEVEL 1: COMPONENT TESTS ─────────────────────────────────────────────────

def run_level_1():
    print("\n-- Level 1: Component Tests --------------------------------")

    def _sqlite():
        from backend.storage.sqlite_logger import get_sqlite_logger
        return get_sqlite_logger()
    check("SQLite logger imports", _sqlite)

    def _chroma():
        from backend.storage.chromadb_client import get_chroma_client
        return get_chroma_client()
    chroma = check("ChromaDB client imports", _chroma)

    def _entries():
        c = chroma or _chroma()
        entries = c.list_documents("brand_knowledge")
        _assert(len(entries) >= 5,
            f"Expected >=5 brand_knowledge entries, got {len(entries)}")
        return entries
    check("brand_knowledge has entries", _entries)

    def _brand_config():
        cfg = json.loads(Path("brand_config.json").read_text(encoding="utf-8"))
        _assert("logos" in cfg, "Missing 'logos' key")
        _assert("themes" in cfg, "Missing 'themes' key")
        return cfg
    check("brand_config.json loads", _brand_config)

    def _logo():
        _assert(Path("backend/assets/logos/nowpurchase_white.png").exists(),
            "nowpurchase_white.png missing from assets/logos/")
        return True
    check("Nowpurchase white logo exists", _logo)

    def _fonts():
        _assert(Path("backend/assets/fonts/Urbanist-ExtraBold.ttf").exists(),
            "Urbanist-ExtraBold.ttf missing")
        _assert(Path("backend/assets/fonts/Oxanium-Regular.ttf").exists(),
            "Oxanium-Regular.ttf missing")
        return True
    check("Fonts exist", _fonts)

    def _sys_cfg():
        cfg = json.loads(Path("system_config.json").read_text(encoding="utf-8"))
        _assert(cfg.get("glass_renderer") in ("pillow", "playwright"),
            f"Invalid glass_renderer: {cfg.get('glass_renderer')}")
        return cfg
    check("system_config.json valid", _sys_cfg)

    def _playwright_renderer():
        from backend.core.compositor.glass_renderer import PlaywrightGlassRenderer
        return PlaywrightGlassRenderer()
    check("PlaywrightGlassRenderer importable", _playwright_renderer)

    def _pipeline_class():
        from backend.core.pipeline import Pipeline
        return Pipeline
    check("Pipeline importable", _pipeline_class)


# ── LEVEL 2: AGENT TESTS ──────────────────────────────────────────────────────

def run_level_2(theme: str = "dark", logo_type: str = "nowpurchase"):
    print(f"\n-- Level 2: Agent Tests  [{theme} . {logo_type}] -----------")

    import openai
    from backend.storage.sqlite_logger import get_sqlite_logger
    from backend.core.agents import PlannerAgent, CreatorAgent

    client = openai.OpenAI(
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )
    config = json.loads(Path("brand_config.json").read_text(encoding="utf-8"))
    db = get_sqlite_logger()

    session_id = f"test_{int(time.time())}"
    db.create_session(
        session_id=session_id,
        brief_json=json.dumps({"theme": theme, "logo_type": logo_type}),
        logo_type=logo_type,
        theme=theme,
        requested_by="test_script",
    )

    brief = {
        "theme": theme,
        "logo_type": logo_type,
        "purpose": "product_feature",
        "emotion": "professional",
        "headline": "MetalCloud reduces charge mix costs by 18%",
        "stat": "18%",
        "body_copy": "AI-powered optimization across 250+ foundries",
    }

    def _run_planner():
        return PlannerAgent(db, client, config).plan(session_id, brief)
    planner_result = check(
        f"PlannerAgent.plan() [{theme} . {logo_type}]",
        _run_planner,
        skip_if_no_key="OPENROUTER_API_KEY",
    )

    def _get_plan():
        plan = db.get_session_layout_plan(session_id)
        _assert(bool(plan), "Layout plan is empty - WriteLayoutPlan skill may not have run")
        return plan

    layout_plan = check("Layout plan written to SQLite", _get_plan) if planner_result else None

    if not layout_plan:
        print("  [SKIP] Skipping Creator (no layout plan)")
        return session_id

    def _run_creator():
        return CreatorAgent(db, client, config).create(session_id, layout_plan)
    check(
        f"CreatorAgent.create() [{theme} . {logo_type}]",
        _run_creator,
        skip_if_no_key="OPENROUTER_API_KEY",
    )

    def _check_image():
        images_path = Path(os.getenv("IMAGES_PATH",
            "backend/storage_data/generated_posts"))
        files = list(images_path.glob(f"{session_id}*.png"))
        _assert(len(files) > 0,
            f"No PNG files found for session {session_id} in {images_path}")
        print(f"       Image: {files[0]}")
        return files[0]
    check("Image file exists on disk", _check_image)

    return session_id


# ── LEVEL 3: FULL END-TO-END ──────────────────────────────────────────────────

def run_level_3(theme: str = "dark", logo_type: str = "nowpurchase"):
    print(f"\n-- Level 3: Full Pipeline [{theme} . {logo_type}] ----------")

    import queue as q_module
    from backend.core.pipeline import Pipeline

    pipeline = Pipeline()
    event_queue = q_module.Queue()

    brief = {
        "theme": theme,
        "logo_type": logo_type,
        "purpose": "product_feature",
        "emotion": "professional",
        "headline": "MetalCloud reduces charge mix costs by 18%",
        "stat": "18%",
        "body_copy": "AI-powered optimization across 250+ foundries",
        "requested_by": "integration_test",
    }

    def _start():
        return pipeline.start(brief, event_queue)
    session_id = check(
        f"Pipeline.start() [{theme} . {logo_type}]",
        _start,
        skip_if_no_key="OPENROUTER_API_KEY",
    )
    if not session_id:
        return None

    print(f"  Session ID: {session_id}")

    image_url = None
    score = None
    events_seen: list = []
    # Full pipeline can retry up to MAX_PIPELINE_ATTEMPTS times; each attempt
    # is ~3 minutes. Allow 12 minutes total before timing out.
    deadline = time.monotonic() + 720

    while time.monotonic() < deadline:
        try:
            event = event_queue.get(timeout=1.0)
        except q_module.Empty:
            sys.stdout.write(".")
            sys.stdout.flush()
            continue

        if event is None:
            print()
            break

        event_type = event.get("event")
        events_seen.append(event_type)

        if event_type == "status_update":
            pct = event["data"].get("progress_pct", 0)
            msg = event["data"].get("message", "")
            print(f"  [{pct:3d}%] {msg}")
        elif event_type == "image_ready":
            image_url = event["data"].get("image_url")
            score = event["data"].get("compliance_score")
            passed = event["data"].get("passed")
            print(f"  Image ready -> {image_url}  score={score}  passed={passed}")
        elif event_type == "state_change":
            new_state = event["data"].get("new_state")
            print(f"  State -> {new_state}")
        elif event_type == "error":
            msg = event["data"].get("message", "Unknown error")
            print(f"  {FAIL} Pipeline error: {msg}")
            results.append(("fail", f"Pipeline error: {msg}"))
            return None

    check("image_ready event received",
        lambda: _assert(image_url is not None,
            f"No image_ready event. Events seen: {events_seen}"))
    check("Compliance score present",
        lambda: _assert(score is not None, "compliance_score missing from image_ready"))

    def _check_disk():
        images_path = Path(os.getenv("IMAGES_PATH",
            "backend/storage_data/generated_posts"))
        files = list(images_path.glob(f"{session_id}*.png"))
        _assert(len(files) > 0, f"No PNGs found for session {session_id}")
        size_kb = files[0].stat().st_size // 1024
        _assert(size_kb > 10, f"Image too small: {size_kb}KB")
        print(f"       File: {files[0]}  ({size_kb} KB)")
        return files[0]
    check("Generated PNG exists on disk", _check_disk)

    return session_id


# ── SUMMARY ───────────────────────────────────────────────────────────────────

def print_summary():
    print("\n" + "=" * 58)
    passed = sum(1 for s, _ in results if s == "pass")
    failed = sum(1 for s, _ in results if s == "fail")
    skipped = sum(1 for s, _ in results if s == "skip")
    total = len(results)
    print(f"  Results: {passed}/{total} passed, {failed} failed, {skipped} skipped")
    if failed:
        print("\n  Failed tests:")
        for s, name in results:
            if s == "fail":
                print(f"    {FAIL} {name}")
    print("=" * 58)
    return failed == 0


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, choices=[1, 2, 3], default=None)
    parser.add_argument("--theme", default="dark", choices=["dark", "light"])
    parser.add_argument("--logo", default="nowpurchase",
                        choices=["nowpurchase", "metalcloud", "combined"])
    parser.add_argument("--run-all-combinations", action="store_true")
    args = parser.parse_args()

    if args.run_all_combinations:
        for theme in ("dark", "light"):
            for logo in ("nowpurchase", "metalcloud", "combined"):
                run_level_3(theme, logo)
                time.sleep(2)
    elif args.level == 1:
        run_level_1()
    elif args.level == 2:
        run_level_2(args.theme, args.logo)
    elif args.level == 3:
        run_level_3(args.theme, args.logo)
    else:
        run_level_1()
        run_level_2(args.theme, args.logo)
        run_level_3(args.theme, args.logo)

    success = print_summary()
    sys.exit(0 if success else 1)
