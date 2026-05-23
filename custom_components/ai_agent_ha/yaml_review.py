"""YAML configuration review system for AI Agent HA.

This module provides AI-powered review of Home Assistant YAML configurations
(automations, dashboards, scripts, etc.) for security, validity, and best practices.
"""

import logging
from typing import Any, Dict, List, Optional

import yaml

_LOGGER = logging.getLogger(__name__)

# Security-sensitive service domains that require extra scrutiny
SECURITY_SENSITIVE_DOMAINS = {
    "system_health", "recorder", "homeassistant", "config",
    "automation", "script", "scene", "cloud", "google", "alexa",
}

# Dangerous service calls that should never be allowed
DANGEROUS_SERVICES = {
    "system_health.report",
    "recorder.purge",
    "recorder.purge_entities",
    "config.core.restart",
    "homeassistant.restart",
    "homeassistant.stop",
    "cloud.alexa_connect",
    "cloud.google_assistant_connect",
}

# Safe service domains for automations
SAFE_SERVICE_DOMAINS = {
    "light", "switch", "climate", "cover", "media_player", "script",
    "input_boolean", "input_number", "input_text", "input_select",
    "automation", "scene", "zwave_js", "z2m", "mqtt", "homeassistant",
    "lovelace", "websocket_api", "logger", "device_tracker", "binary_sensor",
    "sensor", "weather", "sun", "timer", "counter", "template",
}

# Allowed trigger platforms
ALLOWED_TRIGGER_PLATFORMS = {
    "time", "time_pattern", "state", "homeassistant", "device",
    "zone", "event", "numeric_state", "sun", "template", "webhook",
}

# Allowed condition types
ALLOWED_CONDITION_TYPES = {
    "state", "numeric_state", "time", "zone", "device", "template",
    "and", "or", "not",
}

# Allowed action types
ALLOWED_ACTION_TYPES = {
    "call_service", "device", "condition", "wait_for_trigger", "delay",
    "event", "freeze", "if", "parallel", "repeat", "set_variable",
    "send_message", "stop", "tag", "use_url", "write_homeassistant",
}


class YAMLReviewResult:
    """Result of a YAML configuration review."""

    def __init__(
        self,
        safe: bool = True,
        approved: bool = True,
        issues: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        suggestions: Optional[List[str]] = None,
        risk_level: str = "low",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.safe = safe
        self.approved = approved
        self.issues = issues or []
        self.warnings = warnings or []
        self.suggestions = suggestions or []
        self.risk_level = risk_level
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "safe": self.safe,
            "approved": self.approved,
            "issues": self.issues,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "risk_level": self.risk_level,
            "details": self.details,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format for display."""
        lines = ["## YAML Configuration Review"]

        # Risk level
        risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(
            self.risk_level, "⚪"
        )
        lines.append(f"**Risk Level:** {risk_emoji} {self.risk_level.upper()}\n")

        # Status
        status_emoji = "✅" if self.approved else "❌"
        lines.append(f"**Status:** {status_emoji} {'Approved' if self.approved else 'Rejected'}\n")

        # Issues
        if self.issues:
            lines.append("### ⚠️ Issues")
            for issue in self.issues:
                lines.append(f"- {issue}")
            lines.append("")

        # Warnings
        if self.warnings:
            lines.append("### ⚡ Warnings")
            for warning in self.warnings:
                lines.append(f"- {warning}")
            lines.append("")

        # Suggestions
        if self.suggestions:
            lines.append("### 💡 Suggestions")
            for suggestion in self.suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

        return "\n".join(lines)


class YAMLSyntaxValidator:
    """Validates YAML syntax and Home Assistant structure."""

    @staticmethod
    def validate_syntax(yaml_content: str) -> YAMLReviewResult:
        """Validate basic YAML syntax."""
        try:
            parsed = yaml.safe_load(yaml_content)
            if parsed is None:
                return YAMLReviewResult(
                    safe=False,
                    approved=False,
                    issues=["Empty YAML configuration"],
                    risk_level="high",
                )
            return YAMLReviewResult(safe=True, approved=True)
        except yaml.YAMLError as e:
            return YAMLReviewResult(
                safe=False,
                approved=False,
                issues=[f"YAML syntax error: {str(e)}"],
                risk_level="high",
            )

    @staticmethod
    def validate_automation_structure(config: Dict[str, Any]) -> YAMLReviewResult:
        """Validate automation YAML structure."""
        issues = []
        warnings = []
        suggestions = []

        # Check required fields
        if "trigger" not in config:
            issues.append("Missing required 'trigger' field")
        if "action" not in config:
            issues.append("Missing required 'action' field")

        # Check alias/description
        if "alias" not in config and "id" not in config:
            warnings.append("Consider adding an 'alias' for better readability")

        # Validate triggers
        triggers = config.get("trigger", [])
        if isinstance(triggers, list):
            for i, trigger in enumerate(triggers):
                if "platform" not in trigger:
                    issues.append(f"Trigger {i}: Missing 'platform' field")
                else:
                    platform = trigger["platform"]
                    if platform not in ALLOWED_TRIGGER_PLATFORMS:
                        warnings.append(
                            f"Trigger {i}: Unusual platform '{platform}' - verify this is valid"
                        )
        elif not isinstance(triggers, dict):
            issues.append("Trigger must be a list or dict")

        # Validate actions
        actions = config.get("action", [])
        if isinstance(actions, list):
            for i, action in enumerate(actions):
                if "service" in action:
                    service = action["service"]
                    if isinstance(service, str):
                        domain = service.split(".")[0] if "." in service else service
                        if domain in DANGEROUS_SERVICES:
                            issues.append(
                                f"Action {i}: Potentially dangerous service '{service}'"
                            )
                        elif domain not in SAFE_SERVICE_DOMAINS:
                            warnings.append(
                                f"Action {i}: Unusual service domain '{domain}' - verify this is valid"
                            )
                elif "if" in action:
                    pass  # If conditions are valid
                else:
                    warnings.append(
                        f"Action {i}: Consider using explicit 'service' format"
                    )
        elif isinstance(actions, dict):
            # Single action
            if "service" in actions:
                service = actions["service"]
                if isinstance(service, str):
                    domain = service.split(".")[0] if "." in service else service
                    if domain in DANGEROUS_SERVICES:
                        issues.append(f"Action: Potentially dangerous service '{service}'")

        # Check for infinite loops (same entity state triggers -> same entity service)
        triggers = config.get("trigger", [])
        actions = config.get("action", [])
        if isinstance(triggers, list) and isinstance(actions, list):
            for trigger in triggers:
                if trigger.get("platform") == "state":
                    entity_id = trigger.get("entity_id", "")
                    for action in actions:
                        if "service" in action:
                            target = action.get("target", {})
                            if isinstance(target, dict):
                                target_entities = target.get("entity_id", [])
                                if isinstance(target_entities, str):
                                    target_entities = [target_entities]
                                for te in target_entities:
                                    if te == entity_id:
                                        suggestions.append(
                                            "Potential infinite loop: state trigger on entity that is also targeted by action"
                                        )

        if issues:
            return YAMLReviewResult(
                safe=False,
                approved=False,
                issues=issues,
                warnings=warnings,
                suggestions=suggestions,
                risk_level="high",
            )

        if warnings:
            return YAMLReviewResult(
                safe=True,
                approved=True,
                issues=[],
                warnings=warnings,
                suggestions=suggestions,
                risk_level="medium",
            )

        return YAMLReviewResult(
            safe=True,
            approved=True,
            issues=[],
            warnings=[],
            suggestions=suggestions,
            risk_level="low",
        )

    @staticmethod
    def validate_dashboard_structure(config: Dict[str, Any]) -> YAMLReviewResult:
        """Validate dashboard YAML structure."""
        issues = []
        warnings = []
        suggestions = []

        # Check required fields
        if "title" not in config:
            issues.append("Missing required 'title' field")
        if "url_path" not in config:
            issues.append("Missing required 'url_path' field")

        # Check icon
        if "icon" not in config:
            suggestions.append("Consider adding an 'icon' for the dashboard")

        # Validate views
        views = config.get("views", [])
        if isinstance(views, list):
            for i, view in enumerate(views):
                if isinstance(view, dict):
                    if "title" not in view and "name" not in view:
                        warnings.append(f"View {i}: Consider adding a title")
                    if "cards" in view:
                        cards = view["cards"]
                        if not isinstance(cards, list):
                            issues.append(f"View {i}: 'cards' must be a list")

        if issues:
            return YAMLReviewResult(
                safe=False,
                approved=False,
                issues=issues,
                warnings=warnings,
                suggestions=suggestions,
                risk_level="high",
            )

        return YAMLReviewResult(
            safe=True,
            approved=True,
            issues=[],
            warnings=warnings,
            suggestions=suggestions,
            risk_level="low" if not warnings else "medium",
        )


class YAMLReviewer:
    """Main YAML review orchestrator."""

    def __init__(self, hass):
        """Initialize the YAML reviewer."""
        self.hass = hass

    def validate_yaml_syntax(self, yaml_content: str) -> YAMLReviewResult:
        """Validate basic YAML syntax."""
        return YAMLSyntaxValidator.validate_syntax(yaml_content)

    def validate_automation(self, config: Dict[str, Any]) -> YAMLReviewResult:
        """Validate automation configuration."""
        return YAMLSyntaxValidator.validate_automation_structure(config)

    def validate_dashboard(self, config: Dict[str, Any]) -> YAMLReviewResult:
        """Validate dashboard configuration."""
        return YAMLSyntaxValidator.validate_dashboard_structure(config)

    def parse_yaml_content(
        self, yaml_content: str
    ) -> Optional[Dict[str, Any]]:
        """Parse YAML content safely."""
        try:
            parsed = yaml.safe_load(yaml_content)
            if isinstance(parsed, dict):
                return parsed
            return None
        except yaml.YAMLError as e:
            _LOGGER.error(f"Failed to parse YAML: {e}")
            return None
