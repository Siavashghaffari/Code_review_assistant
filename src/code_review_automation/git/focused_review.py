"""
Focused Review System

Analyzes only the modified lines of code from git diffs to provide
targeted feedback on changes without reviewing unchanged code.
"""

from pathlib import Path
from typing import Dict, List, Any, Set, Optional, Tuple
from dataclasses import dataclass

from .diff_parser import GitDiffParser, GitDiffResult, FileDiff, ChangeType
from ..analyzers.core_analyzer import CoreAnalyzer
from ..utils.logger import get_logger


@dataclass
class FocusedIssue:
    """Issue found in changed code with git context."""
    file_path: str
    line_number: int
    old_line_number: Optional[int]
    change_type: ChangeType
    issue_type: str
    severity: str
    message: str
    suggestion: str
    explanation: Optional[str] = None
    code_snippet: Optional[str] = None


@dataclass
class FocusedReviewResult:
    """Result of focused review on git changes."""
    diff_summary: Dict[str, Any]
    issues: List[FocusedIssue]
    suggestions: List[Dict[str, Any]]
    files_reviewed: int
    lines_reviewed: int
    commit_message_suggestions: List[str]


class FocusedReviewAnalyzer:
    """Analyzer that focuses only on changed lines in git diffs."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)
        self.diff_parser = GitDiffParser()
        self.core_analyzer = CoreAnalyzer(config)

    def analyze_diff(self, diff_text: str, repo_path: Optional[Path] = None) -> FocusedReviewResult:
        """
        Analyze git diff focusing only on changed lines.

        Args:
            diff_text: Raw git diff output
            repo_path: Path to git repository

        Returns:
            FocusedReviewResult with targeted analysis
        """
        self.logger.info("Starting focused review of git diff")

        # Parse the diff
        diff_result = self.diff_parser.parse_diff(diff_text)

        # Analyze each modified file
        all_issues = []
        all_suggestions = []
        total_lines_reviewed = 0

        for file_diff in diff_result.files:
            if file_diff.is_binary:
                self.logger.debug(f"Skipping binary file: {file_diff.new_path}")
                continue

            file_issues, file_suggestions, lines_count = self._analyze_file_changes(
                file_diff, repo_path
            )

            all_issues.extend(file_issues)
            all_suggestions.extend(file_suggestions)
            total_lines_reviewed += lines_count

        # Generate commit message suggestions
        commit_suggestions = self._generate_commit_message_suggestions(diff_result)

        # Create summary
        diff_summary = {
            "total_files": len(diff_result.files),
            "modified_files": len([f for f in diff_result.files if not f.is_binary]),
            "binary_files": len([f for f in diff_result.files if f.is_binary]),
            "total_added": diff_result.total_added,
            "total_removed": diff_result.total_removed,
            "net_change": diff_result.total_added - diff_result.total_removed
        }

        return FocusedReviewResult(
            diff_summary=diff_summary,
            issues=all_issues,
            suggestions=all_suggestions,
            files_reviewed=len([f for f in diff_result.files if not f.is_binary]),
            lines_reviewed=total_lines_reviewed,
            commit_message_suggestions=commit_suggestions
        )

    def _analyze_file_changes(self,
                            file_diff: FileDiff,
                            repo_path: Optional[Path]) -> Tuple[List[FocusedIssue], List[Dict[str, Any]], int]:
        """Analyze changes in a single file."""
        issues = []
        suggestions = []
        lines_reviewed = 0

        if file_diff.change_type == ChangeType.REMOVED:
            # File was deleted, no need to analyze
            return issues, suggestions, 0

        # Get the current file content
        file_content = self._get_file_content(file_diff.new_path, repo_path)
        if not file_content:
            self.logger.warning(f"Could not read file content: {file_diff.new_path}")
            return issues, suggestions, 0

        # Get changed lines
        changed_lines = self.diff_parser.get_changed_lines_for_file(file_diff)
        added_lines = changed_lines['added']

        if not added_lines:
            return issues, suggestions, 0

        # Create focused content with only changed lines and context
        focused_content = self._create_focused_content(file_content, added_lines, context_lines=3)

        # Analyze the focused content
        try:
            analysis_result = self.core_analyzer.analyze_file(Path(file_diff.new_path))

            # Filter results to only include issues on changed lines
            for issue in analysis_result.issues:
                issue_line = issue.get('line', 0)
                if issue_line in added_lines:
                    # Find the corresponding diff line info
                    change_type, old_line = self._find_line_context(file_diff, issue_line)

                    focused_issue = FocusedIssue(
                        file_path=file_diff.new_path,
                        line_number=issue_line,
                        old_line_number=old_line,
                        change_type=change_type,
                        issue_type=issue.get('type', 'unknown'),
                        severity=issue.get('severity', 'info'),
                        message=issue.get('message', ''),
                        suggestion=issue.get('suggestion', ''),
                        explanation=issue.get('explanation'),
                        code_snippet=self._get_code_snippet(file_content, issue_line)
                    )
                    issues.append(focused_issue)

            # Filter suggestions for changed lines
            for suggestion in analysis_result.suggestions:
                suggestion_line = suggestion.get('line', 0)
                if suggestion_line in added_lines:
                    suggestion['file'] = file_diff.new_path
                    suggestion['change_context'] = 'newly_added'
                    suggestions.append(suggestion)

            lines_reviewed = len(added_lines)

        except Exception as e:
            self.logger.error(f"Error analyzing file {file_diff.new_path}: {e}")

        return issues, suggestions, lines_reviewed

    def _get_file_content(self, file_path: str, repo_path: Optional[Path]) -> Optional[str]:
        """Get the current content of a file."""
        try:
            if repo_path:
                full_path = repo_path / file_path
            else:
                full_path = Path(file_path)

            if full_path.exists():
                return full_path.read_text(encoding='utf-8')
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")

        return None

    def _create_focused_content(self, content: str, changed_lines: Set[int], context_lines: int = 3) -> str:
        """Create focused content with only changed lines and context."""
        lines = content.split('\n')
        focused_lines = []

        # Sort changed lines
        sorted_lines = sorted(changed_lines)

        # Group consecutive lines to avoid duplicate context
        line_groups = []
        current_group = []

        for line_num in sorted_lines:
            if not current_group or line_num <= current_group[-1] + context_lines * 2 + 1:
                current_group.append(line_num)
            else:
                line_groups.append(current_group)
                current_group = [line_num]

        if current_group:
            line_groups.append(current_group)

        # Extract lines for each group with context
        for group in line_groups:
            start_line = max(1, group[0] - context_lines)
            end_line = min(len(lines), group[-1] + context_lines)

            for line_num in range(start_line, end_line + 1):
                if line_num <= len(lines):
                    focused_lines.append(f"{line_num:4d}: {lines[line_num - 1]}")

            focused_lines.append("---")  # Separator between groups

        return '\n'.join(focused_lines)

    def _find_line_context(self, file_diff: FileDiff, line_number: int) -> Tuple[ChangeType, Optional[int]]:
        """Find the change context for a specific line number."""
        for hunk in file_diff.hunks:
            for diff_line in hunk.lines:
                if diff_line.new_line_number == line_number:
                    return diff_line.change_type, diff_line.old_line_number

        return ChangeType.MODIFIED, None

    def _get_code_snippet(self, content: str, line_number: int, context: int = 2) -> str:
        """Get a code snippet around the specified line."""
        lines = content.split('\n')
        start = max(0, line_number - context - 1)
        end = min(len(lines), line_number + context)

        snippet_lines = []
        for i in range(start, end):
            marker = "→ " if i == line_number - 1 else "  "
            snippet_lines.append(f"{marker}{i+1:3d}: {lines[i]}")

        return '\n'.join(snippet_lines)

    def _generate_commit_message_suggestions(self, diff_result: GitDiffResult) -> List[str]:
        """Generate commit message suggestions based on the changes."""
        suggestions = []

        # Analyze the types of changes
        added_files = [f for f in diff_result.files if f.change_type == ChangeType.ADDED]
        removed_files = [f for f in diff_result.files if f.change_type == ChangeType.REMOVED]
        modified_files = [f for f in diff_result.files if f.change_type == ChangeType.MODIFIED]
        renamed_files = [f for f in diff_result.files if f.change_type == ChangeType.RENAMED]

        # Generate suggestions based on change patterns
        if added_files and not modified_files and not removed_files:
            if len(added_files) == 1:
                suggestions.append(f"Add {Path(added_files[0].new_path).name}")
            else:
                suggestions.append(f"Add {len(added_files)} new files")

        elif removed_files and not modified_files and not added_files:
            if len(removed_files) == 1:
                suggestions.append(f"Remove {Path(removed_files[0].old_path).name}")
            else:
                suggestions.append(f"Remove {len(removed_files)} files")

        elif renamed_files and not added_files and not removed_files:
            if len(renamed_files) == 1:
                old_name = Path(renamed_files[0].old_path).name
                new_name = Path(renamed_files[0].new_path).name
                suggestions.append(f"Rename {old_name} to {new_name}")
            else:
                suggestions.append(f"Rename {len(renamed_files)} files")

        elif modified_files:
            # Analyze the nature of modifications
            if len(modified_files) == 1:
                file_name = Path(modified_files[0].new_path).name
                suggestions.append(f"Update {file_name}")

                # More specific suggestions based on file type
                if file_name.endswith('.py'):
                    suggestions.append(f"Improve Python code in {file_name}")
                elif file_name.endswith(('.js', '.ts')):
                    suggestions.append(f"Enhance JavaScript functionality in {file_name}")
                elif file_name.endswith('.md'):
                    suggestions.append(f"Update documentation in {file_name}")
            else:
                suggestions.append(f"Update {len(modified_files)} files")

        # Generic suggestions based on change size
        total_changes = diff_result.total_added + diff_result.total_removed

        if total_changes < 10:
            suggestions.append("Minor code improvements")
        elif total_changes < 50:
            suggestions.append("Code refactoring and improvements")
        elif total_changes < 200:
            suggestions.append("Significant code changes")
        else:
            suggestions.append("Major code restructuring")

        # Add conventional commit format suggestions
        conventional_suggestions = []
        for suggestion in suggestions[:3]:  # Limit to first 3
            conventional_suggestions.extend([
                f"feat: {suggestion.lower()}",
                f"fix: {suggestion.lower()}",
                f"refactor: {suggestion.lower()}",
                f"docs: {suggestion.lower()}" if any(f.new_path.endswith('.md') for f in diff_result.files) else None
            ])

        # Remove None values and duplicates
        conventional_suggestions = list(set(filter(None, conventional_suggestions)))

        return suggestions + conventional_suggestions[:5]  # Limit total suggestions

    def analyze_pull_request_diff(self, base_ref: str, head_ref: str, repo_path: Path) -> FocusedReviewResult:
        """Analyze diff between two git references (e.g., for pull requests)."""
        from .diff_parser import GitCommands

        git_commands = GitCommands(repo_path)

        try:
            # Get the diff between base and head
            diff_text = git_commands.get_diff(base_ref, head_ref)

            if not diff_text.strip():
                self.logger.info("No differences found between references")
                return FocusedReviewResult(
                    diff_summary={"total_files": 0, "modified_files": 0, "binary_files": 0,
                                "total_added": 0, "total_removed": 0, "net_change": 0},
                    issues=[],
                    suggestions=[],
                    files_reviewed=0,
                    lines_reviewed=0,
                    commit_message_suggestions=[]
                )

            # Analyze the diff
            return self.analyze_diff(diff_text, repo_path)

        except Exception as e:
            self.logger.error(f"Error analyzing pull request diff: {e}")
            raise

    def get_review_summary(self, result: FocusedReviewResult) -> Dict[str, Any]:
        """Generate a summary of the focused review results."""
        # Group issues by severity
        severity_counts = {}
        for issue in result.issues:
            severity = issue.severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Group issues by type
        type_counts = {}
        for issue in result.issues:
            issue_type = issue.issue_type
            type_counts[issue_type] = type_counts.get(issue_type, 0) + 1

        return {
            "files_reviewed": result.files_reviewed,
            "lines_reviewed": result.lines_reviewed,
            "total_issues": len(result.issues),
            "total_suggestions": len(result.suggestions),
            "severity_breakdown": severity_counts,
            "issue_type_breakdown": type_counts,
            "diff_stats": result.diff_summary,
            "review_focus": "changed_lines_only",
            "commit_suggestions_count": len(result.commit_message_suggestions)
        }