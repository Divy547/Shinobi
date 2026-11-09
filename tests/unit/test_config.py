"""Unit tests for configuration loading and validation."""

from pathlib import Path

import pytest
from pydantic import SecretStr

from repovet_mcp.config.settings import Settings


def test_default_settings(clean_settings: Settings) -> None:
    """Verify default settings values and graceful handling of missing optional secrets."""
    assert clean_settings.environment == "development"
    assert clean_settings.log_level == "INFO"
    assert clean_settings.server_name == "repovet-mcp"
    assert clean_settings.server_version == "0.1.0"
    assert clean_settings.github_token is None
    assert clean_settings.gemini_api_key is None
    assert clean_settings.has_github_auth is False
    assert clean_settings.has_ai_auth is False
    assert clean_settings.github_api_url == "https://api.github.com"
    assert clean_settings.ai_model == "gemini-2.0-flash"


def test_settings_with_env_override(monkeypatch: pytest.MonkeyPatch, project_root: Path) -> None:
    """Verify environment variables properly override defaults."""
    monkeypatch.setenv("REPOVET_ENVIRONMENT", "production")
    monkeypatch.setenv("REPOVET_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("REPOVET_GITHUB_TOKEN", "ghp_testtoken1234567890")
    monkeypatch.setenv("REPOVET_GEMINI_API_KEY", "gemini_secret_key_abc")

    settings = Settings(
        scoring_config_path=project_root / "config" / "scoring.yaml",
        thresholds_config_path=project_root / "config" / "thresholds.yaml",
    )

    assert settings.environment == "production"
    assert settings.log_level == "DEBUG"
    assert isinstance(settings.github_token, SecretStr)
    assert settings.github_token.get_secret_value() == "ghp_testtoken1234567890"
    assert settings.has_github_auth is True
    assert isinstance(settings.gemini_api_key, SecretStr)
    assert settings.gemini_api_key.get_secret_value() == "gemini_secret_key_abc"
    assert settings.has_ai_auth is True


def test_scoring_yaml_structure(clean_settings: Settings) -> None:
    """Verify scoring.yaml exists, loads cleanly, and matches the 10-criterion 0-20 methodology."""
    scoring_data = clean_settings.load_scoring_config()

    assert "scale" in scoring_data
    scale = scoring_data["scale"]
    assert scale["min_score_per_criterion"] == 0
    assert scale["max_score_per_criterion"] == 2
    assert scale["total_criteria"] == 10
    assert scale["max_total_score"] == 20

    assert "criteria" in scoring_data
    criteria = scoring_data["criteria"]
    assert len(criteria) == 10

    criterion_ids = set()
    for item in criteria:
        assert "id" in item
        assert "name" in item
        assert "phase" in item
        assert "max_score" in item
        assert item["max_score"] == 2
        assert "rubric" in item
        rubric = item["rubric"]
        assert "score_0" in rubric
        assert "score_1" in rubric
        assert "score_2" in rubric
        criterion_ids.add(item["id"])

    assert len(criterion_ids) == 10


def test_thresholds_yaml_structure(clean_settings: Settings) -> None:
    """Verify thresholds.yaml exists, loads cleanly, and defines all 4 decision thresholds."""
    thresholds_data = clean_settings.load_thresholds_config()

    assert "decisions" in thresholds_data
    decisions = thresholds_data["decisions"]

    required_decisions = ["APPROVE", "CONDITIONAL", "NEEDS_MANUAL_REVIEW", "REJECT"]
    for decision_key in required_decisions:
        assert decision_key in decisions
        decision_info = decisions[decision_key]
        assert "name" in decision_info
        assert "score_range" in decision_info
        assert "min" in decision_info["score_range"]
        assert "max" in decision_info["score_range"]

    # Verify score continuity and bounds
    assert decisions["APPROVE"]["score_range"]["max"] == 20
    assert decisions["APPROVE"]["score_range"]["min"] >= 16
    assert decisions["REJECT"]["score_range"]["min"] == 0

    assert "critical_disqualifiers" in thresholds_data
    disqualifiers = thresholds_data["critical_disqualifiers"]
    assert len(disqualifiers) >= 4
    for dq in disqualifiers:
        assert "id" in dq
        assert "name" in dq
        assert "condition" in dq
        assert "action" in dq
        assert "severity" in dq


def test_missing_config_files(tmp_path: Path) -> None:
    """Verify FileNotFoundError is raised when YAML configuration files do not exist."""
    bad_settings = Settings(
        scoring_config_path=tmp_path / "non_existent_scoring.yaml",
        thresholds_config_path=tmp_path / "non_existent_thresholds.yaml",
    )

    with pytest.raises(FileNotFoundError, match="Scoring configuration file not found"):
        bad_settings.load_scoring_config()

    with pytest.raises(FileNotFoundError, match="Thresholds configuration file not found"):
        bad_settings.load_thresholds_config()
