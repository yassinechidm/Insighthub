import json
import uuid
from typing import Any
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

_in_memory_store: dict[str, dict[str, Any]] = {"documents": {}, "embeddings": {}}


async def upsert_chunks(chunks_with_vectors: list[tuple], document_id: str) -> int:
    """
    chunks_with_vectors : liste de (chunk, vector)
    chunk : objet avec chunk_id, document_id, source, content, metadata
    """
    if AsyncSessionLocal is None:
        for chunk, vector in chunks_with_vectors:
            _in_memory_store["embeddings"][chunk.chunk_id] = {
                "chunk": chunk,
                "vector": vector,
            }
        return len(chunks_with_vectors)

    async with AsyncSessionLocal() as session:
        count = 0
        for chunk, vector in chunks_with_vectors:
            await session.execute(
                text("""
                    INSERT INTO embeddings (chunk_id, document_id, source, content, embedding, metadata)
                    VALUES (:chunk_id, :document_id, :source, :content, :embedding, :metadata)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        content   = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata  = EXCLUDED.metadata
                """),
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": document_id,
                    "source": chunk.source,
                    "content": chunk.content,
                    "embedding": str(vector),
                    "metadata": json.dumps(chunk.metadata),
                }
            )
            count += 1
        await session.commit()
        return count


async def upsert_document(source: str, external_id: str, title: str, metadata: dict) -> str:
    if AsyncSessionLocal is None:
        document_id = str(uuid.uuid4())
        _in_memory_store["documents"][f"{source}:{external_id}"] = {
            "id": document_id,
            "source": source,
            "external_id": external_id,
            "title": title,
            "metadata": metadata,
        }
        return document_id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                INSERT INTO documents (source, external_id, title, metadata)
                VALUES (:source, :external_id, :title, :metadata)
                ON CONFLICT (source, external_id) DO UPDATE SET
                    title    = EXCLUDED.title,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                RETURNING id
            """),
            {
                "source": source,
                "external_id": external_id,
                "title": title,
                "metadata": json.dumps(metadata),
            }
        )
        await session.commit()
        return str(result.scalar())