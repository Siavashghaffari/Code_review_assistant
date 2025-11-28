"""
Error Handling Checker

Analyzes error handling patterns and identifies missing or inadequate
error handling in code.
"""

import ast
import re
from typing import Dict, List, Any, Set, Optional

from ...utils.logger import get_logger


class ErrorHandlingChecker:
    """Checker for error handling analysis."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

    def check(self, content: str, ast_tree: Any, language: str) -> Dict[str, Any]:
        """
        Check for error handling issues.

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
                python_results = self._check_python_error_handling(content, ast_tree)
                issues.extend(python_results['issues'])
                suggestions.extend(python_results['suggestions'])

            elif language in ['javascript', 'typescript']:
                js_results = self._check_javascript_error_handling(content, ast_tree)
                issues.extend(js_results['issues'])
                suggestions.extend(js_results['suggestions'])

        except Exception as e:
            self.logger.warning(f"Error handling analysis failed: {e}")

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_python_error_handling(self, content: str, ast_tree: ast.AST) -> Dict[str, Any]:
        """Check Python error handling patterns."""
        issues = []
        suggestions = []

        # Check for risky operations without try-catch
        risky_operations = self._find_risky_python_operations(ast_tree)
        for operation in risky_operations:
            if not self._is_in_try_block(operation, ast_tree):
                issues.append({
                    'type': 'missing_error_handling',
                    'severity': 'warning',
                    'message': f"Risky operation '{operation['type']}' should be wrapped in try-except",
                    'line': operation['line'],
                    'suggestion': f"Wrap {operation['type']} in try-except block"
                })

        # Check for bare except clauses
        bare_excepts = self._find_bare_except_clauses(ast_tree)
        for except_info in bare_excepts:
            issues.append({
                'type': 'bare_except',
                'severity': 'warning',
                'message': "Bare except clause catches all exceptions",
                'line': except_info['line'],
                'suggestion': "Specify specific exception types instead of using bare 'except:'"
            })

        # Check for empty exception handlers
        empty_handlers = self._find_empty_exception_handlers(ast_tree)
        for handler in empty_handlers:
            issues.append({
                'type': 'empty_exception_handler',
                'severity': 'warning',
                'message': "Empty exception handler silently ignores errors",
                'line': handler['line'],
                'suggestion': "Add appropriate error handling or logging in exception handler"
            })

        # Check for missing finally blocks for resource cleanup
        resource_suggestions = self._check_python_resource_cleanup(ast_tree)
        suggestions.extend(resource_suggestions)

        # Check for exception chaining
        exception_chaining_suggestions = self._check_python_exception_chaining(ast_tree)
        suggestions.extend(exception_chaining_suggestions)

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_javascript_error_handling(self, content: str, ast_tree: Dict[str, Any]) -> Dict[str, Any]:
        """Check JavaScript/TypeScript error handling patterns."""
        issues = []
        suggestions = []

        # Check for unhandled promises
        promise_issues = self._find_unhandled_promises(content)
        issues.extend(promise_issues)

        # Check for missing try-catch around async operations
        async_issues = self._find_unprotected_async_calls(content)
        issues.extend(async_issues)

        # Check for empty catch blocks
        empty_catch_blocks = self._find_empty_catch_blocks(content)
        issues.extend(empty_catch_blocks)

        # Check for missing error callbacks
        callback_suggestions = self._check_callback_error_handling(content)
        suggestions.extend(callback_suggestions)

        # Check for proper error propagation
        propagation_suggestions = self._check_error_propagation(content)
        suggestions.extend(propagation_suggestions)

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _find_risky_python_operations(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Find risky operations that should be wrapped in try-except."""
        risky_operations = []

        for node in ast.walk(ast_tree):
            # File operations
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ['open', 'input']:
                    risky_operations.append({
                        'type': f'call:{node.func.id}',
                        'line': node.lineno,
                        'node': node
                    })

            # Attribute access that might fail
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                # Network operations, file operations, etc.
                risky_methods = ['read', 'write', 'connect', 'request', 'get', 'post']
                if node.func.attr in risky_methods:
                    risky_operations.append({
                        'type': f'method:{node.func.attr}',
                        'line': node.lineno,
                        'node': node
                    })

            # Dictionary/list access
            elif isinstance(node, ast.Subscript):
                risky_operations.append({
                    'type': 'subscript_access',
                    'line': node.lineno,
                    'node': node
                })

        return risky_operations

    def _is_in_try_block(self, operation: Dict[str, Any], ast_tree: ast.AST) -> bool:
        """Check if an operation is already within a try block."""
        target_node = operation['node']

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Try):
                # Check if target_node is within this try block
                for try_node in ast.walk(node):
                    if try_node == target_node:
                        return True

        return False

    def _find_bare_except_clauses(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Find bare except clauses."""
        bare_excepts = []

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bare_excepts.append({
                    'line': node.lineno,
                    'node': node
                })

        return bare_excepts

    def _find_empty_exception_handlers(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Find empty exception handlers."""
        empty_handlers = []

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ExceptHandler):
                # Check if handler body is empty or only contains pass
                if len(node.body) == 0 or (
                    len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
                ):
                    empty_handlers.append({
                        'line': node.lineno,
                        'node': node
                    })

        return empty_handlers

    def _check_python_resource_cleanup(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check for proper resource cleanup patterns."""
        suggestions = []

        for node in ast.walk(ast_tree):
            # Look for file operations without context managers
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == 'open':
                    # Check if it's within a 'with' statement
                    is_in_with = self._is_in_with_statement(node, ast_tree)
                    if not is_in_with:
                        suggestions.append({
                            'type': 'use_context_manager',
                            'message': "Use 'with' statement for file operations to ensure proper cleanup",
                            'line': node.lineno,
                            'suggestion': "Replace open() with 'with open() as f:' for automatic file cleanup"
                        })

        return suggestions

    def _is_in_with_statement(self, target_node: ast.AST, ast_tree: ast.AST) -> bool:
        """Check if a node is within a with statement."""
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.With):
                for with_node in ast.walk(node):
                    if with_node == target_node:
                        return True
        return False

    def _check_python_exception_chaining(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check for proper exception chaining."""
        suggestions = []

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Raise) and node.exc:
                # Check if raising a new exception within an except block
                # without chaining the original exception
                parent_except = self._find_parent_except_handler(node, ast_tree)
                if parent_except and not self._has_exception_chaining(node):
                    suggestions.append({
                        'type': 'exception_chaining',
                        'message': "Consider chaining exceptions to preserve error context",
                        'line': node.lineno,
                        'suggestion': "Use 'raise new_exception from original_exception' for exception chaining"
                    })

        return suggestions

    def _find_parent_except_handler(self, target_node: ast.AST, ast_tree: ast.AST) -> Optional[ast.ExceptHandler]:
        """Find the parent except handler for a node."""
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ExceptHandler):
                for child in ast.walk(node):
                    if child == target_node:
                        return node
        return None

    def _has_exception_chaining(self, raise_node: ast.Raise) -> bool:
        """Check if a raise statement uses exception chaining."""
        return hasattr(raise_node, 'cause') and raise_node.cause is not None

    def _find_unhandled_promises(self, content: str) -> List[Dict[str, Any]]:
        """Find promises without proper error handling."""
        issues = []
        lines = content.split('\n')

        # Look for promises without .catch()
        promise_pattern = r'\.then\s*\([^)]+\)(?!\s*\.catch)'
        for i, line in enumerate(lines, 1):
            if re.search(promise_pattern, line):
                issues.append({
                    'type': 'unhandled_promise',
                    'severity': 'warning',
                    'message': "Promise should have error handling with .catch()",
                    'line': i,
                    'suggestion': "Add .catch() to handle promise rejections"
                })

        return issues

    def _find_unprotected_async_calls(self, content: str) -> List[Dict[str, Any]]:
        """Find async calls without try-catch."""
        issues = []
        lines = content.split('\n')

        # Look for await calls not in try blocks
        for i, line in enumerate(lines, 1):
            if 'await' in line and not self._is_line_in_try_block(i, lines):
                issues.append({
                    'type': 'unprotected_async_call',
                    'severity': 'warning',
                    'message': "Async operation should be wrapped in try-catch",
                    'line': i,
                    'suggestion': "Wrap await call in try-catch block"
                })

        return issues

    def _find_empty_catch_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Find empty catch blocks."""
        issues = []
        lines = content.split('\n')

        # Simple pattern matching for empty catch blocks
        in_catch_block = False
        catch_line = 0
        brace_count = 0

        for i, line in enumerate(lines, 1):
            stripped_line = line.strip()

            if 'catch' in stripped_line and '(' in stripped_line:
                in_catch_block = True
                catch_line = i
                brace_count = 0

            if in_catch_block:
                brace_count += stripped_line.count('{')
                brace_count -= stripped_line.count('}')

                if brace_count == 0 and in_catch_block:
                    # Check if catch block is empty
                    if self._is_empty_catch_block(catch_line, i, lines):
                        issues.append({
                            'type': 'empty_catch_block',
                            'severity': 'warning',
                            'message': "Empty catch block silently ignores errors",
                            'line': catch_line,
                            'suggestion': "Add appropriate error handling or logging in catch block"
                        })
                    in_catch_block = False

        return issues

    def _is_line_in_try_block(self, line_num: int, lines: List[str]) -> bool:
        """Check if a line is within a try block."""
        # Simple heuristic: look backwards for try keyword
        for i in range(line_num - 1, max(0, line_num - 20), -1):
            line = lines[i].strip()
            if line.startswith('try') and '{' in line:
                return True
            if line.startswith('catch') or line.startswith('finally'):
                return False
        return False

    def _is_empty_catch_block(self, start_line: int, end_line: int, lines: List[str]) -> bool:
        """Check if a catch block is empty."""
        for i in range(start_line - 1, end_line):
            line = lines[i].strip()
            # Skip the catch declaration line and braces
            if (line and
                not line.startswith('catch') and
                line not in ['{', '}'] and
                not line.startswith('//')):
                return False
        return True

    def _check_callback_error_handling(self, content: str) -> List[Dict[str, Any]]:
        """Check for proper error handling in callbacks."""
        suggestions = []

        # Look for Node.js style callbacks without error checking
        callback_pattern = r'function\s*\([^)]*err[^)]*\)\s*\{'
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            if re.search(callback_pattern, line):
                # Check if error is handled in the next few lines
                error_handled = False
                for j in range(i, min(i + 5, len(lines))):
                    if 'if' in lines[j] and 'err' in lines[j]:
                        error_handled = True
                        break

                if not error_handled:
                    suggestions.append({
                        'type': 'callback_error_handling',
                        'message': "Callback should check for error parameter",
                        'line': i,
                        'suggestion': "Add error checking: if (err) { /* handle error */ }"
                    })

        return suggestions

    def _check_error_propagation(self, content: str) -> List[Dict[str, Any]]:
        """Check for proper error propagation patterns."""
        suggestions = []

        # Look for functions that might need to propagate errors
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Functions with async operations that don't seem to handle/propagate errors
            if ('async function' in line or 'function' in line) and 'throw' not in content:
                # This is a simplified check - more sophisticated analysis would be needed
                if any(keyword in content for keyword in ['await', 'fetch', 'request', 'readFile']):
                    suggestions.append({
                        'type': 'error_propagation',
                        'message': "Consider propagating errors or adding explicit error handling",
                        'line': i,
                        'suggestion': "Ensure errors are properly handled or propagated to caller"
                    })

        return suggestions