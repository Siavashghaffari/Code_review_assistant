#!/bin/bash
set -euo pipefail

# =============================================================================
# Code Review Assistant - Deployment Script
# =============================================================================
# This script handles deployment with comprehensive error handling and exit codes
#
# Exit Codes:
#   0 - Success
#   1 - General deployment error
#   2 - Quality gate failure (too many critical issues)
#   3 - Configuration error
#   4 - Timeout error
#   5 - Permission/authentication error
# =============================================================================

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_TIMEOUT="${DEPLOYMENT_TIMEOUT:-300}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
FORCE_DEPLOY="${FORCE_DEPLOY:-false}"
CRITICAL_ISSUE_THRESHOLD="${CRITICAL_ISSUE_THRESHOLD:-5}"
TOTAL_ISSUE_THRESHOLD="${TOTAL_ISSUE_THRESHOLD:-50}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Exit code handler
exit_with_code() {
    local code=$1
    local message="$2"

    case $code in
        0)
            log_success "$message"
            ;;
        1)
            log_error "$message (General Error)"
            ;;
        2)
            log_error "$message (Quality Gate Failure)"
            ;;
        3)
            log_error "$message (Configuration Error)"
            ;;
        4)
            log_error "$message (Timeout Error)"
            ;;
        5)
            log_error "$message (Permission/Authentication Error)"
            ;;
        *)
            log_error "$message (Unknown Error: $code)"
            ;;
    esac

    # Write exit code to file for CI/CD systems
    echo "$code" > "${PROJECT_ROOT}/deployment-exit-code.txt"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): Deployment finished with exit code $code" >> "${PROJECT_ROOT}/deployment.log"

    exit $code
}

# Validate configuration
validate_config() {
    log_info "Validating deployment configuration..."

    # Check required files
    local required_files=(
        "${PROJECT_ROOT}/combined-results.json"
        "${PROJECT_ROOT}/.codereview.yaml"
        "${PROJECT_ROOT}/requirements.txt"
    )

    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            exit_with_code 3 "Required file not found: $file"
        fi
    done

    # Validate environment
    case "$ENVIRONMENT" in
        staging|production|development)
            log_info "Deploying to environment: $ENVIRONMENT"
            ;;
        *)
            exit_with_code 3 "Invalid environment: $ENVIRONMENT. Must be staging, production, or development"
            ;;
    esac

    log_success "Configuration validation passed"
}

# Quality gate check
quality_gate_check() {
    log_info "Running quality gate checks..."

    local results_file="${PROJECT_ROOT}/combined-results.json"

    if [[ ! -f "$results_file" ]]; then
        exit_with_code 3 "Analysis results not found: $results_file"
    fi

    # Extract metrics using Python
    local metrics
    metrics=$(python3 -c "
import json, sys
try:
    with open('$results_file') as f:
        data = json.load(f)
    summary = data.get('summary', {})
    print(f\"{summary.get('total_issues', 0)} {summary.get('critical_issues', 0)}\")
except Exception as e:
    print('0 0', file=sys.stderr)
    sys.exit(1)
")

    if [[ $? -ne 0 ]]; then
        exit_with_code 1 "Failed to parse analysis results"
    fi

    read -r total_issues critical_issues <<< "$metrics"

    log_info "Quality gate metrics:"
    log_info "  - Total issues: $total_issues (threshold: $TOTAL_ISSUE_THRESHOLD)"
    log_info "  - Critical issues: $critical_issues (threshold: $CRITICAL_ISSUE_THRESHOLD)"

    # Check quality gates
    if [[ "$FORCE_DEPLOY" != "true" ]]; then
        if [[ $critical_issues -gt $CRITICAL_ISSUE_THRESHOLD ]]; then
            exit_with_code 2 "Quality gate failed: $critical_issues critical issues exceed threshold ($CRITICAL_ISSUE_THRESHOLD)"
        fi

        if [[ $total_issues -gt $TOTAL_ISSUE_THRESHOLD ]]; then
            log_warning "High number of issues: $total_issues (threshold: $TOTAL_ISSUE_THRESHOLD)"
            log_warning "Proceeding with deployment but consider addressing these issues"
        fi
    else
        log_warning "Quality gates bypassed due to FORCE_DEPLOY=true"
    fi

    log_success "Quality gate check passed"
}

# Pre-deployment preparations
prepare_deployment() {
    log_info "Preparing deployment package..."

    # Create deployment directory
    local deploy_dir="${PROJECT_ROOT}/deployment"
    mkdir -p "$deploy_dir"

    # Copy necessary files
    cp "${PROJECT_ROOT}/combined-results.json" "$deploy_dir/data.json"
    cp "${PROJECT_ROOT}/dashboard.html" "$deploy_dir/index.html" 2>/dev/null || log_warning "Dashboard not found, skipping"

    # Create deployment manifest
    cat > "$deploy_dir/deployment-info.json" << EOF
{
    "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "environment": "$ENVIRONMENT",
    "version": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "branch": "$(git branch --show-current 2>/dev/null || echo 'unknown')",
    "deployer": "$(whoami)",
    "force_deploy": $FORCE_DEPLOY,
    "quality_metrics": {
        "total_issues": $total_issues,
        "critical_issues": $critical_issues
    }
}
EOF

    log_success "Deployment package prepared"
}

# Execute deployment with timeout
execute_deployment() {
    log_info "Starting deployment to $ENVIRONMENT environment..."

    local start_time
    start_time=$(date +%s)

    # Use timeout to prevent hanging deployments
    if timeout "$DEPLOYMENT_TIMEOUT" bash -c "
        set -euo pipefail

        # Simulate deployment steps (replace with actual deployment logic)
        echo 'Building application...'
        sleep 2

        echo 'Running pre-deployment tests...'
        sleep 1

        case '$ENVIRONMENT' in
            staging)
                echo 'Deploying to staging environment...'
                # Add staging-specific deployment commands here
                sleep 3
                echo 'Staging deployment completed'
                ;;
            production)
                echo 'Deploying to production environment...'
                # Add production-specific deployment commands here
                sleep 5
                echo 'Production deployment completed'
                ;;
            development)
                echo 'Deploying to development environment...'
                # Add development-specific deployment commands here
                sleep 1
                echo 'Development deployment completed'
                ;;
        esac

        echo 'Running post-deployment verification...'
        sleep 2
        echo 'Deployment verification passed'
    "; then
        local end_time
        end_time=$(date +%s)
        local duration=$((end_time - start_time))

        log_success "Deployment completed successfully in ${duration}s"

        # Write deployment success metrics
        cat > "${PROJECT_ROOT}/deployment-metrics.json" << EOF
{
    "deployment_time": $duration,
    "environment": "$ENVIRONMENT",
    "status": "success",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    else
        local exit_code=$?
        if [[ $exit_code -eq 124 ]]; then
            exit_with_code 4 "Deployment timed out after ${DEPLOYMENT_TIMEOUT}s"
        else
            exit_with_code 1 "Deployment failed during execution"
        fi
    fi
}

# Post-deployment verification
verify_deployment() {
    log_info "Verifying deployment..."

    # Add environment-specific verification
    case "$ENVIRONMENT" in
        staging)
            # Verify staging environment
            log_info "Verifying staging deployment..."
            # Add staging-specific checks here
            ;;
        production)
            # Verify production environment
            log_info "Verifying production deployment..."
            # Add production-specific checks here
            ;;
        development)
            # Verify development environment
            log_info "Verifying development deployment..."
            # Add development-specific checks here
            ;;
    esac

    log_success "Deployment verification completed"
}

# Cleanup function
cleanup() {
    log_info "Performing cleanup..."

    # Clean temporary files but preserve logs and metrics
    local temp_files=(
        "${PROJECT_ROOT}/temp_deploy"
        "${PROJECT_ROOT}/.deploy_cache"
    )

    for file in "${temp_files[@]}"; do
        if [[ -e "$file" ]]; then
            rm -rf "$file"
            log_info "Cleaned up: $file"
        fi
    done

    log_success "Cleanup completed"
}

# Main deployment function
main() {
    log_info "Starting Code Review Assistant deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Force Deploy: $FORCE_DEPLOY"
    log_info "Timeout: ${DEPLOYMENT_TIMEOUT}s"
    echo "================================"

    # Trap to ensure cleanup runs on exit
    trap cleanup EXIT

    # Execute deployment steps
    validate_config
    quality_gate_check
    prepare_deployment
    execute_deployment
    verify_deployment

    exit_with_code 0 "Deployment completed successfully"
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi