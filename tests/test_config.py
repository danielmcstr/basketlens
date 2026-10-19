"""Unit tests for Phase 0 project foundation and basketlens.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from basketlens import PROJECT_ROOT, Settings, get_settings


def test_default_settings_without_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify default settings match local Docker services and PDF case study."""
    for key in (
        "BASKETLENS_MONGO_HOST",
        "BASKETLENS_MONGO_PORT",
        "BASKETLENS_MONGO_DB",
        "BASKETLENS_MONGO_URI",
        "BASKETLENS_CASSANDRA_HOST",
        "BASKETLENS_CASSANDRA_PORT",
        "BASKETLENS_CASSANDRA_KEYSPACE",
        "BASKETLENS_REDIS_HOST",
        "BASKETLENS_REDIS_PORT",
        "BASKETLENS_DATASET_DIR",
        "BASKETLENS_REFERENCE_DAY",
        "BASKETLENS_SECONDS_PER_DAY",
        "BASKETLENS_PROFILE_TTL_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = get_settings(_env_file=None)

    assert isinstance(settings, Settings)
    assert settings.mongo_host == "localhost"
    assert settings.mongo_port == 27017
    assert settings.mongo_db == "basketlens"
    assert settings.effective_mongo_uri == "mongodb://localhost:27017"
    assert settings.cassandra_host == "localhost"
    assert settings.cassandra_port == 9042
    assert settings.cassandra_keyspace == "basketlens"
    assert settings.redis_host == "localhost"
    assert settings.redis_port == 6379
    assert settings.dataset_dir == Path("dataset")
    assert settings.reference_day == 650
    assert settings.full_cutoff_day == 711
    assert settings.seconds_per_day == 5
    assert settings.profile_ttl_seconds == 60
    assert settings.case_study_household == 208
    assert settings.batch_size == 50_000
    assert settings.recent_baskets_limit == 5


def test_dataset_path_resolution() -> None:
    """Verify dataset_dir and csv_path resolve against PROJECT_ROOT."""
    settings = get_settings(_env_file=None)
    assert settings.resolved_dataset_dir == PROJECT_ROOT / "dataset"
    assert settings.resolved_dataset_dir.is_dir()

    expected_csvs = [
        "transaction_data.csv",
        "causal_data.csv",
        "product.csv",
        "coupon.csv",
        "campaign_table.csv",
        "coupon_redempt.csv",
        "hh_demographic.csv",
        "campaign_desc.csv",
    ]
    for filename in expected_csvs:
        csv_file = settings.csv_path(filename)
        assert csv_file.is_file(), f"Expected CSV file not found: {csv_file}"


def test_environment_variable_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify BASKETLENS_* environment variables override default Settings."""
    monkeypatch.setenv("BASKETLENS_REFERENCE_DAY", "654")
    monkeypatch.setenv("BASKETLENS_SECONDS_PER_DAY", "10")
    monkeypatch.setenv("BASKETLENS_PROFILE_TTL_SECONDS", "120")
    monkeypatch.setenv("BASKETLENS_MONGO_URI", "mongodb://mongo-custom:27018")

    settings = get_settings(_env_file=None)

    assert settings.reference_day == 654
    assert settings.seconds_per_day == 10
    assert settings.profile_ttl_seconds == 120
    assert settings.effective_mongo_uri == "mongodb://mongo-custom:27018"


def test_required_dependencies_importable() -> None:
    """Verify all pinned core dependencies can be imported inside .venv."""
    import cassandra  # noqa: F401
    import polars  # noqa: F401
    import pymongo  # noqa: F401
    import redis  # noqa: F401


def test_draft_documentation_schema_alignment() -> None:
    """Verify documentation reflects official PDF schema and architectural decisions."""
    draft_path = PROJECT_ROOT / "docs" / "DRAFT.md"
    if draft_path.is_file():
        content = draft_path.read_text(encoding="utf-8")
    else:
        content = (
            (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
            + "\n"
            + (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        )

    for col in (
        "classification_1",
        "classification_2",
        "classification_3",
        "HOMEOWNER_DESC",
        "classification_4",
        "classification_5",
        "KID_CATEGORY_DESC",
        "household_key",
    ):
        assert col in content

    assert "display_type" in content and "text" in content
    assert "mailer_page" in content and "text" in content
    assert "REFERENCE_DAY = 650" in content
    assert "household_key = 208" in content
