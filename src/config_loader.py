import pyjson5 as json5
from pathlib import Path
from typing import TypedDict, Any


class LLMConfig(TypedDict):
    """Type definition for LLM configuration."""
    model_provider: str
    model: str | None
    temperature: float | None
    system_prompt: str | None


class ConfigError(Exception):
    """Base exception for configuration related errors."""
    pass


class ConfigFileNotFoundError(ConfigError):
    """Raised when the configuration file cannot be found."""
    pass


class ConfigValidationError(ConfigError):
    """Raised when the configuration fails validation."""
    pass


def load_config(config_path: str):
    """Load and validate configuration from JSON5 file.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise ConfigFileNotFoundError(f"Config file {config_path} not found")

    with open(config_file, "r", encoding="utf-8") as f:
        config: dict[str, Any] = json5.load(f)

    return config
