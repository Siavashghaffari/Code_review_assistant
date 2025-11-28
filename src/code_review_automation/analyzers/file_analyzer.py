"""
File Analyzer

Analyzes individual files for code review issues and improvements.
"""

from pathlib import Path
from typing import Dict, List, Any

from .base_analyzer import BaseAnalyzer
from .core_analyzer import CoreAnalyzer
from ..utils.logger import get_logger


class FileAnalyzer(BaseAnalyzer):
    """Analyzer for individual files."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.logger = get_logger(__name__)
        self.core_analyzer = CoreAnalyzer(config)

    def analyze(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze the specified files.

        Args:
            file_paths: List of file paths to analyze

        Returns:
            Analysis results dictionary
        """
        self.logger.info(f"Analyzing {len(file_paths)} files")

        results = {
            "analysis_type": "files",
            "files_analyzed": 0,
            "files_skipped": 0,
            "issues": [],
            "suggestions": [],
            "summary": {}
        }

        for file_path_str in file_paths:
            file_path = Path(file_path_str)

            if not file_path.exists():
                self.logger.warning(f"File not found: {file_path}")
                results["files_skipped"] += 1
                continue

            if not self._should_analyze_file(file_path):
                self.logger.debug(f"Skipping file: {file_path}")
                results["files_skipped"] += 1
                continue

            try:
                # Use core analyzer for comprehensive analysis
                analysis_result = self.core_analyzer.analyze_file(file_path)
                results["issues"].extend(analysis_result.issues)
                results["suggestions"].extend(analysis_result.suggestions)
                results["files_analyzed"] += 1

                # Also run legacy analysis for backward compatibility
                legacy_results = self._analyze_single_file(file_path)
                results["issues"].extend(legacy_results.get("issues", []))
                results["suggestions"].extend(legacy_results.get("suggestions", []))

            except Exception as e:
                self.logger.error(f"Error analyzing {file_path}: {e}")
                results["files_skipped"] += 1

        # Generate summary
        results["summary"] = self._generate_summary(results)

        return results

    def _should_analyze_file(self, file_path: Path) -> bool:
        """Check if file should be analyzed based on configuration."""
        # Check file size limits
        max_size = self.config.get("limits", {}).get("max_file_size", 1024 * 1024)  # 1MB default
        if file_path.stat().st_size > max_size:
            return False

        # Check file extensions
        allowed_extensions = self.config.get("file_types", {}).get("include", [])
        excluded_extensions = self.config.get("file_types", {}).get("exclude", [])

        file_extension = file_path.suffix.lower()

        if excluded_extensions and file_extension in excluded_extensions:
            return False

        if allowed_extensions and file_extension not in allowed_extensions:
            return False

        # Check file paths
        excluded_paths = self.config.get("file_types", {}).get("exclude_paths", [])
        for excluded_path in excluded_paths:
            if excluded_path in str(file_path):
                return False

        return True

    def _analyze_single_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single file."""
        self.logger.debug(f"Analyzing file: {file_path}")

        issues = []
        suggestions = []

        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                content = file_path.read_text(encoding='latin1')
            except Exception as e:
                raise RuntimeError(f"Cannot read file {file_path}: {e}")

        lines = content.split('\n')
        file_extension = file_path.suffix.lower()

        # Get language-specific rules
        language_rules = self.config.get("languages", {}).get(file_extension, {})

        # Analyze each line
        for line_number, line in enumerate(lines, 1):
            # Check for issues
            line_issues = self._check_line_issues(line, language_rules)
            for issue in line_issues:
                issue.update({
                    "file": str(file_path),
                    "line": line_number,
                    "content": line.strip()
                })
            issues.extend(line_issues)

            # Check for suggestions
            line_suggestions = self._check_line_suggestions(line, language_rules)
            for suggestion in line_suggestions:
                suggestion.update({
                    "file": str(file_path),
                    "line": line_number,
                    "content": line.strip()
                })
            suggestions.extend(line_suggestions)

        # File-level analysis
        file_issues = self._check_file_level_issues(content, file_path, language_rules)
        issues.extend(file_issues)

        return {
            "file": str(file_path),
            "issues": issues,
            "suggestions": suggestions
        }

    def _check_file_level_issues(self, content: str, file_path: Path, language_rules: Dict) -> List[Dict[str, Any]]:
        """Check for file-level issues."""
        issues = []

        # Check file length
        max_lines = language_rules.get("max_file_lines", 1000)
        line_count = len(content.split('\n'))
        if line_count > max_lines:
            issues.append({
                "type": "file_too_long",
                "severity": "warning",
                "message": f"File has {line_count} lines, exceeds limit of {max_lines}",
                "file": str(file_path)
            })

        # Check for missing docstrings (Python files)
        if file_path.suffix.lower() == '.py':
            if not content.strip().startswith('"""') and not content.strip().startswith("'''"):
                # Check if it's a script file or module
                if 'def ' in content or 'class ' in content:
                    issues.append({
                        "type": "missing_docstring",
                        "severity": "info",
                        "message": "File should have a module docstring",
                        "file": str(file_path)
                    })

        return issues

    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary statistics."""
        return {
            "total_issues": len(results["issues"]),
            "total_suggestions": len(results["suggestions"]),
            "files_with_issues": len(set(issue.get("file") for issue in results["issues"])),
            "most_common_issues": self._get_most_common_issues(results["issues"]),
            "severity_breakdown": self._get_severity_breakdown(results["issues"])
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

    def _get_severity_breakdown(self, issues: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get breakdown of issues by severity."""
        severity_counts = {}
        for issue in issues:
            severity = issue.get("severity", "unknown")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return severity_counts