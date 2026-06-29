from dataclasses import dataclass
from datetime import datetime

CHUNK_SIZE = 512  # tokens approximatifs (~2000 caractères)

@dataclass
class Chunk:
    chunk_id: str          # "jira-PROJ-123-0", "jira-PROJ-123-1"...
    document_id: str       # clé externe Jira (ex: "PROJ-123")
    source: str            # "jira"
    content: str
    metadata: dict
    tenant_id: str

def normalize_issue(issue: dict, tenant_id: str) -> dict:
    fields = issue["fields"]
    return {
        "external_id": issue["key"],
        "source": "jira",
        "title": fields.get("summary", ""),
        "description": _adf_to_text(fields.get("description")),
        "status": fields.get("status", {}).get("name", ""),
        "priority": fields.get("priority", {}).get("name", ""),
        "assignee": (fields.get("assignee") or {}).get("displayName", ""),
        "reporter": (fields.get("reporter") or {}).get("displayName", ""),
        "issue_type": fields.get("issuetype", {}).get("name", ""),
        "created_at": fields.get("created"),
        "updated_at": fields.get("updated"),
        "comments": _extract_comments(fields.get("comment", {}).get("comments", [])),
        "tenant_id": tenant_id,
    }

def chunk_issue(normalized: dict) -> list[Chunk]:
    chunks = []
    base_id = normalized["external_id"]

    metadata = {
        "source": "jira",
        "external_id": base_id,
        "status": normalized["status"],
        "priority": normalized["priority"],
        "assignee": normalized["assignee"],
        "issue_type": normalized["issue_type"],
        "created_at": normalized["created_at"],
        "updated_at": normalized["updated_at"],
    }

    # Chunk principal : titre + description
    main_content = f"[{base_id}] {normalized['title']}\n\n{normalized['description']}"
    for i, text in enumerate(_split_text(main_content)):
        chunks.append(Chunk(
            chunk_id=f"jira-{base_id}-{i}",
            document_id=base_id,
            source="jira",
            content=text,
            metadata={**metadata, "chunk_type": "body"},
            tenant_id=normalized["tenant_id"],
        ))

    # Chunks commentaires (1 par commentaire)
    offset = len(chunks)
    for j, comment in enumerate(normalized["comments"]):
        text = f"[{base_id}] Commentaire de {comment['author']}:\n{comment['body']}"
        chunks.append(Chunk(
            chunk_id=f"jira-{base_id}-c{j}",
            document_id=base_id,
            source="jira",
            content=text[:2000],
            metadata={**metadata, "chunk_type": "comment", "comment_author": comment["author"]},
            tenant_id=normalized["tenant_id"],
        ))

    return chunks

def _split_text(text: str, max_chars: int = 2000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts = []
    while text:
        parts.append(text[:max_chars])
        text = text[max_chars:]
    return parts

def _extract_comments(comments: list) -> list[dict]:
    result = []
    for c in comments:
        result.append({
            "author": (c.get("author") or {}).get("displayName", ""),
            "body": _adf_to_text(c.get("body")),
            "created": c.get("created"),
        })
    return result

def _adf_to_text(adf: dict | str | None) -> str:
    """Convertit Atlassian Document Format en texte brut."""
    if adf is None:
        return ""
    if isinstance(adf, str):
        return adf
    texts = []
    def traverse(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                texts.append(node.get("text", ""))
            for child in node.get("content", []):
                traverse(child)
    traverse(adf)
    return " ".join(texts).strip()