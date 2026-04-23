"""
Veda AI — Application Configuration
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    openai_api_key: str = ""
    use_local_llm: bool = False
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2:1.5b"

    # ── Whisper ───────────────────────────────────────────────────────
    whisper_model: str = "base"          # tiny / base / small / medium / large

    # ── MinIO / S3 ───────────────────────────────────────────────────
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "veda-videos"
    minio_secure: bool = False
    minio_public_url: str = ""

    # ── Temp scratch dir (FFmpeg working space) ───────────────────────
    temp_dir: str = "/tmp/veda"

    @property
    def temp_path(self) -> Path:
        return Path(self.temp_dir)

    # ── Redis / Celery ────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Database ──────────────────────────────────────────────────────
    database_url: str = "sqlite:///./veda.db"

    # ── App ───────────────────────────────────────────────────────────
    app_env: str = "development"
    max_upload_size_mb: int = 2000
    clip_min_duration: int = 20
    clip_max_duration: int = 30
    virality_threshold: int = 55

    class Config:
        env_file = ".env"
        extra = "ignore"

    def ensure_dirs(self):
        """Create temp scratch directories if they don't exist."""
        self.temp_path.mkdir(parents=True, exist_ok=True)


settings = Settings()
