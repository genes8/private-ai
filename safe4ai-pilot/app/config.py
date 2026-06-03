from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_url: str = "postgresql+psycopg2://safe4ai:safe4ai@localhost:5432/safe4ai"
    qdrant_url: str = "http://localhost:6333"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    embedding_model: str = "nomic-embed-text"
    secret_key: str
    allowed_origins: str = "http://localhost:3000"
    enforce_https: bool = False
    audit_log_retention_days: int = 90
    audit_archive_dir: str = "data/audit-archive"
    cache_retention_days: int = 30
    semantic_cache_threshold: float = 0.92
    cost_per_1k_tokens: float = 0.0
    max_upload_size_mb: int = 50

    @field_validator("secret_key")
    @classmethod
    def _secret_key_strength(cls, v: str) -> str:
        weak = {"change-me", "secret", "password", "changeme", "test"}
        if v in weak or len(v) < 16:
            raise ValueError(
                "SECRET_KEY must be at least 16 characters and not a known-weak value; "
                "set a strong random value in your .env file"
            )
        return v

    @field_validator("max_upload_size_mb")
    @classmethod
    def _max_upload_size_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_upload_size_mb must be greater than 0")
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[1] / ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
