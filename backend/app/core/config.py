"""应用配置管理 —— 使用 pydantic-settings 加载环境变量"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """智翼平台全局配置"""

    # ── 应用基础 ──
    APP_NAME: str = "智翼 AI 学习助手"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-to-a-random-secret-key-at-least-32-chars"

    # ── 数据库 ──
    DATABASE_URL: str = "sqlite+aiosqlite:///./zhiyi.db"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── LLM ──
    LLM_API_KEY: str = "sk-your-api-key"
    LLM_API_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"

    # ── CORS ──
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # ── 文件上传 ──
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    # ── JWT ──
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 86400  # 24 小时

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
