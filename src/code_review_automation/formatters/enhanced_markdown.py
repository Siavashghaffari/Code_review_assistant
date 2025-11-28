"""
Enhanced Markdown Formatter

Advanced markdown formatter for GitHub/GitLab comments, PR reviews,
and documentation with platform-specific features.
"""

import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

from .base import BaseFormatter, FormatterConfig, OutputContext, MultiFormatSupport
from ..config.rule_engine import RuleResult


class MarkdownFormatter(BaseFormatter, MultiFormatSupport):
    """Enhanced markdown formatter for various platforms."""

    def __init__(self, config: FormatterConfig = None, context: OutputContext = None):
        super().__init__(config, context)

        # Add platform-specific sub-formats
        self.add_sub_format("github")
        self.add_sub_format("gitlab")
        self.add_sub_format("generic")
        self.add_sub_format("pr_comment")
        self.add_sub_format("issue_report")

    def get_format_type(self) -> str:
        return "markdown"

    def supports_feature(self, feature: str) -> bool:
        features = {
            "tables": True,
            "code_blocks": True,
            "links": True,
            "collapsible": True,
            "checkboxes": True,
            "emojis": True,
            "badges": True
        }
        return features.get(feature, False)

    def format(self, results: List[RuleResult], sub_format: str = "github", **kwargs) -> Any:
        """Format results as markdown for specific platforms."""
        if sub_format == "github":
            return self._format_github(results, **kwargs)
        elif sub_format == "gitlab":
            return self._format_gitlab(results, **kwargs)
        elif sub_format == "pr_comment":
            return self._format_pr_comment(results, **kwargs)
        elif sub_format == "issue_report":
            return self._format_issue_report(results, **kwargs)
        else:
            return self._format_generic(results, **kwargs)

    def _format_github(self, results: List[RuleResult], **kwargs) -> Any:
        """Format for GitHub PR comments and reviews."""
        filtered_results = self.filter_results(results)
        summary = self.create_summary(filtered_results)
        grouped = self.group_results(filtered_results)

        sections = []

        # Header with status badge
        sections.append(self._create_github_header(summary))

        # Executive summary
        if kwargs.get('include_summary', True):
            sections.append(self._create_executive_summary(summary))

        # Issues section
        if filtered_results:
            sections.append(self._create_github_issues_section(grouped, summary))

        # Suggestions section
        suggestions = [r for r in filtered_results if r.suggestion]
        if suggestions:
            sections.append(self._create_suggestions_section(suggestions))

        # Footer with metadata
        if kwargs.get('include_metadata', True):
            sections.append(self._create_github_footer())

        content = "\n\n".join(sections)
        return self.create_formatted_output(content)

    def _format_gitlab(self, results: List[RuleResult], **kwargs) -> Any:
        """Format for GitLab MR comments and reviews."""
        filtered_results = self.filter_results(results)
        summary = self.create_summary(filtered_results)
        grouped = self.group_results(filtered_results)

        sections = []

        # Header with GitLab-specific formatting
        sections.append(self._create_gitlab_header(summary))

        # Summary table
        sections.append(self._create_gitlab_summary_table(summary))

        # Issues by severity
        if filtered_results:
            sections.append(self._create_gitlab_issues_section(grouped))

        # Footer
        sections.append(self._create_gitlab_footer())

        content = "\n\n".join(sections)
        return self.create_formatted_output(content)

    def _format_pr_comment(self, results: List[RuleResult], **kwargs) -> Any:
        """Format as a concise PR comment."""
        if not results:
            return self.create_formatted_output(
                "✅ **No issues found!** Great job on the clean code! 🎉"
            )

        summary = self.create_summary(results)
        lines = []

        # Status indicator
        total_issues = summary["total_issues"]
        if total_issues <= 3:
            status = f"⚠️ **Found {total_issues} minor issues**"
        elif total_issues <= 10:
            status = f"⚠️ **Found {total_issues} issues that need attention**"
        else:
            status = f"❌ **Found {total_issues} issues - please review**"

        lines.append(status)
        lines.append("")

        # Quick breakdown
        if summary["severity_breakdown"]:
            breakdown_parts = []
            for severity, count in summary["severity_breakdown"].items():
                if count > 0:
                    emoji = {"error": "🔴", "warning": "🟡", "suggestion": "🔵", "info": "⚪"}.get(severity, "⚪")
                    breakdown_parts.append(f"{emoji} {count} {severity}")

            if breakdown_parts:
                lines.append("**Issues breakdown:** " + " | ".join(breakdown_parts))
                lines.append("")

        # Top 3 most critical issues
        critical_issues = sorted(results, key=self.get_issue_priority_score, reverse=True)[:3]
        if critical_issues:
            lines.append("**Top issues to address:**")
            for i, issue in enumerate(critical_issues, 1):
                file_path = self.format_file_path(issue.file_path, self.context.repository_path)
                location = f" (line {issue.line_number})" if issue.line_number else ""
                lines.append(f"{i}. {issue.message} - `{file_path}`{location}")

        # Call to action
        lines.append("")
        if total_issues <= 5:
            lines.append("💡 *These are mostly minor issues that can be quickly addressed.*")
        else:
            lines.append("🔧 *Please review and address these issues before merging.*")

        content = "\n".join(lines)
        return self.create_formatted_output(content)

    def _format_issue_report(self, results: List[RuleResult], **kwargs) -> Any:
        """Format as a detailed issue report."""
        filtered_results = self.filter_results(results)
        summary = self.create_summary(filtered_results)

        sections = []

        # Title and metadata
        sections.append(f"# Code Review Report")
        sections.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if self.context.repository_url:
            sections.append(f"**Repository:** {self.context.repository_url}")

        if self.context.git_range:
            sections.append(f"**Git Range:** `{self.context.git_range}`")

        # Executive summary
        sections.append("## Executive Summary")
        sections.append(self._create_detailed_summary(summary))

        # Issues by category
        if filtered_results:
            sections.append("## Issues by Category")
            sections.append(self._create_categorized_issues(filtered_results))

        # Action items
        sections.append("## Action Items")
        sections.append(self._create_action_items(filtered_results, summary))

        content = "\n\n".join(sections)
        return self.create_formatted_output(content)

    def _create_github_header(self, summary: Dict[str, Any]) -> str:
        """Create GitHub-style header with badges."""
        total_issues = summary["total_issues"]

        # Status badge
        if total_issues == 0:
            status_badge = "![Status](https://img.shields.io/badge/Code%20Review-✅%20Clean-brightgreen)"
        elif total_issues <= 5:
            status_badge = "![Status](https://img.shields.io/badge/Code%20Review-⚠️%20Minor%20Issues-yellow)"
        else:
            status_badge = "![Status](https://img.shields.io/badge/Code%20Review-❌%20Issues%20Found-red)"

        lines = [
            "# 🔍 Code Review Analysis",
            "",
            status_badge
        ]

        # Additional context badges
        if self.context.files_analyzed:
            files_badge = f"![Files](https://img.shields.io/badge/Files%20Analyzed-{self.context.files_analyzed}-blue)"
            lines.append(files_badge)

        if total_issues > 0:
            issues_badge = f"![Issues](https://img.shields.io/badge/Issues%20Found-{total_issues}-orange)"
            lines.append(issues_badge)

        return "\n".join(lines)

    def _create_executive_summary(self, summary: Dict[str, Any]) -> str:
        """Create executive summary section."""
        lines = ["## 📊 Executive Summary"]

        total_issues = summary["total_issues"]
        files_with_issues = summary["files_with_issues"]
        clean_files = summary["clean_files"]

        if total_issues == 0:
            lines.append("🎉 **Excellent!** No issues found in your code. Everything looks clean and follows best practices.")
            return "\n".join(lines)

        # Summary paragraph
        if total_issues <= 3:
            summary_text = f"Found **{total_issues}** minor issues across **{files_with_issues}** files. These are mostly style or best practice recommendations."
        elif total_issues <= 10:
            summary_text = f"Found **{total_issues}** issues across **{files_with_issues}** files that should be addressed before merging."
        else:
            summary_text = f"Found **{total_issues}** issues across **{files_with_issues}** files. Please review and address these concerns."

        lines.append(summary_text)

        # Quick stats table
        lines.append("")
        lines.append("| Metric | Count |")
        lines.append("|--------|--------|")
        lines.append(f"| 📄 Files Analyzed | {summary['files_analyzed']} |")
        lines.append(f"| ✅ Clean Files | {clean_files} |")
        lines.append(f"| ⚠️ Files with Issues | {files_with_issues} |")
        lines.append(f"| 🐛 Total Issues | {total_issues} |")

        # Severity breakdown
        if summary["severity_breakdown"]:
            lines.append("")
            lines.append("**Severity Breakdown:**")
            for severity, count in summary["severity_breakdown"].items():
                if count > 0:
                    emoji = {"error": "🔴", "warning": "🟡", "suggestion": "🔵", "info": "⚪"}.get(severity, "⚪")
                    lines.append(f"- {emoji} **{severity.title()}:** {count} issues")

        return "\n".join(lines)

    def _create_github_issues_section(self, grouped: Dict[str, Any], summary: Dict[str, Any]) -> str:
        """Create GitHub-style issues section with collapsible details."""
        lines = ["## 🐛 Issues Found"]

        issues_by_file = grouped.get("by_file", {})
        total_files = len(issues_by_file)

        if total_files > 5:
            # Use collapsible sections for many files
            lines.append(f"<details>")
            lines.append(f"<summary><strong>Issues in {total_files} files (click to expand)</strong></summary>")
            lines.append("")

        for file_path, file_results in issues_by_file.items():
            lines.extend(self._create_file_issues_section(file_path, file_results))

        if total_files > 5:
            lines.append("</details>")

        return "\n".join(lines)

    def _create_file_issues_section(self, file_path: str, results: List[RuleResult]) -> List[str]:
        """Create issues section for a single file."""
        lines = []
        relative_path = self.format_file_path(file_path, self.context.repository_path)
        issue_count = len(results)

        # File header
        lines.append(f"### 📄 `{relative_path}` ({issue_count} issues)")
        lines.append("")

        # Sort by priority
        sorted_results = sorted(results, key=self.get_issue_priority_score, reverse=True)

        for result in sorted_results:
            lines.extend(self._create_markdown_issue_block(result))

        return lines

    def _create_markdown_issue_block(self, result: RuleResult) -> List[str]:
        """Create a markdown block for a single issue."""
        lines = []

        # Issue header with severity badge
        severity_emoji = {"error": "🔴", "warning": "🟡", "suggestion": "🔵", "info": "⚪"}.get(
            result.severity.value, "⚪"
        )

        issue_header = f"{severity_emoji} **{result.severity.value.title()}:** {result.message}"
        if result.line_number:
            issue_header += f" (Line {result.line_number})"

        lines.append(issue_header)

        # Rule information
        rule_info = f"`{result.checker_name}.{result.rule_name}`"
        lines.append(f"*Rule:* {rule_info}")

        # Code block if content available
        if hasattr(result, 'content') and result.metadata and result.metadata.get('content'):
            content = result.metadata['content']
            # Try to determine language from file extension
            file_ext = Path(result.file_path).suffix.lstrip('.')
            language = self._get_language_from_extension(file_ext)

            lines.append("")
            lines.append("```" + language)
            lines.append(content)
            lines.append("```")

        # Suggestion
        if result.suggestion:
            lines.append("")
            lines.append(f"💡 **Suggestion:** {result.suggestion}")

        lines.append("")  # Empty line after each issue
        return lines

    def _create_suggestions_section(self, suggestions: List[RuleResult]) -> str:
        """Create suggestions section."""
        lines = ["## 💡 Suggestions"]
        lines.append("")

        for suggestion in suggestions:
            file_path = self.format_file_path(suggestion.file_path, self.context.repository_path)
            location = f" (line {suggestion.line_number})" if suggestion.line_number else ""

            lines.append(f"- **`{file_path}`{location}**: {suggestion.suggestion}")

        return "\n".join(lines)

    def _create_github_footer(self) -> str:
        """Create GitHub-style footer."""
        lines = ["---"]
        lines.append(f"*Generated by Code Review Assistant v{self.context.analyzer_version}*")

        if self.context.execution_time:
            duration = f"{self.context.execution_time:.2f}s"
            lines.append(f"*Analysis completed in {duration}*")

        # Add helpful links or actions
        lines.append("")
        lines.append("**Next Steps:**")
        lines.append("1. 🔍 Review the issues above")
        lines.append("2. 🔧 Make necessary fixes")
        lines.append("3. ✅ Re-run analysis to verify fixes")

        return "\n".join(lines)

    def _create_gitlab_header(self, summary: Dict[str, Any]) -> str:
        """Create GitLab-style header."""
        total_issues = summary["total_issues"]

        # GitLab uses different emoji style
        if total_issues == 0:
            status = ":white_check_mark: **Code Review: Clean**"
        elif total_issues <= 5:
            status = ":warning: **Code Review: Minor Issues**"
        else:
            status = ":x: **Code Review: Issues Found**"

        return f"## :mag: Code Review Analysis\n\n{status}"

    def _create_gitlab_summary_table(self, summary: Dict[str, Any]) -> str:
        """Create GitLab-style summary table."""
        lines = ["| Metric | Value |"]
        lines.append("|--------|-------|")
        lines.append(f"| Files Analyzed | {summary['files_analyzed']} |")
        lines.append(f"| Issues Found | {summary['total_issues']} |")
        lines.append(f"| Clean Files | {summary['clean_files']} |")

        if summary["severity_breakdown"]:
            for severity, count in summary["severity_breakdown"].items():
                if count > 0:
                    emoji = {"error": ":red_circle:", "warning": ":yellow_circle:",
                            "suggestion": ":blue_circle:", "info": ":white_circle:"}.get(severity, ":white_circle:")
                    lines.append(f"| {emoji} {severity.title()} | {count} |")

        return "\n".join(lines)

    def _create_gitlab_issues_section(self, grouped: Dict[str, Any]) -> str:
        """Create GitLab-style issues section."""
        lines = ["## :bug: Issues by Severity"]

        issues_by_severity = grouped.get("by_severity", {})

        for severity in ["error", "warning", "suggestion", "info"]:
            severity_results = issues_by_severity.get(severity, [])
            if not severity_results:
                continue

            emoji = {"error": ":red_circle:", "warning": ":yellow_circle:",
                    "suggestion": ":blue_circle:", "info": ":white_circle:"}.get(severity)

            lines.append(f"### {emoji} {severity.title()} ({len(severity_results)} issues)")
            lines.append("")

            for result in severity_results:
                file_path = self.format_file_path(result.file_path, self.context.repository_path)
                location = f":line_number: {result.line_number}" if result.line_number else ""

                lines.append(f"- **`{file_path}`** {location}")
                lines.append(f"  {result.message}")

                if result.suggestion:
                    lines.append(f"  :bulb: {result.suggestion}")

                lines.append("")

        return "\n".join(lines)

    def _create_gitlab_footer(self) -> str:
        """Create GitLab-style footer."""
        lines = ["---"]
        lines.append(f"*:robot: Generated by Code Review Assistant*")
        return "\n".join(lines)

    def _create_detailed_summary(self, summary: Dict[str, Any]) -> str:
        """Create detailed summary for reports."""
        lines = []
        total_issues = summary["total_issues"]

        if total_issues == 0:
            lines.append("✅ **All Clear!** No issues were found during the analysis.")
        else:
            lines.append(f"📋 **Analysis Results:** Found {total_issues} issues that require attention.")

        # Detailed metrics
        lines.append("")
        lines.append(f"- **Files Analyzed:** {summary['files_analyzed']}")
        lines.append(f"- **Files with Issues:** {summary['files_with_issues']}")
        lines.append(f"- **Clean Files:** {summary['clean_files']}")

        if summary["analysis_duration"]:
            duration = f"{summary['analysis_duration']:.2f} seconds"
            lines.append(f"- **Analysis Time:** {duration}")

        return "\n".join(lines)

    def _create_categorized_issues(self, results: List[RuleResult]) -> str:
        """Create issues categorized by checker type."""
        lines = []

        # Group by checker
        by_checker = {}
        for result in results:
            checker = result.checker_name
            if checker not in by_checker:
                by_checker[checker] = []
            by_checker[checker].append(result)

        for checker_name, checker_results in sorted(by_checker.items()):
            lines.append(f"### {checker_name.title()} Issues ({len(checker_results)})")
            lines.append("")

            # Create table
            lines.append("| File | Line | Issue | Severity |")
            lines.append("|------|------|-------|----------|")

            for result in sorted(checker_results, key=lambda r: (str(r.file_path), r.line_number or 0)):
                file_path = self.format_file_path(result.file_path, self.context.repository_path)
                line_num = str(result.line_number) if result.line_number else "-"
                message = self._truncate_text(result.message, 50)
                severity = result.severity.value

                lines.append(f"| `{file_path}` | {line_num} | {message} | {severity} |")

            lines.append("")

        return "\n".join(lines)

    def _create_action_items(self, results: List[RuleResult], summary: Dict[str, Any]) -> str:
        """Create actionable checklist."""
        lines = []

        if not results:
            lines.append("- [x] No issues found - code is ready for review!")
            return "\n".join(lines)

        # Priority-based action items
        critical_issues = [r for r in results if r.severity.value == "error"]
        warnings = [r for r in results if r.severity.value == "warning"]

        if critical_issues:
            lines.append("### 🔴 Critical Issues (Must Fix)")
            for issue in critical_issues[:5]:  # Limit to top 5
                file_path = self.format_file_path(issue.file_path, self.context.repository_path)
                lines.append(f"- [ ] Fix {issue.rule_name} in `{file_path}`")

        if warnings:
            lines.append("### 🟡 Important Issues (Should Fix)")
            for issue in warnings[:5]:  # Limit to top 5
                file_path = self.format_file_path(issue.file_path, self.context.repository_path)
                lines.append(f"- [ ] Address {issue.rule_name} in `{file_path}`")

        # Overall tasks
        lines.append("### 📋 General Tasks")
        lines.append("- [ ] Review all security-related issues")
        lines.append("- [ ] Run tests after fixes")
        lines.append("- [ ] Re-run code analysis")

        return "\n".join(lines)

    def _get_language_from_extension(self, ext: str) -> str:
        """Get language identifier for code blocks from file extension."""
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "jsx": "jsx",
            "tsx": "tsx",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "cs": "csharp",
            "go": "go",
            "rs": "rust",
            "php": "php",
            "rb": "ruby",
            "swift": "swift",
            "kt": "kotlin",
            "scala": "scala",
            "sh": "bash",
            "sql": "sql",
            "html": "html",
            "css": "css",
            "xml": "xml",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "md": "markdown"
        }
        return lang_map.get(ext.lower(), "")

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to maximum length."""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."