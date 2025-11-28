"""
Configuration Loader

Loads and validates configuration files for the code review tool.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List

from .logger import get_logger
from .exceptions import ConfigurationError


class ConfigLoader:
    """Loads and manages configuration for the code review tool."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.default_config_path = Path(__file__).parent.parent.parent / "config" / "default_rules.yaml"

    def load(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from file.

        Args:
            config_path: Path to custom config file (optional)

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            if config_path:
                # Load custom configuration
                custom_config = self._load_config_file(Path(config_path))

                # Merge with default configuration
                default_config = self._load_default_config()
                config = self._merge_configs(default_config, custom_config)

                self.logger.info(f"Loaded custom configuration from {config_path}")
            else:
                # Load default configuration
                config = self._load_default_config()
                self.logger.info("Using default configuration")

            # Validate configuration
            self._validate_config(config)

            return config

        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def _load_default_config(self) -> Dict[str, Any]:
        """Load the default configuration file."""
        if not self.default_config_path.exists():
            raise ConfigurationError(f"Default configuration file not found: {self.default_config_path}")

        return self._load_config_file(self.default_config_path)

    def _load_config_file(self, config_path: Path) -> Dict[str, Any]:
        """
        Load a YAML configuration file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary
        """
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if not isinstance(config, dict):
                raise ConfigurationError("Configuration file must contain a YAML dictionary")

            return config

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error reading configuration file: {e}")

    def _merge_configs(self, default: Dict[str, Any], custom: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge custom configuration with default configuration.

        Args:
            default: Default configuration
            custom: Custom configuration

        Returns:
            Merged configuration
        """
        merged = dict(default)

        for key, value in custom.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                merged[key] = self._merge_configs(merged[key], value)
            else:
                # Override or add new key
                merged[key] = value

        return merged

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate configuration structure and values.

        Args:
            config: Configuration to validate

        Raises:
            ConfigurationError: If configuration is invalid
        """
        required_sections = ["file_types", "languages", "severity"]

        # Check required sections
        for section in required_sections:
            if section not in config:
                raise ConfigurationError(f"Missing required configuration section: {section}")

        # Validate file_types section
        file_types = config.get("file_types", {})
        if not isinstance(file_types, dict):
            raise ConfigurationError("file_types must be a dictionary")

        # Validate languages section
        languages = config.get("languages", {})
        if not isinstance(languages, dict):
            raise ConfigurationError("languages must be a dictionary")

        # Validate each language configuration
        for ext, lang_config in languages.items():
            if not isinstance(lang_config, dict):
                raise ConfigurationError(f"Language configuration for {ext} must be a dictionary")

            # Check for required language fields
            if "language" not in lang_config:
                self.logger.warning(f"Language not specified for extension {ext}")

        # Validate severity section
        severity = config.get("severity", {})
        if not isinstance(severity, dict):
            raise ConfigurationError("severity must be a dictionary")

        valid_severities = ["error", "warning", "info"]
        for severity_level in severity.keys():
            if severity_level not in valid_severities:
                raise ConfigurationError(f"Invalid severity level: {severity_level}")

        # Validate limits section if present
        limits = config.get("limits", {})
        if limits and not isinstance(limits, dict):
            raise ConfigurationError("limits must be a dictionary")

        if limits:
            max_file_size = limits.get("max_file_size")
            if max_file_size is not None and (not isinstance(max_file_size, int) or max_file_size <= 0):
                raise ConfigurationError("max_file_size must be a positive integer")

            max_files = limits.get("max_files")
            if max_files is not None and (not isinstance(max_files, int) or max_files <= 0):
                raise ConfigurationError("max_files must be a positive integer")

        self.logger.debug("Configuration validation successful")

    def get_language_config(self, config: Dict[str, Any], file_extension: str) -> Dict[str, Any]:
        """
        Get language-specific configuration for a file extension.

        Args:
            config: Main configuration
            file_extension: File extension (e.g., '.py')

        Returns:
            Language configuration dictionary
        """
        languages = config.get("languages", {})
        return languages.get(file_extension, {})

    def get_severity_rules(self, config: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Get severity rules from configuration.

        Args:
            config: Main configuration

        Returns:
            Dictionary mapping severity levels to rule types
        """
        return config.get("severity", {})