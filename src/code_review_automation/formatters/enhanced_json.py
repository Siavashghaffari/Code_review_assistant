"""
Enhanced JSON Formatter

Advanced JSON formatter for CI/CD integration with multiple schemas,
metrics export, and integration with various CI/CD platforms.
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

from .base import BaseFormatter, FormatterConfig, OutputContext, MultiFormatSupport
from ..config.rule_engine import RuleResult


class JSONFormatter(BaseFormatter, MultiFormatSupport):
    """Enhanced JSON formatter for CI/CD and API integration."""

    def __init__(self, config: FormatterConfig = None, context: OutputContext = None):
        super().__init__(config, context)

        # Add schema sub-formats
        self.add_sub_format("sarif")      # Static Analysis Results Interchange Format
        self.add_sub_format("gitlab_ci")  # GitLab CI format
        self.add_sub_format("github_ci")  # GitHub Actions format
        self.add_sub_format("jenkins")    # Jenkins format
        self.add_sub_format("sonarqube")  # SonarQube format
        self.add_sub_format("eslint")     # ESLint-compatible format
        self.add_sub_format("generic")    # Generic structured format
        self.add_sub_format("metrics")    # Metrics and analytics format

    def get_format_type(self) -> str:
        return "json"

    def supports_feature(self, feature: str) -> bool:
        features = {
            "streaming": True,
            "structured_data": True,
            "metrics": True,
            "filtering": True,
            "aggregation": True
        }
        return features.get(feature, False)

    def format(self, results: List[RuleResult], sub_format: str = "generic", **kwargs) -> Any:
        """Format results as JSON for specific platforms."""
        if sub_format == "sarif":
            return self._format_sarif(results, **kwargs)
        elif sub_format == "gitlab_ci":
            return self._format_gitlab_ci(results, **kwargs)
        elif sub_format == "github_ci":
            return self._format_github_ci(results, **kwargs)
        elif sub_format == "jenkins":
            return self._format_jenkins(results, **kwargs)
        elif sub_format == "sonarqube":
            return self._format_sonarqube(results, **kwargs)
        elif sub_format == "eslint":
            return self._format_eslint(results, **kwargs)
        elif sub_format == "metrics":
            return self._format_metrics(results, **kwargs)
        else:
            return self._format_generic(results, **kwargs)

    def _format_sarif(self, results: List[RuleResult], **kwargs) -> Any:
        """Format as SARIF (Static Analysis Results Interchange Format)."""
        # SARIF v2.1.0 schema
        sarif_report = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "Code Review Assistant",
                        "version": self.context.analyzer_version,
                        "informationUri": "https://github.com/your-org/code-review-assistant",
                        "rules": self._create_sarif_rules(results)
                    }
                },
                "results": self._create_sarif_results(results),
                "artifacts": self._create_sarif_artifacts(results),
                "invocations": [{
                    "executionSuccessful": True,
                    "startTimeUtc": self.context.timestamp.isoformat() + "Z",
                    "endTimeUtc": datetime.now().isoformat() + "Z",
                    "workingDirectory": {
                        "uri": f"file://{self.context.repository_path}/" if self.context.repository_path else "file:///"
                    }
                }]
            }]
        }

        content = json.dumps(sarif_report, indent=2, ensure_ascii=False)
        return self.create_formatted_output(content)

    def _format_gitlab_ci(self, results: List[RuleResult], **kwargs) -> Any:
        """Format for GitLab CI Code Quality reports."""
        gitlab_issues = []

        for result in results:
            # Map severity to GitLab levels
            severity_map = {
                "error": "major",
                "warning": "minor",
                "suggestion": "info",
                "info": "info"
            }

            # Convert paths to relative
            file_path = self.format_file_path(result.file_path, self.context.repository_path)

            issue = {
                "description": result.message,
                "check_name": f"{result.checker_name}/{result.rule_name}",
                "fingerprint": self._generate_fingerprint(result),
                "severity": severity_map.get(result.severity.value, "info"),
                "location": {
                    "path": file_path,
                    "lines": {
                        "begin": result.line_number or 1
                    }
                }
            }

            if result.column:
                issue["location"]["positions"] = {
                    "begin": {
                        "line": result.line_number or 1,
                        "column": result.column
                    }
                }

            # Add categories
            categories = self._categorize_issue(result)
            if categories:
                issue["categories"] = categories

            gitlab_issues.append(issue)

        content = json.dumps(gitlab_issues, indent=2, ensure_ascii=False)
        return self.create_formatted_output(content)

    def _format_github_ci(self, results: List[RuleResult], **kwargs) -> Any:
        """Format for GitHub Actions and GitHub Code Scanning."""
        github_format = {
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "code-review-assistant",
                        "version": self.context.analyzer_version
                    }
                },
                "results": []
            }]
        }

        for result in results:
            file_path = self.format_file_path(result.file_path, self.context.repository_path)

            github_result = {
                "ruleId": f"{result.checker_name}.{result.rule_name}",
                "message": {
                    "text": result.message
                },
                "level": self._map_severity_to_github_level(result.severity.value),
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": file_path
                        },
                        "region": {
                            "startLine": result.line_number or 1,
                            "startColumn": result.column or 1
                        }
                    }
                }]
            }

            if result.suggestion:
                github_result["fixes"] = [{
                    "description": {
                        "text": result.suggestion
                    }
                }]

            github_format["runs"][0]["results"].append(github_result)

        content = json.dumps(github_format, indent=2, ensure_ascii=False)
        return self.create_formatted_output(content)

    def _format_jenkins(self, results: List[RuleResult], **kwargs) -> Any:
        """Format for Jenkins with warnings-ng plugin."""
        jenkins_issues = []

        for result in results:
            file_path = self.format_file_path(result.file_path, self.context.repository_path)

            jenkins_issue = {
                "fileName": file_path,
                "lineStart": result.line_number or 1,
                "lineEnd": result.line_number or 1,
                "columnStart": result.column or 1,
                "columnEnd": result.column or 1,
                "severity": result.severity.value.upper(),
                "message": result.message,
                "category": result.checker_name,
                "type": result.rule_name,
                "moduleName": self._get_module_name(result.file_path),
                "packageName": self._get_package_name(result.file_path)
            }

            if result.suggestion:
                jenkins_issue["description"] = result.suggestion

            jenkins_issues.append(jenkins_issue)

        jenkins_report = {
            "issues": jenkins_issues,
            "size": len(jenkins_issues)
        }

        content = json.dumps(jenkins_report, indent=2, ensure_ascii=False)
        return self.create_formatted_output(content)

    def _format_sonarqube(self, results: List[RuleResult], **kwargs) -> Any:
        """Format for SonarQube Generic Issue Import."""
        sonar_issues = []

        for result in results:
            file_path = self.format_file_path(result.file_path, self.context.repository_path)

            # Map severity to SonarQube severity
            severity_map = {
                "error": "CRITICAL",
                "warning": "MAJOR",
                "suggestion": "MINOR",
                "info": "INFO"
            }

            # Map to SonarQube types
            type_map = {
                "security": "VULNERABILITY",
                "bug": "BUG",
                "style": "CODE_SMELL",
                "complexity": "CODE_SMELL",
                "maintainability": "CODE_SMELL"
            }

            issue_type = type_map.get(result.checker_name.lower(), "CODE_SMELL")

            sonar_issue = {
                "engineId": "code-review-assistant",
                "ruleId": f"{result.checker_name}.{result.rule_name}",
                "severity": severity_map.get(result.severity.value, "MINOR"),
                "type": issue_type,
                "primaryLocation": {
                    "message": result.message,
                    "filePath": file_path,
                    "textRange": {
                        "startLine": result.line_number or 1,
                        "startColumn": result.column or 0 if result.column else 0
                    }
                }
            }

            # Add effort minutes for technical debt
            if result.severity.value in ["warning", "suggestion"]:
                effort_map = {"warning": 10, "suggestion": 5}
                sonar_issue["effortMinutes"] = effort_map.get(result.severity.value, 5)

            sonar_issues.append(sonar_issue)

        sonar_report = {"issues": sonar_issues}
        content = json.dumps(sonar_report, indent=2, ensure_ascii=False)
        return self.create_formatted_output(content)

    def _format_eslint(self, results: List[RuleResult], **kwargs) -> Any:
        """Format in ESLint-compatible JSON format."""
        # Group results by file
        files_map = {}
        for result in results:
            file_path = str(result.file_path)
            if file_path not in files_map:
                files_map[file_path] = {
                    "filePath": file_path,
                    "messages": [],
                    "errorCount": 0,
                    "warningCount": 0,
                    "fixableErrorCount": 0,
                    "fixableWarningCount": 0
                }

            # Map severity
            severity_map = {"error": 2, "warning": 1, "suggestion": 1, "info": 1}
            severity_num = severity_map.get(result.severity.value, 1)

            message = {
                "ruleId": f"{result.checker_name}/{result.rule_name}",
                "severity": severity_num,
                "message": result.message,
                "line": result.line_number or 1,
                "column": result.column or 1,
                "nodeType": "Program",  # Generic node type
                "source": result.metadata.get("content", "") if result.metadata else ""
            }

            if result.suggestion:
                message["fix"] = {
                    "text": result.suggestion
                }
                if severity_num == 2:
                    files_map[file_path]["fixableErrorCount"] += 1
                else:
                    files_map[file_path]["fixableWarningCount"] += 1

            files_map[file_path]["messages"].append(message)

            if severity_num == 2:
                files_map[file_path]["errorCount"] += 1
            else:
                files_map[file_path]["warningCount"] += 1

        eslint_results = list(files_map.values())
        content = json.dumps(eslint_results, indent=2, ensure_ascii=False)
        return self.create_formatted_output(content)

    def _format_metrics(self, results: List[RuleResult], **kwargs) -> Any:
        """Format for metrics and analytics."""
        summary = self.create_summary(results)

        # Detailed metrics
        metrics = {
            "metadata": {
                "timestamp": self.context.timestamp.isoformat(),
                "analyzer_version": self.context.analyzer_version,
                "analysis_type": self.context.analysis_type,
                "repository_url": self.context.repository_url,
                "commit_sha": self.context.commit_sha,
                "branch_name": self.context.branch_name,
                "execution_time_seconds": self.context.execution_time
            },
            "summary": summary,
            "metrics": {
                "code_quality": self._calculate_code_quality_metrics(results, summary),
                "security": self._calculate_security_metrics(results),
                "maintainability": self._calculate_maintainability_metrics(results),
                "technical_debt": self._calculate_technical_debt_metrics(results)
            },
            "trends": self._calculate_trend_metrics(results, kwargs.get("historical_data")),
            "detailed_results": [self._result_to_dict(result) for result in results]
        }

        content = json.dumps(metrics, indent=2, ensure_ascii=False, default=str)
        return self.create_formatted_output(content)

    def _format_generic(self, results: List[RuleResult], **kwargs) -> Any:
        """Format as generic structured JSON."""
        summary = self.create_summary(results)

        report = {
            "metadata": {
                "timestamp": self.context.timestamp.isoformat(),
                "analyzer_version": self.context.analyzer_version,
                "analysis_type": self.context.analysis_type,
                "files_analyzed": self.context.files_analyzed,
                "execution_time": self.context.execution_time
            },
            "summary": summary,
            "issues": [self._result_to_dict(result) for result in results]
        }

        if self.context.repository_url:
            report["metadata"]["repository"] = self.context.repository_url

        if self.context.git_range:
            report["metadata"]["git_range"] = self.context.git_range

        content = json.dumps(report, indent=2, ensure_ascii=False, default=str)
        return self.create_formatted_output(content)

    def _create_sarif_rules(self, results: List[RuleResult]) -> List[Dict[str, Any]]:
        """Create SARIF rules section."""
        rules_map = {}

        for result in results:
            rule_id = f"{result.checker_name}.{result.rule_name}"
            if rule_id not in rules_map:
                rules_map[rule_id] = {
                    "id": rule_id,
                    "name": result.rule_name,
                    "shortDescription": {"text": result.message},
                    "fullDescription": {"text": result.message},
                    "helpUri": f"https://docs.example.com/rules/{result.checker_name}/{result.rule_name}",
                    "properties": {
                        "category": result.checker_name,
                        "tags": [result.checker_name, result.severity.value]
                    }
                }

        return list(rules_map.values())

    def _create_sarif_results(self, results: List[RuleResult]) -> List[Dict[str, Any]]:
        """Create SARIF results section."""
        sarif_results = []

        for result in results:
            file_path = self.format_file_path(result.file_path, self.context.repository_path)

            sarif_result = {
                "ruleId": f"{result.checker_name}.{result.rule_name}",
                "message": {"text": result.message},
                "level": self._map_severity_to_sarif_level(result.severity.value),
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": file_path},
                        "region": {
                            "startLine": result.line_number or 1,
                            "startColumn": result.column or 1
                        }
                    }
                }]
            }

            if result.suggestion:
                sarif_result["fixes"] = [{
                    "description": {"text": result.suggestion}
                }]

            sarif_results.append(sarif_result)

        return sarif_results

    def _create_sarif_artifacts(self, results: List[RuleResult]) -> List[Dict[str, Any]]:
        """Create SARIF artifacts section."""
        artifacts_map = {}

        for result in results:
            file_path = self.format_file_path(result.file_path, self.context.repository_path)
            if file_path not in artifacts_map:
                artifacts_map[file_path] = {
                    "location": {"uri": file_path},
                    "length": -1,  # Unknown length
                    "mimeType": self._get_mime_type(result.file_path)
                }

        return list(artifacts_map.values())

    def _result_to_dict(self, result: RuleResult) -> Dict[str, Any]:
        """Convert RuleResult to dictionary."""
        return {
            "rule_name": result.rule_name,
            "checker_name": result.checker_name,
            "severity": result.severity.value,
            "message": result.message,
            "file_path": str(result.file_path),
            "line_number": result.line_number,
            "column": result.column,
            "suggestion": result.suggestion,
            "metadata": result.metadata or {}
        }

    def _calculate_code_quality_metrics(self, results: List[RuleResult], summary: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate code quality metrics."""
        total_files = self.context.files_analyzed or 1
        issues_per_file = summary["total_issues"] / total_files if total_files > 0 else 0

        # Quality score (0-100)
        base_score = 100
        penalty_per_error = 10
        penalty_per_warning = 5
        penalty_per_suggestion = 2

        score = base_score
        for severity, count in summary["severity_breakdown"].items():
            if severity == "error":
                score -= count * penalty_per_error
            elif severity == "warning":
                score -= count * penalty_per_warning
            elif severity == "suggestion":
                score -= count * penalty_per_suggestion

        quality_score = max(0, score)

        return {
            "quality_score": round(quality_score, 1),
            "issues_per_file": round(issues_per_file, 2),
            "clean_file_ratio": round(summary["clean_files"] / total_files * 100, 1) if total_files > 0 else 100,
            "technical_debt_ratio": self._calculate_debt_ratio(results)
        }

    def _calculate_security_metrics(self, results: List[RuleResult]) -> Dict[str, Any]:
        """Calculate security-specific metrics."""
        security_issues = [r for r in results if "security" in r.checker_name.lower()]

        return {
            "total_security_issues": len(security_issues),
            "critical_security_issues": len([r for r in security_issues if r.severity.value == "error"]),
            "security_score": self._calculate_security_score(security_issues)
        }

    def _calculate_maintainability_metrics(self, results: List[RuleResult]) -> Dict[str, Any]:
        """Calculate maintainability metrics."""
        complexity_issues = [r for r in results if "complexity" in r.checker_name.lower()]
        style_issues = [r for r in results if "style" in r.checker_name.lower()]

        return {
            "complexity_issues": len(complexity_issues),
            "style_issues": len(style_issues),
            "maintainability_index": self._calculate_maintainability_index(results)
        }

    def _calculate_technical_debt_metrics(self, results: List[RuleResult]) -> Dict[str, Any]:
        """Calculate technical debt metrics."""
        # Estimate effort in minutes
        effort_map = {"error": 30, "warning": 15, "suggestion": 5, "info": 2}
        total_effort = sum(effort_map.get(r.severity.value, 2) for r in results)

        return {
            "total_debt_minutes": total_effort,
            "total_debt_hours": round(total_effort / 60, 1),
            "debt_per_file": round(total_effort / (self.context.files_analyzed or 1), 1)
        }

    def _calculate_trend_metrics(self, results: List[RuleResult], historical_data: Optional[List] = None) -> Dict[str, Any]:
        """Calculate trend metrics if historical data is available."""
        if not historical_data:
            return {"trend_available": False}

        current_count = len(results)
        previous_count = len(historical_data) if historical_data else 0

        change = current_count - previous_count
        change_percentage = (change / previous_count * 100) if previous_count > 0 else 0

        return {
            "trend_available": True,
            "current_issues": current_count,
            "previous_issues": previous_count,
            "change": change,
            "change_percentage": round(change_percentage, 1),
            "trend": "improving" if change < 0 else "degrading" if change > 0 else "stable"
        }

    def _generate_fingerprint(self, result: RuleResult) -> str:
        """Generate a unique fingerprint for an issue."""
        import hashlib

        fingerprint_data = f"{result.file_path}:{result.line_number}:{result.rule_name}:{result.message}"
        return hashlib.md5(fingerprint_data.encode()).hexdigest()

    def _categorize_issue(self, result: RuleResult) -> List[str]:
        """Categorize issue for GitLab."""
        categories = []

        category_map = {
            "security": ["Security"],
            "bug": ["Bug Risk"],
            "style": ["Style"],
            "complexity": ["Complexity"],
            "performance": ["Performance"]
        }

        checker_lower = result.checker_name.lower()
        for key, cats in category_map.items():
            if key in checker_lower:
                categories.extend(cats)

        return categories or ["Code Quality"]

    def _map_severity_to_github_level(self, severity: str) -> str:
        """Map severity to GitHub level."""
        mapping = {"error": "error", "warning": "warning", "suggestion": "note", "info": "note"}
        return mapping.get(severity, "note")

    def _map_severity_to_sarif_level(self, severity: str) -> str:
        """Map severity to SARIF level."""
        mapping = {"error": "error", "warning": "warning", "suggestion": "note", "info": "note"}
        return mapping.get(severity, "note")

    def _get_module_name(self, file_path: Path) -> str:
        """Get module name from file path."""
        return file_path.stem

    def _get_package_name(self, file_path: Path) -> str:
        """Get package name from file path."""
        return str(file_path.parent).replace("/", ".")

    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type from file extension."""
        ext = file_path.suffix.lower()
        mime_map = {
            ".py": "text/x-python",
            ".js": "application/javascript",
            ".ts": "application/typescript",
            ".java": "text/x-java-source",
            ".cpp": "text/x-c++src",
            ".c": "text/x-csrc",
            ".go": "text/x-go",
            ".rs": "text/x-rust"
        }
        return mime_map.get(ext, "text/plain")

    def _calculate_debt_ratio(self, results: List[RuleResult]) -> float:
        """Calculate technical debt ratio."""
        if not results:
            return 0.0

        total_lines = sum(1 for r in results if r.line_number)  # Approximation
        if total_lines == 0:
            return 0.0

        return round(len(results) / total_lines * 100, 2)

    def _calculate_security_score(self, security_issues: List[RuleResult]) -> float:
        """Calculate security score (0-100)."""
        if not security_issues:
            return 100.0

        # Penalty based on severity
        penalty = 0
        for issue in security_issues:
            if issue.severity.value == "error":
                penalty += 20
            elif issue.severity.value == "warning":
                penalty += 10
            else:
                penalty += 5

        return max(0.0, 100.0 - penalty)

    def _calculate_maintainability_index(self, results: List[RuleResult]) -> float:
        """Calculate maintainability index (0-100)."""
        if not results:
            return 100.0

        # Simple calculation based on issue density
        complexity_weight = 15
        style_weight = 5
        other_weight = 10

        penalty = 0
        for result in results:
            if "complexity" in result.checker_name.lower():
                penalty += complexity_weight
            elif "style" in result.checker_name.lower():
                penalty += style_weight
            else:
                penalty += other_weight

        return max(0.0, 100.0 - min(penalty, 100))  # Cap at 100