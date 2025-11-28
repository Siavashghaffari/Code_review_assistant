"""
GitHub API Integration

Integrates with GitHub API to fetch repository information, create pull request
reviews, and post comments on specific lines of code.
"""

import re
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
import aiohttp

from ...utils.logger import get_logger
from ..focused_review import FocusedIssue


@dataclass
class GitHubRepo:
    """GitHub repository information."""
    owner: str
    name: str
    full_name: str
    default_branch: str
    clone_url: str
    api_url: str


@dataclass
class PullRequest:
    """Pull request information."""
    number: int
    title: str
    body: str
    base_branch: str
    head_branch: str
    base_sha: str
    head_sha: str
    state: str
    url: str


@dataclass
class ReviewComment:
    """Pull request review comment."""
    path: str
    line: int
    body: str
    side: str = "RIGHT"  # RIGHT for new lines, LEFT for old lines


class GitHubIntegration:
    """GitHub API integration for code review features."""

    def __init__(self, token: str):
        self.token = token
        self.logger = get_logger(__name__)
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Code-Review-Assistant"
        }

    async def parse_github_url(self, url: str) -> Optional[GitHubRepo]:
        """
        Parse GitHub URL to extract repository information.

        Args:
            url: GitHub repository URL

        Returns:
            GitHubRepo object or None if invalid
        """
        # Handle different GitHub URL formats
        patterns = [
            r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$',
            r'github\.com/([^/]+)/([^/]+)/?$'
        ]

        for pattern in patterns:
            match = re.match(pattern, url.strip())
            if match:
                owner, repo = match.groups()
                return await self._fetch_repo_info(owner, repo)

        self.logger.warning(f"Could not parse GitHub URL: {url}")
        return None

    async def _fetch_repo_info(self, owner: str, repo: str) -> Optional[GitHubRepo]:
        """Fetch repository information from GitHub API."""
        url = f"{self.base_url}/repos/{owner}/{repo}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return GitHubRepo(
                            owner=data['owner']['login'],
                            name=data['name'],
                            full_name=data['full_name'],
                            default_branch=data['default_branch'],
                            clone_url=data['clone_url'],
                            api_url=data['url']
                        )
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitHub API error {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error fetching repo info: {e}")
            return None

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Optional[PullRequest]:
        """Get pull request information."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return PullRequest(
                            number=data['number'],
                            title=data['title'],
                            body=data['body'] or '',
                            base_branch=data['base']['ref'],
                            head_branch=data['head']['ref'],
                            base_sha=data['base']['sha'],
                            head_sha=data['head']['sha'],
                            state=data['state'],
                            url=data['html_url']
                        )
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitHub API error {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error fetching pull request: {e}")
            return None

    async def get_pull_request_diff(self, owner: str, repo: str, pr_number: int) -> Optional[str]:
        """Get the diff for a pull request."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

        headers = dict(self.headers)
        headers["Accept"] = "application/vnd.github.v3.diff"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitHub API error {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error fetching pull request diff: {e}")
            return None

    async def create_review_comment(self,
                                  owner: str,
                                  repo: str,
                                  pr_number: int,
                                  path: str,
                                  line: int,
                                  body: str,
                                  side: str = "RIGHT") -> bool:
        """
        Create a review comment on a specific line.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            path: File path
            line: Line number
            body: Comment body
            side: Side of diff (RIGHT for new, LEFT for old)

        Returns:
            True if successful
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"

        comment_data = {
            "body": body,
            "path": path,
            "line": line,
            "side": side
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=comment_data) as response:
                    if response.status == 201:
                        self.logger.info(f"Created review comment on {path}:{line}")
                        return True
                    else:
                        error_data = await response.text()
                        self.logger.error(f"Failed to create comment {response.status}: {error_data}")
                        return False

        except Exception as e:
            self.logger.error(f"Error creating review comment: {e}")
            return False

    async def create_pull_request_review(self,
                                       owner: str,
                                       repo: str,
                                       pr_number: int,
                                       comments: List[ReviewComment],
                                       event: str = "COMMENT",
                                       body: Optional[str] = None) -> bool:
        """
        Create a pull request review with multiple comments.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            comments: List of review comments
            event: Review event (COMMENT, APPROVE, REQUEST_CHANGES)
            body: Overall review body

        Returns:
            True if successful
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

        review_data = {
            "event": event,
            "comments": [
                {
                    "path": comment.path,
                    "line": comment.line,
                    "body": comment.body,
                    "side": comment.side
                }
                for comment in comments
            ]
        }

        if body:
            review_data["body"] = body

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=review_data) as response:
                    if response.status == 200:
                        self.logger.info(f"Created pull request review with {len(comments)} comments")
                        return True
                    else:
                        error_data = await response.text()
                        self.logger.error(f"Failed to create review {response.status}: {error_data}")
                        return False

        except Exception as e:
            self.logger.error(f"Error creating pull request review: {e}")
            return False

    async def post_review_comments(self,
                                 owner: str,
                                 repo: str,
                                 pr_number: int,
                                 issues: List[FocusedIssue]) -> Dict[str, Any]:
        """
        Post review comments for focused issues.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            issues: List of focused issues to comment on

        Returns:
            Dictionary with posting results
        """
        comments = []
        results = {
            "total_issues": len(issues),
            "comments_created": 0,
            "comments_failed": 0,
            "errors": []
        }

        # Convert issues to review comments
        for issue in issues:
            comment_body = self._format_issue_comment(issue)
            comment = ReviewComment(
                path=issue.file_path,
                line=issue.line_number,
                body=comment_body,
                side="RIGHT"  # Always comment on new lines for focused reviews
            )
            comments.append(comment)

        # Group comments by severity and create batches
        critical_comments = [c for i, c in zip(issues, comments) if i.severity == 'error']
        warning_comments = [c for i, c in zip(issues, comments) if i.severity == 'warning']
        info_comments = [c for i, c in zip(issues, comments) if i.severity == 'info']

        # Post critical issues first
        if critical_comments:
            success = await self.create_pull_request_review(
                owner, repo, pr_number, critical_comments[:10],  # Limit to 10 per review
                event="REQUEST_CHANGES",
                body="🔴 **Critical Issues Found**\n\nThese issues need to be addressed before merging."
            )
            if success:
                results["comments_created"] += len(critical_comments[:10])
            else:
                results["comments_failed"] += len(critical_comments[:10])
                results["errors"].append("Failed to post critical issues")

        # Post warnings as comments
        if warning_comments:
            success = await self.create_pull_request_review(
                owner, repo, pr_number, warning_comments[:15],  # Limit to 15 per review
                event="COMMENT",
                body="🟡 **Code Quality Issues**\n\nConsider addressing these improvements."
            )
            if success:
                results["comments_created"] += len(warning_comments[:15])
            else:
                results["comments_failed"] += len(warning_comments[:15])
                results["errors"].append("Failed to post warnings")

        # Post info as suggestions (limited)
        if info_comments:
            success = await self.create_pull_request_review(
                owner, repo, pr_number, info_comments[:5],  # Limit to 5 suggestions
                event="COMMENT",
                body="💡 **Suggestions**\n\nOptional improvements for better code quality."
            )
            if success:
                results["comments_created"] += len(info_comments[:5])
            else:
                results["comments_failed"] += len(info_comments[:5])
                results["errors"].append("Failed to post suggestions")

        return results

    def _format_issue_comment(self, issue: FocusedIssue) -> str:
        """Format a focused issue as a GitHub comment."""
        severity_emoji = {
            'error': '🔴',
            'warning': '🟡',
            'info': '💡'
        }

        emoji = severity_emoji.get(issue.severity, '📝')

        comment_parts = [
            f"{emoji} **{issue.severity.title()}**: {issue.message}",
            ""
        ]

        if issue.suggestion:
            comment_parts.extend([
                "**Suggestion:**",
                issue.suggestion,
                ""
            ])

        if issue.explanation:
            comment_parts.extend([
                "**Why:**",
                issue.explanation,
                ""
            ])

        if issue.code_snippet:
            comment_parts.extend([
                "**Code:**",
                "```",
                issue.code_snippet,
                "```"
            ])

        comment_parts.append("*Generated by Code Review Assistant*")

        return "\n".join(comment_parts)

    async def get_repository_files(self, owner: str, repo: str, ref: str = "main", path: str = "") -> List[Dict[str, Any]]:
        """Get list of files in repository."""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitHub API error {response.status}: {error_data}")
                        return []

        except Exception as e:
            self.logger.error(f"Error fetching repository files: {e}")
            return []

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str = "main") -> Optional[str]:
        """Get file content from repository."""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref}

        headers = dict(self.headers)
        headers["Accept"] = "application/vnd.github.v3.raw"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitHub API error {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error fetching file content: {e}")
            return None

    async def create_issue(self,
                         owner: str,
                         repo: str,
                         title: str,
                         body: str,
                         labels: Optional[List[str]] = None) -> Optional[int]:
        """Create a GitHub issue."""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"

        issue_data = {
            "title": title,
            "body": body
        }

        if labels:
            issue_data["labels"] = labels

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=issue_data) as response:
                    if response.status == 201:
                        data = await response.json()
                        self.logger.info(f"Created issue #{data['number']}: {title}")
                        return data['number']
                    else:
                        error_data = await response.text()
                        self.logger.error(f"Failed to create issue {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error creating issue: {e}")
            return None

    async def check_rate_limit(self) -> Dict[str, Any]:
        """Check GitHub API rate limit status."""
        url = f"{self.base_url}/rate_limit"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"Status {response.status}"}

        except Exception as e:
            self.logger.error(f"Error checking rate limit: {e}")
            return {"error": str(e)}