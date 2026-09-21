"""
Central application configuration.

All configuration is sourced from environment variables (via a .env file in
local/dev, or real environment variables in containers). Nothing here should
ever contain a hard-coded secret.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # --- Database -----------------------------------------------------
    DATABASE_URL: str = (
        "postgresql+psycopg2://perf:perf@localhost:5432/perf_intelligence"
    )

    # --- PageSpeed Insights ------------------------------------------
    PSI_PROVIDER: Literal["mock", "real"] = "mock"
    PSI_API_KEY: str = ""
    PSI_STRATEGY: Literal["mobile", "desktop"] = "mobile"
    PSI_API_BASE_URL: str = (
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    )
    PSI_TIMEOUT_SECONDS: int = 60

    # --- LLM ---------------------------------------------------------
    LLM_PROVIDER: Literal["mock", "groq"] = "mock"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    LLM_PROMPT_VERSION: str = "v1"

    # --- Raw PSI storage ---------------------------------------------
    STORAGE_MODE: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_ROOT: str = "../storage/raw"

    # --- Scheduler ----------------------------------------------------
    RUN_INTERVAL_HOURS: int = 6
    AUTO_LLM_ANALYSIS: bool = False
    SCHEDULER_ENABLED: bool = True

    # --- Stabilization thresholds ------------------------------------
    STABILIZATION_WINDOW_RUNS: int = 5
    STABILIZATION_MIN_RUNS: int = 3
    VARIABILITY_FLAG_RELATIVE_STDEV: float = 0.20

    # --- Evidence thresholds -----------------------------------------
    LCP_GOOD_MS: int = 2500
    LCP_POOR_MS: int = 4000
    CLS_GOOD: float = 0.1
    CLS_POOR: float = 0.25
    TBT_GOOD_MS: int = 200
    TBT_POOR_MS: int = 600
    FCP_GOOD_MS: int = 1800
    FCP_POOR_MS: int = 3000
    UNUSED_JS_FLAG_BYTES: int = 100_000
    IMAGE_SAVINGS_FLAG_BYTES: int = 100_000
    THIRD_PARTY_TBT_FLAG_MS: int = 250
    BANDWIDTH_GOOD_BYTES: int = 1_800_000
    BANDWIDTH_POOR_BYTES: int = 3_000_000

    # --- Priority engine weights -------------------------------------
    PRIORITY_IMPACT_WEIGHT: float = 0.5
    PRIORITY_EASE_WEIGHT: float = 0.3
    PRIORITY_CONFIDENCE_WEIGHT: float = 0.2

    # --- Recommendation validation -----------------------------------
    RECOMMENDATION_NEEDS_REVIEW_CONFIDENCE: float = 0.5

    ENV: Literal["development", "test", "production"] = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()