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

# Extended permission modes (E3 - Fine-Grained Permissions)
PERMISSION_MODE_CONTEXT_AWARE = "context_aware"  # Consider time, entity scope
PERMISSION_MODE_AREA_BASED = "area_based"  # Area-specific permissions
PERMISSION_MODE_ENTITY_LEVEL = "entity_level"  # Entity-level granular control

# Risk levels
RISK_LEVEL_LOW = "low"
RISK_LEVEL_MEDIUM = "medium"
RISK_LEVEL_HIGH = "high"
RISK_LEVEL_CRITICAL = "critical"

# Permission scopes (E3)
SCOPE_GLOBAL = "global"  # Applies to all entities
SCOPE_DOMAIN = "domain"  # Applies to a domain (e.g., all lights)
SCOPE_AREA = "area"  # Applies to an area
SCOPE_ENTITY = "entity"  # Applies to a specific entity

# Permission levels (E3)
PERMISSION_LEVEL_READ = "read"  # Can read state only
PERMISSION_LEVEL_WRITE = "write"  # Can modify state
PERMISSION_LEVEL_ADMIN = "admin"  # Full control including dangerous operations
PERMISSION_LEVEL_CUSTOM = "custom"  # Custom permission rules

# Permission result
PERMIT = "permit"
DENY = "deny"
PROMPT = "prompt"

# Time-based permission rules
TIME_RULE_ALL_DAY = "all_day"  # Available all day
TIME_RULE_BUSINESS_HOURS = "business_hours"  # 9 AM - 5 PM
TIME_RULE_NIGHTTIME = "nighttime"  # 10 PM - 6 AM
TIME_RULE_WEEKDAYS = "weekdays"  # Monday - Friday
TIME_RULE_WEEKENDS = "weekends"  # Saturday - Sunday
TIME_RULE_CUSTOM = "custom"  # Custom time range

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


# === E3: Fine-Grained Permission Controls ===

@dataclass
class FineGrainedPermission:
    """A fine-grained permission with scope, level, and time-based rules.
    
    This extends the basic PermissionRule with more granular control.
    """
    # Identifier
    id: str = ""  # Unique ID for this permission
    name: str = ""  # Human-readable name
    
    # Scope (E3)
    scope: str = SCOPE_GLOBAL  # SCOPE_GLOBAL, SCOPE_DOMAIN, SCOPE_AREA, SCOPE_ENTITY
    scope_value: str = ""  # e.g., "light", "living_room", "light.kitchen"
    
    # Permission level (E3)
    level: str = PERMISSION_LEVEL_WRITE  # PERMISSION_LEVEL_READ, WRITE, ADMIN, CUSTOM
    custom_actions: List[str] = field(default_factory=list)  # Specific actions allowed
    
    # Time-based rules (E3)
    time_rule: str = TIME_RULE_ALL_DAY  # TIME_RULE_ALL_DAY, BUSINESS_HOURS, etc.
    time_start: Optional[str] = None  # Custom start time (e.g., "09:00")
    time_end: Optional[str] = None  # Custom end time (e.g., "17:00")
    allowed_days: List[int] = field(default_factory=list)  # 0=Monday, 6=Sunday
    
    # Entity patterns (E3)
    entity_patterns: List[str] = field(default_factory=list)  # Specific entity patterns
    
    # Area patterns (E3)
    area_patterns: List[str] = field(default_factory=list)  # Area name patterns
    
    # Rule type
    rule_type: str = "allow"  # "allow" or "deny"
    
    # Metadata
    description: str = ""
    priority: int = 0  # Higher priority rules evaluated first
    enabled: bool = True
    
    # Temporary permissions (E3)
    is_temporary: bool = False
    granted_at: Optional[str] = None  # ISO timestamp
    expires_at: Optional[str] = None  # ISO timestamp
    max_uses: Optional[int] = None
    uses_remaining: int = 0


@dataclass
class TimePermissionRule:
    """Time-based permission rule for controlling when actions are allowed."""
    
    rule_id: str = ""
    rule_name: str = ""
    time_rule: str = TIME_RULE_ALL_DAY
    start_time: Optional[str] = None  # "09:00"
    end_time: Optional[str] = None  # "17:00"
    allowed_days: List[int] = field(default_factory=list)  # 0=Monday, 6=Sunday
    timezone: str = "UTC"
    enabled: bool = True
    description: str = ""


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
    """Checks permissions for actions and manages permission requests.
    
    Extended with fine-grained permission controls (E3):
    - Entity-level permissions with scopes
    - Time-based permission rules
    - Permission levels (read/write/admin)
    - Temporary permission grants
    """

    def __init__(
        self,
        mode: str = PERMISSION_MODE_PROMPT,
        whitelist: Optional[List[PermissionRule]] = None,
        blacklist: Optional[List[PermissionRule]] = None,
        timeout: int = 60,  # seconds
        auto_allow_list: Optional[List[str]] = None,  # Service patterns to auto-allow
        auto_deny_list: Optional[List[str]] = None,  # Service patterns to auto-deny
        # E3: Fine-grained permissions
        fine_grained_permissions: Optional[List[FineGrainedPermission]] = None,
        time_permission_rules: Optional[List[TimePermissionRule]] = None,
        enable_time_based_permissions: bool = False,
        enable_scope_based_permissions: bool = False,
        enable_temporary_permissions: bool = False,
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
        
        # E3: Fine-grained permission controls
        self.fine_grained_permissions = fine_grained_permissions or []
        self.time_permission_rules = time_permission_rules or []
        self.enable_time_based_permissions = enable_time_based_permissions
        self.enable_scope_based_permissions = enable_scope_based_permissions
        self.enable_temporary_permissions = enable_temporary_permissions
        self.temporary_permissions: Dict[str, FineGrainedPermission] = {}
        self.permission_grant_history: List[Dict] = []

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

    # === E3: Fine-Grained Permission Controls ===

    def check_action_with_fine_grained_permissions(
        self,
        action: str,
        entities: List[str],
        current_time: Optional[str] = None,
        user_area: Optional[str] = None,
        user_permission_level: str = PERMISSION_LEVEL_WRITE,
    ) -> str:
        """Check permissions with fine-grained controls (E3 extension).
        
        This extends the basic check_action with:
        - Time-based permission rules
        - Scope-based permissions (area, domain, entity)
        - Permission levels (read/write/admin)
        - Temporary permissions
        
        Args:
            action: The service action (e.g., "light.turn_on")
            entities: List of entity IDs involved
            current_time: Optional current time (ISO format, defaults to now)
            user_area: Optional area the user is in
            user_permission_level: User's permission level
            
        Returns:
            PERMIT, DENY, or PROMPT
        """
        # First, try basic permission check
        basic_result = self.check_action(action, entities)
        
        # If basic check denies, respect that
        if basic_result == DENY:
            return DENY
        
        # Apply fine-grained permissions if enabled
        if self.enable_time_based_permissions or self.enable_scope_based_permissions:
            # Check time-based rules
            if self.enable_time_based_permissions:
                time_result = self._check_time_based_permission(action, entities, current_time)
                if time_result == DENY:
                    return DENY
            
            # Check scope-based rules
            if self.enable_scope_based_permissions:
                scope_result = self._check_scope_based_permission(
                    action, entities, user_area, user_permission_level
                )
                if scope_result == DENY:
                    return DENY
                elif scope_result == PERMIT:
                    return PERMIT
            
            # Check temporary permissions
            if self.enable_temporary_permissions:
                temp_result = self._check_temporary_permissions(action, entities)
                if temp_result is not None:
                    return temp_result
        
        # Return basic check result
        return basic_result

    def _check_time_based_permission(
        self,
        action: str,
        entities: List[str],
        current_time: Optional[str] = None
    ) -> str:
        """Check time-based permission rules.
        
        Args:
            action: The service action
            entities: List of entity IDs
            current_time: Optional current time (ISO format)
            
        Returns:
            PERMIT, DENY, or None (no rule matched)
        """
        if not self.time_permission_rules:
            return None
        
        # Parse current time
        if current_time is None:
            now = datetime.now()
        else:
            try:
                now = datetime.fromisoformat(current_time)
            except (ValueError, TypeError):
                return None
        
        # Check each time rule
        for rule in self.time_permission_rules:
            if not rule.enabled:
                continue
            
            # Check if current time is within allowed window
            if not self._is_time_within_rule(now, rule):
                _LOGGER.debug(
                    "Time-based permission denied for action %s: outside allowed window",
                    action
                )
                return DENY
        
        return None

    def _is_time_within_rule(
        self,
        current_time: datetime,
        rule: TimePermissionRule
    ) -> bool:
        """Check if current time is within a permission rule's allowed window.
        
        Args:
            current_time: Current datetime
            rule: The time permission rule to check
            
        Returns:
            True if time is within allowed window
        """
        # Check allowed days
        if rule.allowed_days:
            # Python: Monday=0, Sunday=6
            # Home Assistant: Sunday=0, Saturday=5
            # Convert HA day to Python day
            current_python_day = (current_time.weekday() + 1) % 7
            if current_python_day not in rule.allowed_days:
                return False
        
        # Check time range
        if rule.start_time and rule.end_time:
            try:
                current_time_only = current_time.strftime("%H:%M")
                if current_time_only < rule.start_time or current_time_only > rule.end_time:
                    return False
            except (ValueError, TypeError):
                pass
        
        return True

    def _check_scope_based_permission(
        self,
        action: str,
        entities: List[str],
        user_area: Optional[str] = None,
        user_permission_level: str = PERMISSION_LEVEL_WRITE,
    ) -> Optional[str]:
        """Check scope-based permission rules.
        
        Args:
            action: The service action
            entities: List of entity IDs
            user_area: Optional current area
            user_permission_level: User's permission level
            
        Returns:
            PERMIT, DENY, or None (no rule matched)
        """
        if not self.fine_grained_permissions:
            return None
        
        # Check each fine-grained permission
        for perm in sorted(self.fine_grained_permissions, key=lambda p: p.priority, reverse=True):
            if not perm.enabled:
                continue
            
            # Check if permission applies to this action/entities
            if self._permission_applies_to_action(perm, action, entities, user_area, user_permission_level):
                if perm.rule_type == "allow":
                    return PERMIT
                elif perm.rule_type == "deny":
                    return DENY
        
        return None

    def _permission_applies_to_action(
        self,
        perm: FineGrainedPermission,
        action: str,
        entities: List[str],
        user_area: Optional[str] = None,
        user_permission_level: str = PERMISSION_LEVEL_WRITE,
    ) -> bool:
        """Check if a fine-grained permission applies to an action.
        
        Args:
            perm: The fine-grained permission to check
            action: The service action
            entities: List of entity IDs
            user_area: Optional current area
            user_permission_level: User's permission level
            
        Returns:
            True if permission applies
        """
        # Check permission level
        if perm.level == PERMISSION_LEVEL_READ and user_permission_level != PERMISSION_LEVEL_READ:
            # Read-only permission doesn't apply to write actions
            if "." in action:
                _, service = action.split(".", 1)
                if not service.startswith("get_") and service not in ["turn_on", "turn_off", "toggle"]:
                    return False
        
        if perm.level == PERMISSION_LEVEL_ADMIN and user_permission_level != PERMISSION_LEVEL_ADMIN:
            # Admin permission required for dangerous operations
            if action in ["homeassistant.stop", "homeassistant.restart", "alarm_control_panel.alarm_disarm"]:
                return False
        
        # Check scope
        if perm.scope == SCOPE_DOMAIN:
            # Domain scope: e.g., "light" matches "light.turn_on"
            if perm.scope_value in action:
                return True
        
        elif perm.scope == SCOPE_ENTITY:
            # Entity scope: e.g., "light.kitchen" matches entity
            for entity in entities:
                if entity == perm.scope_value or entity.startswith(perm.scope_value + "."):
                    return True
        
        elif perm.scope == SCOPE_AREA:
            # Area scope: check if entity is in the area
            if user_area and user_area.lower() in perm.scope_value.lower():
                return True
            
            # Check entity patterns for area association
            for pattern in perm.entity_patterns:
                for entity in entities:
                    if self.match_pattern(pattern, entity):
                        return True
        
        elif perm.scope == SCOPE_GLOBAL:
            # Global scope: applies to everything
            return True
        
        # Check entity patterns
        if perm.entity_patterns:
            for pattern in perm.entity_patterns:
                for entity in entities:
                    if self.match_pattern(pattern, entity):
                        return True
        
        # Check custom actions
        if perm.custom_actions and perm.level == PERMISSION_LEVEL_CUSTOM:
            return action in perm.custom_actions
        
        return False

    def grant_temporary_permission(
        self,
        action: str,
        entities: List[str],
        expires_at: Optional[str] = None,
        max_uses: int = 1,
        reason: str = ""
    ) -> str:
        """Grant a temporary permission for specific action(s).
        
        Args:
            action: The service action to allow
            entities: List of entity IDs
            expires_at: Optional expiration time (ISO format)
            max_uses: Maximum number of uses (default 1)
            reason: Reason for the temporary permission
            
        Returns:
            Permission ID
        """
        import uuid
        
        permission_id = f"temp_{uuid.uuid4().hex[:8]}"
        
        temp_perm = FineGrainedPermission(
            id=permission_id,
            name=f"Temporary: {action}",
            scope=SCOPE_ENTITY,
            scope_value=action,
            level=PERMISSION_LEVEL_WRITE,
            entity_patterns=entities,
            rule_type="allow",
            is_temporary=True,
            granted_at=datetime.now().isoformat(),
            expires_at=expires_at,
            max_uses=max_uses,
            uses_remaining=max_uses,
            description=reason or f"Temporary permission for {action}"
        )
        
        self.temporary_permissions[permission_id] = temp_perm
        self.permission_grant_history.append({
            "permission_id": permission_id,
            "action": action,
            "entities": entities,
            "granted_at": temp_perm.granted_at,
            "expires_at": expires_at,
            "reason": reason
        })
        
        _LOGGER.info(
            "Granted temporary permission %s for action %s on entities %s",
            permission_id,
            action,
            entities
        )
        
        return permission_id

    def revoke_temporary_permission(self, permission_id: str) -> bool:
        """Revoke a temporary permission.
        
        Args:
            permission_id: The ID of the temporary permission to revoke
            
        Returns:
            True if revoked, False if not found
        """
        if permission_id in self.temporary_permissions:
            del self.temporary_permissions[permission_id]
            _LOGGER.info("Revoked temporary permission %s", permission_id)
            return True
        return False

    def use_temporary_permission(self, permission_id: str) -> bool:
        """Use a temporary permission (decrements use counter).
        
        Args:
            permission_id: The ID of the temporary permission
            
        Returns:
            True if used successfully, False if expired or max uses reached
        """
        if permission_id not in self.temporary_permissions:
            return False
        
        temp_perm = self.temporary_permissions[permission_id]
        
        # Check expiration
        if temp_perm.expires_at:
            try:
                expires = datetime.fromisoformat(temp_perm.expires_at)
                if datetime.now() > expires:
                    _LOGGER.warning("Temporary permission %s is expired", permission_id)
                    del self.temporary_permissions[permission_id]
                    return False
            except (ValueError, TypeError):
                pass
        
        # Check uses
        if temp_perm.max_uses is not None:
            if temp_perm.uses_remaining <= 0:
                _LOGGER.warning("Temporary permission %s has no uses remaining", permission_id)
                del self.temporary_permissions[permission_id]
                return False
            temp_perm.uses_remaining -= 1
        
        return True

    def add_fine_grained_permission(self, permission: FineGrainedPermission) -> str:
        """Add a fine-grained permission.
        
        Args:
            permission: The fine-grained permission to add
            
        Returns:
            Permission ID
        """
        if not permission.id:
            import uuid
            permission.id = f"fgperm_{uuid.uuid4().hex[:8]}"
        
        self.fine_grained_permissions.append(permission)
        _LOGGER.info(
            "Added fine-grained permission %s: %s %s on %s",
            permission.id,
            permission.rule_type,
            permission.scope,
            permission.scope_value
        )
        
        return permission.id

    def remove_fine_grained_permission(self, permission_id: str) -> bool:
        """Remove a fine-grained permission.
        
        Args:
            permission_id: The ID of the permission to remove
            
        Returns:
            True if removed, False if not found
        """
        for i, perm in enumerate(self.fine_grained_permissions):
            if perm.id == permission_id:
                del self.fine_grained_permissions[i]
                _LOGGER.info("Removed fine-grained permission %s", permission_id)
                return True
        return False

    def add_time_permission_rule(self, rule: TimePermissionRule) -> str:
        """Add a time-based permission rule.
        
        Args:
            rule: The time permission rule to add
            
        Returns:
            Rule ID
        """
        if not rule.rule_id:
            import uuid
            rule.rule_id = f"time_{uuid.uuid4().hex[:8]}"
        
        self.time_permission_rules.append(rule)
        _LOGGER.info("Added time permission rule %s: %s", rule.rule_id, rule.rule_name)
        
        return rule.rule_id

    def get_permission_summary(self) -> Dict[str, Any]:
        """Get a summary of all permissions.
        
        Returns:
            Dictionary with permission summary
        """
        return {
            "mode": self.mode,
            "whitelist_count": len(self.whitelist),
            "blacklist_count": len(self.blacklist),
            "fine_grained_permissions_count": len(self.fine_grained_permissions),
            "time_rules_count": len(self.time_permission_rules),
            "temporary_permissions_count": len(self.temporary_permissions),
            "pending_requests_count": len(self.pending_requests),
            "enable_time_based": self.enable_time_based_permissions,
            "enable_scope_based": self.enable_scope_based_permissions,
            "enable_temporary": self.enable_temporary_permissions,
        }
