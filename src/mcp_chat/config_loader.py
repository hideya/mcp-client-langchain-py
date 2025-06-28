import os
import re
from pathlib import Path
from typing import TypedDict, Any
import pyjson5 as json5


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
    """Load and validate configuration from JSON5 file with environment
    variable substitution.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise ConfigFileNotFoundError(f"Config file {config_path} not found")

    with open(config_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace ${VAR_NAME} with environment variable values, but skip comments
    def replace_env_var(match):
        var_name = match.group(1)
        env_value = os.getenv(var_name)
        if env_value is None:
            raise ConfigValidationError(
                f'Environment variable "{var_name}" not found '
                f'in "{config_file}"'
            )
        return env_value
    
    # Process line by line to skip comments
    lines = content.split("\n")
    processed_lines = []
    
    for line in lines:
        # Split line at first occurrence of "//"
        if "//" in line:
            code_part, comment_part = line.split("//", 1)
            # Apply substitution only to the code part
            processed_code = re.sub(r"\$\{([^}]+)\}", replace_env_var,
                                    code_part)
            # Reconstruct line with original comment
            processed_line = processed_code + "//" + comment_part
        else:
            # No comment in line, apply substitution to entire line
            processed_line = re.sub(r"\$\{([^}]+)\}", replace_env_var, line)
        
        processed_lines.append(processed_line)
    
    content = "\n".join(processed_lines)
    
    # Parse the substituted content
    config: dict[str, Any] = json5.loads(content)
    
    return config
