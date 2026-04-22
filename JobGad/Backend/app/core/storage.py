import asyncio
from supabase import create_client, Client
from app.core.config import settings


def get_supabase_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


async def upload_file_to_supabase(
    file_bytes: bytes,
    file_name: str,
    user_id: str,
    bucket: str = "documents",
) -> str:
    """
    Uploads a file to Supabase Storage and returns the public URL.
    Path pattern: documents/{user_id}/{file_name}

    Runs the synchronous Supabase SDK in a thread so the async event loop
    is never blocked.
    """
    def _upload() -> str:
        client = get_supabase_client()
        storage_path = f"{user_id}/{file_name}"
        client.storage.from_(bucket).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"upsert": "true"},
        )
        return client.storage.from_(bucket).get_public_url(storage_path)

    return await asyncio.to_thread(_upload)


async def delete_file_from_supabase(
    storage_path: str,
    bucket: str = "documents",
) -> None:
    """
    Deletes a file from Supabase Storage given its storage path (user_id/filename).
    Path must match the one used during upload.
    """
    def _delete() -> None:
        client = get_supabase_client()
        client.storage.from_(bucket).remove([storage_path])

    await asyncio.to_thread(_delete)