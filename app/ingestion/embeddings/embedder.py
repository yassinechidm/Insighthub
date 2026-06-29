import hashlib
import json
import re
from config import settings
from app.connectors.jira.transformer import Chunk

_client = None


def _bedrock():
    global _client
    if _client is None:
        try:
            import boto3
        except ImportError:
            raise RuntimeError("boto3 is not installed")

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
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        try:
            body = json.dumps({"inputText": text[:8000]})
            resp = _bedrock().invoke_model(
                modelId=settings.bedrock_embedding_model,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            return json.loads(resp["body"].read())["embedding"]
        except Exception:
            pass

    return _fallback_embedding(text)


def _fallback_embedding(text: str) -> list[float]:
    tokens = [token for token in re.split(r"\W+", text.lower()) if token]
    vector = [0.0] * 1536
    for index, token in enumerate(tokens[:1536]):
        digest = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16)
        vector[index % 1536] += digest / 10**8
    return vector