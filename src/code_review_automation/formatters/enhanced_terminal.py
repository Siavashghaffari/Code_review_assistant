"""
Enhanced Terminal Formatter

Advanced terminal formatter with colors, Unicode symbols, progress indicators,
and interactive features.
"""

import sys
import os
import shutil
from typing import Dict, List, Any, Optional
from pathlib import Path

from .base import BaseFormatter, FormatterConfig, OutputContext, MultiFormatSupport
from ..config.rule_engine import RuleResult
from ..config.schema import SeverityLevel


class TerminalFormatter(BaseFormatter, MultiFormatSupport):
    """Enhanced terminal formatter with advanced features."""

    def __init__(self, config: FormatterConfig = None, context: OutputContext = None):
        super().__init__(config, context)
        self.use_colors = self._supports_color()
        self.use_unicode = self._supports_unicode()
        self.terminal_width = self._get_terminal_width()

        # Add sub-formats
        self.add_sub_format("compact")
        self.add_sub_format("detailed")
        self.add_sub_format("summary")
        self.add_sub_format("interactive")

    def get_format_type(self) -> str:
        return "terminal"

    def supports_feature(self, feature: str) -> bool:
        features = {
            "colors": self.use_colors,
            "unicode": self.use_unicode,
            "interactive": True,
            "streaming": True,
            "progress": True
        }
        return features.get(feature, False)

    def format(self, results: List[RuleResult], sub_format: str = "detailed", **kwargs) -> Any:
        """Format results for terminal display."""
        if sub_format == "compact":
            return self._format_compact(results)
        elif sub_format == "summary":
            return self._format_summary_only(results)
        elif sub_format == "interactive":
            return self._format_interactive(results)
        else:
            return self._format_detailed(results)

    def _format_detailed(self, results: List[RuleResult]) -> Any:
        """Format detailed terminal output."""
        filtered_results = self.filter_results(results)
        summary = self.create_summary(filtered_results)
        grouped = self.group_results(filtered_results)

        output_lines = []

        # Header with box drawing
        output_lines.extend(self._create_header())
        output_lines.append("")

        # Summary section
        output_lines.extend(self._create_summary_section(summary))
        output_lines.append("")

        # Issues section
        if filtered_results:
            output_lines.extend(self._create_issues_section(grouped))
            output_lines.append("")

        # Footer
        output_lines.extend(self._create_footer(summary))

        content = "\n".join(output_lines)
        return self.create_formatted_output(content)

    def _format_compact(self, results: List[RuleResult]) -> Any:
        """Format compact terminal output."""
        if not results:
            return self.create_formatted_output(
                self._colorize("✅ No issues found!", "green")
            )

        lines = []
        summary = self.create_summary(results)

        # One-line summary
        total = summary["total_issues"]
        files = summary["files_with_issues"]

        summary_line = f"{self._get_status_symbol(total)} {total} issues in {files} files"
        if summary["severity_breakdown"]:
            severity_parts = []
            for severity, count in summary["severity_breakdown"].items():
                if count > 0:
                    color = self._get_severity_color(severity)
                    severity_parts.append(self._colorize(f"{count} {severity}", color))
            if severity_parts:
                summary_line += f" ({', '.join(severity_parts)})"

        lines.append(summary_line)

        # Top issues (limit to 10)
        grouped = self._group_by_file(results)
        issue_count = 0
        for file_path, file_results in list(grouped.items())[:5]:  # Top 5 files
            relative_path = self.format_file_path(file_path, self.context.repository_path)
            file_issues = len(file_results)

            symbol = self._get_severity_symbol(file_results[0].severity.value)
            lines.append(f"  {symbol} {relative_path}: {file_issues} issues")

            issue_count += file_issues
            if issue_count >= 10:
                remaining = total - issue_count
                if remaining > 0:
                    lines.append(f"  ... and {remaining} more issues")
                break

        content = "\n".join(lines)
        return self.create_formatted_output(content)

    def _format_summary_only(self, results: List[RuleResult]) -> Any:
        """Format summary-only output."""
        summary = self.create_summary(results)

        lines = []
        lines.append(self._create_title_bar("Analysis Summary"))
        lines.append("")

        # Key metrics
        total_issues = summary["total_issues"]
        files_analyzed = summary["files_analyzed"]
        clean_files = summary["clean_files"]

        lines.append(f"📊 Total Issues: {self._colorize_by_count(total_issues)}")
        lines.append(f"📁 Files Analyzed: {self._colorize(str(files_analyzed), 'cyan')}")
        lines.append(f"✅ Clean Files: {self._colorize(str(clean_files), 'green')}")

        if summary["analysis_duration"]:
            duration = f"{summary['analysis_duration']:.2f}s"
            lines.append(f"⏱️  Duration: {self._colorize(duration, 'dim')}")

        # Severity breakdown with progress bars
        if summary["severity_breakdown"]:
            lines.append("")
            lines.append("Severity Breakdown:")

            max_count = max(summary["severity_breakdown"].values()) if summary["severity_breakdown"] else 1
            for severity in ["error", "warning", "suggestion", "info"]:
                count = summary["severity_breakdown"].get(severity, 0)
                if count > 0:
                    percentage = (count / max_count) * 100
                    bar = self._create_progress_bar(percentage, 20)
                    color = self._get_severity_color(severity)
                    lines.append(f"  {severity.upper():>10}: {self._colorize(str(count).rjust(3), color)} {bar}")

        content = "\n".join(lines)
        return self.create_formatted_output(content)

    def _create_header(self) -> List[str]:
        """Create a fancy header with box drawing."""
        lines = []

        title = "🔍 Code Review Analysis Results"
        subtitle = f"Analysis Type: {self.context.analysis_type.title()}"

        # Top border
        top_border = "┏" + "━" * (self.terminal_width - 2) + "┓"
        lines.append(self._colorize(top_border, "cyan"))

        # Title line (centered)
        title_line = f"┃ {title:^{self.terminal_width-4}} ┃"
        lines.append(self._colorize(title_line, "bold"))

        # Subtitle line
        subtitle_line = f"┃ {subtitle:^{self.terminal_width-4}} ┃"
        lines.append(self._colorize(subtitle_line, "dim"))

        # Context info
        if self.context.git_range:
            info_line = f"┃ Git Range: {self.context.git_range:<{self.terminal_width-15}} ┃"
            lines.append(self._colorize(info_line, "cyan"))
        elif self.context.files_analyzed:
            info_line = f"┃ Files: {self.context.files_analyzed:<{self.terminal_width-11}} ┃"
            lines.append(self._colorize(info_line, "cyan"))

        # Bottom border
        bottom_border = "┗" + "━" * (self.terminal_width - 2) + "┛"
        lines.append(self._colorize(bottom_border, "cyan"))

        return lines

    def _create_summary_section(self, summary: Dict[str, Any]) -> List[str]:
        """Create enhanced summary section."""
        lines = []

        lines.append(self._colorize("📊 Summary", "bold"))
        lines.append(self._colorize("─" * 20, "dim"))

        # Main metrics with emojis
        total_issues = summary["total_issues"]
        total_suggestions = summary["total_suggestions"]
        files_with_issues = summary["files_with_issues"]

        status_emoji = self._get_overall_status_emoji(total_issues)
        lines.append(f"{status_emoji} Total Issues: {self._colorize_by_count(total_issues)}")

        if total_suggestions > 0:
            lines.append(f"💡 Suggestions: {self._colorize(str(total_suggestions), 'blue')}")

        lines.append(f"📄 Files with Issues: {self._colorize(str(files_with_issues), 'yellow')}")
        lines.append(f"✅ Clean Files: {self._colorize(str(summary['clean_files']), 'green')}")

        # Severity breakdown with visual indicators
        if summary["severity_breakdown"]:
            lines.append("")
            lines.append("🎯 By Severity:")

            severity_order = ["error", "warning", "suggestion", "info"]
            for severity in severity_order:
                count = summary["severity_breakdown"].get(severity, 0)
                if count > 0:
                    symbol = self._get_severity_symbol(severity)
                    color = self._get_severity_color(severity)
                    count_str = self._colorize(f"{count:>3}", color)
                    severity_name = f"{severity.title():<10}"

                    # Add visual bar
                    bar_length = min(20, count)
                    bar = "█" * bar_length if self.use_unicode else "#" * bar_length
                    bar_colored = self._colorize(bar, color)

                    lines.append(f"  {symbol} {severity_name} {count_str} {bar_colored}")

        # Top issue types
        if summary["most_common_issues"]:
            lines.append("")
            lines.append("🔍 Most Common:")
            for i, issue in enumerate(summary["most_common_issues"][:3], 1):
                issue_type = issue["type"].split(".")[-1]  # Just rule name
                count = issue["count"]
                lines.append(f"  {i}. {issue_type}: {self._colorize(str(count), 'cyan')}")

        return lines

    def _create_issues_section(self, grouped: Dict[str, Any]) -> List[str]:
        """Create detailed issues section."""
        lines = []

        lines.append(self._colorize("🐛 Issues Found", "bold"))
        lines.append(self._colorize("─" * 20, "dim"))

        # Group by file
        issues_by_file = grouped.get("by_file", {})

        for file_path, file_results in issues_by_file.items():
            # File header with issue count
            relative_path = self.format_file_path(file_path, self.context.repository_path)
            issue_count = len(file_results)

            file_header = f"📄 {relative_path} ({issue_count} issues)"
            lines.append(self._colorize(file_header, "bold"))

            # Sort issues by priority
            sorted_issues = sorted(file_results,
                                 key=self.get_issue_priority_score,
                                 reverse=True)

            # Limit issues per file
            display_issues = sorted_issues[:self.config.max_issues_per_file]
            remaining = len(sorted_issues) - len(display_issues)

            for issue in display_issues:
                lines.extend(self._format_single_issue(issue))

            if remaining > 0:
                lines.append(f"  {self._colorize(f'... and {remaining} more issues', 'dim')}")

            lines.append("")  # Space between files

        return lines

    def _format_single_issue(self, result: RuleResult) -> List[str]:
        """Format a single issue with enhanced styling."""
        lines = []

        # Main issue line
        severity_symbol = self._get_severity_symbol(result.severity.value)
        severity_color = self._get_severity_color(result.severity.value)

        # Build issue line
        issue_parts = [
            f"  {severity_symbol}",
            self._colorize(result.severity.value.upper(), severity_color),
            result.message
        ]

        if result.line_number:
            location = f"(line {result.line_number}"
            if result.column:
                location += f", col {result.column}"
            location += ")"
            issue_parts.append(self._colorize(location, "dim"))

        lines.append(" ".join(issue_parts))

        # Rule information
        rule_info = f"{result.checker_name}.{result.rule_name}"
        lines.append(f"    {self._colorize('Rule:', 'dim')} {self._colorize(rule_info, 'blue')}")

        # Code snippet if available
        if hasattr(result, 'content') and result.metadata and result.metadata.get('content'):
            content = result.metadata['content']
            snippet = self._format_code_snippet(content)
            if snippet:
                lines.append(f"    {self._colorize('Code:', 'dim')}")
                for line in snippet.split('\n'):
                    lines.append(f"      {self._colorize(line, 'white')}")

        # Suggestion if available
        if result.suggestion:
            lines.append(f"    {self._colorize('💡 Suggestion:', 'blue')} {result.suggestion}")

        return lines

    def _create_footer(self, summary: Dict[str, Any]) -> List[str]:
        """Create footer with additional info."""
        lines = []

        # Analysis completion message
        total_issues = summary["total_issues"]
        if total_issues == 0:
            message = "🎉 Analysis complete - no issues found!"
            lines.append(self._colorize(message, "green"))
        else:
            message = f"📋 Analysis complete - found {total_issues} issues to review"
            lines.append(self._colorize(message, "yellow"))

        # Timestamp and performance info
        footer_info = []
        if summary.get("timestamp"):
            footer_info.append(f"Generated: {summary['timestamp']}")
        if summary.get("analysis_duration"):
            duration = f"{summary['analysis_duration']:.2f}s"
            footer_info.append(f"Duration: {duration}")

        if footer_info:
            lines.append(self._colorize(" | ".join(footer_info), "dim"))

        return lines

    def _create_title_bar(self, title: str) -> str:
        """Create a title bar with box drawing."""
        if not self.use_unicode:
            return f"=== {title} ==="

        padding = max(0, (self.terminal_width - len(title) - 4) // 2)
        border = "─" * padding
        return f"{border}[ {title} ]{border}"

    def _create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """Create a progress bar."""
        if not self.use_unicode:
            filled = int(width * percentage / 100)
            return "[" + "#" * filled + " " * (width - filled) + "]"

        filled = int(width * percentage / 100)
        return "█" * filled + "░" * (width - filled)

    def _format_code_snippet(self, content: str) -> Optional[str]:
        """Format code snippet for terminal display."""
        if not content or not self.config.show_line_numbers:
            return content

        lines = content.strip().split('\n')
        if len(lines) > 3:  # Limit for terminal
            lines = lines[:3] + ['...']

        # Simple syntax highlighting for common patterns
        formatted_lines = []
        for i, line in enumerate(lines, 1):
            if line == '...':
                formatted_lines.append(self._colorize(line, 'dim'))
            else:
                # Basic highlighting
                highlighted = self._simple_syntax_highlight(line)
                line_num = self._colorize(f"{i:2d}:", 'dim')
                formatted_lines.append(f"{line_num} {highlighted}")

        return '\n'.join(formatted_lines)

    def _simple_syntax_highlight(self, line: str) -> str:
        """Apply simple syntax highlighting."""
        if not self.use_colors:
            return line

        # Keywords (simple patterns)
        keywords = ['def ', 'class ', 'if ', 'else', 'for ', 'while ', 'import ', 'from ']
        for keyword in keywords:
            if keyword in line:
                line = line.replace(keyword, self._colorize(keyword, 'blue'))

        # Strings (basic pattern)
        import re
        line = re.sub(r'(["\'])((?:\\.|(?!\1).)*?)\1',
                     lambda m: self._colorize(m.group(0), 'green'), line)

        # Comments
        if '#' in line:
            parts = line.split('#', 1)
            if len(parts) == 2:
                line = parts[0] + self._colorize('#' + parts[1], 'dim')

        return line

    def _get_overall_status_emoji(self, total_issues: int) -> str:
        """Get emoji representing overall status."""
        if not self.use_unicode:
            return ""

        if total_issues == 0:
            return "✅"
        elif total_issues <= 5:
            return "⚠️"
        else:
            return "❌"

    def _get_status_symbol(self, issue_count: int) -> str:
        """Get status symbol based on issue count."""
        if issue_count == 0:
            return self._colorize("✓", "green")
        elif issue_count <= 5:
            return self._colorize("⚠", "yellow")
        else:
            return self._colorize("✗", "red")

    def _colorize_by_count(self, count: int) -> str:
        """Colorize count based on value."""
        if count == 0:
            return self._colorize(str(count), "green")
        elif count <= 5:
            return self._colorize(str(count), "yellow")
        else:
            return self._colorize(str(count), "red")

    def _get_severity_symbol(self, severity: str) -> str:
        """Get Unicode symbol for severity level."""
        if not self.use_unicode:
            symbols = {"error": "!", "warning": "W", "suggestion": "S", "info": "I"}
            return symbols.get(severity, "•")

        symbols = {
            "error": "❌",
            "warning": "⚠️",
            "suggestion": "💡",
            "info": "ℹ️"
        }
        return symbols.get(severity, "•")

    def _get_severity_color(self, severity: str) -> str:
        """Get color for severity level."""
        colors = {
            "error": "red",
            "warning": "yellow",
            "suggestion": "blue",
            "info": "cyan"
        }
        return colors.get(severity, "white")

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are supported."""
        if not self.use_colors:
            return text

        colors = {
            "red": "\033[31m",
            "green": "\033[32m",
            "yellow": "\033[33m",
            "blue": "\033[34m",
            "magenta": "\033[35m",
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
            'NO_COLOR' not in os.environ and
            'TERM' in os.environ and
            os.environ['TERM'] != 'dumb'
        )

    def _supports_unicode(self) -> bool:
        """Check if terminal supports Unicode."""
        try:
            encoding = getattr(sys.stdout, 'encoding', '') or ''
            return encoding.lower().startswith('utf')
        except (AttributeError, TypeError):
            return False

    def _get_terminal_width(self) -> int:
        """Get terminal width, with fallback."""
        try:
            return shutil.get_terminal_size().columns
        except (AttributeError, OSError):
            return 80  # Fallback width