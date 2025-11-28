"""
Rule Engine

Manages rule execution, filtering, and enable/disable controls based on configuration.
"""

import fnmatch
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass

from .schema import (
    ConfigSchema, RuleConfig, SeverityLevel, FileTypeConfig,
    CheckerConfig, IgnorePattern
)
from ..utils.logger import get_logger


@dataclass
class RuleContext:
    """Context information for rule execution."""
    file_path: Path
    file_type: Optional[FileTypeConfig] = None
    checker_name: str = ""
    rule_name: str = ""
    content: str = ""
    line_number: Optional[int] = None


@dataclass
class RuleResult:
    """Result of a rule execution."""
    rule_name: str
    checker_name: str
    severity: SeverityLevel
    message: str
    file_path: Path
    line_number: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RuleFilter:
    """Filters rules and results based on configuration."""

    def __init__(self, config: ConfigSchema):
        self.config = config
        self.logger = get_logger(__name__)

    def should_ignore_file(self, file_path: Path) -> bool:
        """Check if file should be ignored based on patterns."""
        file_str = str(file_path)

        # Check ignore patterns
        for pattern in self.config.ignore_patterns:
            if self._matches_pattern(file_str, pattern.pattern, pattern.type):
                self.logger.debug(f"File {file_path} ignored by pattern: {pattern.pattern}")
                return True

        # Check if file matches include patterns
        if self.config.include_patterns:
            matches_include = False
            for pattern in self.config.include_patterns:
                if self._matches_pattern(file_str, pattern, "glob"):
                    matches_include = True
                    break

            if not matches_include:
                self.logger.debug(f"File {file_path} not in include patterns")
                return True

        return False

    def _matches_pattern(self, text: str, pattern: str, pattern_type: str) -> bool:
        """Check if text matches pattern based on type."""
        if pattern_type == "glob":
            return fnmatch.fnmatch(text, pattern)
        elif pattern_type == "regex":
            try:
                return bool(re.search(pattern, text))
            except re.error:
                self.logger.warning(f"Invalid regex pattern: {pattern}")
                return False
        elif pattern_type == "path":
            return pattern in text
        return False

    def get_file_type(self, file_path: Path) -> Optional[FileTypeConfig]:
        """Determine file type from path."""
        suffix = file_path.suffix.lower()

        type_mapping = {
            '.py': FileTypeConfig.PYTHON,
            '.js': FileTypeConfig.JAVASCRIPT,
            '.ts': FileTypeConfig.TYPESCRIPT,
            '.jsx': FileTypeConfig.JAVASCRIPT,
            '.tsx': FileTypeConfig.TYPESCRIPT,
            '.json': FileTypeConfig.JSON,
            '.yaml': FileTypeConfig.YAML,
            '.yml': FileTypeConfig.YAML,
            '.md': FileTypeConfig.MARKDOWN,
        }

        return type_mapping.get(suffix)

    def filter_results_by_severity(self, results: List[RuleResult]) -> List[RuleResult]:
        """Filter results based on severity threshold."""
        severity_order = {
            SeverityLevel.INFO: 0,
            SeverityLevel.SUGGESTION: 1,
            SeverityLevel.WARNING: 2,
            SeverityLevel.ERROR: 3
        }

        threshold = severity_order[self.config.severity_threshold]
        return [
            result for result in results
            if severity_order[result.severity] >= threshold
        ]

    def should_fail_build(self, results: List[RuleResult]) -> bool:
        """Check if build should fail based on severity."""
        severity_order = {
            SeverityLevel.INFO: 0,
            SeverityLevel.SUGGESTION: 1,
            SeverityLevel.WARNING: 2,
            SeverityLevel.ERROR: 3
        }

        fail_threshold = severity_order[self.config.fail_on_severity]
        return any(
            severity_order[result.severity] >= fail_threshold
            for result in results
        )


class RuleEngine:
    """Main rule engine that orchestrates rule execution."""

    def __init__(self, config: ConfigSchema):
        self.config = config
        self.filter = RuleFilter(config)
        self.logger = get_logger(__name__)
        self._rule_registry: Dict[str, Dict[str, Callable]] = {}

    def register_checker_rules(self, checker_name: str, rules: Dict[str, Callable]):
        """Register rules for a specific checker."""
        self._rule_registry[checker_name] = rules
        self.logger.debug(f"Registered {len(rules)} rules for checker {checker_name}")

    def is_checker_enabled(self, checker_name: str) -> bool:
        """Check if a checker is enabled."""
        if checker_name not in self.config.checkers:
            return True  # Default enabled

        return self.config.checkers[checker_name].enabled

    def is_rule_enabled(self, checker_name: str, rule_name: str, context: RuleContext) -> bool:
        """Check if a specific rule is enabled for the given context."""
        if not self.is_checker_enabled(checker_name):
            return False

        checker_config = self.config.checkers.get(checker_name)
        if not checker_config:
            return True

        rule_config = checker_config.rules.get(rule_name)
        if not rule_config:
            return True

        if not rule_config.enabled:
            return False

        # Check file type restrictions
        if rule_config.file_types and context.file_type:
            if context.file_type not in rule_config.file_types:
                return False

        # Check rule-specific ignore patterns
        if rule_config.ignore_patterns:
            file_str = str(context.file_path)
            for pattern in rule_config.ignore_patterns:
                if self.filter._matches_pattern(file_str, pattern, "glob"):
                    return False

        return True

    def get_rule_config(self, checker_name: str, rule_name: str) -> Optional[RuleConfig]:
        """Get configuration for a specific rule."""
        checker_config = self.config.checkers.get(checker_name)
        if not checker_config:
            return None

        return checker_config.rules.get(rule_name)

    def get_effective_severity(self, checker_name: str, rule_name: str, default_severity: SeverityLevel) -> SeverityLevel:
        """Get effective severity for a rule considering overrides."""
        checker_config = self.config.checkers.get(checker_name)
        if not checker_config:
            return default_severity

        # Check checker-level severity override
        if checker_config.severity_override:
            return checker_config.severity_override

        # Check rule-specific severity
        rule_config = checker_config.rules.get(rule_name)
        if rule_config:
            return rule_config.severity

        return default_severity

    def execute_rules_for_file(self, file_path: Path, content: str) -> List[RuleResult]:
        """Execute all applicable rules for a file."""
        if self.filter.should_ignore_file(file_path):
            return []

        file_type = self.filter.get_file_type(file_path)
        context = RuleContext(
            file_path=file_path,
            file_type=file_type,
            content=content
        )

        all_results = []
        rules_executed = 0

        for checker_name, rules in self._rule_registry.items():
            if not self.is_checker_enabled(checker_name):
                continue

            context.checker_name = checker_name

            for rule_name, rule_func in rules.items():
                context.rule_name = rule_name

                if not self.is_rule_enabled(checker_name, rule_name, context):
                    continue

                try:
                    rule_results = self._execute_rule(rule_func, context)

                    # Apply severity overrides
                    for result in rule_results:
                        result.severity = self.get_effective_severity(
                            checker_name, rule_name, result.severity
                        )

                    all_results.extend(rule_results)
                    rules_executed += 1

                    # Check max issues limit
                    if len(all_results) >= self.config.max_issues_per_run:
                        self.logger.info(f"Reached max issues limit ({self.config.max_issues_per_run})")
                        break

                except Exception as e:
                    self.logger.error(f"Error executing rule {checker_name}.{rule_name}: {e}")

            if len(all_results) >= self.config.max_issues_per_run:
                break

        self.logger.debug(f"Executed {rules_executed} rules for {file_path}, found {len(all_results)} issues")
        return self.filter.filter_results_by_severity(all_results)

    def _execute_rule(self, rule_func: Callable, context: RuleContext) -> List[RuleResult]:
        """Execute a single rule function."""
        rule_config = self.get_rule_config(context.checker_name, context.rule_name)

        # Prepare rule options
        options = rule_config.options if rule_config else {}

        # Get file type specific options
        if context.file_type and context.file_type in self.config.file_types:
            file_type_config = self.config.file_types[context.file_type]

            # Add file type specific limits as options
            options.update({
                'max_line_length': file_type_config.max_line_length,
                'max_function_length': file_type_config.max_function_length,
                'max_complexity': file_type_config.max_complexity,
                'naming_conventions': file_type_config.naming_conventions
            })

        # Execute rule
        try:
            results = rule_func(context, options)

            # Ensure results are properly formatted
            if not isinstance(results, list):
                results = [results] if results else []

            formatted_results = []
            for result in results:
                if isinstance(result, RuleResult):
                    formatted_results.append(result)
                elif isinstance(result, dict):
                    # Convert dict to RuleResult
                    formatted_results.append(RuleResult(
                        rule_name=context.rule_name,
                        checker_name=context.checker_name,
                        severity=result.get('severity', SeverityLevel.WARNING),
                        message=result.get('message', ''),
                        file_path=context.file_path,
                        line_number=result.get('line_number'),
                        column=result.get('column'),
                        suggestion=result.get('suggestion'),
                        metadata=result.get('metadata', {})
                    ))

            return formatted_results

        except Exception as e:
            self.logger.error(f"Rule execution failed: {e}")
            return []

    def get_enabled_rules_summary(self) -> Dict[str, Any]:
        """Get summary of enabled rules and checkers."""
        summary = {
            'total_checkers': len(self._rule_registry),
            'enabled_checkers': 0,
            'total_rules': 0,
            'enabled_rules': 0,
            'checkers': {}
        }

        for checker_name, rules in self._rule_registry.items():
            is_enabled = self.is_checker_enabled(checker_name)
            summary['checkers'][checker_name] = {
                'enabled': is_enabled,
                'total_rules': len(rules),
                'enabled_rules': 0,
                'rules': {}
            }

            if is_enabled:
                summary['enabled_checkers'] += 1

            summary['total_rules'] += len(rules)

            # Check individual rules (using dummy context)
            dummy_context = RuleContext(
                file_path=Path("dummy.py"),
                file_type=FileTypeConfig.PYTHON,
                checker_name=checker_name
            )

            for rule_name in rules:
                dummy_context.rule_name = rule_name
                rule_enabled = self.is_rule_enabled(checker_name, rule_name, dummy_context)

                summary['checkers'][checker_name]['rules'][rule_name] = {
                    'enabled': rule_enabled
                }

                if rule_enabled and is_enabled:
                    summary['enabled_rules'] += 1
                    summary['checkers'][checker_name]['enabled_rules'] += 1

        return summary

    def validate_configuration(self) -> List[str]:
        """Validate the current configuration."""
        errors = []

        # Check for unknown checkers
        for checker_name in self.config.checkers:
            if checker_name not in self._rule_registry:
                errors.append(f"Unknown checker: {checker_name}")

        # Check for unknown rules
        for checker_name, checker_config in self.config.checkers.items():
            if checker_name in self._rule_registry:
                available_rules = set(self._rule_registry[checker_name].keys())
                configured_rules = set(checker_config.rules.keys())
                unknown_rules = configured_rules - available_rules

                for rule_name in unknown_rules:
                    errors.append(f"Unknown rule: {checker_name}.{rule_name}")

        return errors