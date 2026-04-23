import asyncio
from app.tools.pinecone_tools import upsert_job_vector, query_similar_jobs, delete_job_vector

async def test():
    print("Testing Pinecone connection...")

    # Test 1 — Upsert a dummy vector
    print("\n[1] Upserting test vector...")
    vector_id = await upsert_job_vector(
        job_id="test-123",
        text="Python developer with FastAPI and PostgreSQL experience",
        metadata={
            "title": "Backend Developer",
            "company": "Test Company",
            "location": "Remote",
            "employment_type": "full-time",
            "is_active": True,
        }
    )
    print(f"    ✅ Upserted vector: {vector_id}")

    # Test 2 — Query similar jobs
    print("\n[2] Querying similar jobs...")
    results = await query_similar_jobs(
        profile_text="I am a Python developer skilled in FastAPI and databases",
        top_k=3,
    )
    print(f"    ✅ Found {len(results)} results")
    for r in results:
        print(f"       - {r['id']} | score: {r['score']:.4f}")

    # Test 3 — Delete test vector
    print("\n[3] Cleaning up test vector...")
    await delete_job_vector("test-123")
    print("    ✅ Test vector deleted")

    print("\n✅ ALL PINECONE TESTS PASSED!")

asyncio.run(test())