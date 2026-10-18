"""Centralized typed configuration for BasketLens using pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed environment settings for BasketLens polyglot persistence and replay."""

    model_config = SettingsConfigDict(
        env_prefix="BASKETLENS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Dataset configuration
    dataset_dir: Path = Field(
        default=Path("dataset"),
        description="Directory containing the 8 official dunnhumby CSV files.",
    )

    # MongoDB (Document Store: 360º Household Profiles)
    mongo_host: str = Field(default="localhost")
    mongo_port: int = Field(default=27017)
    mongo_db: str = Field(default="basketlens")
    mongo_uri: Optional[str] = Field(default=None)

    # Apache Cassandra (Wide-Column Store: Historical Transactions & Causal Data)
    cassandra_host: str = Field(default="localhost")
    cassandra_port: int = Field(default=9042)
    cassandra_keyspace: str = Field(default="basketlens")
    cassandra_concurrency: int = Field(default=64)

    # Redis (Key-Value Speed Layer: Active Campaigns/Coupons with TTL & Profile Cache)
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)

    # Ingestion & Operational Simulation Parameters
    batch_size: int = Field(default=50_000, ge=1)
    recent_baskets_limit: int = Field(default=5, ge=1)
    reference_day: int = Field(default=650, ge=1, le=711)
    full_cutoff_day: int = Field(default=711, ge=1, le=711)
    seconds_per_day: int = Field(default=5, ge=1)
    profile_ttl_seconds: int = Field(default=60, ge=1)
    case_study_household: int = Field(default=208, ge=1)

    @property
    def effective_mongo_uri(self) -> str:
        """Return explicit mongo_uri if set, otherwise build from host and port."""
        if self.mongo_uri:
            return self.mongo_uri
        return f"mongodb://{self.mongo_host}:{self.mongo_port}"

    @property
    def resolved_dataset_dir(self) -> Path:
        """Resolve dataset_dir against PROJECT_ROOT when relative."""
        if self.dataset_dir.is_absolute():
            return self.dataset_dir
        return (PROJECT_ROOT / self.dataset_dir).resolve()

    def csv_path(self, filename: str) -> Path:
        """Return the resolved path to a CSV file inside the dataset directory."""
        return self.resolved_dataset_dir / filename


def get_settings(**overrides: object) -> Settings:
    """Instantiate and return the BasketLens Settings object."""
    return Settings(**overrides)
