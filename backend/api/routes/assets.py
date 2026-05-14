"""Asset routes — serve generated PNG files."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/assets", tags=["assets"])

IMAGES_PATH = Path(
    os.getenv("IMAGES_PATH", "backend/storage_data/generated_posts")
)


@router.get("/image/{session_id}")
async def get_image(session_id: str, attempt: int = None):
    """Serve the generated PNG for a session."""
    if attempt:
        path = IMAGES_PATH / f"{session_id}_attempt{attempt}.png"
    else:
        path = IMAGES_PATH / f"{session_id}_latest.png"

    if not path.exists():
        matches = list(IMAGES_PATH.glob(f"{session_id}*.png"))
        if matches:
            path = sorted(matches)[-1]
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No image found for session {session_id}",
            )

    return FileResponse(str(path), media_type="image/png")
