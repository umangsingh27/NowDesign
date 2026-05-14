# NowPurchase AI Design System — Complete System Plan v2.1
## The Definitive Blueprint: Zero to Live on the Company LAN
**Prepared for:** Umang Singh & Thotreichan Shaiza | **Version:** 2.1 | **May 2026**
**Status:** Final — Supersedes v2.0 entirely. Ready for implementation.

### What Changed from v2.0
- **Logo Type Selector** added throughout: NowPurchase / MetalCloud / Combined (6 logo assets, logo registry in config, updated Planner schema, updated `place_logo` skill, updated Critic criterion)
- **Post Theme (Dark / Light)** added throughout: parallel design constitutions in `brand_config.json`, theme-conditional background generation, theme-conditional glass rendering, theme-conditional Critic checklist, separate background libraries
- **Combined logo** resolved as pre-designed asset (one PNG per theme mode, exported from Figma — not runtime-composed)
- All other content from v2.0 is preserved unchanged

---

## TABLE OF CONTENTS

1. System Philosophy
2. Full Architecture Overview
3. Technology Stack (Final)
4. Knowledge Layer — ChromaDB + SQLite
5. The Skill System — The Real Foundation
6. The Four Agents & Their Skills
7. The Session State Machine
8. API Design
9. Frontend Design
10. Image Compositor — Modular Glass Renderer
11. Complete Project File Structure
12. Windows Local Deployment
13. Build Plan with Claude Code — Day by Day
14. Knowledge Base Seeding
15. Cost Analysis
16. Roadmap Beyond MVP
17. Appendix A — Configuration Files
18. Appendix B — Claude Code Usage Guide

---

## 1. SYSTEM PHILOSOPHY

### The Three Laws

**Law 1 — Everything Is Replaceable**
Every single piece of this system — an agent, a skill, a renderer, a model, a storage backend — must be swappable without touching anything else. This is achieved through interfaces and configuration, not code coupling. If Gemini Imagen is replaced by a better model next year, only one file changes. If the glass renderer is upgraded from Pillow to Playwright, only the renderer class changes. The rest of the system doesn't know or care.

**Law 2 — Everything Is Logged**
No action happens in silence. Every skill invocation, every agent decision, every KB read and write, every user message, every image generated — all of it flows into the SQLite log automatically. The log is not bolted on after the fact. It is the default behaviour of the Skill base class. If it happened, it was logged.

**Law 3 — Everything Gets Smarter Over Time**
The system ships with a brain (brand_knowledge) and grows one (agent_memory). Every approved generation, every user correction, every piece of feedback becomes a vector in ChromaDB that future agents retrieve before making decisions. The system on Day 90 is meaningfully better than the system on Day 1 — not because anyone fine-tuned a model, but because the knowledge stores grew.

### The Mental Model

```
NowPurchase Design Studio is not an image generation tool.
It is a knowledge-driven, session-based, adaptive creative agent
that happens to produce social media posts.
```

The distinction matters for how you build it. A tool has inputs and outputs. An agent has memory, context, judgement, and the ability to ask questions. Build the agent.

---

## 2. FULL ARCHITECTURE OVERVIEW

```
╔══════════════════════════════════════════════════════════════════════════╗
║                         KNOWLEDGE LAYER                                 ║
║                                                                          ║
║  ┌─────────────────────────────┐  ┌─────────────────────────────────┐   ║
║  │  ChromaDB PersistentClient  │  │   SQLite Structured Log         │   ║
║  │                             │  │                                 │   ║
║  │  Collection: brand_knowledge│  │  Tables:                        │   ║
║  │  "What NowPurchase IS"      │  │  • sessions                     │   ║
║  │  • Company overview         │  │  • skill_invocations            │   ║
║  │  • MetalCloud product info  │  │  • conversations                │   ║
║  │  • Raw materials sold       │  │  • kb_operations                │   ║
║  │  • Team & leadership        │  │  • generated_images             │   ║
║  │  • Customers & metrics      │  │  • agent_decisions              │   ║
║  │  • Brand voice rules        │  │                                 │   ║
║  │  • Dark mode design rules   │  │  Writable by: Skill base class  │   ║
║  │  • Light mode design rules  │  │  (automatic, always)            │   ║
║  │  • Logo type guidelines     │  └─────────────────────────────────┘   ║
║  │  Writable by: humans+agents │                                         ║
║  │                             │  Embedding model: all-MiniLM-L6-v2     ║
║  │  Collection: agent_memory   │  (sentence-transformers, runs locally)  ║
║  │  "What the system LEARNED"  │                                         ║
║  │  • Past generation outcomes │  Metadata tags on every entry:          ║
║  │  • User correction patterns │  • theme: "dark" | "light"              ║
║  │  • Layout decisions & scores│  • logo_type: "nowpurchase" |           ║
║  │  • Critic scoring history   │    "metalcloud" | "combined"            ║
║  │  Writable by: agents only   │  • post_type, compliance_score          ║
║  └─────────────────────────────┘                                         ║
╚══════════════════════════════════════════════════════════════════════════╝
                               │ all agents query here
╔══════════════════════════════╧═══════════════════════════════════════════╗
║                          SKILL REGISTRY                                  ║
║  Every agent has its own SkillRegistry — a named set of callable tools   ║
║  All skills auto-log to SQLite. All skills are independently testable.   ║
║  Skills are the atoms of the system. Agents are the reasoning loops.     ║
╚══════════════════════════════════════════════════════════════════════════╝
                               │
╔══════════════════════════════╧═══════════════════════════════════════════╗
║                         SESSION ENGINE                                   ║
║                                                                          ║
║  Session carries: brief (incl. logo_type + theme) → dialogue →          ║
║  generation → review → approval → learning.                              ║
║                                                                          ║
║  States: BRIEF → DIALOGUE → GENERATING → REVIEW → APPROVED              ║
║                    ↑_______________|  (re-composite loop)                ║
╚══════════════════════════════════════════════════════════════════════════╝
                               │
     ┌─────────────────┬────────┴──────────┬──────────────────┐
     ▼                 ▼                   ▼                  ▼
┌─────────┐     ┌─────────────┐     ┌──────────┐     ┌──────────────┐
│PLANNER  │     │  CREATOR    │     │  CRITIC  │     │  LEARNING    │
│AGENT    │     │  AGENT      │     │  AGENT   │     │  AGENT       │
│         │     │             │     │          │     │              │
│Resolves │     │Theme-aware: │     │Theme-    │     │Tags all      │
│logo path│     │• Imagen     │     │conditional│    │writes with   │
│from     │     │  prompts    │     │checklist │     │logo_type +   │
│registry │     │• Glass      │     │          │     │theme         │
│+theme   │     │  renderer   │     │14-point  │     │              │
│         │     │• Logo       │     │check     │     │              │
│         │     │  placement  │     │(4 dark-  │     │              │
│         │     │  (3 types)  │     │specific, │     │              │
│         │     │             │     │4 light-  │     │              │
│         │     │             │     │specific, │     │              │
│         │     │             │     │6 shared) │     │              │
└────┬────┘     └──────┬──────┘     └────┬─────┘     └──────┬───────┘
     │                 │                  │                  │
     └─────────────────┴──────────────────┴──────────────────┘
                               │
╔══════════════════════════════╧═══════════════════════════════════════════╗
║                    FastAPI BACKEND  (port 8000)                          ║
║  Session management · SSE streaming · REST API · File serving           ║
╚══════════════════════════════════════════════════════════════════════════╝
                               │ http://192.168.x.x:3000
╔══════════════════════════════╧═══════════════════════════════════════════╗
║                  Next.js FRONTEND  (port 3000)                           ║
║  5-state UI · Logo type selector · Theme toggle · reactbits.dev glass    ║
╚══════════════════════════════════════════════════════════════════════════╝
                               │
╔══════════════════════════════╧═══════════════════════════════════════════╗
║              Windows Laptop — Company LAN / WiFi                         ║
║  All processes local · No cloud hosting · Single bat file to start       ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 3. TECHNOLOGY STACK (FINAL)

| Layer | Technology | Version | Reason |
|-------|-----------|---------|--------|
| **LLM (all agents)** | Claude Sonnet 4.6 via OpenRouter | Latest | Best tool-use + vision. OpenRouter compatible. Umang has tokens. |
| **LLM API Protocol** | OpenAI-compatible SDK → OpenRouter | openai 1.x | OpenRouter uses OpenAI format. Tool calling fully supported for Claude models. |
| **Image Generation** | Gemini Imagen 4 (`imagen-4.0-fast-generate-001`) | Latest | Best photorealistic industrial imagery. $0.02/image. 1:1 aspect ratio supported. |
| **Image SDK** | `google-genai` Python SDK | Latest | Official Google SDK. Async support. |
| **Compositor** | Pillow + NumPy | Pillow 10.x | Image compositing, text rendering, glass approximation. Pure Python. Option A. |
| **Glass Renderer Interface** | Abstract base class | — | Swappable: PillowGlassRenderer (default) → PlaywrightGlassRenderer (upgrade path). Theme-conditional internally. |
| **Vector Database** | ChromaDB PersistentClient | Latest | Python-native, local, no server needed, Windows compatible, sentence-transformers built-in. |
| **Embeddings** | sentence-transformers all-MiniLM-L6-v2 | Latest | Ships with ChromaDB. ~300MB, runs on CPU. Fully local. |
| **Structured Database** | SQLite via SQLAlchemy async | aiosqlite | All logs, sessions, conversations. Zero setup. Single file. |
| **Backend** | FastAPI + uvicorn | 0.115.x | Async Python. Native Pydantic. SSE streaming. Works with all Python image libraries. |
| **Frontend** | Next.js 15 + TypeScript | Latest | React-based. LAN-exposable. SSR available. |
| **Frontend UI Kit** | reactbits.dev (Fluid Glass) + Tailwind CSS + shadcn/ui | Latest | Fluid Glass for UI chrome. Tailwind for layout. shadcn for base components. |
| **Frontend State** | React Context + useReducer | — | Session state machine. No Redux overhead for this scale. |
| **Frontend Data** | SWR | Latest | History fetching, auto-revalidation. |
| **Fonts (web UI)** | Google Fonts CDN | — | Urbanist + Oxanium. |
| **Fonts (Pillow)** | .ttf files on disk | — | Urbanist-ExtraBold.ttf, Oxanium-Regular.ttf downloaded at setup. |
| **Version Control** | Git + GitHub (private repo) | — | Standard. |
| **Build Tooling** | Claude Code CLI | Latest | Primary code-writing tool. All agent code written via Claude Code prompts. |

### What Is Explicitly NOT Used
- No Docker (unnecessary complexity for local Windows deployment)
- No Vercel, Railway, or any cloud hosting
- No LangChain or LlamaIndex (unnecessary abstraction — all agent logic is custom)
- No Redis (SQLite is sufficient for this scale)
- No message queues (SSE handles streaming directly)

---

## 4. KNOWLEDGE LAYER

### 4.1 ChromaDB — Two Collections

**ChromaDB Setup**
```python
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

client = chromadb.PersistentClient(
    path="./storage/chromadb",
    settings=chromadb.Settings(anonymized_telemetry=False)
)

embedding_fn = SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
```

**Collection 1: `brand_knowledge`**

The company brain. Everything agents need to know about NowPurchase, MetalCloud, and the brand — including both dark and light mode design rules, and all logo variants.

Document schema:
```python
{
    "id": "bk_<uuid>",
    "document": "NowPurchase dark mode posts use a deep navy background (#020C13)...",
    "metadata": {
        "category": "product_info",   # company_info | product_info | team_info
                                       # material_info | customer_info | brand_voice
                                       # design_rules_dark | design_rules_light | logo_guidelines
        "topic": "dark mode design language",
        "added_by": "umang",           # human username OR "agent:<agent_name>"
        "added_at": "2026-05-12T10:00:00Z",
        "verified": True,
        "source": "manual"             # manual | learning_agent | seed_script
    }
}
```

**Collection 2: `agent_memory`**

What the system has learned from its own operation. Every entry is tagged with `theme` and `logo_type` so retrieval is always context-specific.

Document schema:
```python
{
    "id": "am_<uuid>",
    "document": "For dark-mode product_feature posts with a stat, NowPurchase logo...",
    "metadata": {
        "memory_type": "layout_pattern",    # layout_pattern | correction | approval_pattern
                                             # failure_pattern | user_preference
        "post_type": "product_feature",
        "theme": "dark",                    # REQUIRED: "dark" | "light"
        "logo_type": "nowpurchase",         # REQUIRED: "nowpurchase" | "metalcloud" | "combined"
        "compliance_score": 92,
        "user_rating": 5,
        "session_id": "sess_<uuid>",
        "added_by": "agent:learning_agent",
        "added_at": "2026-05-12T10:00:00Z"
    }
}
```

### 4.2 SQLite — Structured Logs

Five tables. Every row is immutable (append-only). Nothing is ever deleted from logs.

```sql
-- Every generation session
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    state TEXT,                    -- BRIEF|DIALOGUE|GENERATING|REVIEW|APPROVED
    brief_json TEXT,               -- original user brief (includes logo_type + theme)
    logo_type TEXT,                -- nowpurchase | metalcloud | combined
    theme TEXT,                    -- dark | light
    layout_plan_json TEXT,
    image_path TEXT,
    compliance_score INTEGER,
    user_rating INTEGER,
    requested_by TEXT,
    total_attempts INTEGER DEFAULT 1,
    duration_ms INTEGER
);

-- Every skill invocation across all agents
CREATE TABLE skill_invocations (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    agent_name TEXT,
    skill_name TEXT,
    input_json TEXT,
    output_json TEXT,
    duration_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    invoked_at TIMESTAMP
);

-- Every message in every conversation (dialogue + review)
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    phase TEXT,                    -- DIALOGUE|REVIEW
    role TEXT,                     -- user|agent
    content TEXT,
    metadata_json TEXT,
    sent_at TIMESTAMP
);

-- Every KB read and write
CREATE TABLE kb_operations (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    collection TEXT,               -- brand_knowledge|agent_memory
    operation TEXT,                -- read|write|delete
    query TEXT,
    result_count INTEGER,
    document_id TEXT,
    agent_name TEXT,
    operated_at TIMESTAMP
);

-- Every generated image with full metadata
CREATE TABLE generated_images (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    attempt_number INTEGER,
    image_path TEXT,
    background_prompt TEXT,
    theme TEXT,                    -- dark | light
    logo_type TEXT,                -- nowpurchase | metalcloud | combined
    glass_renderer TEXT,           -- pillow|playwright
    compliance_score INTEGER,
    approved BOOLEAN DEFAULT FALSE,
    generated_at TIMESTAMP
);
```

---

## 5. THE SKILL SYSTEM

### 5.1 The Skill Base Class

```python
# backend/core/skills/base.py

from abc import ABC, abstractmethod
from typing import Any, Optional
import time
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel

class SkillResult(BaseModel):
    success: bool
    data: Any
    error: Optional[str] = None
    duration_ms: int

class Skill(ABC):
    """
    Every capability in the system is a Skill.
    Skills are: callable, logged, independently testable, and swappable.
    To add a new capability: subclass Skill, implement _execute().
    The base class handles logging automatically.
    """

    def __init__(self, db_logger, agent_name: str):
        self.db_logger = db_logger
        self.agent_name = agent_name

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def _execute(self, **kwargs) -> Any:
        pass

    def __call__(self, session_id: str, **kwargs) -> SkillResult:
        start_ms = time.monotonic_ns() // 1_000_000
        try:
            result_data = self._execute(**kwargs)
            duration = (time.monotonic_ns() // 1_000_000) - start_ms
            result = SkillResult(success=True, data=result_data, duration_ms=duration)
        except Exception as e:
            duration = (time.monotonic_ns() // 1_000_000) - start_ms
            result = SkillResult(success=False, data=None, error=str(e), duration_ms=duration)

        self.db_logger.log_skill_invocation(
            invocation_id=f"si_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            agent_name=self.agent_name,
            skill_name=self.name,
            input_json=str(kwargs),
            output_json=str(result.data)[:2000],
            duration_ms=result.duration_ms,
            success=result.success,
            error_message=result.error,
            invoked_at=datetime.now(timezone.utc).isoformat()
        )
        return result

    def as_tool_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema()
            }
        }

    @abstractmethod
    def get_parameters_schema(self) -> dict:
        pass
```

### 5.2 The Agent Base Class (The Reasoning Loop)

```python
# backend/core/agents/base.py

import json
import openai

class AgentResult:
    def __init__(self, output, skills_used: list[str], total_tokens: int):
        self.output = output
        self.skills_used = skills_used
        self.total_tokens = total_tokens

class Agent:
    def __init__(self, name: str, system_prompt: str, skills: list, llm_client):
        self.name = name
        self.system_prompt = system_prompt
        self.skill_registry = {s.name: s for s in skills}
        self.llm = llm_client
        self.tool_definitions = [s.as_tool_definition() for s in skills]

    def run(self, session_id: str, context: str, max_iterations: int = 12) -> AgentResult:
        messages = [{"role": "user", "content": context}]
        skills_used = []
        total_tokens = 0
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            response = self.llm.chat.completions.create(
                model="anthropic/claude-sonnet-4",
                messages=[{"role": "system", "content": self.system_prompt}] + messages,
                tools=self.tool_definitions,
                tool_choice="auto"
            )

            total_tokens += response.usage.total_tokens
            choice = response.choices[0]

            if choice.finish_reason == "stop":
                return AgentResult(
                    output=choice.message.content,
                    skills_used=skills_used,
                    total_tokens=total_tokens
                )

            messages.append(choice.message.model_dump())
            tool_results = []

            for tool_call in choice.message.tool_calls:
                skill_name = tool_call.function.name
                skill_args = json.loads(tool_call.function.arguments)
                skills_used.append(skill_name)

                if skill_name in self.skill_registry:
                    skill = self.skill_registry[skill_name]
                    result = skill(session_id=session_id, **skill_args)
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": json.dumps(result.data) if result.success
                                   else f"ERROR: {result.error}"
                    })

            messages.extend(tool_results)

        raise RuntimeError(f"Agent {self.name} exceeded max_iterations={max_iterations}")
```

---

## 6. THE FOUR AGENTS AND THEIR SKILLS

### 6.1 Planner Agent

**Role:** Understand the brief, consult knowledge, ask for missing context, produce a precise pixel-level layout plan that includes resolved logo path and theme-correct colours.

**System Prompt Core:**
```
You are the Planner Agent for NowPurchase's AI Design Studio.
Your job is to translate a creative brief into a precise, pixel-level layout plan
for a 1080×1080 PNG social media post.

You ALWAYS begin by querying brand_knowledge for context relevant to the brief,
including design rules for the specified theme (dark or light).
You ALWAYS query agent_memory for similar past generations, filtering by
the brief's theme and logo_type.
You ask clarifying questions BEFORE generating a layout plan if the brief is ambiguous.
You produce layout plans with exact pixel values — never ranges or approximations.
You resolve the logo file path from the logo registry in brand_config using both
logo_type and theme before writing the layout plan.

Canvas: 1080×1080px. Safe zone: 72px inset. Base unit: 8px grid.
```

**Skills:**
```python
# query_brand_knowledge
# Input: query (str), n_results (int, default 3)
# What it does: Semantic search on brand_knowledge collection.
#               When called for design rules, query should include the theme:
#               e.g. "light mode glass card design rules NowPurchase"
# Returns: list of relevant documents with metadata

# query_agent_memory
# Input: query (str), post_type (str), theme (str), logo_type (str), n_results (int)
# What it does: Semantic search on agent_memory collection,
#               filtered by theme AND logo_type metadata
# Returns: list of relevant past patterns for this exact combination

# ask_clarification
# Input: questions (list[str])
# What it does: Suspends pipeline, puts session into DIALOGUE state,
#               sends questions to frontend via SSE, waits for user answers
# Returns: None

# estimate_text_dimensions
# Input: text (str), font_path (str), font_size (int), max_width (int)
# What it does: Uses Pillow's ImageFont.getbbox() to measure rendered text dimensions
# Returns: {width_px, height_px, lines, actual_font_size}

# resolve_logo_asset
# Input: logo_type (str), theme (str)
# What it does: Looks up brand_config.logos[logo_type][theme] and returns the file path.
#               Validates the file exists on disk.
# Returns: {asset_path: str, width_px: int, height_px: int}

# calculate_layout
# Input: canvas_w (int), canvas_h (int), safe_zone (int), elements (list[ElementSpec])
# What it does: Validates element placement, detects overlaps,
#               ensures all elements within safe zone
# Returns: {valid: bool, warnings: list, adjusted_elements: list[ElementSpec]}

# write_layout_plan
# Input: layout_json (dict)
# What it does: Validates against brand_config schema, writes to session
# Returns: LayoutPlan (validated Pydantic model)
```

**Pixel-Level Layout Plan Schema (updated for theme + logo_type):**

```json
{
  "template": "stat_forward",
  "session_id": "sess_abc123",
  "theme": "dark",
  "logo_type": "nowpurchase",
  "canvas": {"width": 1080, "height": 1080},
  "background": {
    "prompt": "abstract dark industrial environment, shallow depth of field...",
    "mood_modifier": "blue steel cool tones",
    "luminance_target": 0.35,
    "center_zone_darkness": 0.7,
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
      "id": "stat_label",
      "type": "text",
      "content": "Reduction in scrap",
      "font": "assets/fonts/Oxanium-Medium.ttf",
      "size": 22,
      "color": "rgba(255,255,255,0.70)",
      "position": {"x": 48, "y": 175, "relative_to": "glass_card"},
      "alignment": "left",
      "max_width": 400,
      "letter_spacing": 1,
      "text_transform": "uppercase",
      "estimated_dimensions": {"width_px": 310, "height_px": 28}
    },
    {
      "id": "headline",
      "type": "text",
      "content": "MetalCloud's AI charge mix optimizer, live in 250+ foundries",
      "font": "assets/fonts/Urbanist-Bold.ttf",
      "size": 52,
      "color": "#FFFFFF",
      "position": {"x": 48, "y": 228, "relative_to": "glass_card"},
      "alignment": "left",
      "max_width": 768,
      "max_lines": 2,
      "line_height": 1.25,
      "letter_spacing": -0.5,
      "estimated_dimensions": {"width_px": 768, "height_px": 130}
    }
  ],
  "divider": {
    "type": "horizontal_line",
    "position": {"x": 48, "y": 390, "relative_to": "glass_card"},
    "width": 768,
    "color": "rgba(21,121,190,0.50)",
    "thickness": 1
  },
  "attribution": null,
  "bottom_tag": {
    "type": "text",
    "content": "MetalCloud by NowPurchase",
    "font": "assets/fonts/Oxanium-Regular.ttf",
    "size": 16,
    "color": "rgba(255,255,255,0.45)",
    "position": {"x": "center", "y": 1028}
  }
}
```

**Note on light mode layout plan:** When `theme` is `"light"`, all colour values in the Layout Plan are resolved from `brand_config.themes.light` — glass fill becomes `rgba(255,255,255,0.78)`, text primary becomes `#0D0D0D`, border becomes `rgba(0,0,0,0.12)`, and the logo asset resolves to the dark-variant file (e.g. `nowpurchase_dark.png`). The background prompt and luminance target also switch to light-mode values. The Planner handles all of these resolutions when writing the layout plan — the Compositor receives an already-resolved plan and executes it literally.

---

### 6.2 Creator Agent

**Role:** Execute the layout plan exactly. Generate theme-appropriate background, render theme-correct glass effect, composite all elements, output PNG.

**System Prompt Core:**
```
You are the Creator Agent. You receive a validated LayoutPlan and execute it exactly.
You do not make creative decisions — the Planner already made them.
The LayoutPlan contains all resolved values (colours, logo path, glass params).
You execute the plan literally, pixel by pixel.
```

**Skills:**

```python
# generate_background
# Input: prompt (str), mood_modifier (str), theme (str),
#        library_path (str), force_generate (bool)
# What it does:
#   - Checks library_path for pre-approved backgrounds (dark or light library)
#   - If count > 0 AND force_generate=False: randomly selects one
#   - If empty OR force_generate=True: calls Gemini Imagen 4 API
#   - Dark mode: prompt includes "dark moody industrial...", target luminance ≤ 0.40
#   - Light mode: prompt includes "minimal abstract industrial, soft diffused light...",
#                 target luminance ≥ 0.72
# Returns: PIL Image object (1080×1080)

# validate_background_luminance
# Input: image (PIL Image), theme (str), target (float)
# What it does: Computes average luminance of full image and centre 70% zone.
#   - Dark mode: passes if luminance ≤ target (default 0.40)
#   - Light mode: passes if luminance ≥ target (default 0.72)
# Returns: {passed: bool, full_luminance: float, center_luminance: float}

# render_glass_effect
# Input: background (PIL Image), card_spec (dict), theme (str)
# What it does: Delegates to GlassEffectRenderer interface.
#               Passes theme through to renderer so it uses correct glass params.
#               Default: PillowGlassRenderer (Option A)
#               Config-switchable to: PlaywrightGlassRenderer (Option B)
# Returns: PIL Image with glass card composited

# render_text_element
# Input: canvas (PIL Image), element_spec (dict)
# What it does: Renders text at exact position. All colour values are pre-resolved
#               in the element_spec by the Planner. No colour logic here.
# Returns: PIL Image with text rendered

# place_logo
# Input: canvas (PIL Image), pill_spec (dict)
# What it does: Loads logo asset from pill_spec.logo.asset path.
#               Renders glass pill (hug_content sizing from pill_spec).
#               Places logo inside pill centred.
#               Works identically for all three logo types — the asset path
#               already points to the correct pre-designed PNG.
# Returns: PIL Image with logo pill composited

# composite_final
# Input: canvas (PIL Image), all_layers (list[PIL Image])
# What it does: Alpha-composites all layers in order, converts to RGB, saves as PNG
# Returns: bytes (1080×1080 PNG)
```

**The Glass Renderer Interface (updated for theme):**

```python
# backend/core/compositor/glass_renderer.py

from abc import ABC, abstractmethod
from PIL import Image

class GlassEffectRenderer(ABC):
    """
    Swappable glass card renderer.
    Config key: glass_renderer = "pillow" | "playwright"
    """

    @abstractmethod
    def render(self, background: Image.Image, card_spec: dict, theme: str) -> Image.Image:
        """
        Given background image, card specification, and theme ("dark"|"light"),
        return the image with glass card composited on top.
        """
        pass


class PillowGlassRenderer(GlassEffectRenderer):
    """
    Option A: Pillow + NumPy approximation of liquid glass.
    Branches on theme for all layer parameters.

    Layers applied in order (both themes):
    1. Extract background region behind card
    2. Apply GaussianBlur (backdrop blur simulation)
    3. Apply radial displacement map at card edges (refraction simulation)
    4. Apply RGB channel offset at edges (chromatic aberration simulation)
    5. Semi-transparent overlay (fill from card_spec.glass.fill)
    6. Rounded rectangle mask
    7. Gradient border (bright top edge, dim rest — values from card_spec)
    8. Inner highlight line (top edge — values from card_spec)
    9. Specular highlight (radial gradient — values from card_spec)
    10. Drop shadow (offset composite on separate layer)
    """

    def render(self, background: Image.Image, card_spec: dict, theme: str) -> Image.Image:
        import numpy as np
        from PIL import ImageFilter, ImageDraw

        # All visual parameters come from card_spec (pre-resolved by Planner)
        # theme is passed for any conditional logic not captured in card_spec
        x = card_spec["position"]["x"]
        y = card_spec["position"]["y"]
        w = card_spec["width"]
        h = card_spec["height"]
        r = card_spec["corner_radius"]
        glass = card_spec["glass"]

        # Parse fill opacity from rgba string
        fill_str = glass["fill"]
        fill_opacity_int = int(float(fill_str.split(",")[3].rstrip(")").strip()) * 255)

        canvas = background.copy().convert("RGBA")

        # 1. Extract and blur background region
        region = background.crop((x, y, x + w, y + h)).convert("RGBA")
        blurred = region.filter(ImageFilter.GaussianBlur(radius=glass.get("blur_radius", 16)))

        # 2. Displacement at edges (refraction simulation)
        bg_array = np.array(blurred).astype(np.float32)
        cx, cy = w / 2, h / 2
        for py_r in range(h):
            for px_r in range(w):
                dist = ((px_r - cx) ** 2 + (py_r - cy) ** 2) ** 0.5
                edge_prox = max(0, 1 - (min(px_r, w - px_r, py_r, h - py_r) / 28))
                if edge_prox > 0:
                    strength = edge_prox * 3.5
                    sx = min(w-1, max(0, int(px_r + (px_r-cx)/max(dist,1)*strength)))
                    sy = min(h-1, max(0, int(py_r + (py_r-cy)/max(dist,1)*strength)))
                    bg_array[py_r, px_r] = bg_array[sy, sx]
        displaced = Image.fromarray(bg_array.astype(np.uint8))

        # 3. Chromatic aberration (RGB channel split at edges)
        r_ch, g_ch, b_ch, a_ch = displaced.split()
        displaced = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))

        # 4. Fill overlay (dark or light depending on theme)
        if theme == "dark":
            fill_color = (0, 0, 0, fill_opacity_int)
        else:
            fill_color = (255, 255, 255, fill_opacity_int)
        fill_layer = Image.new("RGBA", (w, h), fill_color)
        glass_base = Image.alpha_composite(displaced, fill_layer)

        # 5. Rounded rectangle mask
        mask = Image.new("L", (w, h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle([0, 0, w-1, h-1], radius=r, fill=255)
        glass_base.putalpha(mask)

        # 6. Composite onto canvas
        canvas.paste(blurred, (x, y))
        canvas.alpha_composite(glass_base, dest=(x, y))

        # 7. Draw border (bright top, dim rest)
        border_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw_border = ImageDraw.Draw(border_layer)
        if theme == "dark":
            top_border_color = (255, 255, 255, 71)   # white 28%
            full_border_color = (255, 255, 255, 20)  # white 8%
        else:
            top_border_color = (0, 0, 0, 31)         # black 12%
            full_border_color = (0, 0, 0, 13)        # black 5%
        draw_border.line([(x+r, y), (x+w-r, y)], fill=top_border_color, width=1)
        draw_border.rounded_rectangle([x, y, x+w-1, y+h-1], radius=r,
                                      outline=full_border_color, width=1)
        canvas.alpha_composite(border_layer)

        # 8. Inner highlight
        hl_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw_hl = ImageDraw.Draw(hl_layer)
        if theme == "dark":
            hl_color = (255, 255, 255, 46)  # white 18%
        else:
            hl_color = (255, 255, 255, 230) # near-white (light glass top sheen)
        draw_hl.line([(x+r+2, y+1), (x+w-r-2, y+1)], fill=hl_color, width=1)
        canvas.alpha_composite(hl_layer)

        return canvas


class PlaywrightGlassRenderer(GlassEffectRenderer):
    """
    Option B: Playwright headless Chromium — TRUE liquid glass via CSS + SVG filters.
    Activate by setting config: glass_renderer = "playwright"
    Requires: pip install playwright && playwright install chromium
    """

    def render(self, background: Image.Image, card_spec: dict, theme: str) -> Image.Image:
        raise NotImplementedError(
            "PlaywrightGlassRenderer not yet activated. "
            "Set glass_renderer=pillow in config or install playwright."
        )
```

---

### 6.3 Critic Agent

**Role:** Validate the generated image against brand standards. Score 0–100. Compliance checklist is theme-conditional.

**System Prompt Core:**
```
You are the Critic Agent for NowPurchase's AI Design Studio.
You evaluate generated social media posts against the Brand Design Language.
You score each criterion explicitly. You never say "looks good" without a score.

IMPORTANT: The brief includes a theme field ("dark" or "light").
You apply the correct criteria set for that theme — 4 criteria differ between themes.
You always query agent_memory for past compliance patterns,
filtering by the session's theme and logo_type.
```

**Skills:**
```python
# query_agent_memory
# Input: query (str), post_type (str), theme (str), logo_type (str), n_results (int)
# Returns: past compliance patterns for this specific theme + logo_type combination

# analyze_visual_compliance
# Input: image_base64 (str), layout_plan (dict), theme (str)
# What it does: Sends image + layout plan + theme to Claude vision via OpenRouter.
#               Runs the 14-point compliance check appropriate for the theme.
# Returns: dict of {criterion_name: {score, max_score, notes}}

# check_text_legibility
# Input: image_path (str), text_elements (list[dict]), theme (str)
# What it does: Samples contrast ratio between text colour and glass card background.
#               WCAG AA: ≥ 4.5:1 for normal text, ≥ 3:1 for large text.
# Returns: dict of {element_id: {contrast_ratio, passes_wcag_aa}}

# check_luminance_zones
# Input: image_path (str), glass_card_bounds (dict), theme (str)
# What it does:
#   - Dark mode: verifies background isn't too bright in card zone (< 0.40)
#   - Light mode: verifies background isn't too dark in card zone (> 0.70)
# Returns: {passes: bool, center_luminance: float}

# score_and_report
# Input: criterion_results (dict), luminance_results (dict), legibility_results (dict)
# Returns: ComplianceReport with total_score, passed, issues list

# write_correction_brief
# Input: compliance_report (ComplianceReport), original_layout_plan (dict)
# Returns: correction_brief (str) injected into next Planner run
```

**The 14-Point Compliance Checklist:**

```
─────────────────────────────────────────────────────────────────────
SHARED CRITERIA (both themes) — 60 points
─────────────────────────────────────────────────────────────────────
1.  Logo present and visible                           — 7 pts
2.  Logo inside glass pill at top-center               — 6 pts
3.  Logo variant correct for theme                     — 5 pts
    (dark theme → white logo; light theme → dark logo)
4.  All text is inside glassmorphism container         — 10 pts
5.  Glass card has visible blur/depth effect           — 5 pts
6.  No text directly on background without glass       — 5 pts
7.  Brand blue (#1579BE) used as accent               — 5 pts
8.  Headline readable at 200px preview size            — 7 pts
9.  No element overlap                                 — 5 pts
10. Text contrast passes WCAG AA on glass bg           — 5 pts

─────────────────────────────────────────────────────────────────────
THEME-CONDITIONAL CRITERIA — 40 points
─────────────────────────────────────────────────────────────────────
DARK MODE:                          │  LIGHT MODE:
                                    │
11. Background is industrial/       │  11. Background is industrial/
    foundry/factory imagery         │      clean/minimal imagery
                          — 10 pts  │                        — 10 pts
                                    │
12. Background is dark/moody,       │  12. Background is light/airy,
    not bright or cheerful          │      not dark or heavy
                          —  8 pts  │                        —  8 pts
                                    │
13. Color palette: navy/dark +      │  13. Color palette: white/grey +
    blue accent only                │      blue accent only
                          — 12 pts  │                        — 12 pts
                                    │
14. Visual hierarchy clear on       │  14. Visual hierarchy clear on
    dark glass surface              │      light glass surface
                          — 10 pts  │                        — 10 pts

─────────────────────────────────────────────────────────────────────
PASS THRESHOLD: 80 / 100
MAX REGENERATION ATTEMPTS: 3
─────────────────────────────────────────────────────────────────────
```

---

### 6.4 Learning Agent

**Role:** Activated after user approves a post. Process the session conversation, extract learnings, route to the correct ChromaDB collection with full metadata including theme and logo_type.

**System Prompt Core:**
```
You are the Learning Agent. You read completed session conversations and extract knowledge.

You classify extracted knowledge as:
1. BRAND KNOWLEDGE → brand_knowledge collection
   Facts about NowPurchase, products, team, customers, brand voice.

2. DESIGN PATTERNS → agent_memory collection
   What design decisions worked or failed for a specific theme + logo_type combination.
   Always tag with: theme ("dark" or "light") and logo_type.

When classifying, always extract the theme and logo_type from the session record.
Never invent information. Only extract what was explicitly stated.
```

**Skills:**
```python
# read_session_conversation
# Input: session_id (str)
# Returns: list[ConversationMessage] + session metadata (incl. theme + logo_type)

# classify_knowledge
# Input: extracted_statement (str), context (str)
# Returns: {type: "brand_knowledge"|"agent_memory"|"discard", confidence, reasoning}

# write_brand_knowledge
# Input: content (str), category (str), topic (str)
# Returns: {id: str, status: "written"}

# write_agent_memory
# Input: content (str), memory_type (str), post_type (str),
#        theme (str), logo_type (str),
#        compliance_score (int), user_rating (int)
# What it does: ALWAYS requires theme and logo_type as parameters.
#               These are stored in metadata for precise retrieval.
# Returns: {id: str, status: "written"}

# extract_design_patterns
# Input: conversation (list), layout_plan (dict),
#        theme (str), logo_type (str),
#        final_compliance_score (int), user_rating (int)
# Returns: list[DesignPattern] with theme + logo_type tagged

# log_session_outcome
# Input: session_id (str), outcome (str), user_rating (int),
#        compliance_score (int), learnings_written (int)
# Returns: None
```

---

## 7. THE SESSION STATE MACHINE

```
State: BRIEF
User fills in brief form. No session created yet.
Brief includes: emotion, purpose, headline, body_copy, stat, attribution,
                cta, requested_by, logo_type, theme
Transitions to: → DIALOGUE (Planner has questions)
                → GENERATING (brief complete, no questions)

─────────────────────────────────────────────────────────────────────

State: DIALOGUE
Planner has asked clarifying questions. Pipeline paused.
Data stored: original_brief (incl. logo_type + theme), planner_questions, session_id
Transitions to: → GENERATING (user answers)

─────────────────────────────────────────────────────────────────────

State: GENERATING
The 3-agent pipeline is running.
Progress steps:
  "Querying brand knowledge (theme: dark)..."
  "Querying past learnings..."
  "Planning pixel-perfect layout..."
  "Generating background image..."
  "Rendering glass effect..."
  "Compositing elements..."
  "Running quality review..."
Data stored: layout_plan_json (incl. theme + logo_type), image_path, compliance_score
Transitions to: → REVIEW (Critic score ≥ 80)
                → GENERATING again (score < 80, attempt < 3, with correction brief)
                → REVIEW with warning (max attempts reached — show best attempt)

─────────────────────────────────────────────────────────────────────

State: REVIEW
Generated image shown to user.
Right panel: chat interface.
Revision classification:
  Layout change → recomposite only (2–3 seconds, fast)
  Content change → full pipeline re-run (30–60 seconds)
  Theme change request → full pipeline re-run (new theme, new background)
  Logo type change request → recomposite only (swap logo asset, re-render pill)
Data stored: conversation_messages[], current_image_path, revision_count
Transitions to: → REVIEW (after each revision)
                → APPROVED (user approves)

─────────────────────────────────────────────────────────────────────

State: APPROVED
Final image confirmed. Copy + Download available.
Learning Agent runs in background (non-blocking).
Data stored: final_image_path, user_rating, theme, logo_type
Transitions to: (terminal state)
```

**Revision Classification Logic:**

```python
LAYOUT_CHANGE_KEYWORDS = [
    "bigger", "smaller", "font", "size", "move", "position", "spacing",
    "opacity", "darker", "lighter", "color", "align", "padding", "margin",
    "bold", "weight", "centered", "left", "right", "wider", "narrower"
]

CONTENT_CHANGE_KEYWORDS = [
    "headline", "text", "copy", "write", "change the message", "different stat",
    "add a line", "remove", "replace the background", "different background",
    "new image", "regenerate"
]

LOGO_CHANGE_KEYWORDS = [
    "logo", "metalcloud", "nowpurchase", "combined", "switch logo", "use metalcloud"
]

THEME_CHANGE_KEYWORDS = [
    "light mode", "dark mode", "switch to light", "switch to dark",
    "make it lighter", "make it darker", "white background", "dark background"
]

# Logo change → recomposite only (swap logo asset, re-render pill, 2–3 seconds)
# Theme change → full pipeline re-run (new background, new glass params)
# Layout change → recomposite only (2–3 seconds)
# Content change → full pipeline re-run (30–60 seconds)
```

---

## 8. API DESIGN

### Session Endpoints

```
POST   /api/session/start
       Body: BriefInput {
               logo_type: "nowpurchase" | "metalcloud" | "combined" (default: "nowpurchase")
               theme: "dark" | "light" (default: "dark")
               emotion: str
               purpose: str
               headline: str
               body_copy: str | null
               stat: str | null
               attribution: str | null
               cta: str | null
               requested_by: str | null
             }
       Response: {session_id, status, questions?}
       Behaviour: Creates session, runs Planner evaluation.
                  If Planner calls ask_clarification → returns questions.
                  If no questions → status="generating", starts pipeline.

POST   /api/session/{session_id}/answer
       Body: {answers: list[str]}
       Response: {status: "generating"}
       Behaviour: Injects answers into Planner context, starts pipeline.

GET    /api/session/{session_id}/stream
       Response: Server-Sent Events stream
       Events:
         {event: "status_update", data: {step, progress_pct, message, theme}}
         {event: "image_ready", data: {image_url, compliance_score, attempt, theme, logo_type}}
         {event: "state_change", data: {new_state}}
         {event: "error", data: {message, recoverable}}

POST   /api/session/{session_id}/feedback
       Body: {message: str}
       Response: SSE stream
       Behaviour: Classifies as layout_change, content_change, logo_change, theme_change.
                  Runs recomposite (fast) or full pipeline accordingly.

POST   /api/session/{session_id}/approve
       Body: {user_rating: int}
       Response: {status: "approved", final_image_url, learning_agent_status}
```

### Knowledge Base Endpoints

```
GET    /api/knowledge
       Response: {brand_knowledge: [...], agent_memory: [...]}

POST   /api/knowledge
       Body: {collection: str, content: str, category: str, topic: str}
       Response: {id, status: "written"}

DELETE /api/knowledge/{entry_id}
       Response: {status: "deleted"}
```

### History & Assets Endpoints

```
GET    /api/history
       Query params: ?requested_by=&post_type=&theme=&logo_type=&date_from=&date_to=&min_score=
       Response: list[SessionSummary]

GET    /api/history/{session_id}
       Response: SessionDetail

GET    /api/assets/image/{session_id}/{attempt?}
       Response: PNG file (1080×1080)

GET    /api/health
       Response: {status: "ok", chromadb: "ok", sqlite: "ok", models: {...}}
```

---

## 9. FRONTEND DESIGN

### Design Direction for the UI

Dark theme throughout: `#020C13` page background, `#041826` card backgrounds. Accent: `#1579BE`. Typography: Urbanist (headings), Oxanium (UI text). Glass elements: reactbits.dev Fluid Glass for card surfaces and navigation. Generated image preview: raw `<img>` tag, PNG as-is.

### The 5 UI States

**STATE 1 — BRIEF**

```
Layout: Two columns on desktop.

Left (420px): Brief input form in a glass card

  ┌─ POST THEME ────────────────────────────────────────────────────┐
  │  [● Dark Mode]  [  Light Mode  ]   ← prominent toggle, top      │
  │   Moon icon        Sun icon         of form, largest element     │
  └─────────────────────────────────────────────────────────────────┘

  ┌─ LOGO TYPE ─────────────────────────────────────────────────────┐
  │  [● NowPurchase]  [MetalCloud]  [Combined]   ← pill group        │
  └─────────────────────────────────────────────────────────────────┘

  • Post Type selector (dropdown)
  • Emotion selector (pill group)
  • Headline (text input, required)
  • Stat (text input, optional)
  • Body copy (textarea, optional)
  • Attribution (text input, optional)
  • CTA (text input, optional)
  • Requested by (text input)
  • "Generate Post" button

Right (flex): Empty state
  • When theme = "dark": dark navy preview placeholder
  • When theme = "light": light grey preview placeholder
    (the right panel shifts its own background on toggle —
     gives immediate visual feedback of what's coming)
  • Recent posts thumbnails strip at bottom
```

**Theme Toggle UI spec:**
- Two pill options: Moon + "Dark Mode" | Sun + "Light Mode"
- Selected state: filled background in brand blue with white text
- Unselected state: glass surface with muted text
- Positioned at the absolute top of the form — it is the most consequential decision and should be made first

**Logo Type UI spec:**
- Three pill options: NowPurchase | MetalCloud | Combined
- Selected: brand blue fill
- Unselected: glass surface, muted
- Positioned second in the form, directly below theme toggle
- Tooltip on "Combined": "Shows both the NowPurchase and MetalCloud logos side by side"

**STATE 2 — DIALOGUE** *(no changes from v2.0)*

Planner questions appear. Brief is locked and dimmed. Theme and logo_type are visible in the locked brief summary.

**STATE 3 — GENERATING**

Progress steps include the theme indicator:
```
  ◉ Querying brand knowledge (dark mode)...
  ✓ Querying past learnings (nowpurchase · dark)
  ✓ Planning pixel-perfect layout...
  ◉ Generating background image...     ← "Dark industrial · Gemini Imagen 4"
  ○ Rendering glass effect
  ○ Compositing elements
  ○ Quality review
```

**STATE 4 — REVIEW**

```
Left (60%): Generated image
  • PNG shown at ~580×580px
  • Compliance score badge
  • Theme + logo type badge: e.g. "Dark · NowPurchase"
  • Attempt counter
  • Expandable compliance breakdown (shows theme-appropriate criteria labels)
  • "Regenerate" button

Right (40%): Review chat (reactbits.dev FluidGlass card)
  • Chat thread
  • Suggestion chips include theme/logo actions:
    "Switch to light mode" | "Use MetalCloud logo" | "Make headline bigger"
  • "Approve & Download" button
  • 5-star rating
```

**Compliance breakdown in STATE 4:** The accordion renders the correct 14 criteria labels for the post's theme. Dark mode posts show "Background is dark/moody" — light mode posts show "Background is light/airy." The criterion label is resolved from a frontend-side map keyed by `theme`.

**STATE 5 — APPROVED** *(no changes from v2.0)*

Final image. Copy + Download. Theme and logo_type shown in metadata strip. Learning Agent notice.

### Component Tree

```
app/
├── layout.tsx
├── page.tsx                    ← Main generator (5-state machine)
├── history/page.tsx
└── knowledge/page.tsx

components/
├── layout/
│   ├── Header.tsx
│   └── Sidebar.tsx
├── brief/
│   ├── BriefForm.tsx
│   ├── ThemeToggle.tsx          ← NEW: Dark/Light toggle (prominent, top of form)
│   ├── LogoTypeSelector.tsx     ← NEW: NowPurchase/MetalCloud/Combined pills
│   ├── EmotionPills.tsx
│   └── PostTypeSelector.tsx
├── dialogue/
│   └── ClarificationChat.tsx
├── generation/
│   └── GenerationProgress.tsx
├── review/
│   ├── ReviewLayout.tsx
│   ├── PostPreview.tsx
│   ├── ComplianceBreakdown.tsx  ← UPDATED: theme-conditional criterion labels
│   ├── ThemeLogoBadge.tsx       ← NEW: "Dark · NowPurchase" badge
│   ├── ReviewChat.tsx
│   └── ChatMessage.tsx
├── approved/
│   └── ApprovedPost.tsx
├── history/
│   ├── HistoryGrid.tsx
│   ├── PostCard.tsx
│   └── HistoryFilters.tsx       ← UPDATED: theme + logo_type filter dropdowns
├── knowledge/
│   ├── KBEntryList.tsx
│   └── AddKBEntry.tsx
└── shared/
    ├── GlassCard.tsx
    ├── ScoreBadge.tsx
    ├── LoadingDots.tsx
    └── NPLogo.tsx
```

---

## 10. IMAGE COMPOSITOR — FULL MODULE DESIGN

```python
# backend/core/compositor/compositor.py

class ImageCompositor:
    """
    Receives a validated LayoutPlan and produces a 1080×1080 PNG.
    Independent of all agents. Deterministic given the same LayoutPlan.
    All visual parameters are pre-resolved by the Planner —
    the Compositor executes them literally.
    """

    def __init__(self, config, glass_renderer: GlassEffectRenderer):
        self.config = config
        self.glass_renderer = glass_renderer   # Injected — swappable
        self.font_cache = {}

    def composite(self, layout_plan: LayoutPlan, background: Image.Image) -> bytes:
        # Step 1: Resize/crop background to 1080×1080
        canvas = self._prepare_background(background)

        # Step 2: Apply global overlay
        # Dark mode: subtle darkening (0.15 opacity black)
        # Light mode: subtle brightening / haze (0.08 opacity white)
        overlay_color = (0, 0, 0) if layout_plan.theme == "dark" else (255, 255, 255)
        overlay_opacity = 0.15 if layout_plan.theme == "dark" else 0.08
        canvas = self._apply_global_overlay(canvas, overlay_color, overlay_opacity)

        # Step 3: Render glass card (delegates to GlassEffectRenderer, passes theme)
        canvas = self.glass_renderer.render(canvas, layout_plan.glass_card, layout_plan.theme)

        # Step 4: Render all text elements in z-order
        for element in sorted(layout_plan.elements, key=lambda e: e.get("z_order", 0)):
            if element["type"] == "text":
                canvas = self._render_text(canvas, element)
            elif element["type"] == "line":
                canvas = self._render_line(canvas, element)
            elif element["type"] == "accent_bar":
                canvas = self._render_accent_bar(canvas, element)

        # Step 5: Render logo pill
        canvas = self._render_logo_pill(canvas, layout_plan.logo_pill)

        # Step 6: Render bottom tag if present
        if layout_plan.bottom_tag:
            canvas = self._render_text(canvas, layout_plan.bottom_tag)

        # Step 7: Flatten and encode
        return self._export_png(canvas)

    def _render_logo_pill(self, canvas: Image.Image, pill_spec: dict) -> Image.Image:
        """
        Renders the glass pill with logo inside.
        Works identically for all three logo types — the asset path in pill_spec
        already points to the correct pre-designed PNG (resolved by Planner).
        The combined logo is a single pre-designed PNG, not runtime-composed.
        Pill width uses hug_content sizing: logo_width + 2×horizontal_padding.
        """
        from PIL import ImageDraw

        logo_img = Image.open(pill_spec["logo"]["asset"]).convert("RGBA")

        max_w = pill_spec["logo"]["max_width"]
        logo_scale = min(max_w / logo_img.width, 1.0)
        logo_w = int(logo_img.width * logo_scale)
        logo_h = int(logo_img.height * logo_scale)
        logo_img = logo_img.resize((logo_w, logo_h), Image.LANCZOS)

        h_pad = pill_spec["padding"]["horizontal"]
        v_pad = pill_spec["padding"]["vertical"]
        pill_w = max(logo_w + h_pad * 2, pill_spec.get("min_width", 160))
        pill_h = pill_spec["height"]
        corner_r = pill_spec["corner_radius"]

        canvas_w = canvas.size[0]
        pill_x = (canvas_w - pill_w) // 2
        pill_y = pill_spec["position"]["y"]

        # Parse pill glass fill from pill_spec
        fill_str = pill_spec["glass"]["fill"]
        fill_opacity = float(fill_str.split(",")[3].rstrip(")").strip())
        fill_rgba = (0, 0, 0, int(fill_opacity * 255))

        border_str = pill_spec["glass"]["border"]
        # Parse border color similarly...

        pill_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(pill_layer)
        draw.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=corner_r,
            fill=fill_rgba,
            outline=(255, 255, 255, 51)
        )
        canvas = Image.alpha_composite(canvas, pill_layer)

        logo_x = pill_x + (pill_w - logo_w) // 2
        logo_y = pill_y + (pill_h - logo_h) // 2
        canvas.alpha_composite(logo_img, dest=(logo_x, logo_y))

        return canvas

    def _prepare_background(self, img: Image.Image) -> Image.Image:
        target = 1080
        w, h = img.size
        scale = max(target / w, target / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target) // 2
        top = (new_h - target) // 2
        return resized.crop((left, top, left + target, top + target)).convert("RGBA")

    def _apply_global_overlay(self, canvas: Image.Image, color: tuple, opacity: float) -> Image.Image:
        overlay = Image.new("RGBA", canvas.size, (*color, int(opacity * 255)))
        return Image.alpha_composite(canvas, overlay)

    def _export_png(self, canvas: Image.Image) -> bytes:
        import io
        rgb_canvas = Image.new("RGB", canvas.size, (0, 0, 0))
        rgb_canvas.paste(canvas, mask=canvas.split()[3])
        buf = io.BytesIO()
        rgb_canvas.save(buf, format="PNG", optimize=False)
        return buf.getvalue()
```

---

## 11. COMPLETE PROJECT FILE STRUCTURE

```
nowpurchase-design-studio/
│
├── README.md
├── start_studio.bat
├── setup.bat
├── .env
├── .gitignore
├── brand_config.json              ← v1.1: logos registry + themes.dark + themes.light
├── system_config.json
│
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── session.py
│   │   │   ├── knowledge.py
│   │   │   ├── history.py
│   │   │   └── assets.py
│   │   └── schemas.py             ← BriefInput now includes logo_type + theme
│   │
│   ├── core/
│   │   ├── config.py
│   │   │
│   │   ├── skills/
│   │   │   ├── base.py
│   │   │   ├── knowledge_skills.py
│   │   │   ├── planner_skills.py  ← includes resolve_logo_asset skill
│   │   │   ├── creator_skills.py  ← generate_background is theme-conditional
│   │   │   ├── critic_skills.py   ← analyze_visual_compliance receives theme
│   │   │   └── learning_skills.py ← write_agent_memory requires theme + logo_type
│   │   │
│   │   ├── agents/
│   │   │   ├── base.py
│   │   │   ├── planner.py
│   │   │   ├── creator.py
│   │   │   ├── critic.py
│   │   │   └── learning.py
│   │   │
│   │   ├── compositor/
│   │   │   ├── glass_renderer.py  ← PillowGlassRenderer branches on theme
│   │   │   └── compositor.py      ← _render_logo_pill handles all 3 logo types
│   │   │
│   │   ├── imagen.py              ← theme-conditional prompts + luminance logic
│   │   └── pipeline.py
│   │
│   ├── storage/
│   │   ├── chromadb_client.py
│   │   ├── sqlite_logger.py
│   │   ├── session_store.py
│   │   └── file_store.py
│   │
│   ├── assets/
│   │   ├── fonts/
│   │   │   ├── Urbanist-ExtraBold.ttf
│   │   │   ├── Urbanist-Bold.ttf
│   │   │   ├── Oxanium-Regular.ttf
│   │   │   ├── Oxanium-Medium.ttf
│   │   │   └── Oxanium-SemiBold.ttf
│   │   │
│   │   ├── logos/
│   │   │   ├── nowpurchase_white.png     ← existing (280×72, transparent)
│   │   │   ├── nowpurchase_dark.png      ← NEW: dark wordmark for light mode
│   │   │   ├── metalcloud_white.png      ← NEW: MetalCloud logo, white version
│   │   │   ├── metalcloud_dark.png       ← NEW: MetalCloud logo, dark version
│   │   │   ├── combined_white.png        ← NEW: pre-designed combined lockup, white
│   │   │   └── combined_dark.png         ← NEW: pre-designed combined lockup, dark
│   │   │
│   │   └── backgrounds/
│   │       ├── dark/                     ← approved dark-mode foundry backgrounds
│   │       │   ├── approved_001.png
│   │       │   ├── approved_002.png
│   │       │   └── ...
│   │       └── light/                    ← NEW: approved light-mode backgrounds
│   │           ├── approved_001.png
│   │           └── ...
│   │
│   └── storage_data/
│       ├── chromadb/
│       ├── sqlite/
│       │   └── nowpurchase_studio.db
│       └── generated_posts/
│
├── frontend/
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   │
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── globals.css
│   │   ├── history/page.tsx
│   │   └── knowledge/page.tsx
│   │
│   ├── components/
│   │   ├── brief/
│   │   │   ├── BriefForm.tsx
│   │   │   ├── ThemeToggle.tsx      ← NEW
│   │   │   ├── LogoTypeSelector.tsx ← NEW
│   │   │   ├── EmotionPills.tsx
│   │   │   └── PostTypeSelector.tsx
│   │   ├── dialogue/ClarificationChat.tsx
│   │   ├── generation/GenerationProgress.tsx
│   │   ├── review/
│   │   │   ├── ReviewLayout.tsx
│   │   │   ├── PostPreview.tsx
│   │   │   ├── ComplianceBreakdown.tsx  ← UPDATED
│   │   │   ├── ThemeLogoBadge.tsx       ← NEW
│   │   │   ├── ReviewChat.tsx
│   │   │   └── ChatMessage.tsx
│   │   ├── approved/ApprovedPost.tsx
│   │   ├── history/
│   │   │   ├── HistoryGrid.tsx
│   │   │   ├── PostCard.tsx
│   │   │   └── HistoryFilters.tsx      ← UPDATED
│   │   ├── knowledge/
│   │   │   ├── KBEntryList.tsx
│   │   │   └── AddKBEntry.tsx
│   │   └── shared/
│   │       ├── GlassCard.tsx
│   │       ├── ScoreBadge.tsx
│   │       ├── LoadingDots.tsx
│   │       └── NPLogo.tsx
│   │
│   ├── lib/
│   │   ├── api.ts
│   │   ├── session-machine.ts
│   │   ├── types.ts              ← BriefInput type includes logo_type + theme
│   │   ├── clipboard.ts
│   │   └── compliance-labels.ts  ← NEW: theme-conditional criterion label map
│   │
│   └── public/
│       └── np-mark.svg
│
├── scripts/
│   ├── setup.py
│   ├── seed_knowledge.py         ← UPDATED: includes dark + light mode entries
│   ├── test_pipeline.py
│   ├── test_compositor.py        ← UPDATED: test both dark + light mode outputs
│   └── validate_assets.py        ← UPDATED: checks all 6 logo files exist
│
└── docs/
    ├── NowPurchase_Brand_Design_Language.md
    ├── NowPurchase_AI_Design_System_v2.1.md  ← this document
    └── api_reference.md
```

---

## 12. WINDOWS LOCAL DEPLOYMENT

### One-Time Setup

```batch
REM setup.bat

cd backend
python -m pip install -r requirements.txt
cd ..

cd frontend
npm install
cd ..

python scripts/setup.py
python scripts/seed_knowledge.py
python scripts/validate_assets.py
```

**requirements.txt (complete)**
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-dotenv==1.0.0
Pillow==10.4.0
numpy==1.26.4
google-genai==1.0.0
openai==1.45.0
chromadb==0.5.0
sentence-transformers==3.0.0
sqlalchemy==2.0.35
aiosqlite==0.20.0
httpx==0.27.0
pydantic==2.8.0
aiofiles==24.1.0
python-multipart==0.0.9
```

### Daily Startup

```batch
REM start_studio.bat

@echo off
echo Starting NowPurchase Design Studio...

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set LAN_IP=%%a
    goto :found_ip
)
:found_ip
set LAN_IP=%LAN_IP: =%

start "NP Design Studio — Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak > nul
start "NP Design Studio — Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- -H 0.0.0.0 -p 3000"

echo.
echo ========================================
echo  NowPurchase Design Studio is starting
echo ========================================
echo  This machine:   http://localhost:3000
echo  Company LAN:    http://%LAN_IP%:3000
echo  Share the LAN URL with your team.
echo ========================================
pause
```

### Windows Firewall (One-Time, run as Administrator)

```powershell
New-NetFirewallRule -DisplayName "NP Design Studio Frontend" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow
New-NetFirewallRule -DisplayName "NP Design Studio Backend" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

### Environment Variables (.env)

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-sonnet-4

GEMINI_API_KEY=AIzaSy-your-key-here
IMAGEN_MODEL=imagen-4.0-fast-generate-001

STORAGE_BASE=./storage_data
CHROMADB_PATH=./storage_data/chromadb
SQLITE_PATH=./storage_data/sqlite/nowpurchase_studio.db
IMAGES_PATH=./storage_data/generated_posts

GLASS_RENDERER=pillow
DEFAULT_THEME=dark
DEFAULT_LOGO_TYPE=nowpurchase
MIN_COMPLIANCE_SCORE=80
MAX_PIPELINE_ATTEMPTS=3
DARK_BG_MAX_LUMINANCE=0.45
DARK_BG_CENTER_MAX_LUMINANCE=0.40
LIGHT_BG_MIN_LUMINANCE=0.70
LIGHT_BG_CENTER_MIN_LUMINANCE=0.72
```

---

## 13. BUILD PLAN WITH CLAUDE CODE — DAY BY DAY

### Prerequisites Before Day 1

- [ ] Install Python 3.11+ on Windows
- [ ] Install Node.js 20+ on Windows
- [ ] Install Claude Code: `npm install -g @anthropic-ai/claude-code`
- [ ] Get Google AI Studio API key
- [ ] Confirm OpenRouter account and tokens
- [ ] **Export from Figma (Umang + Shaiza — half day):**
  - `nowpurchase_white.png` — horizontal, white, transparent bg (already exists)
  - `nowpurchase_dark.png` — horizontal, dark wordmark, transparent bg
  - `metalcloud_white.png` — MetalCloud horizontal logo, white, transparent bg
  - `metalcloud_dark.png` — MetalCloud horizontal logo, dark, transparent bg
  - `combined_white.png` — pre-designed combined lockup (both logos side by side), white
  - `combined_dark.png` — pre-designed combined lockup (both logos side by side), dark
  - **Shaiza designs the combined lockup in Figma** before any code runs
- [ ] Download fonts from Google Fonts: Urbanist-ExtraBold.ttf, Urbanist-Bold.ttf, Oxanium-Regular.ttf, Oxanium-Medium.ttf

---

### DAY 1 — FOUNDATION & KNOWLEDGE LAYER
**Owner: Umang | ~5 hours**

Morning (2 hrs):
```
□ Create project directory and git repo
□ Create brand_config.json (v1.1 with logos registry + themes.dark + themes.light)
□ Create system_config.json
□ Write backend/requirements.txt
□ Write .env file with API keys and theme/logo defaults
□ Create full directory structure including assets/logos/, assets/backgrounds/dark/, assets/backgrounds/light/
□ Copy 6 logo files from Figma exports into assets/logos/
□ Copy approved dark foundry backgrounds from NowDesign.fig into assets/backgrounds/dark/
□ Run: pip install -r requirements.txt
□ Run: npm create next-app frontend --typescript --tailwind --app
```

Afternoon (3 hrs — Claude Code):
```
Claude Code prompt:
"Build the Knowledge Layer for NowPurchase Design Studio.
Create these files completely:

1. backend/storage/chromadb_client.py
   - ChromaDB PersistentClient
   - Two collections: brand_knowledge and agent_memory
   - Uses sentence-transformers all-MiniLM-L6-v2 embeddings
   - Singleton pattern
   - Methods: query_collection(name, query, n=3, filters=None)
              add_document(collection, document, metadata, doc_id=None)
              delete_document(collection, doc_id)
              list_documents(collection, filters=None)

2. backend/storage/sqlite_logger.py
   - Creates all 5 SQLite tables on first run (idempotent)
   - sessions table includes logo_type and theme columns
   - generated_images table includes theme and logo_type columns
   - All log methods as specified in Section 4.2

3. scripts/seed_knowledge.py
   - Populates brand_knowledge with the full SEED_DATA from Section 14
   - Prints confirmation for each entry written

Load brand_config.json from project root.
Use python-dotenv for all paths.
Include __main__ test that verifies both collections work."
```

End of Day 1 check:
```
□ python scripts/seed_knowledge.py → 18+ entries written (dark mode + light mode entries)
□ SQLite file created with all 5 tables including logo_type + theme columns
□ 6 logo files present in assets/logos/
```

---

### DAY 2 — THE SKILL SYSTEM
**Owner: Umang | ~6 hours**

```
Claude Code prompt:
"Build the complete Skill System for NowPurchase Design Studio.

Create backend/core/skills/base.py with the Skill ABC exactly as in Section 5.1.
The __call__ method must auto-log to sqlite_logger every invocation.

Create backend/core/skills/knowledge_skills.py with four skills:
1. QueryBrandKnowledge — queries brand_knowledge ChromaDB collection
2. QueryAgentMemory — queries agent_memory, SUPPORTS filters dict
   (e.g. {'theme': 'dark', 'logo_type': 'nowpurchase'})
3. WriteBrandKnowledge — adds to brand_knowledge, logs to kb_operations
4. WriteAgentMemory — adds to agent_memory, REQUIRES theme and logo_type params,
   stores them in metadata

Create backend/core/agents/base.py with Agent ABC from Section 5.2.
The while-loop handles tool calls, stop finish_reason, max_iterations.

Create backend/core/skills/planner_skills.py with five skills:
1. AskClarification — suspends pipeline, sends questions via SSE queue
2. EstimateTextDimensions — Pillow getbbox() text measurement
3. ResolveLogoAsset — reads brand_config.logos[logo_type][theme],
   validates file exists, returns {asset_path, width_px, height_px}
4. CalculateLayout — validates element placement, no overlaps, within safe zone
5. WriteLayoutPlan — validates against LayoutPlan schema, saves to session

Use openai SDK with base_url from OPENROUTER_BASE_URL."
```

---

### DAY 3 — BACKGROUND GENERATOR + GLASS RENDERER
**Owner: Umang | ~7 hours | Shaiza: light mode background generation**

```
Claude Code prompt (Umang):
"Build backend/core/imagen.py — BackgroundGenerator class.

Uses google-genai Python SDK. Model from IMAGEN_MODEL env var.

Method: async generate(prompt, mood_modifier, theme, library_path,
                        force_generate=False) -> PIL Image

Theme-conditional prompt construction:
  If theme == 'dark':
    final_prompt = f'{prompt}, {mood_modifier}, dark industrial environment,
    shallow depth of field with strongly blurred background elements,
    abstract industrial forms with 3D CGI render quality,
    subtle dark gradient centre zone,
    no sharp foreground objects competing with overlaid content,
    no text, no faces, no logos, very dark overall atmosphere,
    ambient minimal industrial lighting, 8K resolution'
    negative = 'bright colors, high contrast, sharp foreground objects,
    text, logos, faces, watermarks, cartoon, illustration,
    oversaturated, busy patterns, daylight exterior, harsh lighting'

  If theme == 'light':
    final_prompt = f'{prompt}, {mood_modifier}, minimal abstract industrial environment,
    soft diffused light, clean airy atmosphere, light tones, out-of-focus depth of field,
    abstract 3D CGI industrial forms, subtle texture, sophisticated clean background,
    no text, no faces, no logos, bright open atmosphere, ambient light industrial'
    negative = 'dark backgrounds, heavy shadows, moody atmosphere, night scene,
    dramatic lighting, high contrast, text, logos, faces, cartoon, illustration'

Theme-conditional luminance validation:
  If theme == 'dark':  reject and retry if center luminance > DARK_BG_CENTER_MAX_LUMINANCE
  If theme == 'light': reject and retry if center luminance < LIGHT_BG_CENTER_MIN_LUMINANCE

BackgroundLibrarySelector:
  - Checks library_path (either assets/backgrounds/dark/ or assets/backgrounds/light/)
  - If count > 0 AND force_generate=False: random pick from theme-correct library
  - If empty OR force_generate=True: call Gemini Imagen
  - force_generate=True when user requests 'different background'

Include retry logic: 3 attempts with 2s backoff."
```

```
Claude Code prompt (Umang):
"Build the ImageCompositor in backend/core/compositor/compositor.py
and the GlassEffectRenderer in backend/core/compositor/glass_renderer.py.

Compositor must implement all methods from Section 10:
- composite(layout_plan, background) → bytes
- _prepare_background, _apply_global_overlay (theme-conditional color)
- _render_text, _render_line, _render_accent_bar
- _render_logo_pill (hug_content sizing, handles all 3 logo types identically
  because asset path is pre-resolved by Planner)
- _export_png
- _resolve_position, _wrap_text, _parse_color

GlassEffectRenderer must implement:
- GlassEffectRenderer ABC with render(background, card_spec, theme) signature
- PillowGlassRenderer with all 10 layers from Section 6.2
  — branches on theme for: fill color, border colors, inner highlight color
- PlaywrightGlassRenderer stub (raises NotImplementedError)

GLASS_RENDERER env var controls which class is instantiated at startup."
```

Shaiza's parallel task:
```
□ Generate 5 light-mode background images using Gemini Imagen (direct API call or AI Studio)
  Prompt: 'minimal abstract industrial environment, soft diffused light, clean airy
           atmosphere, out-of-focus depth of field, abstract 3D CGI industrial forms,
           very light tones, sophisticated clean background, no text, no faces'
□ Curate the best 5 → place in assets/backgrounds/light/
□ Note: at least 70% of the image area should be bright (luminance ≥ 0.72)
□ Run: python scripts/test_compositor.py --theme light
   Compare output to Figma reference for light-mode styling guidance
```

---

### DAY 4 — THE FOUR AGENTS
**Owner: Umang | ~6 hours**

```
Claude Code prompt:
"Build all four agents in backend/core/agents/.

PlannerAgent (planner.py):
System prompt includes:
  - Instructions to always query brand_knowledge with theme context
    ('light mode design rules NowPurchase' or 'dark mode glass card design')
  - Instructions to always query agent_memory filtered by theme AND logo_type
  - Instructions to call resolve_logo_asset before writing layout plan
  - Instructions to resolve all colours from brand_config.themes[theme]
    (never hardcode colour values in the layout plan)
  - Canvas, safe zone, base unit specs
Skills: QueryBrandKnowledge, QueryAgentMemory, AskClarification,
        EstimateTextDimensions, ResolveLogoAsset, CalculateLayout, WriteLayoutPlan

CreatorAgent (creator.py):
Skills: GenerateBackground (passes theme + library_path), ValidateLuminance (theme-aware),
        RenderGlassEffect (passes theme to renderer), RenderTextElement,
        PlaceLogo, CompositeFinal

CriticAgent (critic.py):
System prompt includes the full 14-point checklist from Section 6.3,
with explicit instruction to apply theme-conditional criteria (criteria 11-14)
based on the session's theme field.
The analyze_visual_compliance skill receives the image AND theme.
Skills: QueryAgentMemory (filtered by theme + logo_type), AnalyzeVisualCompliance,
        CheckTextLegibility, CheckLuminanceZones (theme-aware), ScoreAndReport,
        WriteCorrectsBrief

LearningAgent (learning.py):
System prompt emphasises that ALL agent_memory writes MUST include theme and logo_type.
Skills: ReadSessionConversation, ClassifyKnowledge, WriteBrandKnowledge,
        WriteAgentMemory (requires theme + logo_type params), ExtractDesignPatterns,
        LogSessionOutcome"
```

---

### DAY 5 — PIPELINE + FASTAPI BACKEND
**Owner: Umang | ~5 hours**

```
Claude Code prompt:
"Build the Pipeline orchestrator in backend/core/pipeline.py.

BriefInput Pydantic model must include:
  logo_type: Literal['nowpurchase', 'metalcloud', 'combined'] = 'nowpurchase'
  theme: Literal['dark', 'light'] = 'dark'

The pipeline passes logo_type and theme through every agent call.
Session record in SQLite must store logo_type and theme at creation.

SSE progress messages include theme context:
  'Querying brand knowledge (theme: dark)...'
  'Generating background (dark industrial · Gemini Imagen 4)...'

Revision classification must handle four types:
  layout_change → recomposite only
  content_change → full pipeline re-run
  logo_change → recomposite only (swap logo asset only)
  theme_change → full pipeline re-run (new background + glass params)

Build complete FastAPI app in backend/main.py and all routes from Section 8.
History endpoint supports ?theme= and ?logo_type= query params."
```

---

### DAY 6 — NEXT.JS FRONTEND
**Owner: Umang + Shaiza | ~7 hours**

```
Claude Code prompt:
"Build the NowPurchase Design Studio Next.js frontend.
All files in the frontend/ directory.

Brand colors: background #020C13, surface #041826, accent #1579BE,
text #FFFFFF, text-secondary rgba(255,255,255,0.70)
Fonts: Urbanist (headings), Oxanium (UI text) — both Google Fonts
Border radius: 16px cards, 24px large panels, 100px pills
Transitions: 200ms ease

New components required (described in Section 9):

1. ThemeToggle.tsx
   - Two pill options: moon icon + 'Dark Mode' | sun icon + 'Light Mode'
   - Selected: brand blue fill, white text
   - Unselected: glass surface, muted text
   - Must be the FIRST element inside BriefForm (before all other fields)
   - When toggled, the right panel empty state shifts background subtly:
     dark mode → #020C13 | light mode → #E8E8E8

2. LogoTypeSelector.tsx
   - Three pill options: 'NowPurchase' | 'MetalCloud' | 'Combined'
   - Combined pill has an info tooltip: 'Shows both logos side by side'
   - Positioned directly below ThemeToggle in BriefForm

3. ThemeLogoBadge.tsx
   - Displays e.g. 'Dark · NowPurchase' or 'Light · MetalCloud'
   - Shown in STATE 4 review panel under the compliance score

4. ComplianceBreakdown.tsx (updated)
   - Import compliance-labels.ts to resolve correct criterion labels by theme
   - criteria 11-14 labels change based on theme prop

5. lib/compliance-labels.ts
   - Exports COMPLIANCE_CRITERIA: Record<string, {dark: string, light: string}>
   - Maps criterion IDs to theme-specific display labels

Build all other components from Section 9 component tree.
STATE 1 brief form: ThemeToggle first, then LogoTypeSelector, then rest.
STATE 3 generating: progress steps show theme in sub-label.
STATE 4 review: show ThemeLogoBadge, use theme-conditional compliance labels.
STATE 5 approved: show theme + logo_type in metadata strip.

For ReviewChat suggestion chips, include:
  'Make headline bigger' | 'Switch to light mode' | 'Use MetalCloud logo'
  
Install reactbits.dev FluidGlass for GlassCard.tsx wrapper.
Post preview in STATE 4: plain <img> tag, no CSS glass effects on preview."
```

Shaiza reviews the frontend as it's being built:
```
□ Check ThemeToggle is visually prominent and positioned first
□ Check LogoTypeSelector pills feel distinct and clear
□ Verify the empty state right panel shifts background on theme toggle
□ Test suggestion chips including logo + theme suggestions
□ Check mobile responsiveness
□ Verify compliance breakdown shows correct labels for dark vs light posts
```

---

### DAY 7 — INTEGRATION, TESTING & CALIBRATION
**Owner: Umang + Shaiza | ~6 hours**

Morning (3 hrs — Umang):
```
□ Run start_studio.bat for the first time
□ Run scripts/test_pipeline.py --theme dark --logo nowpurchase
□ Run scripts/test_pipeline.py --theme light --logo metalcloud
□ Run scripts/test_pipeline.py --theme dark --logo combined
□ Fix any integration errors
□ Generate 2 posts for each combination (2 themes × 3 logo types = 6 posts)
□ Verify SSE streaming works for all 5 states
□ Test copy button, download button, approval flow
□ Test LAN access from another device
```

Afternoon (3 hrs — Shaiza leads visual calibration):
```
□ Compare dark mode outputs against Figma originals — calibration spreadsheet:
   | Element        | Expected | Actual    | Delta  | Fix? |
   | Glass opacity  | 0.62     | 0.58      | -0.04  | YES  |
   | Headline size  | 64px     | 64px      | 0      | NO   |
   | BG luminance   | ≤ 0.40   | 0.38      | OK     | NO   |

□ Compare light mode outputs:
   | Element        | Expected | Actual    | Delta  | Fix? |
   | Glass fill     | rgba(255,255,255,0.78) | ...  |     |
   | Text color     | #0D0D0D  | ...       | ...    | ...  |
   | BG luminance   | ≥ 0.72   | ...       | ...    | ...  |

□ Review all 3 logo types — do they all look correct in the pill?
□ Check combined logo pill width (should hug the combined PNG)
□ Adjust PillowGlassRenderer parameters based on visual review
□ Generate first real posts for Marketing backlog
□ Present to CEO: 1 dark post + 1 light post + 1 combined logo post
```

---

### DAY 8 — QUALITY HARDENING & REAL USAGE
**Owner: Shaiza leads, Umang supports | ~4 hours**

```
□ Generate 15 real posts across all combinations
□ Document every manual intervention needed
□ Create user guide: 1 page, includes explanation of theme + logo choices
□ Record walkthrough video (show theme toggle, logo selector)
□ Share tool URL with Marketing team
□ Collect initial feedback
□ Fix top 3 issues from real usage
□ Commit everything to GitHub
```

---

### DAY 9 & 10 — KNOWLEDGE BASE GROWTH & LEARNING LOOP
**Owner: Umang + Shaiza | ~4 hours**

```
□ Run 20 posts: variety of types, both themes, all 3 logo types
□ Check agent_memory: are dark and light mode patterns separating correctly?
  (dark-mode posts should never influence light-mode learning and vice versa)
□ Review brand_knowledge: did Learning Agent add anything incorrect? Remove if so.
□ Check Planner: is it asking fewer questions as agent_memory grows?
□ Check Critic: are dark-mode and light-mode scores being evaluated separately?
□ Add 5 manual brand_knowledge entries (see Section 14 additions)
□ Generate light-mode background library: 10+ approved backgrounds
   Place in assets/backgrounds/light/ for BackgroundLibrarySelector
□ Declare PoC complete — full demo to CEO
```

---

## 14. KNOWLEDGE BASE SEEDING

Complete `SEED_DATA` for `scripts/seed_knowledge.py`:

```python
SEED_DATA = [
    # ── COMPANY INFO ──────────────────────────────────────────────────

    {
        "content": "NowPurchase is a Kolkata-based AI-powered B2B platform serving India's $19 billion foundry and castings industry. Founded in 2017 by Naman Shah (CEO) and Aakash Shah (Co-founder). Total funding: approximately ₹120 crore ($18M USD). Latest round of ₹80 crore was led by Bajaj Finserv in April 2026, with participation from Info Edge Ventures, Orios Venture Partners, and REAL Group.",
        "category": "company_info",
        "topic": "company overview and funding"
    },
    {
        "content": "NowPurchase has two business verticals: (1) MetalCloud — a SaaS AI platform for metal manufacturers, and (2) a raw material procurement marketplace where foundries can source scrap, alloys, and additives. The company also operates a network of scrap processing centres and offers branded products for alloys and additives.",
        "category": "company_info",
        "topic": "business verticals"
    },
    {
        "content": "NowPurchase leadership: Naman Shah is the Founder and CEO. Aakash Shah is Co-founder. Ankan Adhikari is CTO. Headquartered in Kolkata, West Bengal, India.",
        "category": "team_info",
        "topic": "founders and leadership"
    },
    {
        "content": "NowPurchase has delivered over 1.95 lakh tonnes of materials to 200+ clients. MetalCloud is deployed across 250+ factories nationwide, with clients including Titagarh Rail Systems Limited and Brakes India. 2x year-over-year growth over three years.",
        "category": "company_info",
        "topic": "scale and key metrics"
    },

    # ── PRODUCT INFO ──────────────────────────────────────────────────

    {
        "content": "MetalCloud is NowPurchase's AI-powered SaaS platform — the core operating system for metal manufacturers. Key features: charge mix optimization, real-time heat data and analytics, quality monitoring, production process optimization, IoT and computer vision for shop-floor digitization.",
        "category": "product_info",
        "topic": "MetalCloud product features"
    },
    {
        "content": "MetalCloud's charge mix optimizer uses AI to give real-time recommendations on what raw materials to add to the furnace to achieve the desired target chemistry. Customers report 2-5% cost savings per heat and significant reductions in melt time.",
        "category": "product_info",
        "topic": "MetalCloud charge mix optimizer outcomes"
    },
    {
        "content": "MetalCloud provides real-time WhatsApp integration for foundry operators — heat-wise updates, dilution suggestions, and raw material pricing delivered directly on WhatsApp. This is a key adoption driver for factory floor workers.",
        "category": "product_info",
        "topic": "MetalCloud WhatsApp integration"
    },
    {
        "content": "MetalCloud uses computer vision (YOLO models, OpenCV, Raspberry Pi edge devices) for anomaly detection on factory floors — detecting process inefficiencies and reducing downtime by 7-10%.",
        "category": "product_info",
        "topic": "MetalCloud computer vision features"
    },

    # ── MATERIAL INFO ──────────────────────────────────────────────────

    {
        "content": "NowPurchase procures and supplies these raw materials to foundries: Ferro Alloys (FeSi, FeMn, FeCr, FeMo), Additives (inoculants, nodularizers, carburizers), Scrap Metal (MS scrap, CI scrap), Pig Iron, and branded private-label alloy and additive products.",
        "category": "material_info",
        "topic": "raw materials supplied"
    },
    {
        "content": "NowPurchase offers real-time pricing and stock availability for all raw materials through WhatsApp bot and MetalCloud. Foundries can check current market prices for ferro alloys, scrap, and pig iron without calling suppliers.",
        "category": "material_info",
        "topic": "real-time pricing and procurement"
    },

    # ── BRAND VOICE ──────────────────────────────────────────────────

    {
        "content": "NowPurchase brand voice: Authoritative, precise, and confident. The audience is engineering professionals — foundry managers, metallurgists, factory owners. Speak in outcomes and data. Always specific: '23% reduction in scrap' not 'significant scrap reduction'. Never casual, never aggressive. No emojis in headlines.",
        "category": "brand_voice",
        "topic": "brand voice and tone"
    },
    {
        "content": "NowPurchase key messages: (1) AI-powered precision for foundry operations, (2) Reduce costs and improve quality with data-driven decisions, (3) From procurement to production — one platform, (4) Trusted by 250+ factories across India, (5) The operating system for modern metal manufacturing.",
        "category": "brand_voice",
        "topic": "key marketing messages"
    },

    # ── DESIGN RULES — DARK MODE ──────────────────────────────────────

    {
        "content": "NowPurchase DARK MODE post design language: Deep navy background (#020C13 to #041826). Primary blue accent (#1579BE). White text on dark surfaces (#FFFFFF primary, rgba(255,255,255,0.75) secondary). Glassmorphism containers with rgba(0,0,0,0.62) fill and backdrop blur 16px. White gradient border (28% opacity top, 8% sides). Inner white highlight on top edge (18% opacity). Foundry or factory background imagery — dark, moody, cinematic. Urbanist ExtraBold for headlines, Oxanium for body.",
        "category": "design_rules_dark",
        "topic": "dark mode complete design language"
    },
    {
        "content": "NowPurchase DARK MODE glass card spec: background rgba(0,0,0,0.62), border top rgba(255,255,255,0.28), border sides/bottom rgba(255,255,255,0.08), inner highlight rgba(255,255,255,0.18), drop shadow 0 8px 32px rgba(0,0,0,0.45), corner radius 24px. Logo pill: rgba(0,0,0,0.60) fill, rgba(255,255,255,0.20) border, 100px corner radius. White (white version) logo on dark glass.",
        "category": "design_rules_dark",
        "topic": "dark mode glassmorphism specification"
    },
    {
        "content": "NowPurchase DARK MODE background imagery: Foundry or factory environment. Dark, moody, cinematic photography style. 3D CGI quality abstract industrial forms. Shallow depth of field with strongly blurred background elements. Subtle dark gradient in centre zone where glass card sits. No text, no faces, no logos. Target luminance: centre zone ≤ 0.40. Use assets/backgrounds/dark/ library.",
        "category": "design_rules_dark",
        "topic": "dark mode background imagery requirements"
    },

    # ── DESIGN RULES — LIGHT MODE ──────────────────────────────────────

    {
        "content": "NowPurchase LIGHT MODE post design language: Light grey/white background (#F2F2F2 to #FFFFFF). Primary blue accent (#1579BE) remains. Dark text on light surfaces (#0D0D0D primary, rgba(0,0,0,0.65) secondary). Glassmorphism containers with rgba(255,255,255,0.78) fill and backdrop blur 16px. Dark gradient border (12% opacity top, 5% sides). Near-white inner highlight on top edge. Minimal, airy, clean abstract industrial background imagery. Urbanist ExtraBold for headlines, Oxanium for body. Dark (dark version) logo on light glass.",
        "category": "design_rules_light",
        "topic": "light mode complete design language"
    },
    {
        "content": "NowPurchase LIGHT MODE glass card spec: background rgba(255,255,255,0.78), border top rgba(0,0,0,0.12), border sides/bottom rgba(0,0,0,0.05), inner highlight rgba(255,255,255,0.90), drop shadow 0 8px 32px rgba(0,0,0,0.12), corner radius 24px. Logo pill: rgba(255,255,255,0.75) fill, rgba(0,0,0,0.10) border, 100px corner radius. Dark (dark version) logo on light glass.",
        "category": "design_rules_light",
        "topic": "light mode glassmorphism specification"
    },
    {
        "content": "NowPurchase LIGHT MODE background imagery: Minimal abstract industrial environment. Soft diffused light. Clean airy atmosphere. Abstract 3D CGI industrial forms with light tones. Out-of-focus depth of field. Sophisticated clean background without heavy shadows or dramatic moody lighting. No text, no faces, no logos. Target luminance: centre zone ≥ 0.72. Use assets/backgrounds/light/ library.",
        "category": "design_rules_light",
        "topic": "light mode background imagery requirements"
    },

    # ── LOGO GUIDELINES ──────────────────────────────────────────────

    {
        "content": "Logo type guidelines: Use 'nowpurchase' logo type for company-wide brand communications, funding announcements, team/culture posts, and general awareness. Use 'metalcloud' logo type for product feature posts, case studies, and MetalCloud-specific content. Use 'combined' logo type when the post references both the procurement/materials business and the MetalCloud platform together. The combined logo is a pre-designed lockup (not composed at runtime).",
        "category": "logo_guidelines",
        "topic": "when to use each logo type"
    },
    {
        "content": "Logo placement law: Logo always at top-center inside a glassmorphism pill. Pill uses hug_content sizing — width equals logo width plus 48px horizontal padding. Minimum pill width: 160px. Pill height: 56px. Corner radius: 100px (full pill shape). Logo vertically centered in pill. Top of pill at 72px from canvas top edge. For combined logo, the pill widens automatically to fit the pre-designed combined PNG.",
        "category": "logo_guidelines",
        "topic": "logo placement and pill sizing rules"
    },

    # ── CUSTOMER INFO ──────────────────────────────────────────────────

    {
        "content": "Notable NowPurchase customers: Titagarh Rail Systems Limited (railway components), Brakes India (automotive brakes), Real Ispat Group (investor and customer). Serves 250+ factories across India in automotive, infrastructure, and heavy machinery sectors.",
        "category": "customer_info",
        "topic": "key customers"
    },
    {
        "content": "NowPurchase competitive differentiators: (1) Deep focus on metal manufacturing specifically, (2) Integrated SaaS platform MetalCloud alongside procurement, (3) AI-powered optimization built into the workflow, (4) Own scrap processing network and branded products, (5) On-ground service teams for quality assurance.",
        "category": "company_info",
        "topic": "competitive differentiation"
    }
]
```

---

## 15. COST ANALYSIS

### API Costs Per Post

| Component | Call | Cost |
|-----------|------|------|
| Imagen 4 Fast (background) | 1 image | $0.020 |
| Imagen retry (if needed) | 0-1 image | $0.020 |
| Claude Sonnet (Planner) | ~2K tokens | $0.006 |
| Claude Sonnet (Critic vision) | ~3K tokens + image | $0.012 |
| Claude Sonnet (Learning Agent) | ~2K tokens | $0.006 |
| **Total per approved post** | | **~$0.044–$0.064** |

At current exchange: ~₹4–5 per post. Infrastructure cost: ₹0.

**Background library optimisation (both modes):** Once you have 10–15 approved backgrounds in each library (dark and light), the BackgroundLibrarySelector uses them for ~60% of generations, cutting Imagen API calls by 60%.

---

## 16. ROADMAP BEYOND MVP

### Phase 2.1 — Week 2–3: Quick Wins
```
□ Additional canvas sizes: LinkedIn landscape (1200×628), Story (1080×1920)
□ Template gallery: show examples per post type + theme before generating
□ Post tagging: custom tags on approved posts for filtering
□ Bulk generation: upload CSV of briefs → batch generate
□ KB UI polish: better KB management interface
□ Background library growth: 10+ approved backgrounds per theme per visual style
```

### Phase 2.2 — Month 2: Team Features
```
□ User profiles: team member name/role tracked per session
□ Post approval queue: design team reviews before download
□ Slack integration: request post via Slack, receive in channel
□ Post calendar view: approved posts on a timeline
□ Option B glass renderer: activate Playwright for true liquid glass
   (applies to both dark and light mode — Playwright handles both via CSS theme vars)
```

### Phase 2.3 — Month 3: Quality Improvements
```
□ A/B variants: generate 2 versions (e.g. dark + light of same post), user picks
□ Brand compliance trends: dashboard showing score improvements over time
□ Auto-retry tuning: Learning Agent tracks which correction types work per theme
□ Copy intelligence: Planner writes headlines if user provides only a topic
□ Custom templates: teams define their own post type templates per theme
```

### Phase 3 — Month 4–6: Motion & Presentations (Shaiza leads)
```
□ Animated posts: 15-second MP4 using Veo 3 (both dark and light mode variants)
□ Slide deck covers: MetalCloud presentation cover slides (dark + light)
□ Email headers: newsletter/email visual headers
□ Video thumbnails: YouTube/LinkedIn cover images
□ Social Story format: 1080×1920 animated stories
```

---

## 17. APPENDIX A — CONFIGURATION FILES

### brand_config.json (v1.1 — complete)

```json
{
  "version": "1.1",
  "canvas": {
    "width": 1080,
    "height": 1080,
    "safe_zone": 72,
    "base_unit": 8,
    "format": "PNG"
  },
  "logos": {
    "nowpurchase": {
      "dark": "assets/logos/nowpurchase_white.png",
      "light": "assets/logos/nowpurchase_dark.png"
    },
    "metalcloud": {
      "dark": "assets/logos/metalcloud_white.png",
      "light": "assets/logos/metalcloud_dark.png"
    },
    "combined": {
      "dark": "assets/logos/combined_white.png",
      "light": "assets/logos/combined_dark.png"
    }
  },
  "logo_pill": {
    "sizing": "hug_content",
    "padding": {"horizontal": 24, "vertical": 12},
    "min_width": 160,
    "max_width": 360,
    "height": 56,
    "corner_radius": 100,
    "top_offset": 72
  },
  "themes": {
    "dark": {
      "background_base": "#020C13",
      "surface": "#041826",
      "accent": "#1579BE",
      "glass": {
        "fill": "rgba(0,0,0,0.62)",
        "blur_radius": 16,
        "border_radius_card": 24,
        "border_radius_pill": 100,
        "border_top_opacity": 0.28,
        "border_rest_opacity": 0.08,
        "inner_highlight_opacity": 0.18,
        "specular_opacity": 0.12,
        "drop_shadow": "0 8px 32px rgba(0,0,0,0.45)",
        "pill_fill": "rgba(0,0,0,0.60)",
        "pill_border": "rgba(255,255,255,0.20)"
      },
      "text": {
        "primary": "#FFFFFF",
        "secondary": "rgba(255,255,255,0.75)",
        "tertiary": "rgba(255,255,255,0.50)",
        "caption": "rgba(255,255,255,0.45)",
        "accent": "#1579BE",
        "label_uppercase": "rgba(255,255,255,0.60)"
      },
      "background": {
        "library_path": "assets/backgrounds/dark/",
        "prompt_style": "dark_industrial",
        "prompt_base": "dark industrial environment, shallow depth of field with strongly blurred background elements, abstract industrial forms with 3D CGI render quality, subtle dark gradient centre zone, no sharp foreground objects competing with overlaid content, no text, no faces, no logos, very dark overall atmosphere, ambient minimal industrial lighting, 8K resolution",
        "negative": "bright colors, high contrast, sharp foreground objects, text, logos, faces, watermarks, cartoon, illustration, oversaturated, busy patterns, daylight exterior, harsh lighting",
        "luminance_max": 0.45,
        "center_luminance_max": 0.40
      }
    },
    "light": {
      "background_base": "#F2F2F2",
      "surface": "#FFFFFF",
      "accent": "#1579BE",
      "glass": {
        "fill": "rgba(255,255,255,0.78)",
        "blur_radius": 16,
        "border_radius_card": 24,
        "border_radius_pill": 100,
        "border_top_opacity": 0.12,
        "border_rest_opacity": 0.05,
        "inner_highlight_opacity": 0.90,
        "specular_opacity": 0.06,
        "drop_shadow": "0 8px 32px rgba(0,0,0,0.12)",
        "pill_fill": "rgba(255,255,255,0.75)",
        "pill_border": "rgba(0,0,0,0.10)"
      },
      "text": {
        "primary": "#0D0D0D",
        "secondary": "rgba(0,0,0,0.65)",
        "tertiary": "rgba(0,0,0,0.45)",
        "caption": "rgba(0,0,0,0.40)",
        "accent": "#1579BE",
        "label_uppercase": "rgba(0,0,0,0.50)"
      },
      "background": {
        "library_path": "assets/backgrounds/light/",
        "prompt_style": "light_industrial",
        "prompt_base": "minimal abstract industrial environment, soft diffused light, clean airy atmosphere, light tones, out-of-focus depth of field, abstract 3D CGI industrial forms, subtle texture, sophisticated clean background, bright open atmosphere, ambient light",
        "negative": "dark backgrounds, heavy shadows, moody atmosphere, night scene, dramatic lighting, high contrast, text, logos, faces, cartoon, illustration",
        "luminance_min": 0.70,
        "center_luminance_min": 0.72
      }
    }
  },
  "typography": {
    "heading_font": "assets/fonts/Urbanist-ExtraBold.ttf",
    "heading_bold_font": "assets/fonts/Urbanist-Bold.ttf",
    "body_font": "assets/fonts/Oxanium-Regular.ttf",
    "body_medium_font": "assets/fonts/Oxanium-Medium.ttf",
    "body_semibold_font": "assets/fonts/Oxanium-SemiBold.ttf",
    "type_scale": {
      "headline": {"min": 52, "max": 72, "weight": 800},
      "subheading": {"min": 36, "max": 48, "weight": 700},
      "body_primary": {"min": 24, "max": 28, "weight": 400},
      "body_secondary": {"min": 18, "max": 22, "weight": 400},
      "label": {"min": 14, "max": 16, "weight": 500},
      "stat": {"min": 60, "max": 96, "weight": 800}
    }
  },
  "validation": {
    "min_compliance_score": 80,
    "max_attempts": 3,
    "wcag_aa_min_contrast": 4.5
  }
}
```

### system_config.json (complete)

```json
{
  "glass_renderer": "pillow",
  "llm_model": "anthropic/claude-sonnet-4",
  "imagen_model": "imagen-4.0-fast-generate-001",
  "default_theme": "dark",
  "default_logo_type": "nowpurchase",
  "background_library_usage_rate": 0.6,
  "chromadb_n_results_default": 3,
  "session_timeout_minutes": 120,
  "max_kb_entries_per_session": 5,
  "learning_agent_delay_seconds": 2,
  "debug_mode": false,
  "save_all_attempts": true
}
```

---

## 18. APPENDIX B — CLAUDE CODE USAGE GUIDE

### Starting Each Session
```bash
cd nowpurchase-design-studio
claude
```

### The Effective Prompt Formula
```
"Build [specific file] in [exact path].

Purpose: [what this does in one sentence]

It must:
- [requirement 1]
- [requirement 2]
- [requirement 3]

[Paste the relevant section of this plan as additional context]

Include:
- Full type hints
- Docstrings on all classes and methods
- A __main__ test that proves it works"
```

### When Tests Fail
```
"I'm getting this error when running [file]:
[paste exact error and stack trace]

The expected behaviour is: [describe]
The relevant code is at line [N] of [file]:
[paste code section]

Fix it."
```

### When Visual Output Is Wrong
```
"The compositor is producing output that doesn't match the spec.
Theme: [dark|light]
Logo type: [nowpurchase|metalcloud|combined]
Specific issue: [e.g. 'glass card fill is too dark on light mode post']
Expected: rgba(255,255,255,0.78) fill opacity
Actual: appears near-opaque white

Here is the relevant glass_renderer code:
[paste the conditional branch]

Fix the light mode fill calculation."
```

### Testing Both Themes
```bash
# Test dark mode — NowPurchase logo
python scripts/test_pipeline.py --theme dark --logo nowpurchase --purpose product_feature

# Test light mode — MetalCloud logo
python scripts/test_pipeline.py --theme light --logo metalcloud --purpose product_feature

# Test combined logo — dark mode
python scripts/test_pipeline.py --theme dark --logo combined --purpose announcement

# Run all 6 combinations
python scripts/test_pipeline.py --run-all-combinations
```

---

*This document is the complete, authoritative blueprint for NowPurchase's AI Design System.*
*Version 2.1 supersedes all previous planning documents.*
*Ready for implementation with Claude Code starting Day 1.*

**Pre-implementation checklist before writing any code:**
- [ ] 6 logo files exported from Figma and placed in assets/logos/
- [ ] Combined logo lockup designed by Shaiza in Figma and exported
- [ ] At least 5 approved dark-mode backgrounds in assets/backgrounds/dark/
- [ ] At least 3 approved light-mode backgrounds in assets/backgrounds/light/
- [ ] Urbanist and Oxanium .ttf files downloaded into assets/fonts/
- [ ] .env file populated with OpenRouter + Gemini API keys
- [ ] Google AI Studio API key confirmed (free tier: 500 Imagen requests/day for testing)
- [ ] Claude Code installed: npm install -g @anthropic-ai/claude-code
- [ ] Python 3.11+ and Node.js 20+ installed on the Windows laptop

---
*Document compiled: May 2026*
*NowPurchase AI Design System — v2.1 Final*
