from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    GOOGLE_CLOUD_VISION_API_KEY: str = ""
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/emunim"
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174"]


settings = Settings()
