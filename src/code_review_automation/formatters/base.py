"""
Base Formatter and Configuration Classes

Provides the foundation for all output formatters with common functionality,
configuration options, and context management.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from datetime import datetime

from ..config.rule_engine import RuleResult
from ..utils.logger import get_logger


@dataclass
class FormatterConfig:
    """Configuration for output formatters."""
    show_suggestions: bool = True
    show_line_numbers: bool = True
    show_file_paths: bool = True
    show_severity_colors: bool = True
    max_issues_per_file: int = 20
    group_by_severity: bool = False
    group_by_file: bool = True
    include_metadata: bool = False
    template_path: Optional[Path] = None
    custom_templates: Dict[str, str] = field(default_factory=dict)
    output_path: Optional[Path] = None
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"


@dataclass
class OutputContext:
    """Context information for formatting output."""
    analysis_type: str = "unknown"  # git_diff, files, pull_request
    repository_path: Optional[Path] = None
    repository_url: Optional[str] = None
    git_range: Optional[str] = None
    files_analyzed: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    analyzer_version: str = "1.0.0"
    config_used: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None
    commit_sha: Optional[str] = None
    branch_name: Optional[str] = None
    pr_number: Optional[int] = None


@dataclass
class FormattedOutput:
    """Container for formatted output with metadata."""
    content: str
    format_type: str
    size_bytes: int
    context: OutputContext
    config: FormatterConfig
    generated_at: datetime = field(default_factory=datetime.now)


class BaseFormatter(ABC):
    """Abstract base class for all output formatters."""

    def __init__(self, config: FormatterConfig = None, context: OutputContext = None):
        self.config = config or FormatterConfig()
        self.context = context or OutputContext()
        self.logger = get_logger(__name__)

    @abstractmethod
    def format(self, results: List[RuleResult], **kwargs) -> FormattedOutput:
        """
        Format analysis results.

        Args:
            results: List of rule results to format
            **kwargs: Additional formatting options

        Returns:
            Formatted output with metadata
        """
        pass

    @abstractmethod
    def get_format_type(self) -> str:
        """Get the format type identifier."""
        pass

    def create_summary(self, results: List[RuleResult]) -> Dict[str, Any]:
        """Create a summary of results for formatting."""
        if not results:
            return {
                "total_issues": 0,
                "total_suggestions": 0,
                "files_with_issues": 0,
                "severity_breakdown": {},
                "most_common_issues": [],
                "files_analyzed": self.context.files_analyzed,
                "clean_files": self.context.files_analyzed
            }

        # Group by severity
        severity_counts = {}
        issue_types = {}
        files_with_issues = set()
        suggestions_count = 0

        for result in results:
            # Count by severity
            severity = result.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # Count issue types
            issue_type = f"{result.checker_name}.{result.rule_name}"
            issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

            # Track files
            files_with_issues.add(str(result.file_path))

            # Count suggestions
            if result.suggestion:
                suggestions_count += 1

        # Most common issues
        most_common = [
            {"type": issue_type, "count": count}
            for issue_type, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "total_issues": len(results),
            "total_suggestions": suggestions_count,
            "files_with_issues": len(files_with_issues),
            "files_analyzed": self.context.files_analyzed,
            "clean_files": max(0, self.context.files_analyzed - len(files_with_issues)),
            "severity_breakdown": severity_counts,
            "most_common_issues": most_common[:10],  # Top 10
            "analysis_duration": self.context.execution_time,
            "timestamp": self.context.timestamp.strftime(self.config.timestamp_format)
        }

    def group_results(self, results: List[RuleResult]) -> Dict[str, Any]:
        """Group results by various criteria."""
        grouped = {}

        if self.config.group_by_file:
            grouped["by_file"] = self._group_by_file(results)

        if self.config.group_by_severity:
            grouped["by_severity"] = self._group_by_severity(results)

        # Always provide ungrouped results
        grouped["all"] = results

        return grouped

    def _group_by_file(self, results: List[RuleResult]) -> Dict[str, List[RuleResult]]:
        """Group results by file path."""
        grouped = {}
        for result in results:
            file_key = str(result.file_path)
            if file_key not in grouped:
                grouped[file_key] = []
            grouped[file_key].append(result)

        # Sort files by issue count (descending)
        return dict(sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True))

    def _group_by_severity(self, results: List[RuleResult]) -> Dict[str, List[RuleResult]]:
        """Group results by severity level."""
        grouped = {}
        severity_order = ["error", "warning", "suggestion", "info"]

        for result in results:
            severity = result.severity.value
            if severity not in grouped:
                grouped[severity] = []
            grouped[severity].append(result)

        # Return in severity order
        return {severity: grouped.get(severity, []) for severity in severity_order}

    def filter_results(self, results: List[RuleResult]) -> List[RuleResult]:
        """Filter results based on configuration."""
        filtered = results[:]

        # Apply max issues per file limit
        if self.config.max_issues_per_file > 0:
            by_file = self._group_by_file(filtered)
            filtered = []
            for file_path, file_results in by_file.items():
                filtered.extend(file_results[:self.config.max_issues_per_file])

        return filtered

    def sanitize_text(self, text: str, format_type: str = None) -> str:
        """Sanitize text for specific output formats."""
        if not text:
            return ""

        # Remove or escape potentially problematic characters
        if format_type == "html":
            return self._escape_html(text)
        elif format_type == "markdown":
            return self._escape_markdown(text)
        elif format_type == "json":
            return self._escape_json(text)

        return text

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;"))

    def _escape_markdown(self, text: str) -> str:
        """Escape Markdown special characters."""
        # Escape Markdown special characters but preserve some formatting
        special_chars = ['*', '_', '`', '#', '+', '-', '.', '!', '[', ']', '(', ')', '{', '}']
        for char in special_chars:
            text = text.replace(char, f"\\{char}")
        return text

    def _escape_json(self, text: str) -> str:
        """Escape JSON special characters."""
        return (text
                .replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t"))

    def format_code_snippet(self, content: str, language: str = None, max_lines: int = 5) -> str:
        """Format code snippet for display."""
        if not content:
            return ""

        lines = content.split('\n')

        # Limit number of lines
        if len(lines) > max_lines:
            lines = lines[:max_lines] + ['...']

        # Add line numbers if configured
        if self.config.show_line_numbers:
            formatted_lines = []
            for i, line in enumerate(lines, 1):
                if line == '...':
                    formatted_lines.append(line)
                else:
                    formatted_lines.append(f"{i:2d}: {line}")
            return '\n'.join(formatted_lines)

        return '\n'.join(lines)

    def format_file_path(self, file_path: Union[str, Path], base_path: Optional[Path] = None) -> str:
        """Format file path for display."""
        if not self.config.show_file_paths:
            return ""

        path_obj = Path(file_path)

        # Make relative to base path if provided
        if base_path:
            try:
                path_obj = path_obj.relative_to(base_path)
            except ValueError:
                pass  # Keep absolute path if not relative to base

        return str(path_obj)

    def get_issue_priority_score(self, result: RuleResult) -> int:
        """Get priority score for sorting issues."""
        severity_scores = {
            "error": 100,
            "warning": 75,
            "suggestion": 50,
            "info": 25
        }

        base_score = severity_scores.get(result.severity.value, 0)

        # Boost score for security issues
        if "security" in result.checker_name.lower():
            base_score += 25

        # Boost score for issues with suggestions
        if result.suggestion:
            base_score += 10

        return base_score

    def create_formatted_output(self, content: str) -> FormattedOutput:
        """Create a FormattedOutput object with metadata."""
        return FormattedOutput(
            content=content,
            format_type=self.get_format_type(),
            size_bytes=len(content.encode('utf-8')),
            context=self.context,
            config=self.config
        )

    def supports_feature(self, feature: str) -> bool:
        """Check if formatter supports a specific feature."""
        # Override in subclasses to specify supported features
        supported_features = {
            "colors": False,
            "links": False,
            "images": False,
            "tables": False,
            "code_blocks": False,
            "interactive": False,
            "streaming": False
        }
        return supported_features.get(feature, False)

    def get_template(self, template_name: str) -> Optional[str]:
        """Get custom template by name."""
        return self.config.custom_templates.get(template_name)

    def render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Simple template rendering with variable substitution."""
        rendered = template

        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            rendered = rendered.replace(placeholder, str(value))

        return rendered


class MultiFormatSupport:
    """Mixin class for formatters that support multiple sub-formats."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sub_formats = set()

    def add_sub_format(self, format_name: str):
        """Add support for a sub-format."""
        self.sub_formats.add(format_name)

    def supports_sub_format(self, format_name: str) -> bool:
        """Check if sub-format is supported."""
        return format_name in self.sub_formats

    def get_available_sub_formats(self) -> List[str]:
        """Get list of available sub-formats."""
        return sorted(list(self.sub_formats))