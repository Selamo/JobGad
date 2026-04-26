
import asyncio
from typing import Optional
from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings

# ─── Constants ────────────────────────────────────────────────────────────────
INDEX_NAME = "jobgad-jobs"
EMBEDDING_DIM = 1024  


def _get_client() -> Pinecone:
    return Pinecone(api_key=settings.PINECONE_API_KEY)


def _get_index():
    pc = _get_client()
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
    """
    Generate embedding using Pinecone's hosted embedding model.
    No local model loading — saves huge amounts of RAM.
    """
    pc = _get_client()
    result = pc.inference.embed(
        model="llama-text-embed-v2",
        inputs=[text],
        parameters={"input_type": "passage"},
    )
    return result[0].values


async def async_embed(text: str) -> list[float]:
    """Async wrapper — runs embedding in a thread pool."""
    return await asyncio.to_thread(embed_text, text)


# ─── Upsert ───────────────────────────────────────────────────────────────────

async def upsert_job_vector(job_id: str, text: str, metadata: dict) -> str:
    """Embed a job listing and upsert into Pinecone."""
    vector_id = f"job_{job_id}"

    def _upsert():
        index = _get_index()
        vector = embed_text(text)
        index.upsert(vectors=[{
            "id": vector_id,
            "values": vector,
            "metadata": metadata,
        }])
        return vector_id

    return await asyncio.to_thread(_upsert)


async def upsert_profile_vector(profile_id: str, text: str) -> str:
    """Embed a user profile and upsert into Pinecone."""
    vector_id = f"profile_{profile_id}"

    def _upsert():
        index = _get_index()
        vector = embed_text(text)
        index.upsert(vectors=[{
            "id": vector_id,
            "values": vector,
            "metadata": {"type": "profile"},
        }])
        return vector_id

    return await asyncio.to_thread(_upsert)


# ─── Query ────────────────────────────────────────────────────────────────────

async def query_similar_jobs(
    profile_text: str,
    top_k: int = 10,
    filter: Optional[dict] = None,
) -> list[dict]:
    """Find the most semantically similar jobs to the given profile text."""
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
    """Remove a job vector from Pinecone."""
    def _delete():
        index = _get_index()
        index.delete(ids=[f"job_{job_id}"])

    await asyncio.to_thread(_delete)