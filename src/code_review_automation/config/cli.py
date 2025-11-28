#!/usr/bin/env python3
"""
Configuration CLI Tool

Command-line interface for managing Code Review Assistant configurations.
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Dict, Any

from .config_manager import ConfigManager
from .validation import AdvancedConfigValidator
from .custom_rules import CustomRuleManager
from ..utils.logger import setup_logger


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Code Review Assistant Configuration Tool",
        prog="codereview-config"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.add_argument("config", nargs="?", help="Configuration file path")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show configuration")
    show_parser.add_argument("config", nargs="?", help="Configuration file path")
    show_parser.add_argument("--format", choices=["yaml", "json"], default="yaml")

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize configuration")
    init_parser.add_argument("--template", choices=["default", "strict", "relaxed", "security"], default="default")
    init_parser.add_argument("--output", default=".codereview.yaml")

    # Rules command
    rules_parser = subparsers.add_parser("rules", help="Manage rules")
    rules_subparsers = rules_parser.add_subparsers(dest="rules_command")

    rules_list_parser = rules_subparsers.add_parser("list", help="List available rules")
    rules_list_parser.add_argument("config", nargs="?", help="Configuration file path")

    rules_enable_parser = rules_subparsers.add_parser("enable", help="Enable a rule")
    rules_enable_parser.add_argument("rule", help="Rule name (checker.rule)")
    rules_enable_parser.add_argument("config", nargs="?", help="Configuration file path")

    rules_disable_parser = rules_subparsers.add_parser("disable", help="Disable a rule")
    rules_disable_parser.add_argument("rule", help="Rule name (checker.rule)")
    rules_disable_parser.add_argument("config", nargs="?", help="Configuration file path")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test configuration")
    test_parser.add_argument("config", nargs="?", help="Configuration file path")
    test_parser.add_argument("--file", required=True, help="Test file path")

    # Global options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")

    args = parser.parse_args()

    # Setup logging
    if args.quiet:
        level = "ERROR"
    elif args.verbose:
        level = "DEBUG"
    else:
        level = "INFO"

    setup_logger(level=level)

    # Execute command
    try:
        if args.command == "validate":
            validate_config(args.config)
        elif args.command == "show":
            show_config(args.config, args.format)
        elif args.command == "init":
            init_config(args.template, args.output)
        elif args.command == "rules":
            manage_rules(args)
        elif args.command == "test":
            test_config(args.config, args.file)
        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def validate_config(config_path: str = None):
    """Validate configuration file."""
    try:
        config_manager = ConfigManager(config_path)
        validator = AdvancedConfigValidator()

        validation_results = validator.validate_config(config_manager.get_config())

        total_errors = sum(len(errors) for errors in validation_results.values())

        if total_errors == 0:
            print("✅ Configuration validation passed!")
            return

        print(f"❌ Configuration validation found {total_errors} issues:\n")

        for category, errors in validation_results.items():
            if errors:
                print(f"{category.replace('_', ' ').title()}:")
                for error in errors:
                    print(f"  • {error}")
                print()

    except Exception as e:
        print(f"Failed to validate configuration: {e}")
        sys.exit(1)


def show_config(config_path: str = None, format: str = "yaml"):
    """Show configuration details."""
    try:
        config_manager = ConfigManager(config_path)
        summary = config_manager.get_configuration_summary()

        if format == "json":
            print(json.dumps(summary, indent=2))
        else:
            print("Configuration Summary:")
            print(f"Version: {summary['version']}")
            print(f"Severity Threshold: {summary['severity_threshold']}")
            print(f"Fail on Severity: {summary['fail_on_severity']}")
            print(f"Max Issues: {summary['max_issues_per_run']}")
            print(f"Ignore Patterns: {summary['ignore_patterns']}")
            print(f"File Types Configured: {summary['file_types_configured']}")
            print(f"Custom Rules: {summary['custom_rules']}")
            print(f"Output Format: {summary['output_format']}")

            print("\nCheckers:")
            rules_info = summary['rules']
            for checker_name, checker_info in rules_info['checkers'].items():
                status = "✅" if checker_info['enabled'] else "❌"
                print(f"  {status} {checker_name}: {checker_info['enabled_rules']}/{checker_info['total_rules']} rules enabled")

    except Exception as e:
        print(f"Failed to show configuration: {e}")
        sys.exit(1)


def init_config(template: str, output_path: str):
    """Initialize a new configuration file."""
    try:
        output = Path(output_path)

        if output.exists():
            response = input(f"Configuration file {output_path} already exists. Overwrite? (y/N): ")
            if response.lower() != 'y':
                print("Aborted.")
                return

        # Create configuration based on template
        config_manager = ConfigManager()

        if template == "strict":
            config_manager.apply_severity_profile("strict")
        elif template == "relaxed":
            config_manager.apply_severity_profile("relaxed")
        elif template == "security":
            config_manager.apply_severity_profile("security_focused")

        # Save configuration
        success = config_manager.save_config(output, "yaml")

        if success:
            print(f"✅ Created configuration file: {output_path}")
            print(f"📝 Template: {template}")
            print("\nNext steps:")
            print("1. Review and customize the configuration")
            print("2. Run 'codereview-config validate' to check it")
            print("3. Test with 'codereview-config test --file <file>'")
        else:
            print("❌ Failed to create configuration file")
            sys.exit(1)

    except Exception as e:
        print(f"Failed to initialize configuration: {e}")
        sys.exit(1)


def manage_rules(args):
    """Manage rules (enable/disable/list)."""
    try:
        config_manager = ConfigManager(args.config)

        if args.rules_command == "list":
            summary = config_manager.get_configuration_summary()
            rules_info = summary['rules']

            print("Available Rules:")
            for checker_name, checker_info in rules_info['checkers'].items():
                print(f"\n{checker_name}:")
                for rule_name, rule_info in checker_info['rules'].items():
                    status = "✅" if rule_info['enabled'] else "❌"
                    severity = rule_info.get('severity', 'unknown')
                    print(f"  {status} {rule_name} ({severity})")

        elif args.rules_command == "enable":
            checker_name, rule_name = parse_rule_name(args.rule)
            config_manager.enable_rule(checker_name, rule_name)
            print(f"✅ Enabled rule: {args.rule}")

        elif args.rules_command == "disable":
            checker_name, rule_name = parse_rule_name(args.rule)
            config_manager.disable_rule(checker_name, rule_name)
            print(f"❌ Disabled rule: {args.rule}")

    except Exception as e:
        print(f"Failed to manage rules: {e}")
        sys.exit(1)


def parse_rule_name(rule_name: str) -> tuple:
    """Parse rule name in format checker.rule."""
    parts = rule_name.split(".", 1)
    if len(parts) != 2:
        raise ValueError("Rule name must be in format 'checker.rule'")
    return parts[0], parts[1]


def test_config(config_path: str = None, test_file: str = None):
    """Test configuration against a file."""
    try:
        config_manager = ConfigManager(config_path)
        test_path = Path(test_file)

        if not test_path.exists():
            print(f"Test file not found: {test_file}")
            sys.exit(1)

        # Check if file would be ignored
        if config_manager.is_file_ignored(test_path):
            print(f"❌ File would be ignored by current configuration: {test_file}")
            return

        # Get file type configuration
        file_config = config_manager.get_file_type_config(test_path)
        if file_config:
            print(f"✅ File would be processed: {test_file}")
            print(f"File type configuration found: {file_config.file_type.value}")
            print(f"Max line length: {file_config.max_line_length}")
            print(f"Max complexity: {file_config.max_complexity}")
        else:
            print(f"⚠️  File would be processed but no specific configuration found: {test_file}")

        # Show applicable rules
        rule_engine = config_manager.get_rule_engine()
        summary = rule_engine.get_enabled_rules_summary()
        total_rules = summary['enabled_rules']
        print(f"Total enabled rules that would apply: {total_rules}")

    except Exception as e:
        print(f"Failed to test configuration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()