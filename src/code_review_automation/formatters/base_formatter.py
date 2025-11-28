"""
Base Formatter

Abstract base class for all output formatters.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseFormatter(ABC):
    """Abstract base class for output formatters."""

    @abstractmethod
    def format(self, results: Dict[str, Any]) -> str:
        """
        Format analysis results.

        Args:
            results: Analysis results dictionary

        Returns:
            Formatted output string
        """
        pass