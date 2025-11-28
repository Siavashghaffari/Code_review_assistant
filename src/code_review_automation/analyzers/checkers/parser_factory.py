"""
Parser Factory

Creates appropriate parsers for different programming languages.
"""

import ast
import re
from typing import Dict, Any, Optional, Union, List
from abc import ABC, abstractmethod

from ...utils.logger import get_logger


class BaseParser(ABC):
    """Abstract base class for language parsers."""

    @abstractmethod
    def parse(self, content: str) -> Any:
        """Parse content and return AST or equivalent structure."""
        pass

    @abstractmethod
    def extract_functions(self, ast_tree: Any) -> List[Dict[str, Any]]:
        """Extract function definitions from AST."""
        pass

    @abstractmethod
    def extract_variables(self, ast_tree: Any) -> List[Dict[str, Any]]:
        """Extract variable definitions from AST."""
        pass


class PythonParser(BaseParser):
    """Parser for Python code using built-in ast module."""

    def parse(self, content: str) -> ast.AST:
        """Parse Python code into AST."""
        try:
            return ast.parse(content)
        except SyntaxError as e:
            raise SyntaxError(f"Python syntax error: {e}")

    def extract_functions(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract function definitions from Python AST."""
        functions = []

        for node in ast.walk(ast_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({
                    'name': node.name,
                    'line_start': node.lineno,
                    'line_end': getattr(node, 'end_lineno', node.lineno),
                    'args': [arg.arg for arg in node.args.args],
                    'is_async': isinstance(node, ast.AsyncFunctionDef),
                    'decorators': [self._get_decorator_name(dec) for dec in node.decorator_list],
                    'docstring': ast.get_docstring(node),
                    'returns': bool(node.returns)
                })

        return functions

    def extract_variables(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract variable assignments from Python AST."""
        variables = []

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        variables.append({
                            'name': target.id,
                            'line': node.lineno,
                            'type': 'assignment',
                            'scope': self._determine_scope(node, ast_tree)
                        })

        return variables

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{decorator.attr}"
        else:
            return str(decorator)

    def _determine_scope(self, node: ast.AST, tree: ast.AST) -> str:
        """Determine the scope of a variable assignment."""
        # Simple heuristic - could be more sophisticated
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                if child == node:
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        return f"function:{parent.name}"
                    elif isinstance(parent, ast.ClassDef):
                        return f"class:{parent.name}"
        return "module"


class JavaScriptParser(BaseParser):
    """Parser for JavaScript/TypeScript code using regex-based parsing."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def parse(self, content: str) -> Dict[str, Any]:
        """Parse JavaScript content using regex patterns."""
        return {
            'content': content,
            'functions': self._extract_functions_regex(content),
            'variables': self._extract_variables_regex(content),
            'classes': self._extract_classes_regex(content),
            'imports': self._extract_imports_regex(content)
        }

    def extract_functions(self, ast_tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract function definitions from parsed structure."""
        return ast_tree.get('functions', [])

    def extract_variables(self, ast_tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract variable definitions from parsed structure."""
        return ast_tree.get('variables', [])

    def _extract_functions_regex(self, content: str) -> List[Dict[str, Any]]:
        """Extract JavaScript functions using regex."""
        functions = []

        # Function declarations: function name() {}
        func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            line_no = content[:match.start()].count('\n') + 1
            functions.append({
                'name': match.group(1),
                'line_start': line_no,
                'type': 'function_declaration',
                'is_async': 'async' in match.group(0),
                'is_export': 'export' in match.group(0)
            })

        # Arrow functions: const name = () => {}
        arrow_pattern = r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>'
        for match in re.finditer(arrow_pattern, content, re.MULTILINE):
            line_no = content[:match.start()].count('\n') + 1
            functions.append({
                'name': match.group(1),
                'line_start': line_no,
                'type': 'arrow_function',
                'is_async': 'async' in match.group(0)
            })

        # Method definitions in classes/objects: methodName() {}
        method_pattern = r'(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(method_pattern, content, re.MULTILINE):
            line_no = content[:match.start()].count('\n') + 1
            # Skip if it looks like a function declaration (already captured)
            if not re.search(r'function\s+' + match.group(1), content[:match.start()]):
                functions.append({
                    'name': match.group(1),
                    'line_start': line_no,
                    'type': 'method'
                })

        return functions

    def _extract_variables_regex(self, content: str) -> List[Dict[str, Any]]:
        """Extract JavaScript variable declarations using regex."""
        variables = []

        # Variable declarations: const/let/var name = value
        var_pattern = r'(const|let|var)\s+(\w+)(?:\s*=\s*[^;]+)?;?'
        for match in re.finditer(var_pattern, content, re.MULTILINE):
            line_no = content[:match.start()].count('\n') + 1
            variables.append({
                'name': match.group(2),
                'line': line_no,
                'type': match.group(1),
                'scope': self._determine_js_scope(match.start(), content)
            })

        return variables

    def _extract_classes_regex(self, content: str) -> List[Dict[str, Any]]:
        """Extract JavaScript class definitions using regex."""
        classes = []

        class_pattern = r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            line_no = content[:match.start()].count('\n') + 1
            classes.append({
                'name': match.group(1),
                'line_start': line_no,
                'is_export': 'export' in match.group(0)
            })

        return classes

    def _extract_imports_regex(self, content: str) -> List[Dict[str, Any]]:
        """Extract import statements using regex."""
        imports = []

        # ES6 imports: import { ... } from '...'
        import_pattern = r'import\s+(?:\{([^}]+)\}|\*\s+as\s+(\w+)|(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            line_no = content[:match.start()].count('\n') + 1
            imports.append({
                'line': line_no,
                'module': match.group(4),
                'type': 'es6_import'
            })

        # CommonJS requires: const name = require('...')
        require_pattern = r'(?:const|let|var)\s+(\w+)\s*=\s*require\([\'"]([^\'"]+)[\'"]\)'
        for match in re.finditer(require_pattern, content, re.MULTILINE):
            line_no = content[:match.start()].count('\n') + 1
            imports.append({
                'line': line_no,
                'name': match.group(1),
                'module': match.group(2),
                'type': 'commonjs_require'
            })

        return imports

    def _determine_js_scope(self, position: int, content: str) -> str:
        """Determine the scope of a variable in JavaScript."""
        # Simple scope detection by looking for nearest function/class
        before_position = content[:position]

        # Look for function scopes
        func_matches = list(re.finditer(r'function\s+(\w+)|(\w+)\s*\(', before_position))
        class_matches = list(re.finditer(r'class\s+(\w+)', before_position))

        if func_matches or class_matches:
            return "local"
        return "module"


class TypeScriptParser(JavaScriptParser):
    """Parser for TypeScript code, extends JavaScript parser."""

    def _extract_functions_regex(self, content: str) -> List[Dict[str, Any]]:
        """Extract TypeScript functions with type annotations."""
        functions = super()._extract_functions_regex(content)

        # TypeScript-specific function patterns with return types
        ts_func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*:\s*\w+\s*\{'
        for match in re.finditer(ts_func_pattern, content, re.MULTILINE):
            line_no = content[:match.start()].count('\n') + 1
            functions.append({
                'name': match.group(1),
                'line_start': line_no,
                'type': 'typescript_function',
                'has_return_type': True,
                'is_async': 'async' in match.group(0),
                'is_export': 'export' in match.group(0)
            })

        return functions


class ParserFactory:
    """Factory class for creating language-specific parsers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

        self._parsers = {
            'python': PythonParser(),
            'javascript': JavaScriptParser(),
            'typescript': TypeScriptParser(),
        }

    def get_parser(self, language: str) -> Optional[BaseParser]:
        """
        Get parser for the specified language.

        Args:
            language: Programming language name

        Returns:
            Parser instance or None if not supported
        """
        parser = self._parsers.get(language.lower())
        if not parser:
            self.logger.debug(f"No parser available for language: {language}")
        return parser

    def is_supported(self, language: str) -> bool:
        """Check if language is supported by available parsers."""
        return language.lower() in self._parsers

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return list(self._parsers.keys())