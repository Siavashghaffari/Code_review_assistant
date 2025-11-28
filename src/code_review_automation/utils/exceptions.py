"""
Custom Exception Classes

Custom exceptions for the code review automation tool.
"""


class CodeReviewError(Exception):
    """Base exception for code review tool."""
    pass


class ConfigurationError(CodeReviewError):
    """Raised when configuration is invalid or cannot be loaded."""
    pass


class AnalysisError(CodeReviewError):
    """Raised when code analysis fails."""
    pass


class GitError(CodeReviewError):
    """Raised when git operations fail."""
    pass


class FormattingError(CodeReviewError):
    """Raised when output formatting fails."""
    pass


class FileProcessingError(CodeReviewError):
    """Raised when file processing fails."""
    pass