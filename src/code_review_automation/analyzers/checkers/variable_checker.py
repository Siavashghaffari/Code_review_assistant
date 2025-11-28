"""
Variable Checker

Analyzes variable usage to detect unused variables, undefined variables,
and variable shadowing issues.
"""

import ast
import re
from typing import Dict, List, Any, Set, Optional
from collections import defaultdict

from ...utils.logger import get_logger


class VariableChecker:
    """Checker for variable usage analysis."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

    def check(self, content: str, ast_tree: Any, language: str) -> Dict[str, Any]:
        """
        Check for variable-related issues.

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
            if language == 'python' and ast_tree:
                python_results = self._check_python_variables(ast_tree)
                issues.extend(python_results['issues'])
                suggestions.extend(python_results['suggestions'])

            elif language in ['javascript', 'typescript']:
                js_results = self._check_javascript_variables(content, ast_tree)
                issues.extend(js_results['issues'])
                suggestions.extend(js_results['suggestions'])

        except Exception as e:
            self.logger.warning(f"Variable analysis failed: {e}")

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_python_variables(self, ast_tree: ast.AST) -> Dict[str, Any]:
        """Check Python variables for issues."""
        issues = []
        suggestions = []

        # Collect variable definitions and usages
        scope_analyzer = PythonScopeAnalyzer()
        scopes = scope_analyzer.analyze(ast_tree)

        for scope_name, scope_info in scopes.items():
            # Check for unused variables
            unused_vars = scope_info['defined'] - scope_info['used']
            for var_name, var_info in unused_vars:
                # Skip common patterns that are intentionally unused
                if self._is_intentionally_unused(var_name):
                    continue

                issues.append({
                    'type': 'unused_variable',
                    'severity': 'warning',
                    'message': f"Variable '{var_name}' is defined but never used",
                    'line': var_info['line'],
                    'suggestion': f"Remove unused variable '{var_name}' or prefix with underscore if intentional"
                })

            # Check for undefined variables (used but not defined)
            undefined_vars = scope_info['used'] - scope_info['defined']
            for var_name, var_info in undefined_vars:
                # Skip built-ins and imports
                if self._is_builtin_or_import(var_name, ast_tree):
                    continue

                issues.append({
                    'type': 'undefined_variable',
                    'severity': 'error',
                    'message': f"Variable '{var_name}' is used but not defined in this scope",
                    'line': var_info['line']
                })

            # Check for variable shadowing
            shadowing_issues = self._find_variable_shadowing(scope_info, scopes)
            issues.extend(shadowing_issues)

        # Check for global variable usage
        global_issues = self._check_global_variables(ast_tree)
        suggestions.extend(global_issues)

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_javascript_variables(self, content: str, ast_tree: Dict[str, Any]) -> Dict[str, Any]:
        """Check JavaScript/TypeScript variables for issues."""
        issues = []
        suggestions = []

        if not ast_tree:
            return {'issues': issues, 'suggestions': suggestions}

        # Extract variable declarations and usages
        declared_vars = self._extract_js_declarations(content)
        used_vars = self._extract_js_usages(content)

        # Check for unused variables
        for var_info in declared_vars:
            var_name = var_info['name']
            if var_name not in used_vars and not self._is_intentionally_unused(var_name):
                issues.append({
                    'type': 'unused_variable',
                    'severity': 'warning',
                    'message': f"Variable '{var_name}' is declared but never used",
                    'line': var_info['line'],
                    'suggestion': f"Remove unused variable '{var_name}'"
                })

        # Check for var usage (suggest let/const)
        var_declarations = self._find_var_declarations(content)
        for var_decl in var_declarations:
            suggestions.append({
                'type': 'prefer_const_let',
                'message': f"Use 'const' or 'let' instead of 'var' for variable '{var_decl['name']}'",
                'line': var_decl['line'],
                'suggestion': "Replace 'var' with 'const' (if never reassigned) or 'let'"
            })

        # Check for const reassignment patterns
        const_issues = self._check_const_reassignment(content)
        issues.extend(const_issues)

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _is_intentionally_unused(self, var_name: str) -> bool:
        """Check if variable is intentionally unused based on naming patterns."""
        return (
            var_name.startswith('_') or
            var_name in ['unused', 'ignore', 'dummy'] or
            var_name.startswith('unused_')
        )

    def _is_builtin_or_import(self, var_name: str, ast_tree: ast.AST) -> bool:
        """Check if variable is a builtin or import."""
        # Check if it's a Python builtin
        python_builtins = {
            'print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set',
            'tuple', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted',
            'max', 'min', 'sum', 'any', 'all', 'abs', 'round', 'isinstance',
            'hasattr', 'getattr', 'setattr', 'delattr', 'super', 'type', 'object'
        }

        if var_name in python_builtins:
            return True

        # Check if it's imported
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname == var_name or alias.name == var_name:
                        return True
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.asname == var_name or alias.name == var_name:
                        return True

        return False

    def _find_variable_shadowing(self, scope_info: Dict, all_scopes: Dict) -> List[Dict[str, Any]]:
        """Find variables that shadow variables in outer scopes."""
        issues = []

        for var_name, var_info in scope_info['defined']:
            # Check if this variable shadows a variable in a parent scope
            for other_scope_name, other_scope_info in all_scopes.items():
                if other_scope_name != scope_info.get('name'):
                    for other_var_name, other_var_info in other_scope_info['defined']:
                        if var_name == other_var_name:
                            issues.append({
                                'type': 'variable_shadowing',
                                'severity': 'warning',
                                'message': f"Variable '{var_name}' shadows variable from outer scope",
                                'line': var_info['line'],
                                'suggestion': f"Consider renaming variable '{var_name}' to avoid shadowing"
                            })

        return issues

    def _check_global_variables(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check for global variable usage and suggest alternatives."""
        suggestions = []

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Global):
                for name in node.names:
                    suggestions.append({
                        'type': 'global_variable_usage',
                        'message': f"Global variable '{name}' used - consider passing as parameter",
                        'line': node.lineno,
                        'suggestion': "Consider refactoring to avoid global variables"
                    })

        return suggestions

    def _extract_js_declarations(self, content: str) -> List[Dict[str, Any]]:
        """Extract JavaScript variable declarations."""
        declarations = []

        # Match const, let, var declarations
        patterns = [
            r'(const|let|var)\s+(\w+)(?:\s*=\s*[^;,]+)?(?:[,;]|$)',
            r'(const|let|var)\s*\{\s*([^}]+)\s*\}\s*=',  # Destructuring
            r'(const|let|var)\s*\[\s*([^\]]+)\s*\]\s*='   # Array destructuring
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                line_no = content[:match.start()].count('\n') + 1

                if '{' in match.group(0) or '[' in match.group(0):
                    # Handle destructuring - extract individual variable names
                    var_part = match.group(2)
                    var_names = re.findall(r'\b(\w+)\b', var_part)
                    for var_name in var_names:
                        if var_name not in ['const', 'let', 'var']:
                            declarations.append({
                                'name': var_name,
                                'line': line_no,
                                'type': match.group(1)
                            })
                else:
                    declarations.append({
                        'name': match.group(2),
                        'line': line_no,
                        'type': match.group(1)
                    })

        return declarations

    def _extract_js_usages(self, content: str) -> Set[str]:
        """Extract JavaScript variable usages."""
        # This is a simplified approach - a full parser would be more accurate
        used_vars = set()

        # Find variable references (excluding keywords and declarations)
        js_keywords = {
            'const', 'let', 'var', 'function', 'class', 'if', 'else', 'for',
            'while', 'do', 'switch', 'case', 'default', 'break', 'continue',
            'return', 'try', 'catch', 'finally', 'throw', 'new', 'this',
            'super', 'extends', 'import', 'export', 'from', 'as', 'async',
            'await', 'yield', 'typeof', 'instanceof', 'in', 'of', 'delete',
            'void', 'null', 'undefined', 'true', 'false'
        }

        # Find identifiers that are likely variable references
        identifier_pattern = r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\b'
        for match in re.finditer(identifier_pattern, content):
            var_name = match.group(1)
            if var_name not in js_keywords and not var_name.isdigit():
                used_vars.add(var_name)

        return used_vars

    def _find_var_declarations(self, content: str) -> List[Dict[str, Any]]:
        """Find var declarations in JavaScript."""
        var_declarations = []

        var_pattern = r'\bvar\s+(\w+)'
        for match in re.finditer(var_pattern, content, re.MULTILINE):
            line_no = content[:match.start()].count('\n') + 1
            var_declarations.append({
                'name': match.group(1),
                'line': line_no
            })

        return var_declarations

    def _check_const_reassignment(self, content: str) -> List[Dict[str, Any]]:
        """Check for potential const reassignment issues."""
        issues = []

        # Find const declarations
        const_vars = set()
        const_pattern = r'\bconst\s+(\w+)'
        for match in re.finditer(const_pattern, content):
            const_vars.add(match.group(1))

        # Look for reassignment patterns
        for var_name in const_vars:
            reassignment_pattern = f'{var_name}\\s*='
            for match in re.finditer(reassignment_pattern, content):
                line_no = content[:match.start()].count('\n') + 1
                # Skip the original declaration
                if 'const' not in content[max(0, match.start()-20):match.start()]:
                    issues.append({
                        'type': 'const_reassignment',
                        'severity': 'error',
                        'message': f"Cannot reassign const variable '{var_name}'",
                        'line': line_no
                    })

        return issues


class PythonScopeAnalyzer:
    """Analyzes Python scopes to track variable definitions and usages."""

    def __init__(self):
        self.scopes = {}
        self.current_scope = None

    def analyze(self, ast_tree: ast.AST) -> Dict[str, Any]:
        """Analyze AST to build scope information."""
        self.scopes = {'module': {'defined': set(), 'used': set(), 'name': 'module'}}
        self.current_scope = 'module'

        self.visit(ast_tree)
        return self.scopes

    def visit(self, node: ast.AST) -> None:
        """Visit AST node and track variable usage."""
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        visitor(node)

    def generic_visit(self, node: ast.AST) -> None:
        """Default visitor for AST nodes."""
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        # Create new scope for function
        func_scope = f'function:{node.name}'
        self.scopes[func_scope] = {'defined': set(), 'used': set(), 'name': func_scope}

        # Add function parameters to defined variables
        for arg in node.args.args:
            self.scopes[func_scope]['defined'].add((arg.arg, {'line': node.lineno}))

        # Visit function body in new scope
        old_scope = self.current_scope
        self.current_scope = func_scope

        for child in ast.iter_child_nodes(node):
            if child != node.args:  # Skip args as we already processed them
                self.visit(child)

        self.current_scope = old_scope

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self.visit_FunctionDef(node)  # Same logic as regular function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        # Create new scope for class
        class_scope = f'class:{node.name}'
        self.scopes[class_scope] = {'defined': set(), 'used': set(), 'name': class_scope}

        # Visit class body in new scope
        old_scope = self.current_scope
        self.current_scope = class_scope

        for child in ast.iter_child_nodes(node):
            self.visit(child)

        self.current_scope = old_scope

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignment statement."""
        # Mark assigned variables as defined
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.scopes[self.current_scope]['defined'].add((target.id, {'line': node.lineno}))

        # Visit the value being assigned
        self.visit(node.value)

    def visit_Name(self, node: ast.Name) -> None:
        """Visit name reference."""
        if isinstance(node.ctx, ast.Load):
            # Variable is being used
            self.scopes[self.current_scope]['used'].add((node.id, {'line': node.lineno}))