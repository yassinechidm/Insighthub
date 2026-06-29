from app.connectors.jira.transformer import normalize_issue, chunk_issue


def test_normalize_issue_extracts_basic_fields():
    issue = {
        "key": "IH-1",
        "fields": {
            "summary": "Example issue",
            "description": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Hello Jira"}]}
                ],
            },
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "assignee": {"displayName": "Alice"},
            "reporter": {"displayName": "Bob"},
            "issuetype": {"name": "Task"},
            "created": "2024-01-01T00:00:00.000Z",
            "updated": "2024-01-02T00:00:00.000Z",
            "comment": {"comments": []},
        },
    }

    normalized = normalize_issue(issue, "tenant-a")

    assert normalized["external_id"] == "IH-1"
    assert normalized["title"] == "Example issue"
    assert normalized["description"] == "Hello Jira"
    assert normalized["tenant_id"] == "tenant-a"


def test_chunk_issue_creates_body_and_comment_chunks():
    normalized = {
        "external_id": "IH-2",
        "title": "Needs follow-up",
        "description": "Detailed description",
        "status": "To Do",
        "priority": "Medium",
        "assignee": "Alice",
        "reporter": "Bob",
        "issue_type": "Bug",
        "created_at": "2024-01-01T00:00:00.000Z",
        "updated_at": "2024-01-02T00:00:00.000Z",
        "comments": [{"author": "Carol", "body": "Looks good"}],
        "tenant_id": "tenant-a",
    }

    chunks = chunk_issue(normalized)

    assert len(chunks) >= 2
    assert any(chunk.metadata["chunk_type"] == "body" for chunk in chunks)
    assert any(chunk.metadata["chunk_type"] == "comment" for chunk in chunks)
