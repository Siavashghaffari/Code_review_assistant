"""
JSON Formatter

Formats analysis results as JSON for programmatic consumption.
"""

import json
from datetime import datetime
from typing import Dict, List, Any

from .base_formatter import BaseFormatter


class JSONFormatter(BaseFormatter):
    """Formatter for JSON output."""

    def format(self, results: Dict[str, Any]) -> str:
        """Format results as JSON."""
        # Create a clean copy of results with additional metadata
        json_results = dict(results)

        # Add metadata
        json_results["metadata"] = {
            "generated_at": datetime.now().isoformat(),
            "tool_name": "Code Review Automation Tool",
            "format_version": "1.0"
        }

        # Ensure all data is JSON serializable
        json_results = self._make_serializable(json_results)

        # Format with proper indentation
        return json.dumps(json_results, indent=2, ensure_ascii=False)

    def _make_serializable(self, obj: Any) -> Any:
        """
        Recursively convert object to JSON serializable format.

        Args:
            obj: Object to convert

        Returns:
            JSON serializable object
        """
        if isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Convert unknown types to string
            return str(obj)