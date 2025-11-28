"""
Commit Message Generator

Generates intelligent commit messages based on git diff analysis
and code changes using AI understanding of the modifications.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import Counter

from .diff_parser import GitDiffResult, FileDiff, ChangeType, DiffHunk
from ..utils.logger import get_logger


@dataclass
class CommitAnalysis:
    """Analysis of changes for commit message generation."""
    change_summary: Dict[str, Any]
    file_changes: List[Dict[str, Any]]
    impact_analysis: Dict[str, Any]
    conventional_type: str
    scope: Optional[str]
    breaking_changes: bool


class CommitMessageGenerator:
    """Generates commit messages based on git diff analysis."""

    def __init__(self):
        self.logger = get_logger(__name__)

        # Conventional commit types and their patterns
        self.commit_types = {
            'feat': ['add', 'new', 'implement', 'create', 'introduce'],
            'fix': ['fix', 'resolve', 'correct', 'repair', 'patch'],
            'docs': ['document', 'readme', 'comment', 'doc', 'guide'],
            'style': ['format', 'whitespace', 'style', 'lint', 'prettier'],
            'refactor': ['refactor', 'restructure', 'reorganize', 'cleanup', 'simplify'],
            'test': ['test', 'spec', 'testing', 'coverage', 'unit'],
            'chore': ['update', 'upgrade', 'maintain', 'dependency', 'config'],
            'perf': ['optimize', 'performance', 'speed', 'cache', 'efficient'],
            'ci': ['ci', 'build', 'deploy', 'pipeline', 'workflow'],
            'revert': ['revert', 'rollback', 'undo']
        }

        # File type to scope mapping
        self.scope_mappings = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'react',
            '.tsx': 'react',
            '.vue': 'vue',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.md': 'docs',
            '.yml': 'config',
            '.yaml': 'config',
            '.json': 'config',
            '.dockerfile': 'docker',
            '.sql': 'database',
            '.css': 'styles',
            '.scss': 'styles',
            '.html': 'template'
        }

    def analyze_changes(self, diff_result: GitDiffResult) -> CommitAnalysis:
        """Analyze git diff to understand the nature of changes."""
        change_summary = self._summarize_changes(diff_result)
        file_changes = self._analyze_file_changes(diff_result)
        impact_analysis = self._analyze_impact(diff_result)

        # Determine conventional commit type
        conventional_type = self._determine_commit_type(diff_result, file_changes)

        # Determine scope
        scope = self._determine_scope(diff_result)

        # Check for breaking changes
        breaking_changes = self._has_breaking_changes(diff_result, file_changes)

        return CommitAnalysis(
            change_summary=change_summary,
            file_changes=file_changes,
            impact_analysis=impact_analysis,
            conventional_type=conventional_type,
            scope=scope,
            breaking_changes=breaking_changes
        )

    def generate_commit_messages(self, diff_result: GitDiffResult, limit: int = 5) -> List[str]:
        """
        Generate multiple commit message suggestions.

        Args:
            diff_result: Parsed git diff result
            limit: Maximum number of suggestions

        Returns:
            List of commit message suggestions
        """
        analysis = self.analyze_changes(diff_result)
        messages = []

        # Generate conventional commit messages
        conventional_messages = self._generate_conventional_commits(analysis)
        messages.extend(conventional_messages)

        # Generate descriptive messages
        descriptive_messages = self._generate_descriptive_commits(analysis)
        messages.extend(descriptive_messages)

        # Generate concise messages
        concise_messages = self._generate_concise_commits(analysis)
        messages.extend(concise_messages)

        # Remove duplicates and limit
        unique_messages = []
        seen = set()
        for msg in messages:
            if msg.lower() not in seen:
                unique_messages.append(msg)
                seen.add(msg.lower())

        return unique_messages[:limit]

    def _summarize_changes(self, diff_result: GitDiffResult) -> Dict[str, Any]:
        """Create a high-level summary of changes."""
        return {
            'files_modified': len([f for f in diff_result.files if f.change_type == ChangeType.MODIFIED]),
            'files_added': len([f for f in diff_result.files if f.change_type == ChangeType.ADDED]),
            'files_removed': len([f for f in diff_result.files if f.change_type == ChangeType.REMOVED]),
            'files_renamed': len([f for f in diff_result.files if f.change_type == ChangeType.RENAMED]),
            'total_files': len(diff_result.files),
            'lines_added': diff_result.total_added,
            'lines_removed': diff_result.total_removed,
            'net_change': diff_result.total_added - diff_result.total_removed
        }

    def _analyze_file_changes(self, diff_result: GitDiffResult) -> List[Dict[str, Any]]:
        """Analyze changes in individual files."""
        file_changes = []

        for file_diff in diff_result.files:
            file_analysis = {
                'path': file_diff.new_path,
                'old_path': file_diff.old_path,
                'change_type': file_diff.change_type.value,
                'extension': Path(file_diff.new_path).suffix.lower(),
                'directory': str(Path(file_diff.new_path).parent),
                'lines_added': file_diff.added_lines,
                'lines_removed': file_diff.removed_lines,
                'is_binary': file_diff.is_binary,
                'hunks_count': len(file_diff.hunks)
            }

            # Analyze the nature of changes in the file
            if file_diff.hunks:
                file_analysis['change_patterns'] = self._analyze_change_patterns(file_diff)

            file_changes.append(file_analysis)

        return file_changes

    def _analyze_change_patterns(self, file_diff: FileDiff) -> Dict[str, Any]:
        """Analyze patterns in the changes within a file."""
        patterns = {
            'function_changes': 0,
            'class_changes': 0,
            'import_changes': 0,
            'config_changes': 0,
            'test_changes': 0,
            'documentation_changes': 0
        }

        for hunk in file_diff.hunks:
            hunk_content = '\n'.join([line.content for line in hunk.lines])

            # Detect function/method changes
            if re.search(r'(def |function |async function)', hunk_content):
                patterns['function_changes'] += 1

            # Detect class changes
            if re.search(r'(class |interface |type )', hunk_content):
                patterns['class_changes'] += 1

            # Detect import changes
            if re.search(r'(import |from |require\(|#include)', hunk_content):
                patterns['import_changes'] += 1

            # Detect config changes
            if re.search(r'(config|settings|options|\.env)', hunk_content, re.IGNORECASE):
                patterns['config_changes'] += 1

            # Detect test changes
            if re.search(r'(test|spec|describe|it\(|assert)', hunk_content, re.IGNORECASE):
                patterns['test_changes'] += 1

            # Detect documentation changes
            if re.search(r'(\/\*\*|"""|\#|\/\/)', hunk_content):
                patterns['documentation_changes'] += 1

        return patterns

    def _analyze_impact(self, diff_result: GitDiffResult) -> Dict[str, Any]:
        """Analyze the impact and scope of changes."""
        impact = {
            'scope': 'small',
            'risk_level': 'low',
            'areas_affected': [],
            'file_types': []
        }

        # Determine scope based on changes
        total_changes = diff_result.total_added + diff_result.total_removed
        if total_changes > 200:
            impact['scope'] = 'large'
        elif total_changes > 50:
            impact['scope'] = 'medium'

        # Analyze affected areas
        directories = set()
        file_types = set()

        for file_diff in diff_result.files:
            directories.add(str(Path(file_diff.new_path).parent))
            extension = Path(file_diff.new_path).suffix.lower()
            if extension:
                file_types.add(extension)

        impact['areas_affected'] = list(directories)
        impact['file_types'] = list(file_types)

        # Determine risk level
        if any('test' in d for d in directories):
            impact['risk_level'] = 'low'
        elif any(d in ['.', 'src', 'lib'] for d in directories):
            impact['risk_level'] = 'medium'
        elif len(directories) > 5 or total_changes > 100:
            impact['risk_level'] = 'high'

        return impact

    def _determine_commit_type(self, diff_result: GitDiffResult, file_changes: List[Dict[str, Any]]) -> str:
        """Determine the conventional commit type."""
        # Count different types of changes
        type_scores = {commit_type: 0 for commit_type in self.commit_types.keys()}

        # Analyze file paths and changes
        for file_change in file_changes:
            path = file_change['path'].lower()
            change_type = file_change['change_type']

            # Score based on file paths
            if any(test_indicator in path for test_indicator in ['test', 'spec', '__test__']):
                type_scores['test'] += 2

            if any(doc_indicator in path for doc_indicator in ['readme', 'doc', '.md']):
                type_scores['docs'] += 2

            if any(config_indicator in path for config_indicator in ['config', '.env', 'setting']):
                type_scores['chore'] += 1

            # Score based on change type
            if change_type == 'added':
                type_scores['feat'] += 2
            elif change_type == 'removed':
                type_scores['chore'] += 1

            # Score based on change patterns
            patterns = file_change.get('change_patterns', {})
            if patterns.get('function_changes', 0) > 0:
                type_scores['feat'] += 1
                type_scores['refactor'] += 1

            if patterns.get('test_changes', 0) > 0:
                type_scores['test'] += 2

            if patterns.get('documentation_changes', 0) > 0:
                type_scores['docs'] += 1

        # Return the highest scoring type, defaulting to 'feat'
        if all(score == 0 for score in type_scores.values()):
            return 'feat'

        return max(type_scores.items(), key=lambda x: x[1])[0]

    def _determine_scope(self, diff_result: GitDiffResult) -> Optional[str]:
        """Determine the scope for conventional commits."""
        # Count file extensions
        extension_counts = Counter()
        directory_counts = Counter()

        for file_diff in diff_result.files:
            extension = Path(file_diff.new_path).suffix.lower()
            directory = Path(file_diff.new_path).parts[0] if Path(file_diff.new_path).parts else ''

            if extension:
                extension_counts[extension] += 1
            if directory:
                directory_counts[directory] += 1

        # Determine scope based on most common extension
        if extension_counts:
            most_common_ext = extension_counts.most_common(1)[0][0]
            if most_common_ext in self.scope_mappings:
                return self.scope_mappings[most_common_ext]

        # Determine scope based on directory
        if directory_counts:
            most_common_dir = directory_counts.most_common(1)[0][0]
            common_scopes = {
                'src': 'core',
                'lib': 'core',
                'api': 'api',
                'ui': 'ui',
                'components': 'ui',
                'utils': 'utils',
                'tests': 'test',
                'docs': 'docs',
                'config': 'config'
            }
            if most_common_dir in common_scopes:
                return common_scopes[most_common_dir]

        return None

    def _has_breaking_changes(self, diff_result: GitDiffResult, file_changes: List[Dict[str, Any]]) -> bool:
        """Detect if changes might be breaking."""
        # Simple heuristics for breaking changes
        for file_change in file_changes:
            # Large removals might indicate breaking changes
            if file_change['lines_removed'] > 50:
                return True

            # API or public interface changes
            path = file_change['path'].lower()
            if any(api_indicator in path for api_indicator in ['api', 'interface', 'public']):
                if file_change['lines_removed'] > 0:
                    return True

            # Configuration file changes
            if file_change['extension'] in ['.env', '.config', '.yml', '.yaml']:
                if file_change['change_type'] == 'removed':
                    return True

        return False

    def _generate_conventional_commits(self, analysis: CommitAnalysis) -> List[str]:
        """Generate conventional commit format messages."""
        messages = []

        commit_type = analysis.conventional_type
        scope = analysis.scope
        breaking = "!" if analysis.breaking_changes else ""

        # Generate based on change summary
        summary = analysis.change_summary

        scope_part = f"({scope})" if scope else ""

        # Simple message
        if summary['files_added'] > 0 and summary['files_modified'] == 0:
            messages.append(f"{commit_type}{scope_part}{breaking}: add new functionality")
        elif summary['files_removed'] > 0 and summary['files_modified'] == 0:
            messages.append(f"{commit_type}{scope_part}{breaking}: remove deprecated code")
        elif summary['files_modified'] > 0:
            messages.append(f"{commit_type}{scope_part}{breaking}: update implementation")

        # More specific messages
        if summary['total_files'] == 1:
            file_change = analysis.file_changes[0]
            file_name = Path(file_change['path']).stem
            messages.append(f"{commit_type}{scope_part}{breaking}: update {file_name}")

        # Change size based messages
        total_changes = summary['lines_added'] + summary['lines_removed']
        if total_changes > 100:
            messages.append(f"{commit_type}{scope_part}{breaking}: major code improvements")
        elif total_changes > 20:
            messages.append(f"{commit_type}{scope_part}{breaking}: enhance functionality")
        else:
            messages.append(f"{commit_type}{scope_part}{breaking}: minor improvements")

        return messages

    def _generate_descriptive_commits(self, analysis: CommitAnalysis) -> List[str]:
        """Generate descriptive commit messages."""
        messages = []
        summary = analysis.change_summary

        # File-based descriptions
        if summary['files_added'] > 0:
            if summary['files_added'] == 1:
                file_name = Path(analysis.file_changes[0]['path']).name
                messages.append(f"Add {file_name}")
            else:
                messages.append(f"Add {summary['files_added']} new files")

        if summary['files_modified'] > 0:
            if summary['files_modified'] == 1:
                file_name = Path([f for f in analysis.file_changes if f['change_type'] == 'modified'][0]['path']).name
                messages.append(f"Update {file_name}")
            else:
                messages.append(f"Update {summary['files_modified']} files")

        if summary['files_removed'] > 0:
            messages.append(f"Remove {summary['files_removed']} files")

        # Change pattern based descriptions
        for file_change in analysis.file_changes:
            patterns = file_change.get('change_patterns', {})

            if patterns.get('function_changes', 0) > 0:
                messages.append("Improve function implementations")

            if patterns.get('test_changes', 0) > 0:
                messages.append("Enhance test coverage")

            if patterns.get('documentation_changes', 0) > 0:
                messages.append("Update documentation")

        return messages

    def _generate_concise_commits(self, analysis: CommitAnalysis) -> List[str]:
        """Generate concise commit messages."""
        messages = []

        # Very short descriptions
        if analysis.change_summary['total_files'] == 1:
            file_change = analysis.file_changes[0]
            if file_change['change_type'] == 'added':
                messages.append("Add new file")
            elif file_change['change_type'] == 'removed':
                messages.append("Remove file")
            else:
                messages.append("Update code")
        else:
            messages.append("Update multiple files")

        messages.extend([
            "Code improvements",
            "Bug fixes and enhancements",
            "Refactor codebase",
            "Update implementation"
        ])

        return messages

    def generate_commit_body(self, analysis: CommitAnalysis) -> Optional[str]:
        """Generate a detailed commit body with change information."""
        lines = []

        # Add change summary
        summary = analysis.change_summary
        if summary['total_files'] > 1:
            lines.append("Changes:")

            if summary['files_added'] > 0:
                lines.append(f"- Added {summary['files_added']} files")
            if summary['files_modified'] > 0:
                lines.append(f"- Modified {summary['files_modified']} files")
            if summary['files_removed'] > 0:
                lines.append(f"- Removed {summary['files_removed']} files")

            lines.append(f"- {summary['lines_added']}+ / {summary['lines_removed']}- lines")
            lines.append("")

        # Add file-specific information for significant changes
        significant_files = [
            f for f in analysis.file_changes
            if f['lines_added'] + f['lines_removed'] > 10
        ]

        if significant_files and len(significant_files) <= 5:
            lines.append("Modified files:")
            for file_change in significant_files:
                path = file_change['path']
                added = file_change['lines_added']
                removed = file_change['lines_removed']
                lines.append(f"- {path}: +{added}/-{removed}")
            lines.append("")

        # Add breaking change warning
        if analysis.breaking_changes:
            lines.append("BREAKING CHANGE: This commit contains breaking changes")
            lines.append("")

        return "\n".join(lines) if lines else None