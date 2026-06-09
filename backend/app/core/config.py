from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "AI Portfolio Analyst"
    environment: str = "development"
    secret_key: str = "change-me-in-production"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/portfolio_analyst"

    # AI
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Market data
    polygon_api_key: str = ""
    news_api_key: str = ""

    # LangSmith observability
    langsmith_api_key: str = ""
    langchain_tracing_v2: bool = True
    langchain_project: str = "portfolio-analyst"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
