"""
HTML Dashboard Formatter

Creates interactive HTML dashboards for team review metrics with charts,
trends, and detailed analysis views.
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

from .base import BaseFormatter, FormatterConfig, OutputContext, MultiFormatSupport
from ..config.rule_engine import RuleResult


class HTMLFormatter(BaseFormatter, MultiFormatSupport):
    """HTML dashboard formatter for team metrics and analytics."""

    def __init__(self, config: FormatterConfig = None, context: OutputContext = None):
        super().__init__(config, context)

        # Add dashboard sub-formats
        self.add_sub_format("dashboard")     # Full interactive dashboard
        self.add_sub_format("report")        # Static HTML report
        self.add_sub_format("summary")       # Summary page
        self.add_sub_format("trends")        # Trends and metrics view
        self.add_sub_format("embedded")      # Embeddable widget

    def get_format_type(self) -> str:
        return "html"

    def supports_feature(self, feature: str) -> bool:
        features = {
            "interactive": True,
            "charts": True,
            "filtering": True,
            "export": True,
            "responsive": True,
            "themes": True
        }
        return features.get(feature, False)

    def format(self, results: List[RuleResult], sub_format: str = "dashboard", **kwargs) -> Any:
        """Format results as HTML dashboard."""
        if sub_format == "dashboard":
            return self._format_dashboard(results, **kwargs)
        elif sub_format == "report":
            return self._format_report(results, **kwargs)
        elif sub_format == "summary":
            return self._format_summary(results, **kwargs)
        elif sub_format == "trends":
            return self._format_trends(results, **kwargs)
        elif sub_format == "embedded":
            return self._format_embedded(results, **kwargs)
        else:
            return self._format_dashboard(results, **kwargs)

    def _format_dashboard(self, results: List[RuleResult], **kwargs) -> Any:
        """Create full interactive dashboard."""
        filtered_results = self.filter_results(results)
        summary = self.create_summary(filtered_results)
        grouped = self.group_results(filtered_results)

        # Generate dashboard HTML
        html_content = self._create_dashboard_html(filtered_results, summary, grouped, **kwargs)
        return self.create_formatted_output(html_content)

    def _format_report(self, results: List[RuleResult], **kwargs) -> Any:
        """Create static HTML report."""
        filtered_results = self.filter_results(results)
        summary = self.create_summary(filtered_results)

        html_content = self._create_report_html(filtered_results, summary, **kwargs)
        return self.create_formatted_output(html_content)

    def _format_summary(self, results: List[RuleResult], **kwargs) -> Any:
        """Create summary page."""
        summary = self.create_summary(results)

        html_content = self._create_summary_html(summary, **kwargs)
        return self.create_formatted_output(html_content)

    def _format_trends(self, results: List[RuleResult], **kwargs) -> Any:
        """Create trends and metrics view."""
        summary = self.create_summary(results)
        metrics = self._calculate_dashboard_metrics(results, summary)

        html_content = self._create_trends_html(metrics, **kwargs)
        return self.create_formatted_output(html_content)

    def _format_embedded(self, results: List[RuleResult], **kwargs) -> Any:
        """Create embeddable widget."""
        summary = self.create_summary(results)

        html_content = self._create_embedded_widget(summary, **kwargs)
        return self.create_formatted_output(html_content)

    def _create_dashboard_html(self, results: List[RuleResult], summary: Dict[str, Any], grouped: Dict[str, Any], **kwargs) -> str:
        """Create the main dashboard HTML."""
        theme = kwargs.get('theme', 'default')
        title = kwargs.get('title', 'Code Review Dashboard')

        # Prepare data for JavaScript
        dashboard_data = {
            'summary': summary,
            'results': [self._result_to_dict(r) for r in results],
            'grouped': {
                'by_file': {k: [self._result_to_dict(r) for r in v] for k, v in grouped.get('by_file', {}).items()},
                'by_severity': {k: [self._result_to_dict(r) for r in v] for k, v in grouped.get('by_severity', {}).items()}
            },
            'metrics': self._calculate_dashboard_metrics(results, summary),
            'context': {
                'timestamp': self.context.timestamp.isoformat(),
                'analyzer_version': self.context.analyzer_version,
                'repository_url': self.context.repository_url,
                'files_analyzed': self.context.files_analyzed
            }
        }

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {self._get_css_styles(theme)}
    {self._get_chart_libraries()}
</head>
<body class="theme-{theme}">
    <div id="app">
        {self._create_header_section(summary)}

        <div class="container">
            {self._create_metrics_overview(summary)}

            <div class="dashboard-grid">
                <div class="chart-container">
                    <h3>Issues by Severity</h3>
                    <canvas id="severityChart"></canvas>
                </div>

                <div class="chart-container">
                    <h3>Issues by Category</h3>
                    <canvas id="categoryChart"></canvas>
                </div>

                <div class="chart-container span-2">
                    <h3>Files with Most Issues</h3>
                    <canvas id="filesChart"></canvas>
                </div>
            </div>

            {self._create_detailed_results_section()}

            {self._create_filters_section()}
        </div>
    </div>

    <script>
        const dashboardData = {json.dumps(dashboard_data, default=str, indent=2)};
    </script>
    {self._get_dashboard_javascript()}
</body>
</html>
        """

    def _create_report_html(self, results: List[RuleResult], summary: Dict[str, Any], **kwargs) -> str:
        """Create static HTML report."""
        title = kwargs.get('title', 'Code Review Report')

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {self._get_css_styles('report')}
</head>
<body>
    <div class="report-container">
        <header class="report-header">
            <h1>📊 {title}</h1>
            <div class="report-meta">
                <span>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                {f'<span>Repository: {self.context.repository_url}</span>' if self.context.repository_url else ''}
            </div>
        </header>

        <section class="executive-summary">
            <h2>Executive Summary</h2>
            {self._create_summary_cards(summary)}
            {self._create_summary_text(summary)}
        </section>

        {self._create_detailed_issues_html(results)}

        <footer class="report-footer">
            <p>Generated by Code Review Assistant v{self.context.analyzer_version}</p>
        </footer>
    </div>
</body>
</html>
        """

    def _create_summary_html(self, summary: Dict[str, Any], **kwargs) -> str:
        """Create summary page HTML."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Review Summary</title>
    {self._get_css_styles('summary')}
</head>
<body>
    <div class="summary-container">
        <h1>📈 Analysis Summary</h1>
        {self._create_summary_cards(summary)}
        {self._create_quick_stats_table(summary)}
    </div>
</body>
</html>
        """

    def _create_trends_html(self, metrics: Dict[str, Any], **kwargs) -> str:
        """Create trends view HTML."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Quality Trends</title>
    {self._get_css_styles('trends')}
    {self._get_chart_libraries()}
</head>
<body>
    <div class="trends-container">
        <h1>📈 Quality Trends & Metrics</h1>

        <div class="metrics-grid">
            {self._create_metric_cards(metrics)}
        </div>

        <div class="trends-charts">
            <div class="chart-container">
                <h3>Quality Score Trend</h3>
                <canvas id="qualityTrendChart"></canvas>
            </div>

            <div class="chart-container">
                <h3>Technical Debt</h3>
                <canvas id="debtChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        const metricsData = {json.dumps(metrics, default=str, indent=2)};
        {self._get_trends_javascript()}
    </script>
</body>
</html>
        """

    def _create_embedded_widget(self, summary: Dict[str, Any], **kwargs) -> str:
        """Create embeddable widget."""
        widget_type = kwargs.get('widget_type', 'badge')

        if widget_type == 'badge':
            return self._create_status_badge(summary)
        elif widget_type == 'mini_dashboard':
            return self._create_mini_dashboard(summary)
        else:
            return self._create_status_badge(summary)

    def _create_header_section(self, summary: Dict[str, Any]) -> str:
        """Create dashboard header."""
        total_issues = summary["total_issues"]

        if total_issues == 0:
            status_class = "status-success"
            status_text = "All Clear"
            status_icon = "✅"
        elif total_issues <= 5:
            status_class = "status-warning"
            status_text = "Minor Issues"
            status_icon = "⚠️"
        else:
            status_class = "status-error"
            status_text = "Needs Attention"
            status_icon = "❌"

        return f"""
        <header class="dashboard-header {status_class}">
            <div class="header-content">
                <div class="status-indicator">
                    <span class="status-icon">{status_icon}</span>
                    <span class="status-text">{status_text}</span>
                </div>
                <h1>Code Review Dashboard</h1>
                <div class="header-stats">
                    <span class="stat">
                        <strong>{summary['total_issues']}</strong> Issues
                    </span>
                    <span class="stat">
                        <strong>{summary['files_analyzed']}</strong> Files
                    </span>
                </div>
            </div>
        </header>
        """

    def _create_metrics_overview(self, summary: Dict[str, Any]) -> str:
        """Create metrics overview section."""
        return f"""
        <section class="metrics-overview">
            <div class="metric-card">
                <div class="metric-value">{summary['total_issues']}</div>
                <div class="metric-label">Total Issues</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{summary['files_with_issues']}</div>
                <div class="metric-label">Files with Issues</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{summary['clean_files']}</div>
                <div class="metric-label">Clean Files</div>
            </div>
            <div class="metric-card quality-score">
                <div class="metric-value">{self._calculate_quality_score(summary)}</div>
                <div class="metric-label">Quality Score</div>
            </div>
        </section>
        """

    def _create_detailed_results_section(self) -> str:
        """Create detailed results section."""
        return """
        <section class="detailed-results">
            <div class="section-header">
                <h2>Issues Details</h2>
                <div class="view-controls">
                    <button class="btn active" data-view="by-file">By File</button>
                    <button class="btn" data-view="by-severity">By Severity</button>
                    <button class="btn" data-view="by-category">By Category</button>
                </div>
            </div>
            <div id="resultsContainer" class="results-container">
                <!-- Results will be populated by JavaScript -->
            </div>
        </section>
        """

    def _create_filters_section(self) -> str:
        """Create filters section."""
        return """
        <section class="filters-section">
            <h3>Filters</h3>
            <div class="filter-controls">
                <div class="filter-group">
                    <label>Severity:</label>
                    <input type="checkbox" id="filter-error" value="error" checked>
                    <label for="filter-error">Error</label>
                    <input type="checkbox" id="filter-warning" value="warning" checked>
                    <label for="filter-warning">Warning</label>
                    <input type="checkbox" id="filter-suggestion" value="suggestion" checked>
                    <label for="filter-suggestion">Suggestion</label>
                    <input type="checkbox" id="filter-info" value="info" checked>
                    <label for="filter-info">Info</label>
                </div>
                <div class="filter-group">
                    <label>Search:</label>
                    <input type="text" id="search-filter" placeholder="Search issues...">
                </div>
            </div>
        </section>
        """

    def _create_summary_cards(self, summary: Dict[str, Any]) -> str:
        """Create summary cards."""
        return f"""
        <div class="summary-cards">
            <div class="card issues-card">
                <h3>Issues Found</h3>
                <div class="card-value">{summary['total_issues']}</div>
                <div class="card-subtitle">
                    {summary['files_with_issues']} files affected
                </div>
            </div>
            <div class="card quality-card">
                <h3>Quality Score</h3>
                <div class="card-value">{self._calculate_quality_score(summary)}</div>
                <div class="card-subtitle">Out of 100</div>
            </div>
            <div class="card files-card">
                <h3>Files Analyzed</h3>
                <div class="card-value">{summary['files_analyzed']}</div>
                <div class="card-subtitle">
                    {summary['clean_files']} clean files
                </div>
            </div>
        </div>
        """

    def _create_summary_text(self, summary: Dict[str, Any]) -> str:
        """Create summary text description."""
        total_issues = summary["total_issues"]

        if total_issues == 0:
            text = "🎉 Excellent! No issues were found in your code. Everything looks clean and follows best practices."
        elif total_issues <= 5:
            text = f"✅ Good job! Found only {total_issues} minor issues. These are mostly style improvements and best practice recommendations."
        elif total_issues <= 15:
            text = f"⚠️ Found {total_issues} issues that should be addressed. Most are manageable and can be fixed quickly."
        else:
            text = f"🔧 Found {total_issues} issues across your codebase. Prioritize fixing critical and high-severity issues first."

        return f'<div class="summary-text">{text}</div>'

    def _create_detailed_issues_html(self, results: List[RuleResult]) -> str:
        """Create detailed issues section for report."""
        if not results:
            return '<section class="no-issues"><h2>🎉 No Issues Found!</h2><p>Your code is clean and follows best practices.</p></section>'

        # Group by file
        by_file = {}
        for result in results:
            file_path = str(result.file_path)
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(result)

        html_sections = ['<section class="detailed-issues"><h2>Issues by File</h2>']

        for file_path, file_results in by_file.items():
            relative_path = self.format_file_path(file_path, self.context.repository_path)
            html_sections.append(f"""
            <div class="file-section">
                <h3>📄 {relative_path} ({len(file_results)} issues)</h3>
                <div class="file-issues">
            """)

            for result in sorted(file_results, key=self.get_issue_priority_score, reverse=True):
                severity_class = f"severity-{result.severity.value}"
                html_sections.append(f"""
                <div class="issue-item {severity_class}">
                    <div class="issue-header">
                        <span class="severity-badge">{result.severity.value.upper()}</span>
                        <span class="issue-message">{self.sanitize_text(result.message, 'html')}</span>
                        {f'<span class="line-number">Line {result.line_number}</span>' if result.line_number else ''}
                    </div>
                    <div class="issue-details">
                        <span class="rule-name">{result.checker_name}.{result.rule_name}</span>
                        {f'<div class="suggestion">💡 {self.sanitize_text(result.suggestion, "html")}</div>' if result.suggestion else ''}
                    </div>
                </div>
                """)

            html_sections.append('</div></div>')

        html_sections.append('</section>')
        return ''.join(html_sections)

    def _create_quick_stats_table(self, summary: Dict[str, Any]) -> str:
        """Create quick stats table."""
        rows = []

        severity_emojis = {"error": "🔴", "warning": "🟡", "suggestion": "🔵", "info": "⚪"}

        for severity, count in summary.get("severity_breakdown", {}).items():
            if count > 0:
                emoji = severity_emojis.get(severity, "⚪")
                rows.append(f"<tr><td>{emoji} {severity.title()}</td><td>{count}</td></tr>")

        return f"""
        <table class="stats-table">
            <thead>
                <tr><th>Metric</th><th>Count</th></tr>
            </thead>
            <tbody>
                <tr><td>📁 Files Analyzed</td><td>{summary['files_analyzed']}</td></tr>
                <tr><td>✅ Clean Files</td><td>{summary['clean_files']}</td></tr>
                <tr><td>⚠️ Files with Issues</td><td>{summary['files_with_issues']}</td></tr>
                {''.join(rows)}
            </tbody>
        </table>
        """

    def _create_metric_cards(self, metrics: Dict[str, Any]) -> str:
        """Create metric cards for trends page."""
        quality_metrics = metrics.get('code_quality', {})

        return f"""
        <div class="metric-card">
            <h3>Quality Score</h3>
            <div class="big-number">{quality_metrics.get('quality_score', 0)}</div>
        </div>
        <div class="metric-card">
            <h3>Issues per File</h3>
            <div class="big-number">{quality_metrics.get('issues_per_file', 0)}</div>
        </div>
        <div class="metric-card">
            <h3>Clean File Ratio</h3>
            <div class="big-number">{quality_metrics.get('clean_file_ratio', 0)}%</div>
        </div>
        <div class="metric-card">
            <h3>Technical Debt</h3>
            <div class="big-number">{metrics.get('technical_debt', {}).get('total_debt_hours', 0)}h</div>
        </div>
        """

    def _create_status_badge(self, summary: Dict[str, Any]) -> str:
        """Create status badge widget."""
        total_issues = summary["total_issues"]

        if total_issues == 0:
            color = "green"
            text = "Clean"
        elif total_issues <= 5:
            color = "yellow"
            text = f"{total_issues} Issues"
        else:
            color = "red"
            text = f"{total_issues} Issues"

        return f"""
        <div class="code-review-badge" style="background-color: {color}; color: white; padding: 8px 12px; border-radius: 4px; font-weight: bold; display: inline-block;">
            Code Review: {text}
        </div>
        """

    def _create_mini_dashboard(self, summary: Dict[str, Any]) -> str:
        """Create mini dashboard widget."""
        return f"""
        <div class="mini-dashboard" style="border: 1px solid #ddd; padding: 16px; border-radius: 8px; max-width: 300px;">
            <h4>Code Review Summary</h4>
            <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                <span>Issues:</span>
                <strong>{summary['total_issues']}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                <span>Files:</span>
                <strong>{summary['files_analyzed']}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin: 8px 0;">
                <span>Quality:</span>
                <strong>{self._calculate_quality_score(summary)}/100</strong>
            </div>
        </div>
        """

    def _get_css_styles(self, theme: str) -> str:
        """Get CSS styles for the theme."""
        return f"""
        <style>
        {self._get_base_styles()}
        {self._get_theme_styles(theme)}
        </style>
        """

    def _get_base_styles(self) -> str:
        """Get base CSS styles."""
        return """
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .dashboard-header { padding: 20px 0; text-align: center; }
        .status-success { background: linear-gradient(135deg, #28a745, #20c997); color: white; }
        .status-warning { background: linear-gradient(135deg, #ffc107, #fd7e14); color: white; }
        .status-error { background: linear-gradient(135deg, #dc3545, #e83e8c); color: white; }
        .metrics-overview { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #333; }
        .metric-label { font-size: 0.9em; color: #666; margin-top: 5px; }
        .dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin: 20px 0; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .span-2 { grid-column: span 2; }
        .btn { padding: 8px 16px; border: 1px solid #ddd; background: white; border-radius: 4px; cursor: pointer; }
        .btn.active { background: #007bff; color: white; }
        .summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card-value { font-size: 2.5em; font-weight: bold; margin: 10px 0; }
        .issue-item { border-left: 4px solid #ddd; padding: 12px; margin: 8px 0; background: #f8f9fa; }
        .severity-error { border-left-color: #dc3545; }
        .severity-warning { border-left-color: #ffc107; }
        .severity-suggestion { border-left-color: #17a2b8; }
        .severity-info { border-left-color: #6c757d; }
        .severity-badge { padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
        .stats-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .stats-table th, .stats-table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        .stats-table th { background: #f8f9fa; }
        """

    def _get_theme_styles(self, theme: str) -> str:
        """Get theme-specific styles."""
        themes = {
            'default': """
            body { background: #f5f5f5; }
            .dashboard-header { background: #fff; border-bottom: 1px solid #ddd; }
            """,
            'dark': """
            body { background: #1a1a1a; color: #fff; }
            .metric-card, .chart-container, .card { background: #2d2d2d; }
            .dashboard-header { background: #333; }
            """,
            'report': """
            body { background: #fff; }
            .report-container { max-width: 1000px; margin: 0 auto; padding: 40px; }
            .report-header { border-bottom: 2px solid #ddd; padding-bottom: 20px; margin-bottom: 30px; }
            """
        }
        return themes.get(theme, themes['default'])

    def _get_chart_libraries(self) -> str:
        """Get chart library scripts."""
        return """
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        """

    def _get_dashboard_javascript(self) -> str:
        """Get dashboard JavaScript."""
        return """
        <script>
        // Dashboard initialization and chart creation
        document.addEventListener('DOMContentLoaded', function() {
            initializeCharts();
            initializeFilters();
            initializeViewControls();
        });

        function initializeCharts() {
            createSeverityChart();
            createCategoryChart();
            createFilesChart();
        }

        function createSeverityChart() {
            const ctx = document.getElementById('severityChart').getContext('2d');
            const severityData = dashboardData.summary.severity_breakdown;

            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(severityData),
                    datasets: [{
                        data: Object.values(severityData),
                        backgroundColor: ['#dc3545', '#ffc107', '#17a2b8', '#6c757d']
                    }]
                }
            });
        }

        function createCategoryChart() {
            const ctx = document.getElementById('categoryChart').getContext('2d');
            const categoryData = {};

            dashboardData.results.forEach(result => {
                const category = result.checker_name;
                categoryData[category] = (categoryData[category] || 0) + 1;
            });

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: Object.keys(categoryData),
                    datasets: [{
                        label: 'Issues',
                        data: Object.values(categoryData),
                        backgroundColor: '#007bff'
                    }]
                }
            });
        }

        function createFilesChart() {
            const ctx = document.getElementById('filesChart').getContext('2d');
            const fileData = {};

            dashboardData.results.forEach(result => {
                const file = result.file_path.split('/').pop();
                fileData[file] = (fileData[file] || 0) + 1;
            });

            // Top 10 files
            const sortedFiles = Object.entries(fileData)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10);

            new Chart(ctx, {
                type: 'horizontalBar',
                data: {
                    labels: sortedFiles.map(f => f[0]),
                    datasets: [{
                        label: 'Issues',
                        data: sortedFiles.map(f => f[1]),
                        backgroundColor: '#28a745'
                    }]
                }
            });
        }

        function initializeFilters() {
            const filterInputs = document.querySelectorAll('input[type="checkbox"]');
            const searchInput = document.getElementById('search-filter');

            filterInputs.forEach(input => {
                input.addEventListener('change', applyFilters);
            });

            searchInput.addEventListener('input', applyFilters);
        }

        function initializeViewControls() {
            const viewButtons = document.querySelectorAll('.btn[data-view]');
            viewButtons.forEach(button => {
                button.addEventListener('click', function() {
                    viewButtons.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    updateResultsView(this.dataset.view);
                });
            });

            updateResultsView('by-file');
        }

        function applyFilters() {
            // Filter implementation
            updateResultsView(document.querySelector('.btn.active').dataset.view);
        }

        function updateResultsView(view) {
            const container = document.getElementById('resultsContainer');
            let html = '';

            if (view === 'by-file') {
                const grouped = dashboardData.grouped.by_file;
                for (const [file, results] of Object.entries(grouped)) {
                    html += `<div class="file-group">
                        <h4>${file} (${results.length} issues)</h4>
                        ${results.map(r => createIssueHTML(r)).join('')}
                    </div>`;
                }
            } else if (view === 'by-severity') {
                const grouped = dashboardData.grouped.by_severity;
                for (const [severity, results] of Object.entries(grouped)) {
                    if (results.length > 0) {
                        html += `<div class="severity-group">
                            <h4>${severity.toUpperCase()} (${results.length} issues)</h4>
                            ${results.map(r => createIssueHTML(r)).join('')}
                        </div>`;
                    }
                }
            }

            container.innerHTML = html;
        }

        function createIssueHTML(result) {
            return `<div class="issue-item severity-${result.severity}">
                <div class="issue-header">
                    <span class="severity-badge">${result.severity.toUpperCase()}</span>
                    <span class="issue-message">${result.message}</span>
                    ${result.line_number ? `<span class="line-number">Line ${result.line_number}</span>` : ''}
                </div>
                <div class="issue-details">
                    <span class="rule-name">${result.checker_name}.${result.rule_name}</span>
                    ${result.suggestion ? `<div class="suggestion">💡 ${result.suggestion}</div>` : ''}
                </div>
            </div>`;
        }
        </script>
        """

    def _get_trends_javascript(self) -> str:
        """Get trends page JavaScript."""
        return """
        // Trends chart initialization
        // Implementation would create trend charts based on historical data
        """

    def _calculate_dashboard_metrics(self, results: List[RuleResult], summary: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metrics for dashboard."""
        return {
            'code_quality': {
                'quality_score': self._calculate_quality_score(summary),
                'issues_per_file': round(summary['total_issues'] / (summary['files_analyzed'] or 1), 2),
                'clean_file_ratio': round(summary['clean_files'] / (summary['files_analyzed'] or 1) * 100, 1)
            },
            'technical_debt': {
                'total_debt_hours': self._estimate_debt_hours(results),
                'debt_per_file': round(self._estimate_debt_hours(results) / (summary['files_analyzed'] or 1), 1)
            },
            'security': {
                'security_issues': len([r for r in results if 'security' in r.checker_name.lower()])
            }
        }

    def _calculate_quality_score(self, summary: Dict[str, Any]) -> int:
        """Calculate overall quality score (0-100)."""
        total_issues = summary["total_issues"]
        if total_issues == 0:
            return 100

        # Simple scoring algorithm
        base_score = 100
        penalty_per_error = 10
        penalty_per_warning = 5
        penalty_per_suggestion = 2

        score = base_score
        for severity, count in summary["severity_breakdown"].items():
            if severity == "error":
                score -= count * penalty_per_error
            elif severity == "warning":
                score -= count * penalty_per_warning
            elif severity == "suggestion":
                score -= count * penalty_per_suggestion

        return max(0, min(100, score))

    def _estimate_debt_hours(self, results: List[RuleResult]) -> float:
        """Estimate technical debt in hours."""
        effort_map = {"error": 0.5, "warning": 0.25, "suggestion": 0.1, "info": 0.05}
        total_hours = sum(effort_map.get(r.severity.value, 0.05) for r in results)
        return round(total_hours, 1)

    def _result_to_dict(self, result: RuleResult) -> Dict[str, Any]:
        """Convert RuleResult to dictionary for JSON serialization."""
        return {
            "rule_name": result.rule_name,
            "checker_name": result.checker_name,
            "severity": result.severity.value,
            "message": result.message,
            "file_path": str(result.file_path),
            "line_number": result.line_number,
            "column": result.column,
            "suggestion": result.suggestion
        }