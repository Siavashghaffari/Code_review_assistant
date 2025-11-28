"""
Terminal Formatter

Formats analysis results for terminal output with colors and Unicode symbols.
"""

import sys
from typing import Dict, List, Any

from .base_formatter import BaseFormatter


class TerminalFormatter(BaseFormatter):
    """Formatter for terminal output."""

    def __init__(self):
        super().__init__()
        self.use_colors = self._supports_color()
        self.use_unicode = self._supports_unicode()

    def format(self, results: Dict[str, Any]) -> str:
        """Format results for terminal display."""
        output_lines = []

        # Header
        output_lines.append(self._format_header(results))
        output_lines.append("")

        # Summary
        summary = results.get("summary", {})
        output_lines.append(self._format_summary(summary))
        output_lines.append("")

        # Issues by file
        issues = results.get("issues", [])
        if issues:
            output_lines.append(self._colorize("📋 Issues Found:", "bold"))
            output_lines.append("")
            output_lines.extend(self._format_issues(issues))
            output_lines.append("")

        # Suggestions
        suggestions = results.get("suggestions", [])
        if suggestions:
            output_lines.append(self._colorize("💡 Suggestions:", "bold"))
            output_lines.append("")
            output_lines.extend(self._format_suggestions(suggestions))
            output_lines.append("")

        # Footer
        output_lines.append(self._format_footer())

        return "\n".join(output_lines)

    def _format_header(self, results: Dict[str, Any]) -> str:
        """Format the header section."""
        title = "Code Review Analysis Results"
        if self.use_unicode:
            title = f"🔍 {title}"

        lines = [
            self._colorize(title, "bold"),
            self._colorize("=" * len(title), "dim")
        ]

        # Analysis type info
        analysis_type = results.get("analysis_type", "unknown")
        if analysis_type == "git_diff":
            git_range = results.get("git_range", "")
            lines.append(f"Git Range: {self._colorize(git_range, 'cyan')}")
        elif analysis_type == "files":
            files_count = results.get("files_analyzed", 0)
            lines.append(f"Files Analyzed: {self._colorize(str(files_count), 'cyan')}")

        return "\n".join(lines)

    def _format_summary(self, summary: Dict[str, Any]) -> str:
        """Format the summary section."""
        lines = [self._colorize("📊 Summary:", "bold")]

        total_issues = summary.get("total_issues", 0)
        total_suggestions = summary.get("total_suggestions", 0)

        # Issue count with color coding
        if total_issues == 0:
            issue_text = self._colorize(f"{total_issues} issues", "green")
        elif total_issues <= 5:
            issue_text = self._colorize(f"{total_issues} issues", "yellow")
        else:
            issue_text = self._colorize(f"{total_issues} issues", "red")

        lines.append(f"  • Total Issues: {issue_text}")
        lines.append(f"  • Total Suggestions: {self._colorize(str(total_suggestions), 'blue')}")

        # Files with issues
        files_with_issues = summary.get("files_with_issues", 0)
        if files_with_issues > 0:
            lines.append(f"  • Files with Issues: {self._colorize(str(files_with_issues), 'yellow')}")

        # Severity breakdown
        severity_breakdown = summary.get("severity_breakdown", {})
        if severity_breakdown:
            lines.append("  • By Severity:")
            for severity, count in severity_breakdown.items():
                color = self._get_severity_color(severity)
                lines.append(f"    - {severity.title()}: {self._colorize(str(count), color)}")

        # Most common issues
        most_common = summary.get("most_common_issues", [])
        if most_common:
            lines.append("  • Most Common Issues:")
            for issue in most_common[:3]:  # Top 3
                issue_type = issue.get("type", "unknown")
                count = issue.get("count", 0)
                lines.append(f"    - {issue_type}: {self._colorize(str(count), 'cyan')}")

        return "\n".join(lines)

    def _format_issues(self, issues: List[Dict[str, Any]]) -> List[str]:
        """Format the issues section."""
        lines = []

        # Group issues by file
        issues_by_file = {}
        for issue in issues:
            file_path = issue.get("file", "unknown")
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)

        for file_path, file_issues in issues_by_file.items():
            # File header
            lines.append(self._colorize(f"📄 {file_path}", "bold"))

            for issue in file_issues:
                lines.extend(self._format_single_issue(issue))

            lines.append("")  # Empty line between files

        return lines

    def _format_single_issue(self, issue: Dict[str, Any]) -> List[str]:
        """Format a single issue."""
        lines = []

        severity = issue.get("severity", "info")
        issue_type = issue.get("type", "unknown")
        message = issue.get("message", "No message")
        line_number = issue.get("line")

        # Issue line with severity indicator
        severity_symbol = self._get_severity_symbol(severity)
        severity_color = self._get_severity_color(severity)

        issue_line = f"  {severity_symbol} {self._colorize(severity.upper(), severity_color)}: {message}"
        if line_number:
            issue_line += f" {self._colorize(f'(line {line_number})', 'dim')}"

        lines.append(issue_line)

        # Show code content if available
        content = issue.get("content")
        if content:
            lines.append(f"    {self._colorize('Code:', 'dim')} {content}")

        return lines

    def _format_suggestions(self, suggestions: List[Dict[str, Any]]) -> List[str]:
        """Format the suggestions section."""
        lines = []

        for suggestion in suggestions:
            message = suggestion.get("message", "No message")
            file_path = suggestion.get("file", "")
            line_number = suggestion.get("line")

            suggestion_line = f"  💡 {message}"
            if file_path and line_number:
                location = f"{file_path}:{line_number}"
                suggestion_line += f" {self._colorize(f'({location})', 'dim')}"

            lines.append(suggestion_line)

            # Show code content if available
            content = suggestion.get("content")
            if content:
                lines.append(f"    {self._colorize('Code:', 'dim')} {content}")

        return lines

    def _format_footer(self) -> str:
        """Format the footer section."""
        return self._colorize("Analysis complete.", "dim")

    def _get_severity_symbol(self, severity: str) -> str:
        """Get Unicode symbol for severity level."""
        if not self.use_unicode:
            return {"error": "!", "warning": "⚠", "info": "i"}.get(severity, "•")

        return {
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }.get(severity, "•")

    def _get_severity_color(self, severity: str) -> str:
        """Get color for severity level."""
        return {
            "error": "red",
            "warning": "yellow",
            "info": "blue"
        }.get(severity, "white")

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are supported."""
        if not self.use_colors:
            return text

        colors = {
            "red": "\033[31m",
            "green": "\033[32m",
            "yellow": "\033[33m",
            "blue": "\033[34m",
            "cyan": "\033[36m",
            "white": "\033[37m",
            "bold": "\033[1m",
            "dim": "\033[2m",
            "reset": "\033[0m"
        }

        color_code = colors.get(color, "")
        reset_code = colors["reset"]

        return f"{color_code}{text}{reset_code}"

    def _supports_color(self) -> bool:
        """Check if terminal supports colors."""
        return (
            hasattr(sys.stdout, 'isatty') and
            sys.stdout.isatty() and
            'NO_COLOR' not in sys.environ
        )

    def _supports_unicode(self) -> bool:
        """Check if terminal supports Unicode."""
        try:
            return sys.stdout.encoding.lower().startswith('utf')
        except AttributeError:
            return False