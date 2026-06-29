from sqlalchemy import text
from app.db.database import AsyncSessionLocal

async def upsert_chunks(chunks_with_vectors: list[tuple]) -> int:
    """
    chunks_with_vectors : liste de (chunk, vector)
    chunk : objet avec chunk_id, document_id, source, content, metadata
    """
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
                    "chunk_id":    chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "source":      chunk.source,
                    "content":     chunk.content,
                    "embedding":   str(vector),
                    "metadata":    chunk.metadata,
                }
            )
            count += 1
        await session.commit()
        return count

async def upsert_document(source: str, external_id: str, title: str, metadata: dict) -> str:
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
            {"source": source, "external_id": external_id,
             "title": title, "metadata": str(metadata)}
        )
        await session.commit()
        return str(result.scalar())