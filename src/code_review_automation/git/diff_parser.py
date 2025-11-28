"""
Git Diff Parser

Parses git diffs to identify changed lines, files, and modifications
for focused code review on only the changed parts.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger


class ChangeType(Enum):
    """Types of changes in git diff."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RENAMED = "renamed"


@dataclass
class DiffLine:
    """Represents a single line change in a diff."""
    line_number: int
    old_line_number: Optional[int]
    new_line_number: Optional[int]
    content: str
    change_type: ChangeType


@dataclass
class DiffHunk:
    """Represents a hunk (section) of changes in a file."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[DiffLine]
    context: str  # The @@ line


@dataclass
class FileDiff:
    """Represents all changes in a single file."""
    old_path: str
    new_path: str
    change_type: ChangeType
    hunks: List[DiffHunk]
    added_lines: int = 0
    removed_lines: int = 0
    is_binary: bool = False


@dataclass
class GitDiffResult:
    """Complete git diff analysis result."""
    files: List[FileDiff]
    total_added: int = 0
    total_removed: int = 0
    commit_hash: Optional[str] = None
    commit_message: Optional[str] = None


class GitDiffParser:
    """Parser for git diff output."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def parse_diff(self, diff_text: str) -> GitDiffResult:
        """
        Parse git diff output into structured format.

        Args:
            diff_text: Raw git diff output

        Returns:
            GitDiffResult with parsed file changes
        """
        files = []
        lines = diff_text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Look for file headers
            if line.startswith('diff --git'):
                file_diff, next_i = self._parse_file_diff(lines, i)
                if file_diff:
                    files.append(file_diff)
                i = next_i
            else:
                i += 1

        # Calculate totals
        total_added = sum(f.added_lines for f in files)
        total_removed = sum(f.removed_lines for f in files)

        return GitDiffResult(
            files=files,
            total_added=total_added,
            total_removed=total_removed
        )

    def _parse_file_diff(self, lines: List[str], start_idx: int) -> Tuple[Optional[FileDiff], int]:
        """Parse a single file's diff section."""
        i = start_idx
        old_path = None
        new_path = None
        change_type = ChangeType.MODIFIED
        hunks = []
        is_binary = False

        # Parse file header
        if i < len(lines) and lines[i].startswith('diff --git'):
            # Extract paths from diff --git line
            diff_line = lines[i]
            paths_match = re.search(r'diff --git a/(.+) b/(.+)', diff_line)
            if paths_match:
                old_path = paths_match.group(1)
                new_path = paths_match.group(2)
            i += 1

        # Look for additional file info
        while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('diff --git'):
            line = lines[i]

            if line.startswith('new file mode'):
                change_type = ChangeType.ADDED
            elif line.startswith('deleted file mode'):
                change_type = ChangeType.REMOVED
            elif line.startswith('rename from'):
                change_type = ChangeType.RENAMED
            elif line.startswith('--- '):
                # Old file path
                path_match = re.search(r'--- a/(.+)', line)
                if path_match:
                    old_path = path_match.group(1)
                elif line == '--- /dev/null':
                    change_type = ChangeType.ADDED
            elif line.startswith('+++ '):
                # New file path
                path_match = re.search(r'\+\+\+ b/(.+)', line)
                if path_match:
                    new_path = path_match.group(1)
                elif line == '+++ /dev/null':
                    change_type = ChangeType.REMOVED
            elif 'Binary files' in line:
                is_binary = True

            i += 1

        # Parse hunks
        while i < len(lines) and lines[i].startswith('@@'):
            hunk, next_i = self._parse_hunk(lines, i)
            if hunk:
                hunks.append(hunk)
            i = next_i

        if not old_path or not new_path:
            return None, i

        # Calculate line counts
        added_lines = sum(
            len([line for line in hunk.lines if line.change_type == ChangeType.ADDED])
            for hunk in hunks
        )
        removed_lines = sum(
            len([line for line in hunk.lines if line.change_type == ChangeType.REMOVED])
            for hunk in hunks
        )

        file_diff = FileDiff(
            old_path=old_path,
            new_path=new_path,
            change_type=change_type,
            hunks=hunks,
            added_lines=added_lines,
            removed_lines=removed_lines,
            is_binary=is_binary
        )

        return file_diff, i

    def _parse_hunk(self, lines: List[str], start_idx: int) -> Tuple[Optional[DiffHunk], int]:
        """Parse a single hunk of changes."""
        i = start_idx

        if i >= len(lines) or not lines[i].startswith('@@'):
            return None, i

        # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
        hunk_header = lines[i]
        hunk_match = re.search(r'@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@', hunk_header)

        if not hunk_match:
            return None, i + 1

        old_start = int(hunk_match.group(1))
        old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
        new_start = int(hunk_match.group(3))
        new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1

        i += 1
        hunk_lines = []
        old_line = old_start
        new_line = new_start

        # Parse hunk content
        while i < len(lines):
            line = lines[i]

            # End of hunk
            if line.startswith('@@') or line.startswith('diff --git'):
                break

            if not line:
                i += 1
                continue

            change_indicator = line[0] if line else ' '
            content = line[1:] if len(line) > 1 else ''

            if change_indicator == '+':
                # Added line
                diff_line = DiffLine(
                    line_number=new_line,
                    old_line_number=None,
                    new_line_number=new_line,
                    content=content,
                    change_type=ChangeType.ADDED
                )
                hunk_lines.append(diff_line)
                new_line += 1

            elif change_indicator == '-':
                # Removed line
                diff_line = DiffLine(
                    line_number=old_line,
                    old_line_number=old_line,
                    new_line_number=None,
                    content=content,
                    change_type=ChangeType.REMOVED
                )
                hunk_lines.append(diff_line)
                old_line += 1

            else:
                # Context line (unchanged)
                diff_line = DiffLine(
                    line_number=new_line,
                    old_line_number=old_line,
                    new_line_number=new_line,
                    content=content,
                    change_type=ChangeType.MODIFIED  # Context line
                )
                hunk_lines.append(diff_line)
                old_line += 1
                new_line += 1

            i += 1

        hunk = DiffHunk(
            old_start=old_start,
            old_count=old_count,
            new_start=new_start,
            new_count=new_count,
            lines=hunk_lines,
            context=hunk_header
        )

        return hunk, i

    def get_changed_lines_for_file(self, file_diff: FileDiff) -> Dict[str, Set[int]]:
        """
        Get sets of changed line numbers for a file.

        Returns:
            Dictionary with 'added' and 'removed' sets of line numbers
        """
        added_lines = set()
        removed_lines = set()

        for hunk in file_diff.hunks:
            for line in hunk.lines:
                if line.change_type == ChangeType.ADDED and line.new_line_number:
                    added_lines.add(line.new_line_number)
                elif line.change_type == ChangeType.REMOVED and line.old_line_number:
                    removed_lines.add(line.old_line_number)

        return {
            'added': added_lines,
            'removed': removed_lines
        }

    def get_modified_files(self, diff_result: GitDiffResult) -> List[str]:
        """Get list of modified file paths."""
        return [f.new_path for f in diff_result.files if not f.is_binary]

    def filter_lines_by_changes(self, file_content: str, changed_lines: Set[int]) -> List[Tuple[int, str]]:
        """
        Filter file content to only include changed lines with context.

        Args:
            file_content: Complete file content
            changed_lines: Set of line numbers that changed

        Returns:
            List of (line_number, content) tuples for changed lines
        """
        lines = file_content.split('\n')
        filtered_lines = []

        for line_num in sorted(changed_lines):
            if 1 <= line_num <= len(lines):
                filtered_lines.append((line_num, lines[line_num - 1]))

        return filtered_lines


class GitCommands:
    """Utility class for executing git commands."""

    def __init__(self, repo_path: Optional[Path] = None):
        self.repo_path = repo_path or Path.cwd()
        self.logger = get_logger(__name__)

    def get_diff(self,
                 base_ref: str = "HEAD",
                 target_ref: Optional[str] = None,
                 files: Optional[List[str]] = None) -> str:
        """
        Get git diff between references.

        Args:
            base_ref: Base reference (default: HEAD)
            target_ref: Target reference (None for working directory)
            files: Specific files to diff

        Returns:
            Raw git diff output
        """
        cmd = ["git", "diff"]

        if target_ref:
            cmd.append(f"{base_ref}..{target_ref}")
        else:
            cmd.append(base_ref)

        if files:
            cmd.extend(["--"] + files)

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git diff failed: {e.stderr}")
            raise RuntimeError(f"Git command failed: {e.stderr}")

    def get_changed_files(self, base_ref: str = "HEAD", target_ref: Optional[str] = None) -> List[str]:
        """Get list of changed files between references."""
        cmd = ["git", "diff", "--name-only"]

        if target_ref:
            cmd.append(f"{base_ref}..{target_ref}")
        else:
            cmd.append(base_ref)

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return [f.strip() for f in result.stdout.split('\n') if f.strip()]

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git diff --name-only failed: {e.stderr}")
            return []

    def get_commit_info(self, commit_ref: str = "HEAD") -> Dict[str, str]:
        """Get commit information."""
        try:
            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", commit_ref],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            # Get commit message
            msg_result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%s%n%n%b", commit_ref],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            # Get author and date
            author_result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%an <%ae>%n%ci", commit_ref],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            author_lines = author_result.stdout.split('\n')

            return {
                'hash': hash_result.stdout.strip(),
                'message': msg_result.stdout.strip(),
                'author': author_lines[0] if author_lines else '',
                'date': author_lines[1] if len(author_lines) > 1 else ''
            }

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git commit info failed: {e.stderr}")
            return {}

    def get_current_branch(self) -> str:
        """Get current branch name."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Get current branch failed: {e.stderr}")
            return "unknown"

    def get_remote_url(self, remote: str = "origin") -> str:
        """Get remote URL."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", remote],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Get remote URL failed: {e.stderr}")
            return ""

    def is_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False