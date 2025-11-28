"""
Git Workflow Handlers

Handles different git workflow patterns including feature branches,
main branch protection, pull requests, and merge requests.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from .diff_parser import GitCommands, GitDiffParser
from .focused_review import FocusedReviewAnalyzer
from .commit_generator import CommitMessageGenerator
from .platforms.github_integration import GitHubIntegration, GitHubRepo
from .platforms.gitlab_integration import GitLabIntegration, GitLabRepo
from ..utils.logger import get_logger


class WorkflowType(Enum):
    """Git workflow types."""
    FEATURE_BRANCH = "feature_branch"
    GITFLOW = "gitflow"
    GITHUB_FLOW = "github_flow"
    GITLAB_FLOW = "gitlab_flow"
    TRUNK_BASED = "trunk_based"


class BranchType(Enum):
    """Branch types in different workflows."""
    MAIN = "main"
    DEVELOP = "develop"
    FEATURE = "feature"
    HOTFIX = "hotfix"
    RELEASE = "release"
    BUGFIX = "bugfix"


@dataclass
class WorkflowConfig:
    """Configuration for git workflow handling."""
    workflow_type: WorkflowType
    protected_branches: List[str]
    feature_branch_pattern: str
    require_pr: bool
    auto_merge: bool
    require_reviews: int
    require_status_checks: bool


@dataclass
class BranchInfo:
    """Information about a git branch."""
    name: str
    branch_type: BranchType
    is_protected: bool
    upstream_branch: Optional[str]
    commits_ahead: int
    commits_behind: int


@dataclass
class ReviewContext:
    """Context information for code review."""
    workflow_type: WorkflowType
    source_branch: BranchInfo
    target_branch: BranchInfo
    is_pull_request: bool
    pr_number: Optional[int]
    repository_info: Optional[Union[GitHubRepo, GitLabRepo]]


class GitWorkflowHandler:
    """Handles different git workflow patterns and integrations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

        # Initialize components
        self.git_commands = GitCommands()
        self.diff_parser = GitDiffParser()
        self.focused_analyzer = FocusedReviewAnalyzer(config)
        self.commit_generator = CommitMessageGenerator()

        # Platform integrations (initialized when needed)
        self.github_integration = None
        self.gitlab_integration = None

        # Default workflow configurations
        self.workflow_configs = {
            WorkflowType.FEATURE_BRANCH: WorkflowConfig(
                workflow_type=WorkflowType.FEATURE_BRANCH,
                protected_branches=["main", "master"],
                feature_branch_pattern=r"feature/.*",
                require_pr=True,
                auto_merge=False,
                require_reviews=1,
                require_status_checks=True
            ),
            WorkflowType.GITHUB_FLOW: WorkflowConfig(
                workflow_type=WorkflowType.GITHUB_FLOW,
                protected_branches=["main"],
                feature_branch_pattern=r".*",
                require_pr=True,
                auto_merge=False,
                require_reviews=1,
                require_status_checks=True
            ),
            WorkflowType.GITFLOW: WorkflowConfig(
                workflow_type=WorkflowType.GITFLOW,
                protected_branches=["main", "develop"],
                feature_branch_pattern=r"feature/.*",
                require_pr=True,
                auto_merge=False,
                require_reviews=2,
                require_status_checks=True
            )
        }

    def detect_workflow(self, repo_path: Optional[Path] = None) -> WorkflowType:
        """
        Detect the git workflow type based on repository structure.

        Args:
            repo_path: Path to git repository

        Returns:
            Detected workflow type
        """
        if repo_path:
            self.git_commands = GitCommands(repo_path)

        try:
            # Get branch information
            current_branch = self.git_commands.get_current_branch()
            remote_url = self.git_commands.get_remote_url()

            # Check for GitFlow branches
            if self._has_gitflow_structure():
                return WorkflowType.GITFLOW

            # Check for GitHub/GitLab
            if "github.com" in remote_url:
                return WorkflowType.GITHUB_FLOW
            elif "gitlab.com" in remote_url or "gitlab" in remote_url:
                return WorkflowType.GITLAB_FLOW

            # Default to feature branch workflow
            return WorkflowType.FEATURE_BRANCH

        except Exception as e:
            self.logger.warning(f"Could not detect workflow: {e}")
            return WorkflowType.FEATURE_BRANCH

    def _has_gitflow_structure(self) -> bool:
        """Check if repository has GitFlow structure."""
        try:
            # Run git branch command to get all branches
            import subprocess
            result = subprocess.run(
                ["git", "branch", "-a"],
                cwd=self.git_commands.repo_path,
                capture_output=True,
                text=True
            )

            branches = result.stdout
            return "develop" in branches and any(
                pattern in branches for pattern in ["feature/", "release/", "hotfix/"]
            )

        except Exception:
            return False

    def analyze_branch_info(self, branch_name: str) -> BranchInfo:
        """Analyze branch information and classify branch type."""
        branch_type = self._classify_branch_type(branch_name)
        is_protected = self._is_protected_branch(branch_name)

        try:
            # Get upstream information
            upstream_info = self._get_upstream_info(branch_name)

            return BranchInfo(
                name=branch_name,
                branch_type=branch_type,
                is_protected=is_protected,
                upstream_branch=upstream_info.get("upstream"),
                commits_ahead=upstream_info.get("ahead", 0),
                commits_behind=upstream_info.get("behind", 0)
            )

        except Exception as e:
            self.logger.warning(f"Error analyzing branch {branch_name}: {e}")
            return BranchInfo(
                name=branch_name,
                branch_type=branch_type,
                is_protected=is_protected,
                upstream_branch=None,
                commits_ahead=0,
                commits_behind=0
            )

    def _classify_branch_type(self, branch_name: str) -> BranchType:
        """Classify branch type based on name patterns."""
        branch_patterns = {
            BranchType.MAIN: [r"^(main|master)$"],
            BranchType.DEVELOP: [r"^(develop|dev)$"],
            BranchType.FEATURE: [r"^feature/.*", r"^feat/.*"],
            BranchType.HOTFIX: [r"^hotfix/.*", r"^fix/.*"],
            BranchType.RELEASE: [r"^release/.*", r"^rel/.*"],
            BranchType.BUGFIX: [r"^bugfix/.*", r"^bug/.*"]
        }

        for branch_type, patterns in branch_patterns.items():
            if any(re.match(pattern, branch_name, re.IGNORECASE) for pattern in patterns):
                return branch_type

        return BranchType.FEATURE  # Default

    def _is_protected_branch(self, branch_name: str) -> bool:
        """Check if branch is protected based on workflow configuration."""
        workflow_type = self.detect_workflow()
        workflow_config = self.workflow_configs.get(workflow_type)

        if workflow_config:
            return branch_name in workflow_config.protected_branches

        return branch_name in ["main", "master", "develop"]

    def _get_upstream_info(self, branch_name: str) -> Dict[str, Any]:
        """Get upstream tracking information for a branch."""
        try:
            import subprocess

            # Get upstream branch
            upstream_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", f"{branch_name}@{{upstream}}"],
                cwd=self.git_commands.repo_path,
                capture_output=True,
                text=True
            )

            upstream_branch = upstream_result.stdout.strip() if upstream_result.returncode == 0 else None

            # Get ahead/behind count
            if upstream_branch:
                count_result = subprocess.run(
                    ["git", "rev-list", "--count", "--left-right", f"{upstream_branch}...{branch_name}"],
                    cwd=self.git_commands.repo_path,
                    capture_output=True,
                    text=True
                )

                if count_result.returncode == 0:
                    counts = count_result.stdout.strip().split()
                    behind = int(counts[0]) if len(counts) > 0 else 0
                    ahead = int(counts[1]) if len(counts) > 1 else 0
                else:
                    behind, ahead = 0, 0
            else:
                behind, ahead = 0, 0

            return {
                "upstream": upstream_branch,
                "ahead": ahead,
                "behind": behind
            }

        except Exception as e:
            self.logger.warning(f"Error getting upstream info: {e}")
            return {"upstream": None, "ahead": 0, "behind": 0}

    def create_review_context(self,
                            source_branch: str,
                            target_branch: str,
                            pr_number: Optional[int] = None,
                            repository_url: Optional[str] = None) -> ReviewContext:
        """Create review context for workflow-aware analysis."""
        workflow_type = self.detect_workflow()

        source_info = self.analyze_branch_info(source_branch)
        target_info = self.analyze_branch_info(target_branch)

        # Get repository information if URL provided
        repository_info = None
        if repository_url:
            if "github.com" in repository_url:
                repository_info = self._parse_github_url(repository_url)
            elif "gitlab.com" in repository_url or "gitlab" in repository_url:
                repository_info = self._parse_gitlab_url(repository_url)

        return ReviewContext(
            workflow_type=workflow_type,
            source_branch=source_info,
            target_branch=target_info,
            is_pull_request=pr_number is not None,
            pr_number=pr_number,
            repository_info=repository_info
        )

    def get_review_strategy(self, context: ReviewContext) -> Dict[str, Any]:
        """Get review strategy based on workflow context."""
        strategy = {
            "focus_areas": [],
            "severity_threshold": "info",
            "require_approval": False,
            "auto_merge_eligible": False,
            "comment_style": "inline"
        }

        # Adjust strategy based on target branch
        if context.target_branch.is_protected:
            strategy["severity_threshold"] = "warning"
            strategy["require_approval"] = True
            strategy["focus_areas"].extend(["security", "performance", "breaking_changes"])

        # Adjust based on branch types
        if context.target_branch.branch_type == BranchType.MAIN:
            strategy["severity_threshold"] = "error"
            strategy["focus_areas"].extend(["tests", "documentation"])

        elif context.target_branch.branch_type == BranchType.DEVELOP:
            strategy["severity_threshold"] = "warning"
            strategy["focus_areas"].extend(["code_quality", "maintainability"])

        # Adjust based on workflow type
        if context.workflow_type == WorkflowType.TRUNK_BASED:
            strategy["auto_merge_eligible"] = True
            strategy["severity_threshold"] = "error"

        elif context.workflow_type == WorkflowType.GITFLOW:
            strategy["require_approval"] = True
            strategy["focus_areas"].append("compatibility")

        return strategy

    def validate_workflow_compliance(self, context: ReviewContext) -> List[Dict[str, Any]]:
        """Validate compliance with workflow rules."""
        violations = []
        workflow_config = self.workflow_configs.get(context.workflow_type)

        if not workflow_config:
            return violations

        # Check if PR is required for protected branches
        if (context.target_branch.is_protected and
            workflow_config.require_pr and
            not context.is_pull_request):

            violations.append({
                "type": "missing_pull_request",
                "severity": "error",
                "message": f"Pull request required for changes to {context.target_branch.name}",
                "suggestion": "Create a pull request to merge these changes"
            })

        # Check feature branch naming
        if context.source_branch.branch_type == BranchType.FEATURE:
            if not re.match(workflow_config.feature_branch_pattern, context.source_branch.name):
                violations.append({
                    "type": "invalid_branch_name",
                    "severity": "warning",
                    "message": f"Branch name doesn't follow pattern: {workflow_config.feature_branch_pattern}",
                    "suggestion": f"Rename branch to match pattern: {workflow_config.feature_branch_pattern}"
                })

        # Check if source branch is up to date
        if context.source_branch.commits_behind > 0:
            violations.append({
                "type": "branch_behind",
                "severity": "warning",
                "message": f"Source branch is {context.source_branch.commits_behind} commits behind target",
                "suggestion": f"Update branch with latest changes from {context.target_branch.name}"
            })

        return violations

    def _parse_github_url(self, url: str) -> Optional[str]:
        """Parse GitHub URL - placeholder for actual implementation."""
        # This would use GitHubIntegration if available
        return url

    def _parse_gitlab_url(self, url: str) -> Optional[str]:
        """Parse GitLab URL - placeholder for actual implementation."""
        # This would use GitLabIntegration if available
        return url

    def suggest_next_actions(self, context: ReviewContext, review_results: Dict[str, Any]) -> List[str]:
        """Suggest next actions based on workflow and review results."""
        suggestions = []

        # Based on review results
        critical_issues = len([i for i in review_results.get("issues", []) if i.get("severity") == "error"])
        warning_issues = len([i for i in review_results.get("issues", []) if i.get("severity") == "warning"])

        if critical_issues > 0:
            suggestions.append(f"🔴 Address {critical_issues} critical issues before merging")

        if warning_issues > 0:
            suggestions.append(f"🟡 Consider fixing {warning_issues} code quality issues")

        # Based on workflow
        if context.target_branch.is_protected:
            if not context.is_pull_request:
                suggestions.append("📝 Create a pull request for code review")
            else:
                suggestions.append("👥 Request review from team members")

        # Based on branch status
        if context.source_branch.commits_behind > 0:
            suggestions.append(f"🔄 Update branch with latest {context.target_branch.name} changes")

        # Workflow-specific suggestions
        if context.workflow_type == WorkflowType.GITFLOW:
            if context.source_branch.branch_type == BranchType.FEATURE:
                suggestions.append("🔀 Merge to develop branch first for integration testing")

        elif context.workflow_type == WorkflowType.GITHUB_FLOW:
            suggestions.append("✅ Ensure all status checks pass before merging")

        return suggestions

    def generate_workflow_summary(self, context: ReviewContext) -> Dict[str, Any]:
        """Generate a summary of workflow information."""
        return {
            "workflow_type": context.workflow_type.value,
            "source_branch": {
                "name": context.source_branch.name,
                "type": context.source_branch.branch_type.value,
                "is_protected": context.source_branch.is_protected,
                "commits_ahead": context.source_branch.commits_ahead,
                "commits_behind": context.source_branch.commits_behind
            },
            "target_branch": {
                "name": context.target_branch.name,
                "type": context.target_branch.branch_type.value,
                "is_protected": context.target_branch.is_protected
            },
            "is_pull_request": context.is_pull_request,
            "pr_number": context.pr_number,
            "compliance_violations": self.validate_workflow_compliance(context)
        }