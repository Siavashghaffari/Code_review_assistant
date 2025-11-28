# Git Integration Module

This module provides comprehensive git integration capabilities for the Code Review Assistant, including diff parsing, focused reviews, platform integrations, and workflow handling.

## 🚀 Features

### Core Git Operations
- **Diff Parsing**: Parse git diffs into structured format with line-by-line analysis
- **Change Detection**: Identify added, removed, and modified lines
- **Focused Reviews**: Analyze only changed code, not entire files
- **Commit Analysis**: Generate intelligent commit messages based on changes

### Platform Integrations
- **GitHub Integration**: Create PR reviews, post line comments, manage issues
- **GitLab Integration**: Handle merge requests, discussions, and project management
- **API Rate Limiting**: Smart handling of API limits and retries

### Workflow Support
- **Multiple Workflows**: Support for GitHub Flow, GitFlow, feature branches
- **Branch Analysis**: Classify branches and understand workflow context
- **Compliance Checking**: Validate against workflow rules and policies
- **Smart Suggestions**: Context-aware recommendations for next steps

## 📁 Module Structure

```
src/git/
├── __init__.py
├── diff_parser.py           # Git diff parsing and analysis
├── focused_review.py        # Focused review on changed lines only
├── commit_generator.py      # Intelligent commit message generation
├── workflow_handlers.py     # Git workflow pattern handling
├── review_orchestrator.py   # Complete review orchestration
├── platforms/
│   ├── __init__.py
│   ├── github_integration.py   # GitHub API integration
│   └── gitlab_integration.py   # GitLab API integration
└── README.md
```

## 🔧 Usage Examples

### Basic Git Diff Analysis

```python
from src.git.diff_parser import GitDiffParser, GitCommands

# Parse a git diff
parser = GitDiffParser()
git_commands = GitCommands(repo_path=Path("/path/to/repo"))

diff_text = git_commands.get_diff("HEAD~1", "HEAD")
diff_result = parser.parse_diff(diff_text)

print(f"Files changed: {len(diff_result.files)}")
print(f"Lines added: {diff_result.total_added}")
print(f"Lines removed: {diff_result.total_removed}")
```

### Focused Review on Changes

```python
from src.git.focused_review import FocusedReviewAnalyzer

# Analyze only changed lines
config = load_config()  # Your configuration
analyzer = FocusedReviewAnalyzer(config)

review_result = analyzer.analyze_diff(diff_text, repo_path)

print(f"Issues found: {len(review_result.issues)}")
print(f"Files reviewed: {review_result.files_reviewed}")
print(f"Lines reviewed: {review_result.lines_reviewed}")
```

### Generate Commit Messages

```python
from src.git.commit_generator import CommitMessageGenerator

# Generate intelligent commit messages
generator = CommitMessageGenerator()
diff_result = parser.parse_diff(diff_text)

suggestions = generator.generate_commit_messages(diff_result)
for suggestion in suggestions:
    print(f"💡 {suggestion}")
```

### GitHub Integration

```python
from src.git.platforms.github_integration import GitHubIntegration

# Setup GitHub integration
github = GitHubIntegration(token="your_github_token")

# Get pull request info
pr_info = await github.get_pull_request("owner", "repo", 123)
print(f"PR: {pr_info.title}")

# Post review comments
await github.post_review_comments("owner", "repo", 123, focused_issues)
```

### GitLab Integration

```python
from src.git.platforms.gitlab_integration import GitLabIntegration

# Setup GitLab integration
gitlab = GitLabIntegration(token="your_gitlab_token")

# Get merge request diff
mr_diff = await gitlab.get_merge_request_diff(project_id=456, mr_iid=789)

# Post review comments
await gitlab.post_review_comments(456, 789, focused_issues, base_sha, head_sha, start_sha)
```

### Complete Review Orchestration

```python
from src.git.review_orchestrator import ReviewOrchestrator, ReviewRequest

# Setup orchestrator
config = load_config()
orchestrator = ReviewOrchestrator(config)

# Review a GitHub pull request
request = ReviewRequest(
    repository_url="https://github.com/owner/repo",
    pr_number=123,
    platform="github",
    github_token="your_token",
    post_comments=True
)

response = await orchestrator.conduct_review(request)

print(f"Issues: {len(response.review_result.issues)}")
print(f"Commit suggestions: {response.commit_suggestions}")
print(f"Next actions: {response.next_actions}")
```

## 🎯 Key Classes and Functions

### GitDiffParser
- `parse_diff(diff_text)` - Parse git diff into structured format
- `get_changed_lines_for_file(file_diff)` - Get line numbers that changed
- `filter_lines_by_changes(content, changed_lines)` - Filter content to changed lines

### FocusedReviewAnalyzer
- `analyze_diff(diff_text, repo_path)` - Analyze only changed lines
- `analyze_pull_request_diff(base_ref, head_ref, repo_path)` - Analyze PR changes

### CommitMessageGenerator
- `generate_commit_messages(diff_result)` - Generate commit message suggestions
- `analyze_changes(diff_result)` - Analyze change patterns
- `generate_commit_body(analysis)` - Generate detailed commit body

### GitHubIntegration
- `parse_github_url(url)` - Parse repository URL
- `get_pull_request(owner, repo, pr_number)` - Get PR information
- `create_pull_request_review(...)` - Create PR review with comments
- `post_review_comments(...)` - Post focused review comments

### GitLabIntegration
- `parse_gitlab_url(url)` - Parse repository URL
- `get_merge_request(project_id, mr_iid)` - Get MR information
- `create_merge_request_discussion(...)` - Create MR discussion
- `post_review_comments(...)` - Post focused review comments

### GitWorkflowHandler
- `detect_workflow(repo_path)` - Auto-detect workflow type
- `analyze_branch_info(branch_name)` - Analyze branch characteristics
- `validate_workflow_compliance(context)` - Check workflow compliance
- `suggest_next_actions(context, results)` - Workflow-aware suggestions

### ReviewOrchestrator
- `conduct_review(request)` - Complete review orchestration
- `review_pull_request(...)` - Review GitHub PR or GitLab MR
- `review_local_changes(...)` - Review local repository changes

## ⚙️ Configuration

The git integration uses the main configuration system with these specific sections:

```yaml
git:
  # Platform tokens (use environment variables)
  github_token: ${GITHUB_TOKEN}
  gitlab_token: ${GITLAB_TOKEN}
  gitlab_url: https://gitlab.example.com  # Optional, defaults to gitlab.com

  # Workflow settings
  workflow:
    auto_detect: true
    default_type: feature_branch
    protected_branches: [main, master, develop]

  # Review settings
  review:
    focus_on_changes_only: true
    context_lines: 3
    max_comments_per_review: 20
    post_summary_comments: true

  # Commit message settings
  commit_messages:
    conventional_commits: true
    include_file_list: false
    max_suggestions: 5
```

## 🔐 Security Considerations

### Token Management
- Store API tokens in environment variables
- Use personal access tokens with minimal required permissions
- Implement token rotation for long-running services

### API Rate Limits
- GitHub: 5000 requests/hour for authenticated users
- GitLab: 2000 requests/hour for authenticated users
- Built-in rate limiting and retry logic

### Permissions Required

**GitHub Token Permissions:**
- `repo` - Repository access
- `pull_requests` - PR read/write
- `issues` - Issue creation (optional)

**GitLab Token Permissions:**
- `api` - Full API access
- `read_repository` - Repository read
- `write_repository` - For creating comments

## 🚧 Error Handling

The module includes comprehensive error handling:

- **Network Errors**: Automatic retry with exponential backoff
- **API Errors**: Detailed error messages and fallback behavior
- **Git Errors**: Graceful handling of git command failures
- **Parsing Errors**: Robust parsing with error recovery

## 📈 Performance Optimizations

- **Async Operations**: All API calls are asynchronous
- **Focused Analysis**: Only analyze changed lines, not entire files
- **Batch Operations**: Group API calls when possible
- **Caching**: Cache repository information during review session
- **Streaming**: Process large diffs in chunks

## 🧪 Testing

```bash
# Run git integration tests
pytest src/git/tests/ -v

# Run with coverage
pytest src/git/tests/ --cov=src/git --cov-report=html

# Run specific test categories
pytest src/git/tests/ -m "github_integration"
pytest src/git/tests/ -m "diff_parsing"
```

## 📝 Contributing

When adding new git integration features:

1. Follow the existing async/await patterns
2. Add comprehensive error handling
3. Include type hints for all functions
4. Write tests for new functionality
5. Update this README with usage examples

## 🔗 Related Modules

- `src/analyzers/` - Core code analysis (used by focused review)
- `src/utils/` - Logging and configuration utilities
- `src/formatters/` - Output formatting for review results

This git integration module provides a complete foundation for git-aware code reviews with platform integration and workflow intelligence.