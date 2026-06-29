import httpx
from typing import AsyncGenerator
from config import settings

class JiraClient:
    def __init__(self):
        self.base_url = settings.jira_url.rstrip("/")
        self.auth = (settings.jira_user, settings.jira_api_token)
        self.headers = {"Accept": "application/json"}

    async def fetch_all_issues(
        self, project_key: str, updated_after: str | None = None
    ) -> AsyncGenerator[dict, None]:
        jql = f'project = "{project_key}"'
        if updated_after:
            jql += f' AND updated >= "{updated_after}"'
        jql += " ORDER BY updated ASC"

        start_at = 0
        max_results = settings.jira_max_results

        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    f"{self.base_url}/rest/api/3/search",
                    params={"jql": jql, "startAt": start_at,
                            "maxResults": max_results,
                            "fields": "summary,description,comment,status,"
                                      "priority,assignee,reporter,created,updated,issuetype"},
                    auth=self.auth,
                    headers=self.headers,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                issues = data.get("issues", [])

                for issue in issues:
                    yield issue

                start_at += len(issues)
                if start_at >= data["total"] or not issues:
                    break