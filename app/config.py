from pydantic import AnyUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: AnyUrl = "redis://localhost:6379/0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    CHAT_HISTORY_LIMIT: int = 50  # max messages kept per room

    class Config:
        env_file = ".env"


settings = Settings()
