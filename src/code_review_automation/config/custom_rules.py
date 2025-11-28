"""
Custom Rules Framework

Allows teams to define custom rules using Python code or declarative YAML/JSON.
"""

import ast
import re
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass
import inspect

from .rule_engine import RuleContext, RuleResult
from .schema import SeverityLevel, RuleConfig
from ..utils.logger import get_logger


@dataclass
class CustomRuleDefinition:
    """Definition of a custom rule."""
    name: str
    description: str
    category: str
    severity: SeverityLevel
    file_types: List[str]
    implementation: Union[str, Callable]  # Python code or function
    options: Dict[str, Any]
    examples: Dict[str, str]  # good/bad examples


class PatternRule:
    """Simple pattern-based custom rule."""

    def __init__(self, rule_def: CustomRuleDefinition):
        self.rule_def = rule_def
        self.logger = get_logger(__name__)

    def execute(self, context: RuleContext, options: Dict[str, Any]) -> List[RuleResult]:
        """Execute pattern-based rule."""
        results = []

        patterns = options.get('patterns', [])
        if isinstance(patterns, str):
            patterns = [patterns]

        for pattern_def in patterns:
            pattern = pattern_def.get('pattern') if isinstance(pattern_def, dict) else pattern_def
            flags = pattern_def.get('flags', 0) if isinstance(pattern_def, dict) else 0
            message = pattern_def.get('message', self.rule_def.description) if isinstance(pattern_def, dict) else self.rule_def.description

            try:
                matches = re.finditer(pattern, context.content, flags)
                for match in matches:
                    line_number = context.content[:match.start()].count('\n') + 1

                    results.append(RuleResult(
                        rule_name=self.rule_def.name,
                        checker_name=self.rule_def.category,
                        severity=self.rule_def.severity,
                        message=message,
                        file_path=context.file_path,
                        line_number=line_number,
                        column=match.start() - context.content.rfind('\n', 0, match.start()),
                        metadata={
                            'pattern': pattern,
                            'match': match.group(0)
                        }
                    ))

            except re.error as e:
                self.logger.error(f"Invalid regex pattern in custom rule {self.rule_def.name}: {e}")

        return results


class ASTRule:
    """AST-based custom rule for more complex analysis."""

    def __init__(self, rule_def: CustomRuleDefinition):
        self.rule_def = rule_def
        self.logger = get_logger(__name__)

    def execute(self, context: RuleContext, options: Dict[str, Any]) -> List[RuleResult]:
        """Execute AST-based rule."""
        if context.file_path.suffix not in ['.py']:  # Only Python for now
            return []

        try:
            tree = ast.parse(context.content, str(context.file_path))
            visitor = CustomASTVisitor(self.rule_def, context, options)
            visitor.visit(tree)
            return visitor.results

        except SyntaxError:
            return []  # Skip files with syntax errors
        except Exception as e:
            self.logger.error(f"Error in AST rule {self.rule_def.name}: {e}")
            return []


class CustomASTVisitor(ast.NodeVisitor):
    """AST visitor for custom rules."""

    def __init__(self, rule_def: CustomRuleDefinition, context: RuleContext, options: Dict[str, Any]):
        self.rule_def = rule_def
        self.context = context
        self.options = options
        self.results = []
        self.logger = get_logger(__name__)

    def visit(self, node):
        """Visit AST node and check custom conditions."""
        # Execute custom rule logic
        if callable(self.rule_def.implementation):
            try:
                custom_results = self.rule_def.implementation(node, self.context, self.options)
                if custom_results:
                    if not isinstance(custom_results, list):
                        custom_results = [custom_results]
                    self.results.extend(custom_results)
            except Exception as e:
                self.logger.error(f"Error in custom AST rule: {e}")

        self.generic_visit(node)

    def create_result(self, node: ast.AST, message: str, suggestion: str = None) -> RuleResult:
        """Create a rule result for an AST node."""
        return RuleResult(
            rule_name=self.rule_def.name,
            checker_name=self.rule_def.category,
            severity=self.rule_def.severity,
            message=message,
            file_path=self.context.file_path,
            line_number=getattr(node, 'lineno', None),
            column=getattr(node, 'col_offset', None),
            suggestion=suggestion,
            metadata={'node_type': type(node).__name__}
        )


class CustomRuleFactory:
    """Factory for creating custom rules."""

    @staticmethod
    def create_rule(rule_def: CustomRuleDefinition) -> Callable:
        """Create a rule executor from definition."""
        if isinstance(rule_def.implementation, str):
            # Code-based rule
            if rule_def.implementation.startswith('ast:'):
                return ASTRule(rule_def).execute
            else:
                return PatternRule(rule_def).execute
        elif callable(rule_def.implementation):
            # Function-based rule
            return rule_def.implementation
        else:
            raise ValueError(f"Invalid rule implementation for {rule_def.name}")


class CustomRuleLoader:
    """Loads custom rules from various sources."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def load_from_file(self, rule_file: Path) -> List[CustomRuleDefinition]:
        """Load custom rules from file."""
        if rule_file.suffix == '.py':
            return self._load_python_rules(rule_file)
        elif rule_file.suffix in ['.yaml', '.yml']:
            return self._load_yaml_rules(rule_file)
        elif rule_file.suffix == '.json':
            return self._load_json_rules(rule_file)
        else:
            self.logger.warning(f"Unsupported rule file format: {rule_file}")
            return []

    def _load_python_rules(self, rule_file: Path) -> List[CustomRuleDefinition]:
        """Load rules from Python file."""
        try:
            spec = importlib.util.spec_from_file_location("custom_rules", rule_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            rules = []
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and hasattr(obj, '_rule_metadata'):
                    metadata = obj._rule_metadata
                    rules.append(CustomRuleDefinition(
                        name=metadata.get('name', name),
                        description=metadata.get('description', ''),
                        category=metadata.get('category', 'custom'),
                        severity=SeverityLevel(metadata.get('severity', 'warning')),
                        file_types=metadata.get('file_types', ['*']),
                        implementation=obj,
                        options=metadata.get('options', {}),
                        examples=metadata.get('examples', {})
                    ))

            self.logger.info(f"Loaded {len(rules)} Python rules from {rule_file}")
            return rules

        except Exception as e:
            self.logger.error(f"Error loading Python rules from {rule_file}: {e}")
            return []

    def _load_yaml_rules(self, rule_file: Path) -> List[CustomRuleDefinition]:
        """Load rules from YAML file."""
        import yaml

        try:
            with open(rule_file, 'r') as f:
                data = yaml.safe_load(f)

            rules = []
            for rule_data in data.get('rules', []):
                rules.append(CustomRuleDefinition(
                    name=rule_data['name'],
                    description=rule_data.get('description', ''),
                    category=rule_data.get('category', 'custom'),
                    severity=SeverityLevel(rule_data.get('severity', 'warning')),
                    file_types=rule_data.get('file_types', ['*']),
                    implementation=rule_data.get('pattern', rule_data.get('implementation')),
                    options=rule_data.get('options', {}),
                    examples=rule_data.get('examples', {})
                ))

            self.logger.info(f"Loaded {len(rules)} YAML rules from {rule_file}")
            return rules

        except Exception as e:
            self.logger.error(f"Error loading YAML rules from {rule_file}: {e}")
            return []

    def _load_json_rules(self, rule_file: Path) -> List[CustomRuleDefinition]:
        """Load rules from JSON file."""
        import json

        try:
            with open(rule_file, 'r') as f:
                data = json.load(f)

            rules = []
            for rule_data in data.get('rules', []):
                rules.append(CustomRuleDefinition(
                    name=rule_data['name'],
                    description=rule_data.get('description', ''),
                    category=rule_data.get('category', 'custom'),
                    severity=SeverityLevel(rule_data.get('severity', 'warning')),
                    file_types=rule_data.get('file_types', ['*']),
                    implementation=rule_data.get('pattern', rule_data.get('implementation')),
                    options=rule_data.get('options', {}),
                    examples=rule_data.get('examples', {})
                ))

            self.logger.info(f"Loaded {len(rules)} JSON rules from {rule_file}")
            return rules

        except Exception as e:
            self.logger.error(f"Error loading JSON rules from {rule_file}: {e}")
            return []


class CustomRuleManager:
    """Manages custom rules and integrates them with the rule engine."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.loader = CustomRuleLoader()
        self.factory = CustomRuleFactory()
        self.custom_rules: Dict[str, Dict[str, CustomRuleDefinition]] = {}

    def load_custom_rules(self, rules_dir: Union[str, Path]) -> int:
        """Load all custom rules from directory."""
        rules_dir = Path(rules_dir)
        if not rules_dir.exists():
            self.logger.warning(f"Custom rules directory not found: {rules_dir}")
            return 0

        total_loaded = 0

        for rule_file in rules_dir.rglob("*"):
            if rule_file.is_file() and rule_file.suffix in ['.py', '.yaml', '.yml', '.json']:
                rules = self.loader.load_from_file(rule_file)
                for rule in rules:
                    self.register_custom_rule(rule)
                    total_loaded += 1

        self.logger.info(f"Loaded {total_loaded} custom rules from {rules_dir}")
        return total_loaded

    def register_custom_rule(self, rule_def: CustomRuleDefinition):
        """Register a custom rule."""
        if rule_def.category not in self.custom_rules:
            self.custom_rules[rule_def.category] = {}

        self.custom_rules[rule_def.category][rule_def.name] = rule_def
        self.logger.debug(f"Registered custom rule: {rule_def.category}.{rule_def.name}")

    def get_custom_rules_for_engine(self) -> Dict[str, Dict[str, Callable]]:
        """Get custom rules formatted for rule engine."""
        engine_rules = {}

        for category, rules in self.custom_rules.items():
            engine_rules[category] = {}
            for rule_name, rule_def in rules.items():
                try:
                    engine_rules[category][rule_name] = self.factory.create_rule(rule_def)
                except Exception as e:
                    self.logger.error(f"Error creating rule {category}.{rule_name}: {e}")

        return engine_rules

    def get_rule_definition(self, category: str, rule_name: str) -> Optional[CustomRuleDefinition]:
        """Get custom rule definition."""
        return self.custom_rules.get(category, {}).get(rule_name)

    def create_rule_template(self, output_path: Path, rule_type: str = "pattern"):
        """Create a template for custom rules."""
        if rule_type == "pattern":
            template = """# Custom Pattern Rules

rules:
  - name: "no_debug_prints"
    description: "Avoid debug print statements in production code"
    category: "style"
    severity: "warning"
    file_types: ["*.py"]
    pattern: "print\\s*\\(.*debug.*\\)"
    options:
      message: "Debug print statement found"
    examples:
      bad: 'print("debug:", value)'
      good: 'logger.debug("value: %s", value)'

  - name: "no_hardcoded_urls"
    description: "Avoid hardcoded URLs"
    category: "security"
    severity: "warning"
    file_types: ["*.py", "*.js"]
    pattern: "https?://[^\\s\"']+[^\\s\"'.]"
    options:
      message: "Hardcoded URL found, consider using configuration"
"""

        elif rule_type == "python":
            template = '''"""
Custom Python Rules

Define custom rules using Python functions with the @rule decorator.
"""

from typing import List, Dict, Any
from src.config.custom_rules import RuleResult, RuleContext


def rule(name: str, description: str = "", category: str = "custom",
         severity: str = "warning", file_types: List[str] = None,
         options: Dict[str, Any] = None, examples: Dict[str, str] = None):
    """Decorator to define custom rules."""
    def decorator(func):
        func._rule_metadata = {
            'name': name,
            'description': description,
            'category': category,
            'severity': severity,
            'file_types': file_types or ['*'],
            'options': options or {},
            'examples': examples or {}
        }
        return func
    return decorator


@rule(
    name="no_debug_prints",
    description="Avoid debug print statements in production code",
    category="style",
    severity="warning",
    file_types=["*.py"]
)
def no_debug_prints(context: RuleContext, options: Dict[str, Any]) -> List[RuleResult]:
    """Check for debug print statements."""
    results = []

    import re
    pattern = r'print\\s*\\(.*debug.*\\)'
    matches = re.finditer(pattern, context.content, re.IGNORECASE)

    for match in matches:
        line_number = context.content[:match.start()].count('\\n') + 1
        results.append(RuleResult(
            rule_name="no_debug_prints",
            checker_name="style",
            severity="warning",
            message="Debug print statement found",
            file_path=context.file_path,
            line_number=line_number,
            suggestion="Use proper logging instead of print statements"
        ))

    return results


@rule(
    name="function_complexity",
    description="Check function complexity",
    category="complexity",
    severity="warning",
    file_types=["*.py"]
)
def check_function_complexity(node, context: RuleContext, options: Dict[str, Any]) -> List[RuleResult]:
    """AST-based rule to check function complexity."""
    import ast

    if not isinstance(node, ast.FunctionDef):
        return []

    # Simple complexity calculation (number of nested structures)
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            complexity += 1

    max_complexity = options.get('max_complexity', 10)

    if complexity > max_complexity:
        return [RuleResult(
            rule_name="function_complexity",
            checker_name="complexity",
            severity="warning",
            message=f"Function {node.name} has complexity {complexity} (max: {max_complexity})",
            file_path=context.file_path,
            line_number=node.lineno,
            suggestion="Consider breaking down this function into smaller functions"
        )]

    return []
'''

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(template)
            self.logger.info(f"Created rule template: {output_path}")
        except Exception as e:
            self.logger.error(f"Error creating rule template: {e}")

    def validate_custom_rules(self) -> List[str]:
        """Validate all loaded custom rules."""
        errors = []

        for category, rules in self.custom_rules.items():
            for rule_name, rule_def in rules.items():
                # Validate rule definition
                if not rule_def.name:
                    errors.append(f"Rule {category}.{rule_name} missing name")

                if not rule_def.description:
                    errors.append(f"Rule {category}.{rule_name} missing description")

                # Validate implementation
                try:
                    self.factory.create_rule(rule_def)
                except Exception as e:
                    errors.append(f"Invalid implementation for {category}.{rule_name}: {e}")

        return errors