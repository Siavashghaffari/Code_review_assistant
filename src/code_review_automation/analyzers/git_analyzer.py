"""
Git Diff Analyzer

Analyzes git diffs to identify code review issues and improvements.
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Any

from .base_analyzer import BaseAnalyzer
from .core_analyzer import CoreAnalyzer
from ..utils.logger import get_logger


class GitAnalyzer(BaseAnalyzer):
    """Analyzer for git diffs."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.logger = get_logger(__name__)
        self.core_analyzer = CoreAnalyzer(config)

    def analyze(self, git_range: str) -> Dict[str, Any]:
        """
        Analyze git diff for the specified range.

        Args:
            git_range: Git revision range (e.g., 'HEAD~1..HEAD')

        Returns:
            Analysis results dictionary
        """
        self.logger.info(f"Analyzing git diff: {git_range}")

        try:
            # Get git diff
            diff_output = self._get_git_diff(git_range)

            # Parse diff and extract changed files
            changed_files = self._parse_diff(diff_output)

            # Analyze each changed file
            results = {
                "analysis_type": "git_diff",
                "git_range": git_range,
                "files_analyzed": len(changed_files),
                "issues": [],
                "suggestions": [],
                "summary": {}
            }

            for file_info in changed_files:
                file_results = self._analyze_file_changes(file_info)
                results["issues"].extend(file_results.get("issues", []))
                results["suggestions"].extend(file_results.get("suggestions", []))

            # Generate summary
            results["summary"] = self._generate_summary(results)

            return results

        except Exception as e:
            self.logger.error(f"Error analyzing git diff: {e}")
            raise

    def _get_git_diff(self, git_range: str) -> str:
        """Get git diff output for the specified range."""
        try:
            result = subprocess.run(
                ["git", "diff", git_range, "--unified=3"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git diff failed: {e.stderr}")

    def _parse_diff(self, diff_output: str) -> List[Dict[str, Any]]:
        """Parse git diff output to extract file changes."""
        files = []
        current_file = None

        for line in diff_output.split('\n'):
            if line.startswith('diff --git'):
                # Start of new file
                if current_file:
                    files.append(current_file)

                # Extract file paths
                parts = line.split(' ')
                if len(parts) >= 4:
                    old_path = parts[2][2:]  # Remove 'a/' prefix
                    new_path = parts[3][2:]  # Remove 'b/' prefix

                    current_file = {
                        "old_path": old_path,
                        "new_path": new_path,
                        "changes": [],
                        "added_lines": 0,
                        "removed_lines": 0
                    }

            elif line.startswith('@@') and current_file:
                # Hunk header
                current_file["changes"].append({
                    "type": "hunk",
                    "header": line,
                    "lines": []
                })

            elif current_file and current_file["changes"]:
                # Content line
                if line.startswith('+') and not line.startswith('+++'):
                    current_file["added_lines"] += 1
                    current_file["changes"][-1]["lines"].append({
                        "type": "added",
                        "content": line[1:]
                    })
                elif line.startswith('-') and not line.startswith('---'):
                    current_file["removed_lines"] += 1
                    current_file["changes"][-1]["lines"].append({
                        "type": "removed",
                        "content": line[1:]
                    })
                elif line.startswith(' '):
                    current_file["changes"][-1]["lines"].append({
                        "type": "context",
                        "content": line[1:]
                    })

        if current_file:
            files.append(current_file)

        return files

    def _analyze_file_changes(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze changes in a specific file."""
        issues = []
        suggestions = []

        file_path = file_info["new_path"]
        file_extension = Path(file_path).suffix.lower()

        # Apply language-specific rules
        language_rules = self.config.get("languages", {}).get(file_extension, {})

        for change in file_info["changes"]:
            for line_info in change["lines"]:
                if line_info["type"] == "added":
                    line_content = line_info["content"]

                    # Check for common issues in added lines
                    line_issues = self._check_line_issues(line_content, language_rules)
                    issues.extend(line_issues)

                    # Check for suggestions
                    line_suggestions = self._check_line_suggestions(line_content, language_rules)
                    suggestions.extend(line_suggestions)

        return {
            "file": file_path,
            "issues": issues,
            "suggestions": suggestions
        }

    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary statistics."""
        return {
            "total_issues": len(results["issues"]),
            "total_suggestions": len(results["suggestions"]),
            "files_with_issues": len(set(issue.get("file") for issue in results["issues"])),
            "most_common_issues": self._get_most_common_issues(results["issues"])
        }

    def _get_most_common_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get the most common issue types."""
        issue_counts = {}
        for issue in issues:
            issue_type = issue.get("type", "unknown")
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        return [
            {"type": issue_type, "count": count}
            for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        ][:5]  # Top 5