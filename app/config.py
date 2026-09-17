from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "CodeSentinel"
    debug: bool = True
    port: int = 8000
    
    # Database
    database_url: str = "sqlite:///./codesentinel.db" # Default fallback SQLite for simple zero-config testing, Postgres URL in prod
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # GitHub
    github_webhook_secret: Optional[str] = "secret"
    github_token: Optional[str] = None
    
    # AI Provider
    ai_provider: str = "gemini" # gemini, openai, or mock
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
