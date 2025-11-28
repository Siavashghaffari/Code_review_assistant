# Code Review Automation Tool

A powerful command-line tool for automated code review analysis that can examine git diffs or individual files and generate comprehensive reports in multiple formats.

## Features

- **Git Diff Analysis**: Analyze changes in git commits or ranges
- **File Analysis**: Review individual files or multiple files at once
- **Multiple Output Formats**: Generate reports in Terminal, Markdown, or JSON format
- **Configurable Rules**: Customize review rules and standards via YAML configuration
- **Language Support**: Built-in support for Python, JavaScript, TypeScript, Java, Go, Rust, and more
- **Error Handling**: Robust error handling and logging
- **Extensible**: Easy to add new analyzers and formatters

## Installation

### From Source

```bash
git clone <repository-url>
cd code_reviewer
pip install -e .
```

### Dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Basic Examples

```bash
# Analyze git diff between commits
python code_review.py --git-diff HEAD~1..HEAD --format terminal

# Analyze specific files
python code_review.py --files src/main.py src/utils/logger.py --format markdown

# Use custom configuration
python code_review.py --git-diff --config .codereview.yaml --format json

# Save output to file
python code_review.py --files *.py --format markdown --output review_report.md

# Analyze all Python files in current directory
python code_review.py --files *.py --format terminal

# Get help
python code_review.py --help
```

### Command Line Options

```
positional arguments:
  None

optional arguments:
  -h, --help            show this help message and exit

Input options (mutually exclusive):
  --git-diff [GIT_RANGE]
                        Analyze git diff (default: HEAD~1..HEAD)
  --files FILES [FILES ...]
                        Analyze specific files

Output options:
  --format {markdown,json,terminal}
                        Output format (default: terminal)
  --output OUTPUT, -o OUTPUT
                        Output file (default: stdout)

Configuration:
  --config CONFIG, -c CONFIG
                        Configuration file path
  --verbose, -v         Enable verbose logging
```

## Configuration

The tool uses YAML configuration files to define review rules and standards. See `config/default_rules.yaml` for the complete configuration schema.

### Key Configuration Sections

#### File Types
```yaml
file_types:
  include:  # File extensions to analyze
    - .py
    - .js
    - .ts
  exclude:  # File extensions to skip
    - .min.js
    - .map
  exclude_paths:  # Path patterns to skip
    - node_modules/
    - __pycache__/
```

#### Language Rules
```yaml
languages:
  .py:
    language: python
    max_line_length: 88
    max_file_lines: 500
    no_tabs: true
    rules:
      - no_wildcard_imports
      - use_logging_not_print
```

#### Severity Levels
```yaml
severity:
  error:    # Critical issues
    - syntax_error
    - security_vulnerability
  warning:  # Important issues
    - line_too_long
    - wildcard_import
  info:     # Suggestions
    - todo_comment
    - print_statement
```

## Output Formats

### Terminal Format
Colorized output with Unicode symbols, perfect for command-line usage:

```
🔍 Code Review Analysis Results
================================
Git Range: HEAD~1..HEAD

📊 Summary:
  • Total Issues: 5 issues
  • Total Suggestions: 3 suggestions
  • Files with Issues: 2

📋 Issues Found:

📄 src/main.py
  ❌ ERROR: Line exceeds 88 characters (line 45)
  ⚠️  WARNING: Avoid wildcard imports (line 12)
```

### Markdown Format
Professional reports suitable for documentation:

```markdown
# Code Review Analysis Report

## Analysis Information

| Field | Value |
|-------|-------|
| Analysis Type | Git Diff |
| Generated At | 2024-01-15 14:30:25 |
| Git Range | `HEAD~1..HEAD` |

## Issues

### 📄 `src/main.py`

**2 issue(s) found**

1. ❌ **ERROR**: Line exceeds 88 characters *(line 45)*
```

### JSON Format
Structured data for programmatic consumption:

```json
{
  "analysis_type": "git_diff",
  "git_range": "HEAD~1..HEAD",
  "files_analyzed": 2,
  "issues": [
    {
      "type": "line_too_long",
      "severity": "warning",
      "message": "Line exceeds 88 characters (95)",
      "file": "src/main.py",
      "line": 45,
      "content": "very_long_function_name_that_exceeds_the_configured_line_length_limit_and_should_be_shortened"
    }
  ],
  "metadata": {
    "generated_at": "2024-01-15T14:30:25",
    "tool_name": "Code Review Automation Tool",
    "format_version": "1.0"
  }
}
```

## Project Structure

```
code_reviewer/
├── src/
│   ├── main.py                 # Main entry point
│   ├── analyzers/              # Code analysis modules
│   │   ├── base_analyzer.py
│   │   ├── git_analyzer.py
│   │   └── file_analyzer.py
│   ├── formatters/             # Output formatting modules
│   │   ├── base_formatter.py
│   │   ├── terminal_formatter.py
│   │   ├── markdown_formatter.py
│   │   └── json_formatter.py
│   └── utils/                  # Utility modules
│       ├── config_loader.py
│       ├── logger.py
│       └── exceptions.py
├── config/
│   └── default_rules.yaml      # Default configuration
├── tests/                      # Test files
├── docs/                       # Documentation
├── requirements.txt            # Python dependencies
├── setup.py                    # Package setup
└── README.md                   # This file
```

## Supported Languages

- Python (.py)
- JavaScript (.js)
- TypeScript (.ts)
- JSX (.jsx)
- TSX (.tsx)
- Java (.java)
- Go (.go)
- Rust (.rs)
- Ruby (.rb)
- PHP (.php)
- Swift (.swift)
- Kotlin (.kt)
- Scala (.scala)
- Shell scripts (.sh)
- YAML (.yml, .yaml)
- JSON (.json)
- XML (.xml)
- Markdown (.md)

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
black src/
```

### Linting

```bash
flake8 src/
mypy src/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Authors

This work was developed by Siavash Ghaffari. For any questions, feedback, or additional information, please feel free to reach out. Your input is highly valued and will help improve and refine this pipeline further.

## Changelog

### v1.0.0
- Initial release
- Git diff and file analysis
- Terminal, Markdown, and JSON output formats
- Configurable rules system
- Multi-language support