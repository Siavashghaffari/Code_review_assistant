"""
Security Checker

Analyzes code for security vulnerabilities including hardcoded secrets,
SQL injection risks, XSS vulnerabilities, and other security issues.
"""

import ast
import re
from typing import Dict, List, Any, Set, Tuple
import base64
import hashlib

from ...utils.logger import get_logger


class SecurityChecker:
    """Checker for security vulnerabilities."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

        # Patterns for detecting secrets
        self.secret_patterns = {
            'api_key': [
                r'["\']?(?:api[_-]?key|apikey)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{16,})["\']',
                r'["\']?(?:secret[_-]?key|secretkey)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{16,})["\']'
            ],
            'password': [
                r'["\']?password["\']?\s*[:=]\s*["\']([^"\']{8,})["\']',
                r'["\']?passwd["\']?\s*[:=]\s*["\']([^"\']{8,})["\']',
                r'["\']?pwd["\']?\s*[:=]\s*["\']([^"\']{8,})["\']'
            ],
            'aws_key': [
                r'AKIA[0-9A-Z]{16}',
                r'["\']?(?:aws[_-]?access[_-]?key[_-]?id)["\']?\s*[:=]\s*["\']([A-Z0-9]{20})["\']'
            ],
            'private_key': [
                r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----',
                r'-----BEGIN\s+(?:DSA\s+)?PRIVATE\s+KEY-----'
            ],
            'jwt_token': [
                r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*'
            ],
            'database_url': [
                r'["\']?(?:database[_-]?url|db[_-]?url)["\']?\s*[:=]\s*["\']([^"\']*://[^"\']+)["\']'
            ]
        }

        # SQL injection patterns
        self.sql_injection_patterns = [
            r'(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\s+.*\+.*["\']',
            r'(?:SELECT|INSERT|UPDATE|DELETE)\s+.*%.*["\']',
            r'(?:SELECT|INSERT|UPDATE|DELETE)\s+.*\{.*\}.*["\']',
            r'execute\s*\(\s*["\'][^"\']*\+',
            r'query\s*\(\s*["\'][^"\']*\+',
            r'sql\s*=\s*["\'][^"\']*\+',
        ]

        # XSS patterns
        self.xss_patterns = [
            r'innerHTML\s*=\s*[^"\']*\+',
            r'document\.write\s*\(\s*[^"\']*\+',
            r'\.html\s*\(\s*[^"\']*\+',
            r'eval\s*\(\s*[^"\']*\+',
        ]

        # Command injection patterns
        self.command_injection_patterns = [
            r'(?:exec|system|popen|subprocess\.call)\s*\([^)]*\+',
            r'os\.system\s*\([^)]*\+',
            r'os\.popen\s*\([^)]*\+',
        ]

    def check(self, content: str, ast_tree: Any, language: str) -> Dict[str, Any]:
        """
        Check for security vulnerabilities.

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
            # Check for hardcoded secrets
            secret_issues = self._check_hardcoded_secrets(content)
            issues.extend(secret_issues)

            # Check for SQL injection vulnerabilities
            sql_issues = self._check_sql_injection(content, ast_tree, language)
            issues.extend(sql_issues)

            # Check for XSS vulnerabilities
            xss_issues = self._check_xss_vulnerabilities(content, language)
            issues.extend(xss_issues)

            # Check for command injection
            cmd_issues = self._check_command_injection(content, ast_tree, language)
            issues.extend(cmd_issues)

            # Check for insecure random usage
            random_issues = self._check_insecure_random(content, ast_tree, language)
            issues.extend(random_issues)

            # Check for path traversal vulnerabilities
            path_issues = self._check_path_traversal(content, ast_tree, language)
            issues.extend(path_issues)

            # Check for insecure crypto usage
            crypto_issues = self._check_insecure_crypto(content, ast_tree, language)
            issues.extend(crypto_issues)

            # General security suggestions
            security_suggestions = self._get_security_suggestions(content, language)
            suggestions.extend(security_suggestions)

        except Exception as e:
            self.logger.warning(f"Security analysis failed: {e}")

        return {
            'issues': issues,
            'suggestions': suggestions
        }

    def _check_hardcoded_secrets(self, content: str) -> List[Dict[str, Any]]:
        """Check for hardcoded secrets and credentials."""
        issues = []
        lines = content.split('\n')

        for secret_type, patterns in self.secret_patterns.items():
            for pattern in patterns:
                for i, line in enumerate(lines, 1):
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    for match in matches:
                        # Skip obvious test/example values
                        if self._is_test_value(match.group(0)):
                            continue

                        issues.append({
                            'type': 'hardcoded_secret',
                            'severity': 'error',
                            'message': f"Hardcoded {secret_type.replace('_', ' ')} detected",
                            'line': i,
                            'secret_type': secret_type,
                            'suggestion': f"Move {secret_type.replace('_', ' ')} to environment variables or secure config"
                        })

        return issues

    def _is_test_value(self, value: str) -> bool:
        """Check if a value appears to be a test/example value."""
        test_indicators = [
            'test', 'example', 'dummy', 'fake', 'sample', 'placeholder',
            'your_key_here', 'replace_me', '123456', 'password123',
            'abcd', 'xxxx', '****'
        ]

        value_lower = value.lower()
        return any(indicator in value_lower for indicator in test_indicators)

    def _check_sql_injection(self, content: str, ast_tree: Any, language: str) -> List[Dict[str, Any]]:
        """Check for SQL injection vulnerabilities."""
        issues = []
        lines = content.split('\n')

        # Check for dangerous SQL string concatenation
        for pattern in self.sql_injection_patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        'type': 'sql_injection',
                        'severity': 'error',
                        'message': "Potential SQL injection vulnerability detected",
                        'line': i,
                        'suggestion': "Use parameterized queries or prepared statements instead of string concatenation"
                    })

        # Language-specific checks
        if language == 'python' and ast_tree:
            python_sql_issues = self._check_python_sql_injection(ast_tree)
            issues.extend(python_sql_issues)

        elif language in ['javascript', 'typescript']:
            js_sql_issues = self._check_javascript_sql_injection(content)
            issues.extend(js_sql_issues)

        return issues

    def _check_python_sql_injection(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check for Python-specific SQL injection patterns."""
        issues = []

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Call):
                # Check for string formatting in SQL queries
                if (isinstance(node.func, ast.Attribute) and
                    node.func.attr in ['execute', 'executemany', 'query']):

                    # Check arguments for string concatenation or formatting
                    for arg in node.args:
                        if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
                            issues.append({
                                'type': 'sql_injection',
                                'severity': 'error',
                                'message': "SQL query uses string concatenation",
                                'line': node.lineno,
                                'suggestion': "Use parameterized queries with placeholders"
                            })

                        elif isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
                            if arg.func.attr == 'format':
                                issues.append({
                                    'type': 'sql_injection',
                                    'severity': 'error',
                                    'message': "SQL query uses string formatting",
                                    'line': node.lineno,
                                    'suggestion': "Use parameterized queries instead of .format()"
                                })

        return issues

    def _check_javascript_sql_injection(self, content: str) -> List[Dict[str, Any]]:
        """Check for JavaScript-specific SQL injection patterns."""
        issues = []
        lines = content.split('\n')

        # Check for template literal SQL queries with variables
        template_sql_pattern = r'`(?:SELECT|INSERT|UPDATE|DELETE)[^`]*\$\{[^}]+\}[^`]*`'

        for i, line in enumerate(lines, 1):
            if re.search(template_sql_pattern, line, re.IGNORECASE):
                issues.append({
                    'type': 'sql_injection',
                    'severity': 'error',
                    'message': "SQL query uses template literals with variables",
                    'line': i,
                    'suggestion': "Use parameterized queries instead of template literals for SQL"
                })

        return issues

    def _check_xss_vulnerabilities(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Check for XSS vulnerabilities."""
        issues = []
        lines = content.split('\n')

        for pattern in self.xss_patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        'type': 'xss_vulnerability',
                        'severity': 'error',
                        'message': "Potential XSS vulnerability detected",
                        'line': i,
                        'suggestion': "Sanitize user input before inserting into DOM"
                    })

        # Check for unsafe eval usage
        if 'eval(' in content:
            for i, line in enumerate(lines, 1):
                if 'eval(' in line:
                    issues.append({
                        'type': 'unsafe_eval',
                        'severity': 'error',
                        'message': "Use of eval() is dangerous and can lead to code injection",
                        'line': i,
                        'suggestion': "Avoid using eval() - consider safer alternatives like JSON.parse()"
                    })

        return issues

    def _check_command_injection(self, content: str, ast_tree: Any, language: str) -> List[Dict[str, Any]]:
        """Check for command injection vulnerabilities."""
        issues = []
        lines = content.split('\n')

        for pattern in self.command_injection_patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        'type': 'command_injection',
                        'severity': 'error',
                        'message': "Potential command injection vulnerability detected",
                        'line': i,
                        'suggestion': "Validate and sanitize input before using in shell commands"
                    })

        # Language-specific checks
        if language == 'python' and ast_tree:
            python_cmd_issues = self._check_python_command_injection(ast_tree)
            issues.extend(python_cmd_issues)

        return issues

    def _check_python_command_injection(self, ast_tree: ast.AST) -> List[Dict[str, Any]]:
        """Check for Python command injection patterns."""
        issues = []

        dangerous_functions = {
            'os.system', 'os.popen', 'subprocess.call', 'subprocess.run',
            'subprocess.Popen', 'exec', 'eval'
        }

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Call):
                func_name = None

                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        func_name = f"{node.func.value.id}.{node.func.attr}"

                if func_name in dangerous_functions:
                    # Check if arguments involve user input or string concatenation
                    for arg in node.args:
                        if isinstance(arg, ast.BinOp) or isinstance(arg, ast.JoinedStr):
                            issues.append({
                                'type': 'command_injection',
                                'severity': 'error',
                                'message': f"Dangerous use of {func_name} with dynamic input",
                                'line': node.lineno,
                                'suggestion': "Use subprocess with shell=False and list arguments"
                            })

        return issues

    def _check_insecure_random(self, content: str, ast_tree: Any, language: str) -> List[Dict[str, Any]]:
        """Check for insecure random number generation."""
        issues = []

        if language == 'python':
            # Check for use of random module for cryptographic purposes
            if 'import random' in content and any(crypto_term in content for crypto_term in ['password', 'key', 'token', 'secret']):
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'random.' in line:
                        issues.append({
                            'type': 'insecure_random',
                            'severity': 'warning',
                            'message': "Using random module for cryptographic purposes is insecure",
                            'line': i,
                            'suggestion': "Use secrets module for cryptographically secure random values"
                        })

        elif language in ['javascript', 'typescript']:
            # Check for Math.random() in crypto contexts
            if 'Math.random()' in content and any(crypto_term in content for crypto_term in ['password', 'key', 'token', 'secret']):
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'Math.random()' in line:
                        issues.append({
                            'type': 'insecure_random',
                            'severity': 'warning',
                            'message': "Math.random() is not cryptographically secure",
                            'line': i,
                            'suggestion': "Use crypto.getRandomValues() for cryptographic random values"
                        })

        return issues

    def _check_path_traversal(self, content: str, ast_tree: Any, language: str) -> List[Dict[str, Any]]:
        """Check for path traversal vulnerabilities."""
        issues = []
        lines = content.split('\n')

        # Look for file operations with user input
        path_traversal_patterns = [
            r'open\s*\([^)]*\+[^)]*\)',
            r'readFile\s*\([^)]*\+[^)]*\)',
            r'writeFile\s*\([^)]*\+[^)]*\)',
            r'path\.join\s*\([^)]*\+[^)]*\)',
        ]

        for pattern in path_traversal_patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    issues.append({
                        'type': 'path_traversal',
                        'severity': 'warning',
                        'message': "Potential path traversal vulnerability",
                        'line': i,
                        'suggestion': "Validate and sanitize file paths to prevent directory traversal"
                    })

        return issues

    def _check_insecure_crypto(self, content: str, ast_tree: Any, language: str) -> List[Dict[str, Any]]:
        """Check for insecure cryptographic practices."""
        issues = []
        lines = content.split('\n')

        # Check for weak hashing algorithms
        weak_hash_patterns = [
            r'md5\s*\(',
            r'sha1\s*\(',
            r'\.md5\s*\(',
            r'\.sha1\s*\(',
            r'hashlib\.md5',
            r'hashlib\.sha1',
        ]

        for pattern in weak_hash_patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        'type': 'weak_crypto',
                        'severity': 'warning',
                        'message': "Weak cryptographic hash algorithm detected",
                        'line': i,
                        'suggestion': "Use SHA-256 or stronger hash algorithms"
                    })

        # Check for hardcoded initialization vectors
        if re.search(r'iv\s*=\s*["\'][0-9a-f]{16,}["\']', content, re.IGNORECASE):
            for i, line in enumerate(lines, 1):
                if re.search(r'iv\s*=\s*["\'][0-9a-f]{16,}["\']', line, re.IGNORECASE):
                    issues.append({
                        'type': 'hardcoded_iv',
                        'severity': 'error',
                        'message': "Hardcoded initialization vector detected",
                        'line': i,
                        'suggestion': "Use randomly generated initialization vectors"
                    })

        return issues

    def _get_security_suggestions(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Get general security suggestions."""
        suggestions = []

        # Check for missing input validation
        if any(term in content for term in ['request', 'input', 'argv', 'form']) and 'validate' not in content:
            suggestions.append({
                'type': 'input_validation',
                'message': "Consider adding input validation for user data",
                'line': 1,
                'suggestion': "Implement proper input validation and sanitization"
            })

        # Check for HTTP instead of HTTPS
        if re.search(r'http://(?!localhost|127\.0\.0\.1)', content):
            suggestions.append({
                'type': 'insecure_protocol',
                'message': "HTTP URLs detected - consider using HTTPS",
                'line': 1,
                'suggestion': "Use HTTPS for secure communication"
            })

        # Check for missing CSRF protection
        if language in ['javascript', 'typescript'] and 'form' in content.lower() and 'csrf' not in content.lower():
            suggestions.append({
                'type': 'csrf_protection',
                'message': "Consider adding CSRF protection for forms",
                'line': 1,
                'suggestion': "Implement CSRF tokens for form submissions"
            })

        return suggestions