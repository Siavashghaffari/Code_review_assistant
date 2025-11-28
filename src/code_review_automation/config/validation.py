"""
Configuration Validation and Merging

Advanced validation, merging, and inheritance capabilities for configurations.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Set
from dataclasses import fields, is_dataclass
import copy

from .schema import (
    ConfigSchema, SeverityLevel, FileTypeConfig, IgnorePattern,
    RuleConfig, CheckerConfig, ConfigValidator
)
from ..utils.logger import get_logger


class ConfigValidationError(Exception):
    """Configuration validation error."""
    pass


class ConfigMerger:
    """Handles merging of configurations with inheritance."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def merge_configs(self, base: ConfigSchema, override: ConfigSchema) -> ConfigSchema:
        """
        Merge two configurations with override taking precedence.

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            Merged configuration
        """
        # Create a deep copy of base to avoid modifying original
        merged = copy.deepcopy(base)

        # Merge each field
        for field in fields(override):
            field_name = field.name
            override_value = getattr(override, field_name)
            base_value = getattr(merged, field_name)

            # Skip None values in override
            if override_value is None:
                continue

            # Handle different types of merging
            if field_name == "checkers":
                merged.checkers = self._merge_checkers(base_value, override_value)
            elif field_name == "ignore_patterns":
                merged.ignore_patterns = self._merge_ignore_patterns(base_value, override_value)
            elif field_name == "include_patterns":
                merged.include_patterns = self._merge_lists(base_value, override_value)
            elif field_name == "file_types":
                merged.file_types = self._merge_file_types(base_value, override_value)
            elif field_name == "custom_rules":
                merged.custom_rules = self._merge_dicts(base_value, override_value)
            elif isinstance(override_value, dict):
                setattr(merged, field_name, self._merge_dicts(base_value, override_value))
            else:
                # Simple override
                setattr(merged, field_name, override_value)

        return merged

    def _merge_checkers(self, base: Dict[str, CheckerConfig], override: Dict[str, CheckerConfig]) -> Dict[str, CheckerConfig]:
        """Merge checker configurations."""
        merged = copy.deepcopy(base)

        for checker_name, override_checker in override.items():
            if checker_name in merged:
                base_checker = merged[checker_name]
                merged_checker = CheckerConfig()

                # Merge enabled status
                merged_checker.enabled = override_checker.enabled if override_checker.enabled is not None else base_checker.enabled

                # Merge severity override
                merged_checker.severity_override = override_checker.severity_override or base_checker.severity_override

                # Merge rules
                merged_checker.rules = self._merge_rules(base_checker.rules, override_checker.rules)

                merged[checker_name] = merged_checker
            else:
                merged[checker_name] = copy.deepcopy(override_checker)

        return merged

    def _merge_rules(self, base: Dict[str, RuleConfig], override: Dict[str, RuleConfig]) -> Dict[str, RuleConfig]:
        """Merge rule configurations."""
        merged = copy.deepcopy(base)

        for rule_name, override_rule in override.items():
            if rule_name in merged:
                base_rule = merged[rule_name]
                merged_rule = RuleConfig()

                # Merge fields with override precedence
                merged_rule.enabled = override_rule.enabled if override_rule.enabled is not None else base_rule.enabled
                merged_rule.severity = override_rule.severity or base_rule.severity
                merged_rule.options = self._merge_dicts(base_rule.options, override_rule.options)
                merged_rule.file_types = override_rule.file_types or base_rule.file_types
                merged_rule.ignore_patterns = self._merge_lists(base_rule.ignore_patterns, override_rule.ignore_patterns)

                merged[rule_name] = merged_rule
            else:
                merged[rule_name] = copy.deepcopy(override_rule)

        return merged

    def _merge_ignore_patterns(self, base: List[IgnorePattern], override: List[IgnorePattern]) -> List[IgnorePattern]:
        """Merge ignore patterns, avoiding duplicates."""
        merged = copy.deepcopy(base)
        existing_patterns = {(p.pattern, p.type) for p in merged}

        for pattern in override:
            if (pattern.pattern, pattern.type) not in existing_patterns:
                merged.append(copy.deepcopy(pattern))
                existing_patterns.add((pattern.pattern, pattern.type))

        return merged

    def _merge_file_types(self, base: Dict[FileTypeConfig, Any], override: Dict[FileTypeConfig, Any]) -> Dict[FileTypeConfig, Any]:
        """Merge file type configurations."""
        merged = copy.deepcopy(base)

        for file_type, override_config in override.items():
            if file_type in merged:
                base_config = merged[file_type]
                # Merge the file type config objects
                if hasattr(base_config, '__dict__'):
                    merged_config = copy.deepcopy(base_config)
                    for key, value in override_config.__dict__.items():
                        if value is not None:
                            setattr(merged_config, key, value)
                    merged[file_type] = merged_config
                else:
                    merged[file_type] = copy.deepcopy(override_config)
            else:
                merged[file_type] = copy.deepcopy(override_config)

        return merged

    def _merge_lists(self, base: List[Any], override: List[Any]) -> List[Any]:
        """Merge two lists, avoiding duplicates."""
        if not base:
            return copy.deepcopy(override)
        if not override:
            return copy.deepcopy(base)

        merged = copy.deepcopy(base)
        existing = set(base) if all(isinstance(x, (str, int, float, bool)) for x in base) else None

        for item in override:
            if existing is None or item not in existing:
                merged.append(copy.deepcopy(item))
                if existing is not None:
                    existing.add(item)

        return merged

    def _merge_dicts(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        if not base:
            return copy.deepcopy(override)
        if not override:
            return copy.deepcopy(base)

        merged = copy.deepcopy(base)

        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_dicts(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)

        return merged


class AdvancedConfigValidator:
    """Advanced configuration validation with detailed error reporting."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.base_validator = ConfigValidator()

    def validate_config(self, config: ConfigSchema) -> Dict[str, List[str]]:
        """
        Comprehensive configuration validation.

        Returns:
            Dict with error categories and their errors
        """
        validation_results = {
            'schema_errors': [],
            'logical_errors': [],
            'compatibility_errors': [],
            'performance_warnings': [],
            'security_warnings': []
        }

        # Basic schema validation
        schema_errors = self.base_validator.validate_config(config)
        validation_results['schema_errors'] = schema_errors

        # Logical validation
        validation_results['logical_errors'] = self._validate_logical_consistency(config)

        # Compatibility validation
        validation_results['compatibility_errors'] = self._validate_compatibility(config)

        # Performance warnings
        validation_results['performance_warnings'] = self._check_performance_implications(config)

        # Security warnings
        validation_results['security_warnings'] = self._check_security_implications(config)

        return validation_results

    def _validate_logical_consistency(self, config: ConfigSchema) -> List[str]:
        """Validate logical consistency of configuration."""
        errors = []

        # Check severity threshold vs fail_on_severity
        severity_order = {
            SeverityLevel.INFO: 0,
            SeverityLevel.SUGGESTION: 1,
            SeverityLevel.WARNING: 2,
            SeverityLevel.ERROR: 3
        }

        if severity_order[config.fail_on_severity] < severity_order[config.severity_threshold]:
            errors.append(
                f"fail_on_severity ({config.fail_on_severity.value}) should be >= "
                f"severity_threshold ({config.severity_threshold.value})"
            )

        # Check for conflicting ignore/include patterns
        conflicts = self._find_pattern_conflicts(config.ignore_patterns, config.include_patterns)
        errors.extend(conflicts)

        # Check for disabled checkers with enabled rules
        for checker_name, checker_config in config.checkers.items():
            if not checker_config.enabled:
                enabled_rules = [
                    rule_name for rule_name, rule_config in checker_config.rules.items()
                    if rule_config.enabled
                ]
                if enabled_rules:
                    errors.append(
                        f"Checker '{checker_name}' is disabled but has enabled rules: {enabled_rules}"
                    )

        return errors

    def _validate_compatibility(self, config: ConfigSchema) -> List[str]:
        """Validate compatibility between different configuration sections."""
        errors = []

        # Check file type compatibility
        for file_type, file_config in config.file_types.items():
            # Validate naming conventions
            if hasattr(file_config, 'naming_conventions'):
                valid_conventions = self._get_valid_conventions_for_file_type(file_type)
                for convention_type, pattern in file_config.naming_conventions.items():
                    if convention_type not in valid_conventions:
                        errors.append(
                            f"Invalid naming convention '{convention_type}' for file type {file_type.value}"
                        )

        # Check git integration compatibility
        if hasattr(config, 'git') and config.git and getattr(config.git, 'enabled', False):
            if not getattr(config.git, 'focus_on_changes_only', True) and config.max_issues_per_run < 1000:
                errors.append(
                    "When git.focus_on_changes_only is false, consider increasing max_issues_per_run"
                )

        return errors

    def _check_performance_implications(self, config: ConfigSchema) -> List[str]:
        """Check for performance implications."""
        warnings = []

        # Check for expensive operations
        if config.max_issues_per_run > 1000:
            warnings.append("High max_issues_per_run may impact performance")

        # Check ignore patterns efficiency
        regex_patterns = [
            p for p in config.ignore_patterns
            if p.type == "regex"
        ]
        if len(regex_patterns) > 20:
            warnings.append("Many regex ignore patterns may impact performance")

        # Check for overly broad include patterns
        broad_patterns = [
            p for p in config.include_patterns
            if p.count('*') > 3
        ]
        if broad_patterns:
            warnings.append(f"Very broad include patterns may impact performance: {broad_patterns}")

        return warnings

    def _check_security_implications(self, config: ConfigSchema) -> List[str]:
        """Check for security implications."""
        warnings = []

        # Check if security checker is disabled
        security_checker = config.checkers.get('security')
        if security_checker and not security_checker.enabled:
            warnings.append("Security checker is disabled - consider enabling for security analysis")

        # Check severity levels for security rules
        if security_checker:
            for rule_name, rule_config in security_checker.rules.items():
                if 'secret' in rule_name or 'password' in rule_name or 'token' in rule_name:
                    if rule_config.severity != SeverityLevel.ERROR:
                        warnings.append(
                            f"Security rule '{rule_name}' should probably be set to 'error' severity"
                        )

        return warnings

    def _find_pattern_conflicts(self, ignore_patterns: List[IgnorePattern], include_patterns: List[str]) -> List[str]:
        """Find conflicts between ignore and include patterns."""
        conflicts = []

        for ignore_pattern in ignore_patterns:
            for include_pattern in include_patterns:
                if self._patterns_conflict(ignore_pattern.pattern, include_pattern):
                    conflicts.append(
                        f"Ignore pattern '{ignore_pattern.pattern}' conflicts with include pattern '{include_pattern}'"
                    )

        return conflicts

    def _patterns_conflict(self, ignore_pattern: str, include_pattern: str) -> bool:
        """Check if two patterns conflict with each other."""
        # Simple heuristic - if patterns are very similar, they might conflict
        # This could be made more sophisticated
        return ignore_pattern == include_pattern or (
            ignore_pattern.replace('*', '') in include_pattern and
            include_pattern.replace('*', '') in ignore_pattern
        )

    def _get_valid_conventions_for_file_type(self, file_type: FileTypeConfig) -> Set[str]:
        """Get valid naming conventions for a file type."""
        common_conventions = {"function", "variable", "class", "constant"}

        type_specific = {
            FileTypeConfig.PYTHON: {"module", "private", "protected"},
            FileTypeConfig.JAVASCRIPT: {"property", "method"},
            FileTypeConfig.TYPESCRIPT: {"interface", "type", "enum", "generic"},
            FileTypeConfig.JAVA: {"package", "annotation", "enum"},
        }

        return common_conventions | type_specific.get(file_type, set())


class ConfigInheritance:
    """Handles configuration inheritance and extends functionality."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.merger = ConfigMerger()

    def resolve_extends(self, config: ConfigSchema, config_dir: Path) -> ConfigSchema:
        """
        Resolve extends directives in configuration.

        Args:
            config: Configuration with potential extends
            config_dir: Directory containing the config file

        Returns:
            Configuration with extends resolved
        """
        if not config.extends:
            return config

        resolved_config = copy.deepcopy(config)
        resolved_config.extends = None  # Remove extends to avoid infinite loops

        # Process extends in order
        for extend_path in config.extends:
            parent_config = self._load_parent_config(extend_path, config_dir)
            if parent_config:
                # Recursively resolve parent extends
                parent_config = self.resolve_extends(parent_config, config_dir)
                # Merge parent as base, current as override
                resolved_config = self.merger.merge_configs(parent_config, resolved_config)

        return resolved_config

    def _load_parent_config(self, extend_path: str, config_dir: Path) -> Optional[ConfigSchema]:
        """Load a parent configuration file."""
        try:
            # Try relative to config directory first
            parent_path = config_dir / extend_path
            if not parent_path.exists():
                # Try relative to current working directory
                parent_path = Path(extend_path)

            if parent_path.exists():
                # Import here to avoid circular imports
                from .config_parser import ConfigParser
                parser = ConfigParser()
                return parser.load_config(parent_path)
            else:
                self.logger.warning(f"Parent config file not found: {extend_path}")
                return None

        except Exception as e:
            self.logger.error(f"Error loading parent config {extend_path}: {e}")
            return None


def create_validator() -> AdvancedConfigValidator:
    """Factory function to create an AdvancedConfigValidator."""
    return AdvancedConfigValidator()


def create_merger() -> ConfigMerger:
    """Factory function to create a ConfigMerger."""
    return ConfigMerger()