"""
GitLab API Integration

Integrates with GitLab API to fetch repository information, create merge request
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
class GitLabRepo:
    """GitLab repository information."""
    id: int
    name: str
    path_with_namespace: str
    default_branch: str
    web_url: str
    http_url_to_repo: str
    api_url: str


@dataclass
class MergeRequest:
    """GitLab merge request information."""
    iid: int  # Internal ID
    id: int   # Global ID
    title: str
    description: str
    source_branch: str
    target_branch: str
    source_project_id: int
    target_project_id: int
    state: str
    web_url: str
    diff_refs: Dict[str, str]


@dataclass
class MergeRequestComment:
    """GitLab merge request comment."""
    path: str
    line: int
    body: str
    line_type: str = "new"  # new or old


class GitLabIntegration:
    """GitLab API integration for code review features."""

    def __init__(self, token: str, gitlab_url: str = "https://gitlab.com"):
        self.token = token
        self.gitlab_url = gitlab_url.rstrip('/')
        self.logger = get_logger(__name__)
        self.base_url = f"{self.gitlab_url}/api/v4"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def parse_gitlab_url(self, url: str) -> Optional[GitLabRepo]:
        """
        Parse GitLab URL to extract repository information.

        Args:
            url: GitLab repository URL

        Returns:
            GitLabRepo object or None if invalid
        """
        # Handle different GitLab URL formats
        patterns = [
            r'https?://([^/]+)/([^/]+/[^/]+?)(?:\.git)?/?$',
            r'git@([^:]+):([^/]+/[^/]+?)(?:\.git)?$',
            r'([^/]+)/([^/]+/[^/]+)/?$'
        ]

        for pattern in patterns:
            match = re.match(pattern, url.strip())
            if match:
                host, path = match.groups()

                # Check if it's the configured GitLab instance
                if self.gitlab_url.endswith(host) or host in self.gitlab_url:
                    return await self._fetch_repo_info_by_path(path)

        self.logger.warning(f"Could not parse GitLab URL: {url}")
        return None

    async def _fetch_repo_info_by_path(self, path: str) -> Optional[GitLabRepo]:
        """Fetch repository information by path."""
        # URL encode the path
        encoded_path = path.replace('/', '%2F')
        url = f"{self.base_url}/projects/{encoded_path}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return GitLabRepo(
                            id=data['id'],
                            name=data['name'],
                            path_with_namespace=data['path_with_namespace'],
                            default_branch=data['default_branch'],
                            web_url=data['web_url'],
                            http_url_to_repo=data['http_url_to_repo'],
                            api_url=url
                        )
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitLab API error {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error fetching repo info: {e}")
            return None

    async def get_merge_request(self, project_id: int, mr_iid: int) -> Optional[MergeRequest]:
        """Get merge request information."""
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return MergeRequest(
                            iid=data['iid'],
                            id=data['id'],
                            title=data['title'],
                            description=data['description'] or '',
                            source_branch=data['source_branch'],
                            target_branch=data['target_branch'],
                            source_project_id=data['source_project_id'],
                            target_project_id=data['target_project_id'],
                            state=data['state'],
                            web_url=data['web_url'],
                            diff_refs=data.get('diff_refs', {})
                        )
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitLab API error {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error fetching merge request: {e}")
            return None

    async def get_merge_request_diff(self, project_id: int, mr_iid: int) -> Optional[str]:
        """Get the diff for a merge request."""
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/diffs"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Convert GitLab diff format to unified diff format
                        diff_text = self._convert_gitlab_diff_to_unified(data)
                        return diff_text
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitLab API error {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error fetching merge request diff: {e}")
            return None

    def _convert_gitlab_diff_to_unified(self, gitlab_diffs: List[Dict[str, Any]]) -> str:
        """Convert GitLab diff format to unified diff format."""
        unified_lines = []

        for file_diff in gitlab_diffs:
            # File header
            old_path = file_diff.get('old_path', '/dev/null')
            new_path = file_diff.get('new_path', '/dev/null')

            unified_lines.extend([
                f"diff --git a/{old_path} b/{new_path}",
                f"--- a/{old_path}",
                f"+++ b/{new_path}"
            ])

            # Process diff content
            diff_content = file_diff.get('diff', '')
            if diff_content:
                # Split by hunks and process
                hunk_lines = diff_content.split('\n')
                for line in hunk_lines:
                    if line.startswith('@@'):
                        unified_lines.append(line)
                    elif line.startswith(('+', '-', ' ')):
                        unified_lines.append(line)

        return '\n'.join(unified_lines)

    async def create_merge_request_note(self,
                                      project_id: int,
                                      mr_iid: int,
                                      body: str,
                                      position: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a note (comment) on a merge request.

        Args:
            project_id: Project ID
            mr_iid: Merge request internal ID
            body: Comment body
            position: Position data for line comments

        Returns:
            True if successful
        """
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/notes"

        note_data = {"body": body}

        if position:
            note_data["position"] = position

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=note_data) as response:
                    if response.status == 201:
                        self.logger.info(f"Created merge request note")
                        return True
                    else:
                        error_data = await response.text()
                        self.logger.error(f"Failed to create note {response.status}: {error_data}")
                        return False

        except Exception as e:
            self.logger.error(f"Error creating merge request note: {e}")
            return False

    async def create_line_comment(self,
                                project_id: int,
                                mr_iid: int,
                                path: str,
                                line: int,
                                body: str,
                                base_sha: str,
                                head_sha: str,
                                start_sha: str) -> bool:
        """
        Create a comment on a specific line.

        Args:
            project_id: Project ID
            mr_iid: Merge request internal ID
            path: File path
            line: Line number
            body: Comment body
            base_sha: Base commit SHA
            head_sha: Head commit SHA
            start_sha: Start commit SHA

        Returns:
            True if successful
        """
        # Position data for line comment
        position = {
            "base_sha": base_sha,
            "start_sha": start_sha,
            "head_sha": head_sha,
            "position_type": "text",
            "new_path": path,
            "new_line": line,
            "line_range": {
                "start": {
                    "line_code": f"{path}_{line}_R",
                    "type": "new",
                    "new_line": line
                }
            }
        }

        return await self.create_merge_request_note(project_id, mr_iid, body, position)

    async def create_merge_request_discussion(self,
                                            project_id: int,
                                            mr_iid: int,
                                            comments: List[MergeRequestComment],
                                            base_sha: str,
                                            head_sha: str,
                                            start_sha: str) -> Dict[str, Any]:
        """
        Create discussions with multiple line comments.

        Args:
            project_id: Project ID
            mr_iid: Merge request internal ID
            comments: List of comments to create
            base_sha: Base commit SHA
            head_sha: Head commit SHA
            start_sha: Start commit SHA

        Returns:
            Dictionary with results
        """
        results = {
            "total_comments": len(comments),
            "comments_created": 0,
            "comments_failed": 0,
            "errors": []
        }

        # Create comments one by one (GitLab doesn't support batch creation)
        for comment in comments:
            success = await self.create_line_comment(
                project_id, mr_iid, comment.path, comment.line, comment.body,
                base_sha, head_sha, start_sha
            )

            if success:
                results["comments_created"] += 1
            else:
                results["comments_failed"] += 1
                results["errors"].append(f"Failed to create comment on {comment.path}:{comment.line}")

            # Add small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        return results

    async def post_review_comments(self,
                                 project_id: int,
                                 mr_iid: int,
                                 issues: List[FocusedIssue],
                                 base_sha: str,
                                 head_sha: str,
                                 start_sha: str) -> Dict[str, Any]:
        """
        Post review comments for focused issues.

        Args:
            project_id: Project ID
            mr_iid: Merge request internal ID
            issues: List of focused issues to comment on
            base_sha: Base commit SHA
            head_sha: Head commit SHA
            start_sha: Start commit SHA

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

        # Convert issues to merge request comments
        for issue in issues:
            comment_body = self._format_issue_comment(issue)
            comment = MergeRequestComment(
                path=issue.file_path,
                line=issue.line_number,
                body=comment_body,
                line_type="new"
            )
            comments.append(comment)

        # Group comments by severity
        critical_comments = [c for i, c in zip(issues, comments) if i.severity == 'error']
        warning_comments = [c for i, c in zip(issues, comments) if i.severity == 'warning']
        info_comments = [c for i, c in zip(issues, comments) if i.severity == 'info']

        # Post critical issues first (limited)
        if critical_comments:
            critical_results = await self.create_merge_request_discussion(
                project_id, mr_iid, critical_comments[:10],  # Limit to 10
                base_sha, head_sha, start_sha
            )
            results["comments_created"] += critical_results["comments_created"]
            results["comments_failed"] += critical_results["comments_failed"]
            results["errors"].extend(critical_results["errors"])

            # Add summary comment for critical issues
            if critical_results["comments_created"] > 0:
                summary_body = f"🔴 **{critical_results['comments_created']} Critical Issues Found**\n\n" \
                             f"Please address these issues before merging."
                await self.create_merge_request_note(project_id, mr_iid, summary_body)

        # Post warnings (limited)
        if warning_comments:
            warning_results = await self.create_merge_request_discussion(
                project_id, mr_iid, warning_comments[:15],  # Limit to 15
                base_sha, head_sha, start_sha
            )
            results["comments_created"] += warning_results["comments_created"]
            results["comments_failed"] += warning_results["comments_failed"]
            results["errors"].extend(warning_results["errors"])

            # Add summary comment for warnings
            if warning_results["comments_created"] > 0:
                summary_body = f"🟡 **{warning_results['comments_created']} Code Quality Issues**\n\n" \
                             f"Consider addressing these improvements."
                await self.create_merge_request_note(project_id, mr_iid, summary_body)

        # Post limited suggestions
        if info_comments:
            info_results = await self.create_merge_request_discussion(
                project_id, mr_iid, info_comments[:5],  # Limit to 5
                base_sha, head_sha, start_sha
            )
            results["comments_created"] += info_results["comments_created"]
            results["comments_failed"] += info_results["comments_failed"]
            results["errors"].extend(info_results["errors"])

        return results

    def _format_issue_comment(self, issue: FocusedIssue) -> str:
        """Format a focused issue as a GitLab comment."""
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

    async def get_project_files(self, project_id: int, ref: str = "main", path: str = "") -> List[Dict[str, Any]]:
        """Get list of files in project."""
        url = f"{self.base_url}/projects/{project_id}/repository/tree"
        params = {"ref": ref, "path": path, "recursive": True}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitLab API error {response.status}: {error_data}")
                        return []

        except Exception as e:
            self.logger.error(f"Error fetching project files: {e}")
            return []

    async def get_file_content(self, project_id: int, file_path: str, ref: str = "main") -> Optional[str]:
        """Get file content from project."""
        # URL encode the file path
        encoded_path = file_path.replace('/', '%2F')
        url = f"{self.base_url}/projects/{project_id}/repository/files/{encoded_path}/raw"
        params = {"ref": ref}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitLab API error {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error fetching file content: {e}")
            return None

    async def create_issue(self,
                         project_id: int,
                         title: str,
                         description: str,
                         labels: Optional[List[str]] = None) -> Optional[int]:
        """Create a GitLab issue."""
        url = f"{self.base_url}/projects/{project_id}/issues"

        issue_data = {
            "title": title,
            "description": description
        }

        if labels:
            issue_data["labels"] = ",".join(labels)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=issue_data) as response:
                    if response.status == 201:
                        data = await response.json()
                        self.logger.info(f"Created issue #{data['iid']}: {title}")
                        return data['iid']
                    else:
                        error_data = await response.text()
                        self.logger.error(f"Failed to create issue {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error creating issue: {e}")
            return None

    async def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current user information."""
        url = f"{self.base_url}/user"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_data = await response.text()
                        self.logger.error(f"GitLab API error {response.status}: {error_data}")
                        return None

        except Exception as e:
            self.logger.error(f"Error fetching user info: {e}")
            return None