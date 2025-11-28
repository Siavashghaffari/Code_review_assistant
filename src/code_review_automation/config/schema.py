"""
Configuration Schema Definitions

Defines the structure and validation schema for configuration files.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Union
import re


class SeverityLevel(Enum):
    """Issue severity levels."""
    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"
    INFO = "info"


class FileTypeConfig(Enum):
    """Supported file types."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"


@dataclass
class IgnorePattern:
    """Configuration for ignore patterns."""
    pattern: str
    type: str = "glob"  # glob, regex, path
    description: Optional[str] = None


@dataclass
class RuleConfig:
    """Configuration for a specific rule."""
    enabled: bool = True
    severity: SeverityLevel = SeverityLevel.WARNING
    options: Dict[str, Any] = field(default_factory=dict)
    file_types: Optional[List[FileTypeConfig]] = None
    ignore_patterns: List[str] = field(default_factory=list)


@dataclass
class CheckerConfig:
    """Configuration for a specific checker category."""
    enabled: bool = True
    rules: Dict[str, RuleConfig] = field(default_factory=dict)
    severity_override: Optional[SeverityLevel] = None


@dataclass
class FileTypeSpecificConfig:
    """File type specific configuration."""
    file_type: FileTypeConfig
    max_line_length: int = 100
    max_function_length: int = 50
    max_complexity: int = 10
    naming_conventions: Dict[str, str] = field(default_factory=dict)
    custom_rules: Dict[str, RuleConfig] = field(default_factory=dict)


@dataclass
class OutputConfig:
    """Output formatting configuration."""
    format: str = "terminal"  # terminal, json, markdown
    show_suggestions: bool = True
    show_line_numbers: bool = True
    show_severity_colors: bool = True
    max_issues_per_file: int = 20
    group_by_severity: bool = False


@dataclass
class GitIntegrationConfig:
    """Git integration configuration."""
    enabled: bool = False
    focus_on_changes_only: bool = True
    context_lines: int = 3
    post_comments: bool = False
    comment_template: Optional[str] = None
    platforms: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ConfigSchema:
    """Main configuration schema."""
    # Core settings
    version: str = "1.0"
    extends: Optional[List[str]] = None

    # Rule configuration
    checkers: Dict[str, CheckerConfig] = field(default_factory=lambda: {
        "complexity": CheckerConfig(),
        "security": CheckerConfig(),
        "style": CheckerConfig(),
        "naming": CheckerConfig(),
        "variables": CheckerConfig(),
        "error_handling": CheckerConfig()
    })

    # Global settings
    severity_threshold: SeverityLevel = SeverityLevel.INFO
    fail_on_severity: SeverityLevel = SeverityLevel.ERROR
    max_issues_per_run: int = 100

    # File handling
    ignore_patterns: List[IgnorePattern] = field(default_factory=lambda: [
        IgnorePattern(pattern="*.pyc", type="glob", description="Python compiled files"),
        IgnorePattern(pattern="node_modules/**", type="glob", description="Node.js dependencies"),
        IgnorePattern(pattern=".git/**", type="glob", description="Git directory"),
        IgnorePattern(pattern="__pycache__/**", type="glob", description="Python cache"),
    ])

    include_patterns: List[str] = field(default_factory=lambda: [
        "**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"
    ])

    # File type specific configurations
    file_types: Dict[FileTypeConfig, FileTypeSpecificConfig] = field(default_factory=dict)

    # Output configuration
    output: OutputConfig = field(default_factory=OutputConfig)

    # Git integration
    git: GitIntegrationConfig = field(default_factory=GitIntegrationConfig)

    # Custom rules
    custom_rules: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class TeamConfig:
    """Team-specific configuration extensions."""
    team_name: str
    coding_standards: Dict[str, Any] = field(default_factory=dict)
    required_checks: List[str] = field(default_factory=list)
    custom_severity_mappings: Dict[str, SeverityLevel] = field(default_factory=dict)
    approval_rules: Dict[str, Any] = field(default_factory=dict)


class ConfigValidator:
    """Validates configuration schemas."""

    @staticmethod
    def validate_severity_level(value: Any) -> bool:
        """Validate severity level value."""
        if isinstance(value, SeverityLevel):
            return True
        if isinstance(value, str):
            return value in [s.value for s in SeverityLevel]
        return False

    @staticmethod
    def validate_pattern(pattern: str, pattern_type: str = "glob") -> bool:
        """Validate ignore/include patterns."""
        try:
            if pattern_type == "regex":
                re.compile(pattern)
            elif pattern_type == "glob":
                # Basic glob validation
                return "*" in pattern or "?" in pattern or pattern.endswith("/")
            return True
        except re.error:
            return False

    @staticmethod
    def validate_file_type(file_type: Any) -> bool:
        """Validate file type configuration."""
        if isinstance(file_type, FileTypeConfig):
            return True
        if isinstance(file_type, str):
            return file_type in [ft.value for ft in FileTypeConfig]
        return False

    @classmethod
    def validate_config(cls, config: ConfigSchema) -> List[str]:
        """Validate entire configuration schema."""
        errors = []

        # Validate version
        if not isinstance(config.version, str):
            errors.append("Version must be a string")

        # Validate severity levels
        if not cls.validate_severity_level(config.severity_threshold):
            errors.append("Invalid severity_threshold")

        if not cls.validate_severity_level(config.fail_on_severity):
            errors.append("Invalid fail_on_severity")

        # Validate patterns
        for pattern in config.ignore_patterns:
            if not cls.validate_pattern(pattern.pattern, pattern.type):
                errors.append(f"Invalid ignore pattern: {pattern.pattern}")

        for pattern in config.include_patterns:
            if not cls.validate_pattern(pattern, "glob"):
                errors.append(f"Invalid include pattern: {pattern}")

        # Validate checker configurations
        for checker_name, checker_config in config.checkers.items():
            if checker_config.severity_override:
                if not cls.validate_severity_level(checker_config.severity_override):
                    errors.append(f"Invalid severity override for checker {checker_name}")

            for rule_name, rule_config in checker_config.rules.items():
                if not cls.validate_severity_level(rule_config.severity):
                    errors.append(f"Invalid severity for rule {checker_name}.{rule_name}")

        return errors


def create_default_config() -> ConfigSchema:
    """Create a default configuration with sensible defaults."""
    config = ConfigSchema()

    # Setup default file type configurations
    config.file_types = {
        FileTypeConfig.PYTHON: FileTypeSpecificConfig(
            file_type=FileTypeConfig.PYTHON,
            max_line_length=88,  # Black default
            max_function_length=50,
            max_complexity=10,
            naming_conventions={
                "function": "snake_case",
                "variable": "snake_case",
                "class": "PascalCase",
                "constant": "UPPER_CASE"
            }
        ),
        FileTypeConfig.JAVASCRIPT: FileTypeSpecificConfig(
            file_type=FileTypeConfig.JAVASCRIPT,
            max_line_length=100,
            max_function_length=40,
            max_complexity=8,
            naming_conventions={
                "function": "camelCase",
                "variable": "camelCase",
                "class": "PascalCase",
                "constant": "UPPER_CASE"
            }
        ),
        FileTypeConfig.TYPESCRIPT: FileTypeSpecificConfig(
            file_type=FileTypeConfig.TYPESCRIPT,
            max_line_length=100,
            max_function_length=40,
            max_complexity=8,
            naming_conventions={
                "function": "camelCase",
                "variable": "camelCase",
                "class": "PascalCase",
                "interface": "PascalCase",
                "type": "PascalCase"
            }
        )
    }

    # Setup default checker rules
    config.checkers["complexity"].rules = {
        "max_cyclomatic_complexity": RuleConfig(
            enabled=True,
            severity=SeverityLevel.WARNING,
            options={"threshold": 10}
        ),
        "max_cognitive_complexity": RuleConfig(
            enabled=True,
            severity=SeverityLevel.WARNING,
            options={"threshold": 15}
        ),
        "max_function_length": RuleConfig(
            enabled=True,
            severity=SeverityLevel.SUGGESTION,
            options={"threshold": 50}
        )
    }

    config.checkers["security"].rules = {
        "hardcoded_secrets": RuleConfig(
            enabled=True,
            severity=SeverityLevel.ERROR
        ),
        "sql_injection_risk": RuleConfig(
            enabled=True,
            severity=SeverityLevel.ERROR
        ),
        "xss_risk": RuleConfig(
            enabled=True,
            severity=SeverityLevel.ERROR
        ),
        "unsafe_eval": RuleConfig(
            enabled=True,
            severity=SeverityLevel.WARNING
        )
    }

    config.checkers["style"].rules = {
        "line_too_long": RuleConfig(
            enabled=True,
            severity=SeverityLevel.SUGGESTION
        ),
        "trailing_whitespace": RuleConfig(
            enabled=True,
            severity=SeverityLevel.SUGGESTION
        ),
        "inconsistent_indentation": RuleConfig(
            enabled=True,
            severity=SeverityLevel.WARNING
        )
    }

    return config