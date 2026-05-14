"""Knowledge base routes — list, add, delete entries in ChromaDB."""

import uuid

from fastapi import APIRouter, HTTPException

from backend.api.schemas import KBAddInput
from backend.storage.chromadb_client import get_chroma_client

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("")
async def list_knowledge():
    client = get_chroma_client()
    brand = client.list_documents("brand_knowledge")
    memory = client.list_documents("agent_memory")
    return {"brand_knowledge": brand, "agent_memory": memory}


@router.post("")
async def add_knowledge(body: KBAddInput):
    client = get_chroma_client()
    doc_id = f"manual_{uuid.uuid4().hex[:8]}"
    client.add_document(
        collection=body.collection,
        document=body.content,
        metadata={
            "category": body.category,
            "topic": body.topic,
            "added_by": "human",
            "source": "manual",
        },
        doc_id=doc_id,
    )
    return {"id": doc_id, "status": "written"}


@router.delete("/{entry_id}")
async def delete_knowledge(entry_id: str):
    client = get_chroma_client()
    for collection in ("brand_knowledge", "agent_memory"):
        try:
            client.delete_document(collection, entry_id)
            return {"status": "deleted", "id": entry_id}
        except Exception:
            continue
    raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
