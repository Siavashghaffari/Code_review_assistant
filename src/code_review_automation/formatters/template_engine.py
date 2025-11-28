"""
Template Engine for Customizable Output Formats

Provides template-based output generation with support for multiple template engines,
custom filters, and dynamic content generation.
"""

import re
import json
from typing import Dict, List, Any, Optional, Union, Callable
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict

from .base import BaseFormatter, FormatterConfig, OutputContext
from ..config.rule_engine import RuleResult
from ..utils.logger import get_logger


@dataclass
class TemplateContext:
    """Context data for template rendering."""
    results: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Callable] = field(default_factory=dict)


class SimpleTemplateEngine:
    """Simple template engine with basic substitution and control structures."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.filters = self._get_default_filters()

    def render(self, template: str, context: TemplateContext) -> str:
        """Render template with context data."""
        try:
            # Prepare context data
            template_vars = {
                "results": context.results,
                "summary": context.summary,
                "context": context.context,
                "config": context.config,
                "metadata": context.metadata,
                "now": datetime.now(),
                **context.filters
            }

            # Process template directives
            rendered = self._process_template(template, template_vars)

            return rendered

        except Exception as e:
            self.logger.error(f"Template rendering error: {e}")
            return f"Template Error: {e}"

    def _process_template(self, template: str, vars: Dict[str, Any]) -> str:
        """Process template with variables and control structures."""
        # Replace simple variables {{ var }}
        template = self._replace_variables(template, vars)

        # Process loops {% for item in items %}
        template = self._process_loops(template, vars)

        # Process conditionals {% if condition %}
        template = self._process_conditionals(template, vars)

        # Process filters {{ var | filter }}
        template = self._process_filters(template, vars)

        return template

    def _replace_variables(self, template: str, vars: Dict[str, Any]) -> str:
        """Replace simple variable expressions."""
        def replace_var(match):
            var_expr = match.group(1).strip()
            try:
                value = self._evaluate_expression(var_expr, vars)
                return str(value) if value is not None else ""
            except Exception:
                return f"{{{{ {var_expr} }}}}"  # Keep original if error

        return re.sub(r'\{\{\s*([^}]+)\s*\}\}', replace_var, template)

    def _process_loops(self, template: str, vars: Dict[str, Any]) -> str:
        """Process for loops."""
        pattern = r'\{% for\s+(\w+)\s+in\s+([^%]+)\s*%\}(.*?)\{% endfor %\}'

        def process_loop(match):
            item_name = match.group(1).strip()
            collection_expr = match.group(2).strip()
            loop_body = match.group(3)

            try:
                collection = self._evaluate_expression(collection_expr, vars)
                if not collection:
                    return ""

                result_parts = []
                for item in collection:
                    loop_vars = vars.copy()
                    loop_vars[item_name] = item
                    loop_vars['loop'] = {
                        'index': len(result_parts) + 1,
                        'index0': len(result_parts),
                        'first': len(result_parts) == 0,
                        'last': len(result_parts) == len(collection) - 1
                    }

                    rendered_body = self._process_template(loop_body, loop_vars)
                    result_parts.append(rendered_body)

                return ''.join(result_parts)

            except Exception as e:
                return f"<!-- Loop Error: {e} -->"

        return re.sub(pattern, process_loop, template, flags=re.DOTALL)

    def _process_conditionals(self, template: str, vars: Dict[str, Any]) -> str:
        """Process if/else conditionals."""
        # Process if-else blocks
        pattern = r'\{% if\s+([^%]+)\s*%\}(.*?)(?:\{% else %\}(.*?))?\{% endif %\}'

        def process_conditional(match):
            condition_expr = match.group(1).strip()
            if_body = match.group(2)
            else_body = match.group(3) or ""

            try:
                condition_result = self._evaluate_condition(condition_expr, vars)
                if condition_result:
                    return self._process_template(if_body, vars)
                else:
                    return self._process_template(else_body, vars)

            except Exception as e:
                return f"<!-- Conditional Error: {e} -->"

        return re.sub(pattern, process_conditional, template, flags=re.DOTALL)

    def _process_filters(self, template: str, vars: Dict[str, Any]) -> str:
        """Process filters like {{ var | filter }}."""
        pattern = r'\{\{\s*([^|{}]+)\s*\|\s*([^}]+)\s*\}\}'

        def apply_filter(match):
            var_expr = match.group(1).strip()
            filter_expr = match.group(2).strip()

            try:
                value = self._evaluate_expression(var_expr, vars)
                filtered_value = self._apply_filter_chain(value, filter_expr, vars)
                return str(filtered_value) if filtered_value is not None else ""

            except Exception as e:
                return f"{{{{ {var_expr} | {filter_expr} }}}}"

        return re.sub(pattern, apply_filter, template)

    def _evaluate_expression(self, expr: str, vars: Dict[str, Any]) -> Any:
        """Safely evaluate simple expressions."""
        # Handle dot notation like "summary.total_issues"
        parts = expr.split('.')
        value = vars

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None

        return value

    def _evaluate_condition(self, condition: str, vars: Dict[str, Any]) -> bool:
        """Evaluate conditional expressions."""
        # Simple conditions like "results", "not results", "summary.total_issues > 0"
        condition = condition.strip()

        # Handle "not" prefix
        if condition.startswith('not '):
            return not self._evaluate_condition(condition[4:], vars)

        # Handle comparisons
        operators = ['>=', '<=', '==', '!=', '>', '<']
        for op in operators:
            if op in condition:
                left, right = condition.split(op, 1)
                left_val = self._evaluate_expression(left.strip(), vars)
                right_val = self._parse_value(right.strip())

                if op == '==':
                    return left_val == right_val
                elif op == '!=':
                    return left_val != right_val
                elif op == '>':
                    return (left_val or 0) > right_val
                elif op == '<':
                    return (left_val or 0) < right_val
                elif op == '>=':
                    return (left_val or 0) >= right_val
                elif op == '<=':
                    return (left_val or 0) <= right_val

        # Simple truthiness check
        value = self._evaluate_expression(condition, vars)
        return bool(value)

    def _parse_value(self, value_str: str) -> Any:
        """Parse string value to appropriate type."""
        value_str = value_str.strip().strip('"\'')

        # Try to parse as number
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass

        # Return as string
        return value_str

    def _apply_filter_chain(self, value: Any, filter_chain: str, vars: Dict[str, Any]) -> Any:
        """Apply a chain of filters."""
        filters = filter_chain.split('|')
        result = value

        for filter_name in filters:
            filter_name = filter_name.strip()
            if filter_name in self.filters:
                result = self.filters[filter_name](result)
            else:
                # Try built-in filters
                result = self._apply_builtin_filter(result, filter_name)

        return result

    def _apply_builtin_filter(self, value: Any, filter_name: str) -> Any:
        """Apply built-in filters."""
        if filter_name == 'upper':
            return str(value).upper() if value else ""
        elif filter_name == 'lower':
            return str(value).lower() if value else ""
        elif filter_name == 'title':
            return str(value).title() if value else ""
        elif filter_name == 'length' or filter_name == 'count':
            return len(value) if value else 0
        elif filter_name == 'first':
            return value[0] if value and len(value) > 0 else None
        elif filter_name == 'last':
            return value[-1] if value and len(value) > 0 else None
        elif filter_name == 'join':
            return ', '.join(str(item) for item in value) if value else ""
        elif filter_name == 'json':
            return json.dumps(value, indent=2) if value else "{}"
        elif filter_name == 'date':
            if isinstance(value, datetime):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            return str(value)
        else:
            return value

    def _get_default_filters(self) -> Dict[str, Callable]:
        """Get default filter functions."""
        return {
            'pluralize': lambda value, suffix='s': suffix if value != 1 else '',
            'truncate': lambda value, length=50: str(value)[:length] + '...' if len(str(value)) > length else str(value),
            'default': lambda value, default='': default if not value else value,
            'yesno': lambda value: 'Yes' if value else 'No'
        }


class TemplateLibrary:
    """Library of predefined templates."""

    def __init__(self):
        self.templates = self._load_builtin_templates()

    def get_template(self, name: str) -> Optional[str]:
        """Get template by name."""
        return self.templates.get(name)

    def add_template(self, name: str, template: str):
        """Add custom template."""
        self.templates[name] = template

    def list_templates(self) -> List[str]:
        """List available templates."""
        return list(self.templates.keys())

    def _load_builtin_templates(self) -> Dict[str, str]:
        """Load built-in templates."""
        return {
            'summary_only': self._get_summary_template(),
            'detailed_report': self._get_detailed_template(),
            'ci_brief': self._get_ci_template(),
            'email_report': self._get_email_template(),
            'slack_notification': self._get_slack_template()
        }

    def _get_summary_template(self) -> str:
        return """
# Code Review Summary

**Analysis Results:** {{ summary.total_issues }} issues found
**Files Analyzed:** {{ summary.files_analyzed }}
**Clean Files:** {{ summary.clean_files }}

{% if summary.severity_breakdown %}
## Issues by Severity
{% for severity, count in summary.severity_breakdown %}
{% if count > 0 %}
- **{{ severity | title }}:** {{ count }}
{% endif %}
{% endfor %}
{% endif %}

{% if summary.total_issues == 0 %}
🎉 **Excellent!** No issues found in your code.
{% else %}
📋 **{{ summary.total_issues }}** issues require attention.
{% endif %}
        """.strip()

    def _get_detailed_template(self) -> str:
        return """
# Code Review Report

Generated: {{ now | date }}
Repository: {{ context.repository_url }}

## Executive Summary

{% if summary.total_issues == 0 %}
✅ **All Clear!** No issues were found during analysis.
{% else %}
📋 Found **{{ summary.total_issues }}** issues across **{{ summary.files_with_issues }}** files.
{% endif %}

### Quick Stats
- Files Analyzed: {{ summary.files_analyzed }}
- Clean Files: {{ summary.clean_files }}
- Issues Found: {{ summary.total_issues }}
{% if summary.execution_time %}
- Analysis Time: {{ summary.execution_time }}s
{% endif %}

{% if results %}
## Issues by File

{% for result in results %}
{% if loop.first or result.file_path != results[loop.index0 - 1].file_path %}

### 📄 {{ result.file_path }}
{% endif %}

**{{ result.severity | upper }}:** {{ result.message }}
{% if result.line_number %}*Line {{ result.line_number }}*{% endif %}
*Rule:* `{{ result.checker_name }}.{{ result.rule_name }}`

{% if result.suggestion %}
💡 **Suggestion:** {{ result.suggestion }}
{% endif %}

{% endfor %}
{% endif %}

---
*Generated by Code Review Assistant {{ context.analyzer_version }}*
        """.strip()

    def _get_ci_template(self) -> str:
        return """
{% if summary.total_issues == 0 %}
✅ Code Review: All Clear
{% else %}
❌ Code Review: {{ summary.total_issues }} Issues Found

Top Issues:
{% for result in results | first:5 %}
- {{ result.severity | upper }}: {{ result.message }} ({{ result.file_path }})
{% endfor %}
{% if summary.total_issues > 5 %}
... and {{ summary.total_issues - 5 }} more
{% endif %}
{% endif %}
        """.strip()

    def _get_email_template(self) -> str:
        return """
<html>
<body style="font-family: Arial, sans-serif;">
<h2>Code Review Results</h2>

<p><strong>Analysis completed:</strong> {{ now | date }}</p>
{% if context.repository_url %}
<p><strong>Repository:</strong> {{ context.repository_url }}</p>
{% endif %}

<h3>Summary</h3>
<ul>
<li><strong>Total Issues:</strong> {{ summary.total_issues }}</li>
<li><strong>Files Analyzed:</strong> {{ summary.files_analyzed }}</li>
<li><strong>Clean Files:</strong> {{ summary.clean_files }}</li>
</ul>

{% if summary.severity_breakdown %}
<h4>By Severity:</h4>
<ul>
{% for severity, count in summary.severity_breakdown %}
{% if count > 0 %}
<li><strong>{{ severity | title }}:</strong> {{ count }}</li>
{% endif %}
{% endfor %}
</ul>
{% endif %}

{% if results %}
<h3>Issues</h3>
{% for result in results | first:10 %}
<div style="border-left: 3px solid #ccc; padding: 10px; margin: 10px 0;">
<strong>{{ result.severity | upper }}:</strong> {{ result.message }}<br>
<em>File: {{ result.file_path }}{% if result.line_number %} (Line {{ result.line_number }}){% endif %}</em><br>
<small>Rule: {{ result.checker_name }}.{{ result.rule_name }}</small>
{% if result.suggestion %}
<br><strong>Suggestion:</strong> {{ result.suggestion }}
{% endif %}
</div>
{% endfor %}
{% endif %}

<hr>
<p><small>Generated by Code Review Assistant</small></p>
</body>
</html>
        """.strip()

    def _get_slack_template(self) -> str:
        return """
{% if summary.total_issues == 0 %}
:white_check_mark: *Code Review: All Clear*
:tada: No issues found in {{ summary.files_analyzed }} files!
{% else %}
:warning: *Code Review: {{ summary.total_issues }} Issues Found*

*Summary:*
• Files analyzed: {{ summary.files_analyzed }}
• Files with issues: {{ summary.files_with_issues }}
• Issues found: {{ summary.total_issues }}

{% if summary.severity_breakdown %}
*By severity:*
{% for severity, count in summary.severity_breakdown %}
{% if count > 0 %}
• {{ severity | title }}: {{ count }}
{% endif %}
{% endfor %}
{% endif %}

{% if results %}
*Top issues:*
{% for result in results | first:3 %}
• {{ result.severity | upper }}: {{ result.message | truncate:80 }}
{% endfor %}
{% if summary.total_issues > 3 %}
... and {{ summary.total_issues - 3 }} more
{% endif %}
{% endif %}
{% endif %}
        """.strip()


class TemplateFormatter(BaseFormatter):
    """Template-based formatter."""

    def __init__(self, config: FormatterConfig = None, context: OutputContext = None):
        super().__init__(config, context)
        self.engine = SimpleTemplateEngine()
        self.library = TemplateLibrary()

    def get_format_type(self) -> str:
        return "template"

    def supports_feature(self, feature: str) -> bool:
        features = {
            "templates": True,
            "custom_filters": True,
            "conditional_logic": True,
            "loops": True
        }
        return features.get(feature, False)

    def format(self, results: List[RuleResult], template_name: str = "detailed_report", **kwargs) -> Any:
        """Format using specified template."""
        # Get template
        template = self._get_template(template_name, kwargs.get('template_content'))

        if not template:
            return self.create_formatted_output(f"Template not found: {template_name}")

        # Prepare context
        template_context = self._create_template_context(results, kwargs)

        # Render template
        rendered_content = self.engine.render(template, template_context)

        return self.create_formatted_output(rendered_content)

    def _get_template(self, template_name: str, template_content: Optional[str] = None) -> Optional[str]:
        """Get template by name or use provided content."""
        if template_content:
            return template_content

        # Check config for custom template
        custom_template = self.get_template(template_name)
        if custom_template:
            return custom_template

        # Check library
        return self.library.get_template(template_name)

    def _create_template_context(self, results: List[RuleResult], kwargs: Dict[str, Any]) -> TemplateContext:
        """Create template context."""
        # Convert results to dictionaries
        results_dicts = [self._result_to_dict(result) for result in results]

        # Create summary
        summary = self.create_summary(results)

        # Context data
        context_data = {
            "repository_url": self.context.repository_url,
            "repository_path": str(self.context.repository_path) if self.context.repository_path else None,
            "git_range": self.context.git_range,
            "files_analyzed": self.context.files_analyzed,
            "analyzer_version": self.context.analyzer_version,
            "execution_time": self.context.execution_time
        }

        # Config data
        config_data = {
            "show_suggestions": self.config.show_suggestions,
            "show_line_numbers": self.config.show_line_numbers,
            "max_issues_per_file": self.config.max_issues_per_file
        }

        return TemplateContext(
            results=results_dicts,
            summary=summary,
            context=context_data,
            config=config_data,
            metadata=kwargs,
            filters=kwargs.get('custom_filters', {})
        )

    def _result_to_dict(self, result: RuleResult) -> Dict[str, Any]:
        """Convert RuleResult to dictionary for templates."""
        return {
            "rule_name": result.rule_name,
            "checker_name": result.checker_name,
            "severity": result.severity.value,
            "message": result.message,
            "file_path": str(result.file_path),
            "line_number": result.line_number,
            "column": result.column,
            "suggestion": result.suggestion,
            "metadata": result.metadata or {}
        }

    def add_custom_filter(self, name: str, filter_func: Callable):
        """Add custom filter function."""
        self.engine.filters[name] = filter_func

    def load_template_from_file(self, template_path: Path) -> str:
        """Load template from file."""
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()


def create_template_formatter(template_name: str = "detailed_report",
                            config: FormatterConfig = None,
                            context: OutputContext = None) -> TemplateFormatter:
    """Factory function to create template formatter."""
    return TemplateFormatter(config, context)