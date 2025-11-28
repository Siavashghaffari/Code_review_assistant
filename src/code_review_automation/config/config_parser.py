"""
Configuration Parser

Handles parsing of YAML and JSON configuration files with validation and merging.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import asdict, fields
import os

from .schema import (
    ConfigSchema, RuleConfig, CheckerConfig, IgnorePattern,
    FileTypeSpecificConfig, SeverityLevel, FileTypeConfig,
    ConfigValidator, create_default_config
)
from ..utils.logger import get_logger


class ConfigParser:
    """Parses and validates configuration files."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.validator = ConfigValidator()

    def load_config(self, config_path: Optional[Union[str, Path]] = None) -> ConfigSchema:
        """
        Load configuration from file or use defaults.

        Args:
            config_path: Path to configuration file

        Returns:
            Parsed and validated configuration
        """
        if config_path is None:
            # Look for default config files
            config_path = self._find_default_config()

        if config_path is None:
            self.logger.info("No configuration file found, using defaults")
            return create_default_config()

        config_path = Path(config_path)

        if not config_path.exists():
            self.logger.warning(f"Configuration file not found: {config_path}")
            return create_default_config()

        try:
            raw_config = self._parse_file(config_path)
            config = self._convert_to_schema(raw_config)

            # Handle extends directive
            if config.extends:
                config = self._merge_extended_configs(config, config_path.parent)

            # Validate configuration
            errors = self.validator.validate_config(config)
            if errors:
                self.logger.warning(f"Configuration validation errors: {errors}")
                # Continue with potentially invalid config for now

            self.logger.info(f"Configuration loaded from {config_path}")
            return config

        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            self.logger.info("Falling back to default configuration")
            return create_default_config()

    def save_config(self, config: ConfigSchema, output_path: Union[str, Path], format: str = "yaml") -> bool:
        """
        Save configuration to file.

        Args:
            config: Configuration to save
            output_path: Output file path
            format: Output format ('yaml' or 'json')

        Returns:
            True if successful
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            config_dict = self._schema_to_dict(config)

            if format.lower() == "json":
                with open(output_path, 'w') as f:
                    json.dump(config_dict, f, indent=2, default=str)
            else:  # yaml
                with open(output_path, 'w') as f:
                    yaml.safe_dump(config_dict, f, default_flow_style=False, indent=2)

            self.logger.info(f"Configuration saved to {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False

    def merge_configs(self, base_config: ConfigSchema, override_config: Dict[str, Any]) -> ConfigSchema:
        """
        Merge override configuration into base configuration.

        Args:
            base_config: Base configuration
            override_config: Override values

        Returns:
            Merged configuration
        """
        base_dict = self._schema_to_dict(base_config)
        merged_dict = self._deep_merge(base_dict, override_config)
        return self._convert_to_schema(merged_dict)

    def _find_default_config(self) -> Optional[Path]:
        """Find default configuration file in current directory."""
        possible_names = [
            ".codereview.yaml",
            ".codereview.yml",
            ".codereview.json",
            "codereview.yaml",
            "codereview.yml",
            "codereview.json"
        ]

        for name in possible_names:
            config_path = Path(name)
            if config_path.exists():
                return config_path

        return None

    def _parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse configuration file based on extension."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if file_path.suffix.lower() in ['.yaml', '.yml']:
            return yaml.safe_load(content) or {}
        elif file_path.suffix.lower() == '.json':
            return json.loads(content)
        else:
            # Try to detect format from content
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return yaml.safe_load(content) or {}

    def _convert_to_schema(self, raw_config: Dict[str, Any]) -> ConfigSchema:
        """Convert raw dictionary to ConfigSchema."""
        config = ConfigSchema()

        # Basic fields
        if 'version' in raw_config:
            config.version = raw_config['version']
        if 'extends' in raw_config:
            config.extends = raw_config['extends']

        # Severity settings
        if 'severity_threshold' in raw_config:
            config.severity_threshold = self._parse_severity(raw_config['severity_threshold'])
        if 'fail_on_severity' in raw_config:
            config.fail_on_severity = self._parse_severity(raw_config['fail_on_severity'])

        # Limits
        if 'max_issues_per_run' in raw_config:
            config.max_issues_per_run = raw_config['max_issues_per_run']

        # Checkers
        if 'checkers' in raw_config:
            config.checkers = self._parse_checkers(raw_config['checkers'])

        # Ignore patterns
        if 'ignore_patterns' in raw_config:
            config.ignore_patterns = self._parse_ignore_patterns(raw_config['ignore_patterns'])

        # Include patterns
        if 'include_patterns' in raw_config:
            config.include_patterns = raw_config['include_patterns']

        # File types
        if 'file_types' in raw_config:
            config.file_types = self._parse_file_types(raw_config['file_types'])

        # Output configuration
        if 'output' in raw_config:
            config.output = self._parse_output_config(raw_config['output'])

        # Git integration
        if 'git' in raw_config:
            config.git = self._parse_git_config(raw_config['git'])

        # Custom rules
        if 'custom_rules' in raw_config:
            config.custom_rules = raw_config['custom_rules']

        return config

    def _parse_severity(self, value: Union[str, SeverityLevel]) -> SeverityLevel:
        """Parse severity level from string or enum."""
        if isinstance(value, SeverityLevel):
            return value
        if isinstance(value, str):
            try:
                return SeverityLevel(value.lower())
            except ValueError:
                self.logger.warning(f"Invalid severity level: {value}")
                return SeverityLevel.WARNING
        return SeverityLevel.WARNING

    def _parse_checkers(self, checkers_config: Dict[str, Any]) -> Dict[str, CheckerConfig]:
        """Parse checker configurations."""
        checkers = {}

        for checker_name, checker_data in checkers_config.items():
            checker_config = CheckerConfig()

            if 'enabled' in checker_data:
                checker_config.enabled = bool(checker_data['enabled'])

            if 'severity_override' in checker_data:
                checker_config.severity_override = self._parse_severity(checker_data['severity_override'])

            if 'rules' in checker_data:
                checker_config.rules = self._parse_rules(checker_data['rules'])

            checkers[checker_name] = checker_config

        return checkers

    def _parse_rules(self, rules_config: Dict[str, Any]) -> Dict[str, RuleConfig]:
        """Parse rule configurations."""
        rules = {}

        for rule_name, rule_data in rules_config.items():
            rule_config = RuleConfig()

            if isinstance(rule_data, bool):
                # Simple boolean enable/disable
                rule_config.enabled = rule_data
            elif isinstance(rule_data, dict):
                if 'enabled' in rule_data:
                    rule_config.enabled = bool(rule_data['enabled'])
                if 'severity' in rule_data:
                    rule_config.severity = self._parse_severity(rule_data['severity'])
                if 'options' in rule_data:
                    rule_config.options = rule_data['options']
                if 'file_types' in rule_data:
                    rule_config.file_types = [
                        FileTypeConfig(ft) if isinstance(ft, str) else ft
                        for ft in rule_data['file_types']
                    ]
                if 'ignore_patterns' in rule_data:
                    rule_config.ignore_patterns = rule_data['ignore_patterns']

            rules[rule_name] = rule_config

        return rules

    def _parse_ignore_patterns(self, patterns_config: List[Any]) -> List[IgnorePattern]:
        """Parse ignore patterns configuration."""
        patterns = []

        for pattern_data in patterns_config:
            if isinstance(pattern_data, str):
                patterns.append(IgnorePattern(pattern=pattern_data))
            elif isinstance(pattern_data, dict):
                patterns.append(IgnorePattern(
                    pattern=pattern_data['pattern'],
                    type=pattern_data.get('type', 'glob'),
                    description=pattern_data.get('description')
                ))

        return patterns

    def _parse_file_types(self, file_types_config: Dict[str, Any]) -> Dict[FileTypeConfig, FileTypeSpecificConfig]:
        """Parse file type specific configurations."""
        file_types = {}

        for ft_name, ft_config in file_types_config.items():
            try:
                file_type_enum = FileTypeConfig(ft_name)
                config = FileTypeSpecificConfig(file_type=file_type_enum)

                if 'max_line_length' in ft_config:
                    config.max_line_length = ft_config['max_line_length']
                if 'max_function_length' in ft_config:
                    config.max_function_length = ft_config['max_function_length']
                if 'max_complexity' in ft_config:
                    config.max_complexity = ft_config['max_complexity']
                if 'naming_conventions' in ft_config:
                    config.naming_conventions = ft_config['naming_conventions']
                if 'custom_rules' in ft_config:
                    config.custom_rules = self._parse_rules(ft_config['custom_rules'])

                file_types[file_type_enum] = config

            except ValueError:
                self.logger.warning(f"Unknown file type: {ft_name}")

        return file_types

    def _parse_output_config(self, output_config: Dict[str, Any]) -> Any:
        """Parse output configuration - simplified for now."""
        # Return the dict as-is for now, could be expanded to use proper dataclass
        return output_config

    def _parse_git_config(self, git_config: Dict[str, Any]) -> Any:
        """Parse git configuration - simplified for now."""
        # Return the dict as-is for now, could be expanded to use proper dataclass
        return git_config

    def _merge_extended_configs(self, config: ConfigSchema, base_dir: Path) -> ConfigSchema:
        """Merge configurations from extends directive."""
        if not config.extends:
            return config

        merged_config = config

        for extend_path in config.extends:
            extend_file = base_dir / extend_path
            if extend_file.exists():
                try:
                    extended_raw = self._parse_file(extend_file)
                    extended_config = self._convert_to_schema(extended_raw)

                    # Merge extended config as base, current config as override
                    base_dict = self._schema_to_dict(extended_config)
                    override_dict = self._schema_to_dict(merged_config)
                    merged_dict = self._deep_merge(base_dict, override_dict)
                    merged_config = self._convert_to_schema(merged_dict)

                except Exception as e:
                    self.logger.error(f"Error extending config from {extend_file}: {e}")

        return merged_config

    def _schema_to_dict(self, config: ConfigSchema) -> Dict[str, Any]:
        """Convert ConfigSchema to dictionary."""
        result = {}

        # Convert dataclass fields to dict
        for field in fields(config):
            value = getattr(config, field.name)
            if value is not None:
                result[field.name] = self._convert_value_to_dict(value)

        return result

    def _convert_value_to_dict(self, value: Any) -> Any:
        """Convert complex values to dictionary representation."""
        if hasattr(value, '__dict__') and hasattr(value, '__annotations__'):
            # Dataclass
            return {k: self._convert_value_to_dict(v) for k, v in asdict(value).items()}
        elif isinstance(value, dict):
            return {k: self._convert_value_to_dict(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._convert_value_to_dict(item) for item in value]
        elif hasattr(value, 'value'):
            # Enum
            return value.value
        else:
            return value

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result


class EnvironmentConfigProvider:
    """Provides configuration overrides from environment variables."""

    @staticmethod
    def get_environment_overrides() -> Dict[str, Any]:
        """Get configuration overrides from environment variables."""
        overrides = {}

        # Severity threshold
        if os.getenv('CODEREVIEW_SEVERITY_THRESHOLD'):
            overrides['severity_threshold'] = os.getenv('CODEREVIEW_SEVERITY_THRESHOLD')

        # Fail on severity
        if os.getenv('CODEREVIEW_FAIL_ON_SEVERITY'):
            overrides['fail_on_severity'] = os.getenv('CODEREVIEW_FAIL_ON_SEVERITY')

        # Max issues
        if os.getenv('CODEREVIEW_MAX_ISSUES'):
            try:
                overrides['max_issues_per_run'] = int(os.getenv('CODEREVIEW_MAX_ISSUES'))
            except ValueError:
                pass

        # Output format
        if os.getenv('CODEREVIEW_OUTPUT_FORMAT'):
            overrides['output'] = {'format': os.getenv('CODEREVIEW_OUTPUT_FORMAT')}

        return overrides