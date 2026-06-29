from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://insighthub:changeme@localhost:5432/insighthub"

    jira_url: str = ""
    jira_user: str = ""
    jira_api_token: str = ""
    jira_project_keys: str = ""
    jira_max_results: int = 50

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    bedrock_embedding_model: str = "amazon.titan-embed-text-v2:0"

    @property
    def jira_projects(self) -> list[str]:
        return [p.strip() for p in self.jira_project_keys.split(",") if p.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()