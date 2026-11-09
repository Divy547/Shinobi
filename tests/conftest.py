"""Pytest fixtures for RepoVet MCP test suite."""

from collections.abc import Generator
from pathlib import Path

import pytest

from repovet_mcp.config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None, None, None]:
    """Ensure lru_cache for get_settings is cleared before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def clean_settings(monkeypatch: pytest.MonkeyPatch, project_root: Path) -> Settings:
    """Provide a pristine Settings instance with explicit paths pointing to project configs."""
    # Ensure no environment variables interfere
    monkeypatch.delenv("REPOVET_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("REPOVET_ENVIRONMENT", raising=False)
    monkeypatch.delenv("REPOVET_LOG_LEVEL", raising=False)
    monkeypatch.delenv("REPOVET_SERVER_NAME", raising=False)

    return Settings(
        _env_file=None,
        scoring_config_path=project_root / "config" / "scoring.yaml",
        thresholds_config_path=project_root / "config" / "thresholds.yaml",
        reports_dir=project_root / "reports",
        data_dir=project_root / "data",
    )
