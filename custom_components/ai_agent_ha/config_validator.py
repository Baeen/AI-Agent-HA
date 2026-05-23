"""Configuration validator for Home Assistant.

This module validates Home Assistant configuration files,
checks for deprecated options, and suggests improvements.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

_LOGGER = logging.getLogger(__name__)


class ConfigIssue:
    """Represents an issue found in configuration."""

    def __init__(
        self,
        issue_type: str,
        severity: str,
        file: str,
        line: int,
        message: str,
        suggestion: str,
        deprecated: bool = False,
    ):
        self.issue_type = issue_type
        self.severity = severity  # critical, high, medium, low, info
        self.file = file
        self.line = line
        self.message = message
        self.suggestion = suggestion
        self.deprecated = deprecated

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "suggestion": self.suggestion,
            "deprecated": self.deprecated,
        }


class ConfigValidationResult:
    """Result of configuration validation."""

    def __init__(
        self,
        config_type: str = "",
        issues: List[ConfigIssue] = None,
        valid: bool = True,
        summary: Dict[str, Any] = None,
    ):
        self.config_type = config_type
        self.issues = issues or []
        self.valid = valid and len(
            [i for i in self.issues if i.severity in ("critical", "high")]
        ) == 0
        self.summary = summary or self._build_summary()

    def _build_summary(self) -> Dict[str, Any]:
        """Build a summary of issues by severity."""
        summary = {
            "total_issues": len(self.issues),
            "by_severity": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0,
            },
        }
        for issue in self.issues:
            if issue.severity in summary["by_severity"]:
                summary["by_severity"][issue.severity] += 1
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "config_type": self.config_type,
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": self.summary,
            "timestamp": datetime.now().isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [
            f"## Configuration Validation Report",
            f"",
            f"**Config Type:** {self.config_type or 'General'}",
            f"**Valid:** {'Yes' if self.valid else 'No'}",
            f"**Total Issues:** {self.summary['total_issues']}",
            f"",
        ]

        # Summary by severity
        lines.append("### Issue Summary")
        lines.append("")
        severity_icons = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🔵",
            "info": "ℹ️",
        }
        for severity, count in self.summary["by_severity"].items():
            if count > 0:
                icon = severity_icons.get(severity, "⚪")
                lines.append(f"- {icon} {severity.upper()}: {count}")
        lines.append("")

        # Detailed issues
        if self.issues:
            lines.append("### Detailed Issues")
            lines.append("")
            for i, issue in enumerate(self.issues, 1):
                icon = severity_icons.get(issue.severity, "⚪")
                deprecated_tag = " [DEPRECATED]" if issue.deprecated else ""
                lines.append(f"#### {i}. {icon} {issue.issue_type}{deprecated_tag}")
                lines.append(f"")
                lines.append(f"- **File:** `{issue.file}`" + (f":{issue.line}" if issue.line else ""))
                lines.append(f"- **Severity:** {issue.severity.upper()}")
                lines.append(f"- **Message:** {issue.message}")
                lines.append(f"- **Suggestion:** {issue.suggestion}")
                lines.append("")

        return "\n".join(lines)


# Known deprecated options
DEPRECATED_OPTIONS = {
    # automation deprecated options
    "automation": {
        "deprecated_fields": ["initial_state"],
        "replaced_by": "Use 'homeassistant.start' trigger instead",
    },
    # sensor deprecated options
    "sensor": {
        "deprecated_options": {"unit": "Use unit_of_measurement"},
    },
    # binary_sensor deprecated options
    "binary_sensor": {
        "deprecated_options": {"unit": "Remove unit, binary sensors don't have units"},
    },
    # switch deprecated options
    "switch": {
        "deprecated_options": {"unit": "Remove unit, switches don't have units"},
    },
    # input_boolean deprecated
    "input_boolean": {
        "deprecated_platforms": [],
        "note": "Use input_boolean helper via UI or services instead of YAML platform",
    },
    # input_number deprecated options
    "input_number": {
        "deprecated_options": {"unit_of_measurement": "Use state_class instead for metrics"},
    },
    # text deprecated options
    "text": {
        "deprecated_options": {"unit": "Remove unit, text inputs don't have units"},
    },
    # select deprecated options
    "select": {
        "deprecated_options": {"unit": "Remove unit, selects don't have units"},
    },
    # Climate deprecated options
    "climate": {
        "deprecated_options": {
            "target_temp_high_service": "Use target_temp_high option in climate.set_temperature",
            "target_temp_low_service": "Use target_temp_low option in climate.set_temperature",
        },
    },
    # Recorder deprecated options
    "recorder": {
        "deprecated_options": {
            "purge_age": "Use purge_keep_days instead",
            "purge_interval": "Still supported but consider purge_keep_days",
        },
    },
}

# Valid trigger platforms
VALID_TRIGGER_PLATFORMS = {
    "time",
    "time_pattern",
    "state",
    "homeassistant",
    "device",
    "zone",
    "event",
    "numeric_state",
    "sun",
    "template",
    "webhook",
    "mqtt",
    "tag",
}

# Valid condition platforms
VALID_CONDITION_PLATFORMS = {
    "state",
    "numeric_state",
    "time",
    "zone",
    "device",
    "template",
    "and",
    "or",
    "not",
}

# Valid action types
VALID_ACTION_TYPES = {
    "call_service",
    "device",
    "condition",
    "wait_for_trigger",
    "delay",
    "event",
    "if",
    "parallel",
    "repeat",
    "set_variable",
    "send_message",
    "stop",
    "tag",
}

# Best practices rules
BEST_PRACTICES = [
    {
        "check": "alias_present",
        "description": "All automations should have an alias",
        "severity": "low",
    },
    {
        "check": "description_present",
        "description": "Automations should have a description",
        "severity": "info",
    },
    {
        "check": "id_present",
        "description": "Automations should have a unique ID",
        "severity": "low",
    },
    {
        "check": "mode_specified",
        "description": "Consider specifying mode for automations",
        "severity": "info",
    },
    {
        "check": "no_sensitive_data",
        "description": "Check for exposed credentials or API keys",
        "severity": "critical",
    },
    {
        "check": "trigger_present",
        "description": "Automations must have at least one trigger",
        "severity": "high",
    },
    {
        "check": "action_present",
        "description": "Automations must have at least one action",
        "severity": "high",
    },
]

# Sensitive data patterns
SENSITIVE_PATTERNS = [
    r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[\w@#$%^&*!]+['\"]?",
    r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[\w-]+['\"]?",
    r"(?i)(token|secret)\s*[:=]\s*['\"]?[\w-]+['\"]?",
    r"(?i)(access[_-]?key)\s*[:=]\s*['\"]?[\w-]+['\"]?",
    r"sk-[a-zA-Z0-9]{20,}",  # OpenAI-style keys
    r"AI[0-9A-Z]{10,}",  # Gemini-style keys
    r"ghp_[a-zA-Z0-9]{36}",  # GitHub tokens
    r"AKIA[0-9A-Z]{16}",  # AWS access keys
]

# Valid core integrations that should be checked
VALID_CORE_INTEGRATIONS = {
    "automation",
    "script",
    "frontend",
    "history",
    "logbook",
    "recorder",
    "homeassistant",
    "http",
    "device_tracker",
    "sensor",
    "binary_sensor",
    "switch",
    "light",
    "climate",
    "cover",
    "media_player",
    "camera",
    "weather",
    "input_boolean",
    "input_number",
    "input_text",
    "input_select",
    "zone",
    "group",
    "person",
    "user",
    "config",
    "cloud",
    "assistant",
    "assist_pipeline",
    "conversation",
}


class ConfigurationValidator:
    """Validates Home Assistant configuration files."""

    def __init__(self):
        """Initialize the configuration validator."""
        self.deprecated_options = DEPRECATED_OPTIONS
        self.best_practices = BEST_PRACTICES
        self.sensitive_patterns = SENSITIVE_PATTERNS

    def validate_configuration_yaml(
        self, config_path: Optional[str] = None, config_content: Optional[str] = None
    ) -> ConfigValidationResult:
        """Validate the main configuration.yaml file.

        Args:
            config_path: Path to the configuration.yaml file
            config_content: YAML content as string (alternative to path)

        Returns:
            ConfigValidationResult with validation issues
        """
        issues = []
        file = config_path or "configuration.yaml"

        try:
            # Load YAML content
            yaml_data = None
            if config_content:
                try:
                    yaml_data = yaml.safe_load(config_content)
                except yaml.YAMLError as e:
                    issues.append(
                        ConfigIssue(
                            issue_type="syntax_error",
                            severity="critical",
                            file=file,
                            line=0,
                            message=f"Invalid YAML syntax: {str(e)}",
                            suggestion="Fix YAML syntax errors. Check indentation and formatting.",
                        )
                    )
                    return ConfigValidationResult(
                        config_type="configuration", issues=issues, valid=False
                    )
            elif config_path:
                with open(config_path, "r") as f:
                    yaml_data = yaml.safe_load(f)

            if yaml_data is None:
                issues.append(
                    ConfigIssue(
                        issue_type="empty_config",
                        severity="medium",
                        file=file,
                        line=0,
                        message="Configuration file is empty",
                        suggestion="Add required configuration sections like homeassistant, http, etc.",
                    )
                )
                return ConfigValidationResult(
                    config_type="configuration", issues=issues, valid=False
                )

            if not isinstance(yaml_data, dict):
                issues.append(
                    ConfigIssue(
                        issue_type="invalid_format",
                        severity="critical",
                        file=file,
                        line=0,
                        message="Configuration must be a YAML mapping",
                        suggestion="Ensure configuration is in key-value format.",
                    )
                )
                return ConfigValidationResult(
                    config_type="configuration", issues=issues, valid=False
                )

            # Check for common required sections
            if "homeassistant" not in yaml_data:
                issues.append(
                    ConfigIssue(
                        issue_type="missing_section",
                        severity="info",
                        file=file,
                        line=0,
                        message="No 'homeassistant' section found",
                        suggestion="Consider adding a homeassistant section with latitude, longitude, time_zone, etc.",
                    )
                )

            if "http" not in yaml_data:
                issues.append(
                    ConfigIssue(
                        issue_type="missing_section",
                        severity="medium",
                        file=file,
                        line=0,
                        message="No 'http' section found",
                        suggestion="Add an http section with 'ssl_profile', 'cors_domains', 'ip_ban_enabled', etc.",
                    )
                )

            # Check for deprecated options
            deprecated_issues = self._check_config_deprecated(yaml_data)
            issues.extend(deprecated_issues)

            # Check for sensitive data
            sensitive_issues = self.check_sensitive_data(yaml_data, file)
            issues.extend(sensitive_issues)

            # Check best practices
            bp_issues = self._check_config_best_practices(yaml_data)
            issues.extend(bp_issues)

            return ConfigValidationResult(
                config_type="configuration",
                issues=issues,
                summary={"total_issues": len(issues)},
            )

        except FileNotFoundError:
            issues.append(
                ConfigIssue(
                    issue_type="file_not_found",
                    severity="high",
                    file=file,
                    line=0,
                    message=f"Configuration file not found: {config_path}",
                    suggestion="Verify the path to your configuration.yaml file.",
                )
            )
            return ConfigValidationResult(
                config_type="configuration", issues=issues, valid=False
            )
        except Exception as e:
            issues.append(
                ConfigIssue(
                    issue_type="read_error",
                    severity="critical",
                    file=file,
                    line=0,
                    message=f"Error reading configuration: {str(e)}",
                    suggestion="Check file permissions and path.",
                )
            )
            return ConfigValidationResult(
                config_type="configuration", issues=issues, valid=False
            )

    def validate_automations_yaml(
        self, automations: List[Dict[str, Any]]
    ) -> ConfigValidationResult:
        """Validate automations.yaml content.

        Args:
            automations: List of automation configurations

        Returns:
            ConfigValidationResult with validation issues
        """
        issues = []

        if not isinstance(automations, list):
            issues.append(
                ConfigIssue(
                    issue_type="invalid_format",
                    severity="critical",
                    file="automations.yaml",
                    line=0,
                    message="Automations must be a list",
                    suggestion="Ensure automations.yaml contains a list of automation objects.",
                )
            )
            return ConfigValidationResult(
                config_type="automations", issues=issues, valid=False
            )

        for idx, automation in enumerate(automations):
            prefix = f"automations.yaml:automation[{idx}]"
            if not isinstance(automation, dict):
                issues.append(
                    ConfigIssue(
                        issue_type="invalid_format",
                        severity="critical",
                        file="automations.yaml",
                        line=0,
                        message=f"Automation {idx} is not a valid object",
                        suggestion="Each automation must be a YAML mapping with fields like alias, trigger, action.",
                    )
                )
                continue

            # Check for required fields
            if "trigger" not in automation:
                issues.append(
                    ConfigIssue(
                        issue_type="missing_trigger",
                        severity="high",
                        file="automations.yaml",
                        line=0,
                        message=f"Automation '{automation.get('alias', idx)}' is missing 'trigger'",
                        suggestion="All automations must have at least one trigger.",
                    )
                )

            if "action" not in automation:
                issues.append(
                    ConfigIssue(
                        issue_type="missing_action",
                        severity="high",
                        file="automations.yaml",
                        line=0,
                        message=f"Automation '{automation.get('alias', idx)}' is missing 'action'",
                        suggestion="All automations must have at least one action.",
                    )
                )

            # Validate trigger platforms
            self._validate_triggers(automation.get("trigger", []), prefix, issues)

            # Check for deprecated options
            deprecated_issues = self.check_deprecated_options("automation", automation)
            issues.extend(deprecated_issues)

            # Check best practices
            bp_issues = self._check_automation_best_practices(automation, prefix)
            issues.extend(bp_issues)

            # Check for sensitive data in actions
            sensitive_issues = self.check_sensitive_data(
                automation.get("action", []), f"{prefix}.action"
            )
            issues.extend(sensitive_issues)

        return ConfigValidationResult(
            config_type="automations",
            issues=issues,
            summary={"total_automations": len(automations)},
        )

    def validate_scripts_yaml(
        self, scripts: Dict[str, Any]
    ) -> ConfigValidationResult:
        """Validate scripts.yaml content.

        Args:
            scripts: Dictionary of script configurations

        Returns:
            ConfigValidationResult with validation issues
        """
        issues = []

        if not isinstance(scripts, dict):
            issues.append(
                ConfigIssue(
                    issue_type="invalid_format",
                    severity="critical",
                    file="scripts.yaml",
                    line=0,
                    message="Scripts must be a mapping",
                    suggestion="Ensure scripts.yaml contains key-value pairs of script configurations.",
                )
            )
            return ConfigValidationResult(
                config_type="scripts", issues=issues, valid=False
            )

        for script_name, script_config in scripts.items():
            prefix = f"scripts.yaml:{script_name}"

            if not isinstance(script_config, dict):
                issues.append(
                    ConfigIssue(
                        issue_type="invalid_format",
                        severity="critical",
                        file="scripts.yaml",
                        line=0,
                        message=f"Script '{script_name}' is not a valid object",
                        suggestion="Each script must be a YAML mapping with 'sequence' or 'alias' fields.",
                    )
                )
                continue

            # Check for sequence
            if "sequence" not in script_config:
                issues.append(
                    ConfigIssue(
                        issue_type="missing_sequence",
                        severity="high",
                        file="scripts.yaml",
                        line=0,
                        message=f"Script '{script_name}' is missing 'sequence'",
                        suggestion="Scripts must have a 'sequence' field with actions to execute.",
                    )
                )

            # Validate sequence if present
            sequence = script_config.get("sequence", [])
            if isinstance(sequence, list):
                self._validate_sequence(sequence, prefix, issues)

            # Check for sensitive data
            sensitive_issues = self.check_sensitive_data(
                script_config, prefix
            )
            issues.extend(sensitive_issues)

        return ConfigValidationResult(
            config_type="scripts",
            issues=issues,
            summary={"total_scripts": len(scripts)},
        )

    def validate_groups_yaml(
        self, groups: Dict[str, Any]
    ) -> ConfigValidationResult:
        """Validate groups.yaml content.

        Args:
            groups: Dictionary of group configurations

        Returns:
            ConfigValidationResult with validation issues
        """
        issues = []

        if not isinstance(groups, dict):
            issues.append(
                ConfigIssue(
                    issue_type="invalid_format",
                    severity="critical",
                    file="groups.yaml",
                    line=0,
                    message="Groups must be a mapping",
                    suggestion="Ensure groups.yaml contains key-value pairs of group configurations.",
                )
            )
            return ConfigValidationResult(
                config_type="groups", issues=issues, valid=False
            )

        for group_name, group_config in groups.items():
            prefix = f"groups.yaml:{group_name}"

            if not isinstance(group_config, dict):
                issues.append(
                    ConfigIssue(
                        issue_type="invalid_format",
                        severity="critical",
                        file="groups.yaml",
                        line=0,
                        message=f"Group '{group_name}' is not a valid object",
                        suggestion="Each group must be a YAML mapping with 'entities' and optionally 'view', 'icon', etc.",
                    )
                )
                continue

            # Check for entities
            if "entities" not in group_config:
                issues.append(
                    ConfigIssue(
                        issue_type="missing_entities",
                        severity="medium",
                        file="groups.yaml",
                        line=0,
                        message=f"Group '{group_name}' is missing 'entities'",
                        suggestion="Groups should have an 'entities' list.",
                    )
                )
            else:
                entities = group_config["entities"]
                if not isinstance(entities, list):
                    issues.append(
                        ConfigIssue(
                            issue_type="invalid_entities",
                            severity="high",
                            file="groups.yaml",
                            line=0,
                            message=f"Group '{group_name}' has invalid 'entities' format",
                            suggestion="'entities' must be a list of entity IDs.",
                        )
                    )
                else:
                    # Validate entity ID format
                    for i, entity in enumerate(entities):
                        if isinstance(entity, str):
                            if "." not in entity:
                                issues.append(
                                    ConfigIssue(
                                        issue_type="invalid_entity_id",
                                        severity="medium",
                                        file="groups.yaml",
                                        line=0,
                                        message=f"Group '{group_name}' has invalid entity at index {i}: '{entity}'",
                                        suggestion="Entity IDs should be in format 'domain.entity_name'.",
                                    )
                                )

            # Check for deprecated 'view' key (deprecated in favor of UI configuration)
            if "view" in group_config:
                issues.append(
                    ConfigIssue(
                        issue_type="deprecated_option",
                        severity="low",
                        file="groups.yaml",
                        line=0,
                        message=f"Group '{group_name}' uses deprecated 'view' option",
                        suggestion="Use the Home Assistant UI to configure dashboard views instead of groups.yaml.",
                        deprecated=True,
                    )
                )

        return ConfigValidationResult(
            config_type="groups",
            issues=issues,
            summary={"total_groups": len(groups)},
        )

    def validate_integration_config(
        self, integration_name: str, config: Dict[str, Any]
    ) -> ConfigValidationResult:
        """Validate a specific integration's configuration.

        Args:
            integration_name: Name of the integration
            config: Configuration dictionary for the integration

        Returns:
            ConfigValidationResult with validation issues
        """
        issues = []
        prefix = f"config:{integration_name}"

        if not isinstance(config, dict):
            issues.append(
                ConfigIssue(
                    issue_type="invalid_format",
                    severity="critical",
                    file=f"configuration.yaml:{integration_name}",
                    line=0,
                    message=f"Integration '{integration_name}' config must be a mapping",
                    suggestion=f"Configuration for '{integration_name}' should be a YAML mapping.",
                )
            )
            return ConfigValidationResult(
                config_type=f"integration:{integration_name}",
                issues=issues,
                valid=False,
            )

        # Check for deprecated options
        deprecated_issues = self.check_deprecated_options(integration_name, config)
        issues.extend(deprecated_issues)

        # Check for sensitive data
        sensitive_issues = self.check_sensitive_data(config, prefix)
        issues.extend(sensitive_issues)

        return ConfigValidationResult(
            config_type=f"integration:{integration_name}",
            issues=issues,
        )

    def check_deprecated_options(
        self, config_type: str, config: Dict[str, Any]
    ) -> List[ConfigIssue]:
        """Check for deprecated options in configuration.

        Args:
            config_type: Type of configuration (e.g., 'automation', 'sensor')
            config: Configuration dictionary

        Returns:
            List of ConfigIssue for deprecated options found
        """
        issues = []

        deprecated_info = self.deprecated_options.get(config_type, {})

        if not deprecated_info:
            return issues

        # Check deprecated fields in automation
        if "deprecated_fields" in deprecated_info:
            for field in deprecated_info["deprecated_fields"]:
                if field in config:
                    replacement = deprecated_info.get("replaced_by", "Check documentation for modern alternative")
                    issues.append(
                        ConfigIssue(
                            issue_type="deprecated_field",
                            severity="medium",
                            file=f"config:{config_type}",
                            line=0,
                            message=f"Field '{field}' is deprecated in '{config_type}'",
                            suggestion=replacement,
                            deprecated=True,
                        )
                    )

        # Check deprecated options
        if "deprecated_options" in deprecated_info:
            for option, suggestion in deprecated_info["deprecated_options"].items():
                if option in config:
                    issues.append(
                        ConfigIssue(
                            issue_type="deprecated_option",
                            severity="medium",
                            file=f"config:{config_type}",
                            line=0,
                            message=f"Option '{option}' is deprecated in '{config_type}'",
                            suggestion=suggestion,
                            deprecated=True,
                        )
                    )

        # Check for deprecated platforms in nested configs
        if isinstance(config, dict):
            for key, value in config.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            nested_issues = self._check_nested_deprecated(
                                item, config_type, key
                            )
                            issues.extend(nested_issues)

        return issues

    def check_best_practices(
        self, config_type: str, config: Any
    ) -> List[ConfigIssue]:
        """Check configuration against best practices.

        Args:
            config_type: Type of configuration
            config: Configuration data

        Returns:
            List of ConfigIssue for best practice violations
        """
        issues = []

        if config_type == "automation" and isinstance(config, dict):
            issues.extend(self._check_automation_best_practices(config))
        elif config_type == "configuration" and isinstance(config, dict):
            issues.extend(self._check_config_best_practices(config))

        return issues

    def check_sensitive_data(
        self, config: Any, path: str = ""
    ) -> List[ConfigIssue]:
        """Check for exposed credentials or sensitive data.

        Args:
            config: Configuration data to check
            path: Current path in the config structure

        Returns:
            List of ConfigIssue for sensitive data found
        """
        issues = []

        if isinstance(config, dict):
            for key, value in config.items():
                current_path = f"{path}.{key}" if path else key
                key_lower = key.lower()

                # Check if key name suggests sensitive data
                sensitive_keys = [
                    "password", "passwd", "pwd", "token", "api_key",
                    "apikey", "secret", "access_key", "auth",
                ]

                is_sensitive_key = any(
                    sk in key_lower for sk in sensitive_keys
                )

                if is_sensitive_key and isinstance(value, str) and value:
                    # Check if it looks like a hardcoded value (not a template or variable reference)
                    if not (
                        value.startswith("{{")
                        or value.startswith("{%")
                        or value.startswith("!secret")
                        or value.startswith("$")
                        or value.startswith("!env_var")
                    ):
                        issues.append(
                            ConfigIssue(
                                issue_type="sensitive_data",
                                severity="critical",
                                file=path or "configuration",
                                line=0,
                                message=f"Potential hardcoded credential in '{current_path}'",
                                suggestion="Use '!secret' to store sensitive values securely.",
                            )
                        )

                # Recursively check nested structures
                if isinstance(value, (dict, list)):
                    issues.extend(self.check_sensitive_data(value, current_path))

        elif isinstance(config, list):
            for i, item in enumerate(config):
                current_path = f"{path}[{i}]"
                if isinstance(item, (dict, list)):
                    issues.extend(self.check_sensitive_data(item, current_path))

        elif isinstance(config, str):
            # Check for patterns that look like API keys or tokens
            for pattern in self.sensitive_patterns:
                import re
                if re.search(pattern, config):
                    issues.append(
                        ConfigIssue(
                            issue_type="sensitive_data_pattern",
                            severity="critical",
                            file=path or "configuration",
                            line=0,
                            message=f"Potential API key or token detected in '{path}'",
                            suggestion="Use '!secret' to store sensitive values securely.",
                        )
                    )
                    break

        return issues

    def get_ai_prompt_for_improvements(
        self, result: ConfigValidationResult
    ) -> str:
        """Generate an AI prompt to get improvement suggestions.

        Args:
            result: Validation result to base the prompt on

        Returns:
            Prompt string for AI improvement suggestions
        """
        prompt = (
            f"I have a Home Assistant {result.config_type} configuration with the following issues:\n\n"
        )

        if result.issues:
            for issue in result.issues:
                prompt += f"- [{issue.severity.upper()}] {issue.issue_type}: {issue.message}\n"
                prompt += f"  Suggestion: {issue.suggestion}\n\n"
        else:
            prompt += "No issues found. Please provide general best practice recommendations.\n"

        prompt += (
            "Please provide specific, actionable improvement suggestions "
            "for my Home Assistant configuration. Focus on:\n"
            "1. Security improvements\n"
            "2. Performance optimizations\n"
            "3. Best practices\n"
            "4. Modern alternatives to deprecated features"
        )

        return prompt

    # Private helper methods

    def _validate_triggers(
        self,
        triggers: List[Dict[str, Any]],
        prefix: str,
        issues: List[ConfigIssue],
    ):
        """Validate trigger configurations."""
        if not isinstance(triggers, list):
            issues.append(
                ConfigIssue(
                    issue_type="invalid_trigger",
                    severity="high",
                    file=prefix,
                    line=0,
                    message="Triggers must be a list",
                    suggestion="Ensure triggers is a list of trigger objects.",
                )
            )
            return

        for idx, trigger in enumerate(triggers):
            if not isinstance(trigger, dict):
                issues.append(
                    ConfigIssue(
                        issue_type="invalid_trigger",
                        severity="high",
                        file=prefix,
                        line=0,
                        message=f"Trigger {idx} is not a valid object",
                        suggestion="Each trigger must be a YAML mapping with a platform field.",
                    )
                )
                continue

            platform = trigger.get("platform", "")
            if platform and platform not in VALID_TRIGGER_PLATFORMS:
                issues.append(
                    ConfigIssue(
                        issue_type="invalid_trigger_platform",
                        severity="medium",
                        file=prefix,
                        line=0,
                        message=f"Trigger {idx} uses unknown platform '{platform}'",
                        suggestion=f"Valid trigger platforms: {', '.join(sorted(VALID_TRIGGER_PLATFORMS))}",
                    )
                )

    def _validate_sequence(
        self,
        sequence: List[Dict[str, Any]],
        prefix: str,
        issues: List[ConfigIssue],
    ):
        """Validate a sequence of actions."""
        if not isinstance(sequence, list):
            issues.append(
                ConfigIssue(
                    issue_type="invalid_sequence",
                    severity="high",
                    file=prefix,
                    line=0,
                    message="Sequence must be a list",
                    suggestion="Ensure sequence is a list of action objects.",
                )
            )
            return

        for idx, action in enumerate(sequence):
            if not isinstance(action, dict):
                issues.append(
                    ConfigIssue(
                        issue_type="invalid_action",
                        severity="high",
                        file=prefix,
                        line=0,
                        message=f"Action {idx} is not a valid object",
                        suggestion="Each action must be a YAML mapping.",
                    )
                )
                continue

            # Check for service call format
            if "service" in action:
                service = action["service"]
                if not isinstance(service, str) or "." not in str(service):
                    issues.append(
                        ConfigIssue(
                            issue_type="invalid_service",
                            severity="medium",
                            file=prefix,
                            line=0,
                            message=f"Action {idx} has invalid service format: '{service}'",
                            suggestion="Service should be in format 'domain.service_name'.",
                        )
                    )

    def _check_nested_deprecated(
        self, item: Dict[str, Any], config_type: str, parent_key: str
    ) -> List[ConfigIssue]:
        """Check nested configurations for deprecated options."""
        issues = []
        for key, value in item.items():
            if key in self.deprecated_options.get(config_type, {}).get(
                "deprecated_fields", []
            ):
                replacement = self.deprecated_options.get(
                    config_type, {}
                ).get("replaced_by", "Check documentation")
                issues.append(
                    ConfigIssue(
                        issue_type="deprecated_field",
                        severity="medium",
                        file=f"config:{config_type}:{parent_key}",
                        line=0,
                        message=f"Field '{key}' is deprecated",
                        suggestion=replacement,
                        deprecated=True,
                    )
                )
        return issues

    def _check_automation_best_practices(
        self, automation: Dict[str, Any], prefix: str = ""
    ) -> List[ConfigIssue]:
        """Check automation against best practices."""
        issues = []
        alias = automation.get("alias", "Unnamed")

        # Check for alias
        if "alias" not in automation:
            issues.append(
                ConfigIssue(
                    issue_type="missing_alias",
                    severity="low",
                    file=prefix or "automations.yaml",
                    line=0,
                    message="Automation is missing an alias",
                    suggestion="Add an 'alias' field to describe what the automation does.",
                )
            )

        # Check for description
        if "description" not in automation:
            issues.append(
                ConfigIssue(
                    issue_type="missing_description",
                    severity="info",
                    file=prefix or "automations.yaml",
                    line=0,
                    message="Automation is missing a description",
                    suggestion="Add a 'description' field to explain the automation's purpose.",
                )
            )

        # Check for ID
        if "id" not in automation:
            issues.append(
                ConfigIssue(
                    issue_type="missing_id",
                    severity="low",
                    file=prefix or "automations.yaml",
                    line=0,
                    message="Automation is missing a unique ID",
                    suggestion="Add an 'id' field with a unique identifier (e.g., using UUID).",
                )
            )

        # Check for mode
        if "mode" not in automation:
            issues.append(
                ConfigIssue(
                    issue_type="missing_mode",
                    severity="info",
                    file=prefix or "automations.yaml",
                    line=0,
                    message="Automation is missing a mode specification",
                    suggestion="Consider adding 'mode' (single, parallel, queued) to control concurrent executions.",
                )
            )

        return issues

    def _check_config_best_practices(self, config: Dict[str, Any]) -> List[ConfigIssue]:
        """Check main configuration against best practices."""
        issues = []

        # Check for timezone
        ha_config = config.get("homeassistant", {})
        if "time_zone" not in ha_config:
            issues.append(
                ConfigIssue(
                    issue_type="missing_timezone",
                    severity="medium",
                    file="configuration.yaml",
                    line=0,
                    message="Time zone is not explicitly set",
                    suggestion="Add 'time_zone' to your homeassistant configuration for consistent timestamps.",
                )
            )

        # Check for latitude/longitude
        if "latitude" not in ha_config or "longitude" not in ha_config:
            issues.append(
                ConfigIssue(
                    issue_type="missing_location",
                    severity="low",
                    file="configuration.yaml",
                    line=0,
                    message="Latitude or longitude is not set",
                    suggestion="Set latitude and longitude for sun-based automations and weather.",
                )
            )

        return issues
