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

    # AI Provider & Orchestration Configuration
    gemini_api_key: SecretStr | None = Field(
        default=None,
        description="Google Gemini API key for qualitative analysis and tool orchestration",
    )
    ai_model: str = Field(
        default="gemini-2.0-flash",
        description="Default AI model identifier for qualitative vetting and orchestration",
    )
    orchestration_timeout_seconds: float = Field(
        default=120.0,
        description="Overall timeout for a Gemini orchestration session in seconds",
    )
    mcp_timeout_seconds: float = Field(
        default=30.0,
        description="Per-tool call timeout for MCP clients in seconds",
    )
    max_orchestration_steps: int = Field(
        default=10,
        description="Maximum sequential tool-call iterations per orchestration session",
    )

    # GitHub MCP Server Client Configuration
    github_mcp_command: str = Field(
        default="npx",
        description="Command to launch the official GitHub MCP server (e.g. npx or docker)",
    )
    github_mcp_args: list[str] = Field(
        default_factory=lambda: ["-y", "@modelcontextprotocol/server-github"],
        description="Arguments passed to the GitHub MCP server command",
    )
    github_mcp_token_env_var: str = Field(
        default="GITHUB_PERSONAL_ACCESS_TOKEN",
        description="Environment variable name used by the GitHub MCP server for authentication",
    )

    # Shinobi MCP Server Client Configuration
    shinobi_mcp_command: str = Field(
        default="repovet-mcp",
        description="Command to launch the Shinobi MCP server for client orchestration",
    )
    shinobi_mcp_args: list[str] = Field(
        default_factory=list,
        description="Arguments passed to the Shinobi MCP server command",
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

    @property
    def has_ai_auth(self) -> bool:
        """Indicate whether an AI provider API key is configured."""
        return self.gemini_api_key is not None and bool(
            self.gemini_api_key.get_secret_value().strip()
        )

    def load_scoring_config(self) -> dict[str, Any]:
        """Load and parse the scoring YAML configuration."""
        if not self.scoring_config_path.exists():
            msg = f"Scoring configuration file not found at: {self.scoring_config_path}"
            raise FileNotFoundError(msg)
        with self.scoring_config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                msg = f"Invalid scoring config format in {self.scoring_config_path}"
                raise ValueError(msg)
            return data

    def load_thresholds_config(self) -> dict[str, Any]:
        """Load and parse the thresholds YAML configuration."""
        if not self.thresholds_config_path.exists():
            msg = f"Thresholds configuration file not found at: {self.thresholds_config_path}"
            raise FileNotFoundError(msg)
        with self.thresholds_config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                msg = f"Invalid thresholds config format in {self.thresholds_config_path}"
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

    def validate_orchestration_config(self) -> None:
        """Validate settings required specifically for AI orchestration and MCP clients."""
        if not self.has_ai_auth:
            msg = (
                "Gemini API key is required for AI orchestration. "
                "Set REPOVET_GEMINI_API_KEY in environment or .env."
            )
            raise ValueError(msg)
        if self.orchestration_timeout_seconds <= 0:
            msg = f"orchestration_timeout_seconds must be positive, got {self.orchestration_timeout_seconds}"
            raise ValueError(msg)
        if self.mcp_timeout_seconds <= 0:
            msg = f"mcp_timeout_seconds must be positive, got {self.mcp_timeout_seconds}"
            raise ValueError(msg)
        if self.max_orchestration_steps <= 0:
            msg = f"max_orchestration_steps must be positive, got {self.max_orchestration_steps}"
            raise ValueError(msg)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
