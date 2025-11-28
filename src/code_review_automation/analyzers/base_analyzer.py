"""
Base Analyzer

Abstract base class for all code analyzers.
"""

import re
from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseAnalyzer(ABC):
    """Abstract base class for code analyzers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def analyze(self, target: Any) -> Dict[str, Any]:
        """
        Analyze the target and return results.

        Args:
            target: The target to analyze (file paths, git range, etc.)

        Returns:
            Analysis results dictionary
        """
        pass

    def get_language_rules(self, file_extension: str) -> Dict[str, Any]:
        """Get language-specific rules from configuration."""
        return self.config.get("languages", {}).get(file_extension, {})

    def _check_line_issues(self, line: str, language_rules: Dict) -> List[Dict[str, Any]]:
        """Check a line for common issues."""
        issues = []

        # Line length check
        max_line_length = language_rules.get("max_line_length", 120)
        if len(line) > max_line_length:
            issues.append({
                "type": "line_too_long",
                "severity": "warning",
                "message": f"Line exceeds {max_line_length} characters ({len(line)})"
            })

        # Trailing whitespace
        if line.rstrip() != line:
            issues.append({
                "type": "trailing_whitespace",
                "severity": "info",
                "message": "Line has trailing whitespace"
            })

        # Tab characters
        if '\t' in line and language_rules.get("no_tabs", False):
            issues.append({
                "type": "tab_character",
                "severity": "warning",
                "message": "Line contains tab characters, use spaces instead"
            })

        # TODO/FIXME comments
        if re.search(r'\b(TODO|FIXME|XXX|HACK)\b', line, re.IGNORECASE):
            issues.append({
                "type": "todo_comment",
                "severity": "info",
                "message": "Line contains TODO/FIXME comment"
            })

        # Language-specific checks
        issues.extend(self._check_language_specific_issues(line, language_rules))

        return issues

    def _check_line_suggestions(self, line: str, language_rules: Dict) -> List[Dict[str, Any]]:
        """Check a line for improvement suggestions."""
        suggestions = []

        # Language-specific suggestions
        suggestions.extend(self._get_language_specific_suggestions(line, language_rules))

        return suggestions

    def _check_language_specific_issues(self, line: str, language_rules: Dict) -> List[Dict[str, Any]]:
        """Check for language-specific issues."""
        issues = []

        # Python-specific checks
        if language_rules.get("language") == "python":
            # Import style
            if line.strip().startswith("from") and " import *" in line:
                issues.append({
                    "type": "wildcard_import",
                    "severity": "warning",
                    "message": "Avoid wildcard imports"
                })

            # Print statements (should use logging)
            if re.search(r'\bprint\s*\(', line):
                issues.append({
                    "type": "print_statement",
                    "severity": "info",
                    "message": "Consider using logging instead of print"
                })

            # Multiple statements on one line
            if ';' in line and not line.strip().startswith('#'):
                issues.append({
                    "type": "multiple_statements",
                    "severity": "warning",
                    "message": "Avoid multiple statements on one line"
                })

        # JavaScript-specific checks
        elif language_rules.get("language") == "javascript":
            # Console statements
            if re.search(r'\bconsole\.(log|warn|error|debug)\s*\(', line):
                issues.append({
                    "type": "console_statement",
                    "severity": "info",
                    "message": "Remove console statements before production"
                })

            # Var usage
            if re.search(r'\bvar\s+', line):
                issues.append({
                    "type": "var_usage",
                    "severity": "warning",
                    "message": "Use 'let' or 'const' instead of 'var'"
                })

        return issues

    def _get_language_specific_suggestions(self, line: str, language_rules: Dict) -> List[Dict[str, Any]]:
        """Get language-specific suggestions."""
        suggestions = []

        # Python-specific suggestions
        if language_rules.get("language") == "python":
            # String formatting
            if '"' in line and '%' in line and 's' in line:
                suggestions.append({
                    "type": "string_formatting",
                    "severity": "info",
                    "message": "Consider using f-strings for string formatting"
                })

            # List comprehension opportunity
            if "for " in line and " in " in line and ".append(" in line:
                suggestions.append({
                    "type": "list_comprehension",
                    "severity": "info",
                    "message": "Consider using list comprehension"
                })

        return suggestions