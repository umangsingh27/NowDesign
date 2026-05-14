"""
ChromaDB client — singleton wrapper for the NowPurchase Design Studio knowledge layer.
Two collections:
  brand_knowledge — what NowPurchase IS (human + agent writable)
  agent_memory    — what the system LEARNED (agent write only, tagged with theme + logo_type)
"""

import os
import uuid
from typing import Optional
from dotenv import load_dotenv
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

load_dotenv()

_client: Optional["ChromaDBClient"] = None
_embedding_fn: Optional[SentenceTransformerEmbeddingFunction] = None


def _get_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    return _embedding_fn


def get_chroma_client() -> "ChromaDBClient":
    global _client
    if _client is None:
        _client = ChromaDBClient()
    return _client


class ChromaDBClient:
    def __init__(self):
        chroma_path = os.getenv("CHROMADB_PATH", "./storage_data/chromadb")
        os.makedirs(chroma_path, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=chroma_path,
            settings=chromadb.Settings(anonymized_telemetry=False)
        )
        emb_fn = _get_embedding_fn()
        self.brand_knowledge = self._client.get_or_create_collection(
            name="brand_knowledge",
            embedding_function=emb_fn,
            metadata={"description": "NowPurchase company and brand knowledge base"}
        )
        self.agent_memory = self._client.get_or_create_collection(
            name="agent_memory",
            embedding_function=emb_fn,
            metadata={"description": "Design system learned patterns and corrections"}
        )

    def _get_collection(self, name: str):
        if name == "brand_knowledge":
            return self.brand_knowledge
        elif name == "agent_memory":
            return self.agent_memory
        raise ValueError(f"Unknown collection: {name}. Must be 'brand_knowledge' or 'agent_memory'.")

    def query_collection(
        self,
        name: str,
        query: str,
        n: int = 3,
        filters: Optional[dict] = None
    ) -> list[dict]:
        """
        Semantic search on a collection.
        filters example: {"theme": {"$eq": "dark"}, "logo_type": {"$eq": "nowpurchase"}}
        Returns list of {id, document, metadata, distance}.
        """
        collection = self._get_collection(name)
        kwargs = {"query_texts": [query], "n_results": min(n, collection.count() or 1)}
        if filters:
            kwargs["where"] = filters
        results = collection.query(**kwargs)
        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            output.append({
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
        return output

    def add_document(
        self,
        collection: str,
        document: str,
        metadata: dict,
        doc_id: Optional[str] = None
    ) -> str:
        """Add a document. Returns the document ID."""
        col = self._get_collection(collection)
        if doc_id is None:
            prefix = "bk" if collection == "brand_knowledge" else "am"
            doc_id = f"{prefix}_{uuid.uuid4().hex[:12]}"
        col.add(
            ids=[doc_id],
            documents=[document],
            metadatas=[metadata]
        )
        return doc_id

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete a document by ID."""
        self._get_collection(collection).delete(ids=[doc_id])

    def list_documents(
        self,
        collection: str,
        filters: Optional[dict] = None
    ) -> list[dict]:
        """List all documents, optionally filtered by metadata."""
        col = self._get_collection(collection)
        kwargs = {}
        if filters:
            kwargs["where"] = filters
        results = col.get(**kwargs)
        output = []
        for i, doc_id in enumerate(results["ids"]):
            output.append({
                "id": doc_id,
                "document": results["documents"][i],
                "metadata": results["metadatas"][i]
            })
        return output


if __name__ == "__main__":
    print("Testing ChromaDB client...")
    client = get_chroma_client()
    test_id = client.add_document(
        "brand_knowledge",
        "Test document for NowPurchase design studio.",
        {"category": "test", "topic": "smoke_test", "added_by": "test", "verified": False, "source": "manual"}
    )
    print(f"  Write test: document added with id={test_id}")
    results = client.query_collection("brand_knowledge", "NowPurchase design studio test", n=1)
    print(f"  Query test: retrieved {len(results)} result(s)")
    client.delete_document("brand_knowledge", test_id)
    print(f"  Delete test: document removed")
    print(f"  brand_knowledge count: {client.brand_knowledge.count()}")
    print(f"  agent_memory count:    {client.agent_memory.count()}")
    print("ChromaDB client: ALL TESTS PASSED")
