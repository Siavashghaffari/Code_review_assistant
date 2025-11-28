"""
Ignore Patterns and File Exclusions

Advanced pattern matching and file filtering capabilities.
"""

import fnmatch
import re
import os
from pathlib import Path
from typing import List, Set, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import gitignore_parser

from .schema import IgnorePattern
from ..utils.logger import get_logger


@dataclass
class IgnoreRule:
    """A single ignore rule with metadata."""
    pattern: str
    pattern_type: str
    source: str  # where the rule came from (config, .gitignore, etc.)
    negated: bool = False  # for patterns that start with !
    directory_only: bool = False  # for patterns that end with /


class GitignorePatternMatcher:
    """Handles .gitignore-style pattern matching."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def parse_gitignore_file(self, gitignore_path: Path) -> List[IgnoreRule]:
        """Parse a .gitignore file into ignore rules."""
        rules = []

        if not gitignore_path.exists():
            return rules

        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                negated = False
                directory_only = False

                # Handle negation
                if line.startswith('!'):
                    negated = True
                    line = line[1:]

                # Handle directory-only patterns
                if line.endswith('/'):
                    directory_only = True
                    line = line[:-1]

                rules.append(IgnoreRule(
                    pattern=line,
                    pattern_type="gitignore",
                    source=f"{gitignore_path}:{line_num}",
                    negated=negated,
                    directory_only=directory_only
                ))

        except Exception as e:
            self.logger.warning(f"Error parsing .gitignore file {gitignore_path}: {e}")

        return rules

    def matches_gitignore_pattern(self, file_path: Path, pattern: str, base_path: Optional[Path] = None) -> bool:
        """Check if file matches a gitignore-style pattern."""
        if base_path:
            try:
                relative_path = file_path.relative_to(base_path)
            except ValueError:
                relative_path = file_path
        else:
            relative_path = file_path

        path_str = str(relative_path).replace(os.sep, '/')

        # Handle different pattern types
        if '/' in pattern:
            # Pattern with directory separators - match against full path
            return fnmatch.fnmatch(path_str, pattern)
        else:
            # Pattern without separators - match against filename or any directory component
            parts = path_str.split('/')
            return any(fnmatch.fnmatch(part, pattern) for part in parts)


class AdvancedPatternMatcher:
    """Advanced pattern matching with multiple strategies."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.gitignore_matcher = GitignorePatternMatcher()

    def matches_pattern(self, file_path: Path, ignore_rule: IgnoreRule, base_path: Optional[Path] = None) -> bool:
        """Check if file matches an ignore rule."""
        try:
            if ignore_rule.pattern_type == "glob":
                return self._matches_glob(file_path, ignore_rule.pattern)

            elif ignore_rule.pattern_type == "regex":
                return self._matches_regex(file_path, ignore_rule.pattern)

            elif ignore_rule.pattern_type == "gitignore":
                match = self.gitignore_matcher.matches_gitignore_pattern(
                    file_path, ignore_rule.pattern, base_path
                )
                # Handle directory-only patterns
                if ignore_rule.directory_only and not file_path.is_dir():
                    return False
                return match

            elif ignore_rule.pattern_type == "path":
                return self._matches_path(file_path, ignore_rule.pattern)

            elif ignore_rule.pattern_type == "extension":
                return self._matches_extension(file_path, ignore_rule.pattern)

            elif ignore_rule.pattern_type == "name":
                return self._matches_name(file_path, ignore_rule.pattern)

            else:
                self.logger.warning(f"Unknown pattern type: {ignore_rule.pattern_type}")
                return False

        except Exception as e:
            self.logger.error(f"Error matching pattern {ignore_rule.pattern}: {e}")
            return False

    def _matches_glob(self, file_path: Path, pattern: str) -> bool:
        """Match using glob patterns."""
        return fnmatch.fnmatch(str(file_path), pattern)

    def _matches_regex(self, file_path: Path, pattern: str) -> bool:
        """Match using regular expressions."""
        try:
            return bool(re.search(pattern, str(file_path)))
        except re.error as e:
            self.logger.error(f"Invalid regex pattern {pattern}: {e}")
            return False

    def _matches_path(self, file_path: Path, pattern: str) -> bool:
        """Match if pattern is contained in the path."""
        return pattern in str(file_path)

    def _matches_extension(self, file_path: Path, pattern: str) -> bool:
        """Match based on file extension."""
        if not pattern.startswith('.'):
            pattern = '.' + pattern
        return file_path.suffix.lower() == pattern.lower()

    def _matches_name(self, file_path: Path, pattern: str) -> bool:
        """Match based on exact filename."""
        return file_path.name == pattern


class FileFilterEngine:
    """Main engine for filtering files based on ignore patterns."""

    def __init__(self, ignore_patterns: List[IgnorePattern], include_patterns: List[str] = None):
        self.logger = get_logger(__name__)
        self.matcher = AdvancedPatternMatcher()

        # Convert ignore patterns to rules
        self.ignore_rules = []
        for pattern in ignore_patterns:
            self.ignore_rules.append(IgnoreRule(
                pattern=pattern.pattern,
                pattern_type=pattern.type,
                source="config"
            ))

        self.include_patterns = include_patterns or []
        self._load_additional_ignores()

    def _load_additional_ignores(self):
        """Load ignore patterns from .gitignore and other sources."""
        # Look for .gitignore files
        gitignore_paths = [
            Path(".gitignore"),
            Path(".codereviewignore"),  # Custom ignore file
        ]

        for gitignore_path in gitignore_paths:
            if gitignore_path.exists():
                rules = self.matcher.gitignore_matcher.parse_gitignore_file(gitignore_path)
                self.ignore_rules.extend(rules)
                self.logger.debug(f"Loaded {len(rules)} rules from {gitignore_path}")

    def should_ignore_file(self, file_path: Path, base_path: Optional[Path] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if file should be ignored.

        Returns:
            Tuple of (should_ignore, reason)
        """
        # Check if file matches any ignore patterns
        for rule in self.ignore_rules:
            if self.matcher.matches_pattern(file_path, rule, base_path):
                if rule.negated:
                    # Negated rule - don't ignore even if other rules match
                    continue
                else:
                    return True, f"Matched ignore pattern: {rule.pattern} (from {rule.source})"

        # Check include patterns if specified
        if self.include_patterns:
            file_str = str(file_path)
            matches_include = any(
                fnmatch.fnmatch(file_str, pattern)
                for pattern in self.include_patterns
            )
            if not matches_include:
                return True, "File not in include patterns"

        return False, None

    def filter_file_list(self, file_paths: List[Path], base_path: Optional[Path] = None) -> Dict[str, List[Path]]:
        """
        Filter a list of files into included and ignored.

        Returns:
            Dict with 'included' and 'ignored' lists
        """
        included = []
        ignored = []
        ignore_reasons = {}

        for file_path in file_paths:
            should_ignore, reason = self.should_ignore_file(file_path, base_path)
            if should_ignore:
                ignored.append(file_path)
                if reason:
                    ignore_reasons[str(file_path)] = reason
            else:
                included.append(file_path)

        self.logger.info(f"Filtered {len(file_paths)} files: {len(included)} included, {len(ignored)} ignored")

        return {
            'included': included,
            'ignored': ignored,
            'ignore_reasons': ignore_reasons
        }

    def get_ignore_stats(self) -> Dict[str, Any]:
        """Get statistics about ignore patterns."""
        pattern_types = {}
        sources = {}

        for rule in self.ignore_rules:
            pattern_types[rule.pattern_type] = pattern_types.get(rule.pattern_type, 0) + 1
            sources[rule.source] = sources.get(rule.source, 0) + 1

        return {
            'total_rules': len(self.ignore_rules),
            'pattern_types': pattern_types,
            'sources': sources,
            'include_patterns': len(self.include_patterns)
        }

    def add_ignore_pattern(self, pattern: str, pattern_type: str = "glob", source: str = "runtime"):
        """Add an ignore pattern at runtime."""
        rule = IgnoreRule(
            pattern=pattern,
            pattern_type=pattern_type,
            source=source
        )
        self.ignore_rules.append(rule)
        self.logger.debug(f"Added ignore pattern: {pattern}")

    def remove_ignore_pattern(self, pattern: str) -> bool:
        """Remove an ignore pattern."""
        original_count = len(self.ignore_rules)
        self.ignore_rules = [rule for rule in self.ignore_rules if rule.pattern != pattern]
        removed = original_count - len(self.ignore_rules)

        if removed > 0:
            self.logger.debug(f"Removed {removed} ignore patterns matching: {pattern}")
            return True
        return False

    def test_pattern(self, file_path: Path, pattern: str, pattern_type: str = "glob") -> bool:
        """Test if a file would match a specific pattern."""
        test_rule = IgnoreRule(
            pattern=pattern,
            pattern_type=pattern_type,
            source="test"
        )
        return self.matcher.matches_pattern(file_path, test_rule)


class DirectoryWalker:
    """Walks directory trees while respecting ignore patterns."""

    def __init__(self, filter_engine: FileFilterEngine):
        self.filter_engine = filter_engine
        self.logger = get_logger(__name__)

    def walk_directory(self, root_path: Path, include_dirs: bool = False) -> List[Path]:
        """
        Walk directory tree and return files that should be included.

        Args:
            root_path: Root directory to walk
            include_dirs: Whether to include directories in results

        Returns:
            List of file paths that should be processed
        """
        included_files = []

        try:
            for item in root_path.rglob("*"):
                # Skip directories unless requested
                if item.is_dir() and not include_dirs:
                    continue

                # Check if item should be ignored
                should_ignore, reason = self.filter_engine.should_ignore_file(item, root_path)
                if not should_ignore:
                    included_files.append(item)

            self.logger.info(f"Found {len(included_files)} files to process in {root_path}")

        except Exception as e:
            self.logger.error(f"Error walking directory {root_path}: {e}")

        return included_files

    def walk_multiple_paths(self, paths: List[Path]) -> List[Path]:
        """Walk multiple paths and return combined results."""
        all_files = []

        for path in paths:
            if path.is_file():
                should_ignore, _ = self.filter_engine.should_ignore_file(path)
                if not should_ignore:
                    all_files.append(path)
            elif path.is_dir():
                all_files.extend(self.walk_directory(path))
            else:
                self.logger.warning(f"Path does not exist: {path}")

        return all_files


def create_file_filter(ignore_patterns: List[IgnorePattern], include_patterns: List[str] = None) -> FileFilterEngine:
    """Factory function to create a FileFilterEngine."""
    return FileFilterEngine(ignore_patterns, include_patterns)