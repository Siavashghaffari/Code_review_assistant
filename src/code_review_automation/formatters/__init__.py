"""
Output Formatters Module

This module provides comprehensive output formatting capabilities for the Code Review Assistant,
including terminal, markdown, JSON, HTML, and notification systems with template support.
"""

from .base import BaseFormatter, FormatterConfig, OutputContext, FormattedOutput
from .enhanced_terminal import TerminalFormatter
from .enhanced_markdown import MarkdownFormatter
from .enhanced_json import JSONFormatter
from .html_dashboard import HTMLFormatter
from .template_engine import TemplateFormatter, TemplateLibrary, create_template_formatter
from .notification import NotificationManager, NotificationConfig
from .formatter_registry import (
    FormatterRegistry, OutputRouter, FormatterFactory,
    OutputRequest, OutputResponse, create_formatter, create_output_router
)

__all__ = [
    # Base classes
    'BaseFormatter', 'FormatterConfig', 'OutputContext', 'FormattedOutput',

    # Formatters
    'TerminalFormatter', 'MarkdownFormatter', 'JSONFormatter', 'HTMLFormatter', 'TemplateFormatter',

    # Template engine
    'TemplateLibrary', 'create_template_formatter',

    # Notifications
    'NotificationManager', 'NotificationConfig',

    # Registry and routing
    'FormatterRegistry', 'OutputRouter', 'FormatterFactory',
    'OutputRequest', 'OutputResponse', 'create_formatter', 'create_output_router'
]