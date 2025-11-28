"""
Style Checker

Analyzes code style consistency including indentation, spacing, line endings,
import organization, and other stylistic conventions.
"""

import ast
import re
from typing import Dict, List, Any, Set, Optional, Tuple
from collections import defaultdict, Counter

from ...utils.logger import get_logger


class StyleChecker:
    """Checker for code style consistency."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

        # Style configuration
        self.preferred_quote_style = config.get('style', {}).get('quote_style', 'double')
        self.max_line_length = config.get('style', {}).get('max_line_length', 120)
        self.indentation_size = config.get('style', {}).get('indentation_size', 4)
        self.prefer_spaces = config.get('style', {}).get('prefer_spaces', True)

    def check(self, content: str, ast_tree: Any, language: str) -> Dict[str, Any]:
        """
        Check for style consistency issues.

        Args:
            content: File content
            ast_tree: Parsed AST
            language: Programming language

        Returns:
            Dictionary with issues and suggestions
        """
        issues = []
        suggestions = []

        try:
            # Check indentation consistency
            indent_issues = self._check_indentation_consistency(content)
            issues.extend(indent_issues)

            # Check line length
            line_length_issues = self._check_line_length(content)
            issues.extend(line_length_issues)

            # Check quote consistency
            quote_issues = self._check_quote_consistency(content, language)
            issues.extend(quote_issues)

            # Check whitespace issues
            whitespace_issues = self._check_whitespace_issues(content)
            issues.extend(whitespace_issues)

            # Language-specific checks
            if language == 'python' and ast_tree:
                python_style_issues = self._check_python_style(content, ast_tree)
                issues.extend(python_style_issues['issues'])
                suggestions.extend(python_style_issues['suggestions'])

            elif language in ['javascript', 'typescript']:
                js_style_issues = self._check_javascript_style(content)
                issues.extend(js_style_issues['issues'])
                suggestions.extend(js_style_issues['suggestions'])

            # Check general style patterns
            general_suggestions = self._check_general_style_patterns(content, language)
            suggestions.extend(general_suggestions)

        except Exception as e:
            self.logger.warning(f"Style analysis failed: {e}")

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_indentation_consistency(self, content: str) -> List[Dict[str, Any]]:
        """Check for consistent indentation throughout the file."""
        issues = []
        lines = content.split('\n')

        # Detect indentation patterns
        indentation_patterns = []
        tab_count = 0
        space_count = 0

        for i, line in enumerate(lines, 1):
            if line.strip():  # Skip empty lines
                leading_whitespace = len(line) - len(line.lstrip())
                if leading_whitespace > 0:
                    indent_text = line[:leading_whitespace]

                    # Count tabs and spaces
                    if '\t' in indent_text:
                        tab_count += 1
                    if ' ' in indent_text:
                        space_count += 1

                    # Check for mixed indentation
                    if '\t' in indent_text and ' ' in indent_text:
                        issues.append({
                            'type': 'mixed_indentation',
                            'severity': 'warning',
                            'message': "Mixed tabs and spaces in indentation",
                            'line': i,
                            'suggestion': "Use either tabs or spaces consistently for indentation"
                        })

        # Check for inconsistent indentation style
        if tab_count > 0 and space_count > 0:
            primary_style = "tabs" if tab_count > space_count else "spaces"
            minority_style = "spaces" if primary_style == "tabs" else "tabs"

            issues.append({
                'type': 'inconsistent_indentation_style',
                'severity': 'info',
                'message': f"File uses both {primary_style} and {minority_style} for indentation",
                'line': 1,
                'suggestion': f"Use {primary_style} consistently throughout the file"
            })

        return issues

    def _check_line_length(self, content: str) -> List[Dict[str, Any]]:
        """Check for lines exceeding maximum length."""
        issues = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            if len(line) > self.max_line_length:
                issues.append({
                    'type': 'line_too_long',
                    'severity': 'info',
                    'message': f"Line exceeds maximum length ({len(line)}/{self.max_line_length} characters)",
                    'line': i,
                    'suggestion': "Break long lines to improve readability"
                })

        return issues

    def _check_quote_consistency(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Check for consistent quote usage."""
        issues = []

        if language not in ['python', 'javascript', 'typescript']:
            return issues

        # Find all string literals
        string_patterns = [
            r'\'([^\'\\]|\\.)*\'',  # Single quotes
            r'"([^"\\]|\\.)*"',    # Double quotes
        ]

        single_quote_count = 0
        double_quote_count = 0
        lines = content.split('\n')

        for pattern in string_patterns:
            for i, line in enumerate(lines, 1):
                # Skip comments
                if line.strip().startswith(('#', '//', '/*')):
                    continue

                matches = re.findall(pattern, line)
                for match in matches:
                    if pattern.startswith(r"'"):
                        single_quote_count += 1
                    else:
                        double_quote_count += 1

        # Check for inconsistent usage
        total_quotes = single_quote_count + double_quote_count
        if total_quotes > 5:  # Only flag if there are enough quotes to matter
            minority_percentage = min(single_quote_count, double_quote_count) / total_quotes

            if minority_percentage > 0.2:  # More than 20% minority usage
                preferred = "double" if double_quote_count > single_quote_count else "single"
                issues.append({
                    'type': 'inconsistent_quote_style',
                    'severity': 'info',
                    'message': f"Inconsistent quote style - consider using {preferred} quotes consistently",
                    'line': 1,
                    'suggestion': f"Use {preferred} quotes consistently throughout the file"
                })

        return issues

    def _check_whitespace_issues(self, content: str) -> List[Dict[str, Any]]:
        """Check for whitespace-related issues."""
        issues = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Trailing whitespace
            if line.rstrip() != line:
                issues.append({
                    'type': 'trailing_whitespace',
                    'severity': 'info',
                    'message': "Line has trailing whitespace",
                    'line': i,
                    'suggestion': "Remove trailing whitespace"
                })

            # Multiple consecutive blank lines (more than 2)
            if i > 2 and all(not lines[j].strip() for j in range(i-3, i)):
                issues.append({
                    'type': 'excessive_blank_lines',
                    'severity': 'info',
                    'message': "Too many consecutive blank lines",
                    'line': i,
                    'suggestion': "Limit consecutive blank lines to 1-2"
                })

        # Check for missing final newline
        if content and not content.endswith('\n'):
            issues.append({
                'type': 'missing_final_newline',
                'severity': 'info',
                'message': "File should end with a newline",
                'line': len(lines),
                'suggestion': "Add a newline at the end of the file"
            })

        return issues

    def _check_python_style(self, content: str, ast_tree: ast.AST) -> Dict[str, Any]:
        """Check Python-specific style issues."""
        issues = []
        suggestions = []

        # Check import organization
        import_issues = self._check_python_import_style(ast_tree)
        issues.extend(import_issues)

        # Check for proper spacing around operators
        operator_issues = self._check_python_operator_spacing(content)
        issues.extend(operator_issues)

        # Check function and class spacing
        spacing_issues = self._check_python_function_class_spacing(content, ast_tree)
        issues.extend(spacing_issues)

        # Check for PEP 8 compliance suggestions
        pep8_suggestions = self._check_pep8_compliance(content, ast_tree)
        suggestions.extend(pep8_suggestions)

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_python_import_style(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check Python import organization and style."""
        issues = []

        imports = []
        from_imports = []

        # Collect all imports
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        'module': alias.name,
                        'line': node.lineno,
                        'type': 'import'
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                from_imports.append({
                    'module': module,
                    'line': node.lineno,
                    'type': 'from_import',
                    'names': [alias.name for alias in node.names]
                })

        # Check import grouping (should be: stdlib, third-party, local)
        all_imports = imports + from_imports
        all_imports.sort(key=lambda x: x['line'])

        # Check for imports not at the top (after the first non-import statement)
        first_non_import_line = None
        for node in ast.walk(ast_tree):
            if (not isinstance(node, (ast.Import, ast.ImportFrom)) and
                hasattr(node, 'lineno') and
                not isinstance(node, ast.Module)):
                if first_non_import_line is None or node.lineno < first_non_import_line:
                    first_non_import_line = node.lineno

        for import_info in all_imports:
            if first_non_import_line and import_info['line'] > first_non_import_line:
                issues.append({
                    'type': 'import_not_at_top',
                    'severity': 'warning',
                    'message': "Imports should be at the top of the file",
                    'line': import_info['line'],
                    'suggestion': "Move imports to the top of the file"
                })

        return issues

    def _check_python_operator_spacing(self, content: str) -> List[Dict[str, Any]]:
        """Check spacing around Python operators."""
        issues = []
        lines = content.split('\n')

        # Operators that should have spaces around them
        binary_ops = [r'\+', r'-', r'\*', r'/', r'==', r'!=', r'<=', r'>=', r'<', r'>', r'=(?!=)']

        for i, line in enumerate(lines, 1):
            # Skip comments and strings (simplified check)
            if line.strip().startswith('#') or '"""' in line or "'''" in line:
                continue

            for op_pattern in binary_ops:
                # Check for missing spaces around operators
                pattern = f'\\S{op_pattern}\\S'
                if re.search(pattern, line):
                    issues.append({
                        'type': 'missing_operator_spacing',
                        'severity': 'info',
                        'message': "Missing spaces around operator",
                        'line': i,
                        'suggestion': "Add spaces around operators for better readability"
                    })

        return issues

    def _check_python_function_class_spacing(self, content: str, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check spacing before function and class definitions."""
        issues = []
        lines = content.split('\n')

        for node in ast.walk(ast_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                line_num = node.lineno

                # Top-level functions should have 2 blank lines before them
                if line_num > 3:  # Not at the very beginning
                    # Check if this is a top-level function (not nested)
                    is_top_level = True
                    for parent in ast.walk(ast_tree):
                        if (isinstance(parent, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and
                            parent != node and
                            hasattr(parent, 'lineno') and hasattr(parent, 'end_lineno')):
                            if (parent.lineno < node.lineno <
                                getattr(parent, 'end_lineno', float('inf'))):
                                is_top_level = False
                                break

                    if is_top_level:
                        # Check for 2 blank lines before
                        blank_lines_before = 0
                        for j in range(line_num - 2, max(0, line_num - 5), -1):
                            if j < len(lines) and not lines[j].strip():
                                blank_lines_before += 1
                            else:
                                break

                        if blank_lines_before < 2:
                            issues.append({
                                'type': 'insufficient_function_spacing',
                                'severity': 'info',
                                'message': "Top-level functions should have 2 blank lines before them",
                                'line': line_num,
                                'suggestion': "Add 2 blank lines before top-level function definitions"
                            })

            elif isinstance(node, ast.ClassDef):
                line_num = node.lineno

                # Classes should have 2 blank lines before them
                if line_num > 3:
                    blank_lines_before = 0
                    for j in range(line_num - 2, max(0, line_num - 5), -1):
                        if j < len(lines) and not lines[j].strip():
                            blank_lines_before += 1
                        else:
                            break

                    if blank_lines_before < 2:
                        issues.append({
                            'type': 'insufficient_class_spacing',
                            'severity': 'info',
                            'message': "Classes should have 2 blank lines before them",
                            'line': line_num,
                            'suggestion': "Add 2 blank lines before class definitions"
                        })

        return issues

    def _check_pep8_compliance(self, content: str, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check for PEP 8 compliance suggestions."""
        suggestions = []

        # Check for lambda usage that could be replaced with def
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Lambda):
                suggestions.append({
                    'type': 'lambda_to_def',
                    'message': "Consider using a def statement instead of lambda for better readability",
                    'line': node.lineno,
                    'suggestion': "Replace lambda with a proper function definition"
                })

        return suggestions

    def _check_javascript_style(self, content: str) -> Dict[str, Any]:
        """Check JavaScript/TypeScript-specific style issues."""
        issues = []
        suggestions = []

        # Check semicolon usage
        semicolon_issues = self._check_semicolon_consistency(content)
        issues.extend(semicolon_issues)

        # Check brace style
        brace_issues = self._check_brace_style(content)
        issues.extend(brace_issues)

        # Check spacing in object literals and arrays
        spacing_issues = self._check_js_spacing(content)
        issues.extend(spacing_issues)

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_semicolon_consistency(self, content: str) -> List[Dict[str, Any]]:
        """Check semicolon usage consistency in JavaScript."""
        issues = []
        lines = content.split('\n')

        with_semicolon = 0
        without_semicolon = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip empty lines, comments, and control structures
            if (not stripped or
                stripped.startswith('//') or
                stripped.startswith('/*') or
                stripped.endswith('{') or
                stripped.endswith('}') or
                any(keyword in stripped for keyword in ['if', 'for', 'while', 'function', 'class'])):
                continue

            # Check if line ends with semicolon
            if stripped.endswith(';'):
                with_semicolon += 1
            elif not stripped.endswith((',', '(', ')')):
                without_semicolon += 1

        # Check for inconsistency
        total_statements = with_semicolon + without_semicolon
        if total_statements > 5:  # Only check if there are enough statements
            minority_percentage = min(with_semicolon, without_semicolon) / total_statements

            if minority_percentage > 0.2:  # More than 20% minority usage
                preferred = "with" if with_semicolon > without_semicolon else "without"
                issues.append({
                    'type': 'inconsistent_semicolon_usage',
                    'severity': 'info',
                    'message': f"Inconsistent semicolon usage - use semicolons {preferred} consistently",
                    'line': 1,
                    'suggestion': f"Use semicolons {preferred} consistently throughout the file"
                })

        return issues

    def _check_brace_style(self, content: str) -> List[Dict[str, Any]]:
        """Check brace placement consistency."""
        issues = []
        lines = content.split('\n')

        same_line_braces = 0
        new_line_braces = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Look for opening braces after control structures
            if re.search(r'(if|for|while|function|class)\s*[^{]*\{', stripped):
                same_line_braces += 1
            elif (stripped == '{' and i > 1 and
                  re.search(r'(if|for|while|function|class)', lines[i-2].strip())):
                new_line_braces += 1

        # Check for inconsistency
        total_braces = same_line_braces + new_line_braces
        if total_braces > 3:
            if same_line_braces > 0 and new_line_braces > 0:
                preferred = "same line" if same_line_braces > new_line_braces else "new line"
                issues.append({
                    'type': 'inconsistent_brace_style',
                    'severity': 'info',
                    'message': f"Inconsistent brace placement - use {preferred} style consistently",
                    'line': 1,
                    'suggestion': f"Place opening braces on the {preferred} consistently"
                })

        return issues

    def _check_js_spacing(self, content: str) -> List[Dict[str, Any]]:
        """Check spacing in JavaScript object literals and arrays."""
        issues = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Check for missing spaces in object literals
            if re.search(r'\{[^\s]', line):
                issues.append({
                    'type': 'missing_object_spacing',
                    'severity': 'info',
                    'message': "Missing space after opening brace in object literal",
                    'line': i,
                    'suggestion': "Add space after opening brace: { key: value }"
                })

            if re.search(r'[^\s]\}', line):
                issues.append({
                    'type': 'missing_object_spacing',
                    'severity': 'info',
                    'message': "Missing space before closing brace in object literal",
                    'line': i,
                    'suggestion': "Add space before closing brace: { key: value }"
                })

        return issues

    def _check_general_style_patterns(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Check general style patterns across languages."""
        suggestions = []

        # Check for TODO/FIXME comments without tracking info
        todo_pattern = r'(TODO|FIXME|XXX|HACK)\s*:?\s*([^(\n]*)'
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            matches = re.finditer(todo_pattern, line, re.IGNORECASE)
            for match in matches:
                todo_text = match.group(2).strip()
                if len(todo_text) < 10:  # Very short or missing description
                    suggestions.append({
                        'type': 'incomplete_todo',
                        'message': f"{match.group(1)} comment should include detailed description",
                        'line': i,
                        'suggestion': "Add descriptive text and consider adding assignee/date"
                    })

        # Check for magic numbers
        magic_number_pattern = r'\b(?<![\w.])((?!0|1|2|10|100|1000)\d{2,})\b(?![\w.])'
        for i, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith(('#', '//', '/*')):
                continue

            matches = re.finditer(magic_number_pattern, line)
            for match in matches:
                number = match.group(1)
                suggestions.append({
                    'type': 'magic_number',
                    'message': f"Magic number '{number}' should be replaced with named constant",
                    'line': i,
                    'suggestion': f"Define a named constant for the value {number}"
                })

        return suggestions