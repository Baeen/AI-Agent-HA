"""Automation troubleshooter for Home Assistant.

This module provides functionality to troubleshoot automations,
identify issues, and suggest fixes.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class AutomationIssue:
    """Represents an issue found in an automation."""

    def __init__(
        self,
        issue_type: str,
        severity: str,
        message: str,
        suggestion: str,
        affected_field: str = "",
        examples: Optional[List[str]] = None,
    ):
        self.issue_type = issue_type
        self.severity = severity  # critical, high, medium, low, info
        self.message = message
        self.suggestion = suggestion
        self.affected_field = affected_field
        self.examples = examples or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "message": self.message,
            "suggestion": self.suggestion,
            "affected_field": self.affected_field,
            "examples": self.examples,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        severity_icon = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "info": "⚪",
        }.get(self.severity, "⚪")
        
        return f"- {severity_icon} **{self.issue_type}**: {self.message}\n  Suggestion: {self.suggestion}"


class AutomationTroubleshootResult:
    """Result of automation troubleshooting."""

    def __init__(
        self,
        automation_id: str = "",
        automation_alias: str = "",
        issues: Optional[List[AutomationIssue]] = None,
        is_valid: bool = True,
        health_score: float = 1.0,
        recommendations: Optional[List[str]] = None,
    ):
        self.automation_id = automation_id
        self.automation_alias = automation_alias
        self.issues = issues or []
        self.is_valid = is_valid and len([i for i in self.issues if i.severity in ("critical", "high")]) == 0
        self.health_score = health_score
        self.recommendations = recommendations or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        # Calculate health score based on issues
        if not self.issues:
            score = 1.0
        else:
            penalties = {
                "critical": 0.4,
                "high": 0.2,
                "medium": 0.1,
                "low": 0.05,
                "info": 0.0,
            }
            score = 1.0 - sum(
                penalties.get(issue.severity, 0) for issue in self.issues
            )
            score = max(0.0, min(1.0, score))
        
        return {
            "automation_id": self.automation_id,
            "automation_alias": self.automation_alias,
            "is_valid": self.is_valid,
            "health_score": round(score, 2),
            "issue_count": len(self.issues),
            "critical_issues": len([i for i in self.issues if i.severity == "critical"]),
            "high_issues": len([i for i in self.issues if i.severity == "high"]),
            "medium_issues": len([i for i in self.issues if i.severity == "medium"]),
            "low_issues": len([i for i in self.issues if i.severity == "low"]),
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [f"## Automation Troubleshooting: {self.automation_alias or self.automation_id}"]
        lines.append("")
        lines.append(f"**Health Score:** {self.health_score:.0%}")
        lines.append(f"**Valid:** {'Yes' if self.is_valid else 'No'}")
        lines.append(f"**Total Issues:** {len(self.issues)}")
        lines.append("")
        
        if self.issues:
            lines.append("### Issues Found")
            for issue in self.issues:
                lines.append(issue.to_markdown())
            lines.append("")
        
        if self.recommendations:
            lines.append("### Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")
        
        return "\n".join(lines)


class AutomationTroubleshooter:
    """Troubleshoots Home Assistant automations."""

    # Validation rules for triggers
    VALID_TRIGGER_PLATFORMS = [
        "time", "time_pattern", "state", "numeric_state", "device",
        "zone", "event", "sun", "template", "tag", "webhook",
        "homeassistant", "system_health", "mqtt",
    ]
    
    # Validation rules for conditions
    VALID_CONDITION_TYPES = [
        "state", "numeric_state", "time", "device", "sun",
        "template", "zone", "and", "or", "not",
    ]
    
    # Services that should not be in infinite loops
    STATE_MODIFYING_SERVICES = [
        "input_boolean.turn_on", "input_boolean.turn_off",
        "input_text.publish", "input_select.select_option",
        "input_number.configure", "light.turn_on", "light.turn_off",
        "switch.turn_on", "switch.turn_off",
    ]

    def troubleshoot(
        self, automation_config: Dict[str, Any]
    ) -> AutomationTroubleshootResult:
        """Troubleshoot an automation configuration.
        
        Args:
            automation_config: The automation configuration to troubleshoot
            
        Returns:
            AutomationTroubleshootResult with all issues found
        """
        issues = []
        
        # Basic structure validation
        issues.extend(self._validate_basic_structure(automation_config))
        
        # Trigger validation
        issues.extend(self._validate_triggers(automation_config))
        
        # Condition validation
        issues.extend(self._validate_conditions(automation_config))
        
        # Action validation
        issues.extend(self._validate_actions(automation_config))
        
        # Advanced checks
        issues.extend(self._check_advanced_issues(automation_config))
        
        # Calculate health score
        health_score = self._calculate_health_score(issues)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(issues)
        
        # Get alias and ID
        alias = automation_config.get("alias", "")
        auto_id = automation_config.get("id", "")
        
        return AutomationTroubleshootResult(
            automation_id=str(auto_id),
            automation_alias=str(alias),
            issues=issues,
            health_score=health_score,
            recommendations=recommendations,
        )

    def troubleshoot_multiple(
        self, automations: List[Dict[str, Any]]
    ) -> List[AutomationTroubleshootResult]:
        """Troubleshoot multiple automations.
        
        Args:
            automations: List of automation configurations
            
        Returns:
            List of troubleshooting results
        """
        return [self.troubleshoot(auto) for auto in automations]

    def _validate_basic_structure(
        self, config: Dict[str, Any]
    ) -> List[AutomationIssue]:
        """Validate basic automation structure."""
        issues = []
        
        # Check required fields
        if "trigger" not in config:
            issues.append(AutomationIssue(
                issue_type="Missing Required Field",
                severity="critical",
                message="Automation is missing required 'trigger' field",
                suggestion="Add a trigger to the automation",
                affected_field="trigger",
            ))
        
        if "action" not in config:
            issues.append(AutomationIssue(
                issue_type="Missing Required Field",
                severity="critical",
                message="Automation is missing required 'action' field",
                suggestion="Add actions to execute when the trigger fires",
                affected_field="action",
            ))
        
        # Optional but recommended fields
        if "alias" not in config:
            issues.append(AutomationIssue(
                issue_type="Missing Alias",
                severity="low",
                message="Automation does not have an alias",
                suggestion="Add an alias to make the automation easier to identify",
                affected_field="alias",
            ))
        
        if "description" not in config:
            issues.append(AutomationIssue(
                issue_type="Missing Description",
                severity="info",
                message="Automation does not have a description",
                suggestion="Add a description to explain what the automation does",
                affected_field="description",
            ))
        
        return issues

    def _validate_triggers(
        self, config: Dict[str, Any]
    ) -> List[AutomationIssue]:
        """Validate automation triggers."""
        issues = []
        triggers = config.get("trigger", [])
        
        if not triggers:
            return issues
        
        # Ensure triggers is a list
        if not isinstance(triggers, list):
            triggers = [triggers]
        
        for i, trigger in enumerate(triggers):
            prefix = f"trigger[{i}]" if len(triggers) > 1 else "trigger"
            
            # Check for platform field
            if "platform" not in trigger:
                issues.append(AutomationIssue(
                    issue_type="Missing Platform",
                    severity="high",
                    message=f"{prefix}: Missing 'platform' field",
                    suggestion="Add a valid platform to the trigger",
                    affected_field=prefix,
                ))
                continue
            
            platform = trigger["platform"]
            
            # Check for valid platform
            if platform not in self.VALID_TRIGGER_PLATFORMS:
                issues.append(AutomationIssue(
                    issue_type="Invalid Platform",
                    severity="high",
                    message=f"{prefix}: Invalid platform '{platform}'",
                    suggestion=f"Use a valid platform from: {', '.join(self.VALID_TRIGGER_PLATFORMS)}",
                    affected_field=f"{prefix}.platform",
                ))
            
            # Validate time trigger
            if platform == "time":
                if "at" not in trigger:
                    issues.append(AutomationIssue(
                        issue_type="Missing Time",
                        severity="high",
                        message=f"{prefix}: Time trigger missing 'at' field",
                        suggestion="Add 'at' field with time in HH:MM:SS format",
                        affected_field=f"{prefix}.at",
                    ))
                else:
                    if not re.match(r"^\d{2}:\d{2}(:\d{2})?$", trigger["at"]):
                        issues.append(AutomationIssue(
                            issue_type="Invalid Time Format",
                            severity="medium",
                            message=f"{prefix}: Invalid time format '{trigger['at']}'",
                            suggestion="Use HH:MM or HH:MM:SS format (24-hour)",
                            affected_field=f"{prefix}.at",
                        ))
            
            # Validate state trigger
            if platform == "state":
                if "entity_id" not in trigger and "entity_id" not in trigger:
                    issues.append(AutomationIssue(
                        issue_type="Missing Entity",
                        severity="high",
                        message=f"{prefix}: State trigger missing 'entity_id'",
                        suggestion="Add 'entity_id' to specify which entity to monitor",
                        affected_field=f"{prefix}.entity_id",
                    ))
            
            # Validate zone trigger
            if platform == "zone":
                if "entity_id" not in trigger and "zone" not in trigger:
                    issues.append(AutomationIssue(
                        issue_type="Missing Entity or Zone",
                        severity="high",
                        message=f"{prefix}: Zone trigger missing 'entity_id' or 'zone'",
                        suggestion="Add 'entity_id' (person) and 'zone' to trigger on",
                        affected_field=f"{prefix}",
                    ))
        
        return issues

    def _validate_conditions(
        self, config: Dict[str, Any]
    ) -> List[AutomationIssue]:
        """Validate automation conditions."""
        issues = []
        conditions = config.get("condition", [])
        
        if not conditions:
            return issues
        
        # Ensure conditions is a list
        if not isinstance(conditions, list):
            conditions = [conditions]
        
        for i, condition in enumerate(conditions):
            prefix = f"condition[{i}]" if len(conditions) > 1 else "condition"
            
            if "condition" not in condition:
                issues.append(AutomationIssue(
                    issue_type="Missing Condition Type",
                    severity="high",
                    message=f"{prefix}: Missing 'condition' field",
                    suggestion="Add condition type (state, numeric_state, time, etc.)",
                    affected_field=f"{prefix}.condition",
                ))
                continue
            
            cond_type = condition["condition"]
            
            if cond_type not in self.VALID_CONDITION_TYPES:
                issues.append(AutomationIssue(
                    issue_type="Invalid Condition Type",
                    severity="high",
                    message=f"{prefix}: Invalid condition type '{cond_type}'",
                    suggestion=f"Use a valid condition type: {', '.join(self.VALID_CONDITION_TYPES)}",
                    affected_field=f"{prefix}.condition",
                ))
        
        return issues

    def _validate_actions(
        self, config: Dict[str, Any]
    ) -> List[AutomationIssue]:
        """Validate automation actions."""
        issues = []
        actions = config.get("action", [])
        
        if not actions:
            return issues
        
        # Ensure actions is a list
        if not isinstance(actions, list):
            actions = [actions]
        
        for i, action in enumerate(actions):
            prefix = f"action[{i}]" if len(actions) > 1 else "action"
            
            # Check for service call
            if "service" not in action and "repeat" not in action and "delay" not in action:
                if "alias" not in action and "continue" not in action and "stop" not in action:
                    issues.append(AutomationIssue(
                        issue_type="Invalid Action Format",
                        severity="high",
                        message=f"{prefix}: Action missing 'service' or other valid action type",
                        suggestion="Add 'service' field with format domain.service",
                        affected_field=prefix,
                    ))
            
            # Validate service format
            if "service" in action:
                service = action["service"]
                if not re.match(r"^\w+\.\w+$", str(service)):
                    issues.append(AutomationIssue(
                        issue_type="Invalid Service Format",
                        severity="medium",
                        message=f"{prefix}: Invalid service format '{service}'",
                        suggestion="Use format 'domain.service' (e.g., light.turn_on)",
                        affected_field=f"{prefix}.service",
                    ))
        
        return issues

    def _check_advanced_issues(
        self, config: Dict[str, Any]
    ) -> List[AutomationIssue]:
        """Check for advanced issues like infinite loops."""
        issues = []
        
        # Check for potential infinite loops
        issues.extend(self._check_infinite_loop(config))
        
        # Check for mode issues
        issues.extend(self._check_mode(config))
        
        # Check for missing max_iterations
        actions = config.get("action", [])
        if isinstance(actions, list):
            for action in actions:
                if isinstance(action, dict) and "repeat" in action:
                    if "max_iterations" not in action.get("repeat", {}):
                        issues.append(AutomationIssue(
                            issue_type="Missing Max Iterations",
                            severity="medium",
                            message="Repeat loop without max_iterations",
                            suggestion="Add 'max_iterations' to prevent infinite loops",
                            affected_field="action.repeat",
                        ))
        
        return issues

    def _check_infinite_loop(self, config: Dict[str, Any]) -> List[AutomationIssue]:
        """Check for potential infinite loops."""
        issues = []
        triggers = config.get("trigger", [])
        actions = config.get("action", [])
        
        if not triggers or not actions:
            return issues
        
        # Ensure lists
        if not isinstance(triggers, list):
            triggers = [triggers]
        if not isinstance(actions, list):
            actions = [actions]
        
        # Check for state trigger -> same entity action pattern
        for trigger in triggers:
            if trigger.get("platform") == "state":
                trigger_entity = trigger.get("entity_id", "")
                
                for action in actions:
                    if isinstance(action, dict):
                        service = action.get("service", "")
                        target = action.get("target", {})
                        data = action.get("data", action.get("data_template", {}))
                        
                        # Check if action modifies the same entity that triggers
                        if trigger_entity:
                            if service and trigger_entity.split(".")[0] in service:
                                issues.append(AutomationIssue(
                                    issue_type="Potential Infinite Loop",
                                    severity="critical",
                                    message=f"State trigger on {trigger_entity} may cause infinite loop if action modifies same entity",
                                    suggestion="Add 'for' delay to trigger or ensure action doesn't immediately re-trigger",
                                    affected_field="trigger/action",
                                    examples=[
                                        f"Trigger: state on {trigger_entity}",
                                        f"Action: modifies {trigger_entity}",
                                    ],
                                ))
        
        return issues

    def _check_mode(self, config: Dict[str, Any]) -> List[AutomationIssue]:
        """Check automation mode settings."""
        issues = []
        mode = config.get("mode")
        
        valid_modes = ["single", "restart", "queued", "parallel"]
        
        if mode is None:
            issues.append(AutomationIssue(
                issue_type="Missing Mode",
                severity="info",
                message="Automation does not specify mode (defaults to 'single')",
                suggestion="Consider specifying mode: 'restart' for canceling running instances, 'queued' for waiting, 'parallel' for concurrent",
                affected_field="mode",
            ))
        elif mode not in valid_modes:
            issues.append(AutomationIssue(
                issue_type="Invalid Mode",
                severity="medium",
                message=f"Invalid mode '{mode}'",
                suggestion=f"Use one of: {', '.join(valid_modes)}",
                affected_field="mode",
            ))
        
        return issues

    def _calculate_health_score(self, issues: List[AutomationIssue]) -> float:
        """Calculate health score based on issues."""
        if not issues:
            return 1.0
        
        penalties = {
            "critical": 0.4,
            "high": 0.2,
            "medium": 0.1,
            "low": 0.05,
            "info": 0.0,
        }
        
        score = 1.0 - sum(penalties.get(i.severity, 0) for i in issues)
        return max(0.0, min(1.0, score))

    def _generate_recommendations(
        self, issues: List[AutomationIssue]
    ) -> List[str]:
        """Generate recommendations based on issues."""
        recommendations = []
        
        critical_issues = [i for i in issues if i.severity == "critical"]
        high_issues = [i for i in issues if i.severity == "high"]
        
        if critical_issues:
            recommendations.append(
                "🔴 CRITICAL: Fix these issues immediately as they may cause automation failure or system issues"
            )
        
        if high_issues:
            recommendations.append(
                "🟠 HIGH: These issues should be fixed soon to ensure reliable automation operation"
            )
        
        # Check for specific patterns
        has_infinite_loop = any("Infinite Loop" in i.issue_type for i in issues)
        if has_infinite_loop:
            recommendations.append(
                "⚠️ Potential infinite loop detected. Add 'for' delay to state triggers or use device triggers instead"
            )
        
        has_missing_alias = any("Missing Alias" in i.issue_type for i in issues)
        if has_missing_alias:
            recommendations.append(
                "💡 Add meaningful aliases to make automations easier to identify and manage"
            )
        
        if not issues:
            recommendations.append(
                "✅ Automation looks good! Consider adding descriptions for better maintainability"
            )
        
        return recommendations

    def get_ai_enhanced_troubleshooting(
        self, automation_config: Dict[str, Any], troubleshoot_result: AutomationTroubleshootResult
    ) -> str:
        """Generate an AI-enhanced troubleshooting prompt.
        
        Args:
            automation_config: The original automation configuration
            troubleshoot_result: Results from static analysis
            
        Returns:
            Prompt string for AI troubleshooting
        """
        import json
        
        prompt = f"""You are a Home Assistant automation troubleshooting expert. Please analyze this automation:

Automation: {troubleshoot_result.automation_alias or 'Unnamed'}
Health Score: {troubleshoot_result.health_score:.0%}

Static Analysis Issues:
"""
        
        for issue in troubleshoot_result.issues:
            prompt += f"- [{issue.severity}] {issue.issue_type}: {issue.message}\n"
        
        prompt += f"""
Automation Configuration:
{json.dumps(automation_config, indent=2)}

Please provide:
1. Detailed explanation of each issue
2. Priority order for fixes
3. Specific code changes needed
4. Best practices for this type of automation
5. Potential edge cases to consider

Respond with actionable recommendations.
"""
        
        return prompt

    def generate_fixed_automation(
        self, automation_config: Dict[str, Any], troubleshoot_result: AutomationTroubleshootResult
    ) -> Optional[Dict[str, Any]]:
        """Generate a fixed version of the automation where possible.
        
        Args:
            automation_config: The original automation configuration
            troubleshoot_result: Results from static analysis
            
        Returns:
            Fixed automation configuration or None if cannot auto-fix
        """
        import copy
        
        fixed = copy.deepcopy(automation_config)
        
        # Auto-fix: Add alias if missing
        if "alias" not in fixed:
            fixed["alias"] = f"Automation created at {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Auto-fix: Add mode if missing
        if "mode" not in fixed:
            fixed["mode"] = "queued"
        
        # Auto-fix: Add max_iterations to repeats if missing
        actions = fixed.get("action", [])
        if isinstance(actions, list):
            for action in actions:
                if isinstance(action, dict) and "repeat" in action:
                    if "max_iterations" not in action.get("repeat", {}):
                        action.setdefault("repeat", {})["max_iterations"] = 100
        
        return fixed if fixed != automation_config else None
