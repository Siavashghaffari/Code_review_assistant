"""
Markdown Formatter

Formats analysis results as Markdown for documentation or reports.
"""

from datetime import datetime
from typing import Dict, List, Any

from .base_formatter import BaseFormatter


class MarkdownFormatter(BaseFormatter):
    """Formatter for Markdown output."""

    def format(self, results: Dict[str, Any]) -> str:
        """Format results as Markdown."""
        sections = []

        # Title and metadata
        sections.append(self._format_header(results))

        # Table of contents
        sections.append(self._format_toc(results))

        # Summary
        sections.append(self._format_summary(results))

        # Issues
        issues = results.get("issues", [])
        if issues:
            sections.append(self._format_issues(issues))

        # Suggestions
        suggestions = results.get("suggestions", [])
        if suggestions:
            sections.append(self._format_suggestions(suggestions))

        # Footer
        sections.append(self._format_footer())

        return "\n\n".join(sections)

    def _format_header(self, results: Dict[str, Any]) -> str:
        """Format the header section."""
        lines = [
            "# Code Review Analysis Report",
            ""
        ]

        # Metadata table
        analysis_type = results.get("analysis_type", "unknown")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines.extend([
            "## Analysis Information",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| Analysis Type | {analysis_type.replace('_', ' ').title()} |",
            f"| Generated At | {timestamp} |"
        ])

        if analysis_type == "git_diff":
            git_range = results.get("git_range", "")
            lines.append(f"| Git Range | `{git_range}` |")
        elif analysis_type == "files":
            files_analyzed = results.get("files_analyzed", 0)
            files_skipped = results.get("files_skipped", 0)
            lines.extend([
                f"| Files Analyzed | {files_analyzed} |",
                f"| Files Skipped | {files_skipped} |"
            ])

        return "\n".join(lines)

    def _format_toc(self, results: Dict[str, Any]) -> str:
        """Format table of contents."""
        lines = [
            "## Table of Contents",
            "",
            "- [Summary](#summary)"
        ]

        if results.get("issues"):
            lines.append("- [Issues](#issues)")

        if results.get("suggestions"):
            lines.append("- [Suggestions](#suggestions)")

        return "\n".join(lines)

    def _format_summary(self, results: Dict[str, Any]) -> str:
        """Format the summary section."""
        lines = [
            "## Summary",
            ""
        ]

        summary = results.get("summary", {})
        total_issues = summary.get("total_issues", 0)
        total_suggestions = summary.get("total_suggestions", 0)

        # Overview
        lines.extend([
            f"- **Total Issues:** {total_issues}",
            f"- **Total Suggestions:** {total_suggestions}"
        ])

        files_with_issues = summary.get("files_with_issues", 0)
        if files_with_issues > 0:
            lines.append(f"- **Files with Issues:** {files_with_issues}")

        # Severity breakdown
        severity_breakdown = summary.get("severity_breakdown", {})
        if severity_breakdown:
            lines.extend([
                "",
                "### Issues by Severity",
                ""
            ])

            for severity, count in sorted(severity_breakdown.items()):
                emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")
                lines.append(f"- {emoji} **{severity.title()}:** {count}")

        # Most common issues
        most_common = summary.get("most_common_issues", [])
        if most_common:
            lines.extend([
                "",
                "### Most Common Issues",
                ""
            ])

            for i, issue in enumerate(most_common[:5], 1):
                issue_type = issue.get("type", "unknown").replace("_", " ").title()
                count = issue.get("count", 0)
                lines.append(f"{i}. **{issue_type}** - {count} occurrences")

        return "\n".join(lines)

    def _format_issues(self, issues: List[Dict[str, Any]]) -> str:
        """Format the issues section."""
        lines = [
            "## Issues",
            ""
        ]

        if not issues:
            lines.append("No issues found.")
            return "\n".join(lines)

        # Group issues by file
        issues_by_file = {}
        for issue in issues:
            file_path = issue.get("file", "unknown")
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)

        # Sort files by number of issues (descending)
        sorted_files = sorted(
            issues_by_file.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        for file_path, file_issues in sorted_files:
            lines.extend([
                f"### 📄 `{file_path}`",
                "",
                f"**{len(file_issues)} issue(s) found**",
                ""
            ])

            # Sort issues by line number if available
            sorted_issues = sorted(
                file_issues,
                key=lambda x: (x.get("line", 0), x.get("severity", "info"))
            )

            for i, issue in enumerate(sorted_issues, 1):
                lines.extend(self._format_single_issue(issue, i))

        return "\n".join(lines)

    def _format_single_issue(self, issue: Dict[str, Any], index: int) -> List[str]:
        """Format a single issue."""
        lines = []

        severity = issue.get("severity", "info")
        issue_type = issue.get("type", "unknown")
        message = issue.get("message", "No message")
        line_number = issue.get("line")

        # Severity emoji
        severity_emoji = {
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }.get(severity, "•")

        # Issue header
        header = f"{index}. {severity_emoji} **{severity.upper()}**: {message}"
        if line_number:
            header += f" *(line {line_number})*"

        lines.append(header)

        # Issue details
        details = []
        details.append(f"**Type:** `{issue_type}`")

        if line_number:
            details.append(f"**Line:** {line_number}")

        lines.extend([
            "",
            "   " + " | ".join(details)
        ])

        # Code snippet
        content = issue.get("content")
        if content:
            lines.extend([
                "",
                "   **Code:**",
                "   ```",
                f"   {content}",
                "   ```"
            ])

        lines.append("")  # Empty line after each issue

        return lines

    def _format_suggestions(self, suggestions: List[Dict[str, Any]]) -> str:
        """Format the suggestions section."""
        lines = [
            "## Suggestions",
            ""
        ]

        if not suggestions:
            lines.append("No suggestions available.")
            return "\n".join(lines)

        # Group suggestions by file
        suggestions_by_file = {}
        for suggestion in suggestions:
            file_path = suggestion.get("file", "unknown")
            if file_path not in suggestions_by_file:
                suggestions_by_file[file_path] = []
            suggestions_by_file[file_path].append(suggestion)

        for file_path, file_suggestions in suggestions_by_file.items():
            lines.extend([
                f"### 💡 `{file_path}`",
                ""
            ])

            for i, suggestion in enumerate(file_suggestions, 1):
                message = suggestion.get("message", "No message")
                line_number = suggestion.get("line")

                suggestion_text = f"{i}. {message}"
                if line_number:
                    suggestion_text += f" *(line {line_number})*"

                lines.append(suggestion_text)

                # Code snippet
                content = suggestion.get("content")
                if content:
                    lines.extend([
                        "",
                        "   **Current code:**",
                        "   ```",
                        f"   {content}",
                        "   ```",
                        ""
                    ])

        return "\n".join(lines)

    def _format_footer(self) -> str:
        """Format the footer section."""
        return "---\n\n*Report generated by Code Review Automation Tool*"