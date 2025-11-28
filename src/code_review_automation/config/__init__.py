"""
Configuration Management Module

This module provides comprehensive configuration management for the Code Review Assistant,
including YAML/JSON parsing, rule engines, severity levels, custom rules, and advanced
file filtering capabilities.
"""

from .config_manager import ConfigManager, create_config_manager
from .config_parser import ConfigParser
from .rule_engine import RuleEngine, RuleResult, RuleContext
from .schema import (
    ConfigSchema, RuleConfig, SeverityLevel, FileTypeConfig,
    CheckerConfig, IgnorePattern, create_default_config
)
from .custom_rules import CustomRuleManager, CustomRuleDefinition
from .ignore_patterns import FileFilterEngine, create_file_filter
from .validation import AdvancedConfigValidator, ConfigMerger

__all__ = [
    'ConfigManager', 'create_config_manager',
    'ConfigParser', 'RuleEngine', 'RuleResult', 'RuleContext',
    'ConfigSchema', 'RuleConfig', 'SeverityLevel', 'FileTypeConfig',
    'CheckerConfig', 'IgnorePattern', 'create_default_config',
    'CustomRuleManager', 'CustomRuleDefinition',
    'FileFilterEngine', 'create_file_filter',
    'AdvancedConfigValidator', 'ConfigMerger'
]