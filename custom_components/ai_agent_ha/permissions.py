"""Permission system for AI Agent HA integration.

This module provides a permission checking system that allows users to control
which AI-executed actions require user confirmation before being executed.
This is important for security-sensitive operations like locking/unlocking doors,
disabling alarms, or modifying critical automations.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# Permission modes
PERMISSION_MODE_PROMPT = "prompt"  # Always ask user
PERMISSION_MODE_AUTO_ALLOW = "auto_allow"  # Allow all
PERMISSION_MODE_AUTO_DENY = "auto_deny"  # Deny all

# Risk levels
RISK_LEVEL_LOW = "low"
RISK_LEVEL_MEDIUM = "medium"
RISK_LEVEL_HIGH = "high"
RISK_LEVEL_CRITICAL = "critical"

# Permission result
PERMIT = "permit"
DENY = "deny"
PROMPT = "prompt"

# Dangerous services that always require permission
DANGEROUS_SERVICES = [
    "lock.unlock",  # Unlocking doors
    "camera.snapshot",  # Camera access
    "camera.record",  # Recording
    "media_player.volume_set",  # Volume control (can be abused)
    "script.turn_on",  # Running scripts
    "automation.turn_off",  # Disabling automations
    "homeassistant.stop",  # Stopping HA
    "homeassistant.start",  # Starting HA
    "homeassistant.restart",  # Restarting HA
    "system_log.write",  # Log manipulation
    "persistent_notification.create",  # Notifications spam
]

# High-risk services
HIGH_RISK_SERVICES = [
    "lock.lock",  # Locking doors
    "lock.unlock",  # Unlocking doors
    "cover.open_cover",  # Opening covers
    "cover.close_cover",  # Closing covers
    "alarm_control_panel.alarm_disarm",  # Disarming alarm
    "alarm_control_panel.alarm_arm_home",  # Arming alarm
    "alarm_control_panel.alarm_arm_away",  # Arming alarm
    "input_boolean.turn_off",  # Disabling input booleans
    "input_number.set_value",  # Modifying input numbers
    "input_text.set_value",  # Modifying input text
    "scene.turn_on",  # Activating scenes
    "script.turn_on",  # Running scripts
    "automation.turn_off",  # Disabling automations
    "automation.turn_on",  # Enabling automations
]


@dataclass
class PermissionRule:
    """A permission rule for pattern matching."""

    pattern: str  # e.g., "light.*", "lock.front_door", "*.unlock"
    rule_type: str  # "allow" or "deny"
    description: str = ""
    priority: int = 0  # Higher priority rules are evaluated first


@dataclass
class PermissionRequest:
    """A request for user permission to execute an action."""

    request_id: str  # Unique ID for this request
    action: str  # e.g., "lock.unlock"
    target_entities: List[str]  # List of entity IDs
    reason: str  # Why this action is being taken
    risk_level: str  # RISK_LEVEL_LOW, MEDIUM, HIGH, CRITICAL
    timestamp: str  # ISO format timestamp
    expires_at: str  # ISO format timestamp (when request expires)
    is_approved: Optional[bool] = None  # User's decision (None = pending)


class PermissionChecker:
    """Checks permissions for actions and manages permission requests."""

    def __init__(
        self,
        mode: str = PERMISSION_MODE_PROMPT,
        whitelist: Optional[List[PermissionRule]] = None,
        blacklist: Optional[List[PermissionRule]] = None,
        timeout: int = 60,  # seconds
        auto_allow_list: Optional[List[str]] = None,  # Service patterns to auto-allow
        auto_deny_list: Optional[List[str]] = None,  # Service patterns to auto-deny
    ):
        self.mode = mode
        self.whitelist = whitelist or []
        self.blacklist = blacklist or []
        self.timeout = timeout
        self.auto_allow_list = auto_allow_list or []
        self.auto_deny_list = auto_deny_list or []
        self.pending_requests: Dict[str, PermissionRequest] = {}
        self.approved_actions: Dict[str, bool] = {}  # Cache user decisions
        self.request_counter = 0

    def check_action(self, action: str, entities: List[str]) -> str:
        """Check if an action is permitted.

        Args:
            action: The service action (e.g., "light.turn_on")
            entities: List of entity IDs involved in the action

        Returns:
            PERMIT, DENY, or PROMPT
        """
        _LOGGER.debug(
            "Checking permission for action '%s' on entities %s (mode: %s)",
            action,
            entities,
            self.mode,
        )

        # Auto-deny mode
        if self.mode == PERMISSION_MODE_AUTO_DENY:
            _LOGGER.debug("Auto-deny mode: denying action %s", action)
            return DENY

        # Auto-allow mode with whitelist
        if self.mode == PERMISSION_MODE_AUTO_ALLOW:
            # Check whitelist
            for rule in sorted(self.whitelist, key=lambda r: r.priority, reverse=True):
                if self.match_pattern(rule.pattern, action) or any(
                    self.match_pattern(rule.pattern, entity) for entity in entities
                ):
                    if rule.rule_type == "allow":
                        _LOGGER.debug("Whitelist allow: permitting action %s", action)
                        return PERMIT
                    elif rule.rule_type == "deny":
                        _LOGGER.debug("Whitelist deny: denying action %s", action)
                        return DENY

            # Check auto-allow list
            for pattern in self.auto_allow_list:
                if self.match_pattern(pattern, action):
                    _LOGGER.debug("Auto-allow list: permitting action %s", action)
                    return PERMIT

            # Check dangerous services
            if action in DANGEROUS_SERVICES:
                _LOGGER.debug("Dangerous service: prompting for action %s", action)
                return PROMPT

            # Check high-risk services
            if action in HIGH_RISK_SERVICES:
                _LOGGER.debug("High-risk service: prompting for action %s", action)
                return PROMPT

            _LOGGER.debug("Auto-allow mode: permitting action %s", action)
            return PERMIT  # Default to allow in auto_allow mode

        # Prompt mode - always check
        # Check blacklist first
        for rule in sorted(self.blacklist, key=lambda r: r.priority, reverse=True):
            if self.match_pattern(rule.pattern, action) or any(
                self.match_pattern(rule.pattern, entity) for entity in entities
            ):
                if rule.rule_type == "deny":
                    _LOGGER.debug("Blacklist deny: denying action %s", action)
                    return DENY

        # Check whitelist
        for rule in sorted(self.whitelist, key=lambda r: r.priority, reverse=True):
            if self.match_pattern(rule.pattern, action) or any(
                self.match_pattern(rule.pattern, entity) for entity in entities
            ):
                if rule.rule_type == "allow":
                    _LOGGER.debug("Whitelist allow: permitting action %s", action)
                    return PERMIT
                elif rule.rule_type == "deny":
                    _LOGGER.debug("Whitelist deny: denying action %s", action)
                    return DENY

        # Check auto-deny list
        for pattern in self.auto_deny_list:
            if self.match_pattern(pattern, action):
                _LOGGER.debug("Auto-deny list: denying action %s", action)
                return DENY

        # Default to prompt in prompt mode
        _LOGGER.debug("Prompt mode: requesting permission for action %s", action)
        return PROMPT

    def match_pattern(self, pattern: str, target: str) -> bool:
        """Match a pattern against a target.

        Supports wildcards: light.*, *.lock, light.kitchen

        Args:
            pattern: The pattern to match (e.g., "light.*")
            target: The target string to match against (e.g., "light.living_room")

        Returns:
            True if the pattern matches, False otherwise
        """
        # Convert pattern to regex
        # Escape special chars except *
        regex_pattern = "^" + pattern.replace(".", r"\.").replace("*", ".*") + "$"
        match = re.match(regex_pattern, target)
        if match:
            _LOGGER.debug("Pattern '%s' matches target '%s'", pattern, target)
        else:
            _LOGGER.debug("Pattern '%s' does not match target '%s'", pattern, target)
        return bool(match)

    def create_permission_request(
        self, action: str, entities: List[str], reason: str
    ) -> PermissionRequest:
        """Create a permission request for user approval.

        Args:
            action: The service action (e.g., "lock.unlock")
            entities: List of entity IDs involved
            reason: Why this action is being taken

        Returns:
            PermissionRequest object
        """
        self.request_counter += 1
        request_id = f"perm_{self.request_counter}_{int(datetime.now().timestamp())}"

        # Determine risk level
        risk_level = self._calculate_risk_level(action, entities)

        # Calculate expiration
        expires_at = datetime.now() + timedelta(seconds=self.timeout)

        request = PermissionRequest(
            request_id=request_id,
            action=action,
            target_entities=entities,
            reason=reason,
            risk_level=risk_level,
            timestamp=datetime.now().isoformat(),
            expires_at=expires_at.isoformat(),
        )

        self.pending_requests[request_id] = request
        _LOGGER.info(
            "Created permission request %s for action %s (risk: %s)",
            request_id,
            action,
            risk_level,
        )

        return request

    def _calculate_risk_level(self, action: str, entities: List[str]) -> str:
        """Calculate risk level for an action.

        Args:
            action: The service action
            entities: List of entity IDs

        Returns:
            Risk level string (LOW, MEDIUM, HIGH, or CRITICAL)
        """
        # Critical: services that can stop/restart HA
        if action in ["homeassistant.stop", "homeassistant.restart"]:
            return RISK_LEVEL_CRITICAL

        # High: security-related services
        if action in HIGH_RISK_SERVICES:
            return RISK_LEVEL_HIGH

        # Medium: services that affect multiple entities
        if len(entities) > 3:
            return RISK_LEVEL_MEDIUM

        # Low: single entity, non-critical service
        return RISK_LEVEL_LOW

    def approve_request(self, request_id: str) -> bool:
        """Approve a pending permission request.

        Args:
            request_id: The ID of the request to approve

        Returns:
            True if approved, False if request not found
        """
        if request_id in self.pending_requests:
            request = self.pending_requests[request_id]
            request.is_approved = True
            # Cache the decision for similar future actions
            self.approved_actions[request.action] = True
            # Remove from pending
            del self.pending_requests[request_id]
            _LOGGER.info("Approved permission request %s for action %s", request_id, request.action)
            return True
        _LOGGER.warning("Permission request %s not found", request_id)
        return False

    def deny_request(self, request_id: str) -> bool:
        """Deny a pending permission request.

        Args:
            request_id: The ID of the request to deny

        Returns:
            True if denied, False if request not found
        """
        if request_id in self.pending_requests:
            request = self.pending_requests[request_id]
            request.is_approved = False
            # Cache the decision
            self.approved_actions[request.action] = False
            # Remove from pending
            del self.pending_requests[request_id]
            _LOGGER.info("Denied permission request %s for action %s", request_id, request.action)
            return True
        _LOGGER.warning("Permission request %s not found", request_id)
        return False

    def get_pending_requests(self) -> List[PermissionRequest]:
        """Get all pending permission requests.

        Returns:
            List of pending PermissionRequest objects
        """
        # Clean up expired requests
        now = datetime.now()
        expired = [
            rid
            for rid, req in self.pending_requests.items()
            if datetime.fromisoformat(req.expires_at) < now
        ]
        for rid in expired:
            _LOGGER.info("Expired permission request %s", rid)
            del self.pending_requests[rid]

        pending = list(self.pending_requests.values())
        _LOGGER.debug("Found %d pending permission requests", len(pending))
        return pending

    def get_risk_description(self, risk_level: str) -> str:
        """Get human-readable description for risk level.

        Args:
            risk_level: The risk level string

        Returns:
            Human-readable description
        """
        descriptions = {
            RISK_LEVEL_LOW: "Low Risk - Minor effect",
            RISK_LEVEL_MEDIUM: "Medium Risk - Affects multiple entities",
            RISK_LEVEL_HIGH: "High Risk - Security or automation impact",
            RISK_LEVEL_CRITICAL: "Critical Risk - Can stop/restart Home Assistant",
        }
        return descriptions.get(risk_level, "Unknown Risk")

    def is_action_approved(self, action: str) -> Optional[bool]:
        """Check if an action has a cached approval decision.

        Args:
            action: The service action to check

        Returns:
            True if approved, False if denied, None if no cached decision
        """
        return self.approved_actions.get(action, None)
