
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



async def get_similarity_score(
    profile_text: str,
    job_vector_id: str,
) -> float:
    """
    Get similarity score between a profile text and a specific job vector.
    Fetches the job vector from Pinecone then computes cosine similarity.
    """
    def _score():
        try:
            index = _get_index()
            # Embed the profile text
            profile_vector = embed_text(profile_text)
            # Fetch the job vector
            fetch_result = index.fetch(ids=[job_vector_id])
            vectors = fetch_result.get("vectors", {})
            if job_vector_id not in vectors:
                return 0.0
            job_vector = vectors[job_vector_id]["values"]
            # Cosine similarity
            dot = sum(a * b for a, b in zip(profile_vector, job_vector))
            norm_p = sum(a * a for a in profile_vector) ** 0.5
            norm_j = sum(b * b for b in job_vector) ** 0.5
            if norm_p == 0 or norm_j == 0:
                return 0.0
            return dot / (norm_p * norm_j)
        except Exception as e:
            print(f"[Pinecone] get_similarity_score error: {e}")
            return 0.0

    return await asyncio.to_thread(_score)


async def query_similar_profiles(
    job_text: str,
    top_k: int = 50,
) -> list[dict]:
    """Find the most semantically similar profiles to the given job text."""
    def _query():
        index = _get_index()
        vector = embed_text(job_text)
        response = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            filter={"type": "profile"},
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