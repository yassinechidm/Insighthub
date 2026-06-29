from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.connectors.jira.pipeline import sync_jira_issues

router = APIRouter()


class JiraSyncRequest(BaseModel):
    project_key: str | None = None
    updated_after: str | None = None
    demo: bool = False


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ingestion/jira/sync")
async def sync_jira(request: JiraSyncRequest) -> dict:
    try:
        return await sync_jira_issues(
            project_key=request.project_key,
            updated_after=request.updated_after,
            demo=request.demo,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.api_route("/ingestion/jira/demo", methods=["GET", "POST"])
async def demo_jira_sync() -> dict:
    return await sync_jira_issues(demo=True)
