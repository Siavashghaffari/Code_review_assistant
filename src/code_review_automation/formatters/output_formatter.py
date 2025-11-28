"""
Output Formatter

Formats analysis results into different output formats (markdown, JSON, terminal).
"""

import json
from datetime import datetime
from typing import Dict, List, Any

from .terminal_formatter import TerminalFormatter
from .markdown_formatter import MarkdownFormatter
from .json_formatter import JSONFormatter
from ..utils.logger import get_logger


class OutputFormatter:
    """Main output formatter that delegates to specific formatters."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.formatters = {
            "terminal": TerminalFormatter(),
            "markdown": MarkdownFormatter(),
            "json": JSONFormatter()
        }

    def format(self, analysis_results: Dict[str, Any], format_type: str = "terminal") -> str:
        """
        Format analysis results using the specified formatter.

        Args:
            analysis_results: Results from code analysis
            format_type: Output format type

        Returns:
            Formatted output string
        """
        if format_type not in self.formatters:
            raise ValueError(f"Unsupported format type: {format_type}")

        formatter = self.formatters[format_type]
        return formatter.format(analysis_results)

    def get_supported_formats(self) -> List[str]:
        """Get list of supported output formats."""
        return list(self.formatters.keys())