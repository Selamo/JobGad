"""
Pinecone vector store tools — wraps the Pinecone v4 SDK and sentence-transformers.

All SDK calls are synchronous, so every public function runs them inside
asyncio.to_thread() to avoid blocking the FastAPI event loop.
"""
import asyncio
from typing import Optional
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings

# ─── Embedding model (loaded once at startup) ─────────────────────────────────
# all-MiniLM-L6-v2 → 384-dim, fast, good semantic quality for skills/jobs
_model: Optional[SentenceTransformer] = None
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
INDEX_NAME = "jobgad-jobs"


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def _get_index():
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    # Create index if it doesn't exist yet (idempotent)
    if INDEX_NAME not in [idx.name for idx in pc.list_indexes()]:
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(INDEX_NAME)


# ─── Embedding ────────────────────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    """Generate a single embedding vector for the given text."""
    model = _get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


async def async_embed(text: str) -> list[float]:
    """Async wrapper — runs embedding in a thread pool."""
    return await asyncio.to_thread(embed_text, text)


# ─── Upsert ───────────────────────────────────────────────────────────────────

async def upsert_job_vector(job_id: str, text: str, metadata: dict) -> str:
    """
    Embed a job listing and upsert it into Pinecone.
    Returns the Pinecone vector ID (prefixed with 'job_').
    """
    vector_id = f"job_{job_id}"

    def _upsert():
        index = _get_index()
        vector = embed_text(text)
        index.upsert(vectors=[{"id": vector_id, "values": vector, "metadata": metadata}])
        return vector_id

    return await asyncio.to_thread(_upsert)


async def upsert_profile_vector(profile_id: str, text: str) -> str:
    """
    Embed a user's skill summary and upsert it into Pinecone.
    Returns the Pinecone vector ID (prefixed with 'profile_').
    """
    vector_id = f"profile_{profile_id}"

    def _upsert():
        index = _get_index()
        vector = embed_text(text)
        index.upsert(vectors=[{"id": vector_id, "values": vector, "metadata": {"type": "profile"}}])
        return vector_id

    return await asyncio.to_thread(_upsert)


# ─── Query (Semantic Search) ──────────────────────────────────────────────────

async def query_similar_jobs(
    profile_text: str,
    top_k: int = 10,
    filter: Optional[dict] = None,
) -> list[dict]:
    """
    Find the top_k most semantically similar job listings to the given profile text.
    Returns: [{"id": vector_id, "score": float, "metadata": {...}}, ...]
    """
    def _query():
        index = _get_index()
        vector = embed_text(profile_text)
        response = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter,
        )
        return [
            {
                "id": match["id"],
                "score": match["score"],
                "metadata": match.get("metadata", {}),
            }
            for match in response.get("matches", [])
        ]

    return await asyncio.to_thread(_query)


# ─── Delete ───────────────────────────────────────────────────────────────────

async def delete_job_vector(job_id: str) -> None:
    """Remove a job's vector from Pinecone."""
    def _delete():
        index = _get_index()
        index.delete(ids=[f"job_{job_id}"])

    await asyncio.to_thread(_delete)
