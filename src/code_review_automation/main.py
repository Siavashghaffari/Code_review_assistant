#!/usr/bin/env python3
"""
Code Review Automation Tool

Main script for analyzing git diffs or individual files and generating
code review reports with configurable rules and output formats.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .analyzers.git_analyzer import GitAnalyzer
from .analyzers.file_analyzer import FileAnalyzer
from .formatters.output_formatter import OutputFormatter
from .utils.config_loader import ConfigLoader
from .utils.logger import setup_logger


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Code Review Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --git-diff HEAD~1..HEAD --format markdown
  %(prog)s --files src/main.py src/utils.py --format json
  %(prog)s --git-diff --format terminal --config custom_rules.yaml
        """
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--git-diff",
        nargs="?",
        const="HEAD~1..HEAD",
        help="Analyze git diff (default: HEAD~1..HEAD)"
    )
    input_group.add_argument(
        "--files",
        nargs="+",
        help="Analyze specific files"
    )

    # Output options
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "terminal"],
        default="terminal",
        help="Output format (default: terminal)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: stdout)"
    )

    # Configuration
    parser.add_argument(
        "--config",
        "-c",
        help="Configuration file path"
    )

    # Verbosity
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    try:
        args = parse_arguments(argv)

        # Setup logging
        logger = setup_logger(verbose=args.verbose)

        # Load configuration
        config_loader = ConfigLoader()
        config = config_loader.load(args.config)

        # Initialize analyzer based on input type
        if args.git_diff is not None:
            logger.info(f"Analyzing git diff: {args.git_diff}")
            analyzer = GitAnalyzer(config)
            analysis_result = analyzer.analyze(args.git_diff)
        else:
            logger.info(f"Analyzing files: {args.files}")
            analyzer = FileAnalyzer(config)
            analysis_result = analyzer.analyze(args.files)

        # Format output
        formatter = OutputFormatter()
        formatted_output = formatter.format(
            analysis_result,
            format_type=args.format
        )

        # Write output
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(formatted_output)
            logger.info(f"Report written to {output_path}")
        else:
            print(formatted_output)

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())