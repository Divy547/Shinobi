"""Configuration settings for RepoVet MCP using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_prefix="REPOVET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment & Logging
    environment: str = Field(
        default="development",
        description="Deployment environment (development, staging, production, testing)",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Server Identity
    server_name: str = Field(
        default="repovet-mcp",
        description="Name of the MCP server instance",
    )
    server_version: str = Field(
        default="0.1.0",
        description="Version of the MCP server instance",
    )

    # GitHub API Configuration (Optional - falls back to unauthenticated public API)
    github_token: SecretStr | None = Field(
        default=None,
        description="Personal access token for GitHub API (recommended to avoid rate limits)",
    )
    github_api_url: str = Field(
        default="https://api.github.com",
        description="Base URL for GitHub API operations",
    )

    # Configuration File Paths
    scoring_config_path: Path = Field(
        default=Path("config/scoring.yaml"),
        description="Filesystem path to the scoring rubric configuration YAML",
    )
    thresholds_config_path: Path = Field(
        default=Path("config/thresholds.yaml"),
        description="Filesystem path to the decision thresholds configuration YAML",
    )

    # Storage & Output Directories
    reports_dir: Path = Field(
        default=Path("reports"),
        description="Directory for generated PDF audit reports",
    )
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory for cached audit payloads and raw evidence",
    )

    @property
    def has_github_auth(self) -> bool:
        """Indicate whether an authenticated GitHub token is configured."""
        return self.github_token is not None and bool(self.github_token.get_secret_value().strip())

    def load_scoring_config(self) -> dict[str, Any]:
        """Load and parse the scoring YAML configuration."""
        path = self.scoring_config_path
        if not path.exists():
            fallback = Path(__file__).resolve().parent.parent.parent.parent / path
            if fallback.exists():
                path = fallback
            else:
                msg = f"Scoring configuration file not found at: {self.scoring_config_path}"
                raise FileNotFoundError(msg)
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                msg = f"Invalid scoring config format in {path}"
                raise ValueError(msg)
            return data

    def load_thresholds_config(self) -> dict[str, Any]:
        """Load and parse the thresholds YAML configuration."""
        path = self.thresholds_config_path
        if not path.exists():
            fallback = Path(__file__).resolve().parent.parent.parent.parent / path
            if fallback.exists():
                path = fallback
            else:
                msg = f"Thresholds configuration file not found at: {self.thresholds_config_path}"
                raise FileNotFoundError(msg)
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                msg = f"Invalid thresholds config format in {path}"
                raise ValueError(msg)
            return data

    def validate_startup_config(self) -> None:
        """Validate required configuration files, directories, and parameters at server startup."""
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            msg = (
                f"Invalid log level '{self.log_level}'. Must be one of: {sorted(valid_log_levels)}"
            )
            raise ValueError(msg)

        # Validate configuration YAMLs
        self.load_scoring_config()
        self.load_thresholds_config()

        # Validate storage directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        (self.reports_dir / "generated").mkdir(parents=True, exist_ok=True)

        # Validate GitHub API base URL
        if not self.github_api_url.startswith(("http://", "https://")):
            msg = f"Invalid GitHub API URL: '{self.github_api_url}' must start with http:// or https://"
            raise ValueError(msg)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
