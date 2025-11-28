"""
Naming Convention Checker

Analyzes naming conventions for variables, functions, classes, and constants
according to language-specific standards and configurable rules.
"""

import ast
import re
from typing import Dict, List, Any, Set, Optional
from enum import Enum

from ...utils.logger import get_logger


class NamingStyle(Enum):
    """Supported naming convention styles."""
    SNAKE_CASE = "snake_case"
    CAMEL_CASE = "camelCase"
    PASCAL_CASE = "PascalCase"
    KEBAB_CASE = "kebab-case"
    SCREAMING_SNAKE_CASE = "SCREAMING_SNAKE_CASE"
    UPPER_CASE = "UPPERCASE"
    LOWER_CASE = "lowercase"


class NamingChecker:
    """Checker for naming convention analysis."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

        # Default naming conventions by language
        self.naming_conventions = {
            'python': {
                'variables': NamingStyle.SNAKE_CASE,
                'functions': NamingStyle.SNAKE_CASE,
                'classes': NamingStyle.PASCAL_CASE,
                'constants': NamingStyle.SCREAMING_SNAKE_CASE,
                'modules': NamingStyle.SNAKE_CASE,
                'private_prefix': '_',
                'dunder_pattern': r'^__\w+__$'
            },
            'javascript': {
                'variables': NamingStyle.CAMEL_CASE,
                'functions': NamingStyle.CAMEL_CASE,
                'classes': NamingStyle.PASCAL_CASE,
                'constants': NamingStyle.SCREAMING_SNAKE_CASE,
                'private_prefix': '_',
                'jquery_prefix': '$'
            },
            'typescript': {
                'variables': NamingStyle.CAMEL_CASE,
                'functions': NamingStyle.CAMEL_CASE,
                'classes': NamingStyle.PASCAL_CASE,
                'interfaces': NamingStyle.PASCAL_CASE,
                'types': NamingStyle.PASCAL_CASE,
                'constants': NamingStyle.SCREAMING_SNAKE_CASE,
                'private_prefix': '_'
            },
            'java': {
                'variables': NamingStyle.CAMEL_CASE,
                'functions': NamingStyle.CAMEL_CASE,
                'classes': NamingStyle.PASCAL_CASE,
                'constants': NamingStyle.SCREAMING_SNAKE_CASE,
                'packages': NamingStyle.LOWER_CASE
            }
        }

    def check(self, content: str, ast_tree: Any, language: str) -> Dict[str, Any]:
        """
        Check for naming convention issues.

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
            conventions = self.naming_conventions.get(language, {})
            if not conventions:
                return {'issues': issues, 'suggestions': suggestions}

            if language == 'python' and ast_tree:
                python_results = self._check_python_naming(ast_tree, conventions)
                issues.extend(python_results['issues'])
                suggestions.extend(python_results['suggestions'])

            elif language in ['javascript', 'typescript']:
                js_results = self._check_javascript_naming(content, ast_tree, conventions)
                issues.extend(js_results['issues'])
                suggestions.extend(js_results['suggestions'])

            # Check for general naming issues
            general_issues = self._check_general_naming_issues(content)
            issues.extend(general_issues)

        except Exception as e:
            self.logger.warning(f"Naming convention analysis failed: {e}")

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_python_naming(self, ast_tree: ast.AST, conventions: Dict) -> Dict[str, Any]:
        """Check Python naming conventions."""
        issues = []
        suggestions = []

        # Check class names
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ClassDef):
                if not self._matches_naming_style(node.name, conventions.get('classes', NamingStyle.PASCAL_CASE)):
                    issues.append({
                        'type': 'class_naming_convention',
                        'severity': 'warning',
                        'message': f"Class '{node.name}' should use PascalCase naming",
                        'line': node.lineno,
                        'suggestion': f"Rename to '{self._convert_to_style(node.name, NamingStyle.PASCAL_CASE)}'"
                    })

            # Check function names
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                expected_style = conventions.get('functions', NamingStyle.SNAKE_CASE)

                # Skip dunder methods
                if re.match(conventions.get('dunder_pattern', r'^__\w+__$'), node.name):
                    continue

                if not self._matches_naming_style(node.name, expected_style):
                    issues.append({
                        'type': 'function_naming_convention',
                        'severity': 'warning',
                        'message': f"Function '{node.name}' should use snake_case naming",
                        'line': node.lineno,
                        'suggestion': f"Rename to '{self._convert_to_style(node.name, NamingStyle.SNAKE_CASE)}'"
                    })

            # Check variable assignments
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id

                        # Check if it's a constant (all uppercase)
                        if var_name.isupper():
                            if not self._matches_naming_style(var_name, NamingStyle.SCREAMING_SNAKE_CASE):
                                issues.append({
                                    'type': 'constant_naming_convention',
                                    'severity': 'info',
                                    'message': f"Constant '{var_name}' should use SCREAMING_SNAKE_CASE",
                                    'line': node.lineno
                                })
                        else:
                            # Regular variable
                            if not self._matches_naming_style(var_name, conventions.get('variables', NamingStyle.SNAKE_CASE)):
                                issues.append({
                                    'type': 'variable_naming_convention',
                                    'severity': 'info',
                                    'message': f"Variable '{var_name}' should use snake_case naming",
                                    'line': node.lineno,
                                    'suggestion': f"Rename to '{self._convert_to_style(var_name, NamingStyle.SNAKE_CASE)}'"
                                })

        # Check for inconsistent naming patterns
        inconsistency_suggestions = self._check_python_naming_consistency(ast_tree)
        suggestions.extend(inconsistency_suggestions)

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_javascript_naming(self, content: str, ast_tree: Dict[str, Any], conventions: Dict) -> Dict[str, Any]:
        """Check JavaScript/TypeScript naming conventions."""
        issues = []
        suggestions = []

        if not ast_tree:
            return {'issues': issues, 'suggestions': suggestions}

        # Check function names
        functions = ast_tree.get('functions', [])
        for func_info in functions:
            func_name = func_info['name']
            line = func_info['line_start']

            if not self._matches_naming_style(func_name, conventions.get('functions', NamingStyle.CAMEL_CASE)):
                issues.append({
                    'type': 'function_naming_convention',
                    'severity': 'warning',
                    'message': f"Function '{func_name}' should use camelCase naming",
                    'line': line,
                    'suggestion': f"Rename to '{self._convert_to_style(func_name, NamingStyle.CAMEL_CASE)}'"
                })

        # Check variable declarations using regex
        var_issues = self._check_js_variable_naming(content, conventions)
        issues.extend(var_issues)

        # Check class names using regex
        class_issues = self._check_js_class_naming(content, conventions)
        issues.extend(class_issues)

        # Check constant declarations
        const_issues = self._check_js_constant_naming(content)
        issues.extend(const_issues)

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_js_variable_naming(self, content: str, conventions: Dict) -> List[Dict[str, Any]]:
        """Check JavaScript variable naming."""
        issues = []
        lines = content.split('\n')

        # Variable declaration patterns
        var_patterns = [
            r'(?:let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)',
            r'(?:const)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?!function|class|\()',  # Not function/class/arrow
        ]

        for pattern in var_patterns:
            for i, line in enumerate(lines, 1):
                matches = re.finditer(pattern, line)
                for match in matches:
                    var_name = match.group(1)

                    # Skip constants (will be checked separately)
                    if var_name.isupper():
                        continue

                    expected_style = conventions.get('variables', NamingStyle.CAMEL_CASE)
                    if not self._matches_naming_style(var_name, expected_style):
                        issues.append({
                            'type': 'variable_naming_convention',
                            'severity': 'info',
                            'message': f"Variable '{var_name}' should use camelCase naming",
                            'line': i,
                            'suggestion': f"Rename to '{self._convert_to_style(var_name, NamingStyle.CAMEL_CASE)}'"
                        })

        return issues

    def _check_js_class_naming(self, content: str, conventions: Dict) -> List[Dict[str, Any]]:
        """Check JavaScript class naming."""
        issues = []
        lines = content.split('\n')

        class_pattern = r'class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
        for i, line in enumerate(lines, 1):
            matches = re.finditer(class_pattern, line)
            for match in matches:
                class_name = match.group(1)

                if not self._matches_naming_style(class_name, conventions.get('classes', NamingStyle.PASCAL_CASE)):
                    issues.append({
                        'type': 'class_naming_convention',
                        'severity': 'warning',
                        'message': f"Class '{class_name}' should use PascalCase naming",
                        'line': i,
                        'suggestion': f"Rename to '{self._convert_to_style(class_name, NamingStyle.PASCAL_CASE)}'"
                    })

        return issues

    def _check_js_constant_naming(self, content: str) -> List[Dict[str, Any]]:
        """Check JavaScript constant naming."""
        issues = []
        lines = content.split('\n')

        # Look for const declarations that should be constants
        const_pattern = r'const\s+([A-Z_][A-Z0-9_]*)\s*='
        for i, line in enumerate(lines, 1):
            matches = re.finditer(const_pattern, line)
            for match in matches:
                const_name = match.group(1)

                if not self._matches_naming_style(const_name, NamingStyle.SCREAMING_SNAKE_CASE):
                    issues.append({
                        'type': 'constant_naming_convention',
                        'severity': 'info',
                        'message': f"Constant '{const_name}' should use SCREAMING_SNAKE_CASE",
                        'line': i,
                        'suggestion': f"Rename to '{self._convert_to_style(const_name, NamingStyle.SCREAMING_SNAKE_CASE)}'"
                    })

        return issues

    def _check_general_naming_issues(self, content: str) -> List[Dict[str, Any]]:
        """Check for general naming issues across all languages."""
        issues = []
        lines = content.split('\n')

        # Check for single-letter variable names (except common ones like i, j, k)
        single_letter_pattern = r'\b([a-hA-H]|[l-zL-Z])\b\s*[=:]'
        for i, line in enumerate(lines, 1):
            # Skip comments and strings
            if line.strip().startswith(('/', '#', '*', '"""', "'''")):
                continue

            matches = re.finditer(single_letter_pattern, line)
            for match in matches:
                var_name = match.group(1)
                if var_name not in ['i', 'j', 'k', 'x', 'y', 'z']:  # Common loop variables
                    issues.append({
                        'type': 'single_letter_variable',
                        'severity': 'info',
                        'message': f"Single-letter variable '{var_name}' should have a descriptive name",
                        'line': i,
                        'suggestion': "Use descriptive variable names for better code readability"
                    })

        # Check for overly long names
        long_name_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]{30,})\b'
        for i, line in enumerate(lines, 1):
            matches = re.finditer(long_name_pattern, line)
            for match in matches:
                long_name = match.group(1)
                issues.append({
                    'type': 'overly_long_name',
                    'severity': 'info',
                    'message': f"Name '{long_name}' is very long ({len(long_name)} characters)",
                    'line': i,
                    'suggestion': "Consider using a shorter, more concise name"
                })

        # Check for names with numbers that might be unclear
        numbered_name_pattern = r'\b([a-zA-Z_]+[0-9]+[a-zA-Z_]*)\b'
        for i, line in enumerate(lines, 1):
            matches = re.finditer(numbered_name_pattern, line)
            for match in matches:
                numbered_name = match.group(1)
                # Skip common patterns like version numbers
                if not re.match(r'.*(?:v|version|test|temp)\d+.*', numbered_name, re.IGNORECASE):
                    issues.append({
                        'type': 'numbered_name',
                        'severity': 'info',
                        'message': f"Name '{numbered_name}' contains numbers - consider more descriptive naming",
                        'line': i,
                        'suggestion': "Use descriptive names instead of numbered suffixes"
                    })

        return issues

    def _check_python_naming_consistency(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check for naming consistency within Python code."""
        suggestions = []

        # Collect all names and their styles
        function_names = []
        class_names = []
        variable_names = []

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ClassDef):
                class_names.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not re.match(r'^__\w+__$', node.name):  # Skip dunder methods
                    function_names.append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if not target.id.isupper():  # Skip constants
                            variable_names.append(target.id)

        # Check consistency within each category
        if len(function_names) > 1:
            styles = [self._detect_naming_style(name) for name in function_names]
            if len(set(styles)) > 1:
                suggestions.append({
                    'type': 'inconsistent_function_naming',
                    'message': "Inconsistent function naming styles detected",
                    'line': 1,
                    'suggestion': "Use consistent snake_case naming for all functions"
                })

        return suggestions

    def _matches_naming_style(self, name: str, style: NamingStyle) -> bool:
        """Check if a name matches the specified naming style."""
        if style == NamingStyle.SNAKE_CASE:
            return re.match(r'^[a-z]+(_[a-z0-9]+)*$', name) is not None

        elif style == NamingStyle.CAMEL_CASE:
            return re.match(r'^[a-z][a-zA-Z0-9]*$', name) is not None

        elif style == NamingStyle.PASCAL_CASE:
            return re.match(r'^[A-Z][a-zA-Z0-9]*$', name) is not None

        elif style == NamingStyle.KEBAB_CASE:
            return re.match(r'^[a-z]+(-[a-z0-9]+)*$', name) is not None

        elif style == NamingStyle.SCREAMING_SNAKE_CASE:
            return re.match(r'^[A-Z]+(_[A-Z0-9]+)*$', name) is not None

        elif style == NamingStyle.UPPER_CASE:
            return name.isupper()

        elif style == NamingStyle.LOWER_CASE:
            return name.islower()

        return True

    def _detect_naming_style(self, name: str) -> NamingStyle:
        """Detect the naming style of a given name."""
        if re.match(r'^[A-Z]+(_[A-Z0-9]+)*$', name):
            return NamingStyle.SCREAMING_SNAKE_CASE
        elif re.match(r'^[A-Z][a-zA-Z0-9]*$', name):
            return NamingStyle.PASCAL_CASE
        elif re.match(r'^[a-z][a-zA-Z0-9]*$', name):
            return NamingStyle.CAMEL_CASE
        elif re.match(r'^[a-z]+(_[a-z0-9]+)*$', name):
            return NamingStyle.SNAKE_CASE
        elif re.match(r'^[a-z]+(-[a-z0-9]+)*$', name):
            return NamingStyle.KEBAB_CASE
        else:
            return NamingStyle.SNAKE_CASE  # Default fallback

    def _convert_to_style(self, name: str, target_style: NamingStyle) -> str:
        """Convert a name to the target naming style."""
        # First, normalize the name to words
        words = self._split_into_words(name)

        if target_style == NamingStyle.SNAKE_CASE:
            return '_'.join(word.lower() for word in words)

        elif target_style == NamingStyle.CAMEL_CASE:
            if not words:
                return name
            return words[0].lower() + ''.join(word.capitalize() for word in words[1:])

        elif target_style == NamingStyle.PASCAL_CASE:
            return ''.join(word.capitalize() for word in words)

        elif target_style == NamingStyle.KEBAB_CASE:
            return '-'.join(word.lower() for word in words)

        elif target_style == NamingStyle.SCREAMING_SNAKE_CASE:
            return '_'.join(word.upper() for word in words)

        return name

    def _split_into_words(self, name: str) -> List[str]:
        """Split a name into words based on various conventions."""
        # Handle different naming conventions
        if '_' in name:
            # Snake case or screaming snake case
            return [word for word in name.split('_') if word]

        elif '-' in name:
            # Kebab case
            return [word for word in name.split('-') if word]

        else:
            # Camel case or Pascal case - split on capital letters
            words = re.findall(r'[A-Z]*[a-z0-9]*|[A-Z]+(?=[A-Z][a-z]|$)', name)
            return [word for word in words if word]