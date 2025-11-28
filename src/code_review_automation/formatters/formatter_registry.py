"""
Formatter Registry and Output Router

Central registry for all formatters with routing, caching, and plugin support.
"""

import asyncio
from typing import Dict, List, Any, Optional, Type, Union, Callable
from dataclasses import dataclass, field
from pathlib import Path
import importlib
import inspect

from .base import BaseFormatter, FormatterConfig, OutputContext, FormattedOutput
from .enhanced_terminal import TerminalFormatter
from .enhanced_markdown import MarkdownFormatter
from .enhanced_json import JSONFormatter
from .html_dashboard import HTMLFormatter
from .notification import NotificationManager, NotificationConfig
from ..config.rule_engine import RuleResult
from ..utils.logger import get_logger


@dataclass
class FormatterInfo:
    """Information about a registered formatter."""
    name: str
    formatter_class: Type[BaseFormatter]
    description: str
    supported_features: List[str] = field(default_factory=list)
    supported_sub_formats: List[str] = field(default_factory=list)
    is_plugin: bool = False
    plugin_path: Optional[Path] = None


@dataclass
class OutputRequest:
    """Request for formatted output."""
    format_type: str
    sub_format: Optional[str] = None
    results: List[RuleResult] = field(default_factory=list)
    context: Optional[OutputContext] = None
    config: Optional[FormatterConfig] = None
    output_path: Optional[Path] = None
    additional_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OutputResponse:
    """Response from formatter."""
    success: bool
    formatted_output: Optional[FormattedOutput] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class FormatterRegistry:
    """Central registry for all output formatters."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self._formatters: Dict[str, FormatterInfo] = {}
        self._instances: Dict[str, BaseFormatter] = {}
        self._plugins_loaded = False

        # Register built-in formatters
        self._register_builtin_formatters()

    def _register_builtin_formatters(self):
        """Register built-in formatters."""
        builtin_formatters = [
            ("terminal", TerminalFormatter, "Enhanced terminal output with colors and formatting"),
            ("markdown", MarkdownFormatter, "Markdown output for GitHub/GitLab integration"),
            ("json", JSONFormatter, "JSON output for CI/CD and API integration"),
            ("html", HTMLFormatter, "HTML dashboard for team metrics and analytics")
        ]

        for name, formatter_class, description in builtin_formatters:
            self.register_formatter(name, formatter_class, description)

    def register_formatter(self, name: str, formatter_class: Type[BaseFormatter],
                         description: str = "", is_plugin: bool = False,
                         plugin_path: Optional[Path] = None):
        """Register a formatter."""
        try:
            # Get supported features from formatter
            temp_instance = formatter_class()
            supported_features = []
            supported_sub_formats = []

            # Check for supported features
            common_features = ["colors", "links", "images", "tables", "code_blocks",
                             "interactive", "streaming", "charts"]

            for feature in common_features:
                if temp_instance.supports_feature(feature):
                    supported_features.append(feature)

            # Check for sub-formats if supported
            if hasattr(temp_instance, 'get_available_sub_formats'):
                supported_sub_formats = temp_instance.get_available_sub_formats()

            formatter_info = FormatterInfo(
                name=name,
                formatter_class=formatter_class,
                description=description,
                supported_features=supported_features,
                supported_sub_formats=supported_sub_formats,
                is_plugin=is_plugin,
                plugin_path=plugin_path
            )

            self._formatters[name] = formatter_info
            self.logger.info(f"Registered formatter: {name}")

        except Exception as e:
            self.logger.error(f"Failed to register formatter {name}: {e}")

    def unregister_formatter(self, name: str):
        """Unregister a formatter."""
        if name in self._formatters:
            del self._formatters[name]
            if name in self._instances:
                del self._instances[name]
            self.logger.info(f"Unregistered formatter: {name}")

    def get_formatter(self, name: str, config: Optional[FormatterConfig] = None,
                     context: Optional[OutputContext] = None) -> Optional[BaseFormatter]:
        """Get formatter instance."""
        if name not in self._formatters:
            self.logger.error(f"Formatter not found: {name}")
            return None

        # Return cached instance or create new one
        cache_key = f"{name}_{id(config)}_{id(context)}"

        if cache_key not in self._instances:
            formatter_info = self._formatters[name]
            try:
                self._instances[cache_key] = formatter_info.formatter_class(config, context)
            except Exception as e:
                self.logger.error(f"Failed to create formatter instance {name}: {e}")
                return None

        return self._instances[cache_key]

    def list_formatters(self) -> Dict[str, FormatterInfo]:
        """List all registered formatters."""
        return self._formatters.copy()

    def get_formatters_by_feature(self, feature: str) -> List[str]:
        """Get formatters that support a specific feature."""
        return [
            name for name, info in self._formatters.items()
            if feature in info.supported_features
        ]

    def load_plugins(self, plugin_directories: List[Path]):
        """Load formatter plugins from directories."""
        if self._plugins_loaded:
            return

        for plugin_dir in plugin_directories:
            if not plugin_dir.exists():
                continue

            self.logger.info(f"Loading plugins from: {plugin_dir}")

            for plugin_file in plugin_dir.glob("*.py"):
                if plugin_file.name.startswith("_"):
                    continue

                try:
                    self._load_plugin_file(plugin_file)
                except Exception as e:
                    self.logger.error(f"Failed to load plugin {plugin_file}: {e}")

        self._plugins_loaded = True

    def _load_plugin_file(self, plugin_file: Path):
        """Load a single plugin file."""
        spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for formatter classes
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and
                issubclass(obj, BaseFormatter) and
                obj is not BaseFormatter):

                plugin_name = getattr(obj, 'PLUGIN_NAME', name.lower())
                description = getattr(obj, 'PLUGIN_DESCRIPTION', f"Plugin formatter: {name}")

                self.register_formatter(
                    plugin_name,
                    obj,
                    description,
                    is_plugin=True,
                    plugin_path=plugin_file
                )


class OutputRouter:
    """Routes output requests to appropriate formatters."""

    def __init__(self, formatter_registry: FormatterRegistry = None):
        self.logger = get_logger(__name__)
        self.registry = formatter_registry or FormatterRegistry()
        self.notification_manager = None

    async def format_output(self, request: OutputRequest) -> OutputResponse:
        """Format output using the appropriate formatter."""
        try:
            # Get formatter
            formatter = self.registry.get_formatter(
                request.format_type,
                request.config,
                request.context
            )

            if not formatter:
                return OutputResponse(
                    success=False,
                    error=f"Formatter not found: {request.format_type}"
                )

            # Check if sub-format is supported
            if request.sub_format and hasattr(formatter, 'supports_sub_format'):
                if not formatter.supports_sub_format(request.sub_format):
                    return OutputResponse(
                        success=False,
                        error=f"Sub-format '{request.sub_format}' not supported by {request.format_type}"
                    )

            # Format the output
            formatted_output = await self._execute_formatter(
                formatter, request.results, request.sub_format, request.additional_options
            )

            # Save to file if requested
            if request.output_path:
                await self._save_output(formatted_output, request.output_path)

            return OutputResponse(
                success=True,
                formatted_output=formatted_output,
                metadata={
                    "formatter": request.format_type,
                    "sub_format": request.sub_format,
                    "output_size": formatted_output.size_bytes
                }
            )

        except Exception as e:
            self.logger.error(f"Error formatting output: {e}")
            return OutputResponse(
                success=False,
                error=str(e)
            )

    async def format_multiple(self, requests: List[OutputRequest]) -> List[OutputResponse]:
        """Format multiple outputs in parallel."""
        tasks = [self.format_output(request) for request in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def send_notifications(self, results: List[RuleResult], context: OutputContext,
                               notification_config: NotificationConfig,
                               platforms: List[str]) -> Dict[str, Any]:
        """Send notifications to specified platforms."""
        if not self.notification_manager:
            self.notification_manager = NotificationManager(notification_config)

        return await self.notification_manager.send_notifications(
            results, context, platforms
        )

    async def _execute_formatter(self, formatter: BaseFormatter, results: List[RuleResult],
                               sub_format: Optional[str], options: Dict[str, Any]) -> FormattedOutput:
        """Execute formatter with proper error handling."""
        if sub_format:
            return formatter.format(results, sub_format=sub_format, **options)
        else:
            return formatter.format(results, **options)

    async def _save_output(self, formatted_output: FormattedOutput, output_path: Path):
        """Save formatted output to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(formatted_output.content)

        self.logger.info(f"Output saved to: {output_path}")


class FormatterFactory:
    """Factory for creating formatters with common configurations."""

    def __init__(self, router: OutputRouter):
        self.router = router
        self.logger = get_logger(__name__)

    def create_terminal_formatter(self, use_colors: bool = True,
                                use_unicode: bool = True) -> TerminalFormatter:
        """Create terminal formatter with specific settings."""
        config = FormatterConfig()
        context = OutputContext()

        formatter = TerminalFormatter(config, context)
        formatter.use_colors = use_colors
        formatter.use_unicode = use_unicode

        return formatter

    def create_github_formatter(self, repository_url: str = None) -> MarkdownFormatter:
        """Create GitHub-optimized markdown formatter."""
        config = FormatterConfig(show_suggestions=True, include_metadata=True)
        context = OutputContext(repository_url=repository_url)

        return MarkdownFormatter(config, context)

    def create_ci_formatter(self, format_type: str = "json",
                          sub_format: str = "gitlab_ci") -> JSONFormatter:
        """Create CI/CD optimized formatter."""
        config = FormatterConfig(include_metadata=False)
        context = OutputContext()

        return JSONFormatter(config, context)

    def create_dashboard_formatter(self, theme: str = "default") -> HTMLFormatter:
        """Create HTML dashboard formatter."""
        config = FormatterConfig(
            show_suggestions=True,
            include_metadata=True,
            custom_templates={"theme": theme}
        )
        context = OutputContext()

        return HTMLFormatter(config, context)


class FormatterPlugin:
    """Base class for formatter plugins."""

    PLUGIN_NAME: str = ""
    PLUGIN_DESCRIPTION: str = ""
    PLUGIN_VERSION: str = "1.0.0"

    @classmethod
    def get_formatter_class(cls) -> Type[BaseFormatter]:
        """Get the formatter class."""
        raise NotImplementedError

    @classmethod
    def get_dependencies(cls) -> List[str]:
        """Get list of required dependencies."""
        return []

    @classmethod
    def validate_environment(cls) -> bool:
        """Validate that the environment supports this plugin."""
        return True


def create_formatter(format_type: str, config: FormatterConfig = None,
                   context: OutputContext = None) -> Optional[BaseFormatter]:
    """Factory function to create a formatter."""
    registry = FormatterRegistry()
    return registry.get_formatter(format_type, config, context)


def create_output_router(plugin_directories: List[Path] = None) -> OutputRouter:
    """Factory function to create an output router."""
    registry = FormatterRegistry()

    if plugin_directories:
        registry.load_plugins(plugin_directories)

    return OutputRouter(registry)


# Example plugin template
class ExampleFormatterPlugin(FormatterPlugin):
    """Example formatter plugin."""

    PLUGIN_NAME = "example"
    PLUGIN_DESCRIPTION = "Example formatter plugin"
    PLUGIN_VERSION = "1.0.0"

    @classmethod
    def get_formatter_class(cls):
        # Would return a custom formatter class
        return TerminalFormatter

    @classmethod
    def get_dependencies(cls):
        return ["requests", "jinja2"]

    @classmethod
    def validate_environment(cls):
        try:
            import requests
            import jinja2
            return True
        except ImportError:
            return False