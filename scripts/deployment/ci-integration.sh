#!/bin/bash
set -euo pipefail

# =============================================================================
# CI/CD Integration Script for Code Review Assistant
# =============================================================================
# This script provides standardized CI/CD integration with proper exit codes
# and performance metrics for various CI/CD systems.
#
# Exit Codes:
#   0 - Success
#   1 - General failure
#   2 - Quality gate failure
#   3 - Configuration error
#   4 - Performance threshold exceeded
#   5 - Cache/dependency error
# =============================================================================

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CI_SYSTEM="${CI_SYSTEM:-unknown}"
PERFORMANCE_BASELINE="${PERFORMANCE_BASELINE:-120}"
ENABLE_CACHING="${ENABLE_CACHING:-true}"
METRICS_OUTPUT="${METRICS_OUTPUT:-json}"

# Detect CI system
detect_ci_system() {
    if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
        CI_SYSTEM="github-actions"
    elif [[ -n "${GITLAB_CI:-}" ]]; then
        CI_SYSTEM="gitlab-ci"
    elif [[ -n "${JENKINS_URL:-}" ]]; then
        CI_SYSTEM="jenkins"
    elif [[ -n "${CIRCLECI:-}" ]]; then
        CI_SYSTEM="circleci"
    elif [[ -n "${TRAVIS:-}" ]]; then
        CI_SYSTEM="travis"
    else
        CI_SYSTEM="generic"
    fi
}

# Logging functions with CI-specific formatting
log_info() {
    case "$CI_SYSTEM" in
        github-actions)
            echo "::notice::$1"
            ;;
        gitlab-ci)
            echo -e "\e[36m$1\e[0m"
            ;;
        *)
            echo "[INFO] $1"
            ;;
    esac
}

log_error() {
    case "$CI_SYSTEM" in
        github-actions)
            echo "::error::$1"
            ;;
        gitlab-ci)
            echo -e "\e[31m$1\e[0m"
            ;;
        *)
            echo "[ERROR] $1"
            ;;
    esac
}

log_warning() {
    case "$CI_SYSTEM" in
        github-actions)
            echo "::warning::$1"
            ;;
        gitlab-ci)
            echo -e "\e[33m$1\e[0m"
            ;;
        *)
            echo "[WARNING] $1"
            ;;
    esac
}

# Set CI-specific output
set_output() {
    local key="$1"
    local value="$2"

    case "$CI_SYSTEM" in
        github-actions)
            echo "$key=$value" >> "$GITHUB_OUTPUT"
            ;;
        gitlab-ci)
            echo "$key=$value" >> ci_outputs.env
            ;;
        *)
            echo "OUTPUT: $key=$value"
            ;;
    esac
}

# Performance monitoring
track_performance() {
    local stage="$1"
    local start_time="$2"
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_info "Performance: $stage completed in ${duration}s"

    # Check against baseline
    if [[ $duration -gt $PERFORMANCE_BASELINE ]]; then
        log_warning "Performance: $stage exceeded baseline (${duration}s > ${PERFORMANCE_BASELINE}s)"
        return 4
    fi

    return 0
}

# Cache management
setup_cache() {
    if [[ "$ENABLE_CACHING" != "true" ]]; then
        log_info "Caching disabled"
        return 0
    fi

    local cache_dir="${PROJECT_ROOT}/.ci-cache"
    local cache_key="ci-cache-$(sha256sum requirements.txt 2>/dev/null | cut -d' ' -f1 || echo 'nocache')"

    log_info "Setting up cache: $cache_key"

    case "$CI_SYSTEM" in
        github-actions)
            # Cache is handled by GitHub Actions cache action
            log_info "Cache managed by GitHub Actions"
            ;;
        gitlab-ci)
            # Cache is handled by GitLab CI cache configuration
            log_info "Cache managed by GitLab CI"
            ;;
        *)
            # Manual cache management
            mkdir -p "$cache_dir"
            if [[ -f "$cache_dir/dependencies.tar.gz" ]]; then
                log_info "Restoring dependencies from cache"
                tar -xzf "$cache_dir/dependencies.tar.gz" -C "$PROJECT_ROOT" || log_warning "Cache restore failed"
            fi
            ;;
    esac
}

# Quality gate enforcement
quality_gate() {
    local results_file="${PROJECT_ROOT}/combined-results.json"

    if [[ ! -f "$results_file" ]]; then
        log_error "Analysis results not found"
        return 3
    fi

    log_info "Running quality gate checks..."

    # Extract metrics
    local quality_data
    quality_data=$(python3 -c "
import json, sys
try:
    with open('$results_file') as f:
        data = json.load(f)
    summary = data.get('summary', {})
    print(f\"{summary.get('total_issues', 0)} {summary.get('critical_issues', 0)} {summary.get('files_analyzed', 0)}\")
except Exception as e:
    print('0 0 0', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null || echo "0 0 0")

    read -r total_issues critical_issues files_analyzed <<< "$quality_data"

    # Set outputs for CI systems
    set_output "total_issues" "$total_issues"
    set_output "critical_issues" "$critical_issues"
    set_output "files_analyzed" "$files_analyzed"

    log_info "Quality metrics: $total_issues total, $critical_issues critical, $files_analyzed files"

    # Quality gates
    local exit_code=0

    if [[ $critical_issues -gt 5 ]]; then
        log_error "Quality gate failed: $critical_issues critical issues (max: 5)"
        exit_code=2
    fi

    if [[ $total_issues -gt 100 ]]; then
        log_warning "High issue count: $total_issues total issues"
    fi

    # Create quality gate report
    cat > "${PROJECT_ROOT}/quality-gate-report.json" << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "ci_system": "$CI_SYSTEM",
    "quality_gate": {
        "status": "$([ $exit_code -eq 0 ] && echo "passed" || echo "failed")",
        "total_issues": $total_issues,
        "critical_issues": $critical_issues,
        "files_analyzed": $files_analyzed,
        "exit_code": $exit_code
    }
}
EOF

    return $exit_code
}

# Metrics collection and reporting
collect_metrics() {
    log_info "Collecting CI/CD pipeline metrics..."

    local start_time="${CI_START_TIME:-$(date +%s)}"
    local end_time
    end_time=$(date +%s)
    local pipeline_duration=$((end_time - start_time))

    # Determine CI-specific variables
    local pipeline_id repo_url commit_sha branch

    case "$CI_SYSTEM" in
        github-actions)
            pipeline_id="${GITHUB_RUN_ID:-unknown}"
            repo_url="${GITHUB_SERVER_URL:-}/${GITHUB_REPOSITORY:-}"
            commit_sha="${GITHUB_SHA:-unknown}"
            branch="${GITHUB_REF_NAME:-unknown}"
            ;;
        gitlab-ci)
            pipeline_id="${CI_PIPELINE_ID:-unknown}"
            repo_url="${CI_PROJECT_URL:-unknown}"
            commit_sha="${CI_COMMIT_SHA:-unknown}"
            branch="${CI_COMMIT_REF_NAME:-unknown}"
            ;;
        *)
            pipeline_id="unknown"
            repo_url="unknown"
            commit_sha="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
            branch="$(git branch --show-current 2>/dev/null || echo unknown)"
            ;;
    esac

    # Create comprehensive metrics
    local metrics_file="${PROJECT_ROOT}/ci-metrics.json"
    cat > "$metrics_file" << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "ci_system": "$CI_SYSTEM",
    "pipeline_info": {
        "id": "$pipeline_id",
        "repository": "$repo_url",
        "commit_sha": "$commit_sha",
        "branch": "$branch",
        "duration_seconds": $pipeline_duration
    },
    "performance": {
        "baseline_threshold": $PERFORMANCE_BASELINE,
        "pipeline_duration": $pipeline_duration,
        "status": "$([ $pipeline_duration -le $PERFORMANCE_BASELINE ] && echo "within_baseline" || echo "exceeds_baseline")"
    },
    "caching": {
        "enabled": $ENABLE_CACHING,
        "system_managed": "$([ "$CI_SYSTEM" = "github-actions" ] || [ "$CI_SYSTEM" = "gitlab-ci" ] && echo true || echo false)"
    }
}
EOF

    # Output format-specific files
    case "$METRICS_OUTPUT" in
        junit)
            create_junit_report "$metrics_file"
            ;;
        prometheus)
            create_prometheus_metrics "$metrics_file"
            ;;
        *)
            log_info "Metrics saved as JSON: $metrics_file"
            ;;
    esac

    # CI system specific metric outputs
    case "$CI_SYSTEM" in
        github-actions)
            set_output "pipeline_duration" "$pipeline_duration"
            set_output "performance_status" "$([ $pipeline_duration -le $PERFORMANCE_BASELINE ] && echo "ok" || echo "slow")"
            ;;
        gitlab-ci)
            echo "PIPELINE_DURATION=$pipeline_duration" >> ci_outputs.env
            echo "PERFORMANCE_STATUS=$([ $pipeline_duration -le $PERFORMANCE_BASELINE ] && echo "ok" || echo "slow")" >> ci_outputs.env
            ;;
    esac
}

# Create JUnit report for test reporting
create_junit_report() {
    local metrics_file="$1"
    local junit_file="${PROJECT_ROOT}/ci-metrics-junit.xml"

    local duration pipeline_status
    duration=$(jq -r '.pipeline_info.duration_seconds' "$metrics_file")
    pipeline_status=$(jq -r '.performance.status' "$metrics_file")

    cat > "$junit_file" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="CI Metrics" tests="2" failures="$([ "$pipeline_status" = "exceeds_baseline" ] && echo "1" || echo "0")" time="$duration">
    <testsuite name="Performance" tests="1" failures="$([ "$pipeline_status" = "exceeds_baseline" ] && echo "1" || echo "0")" time="$duration">
        <testcase classname="ci.performance" name="pipeline_duration" time="$duration">
            $([ "$pipeline_status" = "exceeds_baseline" ] && echo '<failure message="Pipeline duration exceeds baseline">Performance test failed</failure>' || echo '')
        </testcase>
    </testsuite>
    <testsuite name="Quality" tests="1" failures="0" time="0">
        <testcase classname="ci.quality" name="quality_gate" time="0">
        </testcase>
    </testsuite>
</testsuites>
EOF

    log_info "JUnit report created: $junit_file"
}

# Create Prometheus metrics
create_prometheus_metrics() {
    local metrics_file="$1"
    local prometheus_file="${PROJECT_ROOT}/ci-metrics.prom"

    local duration total_issues critical_issues
    duration=$(jq -r '.pipeline_info.duration_seconds' "$metrics_file")
    total_issues=$(jq -r '.quality_gate.total_issues // 0' "${PROJECT_ROOT}/quality-gate-report.json" 2>/dev/null || echo "0")
    critical_issues=$(jq -r '.quality_gate.critical_issues // 0' "${PROJECT_ROOT}/quality-gate-report.json" 2>/dev/null || echo "0")

    cat > "$prometheus_file" << EOF
# HELP ci_pipeline_duration_seconds Duration of CI pipeline execution
# TYPE ci_pipeline_duration_seconds gauge
ci_pipeline_duration_seconds{ci_system="$CI_SYSTEM"} $duration

# HELP ci_code_review_total_issues Total number of issues found
# TYPE ci_code_review_total_issues gauge
ci_code_review_total_issues{ci_system="$CI_SYSTEM"} $total_issues

# HELP ci_code_review_critical_issues Number of critical issues found
# TYPE ci_code_review_critical_issues gauge
ci_code_review_critical_issues{ci_system="$CI_SYSTEM"} $critical_issues
EOF

    log_info "Prometheus metrics created: $prometheus_file"
}

# Main CI integration function
main() {
    local exit_code=0
    CI_START_TIME="${CI_START_TIME:-$(date +%s)}"

    # Detect CI system
    detect_ci_system
    log_info "Detected CI system: $CI_SYSTEM"

    # Setup cache
    if ! setup_cache; then
        log_warning "Cache setup failed, continuing without cache"
    fi

    # Run quality gate
    if ! quality_gate; then
        exit_code=$?
        log_error "Quality gate failed with exit code: $exit_code"
    fi

    # Check performance
    local perf_start
    perf_start=$(date +%s)
    if ! track_performance "pipeline" "$CI_START_TIME"; then
        if [[ $exit_code -eq 0 ]]; then
            exit_code=4
        fi
    fi

    # Collect metrics
    collect_metrics

    # Final status
    if [[ $exit_code -eq 0 ]]; then
        log_info "CI integration completed successfully"
        set_output "ci_status" "success"
    else
        log_error "CI integration failed with exit code: $exit_code"
        set_output "ci_status" "failed"
        set_output "exit_code" "$exit_code"
    fi

    # Write final exit code for external systems
    echo "$exit_code" > "${PROJECT_ROOT}/ci-exit-code.txt"

    exit $exit_code
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi