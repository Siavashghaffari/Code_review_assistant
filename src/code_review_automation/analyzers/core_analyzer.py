"""
Core Code Analyzer

Main analyzer class that orchestrates different types of code analysis including
syntax parsing, complexity analysis, security scanning, and style checking.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass

from .base_analyzer import BaseAnalyzer
from .checkers.complexity_checker import ComplexityChecker
from .checkers.security_checker import SecurityChecker
from .checkers.style_checker import StyleChecker
from .checkers.variable_checker import VariableChecker
from .checkers.error_handling_checker import ErrorHandlingChecker
from .checkers.naming_checker import NamingChecker
from .checkers.parser_factory import ParserFactory
from ..utils.logger import get_logger


@dataclass
class AnalysisResult:
    """Container for analysis results."""
    file_path: str
    language: str
    issues: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    ast_tree: Optional[Any] = None


class CoreAnalyzer(BaseAnalyzer):
    """
    Core analyzer that performs comprehensive code analysis including:
    - Syntax parsing and AST analysis
    - Complexity analysis (cyclomatic, cognitive)
    - Security vulnerability detection
    - Code style and naming convention checking
    - Unused variable detection
    - Error handling analysis
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.logger = get_logger(__name__)

        # Initialize specialized checkers
        self.complexity_checker = ComplexityChecker(config)
        self.security_checker = SecurityChecker(config)
        self.style_checker = StyleChecker(config)
        self.variable_checker = VariableChecker(config)
        self.error_handling_checker = ErrorHandlingChecker(config)
        self.naming_checker = NamingChecker(config)
        self.parser_factory = ParserFactory(config)

    def analyze_file(self, file_path: Path) -> AnalysisResult:
        """
        Perform comprehensive analysis on a single file.

        Args:
            file_path: Path to the file to analyze

        Returns:
            AnalysisResult containing all findings and metrics
        """
        self.logger.debug(f"Starting comprehensive analysis of {file_path}")

        try:
            # Read file content
            content = self._read_file_content(file_path)
            if not content:
                return self._create_empty_result(file_path, "empty")

            # Determine language and get parser
            language = self._detect_language(file_path)
            parser = self.parser_factory.get_parser(language)

            # Parse content into AST
            ast_tree = None
            if parser:
                try:
                    ast_tree = parser.parse(content)
                except Exception as e:
                    self.logger.warning(f"Failed to parse {file_path}: {e}")

            # Initialize result
            result = AnalysisResult(
                file_path=str(file_path),
                language=language,
                issues=[],
                suggestions=[],
                metrics={},
                ast_tree=ast_tree
            )

            # Run all analysis checks
            self._run_complexity_analysis(result, content, ast_tree)
            self._run_security_analysis(result, content, ast_tree)
            self._run_style_analysis(result, content, ast_tree)
            self._run_variable_analysis(result, content, ast_tree)
            self._run_error_handling_analysis(result, content, ast_tree)
            self._run_naming_analysis(result, content, ast_tree)

            # Calculate file-level metrics
            result.metrics.update(self._calculate_file_metrics(content, ast_tree))

            self.logger.debug(f"Analysis complete: {len(result.issues)} issues, {len(result.suggestions)} suggestions")
            return result

        except Exception as e:
            self.logger.error(f"Error analyzing {file_path}: {e}")
            return self._create_error_result(file_path, str(e))

    def _read_file_content(self, file_path: Path) -> str:
        """Read file content with encoding detection."""
        try:
            # Try UTF-8 first
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                # Fallback to latin1
                return file_path.read_text(encoding='latin1')
            except Exception as e:
                self.logger.error(f"Cannot read file {file_path}: {e}")
                return ""

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        extension = file_path.suffix.lower()

        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sh': 'shell',
            '.bash': 'shell',
            '.zsh': 'shell',
        }

        return language_map.get(extension, 'unknown')

    def _run_complexity_analysis(self, result: AnalysisResult, content: str, ast_tree: Any) -> None:
        """Run complexity analysis checks."""
        try:
            complexity_results = self.complexity_checker.check(content, ast_tree, result.language)
            result.issues.extend(complexity_results.get('issues', []))
            result.suggestions.extend(complexity_results.get('suggestions', []))
            result.metrics.update(complexity_results.get('metrics', {}))
        except Exception as e:
            self.logger.warning(f"Complexity analysis failed: {e}")

    def _run_security_analysis(self, result: AnalysisResult, content: str, ast_tree: Any) -> None:
        """Run security vulnerability checks."""
        try:
            security_results = self.security_checker.check(content, ast_tree, result.language)
            result.issues.extend(security_results.get('issues', []))
            result.suggestions.extend(security_results.get('suggestions', []))
        except Exception as e:
            self.logger.warning(f"Security analysis failed: {e}")

    def _run_style_analysis(self, result: AnalysisResult, content: str, ast_tree: Any) -> None:
        """Run code style consistency checks."""
        try:
            style_results = self.style_checker.check(content, ast_tree, result.language)
            result.issues.extend(style_results.get('issues', []))
            result.suggestions.extend(style_results.get('suggestions', []))
        except Exception as e:
            self.logger.warning(f"Style analysis failed: {e}")

    def _run_variable_analysis(self, result: AnalysisResult, content: str, ast_tree: Any) -> None:
        """Run unused variable detection."""
        try:
            variable_results = self.variable_checker.check(content, ast_tree, result.language)
            result.issues.extend(variable_results.get('issues', []))
            result.suggestions.extend(variable_results.get('suggestions', []))
        except Exception as e:
            self.logger.warning(f"Variable analysis failed: {e}")

    def _run_error_handling_analysis(self, result: AnalysisResult, content: str, ast_tree: Any) -> None:
        """Run error handling analysis."""
        try:
            error_results = self.error_handling_checker.check(content, ast_tree, result.language)
            result.issues.extend(error_results.get('issues', []))
            result.suggestions.extend(error_results.get('suggestions', []))
        except Exception as e:
            self.logger.warning(f"Error handling analysis failed: {e}")

    def _run_naming_analysis(self, result: AnalysisResult, content: str, ast_tree: Any) -> None:
        """Run naming convention checks."""
        try:
            naming_results = self.naming_checker.check(content, ast_tree, result.language)
            result.issues.extend(naming_results.get('issues', []))
            result.suggestions.extend(naming_results.get('suggestions', []))
        except Exception as e:
            self.logger.warning(f"Naming analysis failed: {e}")

    def _calculate_file_metrics(self, content: str, ast_tree: Any) -> Dict[str, Any]:
        """Calculate file-level metrics."""
        lines = content.split('\n')

        return {
            'total_lines': len(lines),
            'code_lines': len([line for line in lines if line.strip() and not line.strip().startswith('#')]),
            'comment_lines': len([line for line in lines if line.strip().startswith('#')]),
            'blank_lines': len([line for line in lines if not line.strip()]),
            'file_size_bytes': len(content.encode('utf-8')),
        }

    def _create_empty_result(self, file_path: Path, reason: str) -> AnalysisResult:
        """Create result for empty or unreadable files."""
        return AnalysisResult(
            file_path=str(file_path),
            language='unknown',
            issues=[],
            suggestions=[],
            metrics={'empty_file': True, 'reason': reason}
        )

    def _create_error_result(self, file_path: Path, error_message: str) -> AnalysisResult:
        """Create result for files that failed analysis."""
        return AnalysisResult(
            file_path=str(file_path),
            language='unknown',
            issues=[{
                'type': 'analysis_error',
                'severity': 'error',
                'message': f'Analysis failed: {error_message}',
                'file': str(file_path),
                'line': 1
            }],
            suggestions=[],
            metrics={'analysis_error': True}
        )

    def analyze(self, target: Any) -> Dict[str, Any]:
        """
        Analyze target (implementation of base class method).

        Args:
            target: File path or list of file paths

        Returns:
            Analysis results dictionary
        """
        if isinstance(target, (str, Path)):
            # Single file
            result = self.analyze_file(Path(target))
            return self._convert_result_to_dict(result)
        elif isinstance(target, list):
            # Multiple files
            results = []
            for file_path in target:
                result = self.analyze_file(Path(file_path))
                results.append(result)
            return self._convert_results_to_dict(results)
        else:
            raise ValueError(f"Unsupported target type: {type(target)}")

    def _convert_result_to_dict(self, result: AnalysisResult) -> Dict[str, Any]:
        """Convert single AnalysisResult to dictionary format."""
        return {
            'analysis_type': 'core_analysis',
            'files_analyzed': 1,
            'issues': result.issues,
            'suggestions': result.suggestions,
            'summary': {
                'total_issues': len(result.issues),
                'total_suggestions': len(result.suggestions),
                'files_with_issues': 1 if result.issues else 0,
                'metrics': result.metrics
            }
        }

    def _convert_results_to_dict(self, results: List[AnalysisResult]) -> Dict[str, Any]:
        """Convert multiple AnalysisResults to dictionary format."""
        all_issues = []
        all_suggestions = []
        total_metrics = {}

        for result in results:
            all_issues.extend(result.issues)
            all_suggestions.extend(result.suggestions)

            # Aggregate metrics
            for key, value in result.metrics.items():
                if isinstance(value, (int, float)):
                    total_metrics[key] = total_metrics.get(key, 0) + value

        return {
            'analysis_type': 'core_analysis',
            'files_analyzed': len(results),
            'issues': all_issues,
            'suggestions': all_suggestions,
            'summary': {
                'total_issues': len(all_issues),
                'total_suggestions': len(all_suggestions),
                'files_with_issues': len([r for r in results if r.issues]),
                'metrics': total_metrics,
                'most_common_issues': self._get_most_common_issues(all_issues),
                'severity_breakdown': self._get_severity_breakdown(all_issues)
            }
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