"""
Review Orchestrator

Orchestrates the complete code review process including git integration,
platform-specific commenting, and workflow-aware analysis.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass

from .diff_parser import GitCommands, GitDiffParser
from .focused_review import FocusedReviewAnalyzer, FocusedReviewResult
from .commit_generator import CommitMessageGenerator
from .workflow_handlers import GitWorkflowHandler, ReviewContext
from .platforms.github_integration import GitHubIntegration
from .platforms.gitlab_integration import GitLabIntegration
from ..utils.logger import get_logger


@dataclass
class ReviewRequest:
    """Request for code review analysis."""
    repository_path: Optional[Path] = None
    repository_url: Optional[str] = None
    base_ref: str = "main"
    head_ref: Optional[str] = None
    pr_number: Optional[int] = None
    platform: Optional[str] = None  # 'github' or 'gitlab'
    post_comments: bool = False
    github_token: Optional[str] = None
    gitlab_token: Optional[str] = None
    gitlab_url: Optional[str] = None


@dataclass
class ReviewResponse:
    """Complete code review response."""
    review_result: FocusedReviewResult
    workflow_summary: Dict[str, Any]
    commit_suggestions: List[str]
    platform_results: Optional[Dict[str, Any]] = None
    next_actions: List[str] = None


class ReviewOrchestrator:
    """Orchestrates complete code review workflow with git and platform integration."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

        # Initialize core components
        self.diff_parser = GitDiffParser()
        self.focused_analyzer = FocusedReviewAnalyzer(config)
        self.commit_generator = CommitMessageGenerator()
        self.workflow_handler = GitWorkflowHandler(config)

    async def conduct_review(self, request: ReviewRequest) -> ReviewResponse:
        """
        Conduct a complete code review.

        Args:
            request: Review request with all parameters

        Returns:
            Complete review response
        """
        self.logger.info("Starting comprehensive code review")

        try:
            # Step 1: Setup and validation
            repo_path, git_commands = self._setup_repository(request)

            # Step 2: Get the diff
            diff_text = await self._get_diff(request, git_commands)
            if not diff_text.strip():
                return self._create_empty_review_response("No changes found")

            # Step 3: Analyze the diff with focused review
            review_result = self.focused_analyzer.analyze_diff(diff_text, repo_path)

            # Step 4: Generate commit message suggestions
            diff_result = self.diff_parser.parse_diff(diff_text)
            commit_suggestions = self.commit_generator.generate_commit_messages(diff_result)

            # Step 5: Create workflow context
            context = self._create_review_context(request, git_commands)

            # Step 6: Get workflow-specific analysis
            workflow_summary = self.workflow_handler.generate_workflow_summary(context)
            next_actions = self.workflow_handler.suggest_next_actions(context, {
                "issues": review_result.issues,
                "suggestions": review_result.suggestions
            })

            # Step 7: Post comments to platform if requested
            platform_results = None
            if request.post_comments and request.platform and request.pr_number:
                platform_results = await self._post_platform_comments(request, review_result)

            return ReviewResponse(
                review_result=review_result,
                workflow_summary=workflow_summary,
                commit_suggestions=commit_suggestions,
                platform_results=platform_results,
                next_actions=next_actions
            )

        except Exception as e:
            self.logger.error(f"Error conducting review: {e}")
            raise

    async def review_pull_request(self,
                                repository_url: str,
                                pr_number: int,
                                platform: str,
                                token: str,
                                post_comments: bool = False,
                                gitlab_url: Optional[str] = None) -> ReviewResponse:
        """
        Review a pull request or merge request.

        Args:
            repository_url: Repository URL
            pr_number: Pull/Merge request number
            platform: 'github' or 'gitlab'
            token: API token
            post_comments: Whether to post comments
            gitlab_url: GitLab instance URL (if not gitlab.com)

        Returns:
            Review response
        """
        request = ReviewRequest(
            repository_url=repository_url,
            pr_number=pr_number,
            platform=platform,
            post_comments=post_comments,
            github_token=token if platform == 'github' else None,
            gitlab_token=token if platform == 'gitlab' else None,
            gitlab_url=gitlab_url
        )

        return await self.conduct_review(request)

    async def review_local_changes(self,
                                 repository_path: Path,
                                 base_ref: str = "HEAD",
                                 head_ref: Optional[str] = None) -> ReviewResponse:
        """
        Review local repository changes.

        Args:
            repository_path: Path to local repository
            base_ref: Base reference for comparison
            head_ref: Head reference (None for working directory)

        Returns:
            Review response
        """
        request = ReviewRequest(
            repository_path=repository_path,
            base_ref=base_ref,
            head_ref=head_ref
        )

        return await self.conduct_review(request)

    def _setup_repository(self, request: ReviewRequest) -> Tuple[Optional[Path], GitCommands]:
        """Setup repository access."""
        if request.repository_path:
            repo_path = request.repository_path
            git_commands = GitCommands(repo_path)
        else:
            # For remote repositories, we'll work without local access
            repo_path = None
            git_commands = GitCommands()

        return repo_path, git_commands

    async def _get_diff(self, request: ReviewRequest, git_commands: GitCommands) -> str:
        """Get diff text based on request type."""
        if request.repository_path:
            # Local repository
            return git_commands.get_diff(request.base_ref, request.head_ref)

        elif request.repository_url and request.pr_number and request.platform:
            # Remote PR/MR
            if request.platform == 'github' and request.github_token:
                return await self._get_github_pr_diff(request)
            elif request.platform == 'gitlab' and request.gitlab_token:
                return await self._get_gitlab_mr_diff(request)

        raise ValueError("Insufficient information to retrieve diff")

    async def _get_github_pr_diff(self, request: ReviewRequest) -> str:
        """Get GitHub pull request diff."""
        github = GitHubIntegration(request.github_token)
        repo_info = await github.parse_github_url(request.repository_url)

        if not repo_info:
            raise ValueError(f"Could not parse GitHub URL: {request.repository_url}")

        diff_text = await github.get_pull_request_diff(
            repo_info.owner, repo_info.name, request.pr_number
        )

        if not diff_text:
            raise ValueError(f"Could not retrieve diff for PR #{request.pr_number}")

        return diff_text

    async def _get_gitlab_mr_diff(self, request: ReviewRequest) -> str:
        """Get GitLab merge request diff."""
        gitlab = GitLabIntegration(request.gitlab_token, request.gitlab_url or "https://gitlab.com")
        repo_info = await gitlab.parse_gitlab_url(request.repository_url)

        if not repo_info:
            raise ValueError(f"Could not parse GitLab URL: {request.repository_url}")

        diff_text = await gitlab.get_merge_request_diff(repo_info.id, request.pr_number)

        if not diff_text:
            raise ValueError(f"Could not retrieve diff for MR #{request.pr_number}")

        return diff_text

    def _create_review_context(self, request: ReviewRequest, git_commands: GitCommands) -> ReviewContext:
        """Create review context from request."""
        try:
            current_branch = git_commands.get_current_branch() if request.repository_path else "unknown"
            target_branch = request.base_ref

            return self.workflow_handler.create_review_context(
                source_branch=current_branch,
                target_branch=target_branch,
                pr_number=request.pr_number,
                repository_url=request.repository_url
            )

        except Exception as e:
            self.logger.warning(f"Could not create full review context: {e}")
            # Return minimal context
            return self.workflow_handler.create_review_context("unknown", "main")

    async def _post_platform_comments(self,
                                    request: ReviewRequest,
                                    review_result: FocusedReviewResult) -> Dict[str, Any]:
        """Post comments to the appropriate platform."""
        if not review_result.issues:
            return {"message": "No issues to comment on", "comments_posted": 0}

        if request.platform == 'github' and request.github_token:
            return await self._post_github_comments(request, review_result)
        elif request.platform == 'gitlab' and request.gitlab_token:
            return await self._post_gitlab_comments(request, review_result)
        else:
            return {"error": "Invalid platform or missing token"}

    async def _post_github_comments(self,
                                  request: ReviewRequest,
                                  review_result: FocusedReviewResult) -> Dict[str, Any]:
        """Post comments to GitHub."""
        github = GitHubIntegration(request.github_token)
        repo_info = await github.parse_github_url(request.repository_url)

        if not repo_info:
            return {"error": "Could not parse repository information"}

        return await github.post_review_comments(
            repo_info.owner,
            repo_info.name,
            request.pr_number,
            review_result.issues
        )

    async def _post_gitlab_comments(self,
                                  request: ReviewRequest,
                                  review_result: FocusedReviewResult) -> Dict[str, Any]:
        """Post comments to GitLab."""
        gitlab = GitLabIntegration(request.gitlab_token, request.gitlab_url or "https://gitlab.com")
        repo_info = await gitlab.parse_gitlab_url(request.repository_url)

        if not repo_info:
            return {"error": "Could not parse repository information"}

        # Get MR info to get SHAs
        mr_info = await gitlab.get_merge_request(repo_info.id, request.pr_number)
        if not mr_info:
            return {"error": "Could not retrieve merge request information"}

        return await gitlab.post_review_comments(
            repo_info.id,
            request.pr_number,
            review_result.issues,
            mr_info.diff_refs.get("base_sha", ""),
            mr_info.diff_refs.get("head_sha", ""),
            mr_info.diff_refs.get("start_sha", "")
        )

    def _create_empty_review_response(self, message: str) -> ReviewResponse:
        """Create empty review response."""
        empty_result = FocusedReviewResult(
            diff_summary={"message": message},
            issues=[],
            suggestions=[],
            files_reviewed=0,
            lines_reviewed=0,
            commit_message_suggestions=[]
        )

        return ReviewResponse(
            review_result=empty_result,
            workflow_summary={"message": message},
            commit_suggestions=[],
            next_actions=[]
        )

    def get_review_summary(self, response: ReviewResponse) -> Dict[str, Any]:
        """Get a comprehensive summary of the review."""
        review_result = response.review_result

        return {
            "overview": {
                "files_reviewed": review_result.files_reviewed,
                "lines_reviewed": review_result.lines_reviewed,
                "total_issues": len(review_result.issues),
                "total_suggestions": len(review_result.suggestions)
            },
            "issue_breakdown": {
                "critical": len([i for i in review_result.issues if i.severity == 'error']),
                "warnings": len([i for i in review_result.issues if i.severity == 'warning']),
                "info": len([i for i in review_result.issues if i.severity == 'info'])
            },
            "diff_stats": review_result.diff_summary,
            "workflow_info": response.workflow_summary,
            "commit_suggestions": response.commit_suggestions[:3],  # Top 3
            "next_actions": response.next_actions,
            "platform_integration": {
                "comments_posted": response.platform_results.get("comments_created", 0) if response.platform_results else 0,
                "posting_errors": len(response.platform_results.get("errors", [])) if response.platform_results else 0
            }
        }

    async def batch_review_pull_requests(self,
                                       requests: List[Dict[str, Any]]) -> List[ReviewResponse]:
        """Review multiple pull requests in batch."""
        tasks = []

        for req_data in requests:
            request = ReviewRequest(**req_data)
            task = asyncio.create_task(self.conduct_review(request))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        responses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch review {i} failed: {result}")
                responses.append(self._create_empty_review_response(f"Review failed: {result}"))
            else:
                responses.append(result)

        return responses