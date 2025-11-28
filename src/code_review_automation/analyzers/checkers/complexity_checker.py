"""
Complexity Checker

Analyzes code complexity including cyclomatic complexity, cognitive complexity,
function length, nesting depth, and suggests simplifications.
"""

import ast
import re
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

from ...utils.logger import get_logger


class ComplexityChecker:
    """Checker for code complexity analysis."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

        # Configurable thresholds
        self.max_cyclomatic_complexity = config.get('complexity', {}).get('max_cyclomatic', 10)
        self.max_cognitive_complexity = config.get('complexity', {}).get('max_cognitive', 15)
        self.max_function_length = config.get('complexity', {}).get('max_function_lines', 50)
        self.max_nesting_depth = config.get('complexity', {}).get('max_nesting_depth', 4)
        self.max_parameters = config.get('complexity', {}).get('max_parameters', 7)

    def check(self, content: str, ast_tree: Any, language: str) -> Dict[str, Any]:
        """
        Check for complexity issues.

        Args:
            content: File content
            ast_tree: Parsed AST
            language: Programming language

        Returns:
            Dictionary with issues, suggestions, and metrics
        """
        issues = []
        suggestions = []
        metrics = {}

        try:
            if language == 'python' and ast_tree:
                python_results = self._check_python_complexity(content, ast_tree)
                issues.extend(python_results['issues'])
                suggestions.extend(python_results['suggestions'])
                metrics.update(python_results['metrics'])

            elif language in ['javascript', 'typescript']:
                js_results = self._check_javascript_complexity(content, ast_tree)
                issues.extend(js_results['issues'])
                suggestions.extend(js_results['suggestions'])
                metrics.update(js_results['metrics'])

            # Add general complexity metrics
            general_metrics = self._calculate_general_metrics(content)
            metrics.update(general_metrics)

        except Exception as e:
            self.logger.warning(f"Complexity analysis failed: {e}")

        return {
            'issues': issues,
            'suggestions': suggestions,
            'metrics': metrics
        }

    def _check_python_complexity(self, content: str, ast_tree: ast.AST) -> Dict[str, Any]:
        """Check Python code complexity."""
        issues = []
        suggestions = []
        metrics = {}

        analyzer = PythonComplexityAnalyzer(self.max_cyclomatic_complexity,
                                           self.max_cognitive_complexity,
                                           self.max_function_length,
                                           self.max_nesting_depth,
                                           self.max_parameters)

        function_metrics = analyzer.analyze(content, ast_tree)

        for func_name, func_metrics in function_metrics.items():
            # Cyclomatic complexity issues
            if func_metrics['cyclomatic_complexity'] > self.max_cyclomatic_complexity:
                issues.append({
                    'type': 'high_cyclomatic_complexity',
                    'severity': 'warning',
                    'message': f"Function '{func_name}' has high cyclomatic complexity ({func_metrics['cyclomatic_complexity']})",
                    'line': func_metrics['line_start'],
                    'suggestion': "Consider breaking this function into smaller functions"
                })

            # Cognitive complexity issues
            if func_metrics['cognitive_complexity'] > self.max_cognitive_complexity:
                issues.append({
                    'type': 'high_cognitive_complexity',
                    'severity': 'warning',
                    'message': f"Function '{func_name}' has high cognitive complexity ({func_metrics['cognitive_complexity']})",
                    'line': func_metrics['line_start'],
                    'suggestion': "Consider simplifying the logic or breaking into smaller functions"
                })

            # Function length issues
            if func_metrics['length'] > self.max_function_length:
                issues.append({
                    'type': 'long_function',
                    'severity': 'info',
                    'message': f"Function '{func_name}' is very long ({func_metrics['length']} lines)",
                    'line': func_metrics['line_start'],
                    'suggestion': "Consider breaking this function into smaller, more focused functions"
                })

            # Nesting depth issues
            if func_metrics['max_nesting_depth'] > self.max_nesting_depth:
                issues.append({
                    'type': 'deep_nesting',
                    'severity': 'warning',
                    'message': f"Function '{func_name}' has deep nesting (depth: {func_metrics['max_nesting_depth']})",
                    'line': func_metrics['line_start'],
                    'suggestion': "Consider using early returns or extracting nested logic into separate functions"
                })

            # Too many parameters
            if func_metrics['parameter_count'] > self.max_parameters:
                issues.append({
                    'type': 'too_many_parameters',
                    'severity': 'warning',
                    'message': f"Function '{func_name}' has too many parameters ({func_metrics['parameter_count']})",
                    'line': func_metrics['line_start'],
                    'suggestion': "Consider using a configuration object or breaking the function down"
                })

        # Calculate overall metrics
        if function_metrics:
            complexities = [m['cyclomatic_complexity'] for m in function_metrics.values()]
            metrics.update({
                'avg_cyclomatic_complexity': sum(complexities) / len(complexities),
                'max_cyclomatic_complexity': max(complexities),
                'total_functions': len(function_metrics)
            })

        # Check for specific Python complexity patterns
        python_suggestions = self._check_python_patterns(content, ast_tree)
        suggestions.extend(python_suggestions)

        return {
            'issues': issues,
            'suggestions': suggestions,
            'metrics': metrics
        }

    def _check_javascript_complexity(self, content: str, ast_tree: Dict[str, Any]) -> Dict[str, Any]:
        """Check JavaScript/TypeScript code complexity."""
        issues = []
        suggestions = []
        metrics = {}

        if not ast_tree:
            return {'issues': issues, 'suggestions': suggestions, 'metrics': metrics}

        functions = ast_tree.get('functions', [])

        for func_info in functions:
            func_name = func_info['name']
            line_start = func_info['line_start']

            # Extract function body for analysis
            func_body = self._extract_function_body(content, func_info)
            if not func_body:
                continue

            # Calculate JavaScript-specific complexity
            js_complexity = self._calculate_js_complexity(func_body)

            # Check thresholds and create issues
            if js_complexity['cyclomatic'] > self.max_cyclomatic_complexity:
                issues.append({
                    'type': 'high_cyclomatic_complexity',
                    'severity': 'warning',
                    'message': f"Function '{func_name}' has high cyclomatic complexity ({js_complexity['cyclomatic']})",
                    'line': line_start,
                    'suggestion': "Consider breaking this function into smaller functions"
                })

            if js_complexity['nesting_depth'] > self.max_nesting_depth:
                issues.append({
                    'type': 'deep_nesting',
                    'severity': 'warning',
                    'message': f"Function '{func_name}' has deep nesting (depth: {js_complexity['nesting_depth']})",
                    'line': line_start,
                    'suggestion': "Consider using early returns or extracting nested logic"
                })

            if js_complexity['line_count'] > self.max_function_length:
                issues.append({
                    'type': 'long_function',
                    'severity': 'info',
                    'message': f"Function '{func_name}' is very long ({js_complexity['line_count']} lines)",
                    'line': line_start,
                    'suggestion': "Consider breaking this function into smaller functions"
                })

        # Check for JavaScript-specific patterns
        js_suggestions = self._check_javascript_patterns(content)
        suggestions.extend(js_suggestions)

        return {
            'issues': issues,
            'suggestions': suggestions,
            'metrics': metrics
        }

    def _calculate_general_metrics(self, content: str) -> Dict[str, Any]:
        """Calculate general complexity metrics."""
        lines = content.split('\n')

        return {
            'total_lines': len(lines),
            'code_lines': len([line for line in lines if line.strip() and not line.strip().startswith(('#', '//', '/*'))]),
            'avg_line_length': sum(len(line) for line in lines) / len(lines) if lines else 0,
            'max_line_length': max(len(line) for line in lines) if lines else 0
        }

    def _check_python_patterns(self, content: str, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check for Python-specific complexity patterns."""
        suggestions = []

        # Check for nested list comprehensions
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ListComp):
                # Count nesting levels in comprehension
                nesting_level = self._count_comprehension_nesting(node)
                if nesting_level > 2:
                    suggestions.append({
                        'type': 'complex_comprehension',
                        'message': "List comprehension is too complex - consider using regular loops",
                        'line': node.lineno,
                        'suggestion': "Break complex comprehensions into regular for loops for better readability"
                    })

        # Check for chained comparisons that might be confusing
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Compare) and len(node.ops) > 2:
                suggestions.append({
                    'type': 'complex_comparison',
                    'message': "Complex chained comparison - consider simplifying",
                    'line': node.lineno,
                    'suggestion': "Break complex comparisons into multiple statements"
                })

        # Check for deeply nested lambda functions
        lambda_depth = self._find_nested_lambdas(ast_tree)
        if lambda_depth > 1:
            suggestions.append({
                'type': 'nested_lambda',
                'message': "Nested lambda functions detected - consider using regular functions",
                'line': 1,  # Would need more sophisticated line tracking
                'suggestion': "Replace nested lambdas with regular functions for better readability"
            })

        return suggestions

    def _check_javascript_patterns(self, content: str) -> List[Dict[str, Any]]:
        """Check for JavaScript-specific complexity patterns."""
        suggestions = []

        # Check for callback hell patterns
        callback_depth = self._detect_callback_depth(content)
        if callback_depth > 3:
            suggestions.append({
                'type': 'callback_hell',
                'message': f"Deep callback nesting detected (depth: {callback_depth})",
                'line': 1,
                'suggestion': "Consider using Promises or async/await to avoid callback hell"
            })

        # Check for long promise chains
        promise_chain_length = self._detect_long_promise_chains(content)
        if promise_chain_length > 5:
            suggestions.append({
                'type': 'long_promise_chain',
                'message': f"Long promise chain detected ({promise_chain_length} .then() calls)",
                'line': 1,
                'suggestion': "Consider using async/await for better readability"
            })

        # Check for complex ternary operators
        complex_ternaries = self._find_complex_ternaries(content)
        for ternary_info in complex_ternaries:
            suggestions.append({
                'type': 'complex_ternary',
                'message': "Complex nested ternary operator - consider using if/else",
                'line': ternary_info['line'],
                'suggestion': "Replace nested ternary with if/else statements for better readability"
            })

        return suggestions

    def _extract_function_body(self, content: str, func_info: Dict[str, Any]) -> str:
        """Extract function body from content."""
        lines = content.split('\n')
        start_line = func_info['line_start'] - 1  # Convert to 0-based index

        # Find the opening brace
        func_start = -1
        brace_count = 0
        for i in range(start_line, len(lines)):
            line = lines[i]
            if '{' in line:
                func_start = i
                brace_count += line.count('{')
                brace_count -= line.count('}')
                break

        if func_start == -1:
            return ""

        # Find the closing brace
        func_end = func_start
        for i in range(func_start + 1, len(lines)):
            line = lines[i]
            brace_count += line.count('{')
            brace_count -= line.count('}')
            if brace_count == 0:
                func_end = i
                break

        return '\n'.join(lines[func_start:func_end + 1])

    def _calculate_js_complexity(self, func_body: str) -> Dict[str, Any]:
        """Calculate complexity metrics for JavaScript function."""
        cyclomatic = 1  # Base complexity

        # Count decision points
        decision_patterns = [
            r'\bif\s*\(',
            r'\belse\s+if\s*\(',
            r'\bwhile\s*\(',
            r'\bfor\s*\(',
            r'\bswitch\s*\(',
            r'\bcase\s+',
            r'\bcatch\s*\(',
            r'\?\s*.*?\s*:',  # Ternary operator
            r'&&',
            r'\|\|'
        ]

        for pattern in decision_patterns:
            cyclomatic += len(re.findall(pattern, func_body, re.IGNORECASE))

        # Calculate nesting depth
        nesting_depth = self._calculate_js_nesting_depth(func_body)

        # Count lines
        line_count = len([line for line in func_body.split('\n') if line.strip()])

        return {
            'cyclomatic': cyclomatic,
            'nesting_depth': nesting_depth,
            'line_count': line_count
        }

    def _calculate_js_nesting_depth(self, code: str) -> int:
        """Calculate maximum nesting depth in JavaScript code."""
        depth = 0
        max_depth = 0

        # Track braces, but also control structures
        for char in code:
            if char == '{':
                depth += 1
                max_depth = max(max_depth, depth)
            elif char == '}':
                depth = max(0, depth - 1)

        return max_depth

    def _count_comprehension_nesting(self, node: ast.ListComp) -> int:
        """Count nesting levels in Python comprehensions."""
        level = 0
        for generator in node.generators:
            level += 1
            # Check for nested comprehensions in conditions
            for if_clause in generator.ifs:
                for child in ast.walk(if_clause):
                    if isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp)):
                        level += 1
        return level

    def _find_nested_lambdas(self, ast_tree: ast.AST) -> int:
        """Find maximum nesting depth of lambda functions."""
        max_depth = 0

        def check_lambda_depth(node, current_depth=0):
            nonlocal max_depth
            if isinstance(node, ast.Lambda):
                current_depth += 1
                max_depth = max(max_depth, current_depth)

            for child in ast.iter_child_nodes(node):
                check_lambda_depth(child, current_depth)

        check_lambda_depth(ast_tree)
        return max_depth

    def _detect_callback_depth(self, content: str) -> int:
        """Detect callback hell depth in JavaScript."""
        max_depth = 0
        current_depth = 0

        # Simple heuristic: count nested function patterns
        lines = content.split('\n')
        for line in lines:
            # Count opening of callback functions
            if re.search(r'function\s*\([^)]*\)\s*\{', line) or re.search(r'=>\s*\{', line):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            # Count closing braces (approximation)
            elif line.strip() == '}' or line.strip().endswith('};'):
                current_depth = max(0, current_depth - 1)

        return max_depth

    def _detect_long_promise_chains(self, content: str) -> int:
        """Detect long promise chains."""
        # Count consecutive .then() calls
        then_pattern = r'\.then\s*\('
        matches = list(re.finditer(then_pattern, content))

        if not matches:
            return 0

        max_chain = 0
        current_chain = 0
        last_end = 0

        for match in matches:
            # If this .then() is close to the previous one, it's likely part of the same chain
            if match.start() - last_end < 100:  # Arbitrary threshold
                current_chain += 1
            else:
                max_chain = max(max_chain, current_chain)
                current_chain = 1
            last_end = match.end()

        return max(max_chain, current_chain)

    def _find_complex_ternaries(self, content: str) -> List[Dict[str, Any]]:
        """Find complex ternary operators."""
        complex_ternaries = []

        # Find nested ternary operators
        ternary_pattern = r'\?[^:]*:[^?]*\?'
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            if re.search(ternary_pattern, line):
                complex_ternaries.append({
                    'line': i,
                    'content': line.strip()
                })

        return complex_ternaries


class PythonComplexityAnalyzer:
    """Analyzes complexity metrics for Python code."""

    def __init__(self, max_cyclomatic: int, max_cognitive: int, max_length: int,
                 max_nesting: int, max_params: int):
        self.max_cyclomatic = max_cyclomatic
        self.max_cognitive = max_cognitive
        self.max_length = max_length
        self.max_nesting = max_nesting
        self.max_params = max_params

    def analyze(self, content: str, ast_tree: ast.AST) -> Dict[str, Dict[str, Any]]:
        """Analyze all functions in the AST for complexity."""
        function_metrics = {}

        for node in ast.walk(ast_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                metrics = self._analyze_function(node, content)
                function_metrics[node.name] = metrics

        return function_metrics

    def _analyze_function(self, func_node: ast.FunctionDef, content: str) -> Dict[str, Any]:
        """Analyze a single function for complexity metrics."""
        lines = content.split('\n')

        return {
            'line_start': func_node.lineno,
            'line_end': getattr(func_node, 'end_lineno', func_node.lineno),
            'length': self._calculate_function_length(func_node, lines),
            'cyclomatic_complexity': self._calculate_cyclomatic_complexity(func_node),
            'cognitive_complexity': self._calculate_cognitive_complexity(func_node),
            'max_nesting_depth': self._calculate_nesting_depth(func_node),
            'parameter_count': len(func_node.args.args)
        }

    def _calculate_function_length(self, func_node: ast.FunctionDef, lines: List[str]) -> int:
        """Calculate the length of a function in lines of code."""
        start = func_node.lineno - 1  # Convert to 0-based index
        end = getattr(func_node, 'end_lineno', len(lines))

        # Count non-empty, non-comment lines
        code_lines = 0
        for i in range(start, min(end, len(lines))):
            line = lines[i].strip()
            if line and not line.startswith('#'):
                code_lines += 1

        return code_lines

    def _calculate_cyclomatic_complexity(self, func_node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity

        for node in ast.walk(func_node):
            # Decision points that increase complexity
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, ast.With):
                complexity += 1
            elif isinstance(node, ast.Assert):
                complexity += 1
            elif isinstance(node, (ast.BoolOp, ast.Compare)):
                # Count logical operators
                if isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
                elif isinstance(node, ast.Compare):
                    complexity += len(node.ops)

        return complexity

    def _calculate_cognitive_complexity(self, func_node: ast.FunctionDef) -> int:
        """Calculate cognitive complexity of a function."""
        complexity = 0
        nesting_level = 0

        def visit_node(node, level=0):
            nonlocal complexity, nesting_level

            # Increment for control flow structures
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1 + level
                level += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1 + level
                level += 1
            elif isinstance(node, (ast.BoolOp, ast.Compare)):
                complexity += 1

            # Recursively visit children
            for child in ast.iter_child_nodes(node):
                visit_node(child, level)

        visit_node(func_node)
        return complexity

    def _calculate_nesting_depth(self, func_node: ast.FunctionDef) -> int:
        """Calculate maximum nesting depth in a function."""
        max_depth = 0

        def visit_node(node, depth=0):
            nonlocal max_depth

            # Increase depth for nested structures
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.With, ast.Try)):
                depth += 1
                max_depth = max(max_depth, depth)

            # Visit children with updated depth
            for child in ast.iter_child_nodes(node):
                visit_node(child, depth)

        visit_node(func_node)
        return max_depth