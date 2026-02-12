import os
import re
from pathlib import Path
from typing import TypedDict, NotRequired, Any
import pyjson5 as json5

class ConfigError(Exception):
    """Base exception for configuration related errors."""
    pass


class ConfigFileNotFoundError(ConfigError):
    """Raised when the configuration file cannot be found."""
    pass


class ConfigValidationError(ConfigError):
    """Raised when the configuration fails validation."""
    pass

class LLMConfig(TypedDict):
    """Type definition for LLM configuration."""
    model_provider: NotRequired[str]
    provider: NotRequired[str]
    model: NotRequired[str]
    temperature: NotRequired[float]
    system_prompt: NotRequired[str]


def normalize_config(cfg: dict) -> LLMConfig:
    """
    Normalize alias keys so internal code can rely on 'model_provider'.
    """
    pv = cfg.get("provider")
    mp = cfg.get("model_provider")

    if pv is None and mp is None:
        raise ConfigValidationError(
            '"provider" needs to be specified'
        )
    elif pv is not None and mp is not None:
        raise ConfigValidationError(
            'Both "provider" and "model_provider" are specified'
        )
    elif pv is None and mp is not None:
        cfg["provider"] = mp
        del cfg["model_provider"]

    return cfg


def load_config(config_path: str):
    """Load and validate configuration from JSON5 file with environment
    variable substitution.

    Args:
        config_path: Path to the JSON5 configuration file

    Returns:
        dict: Parsed configuration with environment variables substituted

    Raises:
        ConfigFileNotFoundError: If the config file doesn't exist
        ConfigValidationError: If environment variables are missing or parsing fails
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise ConfigFileNotFoundError(f"Config file {config_path} not found")

    with open(config_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace ${VAR_NAME} with environment variable values w/o checking
    # for key, value in os.environ.items():
    #     content = content.replace(f"${{{key}}}", value or '')

    # Replace ${VAR_NAME} with environment variable values, but skip comments
    # to avoid raising ConfigValidationError for undefined variables in comments
    # (e.g., "// ${THIS_ENV_VAR_NOT_DEFINED_SO_COMMENTED_OUT_TO_AVOID_RAISING_EXCEPTION}")
    def replace_env_var(match):
        """Replace environment variable placeholder with actual value.

        Args:
            match: Regex match object containing variable name

        Returns:
            str: Environment variable value

        Raises:
            ConfigValidationError: If environment variable is not found
        """
        var_name = match.group(1)
        env_value = os.getenv(var_name)
        if env_value is None:
            raise ConfigValidationError(
                f'Environment variable "{var_name}" used '
                f'in "{config_file}" not found'
            )
        return env_value

    # Process line by line to skip comments
    lines = content.split("\n")
    processed_lines = []

    for line in lines:
        # Split line at first occurrence of "//" to separate code from comments
        if "//" in line:
            code_part, comment_part = line.split("//", 1)
            # Apply environment variable substitution only to the code part
            processed_code = re.sub(r"\$\{([^}]+)\}", replace_env_var,
                                    code_part)
            # Reconstruct line with original comment
            processed_line = processed_code + "//" + comment_part
        else:
            # No comment in line, apply substitution to entire line
            processed_line = re.sub(r"\$\{([^}]+)\}", replace_env_var, line)

        processed_lines.append(processed_line)

    content = "\n".join(processed_lines)

    # Parse the processed content as JSON5
    config: dict[str, Any] = json5.loads(content)

    config["llm"] = normalize_config(config["llm"])

    return config
