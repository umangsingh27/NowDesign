"""
NowPurchase Design Studio — FastAPI application entry point.

Run: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import assets, history, knowledge, session
from backend.api.schemas import HealthResponse
from backend.storage.chromadb_client import get_chroma_client
from backend.storage.sqlite_logger import get_sqlite_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure storage directories exist and warm the storage layers."""
    for env_var, default in [
        ("IMAGES_PATH", "backend/storage_data/generated_posts"),
        ("CHROMADB_PATH", "backend/storage_data/chromadb"),
        ("SQLITE_PATH", "backend/storage_data/sqlite/nowpurchase_studio.db"),
    ]:
        target = Path(os.getenv(env_var, default))
        # If the env var points to a file (sqlite db), ensure the parent dir
        if target.suffix == ".db":
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            target.mkdir(parents=True, exist_ok=True)

    get_sqlite_logger()
    get_chroma_client()

    print("NowPurchase Design Studio backend ready.")
    yield
    print("Shutting down.")


app = FastAPI(
    title="NowPurchase AI Design Studio",
    version="2.1.0",
    description="AI-powered social post generator for NowPurchase and MetalCloud",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://0.0.0.0:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router)
app.include_router(knowledge.router)
app.include_router(history.router)
app.include_router(assets.router)


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Quick health check — verify all subsystems are up."""
    chroma_status = "ok"
    sqlite_status = "ok"
    try:
        get_chroma_client()
    except Exception as e:
        chroma_status = f"error: {e}"
    try:
        get_sqlite_logger()
    except Exception as e:
        sqlite_status = f"error: {e}"

    glass_renderer = "pillow"
    try:
        cfg_path = Path("system_config.json")
        if cfg_path.exists():
            sys_config = json.loads(cfg_path.read_text(encoding="utf-8"))
            glass_renderer = sys_config.get("glass_renderer", "pillow")
    except Exception:
        pass

    degraded = "error" in chroma_status or "error" in sqlite_status
    return HealthResponse(
        status="degraded" if degraded else "ok",
        chromadb=chroma_status,
        sqlite=sqlite_status,
        glass_renderer=glass_renderer,
    )


@app.get("/")
async def root():
    return {
        "message": "NowPurchase AI Design Studio API",
        "docs": "/docs",
        "health": "/api/health",
    }
