import json
import boto3
from config import settings
from app.connectors.jira.transformer import Chunk

_client = None

def _bedrock():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
    return _client

async def embed_chunks(chunks: list[Chunk]) -> list[tuple[Chunk, list[float]]]:
    result = []
    for chunk in chunks:
        vector = _embed_text(chunk.content)
        result.append((chunk, vector))
    return result

def _embed_text(text: str) -> list[float]:
    body = json.dumps({"inputText": text[:8000]})
    resp = _bedrock().invoke_model(
        modelId=settings.bedrock_embedding_model,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["body"].read())["embedding"]