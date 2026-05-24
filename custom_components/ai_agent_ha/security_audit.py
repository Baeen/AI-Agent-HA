"""Security audit assistant for Home Assistant.

This module audits automations and configurations for security issues,
checks for exposed credentials, identifies permissive configurations,
and scans for infinite loops.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class SecurityIssue:
    """Represents a security issue found during audit."""

    def __init__(
        self,
        issue_type: str,
        severity: str,
        description: str,
        recommendation: str,
        affected_entity: str = "",
        evidence: str = "",
    ):
        self.issue_type = issue_type
        self.severity = severity  # critical, high, medium, low, info
        self.description = description
        self.recommendation = recommendation
        self.affected_entity = affected_entity
        self.evidence = evidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "description": self.description,
            "recommendation": self.recommendation,
            "affected_entity": self.affected_entity,
            "evidence": self.evidence,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [
            f"### [{self.severity.upper()}] {self.issue_type}",
            "",
            f"**Affected:** `{self.affected_entity}`" if self.affected_entity else "",
            "",
            self.description,
            "",
        ]
        if self.evidence:
            lines.append("**Evidence:**")
            lines.append("```")
            lines.append(self.evidence)
            lines.append("```")
            lines.append("")
        lines.append("**Recommendation:**")
        lines.append(f"{self.recommendation}")
        lines.append("")
        return "\n".join(lines)


class SecurityAuditResult:
    """Result of a security audit."""

    def __init__(
        self,
        issues: List[SecurityIssue] = None,
        score: float = 1.0,
        summary: Dict = None,
    ):
        self.issues = issues or []
        self.score = score
        self.summary = summary or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "issues": [issue.to_dict() for issue in self.issues],
            "score": self.score,
            "summary": self.summary,
            "timestamp": datetime.now().isoformat(),
            "total_issues": len(self.issues),
            "critical_issues": sum(1 for i in self.issues if i.severity == "critical"),
            "high_issues": sum(1 for i in self.issues if i.severity == "high"),
            "medium_issues": sum(1 for i in self.issues if i.severity == "medium"),
            "low_issues": sum(1 for i in self.issues if i.severity == "low"),
            "info_issues": sum(1 for i in self.issues if i.severity == "info"),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        dict_repr = self.to_dict()
        lines = [
            "# Security Audit Report",
            "",
            f"**Security Score:** {self.score:.1f}/100",
            "",
            f"**Total Issues:** {dict_repr['total_issues']}",
            "",
            f"- 🔴 Critical: {dict_repr['critical_issues']}",
            f"- 🟠 High: {dict_repr['high_issues']}",
            f"- 🟡 Medium: {dict_repr['medium_issues']}",
            f"- 🟢 Low: {dict_repr['low_issues']}",
            f"- 🔵 Info: {dict_repr['info_issues']}",
            "",
            "---",
            "",
        ]
        if self.issues:
            lines.append("## Detailed Findings")
            lines.append("")
            for issue in self.issues:
                lines.append(issue.to_markdown())
        else:
            lines.append("## No Issues Found")
            lines.append("")
            lines.append("No security issues were detected.")
            lines.append("")
        return "\n".join(lines)


class SecurityAuditor:
    """Audits Home Assistant configurations for security issues."""

    # Patterns that indicate exposed credentials
    CREDENTIAL_PATTERNS = [
        (r'password\s*[:=]\s*["\']([^"\']+)["\']', 'Hardcoded password detected'),
        (r'api_key\s*[:=]\s*["\']([^"\']+)["\']', 'Hardcoded API key detected'),
        (r'api_token\s*[:=]\s*["\']([^"\']+)["\']', 'Hardcoded API token detected'),
        (r'token\s*[:=]\s*["\']([^"\']+)["\']', 'Hardcoded token detected'),
        (r'secret\s*[:=]\s*["\']([^"\']+)["\']', 'Hardcoded secret detected'),
        (r'access_key\s*[:=]\s*["\']([^"\']+)["\']', 'Hardcoded access key detected'),
    ]

    # API key format validation patterns - detects known credential formats
    API_KEY_FORMAT_PATTERNS = [
        (
            r'ghp_[A-Za-z0-9]{36}',
            'GitHub Personal Access Token detected',
            'GitHub tokens should be stored using secrets! or in .secrets file. Use !secret in your configuration.',
        ),
        (
            r'gho_[A-Za-z0-9]{36}',
            'GitHub OAuth Access Token detected',
            'GitHub OAuth tokens should be stored using secrets! or in .secrets file.',
        ),
        (
            r'github_pat_[A-Za-z0-9_]{82}',
            'GitHub Fine-Grained Personal Access Token detected',
            'GitHub fine-grained tokens should be stored using secrets! or in .secrets file.',
        ),
        (
            r'AKIA[0-9A-Z]{16}',
            'AWS Access Key ID detected',
            'AWS keys should be stored using environment variables or secrets manager. Never hardcode AWS credentials.',
        ),
        (
            r'[A-Za-z0-9/+=]{40}',
            'Potential AWS Secret Access Key detected (base64 format)',
            'AWS secret keys should be stored using environment variables or secrets manager.',
        ),
        (
            r'sk-[A-Za-z0-9]{48}',
            'OpenAI API Secret Key detected',
            'OpenAI API keys should be stored using secrets! or environment variables.',
        ),
        (
            r'sk-proj-[A-Za-z0-9]{48}',
            'OpenAI Project Secret Key detected',
            'OpenAI project keys should be stored using secrets! or environment variables.',
        ),
        (
            r'SK[A-Za-z0-9]{63}',
            'Stripe Secret Key detected',
            'Stripe keys should never be hardcoded. Use environment variables or secrets manager.',
        ),
        (
            r'rk_[A-Za-z0-9]{48}',
            'Replicate API Key detected',
            'Replicate API keys should be stored using secrets! or environment variables.',
        ),
        (
            r'glc_[A-Za-z0-9]{48}',
            'Gleam Cloud API Token detected',
            'Gleam Cloud tokens should be stored using secrets! or environment variables.',
        ),
        (
            r'EAAB[0-9a-zA-Z]{20,}',
            'Facebook Access Token detected',
            'Facebook tokens should be stored using secrets! or environment variables.',
        ),
        (
            r'ya29\.[A-Za-z0-9_-]{20,}',
            'Google OAuth 2.0 Refresh Token detected',
            'Google tokens should be stored using secrets! or environment variables.',
        ),
        (
            r'SG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',
            'SendGrid API Key detected',
            'SendGrid keys should be stored using secrets! or environment variables.',
        ),
        (
            r'xox[baprs]-[0-9]{10,}-[A-Za-z0-9]{10,}',
            'Slack Bot/User Token detected',
            'Slack tokens should be stored using secrets! or environment variables.',
        ),
        (
            r'ATIA[A-Za-z0-9_-]{30,}',
            'Atlassian API Token detected',
            'Atlassian tokens should be stored using secrets! or environment variables.',
        ),
        (
            r'ABK[A-Za-z0-9_-]{30,}',
            'Amazon Selling Partner API Key detected',
            'Amazon API keys should be stored using secrets! or environment variables.',
        ),
    ]

    # Patterns for detecting hardcoded URLs and IP addresses
    HARDCODED_URL_IP_PATTERNS = [
        {
            "pattern": r'https?://[A-Za-z0-9.-]+:[0-9]+',
            "issue": "Hardcoded URL with port detected",
            "recommendation": "Use !secret or environment variables for service endpoints. Consider using Home Assistant services discovery instead of hardcoded URLs.",
            "severity": "medium",
        },
        {
            "pattern": r'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b',
            "issue": "Private IP address detected in configuration",
            "recommendation": "Use Home Assistant service discovery or !secret for internal service endpoints. Avoid hardcoding network addresses.",
            "severity": "low",
        },
        {
            "pattern": r'\b(?:127\.\d{1,3}\.\d{1,3}\.\d{1,3}|::1|0:0:0:0:0:0:0:1)\b',
            "issue": "Loopback address (localhost) detected",
            "recommendation": "Use service names or Home Assistant's built-in discovery instead of hardcoded localhost addresses.",
            "severity": "low",
        },
        {
            "pattern": r'ftp://[A-Za-z0-9.-]+',
            "issue": "FTP URL detected - insecure file transfer protocol",
            "recommendation": "Use SFTP or HTTPS instead of FTP for secure file transfers. Store credentials using secrets!",
            "severity": "high",
        },
        {
            "pattern": r'http://(?!localhost)(?!127\.0\.0\.1)[A-Za-z0-9.-]+',
            "issue": "Insecure HTTP URL detected (not localhost)",
            "recommendation": "Use HTTPS instead of HTTP for external communications to ensure data is encrypted in transit.",
            "severity": "medium",
        },
        {
            "pattern": r'(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*["\']https?://[A-Za-z0-9.-]+',
            "issue": "Credential with embedded URL detected",
            "recommendation": "Separate credentials from URLs. Use !secret for credentials and separate configuration for endpoints.",
            "severity": "high",
        },
    ]

    # Remediation suggestions for common security issues
    REMEDIATION_SUGGESTIONS = {
        "hardcoded_password": {
            "suggestion": "Use Home Assistant's secrets management:",
            "examples": [
                "In configuration.yaml: password: !secret my_password",
                "In .secrets file: my_password=your_actual_password",
                "Alternative: Use environment variable with !env_var MY_PASSWORD",
            ],
        },
        "hardcoded_api_key": {
            "suggestion": "Store API keys securely:",
            "examples": [
                "In configuration.yaml: api_key: !secret api_key_value",
                "In .secrets file: api_key_value=your_api_key_here",
                "For multiple keys: Use !include_dir_named secrets/ directory",
            ],
        },
        "hardcoded_token": {
            "suggestion": "Use secure token storage:",
            "examples": [
                "In configuration.yaml: token: !secret my_token",
                "Use !secret for all authentication tokens",
                "Rotate tokens regularly and update .secrets file",
            ],
        },
        "hardcoded_url": {
            "suggestion": "Use configuration management for URLs:",
            "examples": [
                "In configuration.yaml: endpoint: !secret api_endpoint",
                "Use Home Assistant's built-in service discovery when possible",
                "Consider using template helpers for dynamic endpoints",
            ],
        },
        "exposed_credential": {
            "suggestion": "Immediate actions required:",
            "examples": [
                "Rotate the exposed credential immediately",
                "Move to secrets management (!secret or !include_dir_named)",
                "Review .secrets file permissions (should be 600)",
                "Add .secrets to .gitignore if using version control",
            ],
        },
    }

    # Overly permissive configurations
    PERMISSIVE_PATTERNS = [
        {
            "pattern": r"entity_id:\s*all",
            "issue": "Using 'all' entity IDs can be overly permissive",
            "recommendation": "Specify explicit entity IDs",
            "severity": "medium",
        },
        {
            "pattern": r"target:\s*.*all",
            "issue": "Using 'all' targets can be overly permissive",
            "recommendation": "Specify explicit targets",
            "severity": "medium",
        },
    ]

    # Dangerous services that should be restricted
    DANGEROUS_SERVICES = [
        {
            "service_pattern": "homeassistant.*stop",
            "issue": "Automation can stop Home Assistant",
            "recommendation": "Restrict this automation to admin users only",
            "severity": "critical",
        },
        {
            "service_pattern": "system_shutdown|shutdown",
            "issue": "Automation can shutdown the system",
            "recommendation": "Restrict this automation to admin users only",
            "severity": "critical",
        },
        {
            "service_pattern": "reboot|restart",
            "issue": "Automation can reboot/restart the system",
            "recommendation": "Restrict this automation to admin users only",
            "severity": "high",
        },
        {
            "service_pattern": "persistent_notification.*create",
            "issue": "Automation creates persistent notifications",
            "recommendation": "Ensure notifications are appropriate and not spam",
            "severity": "low",
        },
        {
            "service_pattern": "file_write|write_to_file",
            "issue": "Automation can write to files",
            "recommendation": "Restrict file write access to admin-only automations",
            "severity": "high",
        },
        {
            "service_pattern": "execute_command|shell_command",
            "issue": "Automation can execute system commands",
            "recommendation": "Restrict shell commands to admin users only",
            "severity": "critical",
        },
        {
            "service_pattern": "automation.*disable|automation.*enable",
            "issue": "Automation can disable/enable other automations",
            "recommendation": "Review and restrict automation control",
            "severity": "medium",
        },
        {
            "service_pattern": "script.*turn_on|script.*turn_off",
            "issue": "Automation can control scripts",
            "recommendation": "Review script access controls",
            "severity": "low",
        },
    ]

    # Patterns that indicate external exposure
    EXTERNAL_PATTERNS = [
        {
            "pattern": r"webhook",
            "issue": "Automation uses webhooks (external data exposure)",
            "recommendation": "Ensure webhook endpoints are authenticated and rate-limited",
            "severity": "medium",
        },
        {
            "pattern": r"https?://",
            "issue": "Automation makes external HTTP requests",
            "recommendation": "Verify external endpoints are trusted and use HTTPS",
            "severity": "medium",
        },
        {
            "pattern": r"rest_command|rest:",
            "issue": "Automation uses REST API calls",
            "recommendation": "Ensure REST endpoints are authenticated and use HTTPS",
            "severity": "medium",
        },
        {
            "pattern": r"mqtt.*publish|mqtt\.publish",
            "issue": "Automation publishes to MQTT (potential data exposure)",
            "recommendation": "Ensure MQTT broker is authenticated and topics are secured",
            "severity": "low",
        },
        {
            "pattern": r"send_email|email.*send",
            "issue": "Automation sends emails (potential data leakage)",
            "recommendation": "Ensure email content doesn't contain sensitive data",
            "severity": "low",
        },
    ]

    def audit_automations(
        self, automations: List[Dict[str, Any]]
    ) -> SecurityAuditResult:
        """Audit automations for security issues.

        Args:
            automations: List of automation configurations

        Returns:
            SecurityAuditResult with findings
        """
        issues = []

        for automation in automations:
            alias = automation.get("alias", automation.get("id", "unknown"))
            config_str = str(automation)

            # Check for exposed credentials
            credential_issues = self._check_credentials_in_config(
                config_str, alias
            )
            issues.extend(credential_issues)

            # Check for permissive configs
            permissive_issues = self._check_permissive_in_automation(
                automation, alias
            )
            issues.extend(permissive_issues)

            # Check for infinite loops
            loop_issues = self._check_infinite_loop(automation, alias)
            issues.extend(loop_issues)

            # Check for dangerous services
            service_issues = self._check_dangerous_services(automation, alias)
            issues.extend(service_issues)

            # Check for external exposure
            external_issues = self._check_external_exposure(
                automation, alias
            )
            issues.extend(external_issues)

        score = self.calculate_security_score(issues)
        summary = {
            "automations_audited": len(automations),
            "audit_type": "comprehensive",
            "audit_timestamp": datetime.now().isoformat(),
        }

        return SecurityAuditResult(issues=issues, score=score, summary=summary)

    def check_exposed_credentials(
        self, configurations: List[Dict[str, Any]]
    ) -> List[SecurityIssue]:
        """Check for exposed credentials in configurations.

        Args:
            configurations: List of configuration dictionaries

        Returns:
            List of SecurityIssue objects
        """
        issues = []

        for config in configurations:
            config_str = str(config)
            config_id = config.get("alias", config.get("id", "unknown"))
            issues.extend(self._check_credentials_in_config(config_str, config_id))

        return issues

    def check_permissive_configs(
        self, automations: List[Dict[str, Any]]
    ) -> List[SecurityIssue]:
        """Check for overly permissive configurations.

        Args:
            automations: List of automation configurations

        Returns:
            List of SecurityIssue objects
        """
        issues = []

        for automation in automations:
            alias = automation.get("alias", automation.get("id", "unknown"))
            issues.extend(self._check_permissive_in_automation(automation, alias))

        return issues

    def check_infinite_loops(
        self, automations: List[Dict[str, Any]]
    ) -> List[SecurityIssue]:
        """Scan for potential infinite loops in automations.

        Args:
            automations: List of automation configurations

        Returns:
            List of SecurityIssue objects
        """
        issues = []

        for automation in automations:
            alias = automation.get("alias", automation.get("id", "unknown"))
            issues.extend(self._check_infinite_loop(automation, alias))

        return issues

    def check_service_permissions(
        self, automations: List[Dict[str, Any]]
    ) -> List[SecurityIssue]:
        """Check for potentially dangerous service calls.

        Args:
            automations: List of automation configurations

        Returns:
            List of SecurityIssue objects
        """
        issues = []

        for automation in automations:
            alias = automation.get("alias", automation.get("id", "unknown"))
            issues.extend(self._check_dangerous_services(automation, alias))

        return issues

    def check_external_exposure(
        self, automations: List[Dict[str, Any]]
    ) -> List[SecurityIssue]:
        """Check for automations that expose data externally.

        Args:
            automations: List of automation configurations

        Returns:
            List of SecurityIssue objects
        """
        issues = []

        for automation in automations:
            alias = automation.get("alias", automation.get("id", "unknown"))
            issues.extend(self._check_external_exposure(automation, alias))

        return issues

    def get_ai_security_review(
        self, audit_result: SecurityAuditResult
    ) -> str:
        """Generate an AI prompt for comprehensive security review."""
        issues_text = "\n".join(
            [issue.to_markdown() for issue in audit_result.issues]
        )

        prompt = f"""You are a Home Assistant security expert. Please review the following security audit findings and provide detailed recommendations.

Security Score: {audit_result.score:.1f}/100

Total Issues Found: {len(audit_result.issues)}

Critical Issues: {sum(1 for i in audit_result.issues if i.severity == 'critical')}
High Issues: {sum(1 for i in audit_result.issues if i.severity == 'high')}
Medium Issues: {sum(1 for i in audit_result.issues if i.severity == 'medium')}
Low Issues: {sum(1 for i in audit_result.issues if i.severity == 'low')}
Info Issues: {sum(1 for i in audit_result.issues if i.severity == 'info')}

Detailed Findings:
{issues_text}

Please provide:
1. A comprehensive security assessment
2. Prioritized remediation steps
3. Best practices for Home Assistant security
4. Recommendations for monitoring and alerting
5. Any additional security measures that should be implemented
"""
        return prompt

    def calculate_security_score(
        self, issues: List[SecurityIssue]
    ) -> float:
        """Calculate overall security score based on issues."""
        if not issues:
            return 100.0

        # Weight by severity
        severity_weights = {
            "critical": 25,
            "high": 15,
            "medium": 8,
            "low": 3,
            "info": 0,
        }

        total_deduction = 0
        for issue in issues:
            total_deduction += severity_weights.get(issue.severity, 5)

        score = max(0, 100 - total_deduction)
        return round(score, 1)

    # Private helper methods

    def _check_credentials_in_config(
        self, config_str: str, config_id: str
    ) -> List[SecurityIssue]:
        """Check for credentials in a configuration string."""
        issues = []

        # Check basic credential patterns
        for pattern, description in self.CREDENTIAL_PATTERNS:
            matches = re.finditer(pattern, config_str, re.IGNORECASE)
            for match in matches:
                # Mask the detected credential
                original = match.group(0)
                masked = re.sub(
                    r'(["\'])([^"\']+)(\1)',
                    r'\1***REDACTED***\3',
                    original,
                )
                issues.append(
                    SecurityIssue(
                        issue_type="exposed_credential",
                        severity="critical",
                        description=f"{description}: {masked}",
                        recommendation="Use Home Assistant secrets (!secret) or environment variables instead of hardcoding credentials.",
                        affected_entity=config_id,
                        evidence=original,
                    )
                )

        # Check API key format patterns (GitHub tokens, AWS keys, etc.)
        for pattern, description, recommendation in self.API_KEY_FORMAT_PATTERNS:
            matches = re.finditer(pattern, config_str)
            for match in matches:
                original = match.group(0)
                issues.append(
                    SecurityIssue(
                        issue_type="known_credential_format",
                        severity="critical",
                        description=f"{description}: {original[:20]}***",
                        recommendation=recommendation,
                        affected_entity=config_id,
                        evidence=original,
                    )
                )

        # Check for hardcoded URLs and IPs
        for url_pattern in self.HARDCODED_URL_IP_PATTERNS:
            matches = re.finditer(
                url_pattern["pattern"], config_str, re.IGNORECASE
            )
            for match in matches:
                issues.append(
                    SecurityIssue(
                        issue_type="hardcoded_url_or_ip",
                        severity=url_pattern.get("severity", "medium"),
                        description=url_pattern["issue"],
                        recommendation=url_pattern["recommendation"],
                        affected_entity=config_id,
                        evidence=f"Matched: {match.group(0)}",
                    )
                )

        # Add remediation suggestions for found issues
        if issues:
            _LOGGER.warning(
                "Security issues found in %s - remediation suggestions available",
                config_id,
            )

        return issues

    def _check_permissive_in_automation(
        self, automation: Dict[str, Any], alias: str
    ) -> List[SecurityIssue]:
        """Check for permissive configurations in an automation."""
        issues = []
        config_str = str(automation)

        for permissive_config in self.PERMISSIVE_PATTERNS:
            matches = re.finditer(
                permissive_config["pattern"], config_str, re.IGNORECASE
            )
            for match in matches:
                issues.append(
                    SecurityIssue(
                        issue_type="permissive_configuration",
                        severity=permissive_config.get("severity", "medium"),
                        description=permissive_config["issue"],
                        recommendation=permissive_config["recommendation"],
                        affected_entity=alias,
                        evidence=f"Matched: {match.group(0)}",
                    )
                )

        return issues

    def _check_infinite_loop(
        self, automation: Dict[str, Any], alias: str
    ) -> List[SecurityIssue]:
        """Check for potential infinite loops in an automation."""
        issues = []

        # Get trigger entities
        trigger_entities = self._extract_trigger_entities(automation)
        # Get action entities
        action_entities = self._extract_action_entities(automation)

        # Check if any action targets the same entity as a trigger
        for entity in trigger_entities:
            if entity in action_entities:
                issues.append(
                    SecurityIssue(
                        issue_type="potential_infinite_loop",
                        severity="high",
                        description=(
                            f"Automation may create an infinite loop: "
                            f"trigger on '{entity}' and also act on '{entity}'. "
                            f"This can cause recursive automation execution."
                        ),
                        recommendation=(
                            f"Add a delay or condition to prevent loops. "
                            f"Consider using 'for:' in triggers or adding "
                            f"a state condition before actions."
                        ),
                        affected_entity=alias,
                        evidence=f"Trigger entity: {entity}, Action entity: {entity}",
                    )
                )

        # Check for state triggers without 'for' clause
        triggers = automation.get("trigger", [])
        for trigger in triggers:
            if trigger.get("platform") == "state":
                entity_id = trigger.get("entity_id", "")
                if entity_id and "for" not in trigger:
                    issues.append(
                        SecurityIssue(
                            issue_type="missing_delay",
                            severity="medium",
                            description=(
                                f"State trigger on '{entity_id}' without 'for:' delay. "
                                f"This may cause rapid re-triggering."
                            ),
                            recommendation=(
                                f"Add a 'for:' clause to prevent rapid re-triggering. "
                                f"Example: 'for: '00:01:00' for a 1-minute delay."
                            ),
                            affected_entity=alias,
                            evidence=f"Entity: {entity_id}, Missing: 'for:' clause",
                        )
                    )

        return issues

    def _check_dangerous_services(
        self, automation: Dict[str, Any], alias: str
    ) -> List[SecurityIssue]:
        """Check for dangerous service calls in an automation."""
        issues = []
        config_str = str(automation)

        for dangerous in self.DANGEROUS_SERVICES:
            matches = re.finditer(
                dangerous["service_pattern"], config_str, re.IGNORECASE
            )
            for match in matches:
                issues.append(
                    SecurityIssue(
                        issue_type="dangerous_service",
                        severity=dangerous["severity"],
                        description=dangerous["issue"],
                        recommendation=dangerous["recommendation"],
                        affected_entity=alias,
                        evidence=f"Matched service pattern: {match.group(0)}",
                    )
                )

        return issues

    def _check_external_exposure(
        self, automation: Dict[str, Any], alias: str
    ) -> List[SecurityIssue]:
        """Check for external data exposure in an automation."""
        issues = []
        config_str = str(automation)

        for external in self.EXTERNAL_PATTERNS:
            matches = re.finditer(
                external["pattern"], config_str, re.IGNORECASE
            )
            for match in matches:
                issues.append(
                    SecurityIssue(
                        issue_type="external_exposure",
                        severity=external.get("severity", "medium"),
                        description=external["issue"],
                        recommendation=external["recommendation"],
                        affected_entity=alias,
                        evidence=f"Matched pattern: {match.group(0)}",
                    )
                )

        return issues

    def _extract_trigger_entities(
        self, automation: Dict[str, Any]
    ) -> List[str]:
        """Extract entity IDs from triggers."""
        entities = []
        triggers = automation.get("trigger", [])

        for trigger in triggers:
            if "entity_id" in trigger:
                entity_id = trigger["entity_id"]
                if isinstance(entity_id, list):
                    entities.extend(entity_id)
                elif isinstance(entity_id, str):
                    entities.append(entity_id)

        return entities

    def _extract_action_entities(
        self, automation: Dict[str, Any]
    ) -> List[str]:
        """Extract entity IDs from actions."""
        entities = []
        actions = automation.get("action", [])

        for action in actions:
            # Check for service call
            if "service" in action:
                service = action["service"]
                if isinstance(service, str) and "." in service:
                    # Extract entity from service call
                    target = action.get("target", {})
                    if isinstance(target, dict):
                        entity_id = target.get("entity_id", [])
                        if isinstance(entity_id, list):
                            entities.extend(entity_id)
                        elif isinstance(entity_id, str):
                            entities.append(entity_id)

            # Check for nested actions (repeat, sequence)
            if "sequence" in action:
                for sub_action in action["sequence"]:
                    if "service" in sub_action:
                        target = sub_action.get("target", {})
                        if isinstance(target, dict):
                            entity_id = target.get("entity_id", [])
                            if isinstance(entity_id, list):
                                entities.extend(entity_id)
                            elif isinstance(entity_id, str):
                                entities.append(entity_id)

        return entities
