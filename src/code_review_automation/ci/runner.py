#!/usr/bin/env python3
"""
CI/CD Runner

Specialized runner for CI/CD environments with proper exit codes,
performance tracking, caching, and integration features.
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib

from ..main import main as core_main
from ..config import ConfigManager, create_config_manager
from ..formatters import create_output_router, OutputRequest, NotificationManager, NotificationConfig
from ..utils.logger import setup_logger, get_logger


@dataclass
class CIConfig:
    """CI/CD specific configuration."""
    # Failure thresholds
    max_critical_issues: int = 5
    max_total_issues: int = 50
    fail_on_security_issues: bool = True
    fail_on_performance_regression: bool = False

    # Performance thresholds
    max_execution_time: int = 300  # 5 minutes
    performance_baseline_file: Optional[str] = None
    performance_regression_threshold: float = 1.5  # 50% slowdown

    # Caching
    enable_cache: bool = True
    cache_dir: str = ".cache/code-review-assistant"
    cache_key_factors: List[str] = None

    # Output and reporting
    output_formats: List[str] = None
    artifact_dir: str = "artifacts"
    enable_metrics: bool = True
    enable_trends: bool = True

    # Notifications
    notification_platforms: List[str] = None
    notification_on_success: bool = False
    notification_on_failure: bool = True

    def __post_init__(self):
        if self.cache_key_factors is None:
            self.cache_key_factors = ["requirements.txt", ".codereview.yaml", "src/"]
        if self.output_formats is None:
            self.output_formats = ["json"]
        if self.notification_platforms is None:
            self.notification_platforms = []


@dataclass
class CIResult:
    """CI/CD execution result."""
    success: bool
    exit_code: int
    execution_time: float
    total_issues: int
    critical_issues: int
    files_analyzed: int
    cache_hit: bool
    performance_metrics: Dict[str, Any]
    outputs: Dict[str, str]
    artifacts: List[str]
    error_message: Optional[str] = None


class PerformanceTracker:
    """Tracks performance metrics for CI/CD runs."""

    def __init__(self, baseline_file: Optional[str] = None):
        self.baseline_file = baseline_file
        self.logger = get_logger(__name__)
        self.start_time = None
        self.metrics = {}

    def start(self):
        """Start performance tracking."""
        self.start_time = time.time()
        self.metrics = {
            'start_time': self.start_time,
            'memory_usage': self._get_memory_usage(),
            'cpu_count': os.cpu_count()
        }

    def record_milestone(self, name: str):
        """Record a performance milestone."""
        if self.start_time is None:
            return

        current_time = time.time()
        self.metrics[f'{name}_time'] = current_time - self.start_time
        self.metrics[f'{name}_memory'] = self._get_memory_usage()

    def finish(self) -> Dict[str, Any]:
        """Finish tracking and return metrics."""
        if self.start_time is None:
            return {}

        end_time = time.time()
        self.metrics['end_time'] = end_time
        self.metrics['total_execution_time'] = end_time - self.start_time
        self.metrics['final_memory'] = self._get_memory_usage()

        return self.metrics

    def check_regression(self, threshold: float = 1.5) -> bool:
        """Check for performance regression against baseline."""
        if not self.baseline_file or not Path(self.baseline_file).exists():
            return False

        try:
            with open(self.baseline_file) as f:
                baseline = json.load(f)

            baseline_time = baseline.get('total_execution_time', 0)
            current_time = self.metrics.get('total_execution_time', 0)

            if baseline_time > 0 and current_time > baseline_time * threshold:
                self.logger.warning(
                    f"Performance regression detected: {current_time:.2f}s vs baseline {baseline_time:.2f}s"
                )
                return True

        except Exception as e:
            self.logger.error(f"Error checking performance baseline: {e}")

        return False

    def save_baseline(self, output_file: str):
        """Save current metrics as baseline."""
        try:
            with open(output_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
            self.logger.info(f"Performance baseline saved to {output_file}")
        except Exception as e:
            self.logger.error(f"Error saving performance baseline: {e}")

    def _get_memory_usage(self) -> int:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss // 1024 // 1024
        except ImportError:
            return 0


class CacheManager:
    """Manages caching for faster CI/CD runs."""

    def __init__(self, config: CIConfig):
        self.config = config
        self.cache_dir = Path(config.cache_dir)
        self.logger = get_logger(__name__)

    def get_cache_key(self) -> str:
        """Generate cache key based on relevant factors."""
        hasher = hashlib.sha256()

        for factor in self.config.cache_key_factors:
            factor_path = Path(factor)

            if factor_path.is_file():
                # Hash file content
                with open(factor_path, 'rb') as f:
                    hasher.update(f.read())
            elif factor_path.is_dir():
                # Hash directory structure and key files
                for file_path in sorted(factor_path.rglob("*.py")):
                    hasher.update(str(file_path).encode())
                    try:
                        with open(file_path, 'rb') as f:
                            hasher.update(f.read()[:1024])  # First 1KB
                    except Exception:
                        pass
            else:
                # Hash as string
                hasher.update(factor.encode())

        return hasher.hexdigest()[:16]

    def get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis result."""
        if not self.config.enable_cache:
            return None

        cache_file = self.cache_dir / f"result-{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cached_data = json.load(f)

            # Check if cache is still valid (24 hours)
            cache_time = cached_data.get('timestamp', 0)
            if time.time() - cache_time > 24 * 3600:
                cache_file.unlink()
                return None

            self.logger.info(f"Using cached result: {cache_key}")
            return cached_data

        except Exception as e:
            self.logger.error(f"Error reading cache: {e}")
            return None

    def save_result(self, cache_key: str, result: Dict[str, Any]):
        """Save analysis result to cache."""
        if not self.config.enable_cache:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / f"result-{cache_key}.json"

        try:
            cache_data = {
                'timestamp': time.time(),
                'cache_key': cache_key,
                'result': result
            }

            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

            self.logger.info(f"Result cached: {cache_key}")

        except Exception as e:
            self.logger.error(f"Error saving to cache: {e}")

    def cleanup_cache(self, max_age_days: int = 7):
        """Clean up old cache entries."""
        if not self.cache_dir.exists():
            return

        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        cleaned = 0

        for cache_file in self.cache_dir.glob("result-*.json"):
            try:
                if cache_file.stat().st_mtime < cutoff_time:
                    cache_file.unlink()
                    cleaned += 1
            except Exception:
                pass

        if cleaned > 0:
            self.logger.info(f"Cleaned {cleaned} old cache entries")


class CIRunner:
    """Main CI/CD runner."""

    def __init__(self, config: CIConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.cache_manager = CacheManager(config)
        self.performance_tracker = PerformanceTracker(config.performance_baseline_file)

    def run(self, args: argparse.Namespace) -> CIResult:
        """Run code review analysis in CI/CD mode."""
        self.logger.info("🚀 Starting CI/CD code review analysis")

        # Start performance tracking
        self.performance_tracker.start()

        try:
            # Generate cache key
            cache_key = self.cache_manager.get_cache_key()
            self.logger.info(f"Cache key: {cache_key}")

            # Check cache
            cached_result = self.cache_manager.get_cached_result(cache_key)
            if cached_result and not args.force_analysis:
                return self._handle_cached_result(cached_result)

            # Run analysis
            result = self._run_analysis(args, cache_key)

            # Save to cache
            if result.success:
                self.cache_manager.save_result(cache_key, {
                    'result': asdict(result),
                    'args': vars(args)
                })

            return result

        except Exception as e:
            self.logger.error(f"CI/CD runner error: {e}")
            return CIResult(
                success=False,
                exit_code=2,
                execution_time=time.time() - (self.performance_tracker.start_time or time.time()),
                total_issues=0,
                critical_issues=0,
                files_analyzed=0,
                cache_hit=False,
                performance_metrics={},
                outputs={},
                artifacts=[],
                error_message=str(e)
            )

    def _handle_cached_result(self, cached_data: Dict[str, Any]) -> CIResult:
        """Handle cached analysis result."""
        self.logger.info("📦 Using cached analysis result")

        cached_result = cached_data['result']
        result = CIResult(**cached_result)
        result.cache_hit = True
        result.execution_time = 0.1  # Minimal time for cache hit

        # Still generate outputs if requested
        self._generate_outputs(result, cached_data.get('args', {}))

        return result

    def _run_analysis(self, args: argparse.Namespace, cache_key: str) -> CIResult:
        """Run the actual analysis."""
        self.performance_tracker.record_milestone("setup_complete")

        # Initialize result
        result = CIResult(
            success=True,
            exit_code=0,
            execution_time=0,
            total_issues=0,
            critical_issues=0,
            files_analyzed=0,
            cache_hit=False,
            performance_metrics={},
            outputs={},
            artifacts=[]
        )

        try:
            # Create config manager
            config_manager = create_config_manager(args.config)
            self.performance_tracker.record_milestone("config_loaded")

            # Run core analysis
            analysis_result = self._run_core_analysis(args, config_manager)
            self.performance_tracker.record_milestone("analysis_complete")

            # Extract metrics
            result.total_issues = len(analysis_result.get('issues', []))
            result.critical_issues = len([
                i for i in analysis_result.get('issues', [])
                if i.get('severity') == 'error'
            ])
            result.files_analyzed = analysis_result.get('files_analyzed', 0)

            # Check failure conditions
            result.success, result.exit_code = self._check_failure_conditions(result)

            # Generate outputs
            self._generate_outputs(result, vars(args), analysis_result)
            self.performance_tracker.record_milestone("outputs_generated")

            # Send notifications if configured
            if self.config.notification_platforms:
                self._send_notifications(result, analysis_result)
                self.performance_tracker.record_milestone("notifications_sent")

            # Finalize performance metrics
            result.performance_metrics = self.performance_tracker.finish()
            result.execution_time = result.performance_metrics.get('total_execution_time', 0)

            # Check performance regression
            if (self.config.fail_on_performance_regression and
                self.performance_tracker.check_regression(self.config.performance_regression_threshold)):
                result.success = False
                result.exit_code = 3
                result.error_message = "Performance regression detected"

            # Save performance baseline if successful
            if result.success and args.save_baseline:
                self.performance_tracker.save_baseline("performance-baseline.json")

        except Exception as e:
            result.success = False
            result.exit_code = 2
            result.error_message = str(e)
            self.logger.error(f"Analysis execution error: {e}")

        return result

    def _run_core_analysis(self, args: argparse.Namespace, config_manager: ConfigManager) -> Dict[str, Any]:
        """Run the core analysis logic."""
        # This would integrate with the main analysis engine
        # For now, simulate the analysis

        # Import and run the main analysis
        from ..analyzers.core_analyzer import CoreAnalyzer
        from ..config.rule_engine import RuleResult

        analyzer = CoreAnalyzer(config_manager.get_config())

        # Determine files to analyze
        if args.mode == "git-diff":
            # Analyze git diff
            files_to_analyze = self._get_git_diff_files(args.base_ref, args.head_ref)
        else:
            # Analyze specified files/directories
            files_to_analyze = self._get_files_to_analyze(args.include_path)

        # Run analysis
        all_results = []
        for file_path in files_to_analyze:
            if not file_path.exists():
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                file_results = analyzer.analyze_file(file_path, content)
                all_results.extend(file_results)

            except Exception as e:
                self.logger.warning(f"Error analyzing {file_path}: {e}")

        # Convert to dictionary format
        issues = [
            {
                'severity': result.severity.value,
                'message': result.message,
                'file_path': str(result.file_path),
                'line_number': result.line_number,
                'column': result.column,
                'rule_name': result.rule_name,
                'checker_name': result.checker_name,
                'suggestion': result.suggestion
            }
            for result in all_results
        ]

        return {
            'issues': issues,
            'files_analyzed': len(files_to_analyze),
            'timestamp': datetime.now().isoformat()
        }

    def _get_git_diff_files(self, base_ref: str, head_ref: str) -> List[Path]:
        """Get files changed in git diff."""
        import subprocess

        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', f'{base_ref}..{head_ref}'],
                capture_output=True, text=True, check=True
            )

            files = []
            for line in result.stdout.strip().split('\n'):
                if line and line.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
                    file_path = Path(line)
                    if file_path.exists():
                        files.append(file_path)

            return files

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git diff error: {e}")
            return []

    def _get_files_to_analyze(self, include_paths: List[str]) -> List[Path]:
        """Get files to analyze from include paths."""
        files = []

        for include_path in include_paths or ['src/']:
            path = Path(include_path)

            if path.is_file():
                files.append(path)
            elif path.is_dir():
                for ext in ['.py', '.js', '.ts', '.jsx', '.tsx']:
                    files.extend(path.rglob(f'*{ext}'))

        return files

    def _check_failure_conditions(self, result: CIResult) -> tuple[bool, int]:
        """Check if analysis should fail the CI/CD pipeline."""
        # Check critical issues threshold
        if result.critical_issues > self.config.max_critical_issues:
            self.logger.error(
                f"Too many critical issues: {result.critical_issues} "
                f"(max: {self.config.max_critical_issues})"
            )
            return False, 1

        # Check total issues threshold
        if result.total_issues > self.config.max_total_issues:
            self.logger.error(
                f"Too many total issues: {result.total_issues} "
                f"(max: {self.config.max_total_issues})"
            )
            return False, 1

        # Check execution time threshold
        if result.execution_time > self.config.max_execution_time:
            self.logger.error(
                f"Analysis took too long: {result.execution_time}s "
                f"(max: {self.config.max_execution_time}s)"
            )
            return False, 4

        return True, 0

    def _generate_outputs(self, result: CIResult, args: Dict[str, Any], analysis_result: Dict[str, Any] = None):
        """Generate requested output formats."""
        if not analysis_result:
            return

        # Create output directory
        artifact_dir = Path(self.config.artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Create output router
        router = create_output_router()

        # Prepare output requests
        requests = []
        for format_type in self.config.output_formats:
            output_file = artifact_dir / f"analysis.{format_type}"

            requests.append(OutputRequest(
                format_type=format_type,
                results=[],  # Would need to convert analysis_result to RuleResult objects
                output_path=output_file
            ))

        # Generate outputs (simplified for now)
        for format_type in self.config.output_formats:
            output_file = artifact_dir / f"analysis.{format_type}"

            if format_type == "json":
                with open(output_file, 'w') as f:
                    json.dump(analysis_result, f, indent=2)

            result.outputs[format_type] = str(output_file)
            result.artifacts.append(str(output_file))

    def _send_notifications(self, result: CIResult, analysis_result: Dict[str, Any]):
        """Send notifications to configured platforms."""
        should_notify = (
            (result.success and self.config.notification_on_success) or
            (not result.success and self.config.notification_on_failure)
        )

        if not should_notify:
            return

        try:
            notification_config = NotificationConfig(
                enabled=True,
                severity_threshold="warning",
                max_issues_in_notification=10
            )

            notification_manager = NotificationManager(notification_config)

            # This would send actual notifications
            self.logger.info("Notifications would be sent here")

        except Exception as e:
            self.logger.error(f"Notification error: {e}")


def create_ci_config() -> CIConfig:
    """Create CI config from environment variables."""
    config = CIConfig()

    # Override from environment
    if os.getenv('CI_MAX_CRITICAL_ISSUES'):
        config.max_critical_issues = int(os.getenv('CI_MAX_CRITICAL_ISSUES'))

    if os.getenv('CI_MAX_TOTAL_ISSUES'):
        config.max_total_issues = int(os.getenv('CI_MAX_TOTAL_ISSUES'))

    if os.getenv('CI_ENABLE_CACHE'):
        config.enable_cache = os.getenv('CI_ENABLE_CACHE').lower() == 'true'

    if os.getenv('CI_OUTPUT_FORMATS'):
        config.output_formats = os.getenv('CI_OUTPUT_FORMATS').split(',')

    if os.getenv('CI_NOTIFICATION_PLATFORMS'):
        config.notification_platforms = os.getenv('CI_NOTIFICATION_PLATFORMS').split(',')

    return config


def main():
    """Main entry point for CI/CD runner."""
    parser = argparse.ArgumentParser(description="Code Review CI/CD Runner")

    # Analysis options
    parser.add_argument('--mode', choices=['files', 'git-diff'], default='files',
                       help='Analysis mode')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--include-path', action='append', default=[],
                       help='Paths to include in analysis')

    # Git diff options
    parser.add_argument('--base-ref', help='Base git reference for diff')
    parser.add_argument('--head-ref', help='Head git reference for diff')

    # CI/CD specific options
    parser.add_argument('--force-analysis', action='store_true',
                       help='Force analysis even if cached result exists')
    parser.add_argument('--save-baseline', action='store_true',
                       help='Save performance metrics as baseline')
    parser.add_argument('--cleanup-cache', action='store_true',
                       help='Clean up old cache entries')

    # Output options
    parser.add_argument('--output-format', action='append', default=[],
                       help='Output formats to generate')
    parser.add_argument('--artifact-dir', default='artifacts',
                       help='Directory for output artifacts')

    args = parser.parse_args()

    # Setup logging
    setup_logger(level='INFO')

    # Create CI config
    ci_config = create_ci_config()

    # Override config from arguments
    if args.output_format:
        ci_config.output_formats = args.output_format
    if args.artifact_dir:
        ci_config.artifact_dir = args.artifact_dir

    # Create and run CI runner
    runner = CIRunner(ci_config)

    # Cleanup cache if requested
    if args.cleanup_cache:
        runner.cache_manager.cleanup_cache()

    # Run analysis
    result = runner.run(args)

    # Print results
    print(f"\n{'='*50}")
    print(f"📊 CI/CD Analysis Results")
    print(f"{'='*50}")
    print(f"Success: {'✅' if result.success else '❌'}")
    print(f"Total Issues: {result.total_issues}")
    print(f"Critical Issues: {result.critical_issues}")
    print(f"Files Analyzed: {result.files_analyzed}")
    print(f"Execution Time: {result.execution_time:.2f}s")
    print(f"Cache Hit: {'✅' if result.cache_hit else '❌'}")

    if result.error_message:
        print(f"Error: {result.error_message}")

    if result.artifacts:
        print(f"Artifacts: {', '.join(result.artifacts)}")

    # Exit with appropriate code
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()