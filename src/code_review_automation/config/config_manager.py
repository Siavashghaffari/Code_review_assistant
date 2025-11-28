"""
Configuration Manager

Main interface for configuration management, combining parsing, validation,
severity handling, and rule engine integration.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import os

from .config_parser import ConfigParser, EnvironmentConfigProvider
from .rule_engine import RuleEngine, RuleResult
from .schema import ConfigSchema, SeverityLevel, create_default_config
from ..utils.logger import get_logger


class SeverityManager:
    """Manages severity levels and filtering."""

    def __init__(self, config: ConfigSchema):
        self.config = config
        self.logger = get_logger(__name__)

    def filter_by_severity(self, results: List[RuleResult]) -> List[RuleResult]:
        """Filter results based on severity threshold."""
        severity_order = self._get_severity_order()
        threshold = severity_order[self.config.severity_threshold]

        filtered = [
            result for result in results
            if severity_order[result.severity] >= threshold
        ]

        self.logger.debug(
            f"Filtered {len(results)} results to {len(filtered)} "
            f"with severity >= {self.config.severity_threshold.value}"
        )

        return filtered

    def group_by_severity(self, results: List[RuleResult]) -> Dict[SeverityLevel, List[RuleResult]]:
        """Group results by severity level."""
        groups = {severity: [] for severity in SeverityLevel}

        for result in results:
            groups[result.severity].append(result)

        return groups

    def get_severity_counts(self, results: List[RuleResult]) -> Dict[str, int]:
        """Get count of issues by severity."""
        groups = self.group_by_severity(results)
        return {
            severity.value: len(issues)
            for severity, issues in groups.items()
            if issues  # Only include non-empty groups
        }

    def should_fail_build(self, results: List[RuleResult]) -> bool:
        """Determine if build should fail based on severity levels."""
        severity_order = self._get_severity_order()
        fail_threshold = severity_order[self.config.fail_on_severity]

        failing_results = [
            result for result in results
            if severity_order[result.severity] >= fail_threshold
        ]

        if failing_results:
            self.logger.info(
                f"Build should fail: {len(failing_results)} issues with "
                f"severity >= {self.config.fail_on_severity.value}"
            )

        return bool(failing_results)

    def get_max_severity(self, results: List[RuleResult]) -> Optional[SeverityLevel]:
        """Get the highest severity level from results."""
        if not results:
            return None

        severity_order = self._get_severity_order()
        max_severity = max(results, key=lambda r: severity_order[r.severity]).severity

        return max_severity

    def _get_severity_order(self) -> Dict[SeverityLevel, int]:
        """Get severity ordering for comparisons."""
        return {
            SeverityLevel.INFO: 0,
            SeverityLevel.SUGGESTION: 1,
            SeverityLevel.WARNING: 2,
            SeverityLevel.ERROR: 3
        }


class ConfigManager:
    """Main configuration manager."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self.logger = get_logger(__name__)
        self.parser = ConfigParser()

        # Load configuration
        self.config = self._load_configuration(config_path)
        self.severity_manager = SeverityManager(self.config)
        self.rule_engine = RuleEngine(self.config)

        self.logger.info("Configuration manager initialized")

    def _load_configuration(self, config_path: Optional[Union[str, Path]]) -> ConfigSchema:
        """Load configuration from file with environment overrides."""
        # Load base configuration
        config = self.parser.load_config(config_path)

        # Apply environment variable overrides
        env_overrides = EnvironmentConfigProvider.get_environment_overrides()
        if env_overrides:
            config = self.parser.merge_configs(config, env_overrides)
            self.logger.info("Applied environment variable overrides")

        return config

    def get_config(self) -> ConfigSchema:
        """Get current configuration."""
        return self.config

    def reload_config(self, config_path: Optional[Union[str, Path]] = None):
        """Reload configuration from file."""
        self.config = self._load_configuration(config_path)
        self.severity_manager = SeverityManager(self.config)
        self.rule_engine = RuleEngine(self.config)
        self.logger.info("Configuration reloaded")

    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with new values."""
        self.config = self.parser.merge_configs(self.config, updates)
        self.severity_manager = SeverityManager(self.config)
        self.rule_engine = RuleEngine(self.config)
        self.logger.info("Configuration updated")

    def save_config(self, output_path: Union[str, Path], format: str = "yaml") -> bool:
        """Save current configuration to file."""
        return self.parser.save_config(self.config, output_path, format)

    def get_rule_engine(self) -> RuleEngine:
        """Get rule engine instance."""
        return self.rule_engine

    def get_severity_manager(self) -> SeverityManager:
        """Get severity manager instance."""
        return self.severity_manager

    def is_file_ignored(self, file_path: Path) -> bool:
        """Check if file should be ignored."""
        return self.rule_engine.filter.should_ignore_file(file_path)

    def get_file_type_config(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Get file type specific configuration."""
        file_type = self.rule_engine.filter.get_file_type(file_path)
        if file_type and file_type in self.config.file_types:
            return self.config.file_types[file_type]
        return None

    def validate_config(self) -> List[str]:
        """Validate current configuration."""
        errors = []

        # Validate schema
        schema_errors = self.parser.validator.validate_config(self.config)
        errors.extend(schema_errors)

        # Validate rule engine configuration
        rule_errors = self.rule_engine.validate_configuration()
        errors.extend(rule_errors)

        if errors:
            self.logger.warning(f"Configuration validation found {len(errors)} errors")
        else:
            self.logger.info("Configuration validation passed")

        return errors

    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get comprehensive configuration summary."""
        rule_summary = self.rule_engine.get_enabled_rules_summary()

        return {
            "version": self.config.version,
            "severity_threshold": self.config.severity_threshold.value,
            "fail_on_severity": self.config.fail_on_severity.value,
            "max_issues_per_run": self.config.max_issues_per_run,
            "ignore_patterns": len(self.config.ignore_patterns),
            "include_patterns": len(self.config.include_patterns),
            "file_types_configured": len(self.config.file_types),
            "custom_rules": len(self.config.custom_rules),
            "rules": rule_summary,
            "output_format": getattr(self.config.output, 'format', 'terminal'),
            "git_integration_enabled": getattr(self.config.git, 'enabled', False)
        }

    def create_team_preset(self, team_name: str, preset_config: Dict[str, Any]) -> bool:
        """Create a team-specific configuration preset."""
        try:
            preset_path = Path(f".codereview-{team_name}.yaml")
            merged_config = self.parser.merge_configs(self.config, preset_config)

            success = self.parser.save_config(merged_config, preset_path, "yaml")
            if success:
                self.logger.info(f"Team preset created: {preset_path}")

            return success

        except Exception as e:
            self.logger.error(f"Error creating team preset: {e}")
            return False

    def apply_severity_profile(self, profile: str):
        """Apply predefined severity profiles."""
        profiles = {
            "strict": {
                "severity_threshold": "suggestion",
                "fail_on_severity": "warning",
                "checkers": {
                    "complexity": {"severity_override": "warning"},
                    "style": {"severity_override": "warning"},
                    "security": {"severity_override": "error"}
                }
            },
            "relaxed": {
                "severity_threshold": "warning",
                "fail_on_severity": "error",
                "checkers": {
                    "style": {"enabled": False},
                    "complexity": {"severity_override": "suggestion"}
                }
            },
            "security_focused": {
                "severity_threshold": "info",
                "fail_on_severity": "warning",
                "checkers": {
                    "security": {"severity_override": "error"},
                    "style": {"enabled": False},
                    "complexity": {"enabled": False}
                }
            }
        }

        if profile in profiles:
            self.update_config(profiles[profile])
            self.logger.info(f"Applied severity profile: {profile}")
        else:
            self.logger.warning(f"Unknown severity profile: {profile}")

    def get_checker_status(self, checker_name: str) -> Dict[str, Any]:
        """Get detailed status of a specific checker."""
        if checker_name not in self.config.checkers:
            return {"error": f"Checker '{checker_name}' not found"}

        checker_config = self.config.checkers[checker_name]
        rule_summary = {}

        if checker_name in self.rule_engine._rule_registry:
            available_rules = self.rule_engine._rule_registry[checker_name]
            for rule_name in available_rules:
                rule_config = checker_config.rules.get(rule_name)
                rule_summary[rule_name] = {
                    "enabled": rule_config.enabled if rule_config else True,
                    "severity": rule_config.severity.value if rule_config else "warning",
                    "has_options": bool(rule_config.options if rule_config else False)
                }

        return {
            "enabled": checker_config.enabled,
            "severity_override": checker_config.severity_override.value if checker_config.severity_override else None,
            "total_rules": len(rule_summary),
            "enabled_rules": sum(1 for r in rule_summary.values() if r["enabled"]),
            "rules": rule_summary
        }

    def enable_rule(self, checker_name: str, rule_name: str):
        """Enable a specific rule."""
        if checker_name not in self.config.checkers:
            self.config.checkers[checker_name] = CheckerConfig()

        if rule_name not in self.config.checkers[checker_name].rules:
            from .schema import RuleConfig
            self.config.checkers[checker_name].rules[rule_name] = RuleConfig()

        self.config.checkers[checker_name].rules[rule_name].enabled = True
        self.logger.info(f"Enabled rule: {checker_name}.{rule_name}")

    def disable_rule(self, checker_name: str, rule_name: str):
        """Disable a specific rule."""
        if checker_name in self.config.checkers and rule_name in self.config.checkers[checker_name].rules:
            self.config.checkers[checker_name].rules[rule_name].enabled = False
            self.logger.info(f"Disabled rule: {checker_name}.{rule_name}")

    def set_rule_severity(self, checker_name: str, rule_name: str, severity: Union[str, SeverityLevel]):
        """Set severity for a specific rule."""
        if isinstance(severity, str):
            severity = SeverityLevel(severity)

        if checker_name not in self.config.checkers:
            from .schema import CheckerConfig
            self.config.checkers[checker_name] = CheckerConfig()

        if rule_name not in self.config.checkers[checker_name].rules:
            from .schema import RuleConfig
            self.config.checkers[checker_name].rules[rule_name] = RuleConfig()

        self.config.checkers[checker_name].rules[rule_name].severity = severity
        self.logger.info(f"Set severity for {checker_name}.{rule_name}: {severity.value}")


def create_config_manager(config_path: Optional[Union[str, Path]] = None) -> ConfigManager:
    """Factory function to create ConfigManager instance."""
    return ConfigManager(config_path)