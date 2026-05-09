from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_url: str = "postgresql+psycopg2://safe4ai:safe4ai@localhost:5432/safe4ai"
    qdrant_url: str = "http://localhost:6333"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    embedding_model: str = "nomic-embed-text"
    secret_key: str = Field(default_factory=lambda: "change-me")
    allowed_origins: str = "http://localhost:5173"
    enforce_https: bool = False
    audit_log_retention_days: int = 90
    cache_retention_days: int = 30
    semantic_cache_threshold: float = 0.92
    cost_per_1k_tokens: float = 0.0
    max_upload_size_mb: int = 50

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
