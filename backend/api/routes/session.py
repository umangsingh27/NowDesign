"""
Session routes — the core generation API.

SSE streaming architecture:
  - Each active session has an entry in SESSION_QUEUES (dict of queue.Queue)
  - The pipeline thread pushes events onto the queue
  - The /stream endpoint consumes the queue as an async SSE generator
"""

import asyncio
import json
import queue
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from backend.api.schemas import (
    AnswerInput,
    ApproveInput,
    ApproveResponse,
    BriefInput,
    FeedbackInput,
    StartSessionResponse,
)
from backend.core.pipeline import Pipeline

router = APIRouter(prefix="/api/session", tags=["session"])


# Global pipeline instance (singleton per process)
_pipeline: Pipeline = None


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline


# Active session queues: session_id -> queue.Queue
SESSION_QUEUES: dict[str, queue.Queue] = {}


@router.post("/start", response_model=StartSessionResponse)
async def start_session(brief: BriefInput):
    """Create a new session and start the pipeline."""
    pipeline = get_pipeline()
    brief_dict = brief.model_dump()
    event_queue: queue.Queue = queue.Queue()
    session_id = pipeline.start(brief_dict, event_queue)
    SESSION_QUEUES[session_id] = event_queue
    return StartSessionResponse(
        session_id=session_id,
        status="generating",
        questions=None,
    )


@router.get("/{session_id}/stream")
async def stream_session(session_id: str):
    """SSE endpoint. Streams pipeline events until completion."""
    if session_id not in SESSION_QUEUES:
        raise HTTPException(
            status_code=404,
            detail=f"No active stream for session {session_id}",
        )

    event_queue = SESSION_QUEUES[session_id]

    async def event_generator() -> AsyncGenerator:
        loop = asyncio.get_event_loop()
        try:
            while True:
                try:
                    event = await loop.run_in_executor(
                        None, lambda: event_queue.get(timeout=0.1)
                    )
                except queue.Empty:
                    yield {"comment": "keepalive"}
                    continue

                if event is None:
                    SESSION_QUEUES.pop(session_id, None)
                    return

                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"]),
                }
        except asyncio.CancelledError:
            SESSION_QUEUES.pop(session_id, None)

    return EventSourceResponse(event_generator())


@router.post("/{session_id}/answer")
async def answer_clarification(session_id: str, body: AnswerInput):
    """Provide answers to Planner clarification questions."""
    # TODO Day 7: full dialogue resume flow
    return JSONResponse({"status": "generating", "session_id": session_id})


@router.post("/{session_id}/feedback")
async def feedback(session_id: str, body: FeedbackInput):
    """Submit revision feedback. Pipeline classifies and re-runs."""
    pipeline = get_pipeline()

    from backend.storage.sqlite_logger import get_sqlite_logger
    db = get_sqlite_logger()
    db.log_conversation_message(
        session_id=session_id,
        phase="REVIEW",
        role="user",
        content=body.message,
    )

    event_queue: queue.Queue = queue.Queue()
    SESSION_QUEUES[session_id] = event_queue
    pipeline.handle_feedback(session_id, body.message, event_queue)

    return JSONResponse({
        "status": "generating",
        "session_id": session_id,
        "stream_url": f"/api/session/{session_id}/stream",
    })


@router.post("/{session_id}/approve", response_model=ApproveResponse)
async def approve_session(session_id: str, body: ApproveInput):
    """Approve the generated post. Triggers Learning Agent in background."""
    pipeline = get_pipeline()
    result = pipeline.approve(session_id, body.user_rating)
    return ApproveResponse(**result)
