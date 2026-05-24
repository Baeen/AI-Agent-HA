## Enhancement #4: Permission / Prompt System

### Problem Statement
The AI agent can execute Home Assistant service calls automatically. There is no permission gating - any AI-generated action is executed without user confirmation. This is a security risk for sensitive actions like unlocking doors, disabling alarms, or modifying critical automations.

### Solution Architecture

```
┌──────────────────────────────────────────────────────┐
│              permissions.py (NEW)                    │
│                                                      │
│  ┌─────────────────┐  ┌────────────────────────┐    │
│  │ PermissionRule  │  │ PermissionRequest      │    │
│  │                 │  │                        │    │
│  │ - pattern: str  │  │ - action: str          │    │
│  │ - rule_type:    │  │ - target_entities: []  │    │
│  │   allow|deny    │  │ - reason: str          │    │
│  │ - description   │  │ - risk_level: str      │    │
│  │ - priority: int │  │ - timestamp: str       │    │
│  └─────────────────┘  │ - request_id: str      │    │
│                       └────────────────────────┘    │
│  ┌──────────────────────────────────────────────┐   │
│  │           PermissionChecker                  │   │
│  │                                              │   │
│  │ - mode: prompt|auto_allow|auto_deny          │   │
│  │ - whitelist: List[PermissionRule]            │   │
│  │ - blacklist: List[PermissionRule]            │   │
│  │ - timeout: int (seconds)                     │   │
│  │                                              │   │
│  │ + check_action(action, entities)             │   │
│  │   → PERMIT | DENY | PROMPT                   │   │
│  │                                              │   │
│  │ + create_permission_request(action,          │   │
│  │     entities) → PermissionRequest            │   │
│  │                                              │   │
│  │ + match_pattern(pattern, entity) → bool      │   │
│  │   (supports wildcards: light.*, *.lock)      │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
         │
         │ used by
         ▼
┌──────────────────────────────────────────────────────┐
│                  agent.py                            │
│                                                      │
│  process_query() → AI response parsed                │
│         │                                            │
│         ▼                                            │
│  If response contains service calls:                 │
│         │                                            │
│         ▼                                            │
│  for each action:                                    │
│    result = permission_checker.check_action(         │
│      action, entities                                │
│    )                                                 │
│         │                                            │
│    ┌────┼────────────────────────┐                   │
│    ▼    ▼                        ▼                   │
│  PERMIT  DENY                  PROMPT                │
│  execute  skip                 return                │
│  directly                     permission_request     │
│                               to frontend            │
└──────────────────────────────────────────────────────┘
         │
         │ permission_request response
         ▼
┌──────────────────────────────────────────────────────┐
│              ai_agent_ha-panel.js                    │
│                                                      │
│  _handleLlamaResponse() detects:                     │
│    request_type === 'permission_request'             │
│         │                                            │
│         ▼                                            │
│  ┌──────────────────────────────────────┐            │
│  │ Permission Dialog Modal              │            │
│  │                                      │            │
│  │  Action: "Unlock front door"         │            │
│  │  Entities: lock.front_door           │            │
│  │  Risk: ⚠️ HIGH                        │            │
│  │  Reason: "User requested to unlock"  │            │
│  │                                      │            │
│  │  [Approve] [Deny] [Always Allow]    │            │
│  └──────────────────────────────────────┘            │
└──────────────────────────────────────────────────────┘
```

### Data Flow for Permission Gating

```
sequenceDiagram
    participant U as User
    participant F as Frontend (panel.js)
    participant A as Agent (agent.py)
    participant P as PermissionChecker
    participant AI as AI Provider

    U->>F: "Unlock the front door"
    F->>A: hass.callService('query', {prompt: "Unlock..."})
    A->>AI: Send prompt with HA state
    AI-->>A: Response: {action: "lock.unlock", entities: ["lock.front_door"]}
    A->>P: check_action("lock.unlock", ["lock.front_door"])
    Note over P: Check blacklist: "lock.*" → not in blacklist<br>Check whitelist: empty → no auto-allow<br>Mode: "prompt" → return PROMPT
    P-->>A: PROMPT
    A-->>F: fire_event('ai_agent_ha_response', {request_type: 'permission_request', ...})
    F->>F: Show permission dialog
    U->>F: Clicks [Approve]
    F->>A: hass.callService('query', {approved_action: ..., approve: true})
    A->>A: Execute lock.unlock
    A-->>F: fire_event('ai_agent_ha_response', {request_type: 'action_result', ...})
    F-->>U: Show "Door unlocked successfully"
```

### New File: [`permissions.py`](custom_components/ai_agent_ha/permissions.py)

```python
"""Permission system for AI Agent HA actions.

Provides a configurable permission checker that gates AI-initiated service calls
behind user approval prompts for safety-sensitive operations.
"""

from __future__ import annotations

import fnmatch
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class PermissionResult(Enum):
    """Result of a permission check."""

    PERMIT = "permit"
    DENY = "deny"
    PROMPT = "prompt"


class RiskLevel(Enum):
    """Risk level for an action."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PermissionRule:
    """A rule for allowing or denying actions based on pattern matching.

    Attributes:
        pattern: Entity or service pattern (supports wildcards: *, ?).
            Examples: "light.*", "*.unlock", "switch.kitchen_*", "light.living_room"
        rule_type: Whether this rule ALLOWs or DENYs matching actions.
        description: Human-readable explanation of the rule.
        priority: Higher priority rules are evaluated first.
        enabled: Whether this rule is active.
    """

    pattern: str
    rule_type: str  # "allow" or "deny"
    description: str = ""
    priority: int = 0
    enabled: bool = True

    def matches(self, target: str) -> bool:
        """Check if a target string matches this rule's pattern.

        Supports Unix-style wildcards: * matches everything, ? matches single char.

        Args:
            target: The entity ID or service call to check.

        Returns:
            True if the target matches the pattern.
        """
        if not self.enabled:
            return False
        return fnmatch.fnmatch(target.lower(), self.pattern.lower())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "pattern": self.pattern,
            "rule_type": self.rule_type,
            "description": self.description,
            "priority": self.priority,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PermissionRule:
        """Deserialize from dictionary."""
        return cls(
            pattern=data.get("pattern", ""),
            rule_type=data.get("rule_type", "deny"),
            description=data.get("description", ""),
            priority=data.get("priority", 0),
            enabled=data.get("enabled", True),
        )


@dataclass
class PermissionRequest:
    """A permission request sent to the user for approval.

    Attributes:
        request_id: Unique ID for tracking this request.
        action: The service call being requested (e.g., "lock.unlock").
        target_entities: List of entity IDs affected.
        reason: Why the AI wants to perform this action.
        risk_level: Assessed risk level.
        timestamp: When the request was created.
        expires_at: When the request times out.
        metadata: Additional context about the request.
    """

    request_id: str = ""
    action: str = ""
    target_entities: List[str] = field(default_factory=list)
    reason: str = ""
    risk_level: str = "medium"
    timestamp: str = ""
    expires_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for frontend consumption."""
        return {
            "request_id": self.request_id,
            "action": self.action,
            "target_entities": self.target_entities,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }

    def is_expired(self) -> bool:
        """Check if this permission request has timed out."""
        if not self.expires_at:
            return False
        return datetime.utcnow().isoformat() > self.expires_at


class PermissionChecker:
    """Checks whether AI-initiated actions require user permission.

    Evaluation order:
      1. Check blacklist (deny rules) → if match, DENY immediately.
      2. Check whitelist (allow rules) → if match, PERMIT immediately.
      3. If mode is "auto_allow" → PERMIT.
      4. If mode is "auto_deny" → DENY.
      5. Otherwise (mode "prompt") → PROMPT.

    Usage:
        checker = PermissionChecker(mode="prompt", timeout=60)
        checker.add_whitelist_rule(PermissionRule("light.*", "allow"))
        checker.add_blacklist_rule(PermissionRule("lock.*", "deny"))
        result = checker.check_action("light.turn_on", ["light.kitchen"])
    """

    # Predefined risk levels for common service domains
    RISK_LEVELS = {
        "lock": RiskLevel.HIGH,
        "alarm_control_panel": RiskLevel.HIGH,
        "automation": RiskLevel.MEDIUM,
        "script": RiskLevel.MEDIUM,
        "scene": RiskLevel.LOW,
        "light": RiskLevel.LOW,
        "switch": RiskLevel.LOW,
        "climate": RiskLevel.LOW,
        "fan": RiskLevel.LOW,
        "cover": RiskLevel.MEDIUM,
        "media_player": RiskLevel.LOW,
        "vacuum": RiskLevel.LOW,
        "camera": RiskLevel.MEDIUM,
        "notify": RiskLevel.LOW,
        "input_boolean": RiskLevel.LOW,
        "input_number": RiskLevel.MEDIUM,
        "group": RiskLevel.LOW,
        "zone": RiskLevel.LOW,
        "device_tracker": RiskLevel.MEDIUM,
    }

    # Actions that are always safe (no permission needed)
    DEFAULT_WHITELIST = [
        PermissionRule("light.turn_on", "allow", "Turning lights on is low risk", priority=100),
        PermissionRule("light.turn_off", "allow", "Turning lights off is low risk", priority=100),
        PermissionRule("scene.turn_on", "allow", "Activating scenes is low risk", priority=90),
        PermissionRule("notify.*", "allow", "Sending notifications is low risk", priority=90),
    ]

    # Actions that always require permission
    DEFAULT_BLACKLIST = [
        PermissionRule("lock.unlock", "deny", "Unlocking doors requires permission", priority=100),
        PermissionRule("lock.open", "deny", "Opening locks requires permission", priority=100),
        PermissionRule("alarm_control_panel.alarm_disarm", "deny", "Disarming alarms requires permission", priority=100),
        PermissionRule("automation.turn_off", "deny", "Disabling automations requires permission", priority=80),
        PermissionRule("script.turn_off", "deny", "Disabling scripts requires permission", priority=80),
    ]

    def __init__(
        self,
        mode: str = "prompt",
        timeout: int = 60,
        whitelist: Optional[List[PermissionRule]] = None,
        blacklist: Optional[List[PermissionRule]] = None,
    ):
        """Initialize the permission checker.

        Args:
            mode: One of "prompt", "auto_allow", or "auto_deny".
            timeout: Seconds before a permission request expires.
            whitelist: Custom allow rules (appended to defaults).
            blacklist: Custom deny rules (appended to defaults).
        """
        self.mode = mode
        self.timeout = timeout

        self.whitelist: List[PermissionRule] = list(self.DEFAULT_WHITELIST)
        if whitelist:
            self.whitelist.extend(whitelist)

        self.blacklist: List[PermissionRule] = list(self.DEFAULT_BLACKLIST)
        if blacklist:
            self.blacklist.extend(blacklist)

        # Sort rules by priority (descending)
        self.whitelist.sort(key=lambda r: r.priority, reverse=True)
        self.blacklist.sort(key=lambda r: r.priority, reverse=True)

        # Track pending requests
        self._pending_requests: Dict[str, PermissionRequest] = {}

        # Learning: track which actions user has "always allowed"
        self._learned_allows: List[PermissionRule] = []

    def get_risk_level(self, domain: str, action: str = "") -> RiskLevel:
        """Determine the risk level for a service domain and action.

        Args:
            domain: The Home Assistant domain (e.g., "light", "lock").
            action: The specific service action (e.g., "turn_on").

        Returns:
            RiskLevel enum value.
        """
        # Check for high-risk actions
        high_risk_actions = [
            "unlock", "open", "disarm", "disable", "delete", "remove",
            "turn_off"  # for automations/scripts only
        ]

        if domain in ("automation", "script") and action == "turn_off":
            return RiskLevel.HIGH

        if any(risk_action in action for risk_action in high_risk_actions):
            return RiskLevel.HIGH

        return self.RISK_LEVELS.get(domain, RiskLevel.MEDIUM)

    def check_action(
        self, action: str, entities: List[str]
    ) -> PermissionResult:
        """Check if an action on entities requires permission.

        Args:
            action: The service call (e.g., "light.turn_on", "lock.unlock").
            entities: List of target entity IDs.

        Returns:
            PermissionResult indicating PERMIT, DENY, or PROMPT.
        """
        # If mode is auto_deny, deny everything not explicitly whitelisted
        if self.mode == "auto_deny":
            for rule in self.whitelist:
                if rule.matches(action) or any(
                    rule.matches(e) for e in entities
                ):
                    return PermissionResult.PERMIT
            return PermissionResult.DENY

        # Check blacklist first (deny always wins)
        for rule in self.blacklist:
            if rule.matches(action) or any(
                rule.matches(e) for e in entities
            ):
                _LOGGER.debug(
                    "Action %s on %s DENIED by blacklist rule: %s",
                    action,
                    entities,
                    rule.pattern,
                )
                return PermissionResult.DENY

        # Check learned allows
        for rule in self._learned_allows:
            if rule.matches(action) or any(
                rule.matches(e) for e in entities
            ):
                _LOGGER.debug(
                    "Action %s on %s PERMITTED by learned rule: %s",
                    action,
                    entities,
                    rule.pattern,
                )
                return PermissionResult.PERMIT

        # Check whitelist
        for rule in self.whitelist:
            if rule.matches(action) or any(
                rule.matches(e) for e in entities
            ):
                _LOGGER.debug(
                    "Action %s on %s PERMITTED by whitelist rule: %s",
                    action,
                    entities,
                    rule.pattern,
                )
                return PermissionResult.PERMIT

        # If mode is auto_allow, permit everything not blacklisted
        if self.mode == "auto_allow":
            return PermissionResult.PERMIT

        # Default: prompt the user
        _LOGGER.debug(
            "Action %s on %s requires user PROMPT",
            action,
            entities,
        )
        return PermissionResult.PROMPT

    def create_permission_request(
        self,
        action: str,
        entities: List[str],
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PermissionRequest:
        """Create a permission request for the frontend.

        Args:
            action: The service call being requested.
            entities: Affected entity IDs.
            reason: Why the AI wants to perform this action.
            metadata: Additional context.

        Returns:
            A PermissionRequest ready for serialization.
        """
        # Determine domain for risk assessment
        domain = action.split(".")[0] if "." in action else "unknown"
        action_name = action.split(".")[1] if "." in action else action

        risk = self.get_risk_level(domain, action_name)

        request = PermissionRequest(
            action=action,
            target_entities=entities,
            reason=reason or f"AI agent wants to call {action}",
            risk_level=risk.value,
            metadata=metadata or {},
        )

        # Set expiration
        from datetime import timedelta

        expires = datetime.utcnow() + timedelta(seconds=self.timeout)
        request.expires_at = expires.isoformat()

        # Track pending request
        self._pending_requests[request.request_id] = request

        return request

    def approve_request(self, request_id: str, always_allow: bool = False) -> bool:
        """Approve a pending permission request.

        Args:
            request_id: The request to approve.
            always_allow: If True, add a learned allow rule for future.

        Returns:
            True if approved successfully, False if request not found/expired.
        """
        request = self._pending_requests.get(request_id)
        if not request:
            return False
        if request.is_expired():
            del self._pending_requests[request_id]
            return False

        if always_allow:
            # Learn this pattern for future
            domain = request.action.split(".")[0] if "." in request.action else "*"
            learned_rule = PermissionRule(
                pattern=f"{domain}.*",
                rule_type="allow",
                description=f"User always allowed {request.action}",
                priority=50,
            )
            self._learned_allows.append(learned_rule)
            _LOGGER.info(
                "Learned allow rule: %s for action %s",
                learned_rule.pattern,
                request.action,
            )

        del self._pending_requests[request_id]
        return True

    def deny_request(self, request_id: str) -> bool:
        """Deny a pending permission request.

        Args:
            request_id: The request to deny.

        Returns:
            True if denied successfully, False if not found.
        """
        request = self._pending_requests.pop(request_id, None)
        return request is not None

    def cleanup_expired_requests(self) -> int:
        """Remove expired pending requests.

        Returns:
            Number of expired requests cleaned up.
        """
        expired_ids = [
            rid
            for rid, req in self._pending_requests.items()
            if req.is_expired()
        ]
        for rid in expired_ids:
            del self._pending_requests[rid]
        return len(expired_ids)

    def get_pending_request(
        self, request_id: str
    ) -> Optional[PermissionRequest]:
        """Get a pending permission request by ID.

        Args:
            request_id: The request ID.

        Returns:
            The PermissionRequest or None if not found/expired.
        """
        request = self._pending_requests.get(request_id)
        if request and request.is_expired():
            del self._pending_requests[request_id]
            return None
        return request

    def to_config(self) -> Dict[str, Any]:
        """Export configuration for storage.

        Returns:
            Configuration dict suitable for JSON serialization.
        """
        return {
            "mode": self.mode,
            "timeout": self.timeout,
            "whitelist": [r.to_dict() for r in self.whitelist],
            "blacklist": [r.to_dict() for r in self.blacklist],
            "learned_allows": [r.to_dict() for r in self._learned_allows],
        }

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> PermissionChecker:
        """Create a PermissionChecker from a stored configuration.

        Args:
            config: Configuration dict from to_config().

        Returns:
            Configured PermissionChecker instance.
        """
        checker = cls(
            mode=config.get("mode", "prompt"),
            timeout=config.get("timeout", 60),
            whitelist=[
                PermissionRule.from_dict(r)
                for r in config.get("whitelist", [])
            ],
            blacklist=[
                PermissionRule.from_dict(r)
                for r in config.get("blacklist", [])
            ],
        )
        checker._learned_allows = [
            PermissionRule.from_dict(r)
            for r in config.get("learned_allows", [])
        ]
        return checker
```

### Changes to [`const.py`](custom_components/ai_agent_ha/const.py)

Add:

```python
# Permission System constants
CONF_PERMISSION_MODE = "permission_mode"
CONF_PERMISSION_WHITELIST = "permission_whitelist"
CONF_PERMISSION_BLACKLIST = "permission_blacklist"
CONF_PERMISSION_TIMEOUT = "permission_timeout"

PERMISSION_MODES = ["prompt", "auto_allow", "auto_deny"]
DEFAULT_PERMISSION_MODE = "prompt"
DEFAULT_PERMISSION_TIMEOUT = 60  # seconds
```

### Changes to [`config_flow.py`](custom_components/ai_agent_ha/config_flow.py)

Add to the options flow a `async_step_permissions` method and wire it into the flow:

```python
async def async_step_permissions(self, user_input=None):
    """Configure permission settings."""
    errors = {}

    if user_input is not None:
        self.options.update(user_input)
        return self.async_create_entry(title="", data=self.options)

    current_mode = self.config_entry.options.get(
        CONF_PERMISSION_MODE, DEFAULT_PERMISSION_MODE
    )
    current_timeout = self.config_entry.options.get(
        CONF_PERMISSION_TIMEOUT, DEFAULT_PERMISSION_TIMEOUT
    )

    from homeassistant.helpers.selector import (
        SelectSelector,
        SelectSelectorConfig,
        NumberSelector,
        NumberSelectorConfig,
        TextSelector,
        TextSelectorConfig,
    )

    schema_dict = {
        vol.Required(CONF_PERMISSION_MODE, default=current_mode): SelectSelector(
            SelectSelectorConfig(
                options=[
                    {"value": "prompt", "label": "Prompt - Ask before each action"},
                    {"value": "auto_allow", "label": "Auto-Allow - Execute all non-blacklisted actions"},
                    {"value": "auto_deny", "label": "Auto-Deny - Only execute whitelisted actions"},
                ]
            )
        ),
        vol.Required(CONF_PERMISSION_TIMEOUT, default=current_timeout): NumberSelector(
            NumberSelectorConfig(min=10, max=300, step=10, mode="slider", unit_of_measurement="seconds")
        ),
    }

    return self.async_show_form(
        step_id="permissions",
        data_schema=vol.Schema(schema_dict),
        errors=errors,
    )
```

### Changes to [`agent.py`](custom_components/ai_agent_ha/agent.py)

**In the `__init__` method of `AiAgentHaAgent`:**

```python
from .permissions import PermissionChecker, PermissionResult

# In __init__:
perm_config = config.get("permissions", {})
self.permission_checker = PermissionChecker.from_config(perm_config)
```

**In `process_query()`, after parsing the AI response and before executing service calls:**

```python
# --- Permission Check ---
# When the AI response includes a service call, check permissions
if parsed_response.get("action") and parsed_response.get("target_entities"):
    action = parsed_response["action"]
    entities = parsed_response.get("target_entities", [])

    perm_result = self.permission_checker.check_action(action, entities)

    if perm_result == PermissionResult.DENY:
        _LOGGER.warning(
            "Permission DENIED for action %s on %s", action, entities
        )
        return {
            "success": False,
            "error": f"Action '{action}' was denied by safety policy.",
            "request_type": "permission_denied",
            "action": action,
            "entities": entities,
        }

    elif perm_result == PermissionResult.PROMPT:
        # Create a permission request for the user
        perm_request = self.permission_checker.create_permission_request(
            action=action,
            entities=entities,
            reason=parsed_response.get("reason", ""),
            metadata=parsed_response.get("metadata", {}),
        )
        _LOGGER.info(
            "Permission PROMPT required for action %s on %s (request_id: %s)",
            action,
            entities,
            perm_request.request_id,
        )
        return {
            "success": True,
            "request_type": "permission_request",
            "permission_request": perm_request.to_dict(),
        }

    # PERMIT - proceed with execution
    _LOGGER.debug("Permission PERMITTED for action %s on %s", action, entities)
```

**Add a method to handle approved actions:**

```python
async def execute_approved_action(
    self, request_id: str, approve: bool, always_allow: bool = False
) -> Dict[str, Any]:
    """Execute an action after user approval.

    Args:
        request_id: The permission request ID.
        approve: Whether the user approved.
        always_allow: Whether to add a learned allow rule.

    Returns:
        Result of the action execution.
    """
    if not approve:
        self.permission_checker.deny_request(request_id)
        return {
            "success": False,
            "request_type": "permission_denied",
            "message": "Action was denied by user.",
        }

    perm_request = self.permission_checker.get_pending_request(request_id)
    if not perm_request:
        return {
            "success": False,
            "error": "Permission request not found or expired.",
        }

    # Approve and learn if requested
    self.permission_checker.approve_request(request_id, always_allow)

    # Execute the action
    try:
        domain, service = perm_request.action.split(".", 1)
        result = await self.call_service(
            domain,
            service,
            target={"entity_id": perm_request.target_entities},
        )
        return {
            "success": True,
            "request_type": "action_result",
            "action": perm_request.action,
            "entities": perm_request.target_entities,
            "result": result,
        }
    except Exception as e:
        _LOGGER.exception("Failed to execute approved action: %s", e)
        return {
            "success": False,
            "request_type": "action_error",
            "error": str(e),
        }
```

### Changes to [`ai_agent_ha-panel.js`](custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js)

**Add new properties for permission dialog:**

```javascript
static get properties() {
  return {
    // ... existing ...
    _permissionRequest: { type: Object, reflect: false, attribute: false },
    _showPermissionDialog: { type: Boolean, reflect: false, attribute: false },
  };
}
```

**Initialize:**

```javascript
this._permissionRequest = null;
this._showPermissionDialog = false;
```

**Update `_handleLlamaResponse` to detect permission requests:**

```javascript
// In _handleLlamaResponse, after JSON parsing:
if (response.request_type === 'permission_request') {
  this._permissionRequest = response.permission_request;
  this._showPermissionDialog = true;
  this._isLoading = false;
  return;  // Don't add as a regular message
}

if (response.request_type === 'permission_denied') {
  this._messages = [...this._messages, {
    type: 'assistant',
    text: `⚠️ Action denied: ${response.error || 'Safety policy prevented this action.'}`
  }];
  this._isLoading = false;
  return;
}
```

**Add permission handling methods:**

```javascript
async _handlePermissionResponse(approve, alwaysAllow = false) {
  const requestId = this._permissionRequest?.request_id;
  this._showPermissionDialog = false;
  this._permissionRequest = null;
  
  if (!approve) {
    this._messages = [...this._messages, {
      type: 'assistant',
      text: 'Action cancelled. Would you like to try something else?'
    }];
    return;
  }
  
  this._isLoading = true;
  try {
    // Call a service to execute the approved action
    const result = await this.hass.callService('ai_agent_ha', 'execute_approved_action', {
      request_id: requestId,
      approve: true,
      always_allow: alwaysAllow,
    });
    
    if (result && result.success) {
      this._messages = [...this._messages, {
        type: 'assistant',
        text: `✅ Action executed: ${result.action}`
      }];
    } else {
      this._messages = [...this._messages, {
        type: 'assistant',
        text: `❌ Action failed: ${result?.error || 'Unknown error'}`
      }];
    }
  } catch (e) {
    console.error('Failed to execute approved action:', e);
    this._messages = [...this._messages, {
      type: 'assistant',
      text: `Error executing action: ${e.message || e}`
    }];
  } finally {
    this._clearLoadingState();
  }
}
```

**Render the permission dialog in the `render()` method:**

```javascript
${this._showPermissionDialog && this._permissionRequest ? html`
  <div class="permission-overlay" @click="${() => this._showPermissionDialog = false}"></div>
  <div class="permission-dialog">
    <div class="permission-header">
      <ha-icon icon="mdi:shield-alert"></ha-icon>
      <h3>Permission Required</h3>
    </div>
    <div class="permission-body">
      <div class="permission-risk ${this._permissionRequest.risk_level}">
        Risk Level: ${this._permissionRequest.risk_level.toUpperCase()}
      </div>
      <div class="permission-detail">
        <strong>Action:</strong> ${this._permissionRequest.action}
      </div>
      <div class="permission-detail">
        <strong>Entities:</strong> ${(this._permissionRequest.target_entities || []).join(', ')}
      </div>
      <div class="permission-detail">
        <strong>Reason:</strong> ${this._permissionRequest.reason || 'No reason provided'}
      </div>
    </div>
    <div class="permission-actions">
      <button class="approve-btn" @click="${() => this._handlePermissionResponse(true, false)}">
        ✅ Approve
      </button>
      <button class="always-allow-btn" @click="${() => this._handlePermissionResponse(true, true)}">
        ⭐ Always Allow
      </button>
      <button class="deny-btn" @click="${() => this._handlePermissionResponse(false)}">
        ❌ Deny
      </button>
    </div>
  </div>
` : ''}
```

**Add CSS for permission dialog:**

```css
.permission-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  z-index: 300;
}
.permission-dialog {
  position: fixed;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  background: var(--primary-background-color);
  border-radius: 12px;
  padding: 24px;
  min-width: 380px;
  max-width: 500px;
  z-index: 301;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.permission-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  color: var(--warning-color);
}
.permission-risk {
  padding: 4px 10px;
  border-radius: 4px;
  font-weight: 600;
  margin-bottom: 12px;
  display: inline-block;
}
.permission-risk.high { background: #ffebee; color: #c62828; }
.permission-risk.medium { background: #fff3e0; color: #ef6c00; }
.permission-risk.low { background: #e8f5e9; color: #2e7d32; }
.permission-detail {
  margin: 8px 0;
  font-size: 14px;
}
.permission-actions {
  display: flex;
  gap: 8px;
  margin-top: 20px;
  justify-content: flex-end;
}
.permission-actions button {
  padding: 8px 16px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-weight: 500;
}
.approve-btn { background: #4caf50; color: white; }
.always-allow-btn { background: #2196f3; color: white; }
.deny-btn { background: #f44336; color: white; }
```

---
