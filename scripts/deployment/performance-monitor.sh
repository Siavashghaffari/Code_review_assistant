#!/bin/bash
set -euo pipefail

# =============================================================================
# Performance Monitoring Script for Code Review Assistant
# =============================================================================
# This script monitors and tracks performance metrics across CI/CD runs
# and provides alerting when performance degrades beyond acceptable thresholds.
#
# Features:
# - Historical performance tracking
# - Baseline comparison
# - Performance regression detection
# - Multi-format metric output
# - Integration with monitoring systems
# =============================================================================

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
METRICS_DIR="${PROJECT_ROOT}/metrics"
PERFORMANCE_HISTORY="${METRICS_DIR}/performance-history.json"
BASELINE_FILE="${METRICS_DIR}/performance-baseline.json"
ALERT_THRESHOLD="${PERFORMANCE_ALERT_THRESHOLD:-20}" # 20% degradation
BASELINE_WINDOW="${BASELINE_WINDOW:-10}" # Last 10 successful runs
OUTPUT_FORMAT="${OUTPUT_FORMAT:-json}" # json, csv, prometheus

# Create metrics directory
mkdir -p "$METRICS_DIR"

# Logging functions
log_info() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

log_warning() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [WARNING] $1"
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $1"
}

# Initialize performance history if it doesn't exist
initialize_history() {
    if [[ ! -f "$PERFORMANCE_HISTORY" ]]; then
        cat > "$PERFORMANCE_HISTORY" << EOF
{
    "version": "1.0",
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "runs": []
}
EOF
        log_info "Initialized performance history file"
    fi
}

# Record performance metrics for current run
record_performance() {
    local execution_time="$1"
    local total_issues="$2"
    local critical_issues="$3"
    local files_analyzed="$4"
    local cache_hit="${5:-false}"
    local ci_system="${6:-unknown}"

    log_info "Recording performance metrics..."

    # Create current run data
    local current_run
    current_run=$(cat << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "execution_time_seconds": $execution_time,
    "total_issues": $total_issues,
    "critical_issues": $critical_issues,
    "files_analyzed": $files_analyzed,
    "cache_hit": $cache_hit,
    "ci_system": "$ci_system",
    "commit_sha": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "branch": "$(git branch --show-current 2>/dev/null || echo 'unknown')",
    "performance_score": $(calculate_performance_score "$execution_time" "$total_issues" "$files_analyzed")
}
EOF
)

    # Add to history using Python for JSON manipulation
    python3 << EOF
import json
from datetime import datetime, timedelta

# Read existing history
with open('$PERFORMANCE_HISTORY') as f:
    history = json.load(f)

# Add current run
current_run = $current_run
history['runs'].append(current_run)

# Keep only last 100 runs to prevent file bloat
if len(history['runs']) > 100:
    history['runs'] = history['runs'][-100:]

# Update metadata
history['last_updated'] = current_run['timestamp']
history['total_runs'] = len(history['runs'])

# Save updated history
with open('$PERFORMANCE_HISTORY', 'w') as f:
    json.dump(history, f, indent=2)

print(f"Performance recorded: {current_run['execution_time_seconds']}s, score: {current_run['performance_score']}")
EOF

    log_info "Performance metrics recorded successfully"
}

# Calculate performance score (higher is better)
calculate_performance_score() {
    local execution_time="$1"
    local total_issues="$2"
    local files_analyzed="$3"

    # Simple scoring algorithm: prioritize speed and low issue count
    # Base score of 100, subtract points for slow execution and high issue count
    local score
    score=$(python3 -c "
import math
execution_time = $execution_time
total_issues = $total_issues
files_analyzed = max($files_analyzed, 1)  # Prevent division by zero

# Base score
score = 100

# Penalize slow execution (exponential penalty after 60s)
if execution_time > 60:
    score -= min(50, (execution_time - 60) * 2)

# Penalize high issue density
issue_density = total_issues / files_analyzed
score -= min(30, issue_density * 5)

# Ensure score is non-negative
score = max(0, score)
print(f'{score:.2f}')
")
    echo "$score"
}

# Update performance baseline
update_baseline() {
    log_info "Updating performance baseline..."

    python3 << EOF
import json
import statistics
from datetime import datetime, timedelta

# Read performance history
with open('$PERFORMANCE_HISTORY') as f:
    history = json.load(f)

runs = history.get('runs', [])

# Filter successful runs (no critical issues) from last 30 days
cutoff_date = datetime.now() - timedelta(days=30)
recent_successful_runs = []

for run in runs:
    run_date = datetime.fromisoformat(run['timestamp'].replace('Z', '+00:00'))
    if run_date >= cutoff_date and run.get('critical_issues', 0) <= 5:
        recent_successful_runs.append(run)

if len(recent_successful_runs) < 3:
    print("Insufficient data for baseline calculation")
    exit(0)

# Take last N successful runs for baseline
baseline_runs = recent_successful_runs[-$BASELINE_WINDOW:] if len(recent_successful_runs) > $BASELINE_WINDOW else recent_successful_runs

# Calculate baseline metrics
execution_times = [run['execution_time_seconds'] for run in baseline_runs]
performance_scores = [run['performance_score'] for run in baseline_runs]

baseline = {
    "version": "1.0",
    "created_at": datetime.now().isoformat(),
    "baseline_runs": len(baseline_runs),
    "metrics": {
        "execution_time": {
            "mean": statistics.mean(execution_times),
            "median": statistics.median(execution_times),
            "p95": sorted(execution_times)[int(len(execution_times) * 0.95)] if len(execution_times) > 1 else execution_times[0],
            "std_dev": statistics.stdev(execution_times) if len(execution_times) > 1 else 0
        },
        "performance_score": {
            "mean": statistics.mean(performance_scores),
            "median": statistics.median(performance_scores),
            "p05": sorted(performance_scores)[int(len(performance_scores) * 0.05)] if len(performance_scores) > 1 else performance_scores[0],
            "std_dev": statistics.stdev(performance_scores) if len(performance_scores) > 1 else 0
        }
    }
}

# Save baseline
with open('$BASELINE_FILE', 'w') as f:
    json.dump(baseline, f, indent=2)

print(f"Baseline updated with {len(baseline_runs)} runs")
print(f"Execution time baseline: {baseline['metrics']['execution_time']['mean']:.2f}s")
print(f"Performance score baseline: {baseline['metrics']['performance_score']['mean']:.2f}")
EOF

    log_info "Baseline updated successfully"
}

# Check for performance regressions
check_regressions() {
    local current_execution_time="$1"
    local current_score="$2"

    if [[ ! -f "$BASELINE_FILE" ]]; then
        log_warning "No baseline file found, skipping regression check"
        return 0
    fi

    log_info "Checking for performance regressions..."

    local regression_detected
    regression_detected=$(python3 << EOF
import json

# Read baseline
with open('$BASELINE_FILE') as f:
    baseline = json.load(f)

current_execution_time = $current_execution_time
current_score = $current_score
alert_threshold = $ALERT_THRESHOLD / 100.0  # Convert percentage to decimal

baseline_time = baseline['metrics']['execution_time']['mean']
baseline_score = baseline['metrics']['performance_score']['mean']

regressions = []

# Check execution time regression
time_increase = ((current_execution_time - baseline_time) / baseline_time) * 100
if time_increase > $ALERT_THRESHOLD:
    regressions.append(f"Execution time increased by {time_increase:.1f}% (current: {current_execution_time:.1f}s, baseline: {baseline_time:.1f}s)")

# Check performance score regression
score_decrease = ((baseline_score - current_score) / baseline_score) * 100
if score_decrease > $ALERT_THRESHOLD:
    regressions.append(f"Performance score decreased by {score_decrease:.1f}% (current: {current_score:.1f}, baseline: {baseline_score:.1f})")

if regressions:
    print("REGRESSION_DETECTED")
    for regression in regressions:
        print(f"ALERT: {regression}")
else:
    print("NO_REGRESSION")
    print(f"Performance within acceptable range: {current_execution_time:.1f}s (baseline: {baseline_time:.1f}s)")
EOF
)

    if [[ "$regression_detected" == *"REGRESSION_DETECTED"* ]]; then
        log_error "Performance regression detected!"
        echo "$regression_detected" | grep "ALERT:" | while read -r line; do
            log_error "$line"
        done
        return 1
    else
        log_info "No performance regression detected"
        echo "$regression_detected" | grep -v "NO_REGRESSION" | while read -r line; do
            log_info "$line"
        done
        return 0
    fi
}

# Generate performance report in specified format
generate_report() {
    local format="${1:-json}"

    log_info "Generating performance report in $format format..."

    case "$format" in
        json)
            generate_json_report
            ;;
        csv)
            generate_csv_report
            ;;
        prometheus)
            generate_prometheus_report
            ;;
        html)
            generate_html_report
            ;;
        *)
            log_error "Unsupported format: $format"
            return 1
            ;;
    esac
}

# Generate JSON report
generate_json_report() {
    local report_file="${METRICS_DIR}/performance-report.json"

    python3 << EOF
import json
from datetime import datetime, timedelta

# Read history and baseline
with open('$PERFORMANCE_HISTORY') as f:
    history = json.load(f)

baseline = {}
if os.path.exists('$BASELINE_FILE'):
    with open('$BASELINE_FILE') as f:
        baseline = json.load(f)

runs = history.get('runs', [])
recent_runs = runs[-10:] if len(runs) > 10 else runs

report = {
    "generated_at": datetime.now().isoformat(),
    "summary": {
        "total_runs": len(runs),
        "recent_runs": len(recent_runs),
        "baseline_available": bool(baseline)
    },
    "recent_performance": {
        "runs": recent_runs
    },
    "baseline": baseline
}

if recent_runs:
    # Add trend analysis
    execution_times = [run['execution_time_seconds'] for run in recent_runs]
    performance_scores = [run['performance_score'] for run in recent_runs]

    report["trends"] = {
        "execution_time": {
            "min": min(execution_times),
            "max": max(execution_times),
            "avg": sum(execution_times) / len(execution_times),
            "trend": "improving" if execution_times[-1] < execution_times[0] else "degrading"
        },
        "performance_score": {
            "min": min(performance_scores),
            "max": max(performance_scores),
            "avg": sum(performance_scores) / len(performance_scores),
            "trend": "improving" if performance_scores[-1] > performance_scores[0] else "degrading"
        }
    }

with open('$report_file', 'w') as f:
    json.dump(report, f, indent=2)

print(f"JSON report generated: $report_file")
EOF
}

# Generate CSV report
generate_csv_report() {
    local report_file="${METRICS_DIR}/performance-report.csv"

    python3 << EOF
import json
import csv

# Read history
with open('$PERFORMANCE_HISTORY') as f:
    history = json.load(f)

runs = history.get('runs', [])

with open('$report_file', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['timestamp', 'execution_time_seconds', 'total_issues', 'critical_issues', 'files_analyzed', 'performance_score', 'cache_hit', 'ci_system'])

    for run in runs:
        writer.writerow([
            run['timestamp'],
            run['execution_time_seconds'],
            run['total_issues'],
            run['critical_issues'],
            run['files_analyzed'],
            run['performance_score'],
            run['cache_hit'],
            run['ci_system']
        ])

print(f"CSV report generated: $report_file")
EOF
}

# Generate Prometheus metrics
generate_prometheus_report() {
    local report_file="${METRICS_DIR}/performance-metrics.prom"

    python3 << EOF
import json
from datetime import datetime

# Read history
with open('$PERFORMANCE_HISTORY') as f:
    history = json.load(f)

runs = history.get('runs', [])
if not runs:
    exit(0)

latest_run = runs[-1]

metrics = f"""# HELP code_review_execution_time_seconds Execution time of code review analysis
# TYPE code_review_execution_time_seconds gauge
code_review_execution_time_seconds{{ci_system="{latest_run['ci_system']}"}} {latest_run['execution_time_seconds']}

# HELP code_review_performance_score Performance score of code review analysis
# TYPE code_review_performance_score gauge
code_review_performance_score{{ci_system="{latest_run['ci_system']}"}} {latest_run['performance_score']}

# HELP code_review_total_issues_found Total issues found in analysis
# TYPE code_review_total_issues_found gauge
code_review_total_issues_found{{ci_system="{latest_run['ci_system']}"}} {latest_run['total_issues']}

# HELP code_review_critical_issues_found Critical issues found in analysis
# TYPE code_review_critical_issues_found gauge
code_review_critical_issues_found{{ci_system="{latest_run['ci_system']}"}} {latest_run['critical_issues']}

# HELP code_review_files_analyzed_count Number of files analyzed
# TYPE code_review_files_analyzed_count gauge
code_review_files_analyzed_count{{ci_system="{latest_run['ci_system']}"}} {latest_run['files_analyzed']}
"""

with open('$report_file', 'w') as f:
    f.write(metrics)

print(f"Prometheus metrics generated: $report_file")
EOF
}

# Main function
main() {
    local execution_time="$1"
    local total_issues="${2:-0}"
    local critical_issues="${3:-0}"
    local files_analyzed="${4:-1}"
    local cache_hit="${5:-false}"
    local ci_system="${6:-unknown}"

    log_info "Starting performance monitoring..."
    log_info "Execution time: ${execution_time}s, Issues: $total_issues/$critical_issues, Files: $files_analyzed"

    # Initialize history if needed
    initialize_history

    # Record current performance
    record_performance "$execution_time" "$total_issues" "$critical_issues" "$files_analyzed" "$cache_hit" "$ci_system"

    # Update baseline
    update_baseline

    # Check for regressions
    local current_score
    current_score=$(calculate_performance_score "$execution_time" "$total_issues" "$files_analyzed")

    local regression_exit_code=0
    if ! check_regressions "$execution_time" "$current_score"; then
        regression_exit_code=1
    fi

    # Generate report
    generate_report "$OUTPUT_FORMAT"

    # Output summary
    log_info "Performance monitoring completed"
    if [[ $regression_exit_code -ne 0 ]]; then
        log_error "Performance regression detected!"
        exit 1
    else
        log_info "Performance within acceptable limits"
        exit 0
    fi
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 <execution_time> [total_issues] [critical_issues] [files_analyzed] [cache_hit] [ci_system]"
        echo "Example: $0 120 15 2 45 true github-actions"
        exit 1
    fi

    main "$@"
fi