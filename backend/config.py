"""Backend settings. Paths are rooted here, independent of the launch directory."""
import os
from pathlib import Path
from typing import Annotated, Literal
from dotenv import load_dotenv
from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

ROOT = Path(__file__).resolve().parent
ENV_PATH = str(ROOT / ".env")
load_dotenv(ENV_PATH)

def origins(value):
    if isinstance(value, str):
        import json
        return json.loads(value) if value.strip().startswith("[") else [x.strip() for x in value.split(",") if x.strip()]
    return value

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_PATH, extra="ignore")
    OCR_PROVIDER: Literal["google_vision"] = "google_vision"
    GOOGLE_CLOUD_VISION_API_KEY: str = ""
    GOOGLE_VISION_MAX_ATTEMPTS: int = Field(2, ge=1, le=3)
    GOOGLE_VISION_TIMEOUT_SECONDS: float = Field(30, ge=1, le=120)
    GROQ_API_KEY: str = ""
    HOSTED_VLM_MODEL: str = ""
    HOSTED_VLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    HOSTED_VLM_TIMEOUT_SECONDS: float = Field(60, gt=0, le=300)
    HOSTED_VLM_MAX_ATTEMPTS: int = Field(2, ge=1, le=3)
    HOSTED_VLM_MAX_RETRY_WAIT_SECONDS: float = Field(30, ge=0, le=60)
    HOSTED_VLM_MIN_INTERVAL_SECONDS: float = Field(0, ge=0, le=60)
    HOSTED_VLM_MAX_OUTPUT_TOKENS: int = Field(2048, ge=128, le=8192)
    HOSTED_VLM_CACHE: bool = True
    # Text-only tier over OCR tokens, any OpenAI-compatible chat API. Empty URL/key reuse the Groq
    # settings; unset pacing reuses the VLM's when both tiers call the same provider, else no pacing.
    HOSTED_LLM_MODEL: str = ""
    HOSTED_LLM_BASE_URL: str = ""
    HOSTED_LLM_API_KEY: str = ""
    HOSTED_LLM_MIN_INTERVAL_SECONDS: float | None = Field(None, ge=0, le=60)
    REVIEW_THRESHOLD: float = Field(75, ge=0, le=100)
    FALLBACK_THRESHOLD: float = Field(60, ge=0, le=100)
    HYBRID_CONFLICT_POLICY: str = Field("keep_local", pattern="^(keep_local|prefer_hosted)$")
    DATABASE_URL: str = ""
    DATA_DIR: str = str(ROOT / "data")
    LAYOUTLM_MODEL_ROOT: str = str(ROOT.parent / "layoutLM__model")
    LAYOUTLM_DEVICE: str = Field("auto", pattern="^(auto|cpu|cuda)$")
    RESEARCH_REPORT_DIR: str = str(ROOT / "data/paper_runs")
    MAX_UPLOAD_MB: int = Field(10, ge=1, le=20)
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode, BeforeValidator(origins)] = ["http://localhost:5173", "http://localhost:5174"]

settings = Settings()
