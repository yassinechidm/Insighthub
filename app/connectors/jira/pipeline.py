from typing import Any
from config import settings
from app.connectors.jira.client import JiraClient
from app.connectors.jira.transformer import chunk_issue, normalize_issue
from app.db.vector_store import upsert_chunks, upsert_document
from app.ingestion.embeddings.embedder import embed_chunks


def _sample_issue() -> dict[str, Any]:
    return {
        "key": "IH-DEMO-1",
        "fields": {
            "summary": "Demo issue for local ingestion",
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "This issue was generated locally to verify the ingestion flow."}],
                    }
                ],
            },
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "assignee": {"displayName": "Local User"},
            "reporter": {"displayName": "System"},
            "issuetype": {"name": "Task"},
            "created": "2024-01-01T00:00:00.000Z",
            "updated": "2024-01-02T00:00:00.000Z",
            "comment": {"comments": [{"author": {"displayName": "Reviewer"}, "body": "Looks good."}]},
        },
    }


async def sync_jira_issues(
    project_key: str | None = None,
    updated_after: str | None = None,
    demo: bool = False,
) -> dict[str, Any]:
    if demo:
        issues = [_sample_issue()]
    else:
        project_key = project_key or (settings.jira_projects[0] if settings.jira_projects else None)
        if not project_key:
            raise ValueError("No Jira project key configured")

        if not settings.jira_url or not settings.jira_user or not settings.jira_api_token:
            return {
                "status": "skipped",
                "message": "Jira credentials are not configured; using a demo payload instead.",
                "issues_processed": 0,
                "demo": True,
            }

        client = JiraClient()
        issues = [issue async for issue in client.fetch_all_issues(project_key, updated_after)]

    documents_created = 0
    chunks_created = 0

    for issue in issues:
        normalized = normalize_issue(issue, "default")
        chunks = chunk_issue(normalized)
        embedded_chunks = await embed_chunks(chunks)

        document_id = await upsert_document(
            source="jira",
            external_id=normalized["external_id"],
            title=normalized["title"],
            metadata={
                "status": normalized["status"],
                "priority": normalized["priority"],
                "assignee": normalized["assignee"],
                "issue_type": normalized["issue_type"],
            },
        )
        await upsert_chunks(embedded_chunks, document_id)

        documents_created += 1 if document_id else 0
        chunks_created += len(chunks)

    return {
        "status": "ok",
        "project_key": project_key,
        "issues_processed": len(issues),
        "documents_created": documents_created,
        "chunks_created": chunks_created,
        "demo": demo,
    }