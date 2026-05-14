"""History routes — list past sessions and retrieve a single session's detail."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.storage.sqlite_logger import get_sqlite_logger

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def list_history(
    requested_by: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    logo_type: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    limit: int = Query(default=50, le=200),
):
    db = get_sqlite_logger()
    sessions = db.list_sessions(
        theme=theme,
        logo_type=logo_type,
        min_score=min_score,
        requested_by=requested_by,
        limit=limit,
    )
    for s in sessions:
        if s.get("image_path"):
            s["image_url"] = f"/api/assets/image/{s['id']}"
    return sessions


@router.get("/{session_id}")
async def get_session_detail(session_id: str):
    db = get_sqlite_logger()
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    conversations = db.get_conversations(session_id)
    return {
        **session,
        "conversations": conversations,
        "image_url": f"/api/assets/image/{session_id}",
    }
