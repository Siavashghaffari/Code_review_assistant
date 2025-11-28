"""
Notification System

Comprehensive notification system for Slack, Microsoft Teams, Discord,
email, and webhook integrations.
"""

import json
import asyncio
import smtplib
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import aiohttp

from .base import BaseFormatter, FormatterConfig, OutputContext
from ..config.rule_engine import RuleResult
from ..utils.logger import get_logger


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    enabled: bool = True
    webhook_url: Optional[str] = None
    email_config: Dict[str, str] = field(default_factory=dict)
    mention_users: List[str] = field(default_factory=list)
    mention_channels: List[str] = field(default_factory=list)
    severity_threshold: str = "warning"  # Only notify for this severity and above
    max_issues_in_notification: int = 10
    include_suggestions: bool = True
    include_metrics: bool = True
    custom_message: Optional[str] = None
    template_path: Optional[Path] = None


class NotificationManager:
    """Manages all notification integrations."""

    def __init__(self, config: NotificationConfig = None):
        self.config = config or NotificationConfig()
        self.logger = get_logger(__name__)
        self.formatters = {
            'slack': SlackNotifier(self.config),
            'teams': TeamsNotifier(self.config),
            'discord': DiscordNotifier(self.config),
            'email': EmailNotifier(self.config),
            'webhook': WebhookNotifier(self.config)
        }

    async def send_notifications(self, results: List[RuleResult], context: OutputContext,
                               platforms: List[str], **kwargs) -> Dict[str, Dict[str, Any]]:
        """Send notifications to specified platforms."""
        if not self.config.enabled:
            self.logger.info("Notifications disabled")
            return {}

        # Filter results by severity
        filtered_results = self._filter_by_severity(results)
        if not filtered_results:
            self.logger.info("No issues meet severity threshold for notifications")
            return {}

        notification_results = {}

        # Send to each platform
        for platform in platforms:
            if platform in self.formatters:
                try:
                    result = await self.formatters[platform].send(filtered_results, context, **kwargs)
                    notification_results[platform] = result
                    self.logger.info(f"Notification sent to {platform}")
                except Exception as e:
                    self.logger.error(f"Failed to send notification to {platform}: {e}")
                    notification_results[platform] = {"success": False, "error": str(e)}
            else:
                self.logger.warning(f"Unknown platform: {platform}")

        return notification_results

    def _filter_by_severity(self, results: List[RuleResult]) -> List[RuleResult]:
        """Filter results by severity threshold."""
        severity_order = {"info": 0, "suggestion": 1, "warning": 2, "error": 3}
        threshold = severity_order.get(self.config.severity_threshold, 2)

        return [
            r for r in results
            if severity_order.get(r.severity.value, 0) >= threshold
        ]


class BaseNotifier:
    """Base class for all notification providers."""

    def __init__(self, config: NotificationConfig):
        self.config = config
        self.logger = get_logger(__name__)

    async def send(self, results: List[RuleResult], context: OutputContext, **kwargs) -> Dict[str, Any]:
        """Send notification."""
        raise NotImplementedError

    def create_summary(self, results: List[RuleResult]) -> Dict[str, Any]:
        """Create summary for notifications."""
        if not results:
            return {"total_issues": 0, "severity_breakdown": {}}

        severity_counts = {}
        for result in results:
            severity = result.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return {
            "total_issues": len(results),
            "severity_breakdown": severity_counts,
            "files_affected": len(set(str(r.file_path) for r in results))
        }

    def format_mentions(self, mentions: List[str]) -> str:
        """Format mentions for the platform."""
        return " ".join(f"@{mention}" for mention in mentions)

    def truncate_issues(self, results: List[RuleResult]) -> List[RuleResult]:
        """Truncate issues list for notification."""
        max_issues = self.config.max_issues_in_notification
        if len(results) <= max_issues:
            return results

        # Prioritize by severity
        priority_results = sorted(results, key=lambda r: {
            "error": 4, "warning": 3, "suggestion": 2, "info": 1
        }.get(r.severity.value, 0), reverse=True)

        return priority_results[:max_issues]


class SlackNotifier(BaseNotifier):
    """Slack notification provider."""

    async def send(self, results: List[RuleResult], context: OutputContext, **kwargs) -> Dict[str, Any]:
        """Send Slack notification."""
        if not self.config.webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        summary = self.create_summary(results)
        truncated_results = self.truncate_issues(results)

        # Create Slack message
        message = self._create_slack_message(truncated_results, summary, context)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.webhook_url, json=message) as response:
                    if response.status == 200:
                        return {"success": True, "platform": "slack"}
                    else:
                        error_text = await response.text()
                        return {"success": False, "error": f"HTTP {response.status}: {error_text}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_slack_message(self, results: List[RuleResult], summary: Dict[str, Any],
                            context: OutputContext) -> Dict[str, Any]:
        """Create Slack message payload."""
        total_issues = summary["total_issues"]

        # Determine overall status and color
        if total_issues == 0:
            color = "good"
            title = ":white_check_mark: Code Review: All Clear"
        elif total_issues <= 5:
            color = "warning"
            title = f":warning: Code Review: {total_issues} Issues Found"
        else:
            color = "danger"
            title = f":x: Code Review: {total_issues} Issues Need Attention"

        # Main attachment
        attachment = {
            "color": color,
            "title": title,
            "fields": []
        }

        # Add summary fields
        if summary["files_affected"]:
            attachment["fields"].append({
                "title": "Files Affected",
                "value": str(summary["files_affected"]),
                "short": True
            })

        # Add severity breakdown
        if summary["severity_breakdown"]:
            severity_text = []
            emojis = {"error": ":red_circle:", "warning": ":yellow_circle:",
                     "suggestion": ":blue_circle:", "info": ":white_circle:"}

            for severity, count in summary["severity_breakdown"].items():
                emoji = emojis.get(severity, ":white_circle:")
                severity_text.append(f"{emoji} {count} {severity}")

            attachment["fields"].append({
                "title": "By Severity",
                "value": " | ".join(severity_text),
                "short": False
            })

        # Add repository info
        if context.repository_url:
            attachment["fields"].append({
                "title": "Repository",
                "value": f"<{context.repository_url}|View Repository>",
                "short": True
            })

        if context.git_range:
            attachment["fields"].append({
                "title": "Git Range",
                "value": f"`{context.git_range}`",
                "short": True
            })

        message = {
            "text": self._create_message_text(summary, context),
            "attachments": [attachment]
        }

        # Add top issues if any
        if results:
            issues_attachment = self._create_issues_attachment(results[:3])  # Top 3
            message["attachments"].append(issues_attachment)

        # Add mentions
        if self.config.mention_users:
            mentions = self.format_mentions(self.config.mention_users)
            message["text"] += f" {mentions}"

        return message

    def _create_message_text(self, summary: Dict[str, Any], context: OutputContext) -> str:
        """Create main message text."""
        if self.config.custom_message:
            return self.config.custom_message

        total_issues = summary["total_issues"]
        if total_issues == 0:
            return "🎉 Code review completed successfully - no issues found!"
        else:
            return f"📋 Code review completed with {total_issues} issues requiring attention."

    def _create_issues_attachment(self, results: List[RuleResult]) -> Dict[str, Any]:
        """Create attachment with top issues."""
        fields = []

        for i, result in enumerate(results, 1):
            severity_emoji = {"error": ":red_circle:", "warning": ":yellow_circle:",
                            "suggestion": ":blue_circle:", "info": ":white_circle:"}.get(
                                result.severity.value, ":white_circle:")

            file_path = Path(result.file_path).name  # Just filename
            location = f" (line {result.line_number})" if result.line_number else ""

            fields.append({
                "title": f"{severity_emoji} Issue #{i}",
                "value": f"{result.message}\n*{file_path}*{location}",
                "short": False
            })

        return {
            "color": "#36a64f",
            "title": "Top Issues",
            "fields": fields
        }


class TeamsNotifier(BaseNotifier):
    """Microsoft Teams notification provider."""

    async def send(self, results: List[RuleResult], context: OutputContext, **kwargs) -> Dict[str, Any]:
        """Send Teams notification."""
        if not self.config.webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        summary = self.create_summary(results)
        truncated_results = self.truncate_issues(results)

        # Create Teams adaptive card
        card = self._create_teams_card(truncated_results, summary, context)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.webhook_url, json=card) as response:
                    if response.status == 200:
                        return {"success": True, "platform": "teams"}
                    else:
                        error_text = await response.text()
                        return {"success": False, "error": f"HTTP {response.status}: {error_text}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_teams_card(self, results: List[RuleResult], summary: Dict[str, Any],
                          context: OutputContext) -> Dict[str, Any]:
        """Create Teams adaptive card."""
        total_issues = summary["total_issues"]

        # Determine theme color
        if total_issues == 0:
            theme_color = "28a745"  # Green
            title = "✅ Code Review: All Clear"
        elif total_issues <= 5:
            theme_color = "ffc107"  # Yellow
            title = f"⚠️ Code Review: {total_issues} Issues Found"
        else:
            theme_color = "dc3545"  # Red
            title = f"❌ Code Review: {total_issues} Issues Need Attention"

        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": theme_color,
            "summary": title,
            "sections": [
                {
                    "activityTitle": title,
                    "activitySubtitle": f"Analysis completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "facts": self._create_teams_facts(summary, context),
                    "markdown": True
                }
            ]
        }

        # Add issues section if any
        if results:
            card["sections"].append({
                "title": "Top Issues",
                "text": self._create_teams_issues_text(results[:5])  # Top 5
            })

        # Add potential actions
        actions = []
        if context.repository_url:
            actions.append({
                "@type": "OpenUri",
                "name": "View Repository",
                "targets": [{
                    "os": "default",
                    "uri": context.repository_url
                }]
            })

        if actions:
            card["potentialAction"] = actions

        return card

    def _create_teams_facts(self, summary: Dict[str, Any], context: OutputContext) -> List[Dict[str, str]]:
        """Create facts section for Teams card."""
        facts = [
            {"name": "Total Issues", "value": str(summary["total_issues"])},
            {"name": "Files Affected", "value": str(summary.get("files_affected", 0))}
        ]

        if context.git_range:
            facts.append({"name": "Git Range", "value": context.git_range})

        if context.files_analyzed:
            facts.append({"name": "Files Analyzed", "value": str(context.files_analyzed)})

        # Add severity breakdown
        if summary["severity_breakdown"]:
            for severity, count in summary["severity_breakdown"].items():
                if count > 0:
                    facts.append({"name": f"{severity.title()} Issues", "value": str(count)})

        return facts

    def _create_teams_issues_text(self, results: List[RuleResult]) -> str:
        """Create issues text for Teams."""
        if not results:
            return "No issues found! 🎉"

        lines = []
        for i, result in enumerate(results, 1):
            severity_emoji = {"error": "🔴", "warning": "🟡", "suggestion": "🔵", "info": "⚪"}.get(
                result.severity.value, "⚪")

            file_name = Path(result.file_path).name
            location = f" (line {result.line_number})" if result.line_number else ""

            lines.append(f"{i}. {severity_emoji} **{result.message}**")
            lines.append(f"   📄 {file_name}{location}")
            lines.append("")

        return "\n".join(lines)


class DiscordNotifier(BaseNotifier):
    """Discord notification provider."""

    async def send(self, results: List[RuleResult], context: OutputContext, **kwargs) -> Dict[str, Any]:
        """Send Discord notification."""
        if not self.config.webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        summary = self.create_summary(results)
        truncated_results = self.truncate_issues(results)

        # Create Discord embed
        embed = self._create_discord_embed(truncated_results, summary, context)

        message = {"embeds": [embed]}

        # Add mentions
        if self.config.mention_users:
            message["content"] = self.format_mentions(self.config.mention_users)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.webhook_url, json=message) as response:
                    if response.status == 204:  # Discord returns 204 for success
                        return {"success": True, "platform": "discord"}
                    else:
                        error_text = await response.text()
                        return {"success": False, "error": f"HTTP {response.status}: {error_text}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_discord_embed(self, results: List[RuleResult], summary: Dict[str, Any],
                            context: OutputContext) -> Dict[str, Any]:
        """Create Discord embed."""
        total_issues = summary["total_issues"]

        # Determine color
        if total_issues == 0:
            color = 0x28a745  # Green
            title = "✅ Code Review: All Clear"
        elif total_issues <= 5:
            color = 0xffc107  # Yellow
            title = f"⚠️ Code Review: {total_issues} Issues Found"
        else:
            color = 0xdc3545  # Red
            title = f"❌ Code Review: {total_issues} Issues Need Attention"

        embed = {
            "title": title,
            "color": color,
            "timestamp": datetime.now().isoformat(),
            "fields": []
        }

        # Add summary fields
        embed["fields"].append({
            "name": "📊 Summary",
            "value": f"**Total Issues:** {total_issues}\n**Files Affected:** {summary.get('files_affected', 0)}",
            "inline": True
        })

        # Add severity breakdown
        if summary["severity_breakdown"]:
            severity_text = []
            emojis = {"error": "🔴", "warning": "🟡", "suggestion": "🔵", "info": "⚪"}

            for severity, count in summary["severity_breakdown"].items():
                emoji = emojis.get(severity, "⚪")
                severity_text.append(f"{emoji} {count} {severity}")

            embed["fields"].append({
                "name": "🎯 By Severity",
                "value": "\n".join(severity_text),
                "inline": True
            })

        # Add repository info
        if context.repository_url:
            embed["fields"].append({
                "name": "🔗 Repository",
                "value": f"[View Repository]({context.repository_url})",
                "inline": True
            })

        # Add top issues
        if results:
            issues_text = []
            for i, result in enumerate(results[:3], 1):
                severity_emoji = emojis.get(result.severity.value, "⚪")
                file_name = Path(result.file_path).name
                location = f" (line {result.line_number})" if result.line_number else ""

                issues_text.append(f"{i}. {severity_emoji} {result.message}")
                issues_text.append(f"   📄 `{file_name}`{location}")

            if issues_text:
                embed["fields"].append({
                    "name": "🐛 Top Issues",
                    "value": "\n".join(issues_text),
                    "inline": False
                })

        # Add footer
        embed["footer"] = {
            "text": f"Code Review Assistant v{context.analyzer_version}",
            "icon_url": "https://example.com/icon.png"  # Optional icon
        }

        return embed


class EmailNotifier(BaseNotifier):
    """Email notification provider."""

    async def send(self, results: List[RuleResult], context: OutputContext, **kwargs) -> Dict[str, Any]:
        """Send email notification."""
        email_config = self.config.email_config

        required_fields = ['smtp_server', 'smtp_port', 'username', 'password', 'from_email', 'to_emails']
        if not all(field in email_config for field in required_fields):
            return {"success": False, "error": "Incomplete email configuration"}

        summary = self.create_summary(results)
        truncated_results = self.truncate_issues(results)

        # Create email
        subject, body = self._create_email_content(truncated_results, summary, context)

        try:
            # Send email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = email_config['from_email']
            msg['To'] = ', '.join(email_config['to_emails'])

            # Add HTML version
            html_part = MIMEText(body, 'html')
            msg.attach(html_part)

            # Send via SMTP
            with smtplib.SMTP(email_config['smtp_server'], int(email_config['smtp_port'])) as server:
                server.starttls()
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)

            return {"success": True, "platform": "email", "recipients": len(email_config['to_emails'])}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_email_content(self, results: List[RuleResult], summary: Dict[str, Any],
                            context: OutputContext) -> tuple:
        """Create email subject and body."""
        total_issues = summary["total_issues"]

        # Subject
        if total_issues == 0:
            subject = "✅ Code Review: All Clear"
        elif total_issues <= 5:
            subject = f"⚠️ Code Review: {total_issues} Issues Found"
        else:
            subject = f"❌ Code Review: {total_issues} Issues Need Attention"

        # HTML Body
        body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background: #f8f9fa; padding: 20px; border-radius: 5px; }}
                .summary {{ margin: 20px 0; }}
                .issue {{ border-left: 4px solid #ddd; padding: 10px; margin: 10px 0; }}
                .error {{ border-left-color: #dc3545; }}
                .warning {{ border-left-color: #ffc107; }}
                .suggestion {{ border-left-color: #17a2b8; }}
                .info {{ border-left-color: #6c757d; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{subject}</h2>
                <p>Analysis completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                {f'<p><strong>Repository:</strong> {context.repository_url}</p>' if context.repository_url else ''}
                {f'<p><strong>Git Range:</strong> {context.git_range}</p>' if context.git_range else ''}
            </div>

            <div class="summary">
                <h3>📊 Summary</h3>
                <ul>
                    <li><strong>Total Issues:</strong> {total_issues}</li>
                    <li><strong>Files Affected:</strong> {summary.get('files_affected', 0)}</li>
                    <li><strong>Files Analyzed:</strong> {context.files_analyzed or 0}</li>
                </ul>
        """

        # Add severity breakdown
        if summary["severity_breakdown"]:
            body += "<h4>By Severity:</h4><ul>"
            for severity, count in summary["severity_breakdown"].items():
                if count > 0:
                    body += f"<li><strong>{severity.title()}:</strong> {count}</li>"
            body += "</ul>"

        body += "</div>"

        # Add issues
        if results:
            body += '<div class="issues"><h3>🐛 Issues</h3>'
            for result in results:
                severity_class = result.severity.value
                file_name = Path(result.file_path).name
                location = f" (line {result.line_number})" if result.line_number else ""

                body += f'''
                <div class="issue {severity_class}">
                    <strong>{result.severity.value.upper()}:</strong> {result.message}<br>
                    <em>📄 {file_name}{location}</em><br>
                    <small>Rule: {result.checker_name}.{result.rule_name}</small>
                    {f'<br><strong>💡 Suggestion:</strong> {result.suggestion}' if result.suggestion else ''}
                </div>
                '''
            body += "</div>"

        body += f"""
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
                <p><small>Generated by Code Review Assistant v{context.analyzer_version}</small></p>
            </div>
        </body>
        </html>
        """

        return subject, body


class WebhookNotifier(BaseNotifier):
    """Generic webhook notification provider."""

    async def send(self, results: List[RuleResult], context: OutputContext, **kwargs) -> Dict[str, Any]:
        """Send webhook notification."""
        if not self.config.webhook_url:
            return {"success": False, "error": "No webhook URL configured"}

        summary = self.create_summary(results)
        truncated_results = self.truncate_issues(results)

        # Create generic payload
        payload = {
            "timestamp": datetime.now().isoformat(),
            "event": "code_review_completed",
            "summary": summary,
            "context": {
                "repository_url": context.repository_url,
                "git_range": context.git_range,
                "files_analyzed": context.files_analyzed,
                "analyzer_version": context.analyzer_version
            },
            "issues": [
                {
                    "severity": result.severity.value,
                    "message": result.message,
                    "file_path": str(result.file_path),
                    "line_number": result.line_number,
                    "rule": f"{result.checker_name}.{result.rule_name}",
                    "suggestion": result.suggestion
                }
                for result in truncated_results
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.webhook_url, json=payload) as response:
                    if response.status in [200, 201, 202, 204]:
                        return {"success": True, "platform": "webhook"}
                    else:
                        error_text = await response.text()
                        return {"success": False, "error": f"HTTP {response.status}: {error_text}"}

        except Exception as e:
            return {"success": False, "error": str(e)}