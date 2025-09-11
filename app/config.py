from pydantic import AnyUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: AnyUrl = "redis://localhost:6379/0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    CHAT_HISTORY_LIMIT: int = 50
    HISTORY_TTL_SECONDS: int = 604800
    JWT_SECRET: str = "change-me"
    JWT_EXPIRES_MINUTES: int = 60
    ALLOW_ANON_WS: bool = False
    RATE_LIMIT_TOKENS_PER_SEC: float = 10.0
    RATE_LIMIT_BURST: int = 20

    class Config:
        env_file = ".env"


settings = Settings()
