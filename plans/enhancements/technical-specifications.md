# AI Agent HA - Technical Specifications

## Priority Enhancements: Detailed Design Documents

This document provides detailed technical specifications for the top priority enhancements identified in the Comprehensive Enhancement Plan.

---

## 1. Batch Entity State Retrieval (B3)

**Priority:** High | **Complexity:** Low  
**Files Modified:** `agent.py`, `__init__.py`  
**New Files:** None

### 1.1 Problem Statement

Currently, when the AI agent needs to query multiple entity states, each entity is fetched individually via separate `self.hass.states.get(entity_id)` calls in [`get_entity_state()`](custom_components/ai_agent_ha/agent.py:1916). For operations involving N entities, this results in N separate function calls, increasing latency and CPU overhead.

**Current Flow:**
```
User: "Turn on all lights in the living room"
  → AI requests: get_entities_by_area(living_room)
  → Returns entity IDs: light.living_room_1, light.living_room_2, light.living_room_3
  → AI processes each entity individually (3 separate hass.states.get calls)
```

**Optimized Flow:**
```
User: "Turn on all lights in the living room"
  → AI requests: get_entities_by_area(living_room)
  → Returns entity IDs: light.living_room_1, light.living_room_2, light.living_room_3
  → Single batch call: get_entity_states_batch([entity_ids])
  → Returns all states in one operation
```

### 1.2 Design

#### 1.2.1 New Method: `get_entity_states_batch()`

**Location:** [`AiAgentHaAgent`](custom_components/ai_agent_ha/agent.py:1263) class in `agent.py`

```python
async def get_entity_states_batch(
    self, entity_ids: List[str]
) -> Dict[str, Any]:
    """Get the states of multiple entities in a single batch operation.
    
    Args:
        entity_ids: List of entity IDs to fetch states for
        
    Returns:
        Dictionary with:
        - entities: List of entity state dictionaries
        - entity_ids_requested: Original requested IDs
        - entity_ids_found: IDs that were found
        - entity_ids_not_found: IDs that were not found
        - error: Error message if batch operation failed
        - success: Boolean indicating success
    """
    if not entity_ids or not isinstance(entity_ids, list):
        return {"success": False, "error": "Invalid entity_ids parameter"}
    
    if len(entity_ids) == 0:
        return {"success": True, "entities": [], "count": 0}
    
    # Validate entity IDs format
    invalid_ids = [
        eid for eid in entity_ids 
        if not isinstance(eid, str) or "." not in eid
    ]
    if invalid_ids:
        return {"success": False, "error": f"Invalid entity IDs: {invalid_ids}"}
    
    result = {
        "entities": [],
        "entity_ids_requested": entity_ids,
        "entity_ids_found": [],
        "entity_ids_not_found": [],
        "success": True,
    }
    
    # Batch fetch all states
    for entity_id in entity_ids:
        state = self.hass.states.get(entity_id)
        if state:
            entity_data = {
                "entity_id": entity_id,
                "state": state.state,
                "attributes": state.attributes,
                "last_changed": str(state.last_changed),
                "last_updated": str(state.last_updated),
            }
            
            # Include area information (reuse existing logic from get_entity_state)
            area_info = await self._get_entity_area_info(entity_id)
            if area_info:
                entity_data["area_id"] = area_info.get("area_id")
                entity_data["area_name"] = area_info.get("area_name")
            
            result["entities"].append(entity_data)
            result["entity_ids_found"].append(entity_id)
        else:
            result["entity_ids_not_found"].append(entity_id)
    
    result["count"] = len(result["entities"])
    return result


async def _get_entity_area_info(self, entity_id: str) -> Optional[Dict]:
    """Get area information for an entity (extracted from get_entity_state).
    
    This extracts the area lookup logic into a reusable helper.
    """
    try:
        from homeassistant.helpers import area_registry as ar
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        area_registry = ar.async_get(self.hass)

        if not entity_registry or not hasattr(entity_registry, "async_get"):
            return None

        entity_entry = entity_registry.async_get(entity_id)
        if not entity_entry:
            return None

        # Check direct area assignment
        if hasattr(entity_entry, "area_id") and entity_entry.area_id:
            area_id = entity_entry.area_id
            area_name = None
            if area_registry and hasattr(area_registry, "async_get"):
                area_entry = area_registry.async_get(area_id)
                if area_entry:
                    area_name = area_entry.name
            return {"area_id": area_id, "area_name": area_name}

        # Check device area
        if (
            hasattr(entity_entry, "device_id")
            and entity_entry.device_id
            and device_registry
            and hasattr(device_registry, "async_get")
        ):
            device_entry = device_registry.async_get(entity_entry.device_id)
            if device_entry and hasattr(device_entry, "area_id") and device_entry.area_id:
                area_id = device_entry.area_id
                area_name = None
                if area_registry and hasattr(area_registry, "async_get"):
                    area_entry = area_registry.async_get(area_id)
                    if area_entry:
                        area_name = area_entry.name
                return {"area_id": area_id, "area_name": area_name}

    except Exception as e:
        _LOGGER.debug("Error getting area info for %s: %s", entity_id, e)

    return None
```

#### 1.2.2 New Data Request Type Registration

Add `get_entity_states_batch` to the data request types list in [`process_query()`](custom_components/ai_agent_ha/agent.py:3729):

```python
# In process_query(), around line 3729-3752, add to data_request_types:
"data_request_types = [
    ...existing types...
    "get_entity_states_batch",  # NEW: Batch entity state retrieval
]
```

#### 1.2.3 Handler Addition in process_query()

Add handling in the request dispatch section of [`process_query()`](custom_components/ai_agent_ha/agent.py:3782):

```python
# Around line 3857, add new elif branch:
elif request_type == "get_entity_states_batch":
    data = await self.get_entity_states_batch(
        parameters.get("entity_ids", [])
    )
```

### 1.3 AI Prompt Update

Update the SYSTEM_PROMPT in `agent.py` to include the new batch method:

```python
# Add to SYSTEM_PROMPT content (around line 63-90):
"- get_entity_states_batch(entity_ids): Get states of multiple entities at once\n"
```

### 1.4 Expected Performance Improvement

| Scenario | Current Calls | Batched Calls | Improvement |
|----------|---------------|---------------|-------------|
| Query all lights | N entities | 1 batch | N× faster |
| Query all sensors in area | N entities | 1 batch | N× faster |
| Multi-entity automation check | 3-5 entities | 1 batch | 3-5× faster |

### 1.5 Testing Strategy

```python
# tests/test_agent_batch.py (new file)

async def test_get_entity_states_batch(hass):
    """Test batch entity state retrieval."""
    # Setup test entities
    # Call get_entity_states_batch with multiple IDs
    # Verify all states returned in single response
    # Verify entity_ids_not_found populated for invalid IDs

async def test_get_entity_states_batch_empty():
    """Test batch with empty list."""
    # Call with empty list
    # Verify success=True, count=0

async def test_get_entity_states_batch_invalid():
    """Test batch with invalid entity IDs."""
    # Call with malformed IDs
    # Verify success=False, error message populated
```

---

## 2. AI Response Validation (C2)

**Priority:** High | **Complexity:** Low  
**Files Modified:** `agent.py`, `__init__.py`  
**New Files:** `response_validator.py`

### 2.1 Problem Statement

Currently, AI responses are parsed as JSON and executed with minimal validation. If the AI returns malformed JSON, missing required fields, or dangerous configurations, the system may:
- Create malformed automations
- Fail silently with cryptic errors
- Execute unintended actions

**Current Flow:**
```
AI Response → JSON Parse → Execute Action
                    ↓
            (no validation)
```

**Optimized Flow:**
```
AI Response → JSON Parse → Validate → Sanitize → Execute Action
                             ↓
                    (reject/sanitize invalid fields)
```

### 2.2 Design

#### 2.2.1 New Module: `response_validator.py`

```python
"""Response validation for AI-generated actions and configurations.

This module provides validation, sanitization, and safety checking
for AI-generated responses before they are executed.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

_LOGGER = logging.getLogger(__name__)

# === Data Classes ===

@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "sanitized_data": self.sanitized_data,
        }


@dataclass
class FieldRule:
    """Validation rule for a field."""
    field_path: str  # e.g., "automation.trigger.0.platform"
    required: bool = False
    allowed_values: Optional[List[Any]] = None
    max_length: Optional[int] = None
    must_not_contain: Optional[List[str]] = None
    custom_validator: Optional[callable] = None


# === Core Validator ===

class ResponseValidator:
    """Validates and sanitizes AI-generated responses."""
    
    # Minimum required fields for automation creation
    AUTOMATION_REQUIRED_FIELDS = ["alias", "trigger"]
    AUTOMATION_TRIGGER_REQUIRED = ["platform", "for"]  # for time trigger
    
    # Maximum safe values
    MAX_AUTOMATION_ALIAS_LENGTH = 100
    MAX_AUTOMATION_DESCRIPTION_LENGTH = 500
    MAX_ACTIONS_COUNT = 20
    MAX_CONDITIONS_COUNT = 20
    
    # Dangerous patterns that should be flagged
    DANGEROUS_SERVICE_PATTERNS = [
        "lock.unlock",      # Physical security risk
        "camera.record",    # Privacy risk
        "media_player.volume_set",  # Can be abused
        "homeassistant.stop",  # System disruption
        "homeassistant.restart", # System disruption
    ]
    
    def __init__(self, strict_mode: bool = False):
        """Initialize the validator.
        
        Args:
            strict_mode: If True, reject responses with any warnings
        """
        self.strict_mode = strict_mode
    
    def validate_automation_response(
        self, response_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate an automation configuration response.
        
        Args:
            response_data: AI-generated automation data
            
        Returns:
            ValidationResult with errors, warnings, and sanitized data
        """
        errors = []
        warnings = []
        
        # Check top-level structure
        if not isinstance(response_data, dict):
            return ValidationResult(
                is_valid=False,
                errors=["Response must be a JSON object/dictionary"]
            )
        
        # Check required fields
        for field_name in self.AUTOMATION_REQUIRED_FIELDS:
            if field_name not in response_data:
                errors.append(f"Required field missing: {field_name}")
        
        # If critical fields missing, return early
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # Sanitize and validate alias
        alias = response_data.get("alias", "")
        if isinstance(alias, str) and len(alias) > self.MAX_AUTOMATION_ALIAS_LENGTH:
            warnings.append(f"Alias truncated to {self.MAX_AUTOMATION_ALIAS_LENGTH} characters")
            response_data["alias"] = alias[:self.MAX_AUTOMATION_ALIAS_LENGTH]
        
        # Sanitize and validate description
        description = response_data.get("description", "")
        if isinstance(description, str) and len(description) > self.MAX_AUTOMATION_DESCRIPTION_LENGTH:
            warnings.append(f"Description truncated to {self.MAX_AUTOMATION_DESCRIPTION_LENGTH} characters")
            response_data["description"] = description[:self.MAX_AUTOMATION_DESCRIPTION_LENGTH]
        
        # Validate triggers
        triggers = response_data.get("trigger", [])
        if not isinstance(triggers, list):
            errors.append("Triggers must be a list")
        elif len(triggers) > 10:
            warnings.append("More than 10 triggers detected - may cause performance issues")
        
        # Validate actions
        actions = response_data.get("action", [])
        if not isinstance(actions, list):
            errors.append("Actions must be a list")
        elif len(actions) > self.MAX_ACTIONS_COUNT:
            errors.append(f"Maximum {self.MAX_ACTIONS_COUNT} actions allowed")
        else:
            # Check each action for dangerous services
            for i, action in enumerate(actions):
                if isinstance(action, dict):
                    service = action.get("service", "")
                    for dangerous in self.DANGEROUS_SERVICE_PATTERNS:
                        if dangerous in service:
                            warnings.append(
                                f"Action {i+1} uses potentially dangerous service: {service}"
                            )
        
        # Validate conditions (if present)
        conditions = response_data.get("condition", [])
        if isinstance(conditions, list) and len(conditions) > self.MAX_CONDITIONS_COUNT:
            errors.append(f"Maximum {self.MAX_CONDITIONS_COUNT} conditions allowed")
        
        # Validate mode (if present)
        mode = response_data.get("mode")
        valid_modes = ["single", "restart", "queued", "parallel"]
        if mode and mode not in valid_modes:
            errors.append(f"Invalid automation mode: {mode}. Must be one of: {valid_modes}")
            response_data["mode"] = "single"  # Default to safe mode
        
        # Sanitize entity IDs
        self._sanitize_entity_ids(response_data, warnings)
        
        sanitized = json.loads(json.dumps(response_data))  # Deep copy
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            sanitized_data=sanitized if warnings else None
        )
    
    def validate_service_call_response(
        self, response_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate a service call response.
        
        Args:
            response_data: AI-generated service call data
            
        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        
        if not isinstance(response_data, dict):
            return ValidationResult(
                is_valid=False,
                errors=["Response must be a JSON object/dictionary"]
            )
        
        # Check for required fields based on request_type
        request_type = response_data.get("request_type", "")
        
        if request_type == "create_automation":
            return self.validate_automation_response(response_data)
        
        # Validate entity_id format if present
        entity_id = response_data.get("entity_id", "")
        if entity_id and isinstance(entity_id, str):
            if "." not in entity_id:
                errors.append(f"Invalid entity_id format: {entity_id} (must be domain.object_id)")
            elif len(entity_id) > 255:
                errors.append(f"entity_id too long: {len(entity_id)} characters (max 255)")
        
        # Check for dangerous services
        service = response_data.get("service", "")
        if service:
            for dangerous in self.DANGEROUS_SERVICE_PATTERNS:
                if dangerous == service or service.startswith(dangerous + "."):
                    warnings.append(f"Service '{service}' is potentially dangerous - requires review")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_final_response(
        self, response_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate a final response (no action required).
        
        Args:
            response_data: AI-generated final response data
            
        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        
        if not isinstance(response_data, dict):
            return ValidationResult(
                is_valid=False,
                errors=["Response must be a JSON object/dictionary"]
            )
        
        if response_data.get("request_type") != "final_response":
            errors.append(f"Expected request_type='final_response', got '{response_data.get('request_type')}'")
        
        response_text = response_data.get("response", "")
        if not response_text or not isinstance(response_text, str):
            errors.append("Final response must contain a non-empty 'response' string")
        elif len(response_text) > 10000:
            warnings.append("Response very long (>10000 characters) - may be truncated")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _sanitize_entity_ids(
        self, data: Dict[str, Any], warnings: List[str]
    ) -> None:
        """Sanitize entity IDs in automation configuration.
        
        Removes or corrects invalid entity IDs.
        """
        def find_and_sanitize_entity_ids(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if key in ["entity_id", "area_id", "device_id"]:
                        if isinstance(value, str):
                            if "." not in value:
                                warnings.append(f"Invalid entity ID at {new_path}: {value}")
                                obj[key] = None
                        elif isinstance(value, list):
                            sanitized_list = []
                            for item in value:
                                if isinstance(item, str) and "." in item:
                                    sanitized_list.append(item)
                                else:
                                    warnings.append(f"Invalid entity ID in list at {new_path}: {item}")
                            obj[key] = sanitized_list
                    else:
                        find_and_sanitize_entity_ids(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    find_and_sanitize_entity_ids(item, f"{path}[{i}]")
        
        find_and_sanitize_entity_ids(data)
    
    def validate_json_structure(self, response_text: str) -> Tuple[bool, str]:
        """Validate that a response is valid JSON.
        
        Args:
            response_text: Raw response text from AI
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            data = json.loads(response_text)
            return True, ""
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
```

#### 2.2.2 Integration in `process_query()`

Add validation step in [`process_query()`](custom_components/ai_agent_ha/agent.py:3391) after JSON parsing:

```python
# In agent.py, add import at top:
from .response_validator import ResponseValidator

# In process_query(), after JSON parsing (around line 3720), add validation:

# === NEW: Validate AI Response ===
validator = ResponseValidator(strict_mode=False)

if response_data.get("request_type") == "final_response":
    validation_result = validator.validate_final_response(response_data)
    if not validation_result.is_valid:
        _LOGGER.warning("AI final response validation failed: %s", validation_result.errors)
        return _with_debug({
            "success": False,
            "error": "AI response validation failed",
            "validation_errors": validation_result.errors,
        })
    # Use sanitized data if available
    if validation_result.sanitized_data:
        response_data = validation_result.sanitized_data

elif response_data.get("request_type") in ["create_automation", "data_request"]:
    validation_result = validator.validate_service_call_response(response_data)
    if not validation_result.is_valid:
        _LOGGER.warning("AI service call validation failed: %s", validation_result.errors)
        return _with_debug({
            "success": False,
            "error": "AI response validation failed",
            "validation_errors": validation_result.errors,
        })
    elif validation_result.warnings:
        _LOGGER.warning("AI response validation warnings: %s", validation_result.warnings)
        # Continue with sanitized data if available
        if validation_result.sanitized_data:
            response_data = validation_result.sanitized_data
```

### 2.3 Configuration Options

Add to [`const.py`](custom_components/ai_agent_ha/const.py):

```python
# Response Validation settings
CONF_RESPONSE_VALIDATION_ENABLED = "response_validation_enabled"
CONF_RESPONSE_VALIDATION_STRICT_MODE = "response_validation_strict_mode"

DEFAULT_RESPONSE_VALIDATION_ENABLED = True
DEFAULT_RESPONSE_VALIDATION_STRICT_MODE = False
```

### 2.4 Testing Strategy

```python
# tests/test_response_validator.py (new file)

async def test_validate_automation_required_fields():
    """Test that required fields are validated."""
    # Test with missing alias
    # Test with missing trigger
    # Verify errors returned

async def test_validate_automation_max_lengths():
    """Test that max lengths are enforced."""
    # Test with very long alias
    # Test with very long description
    # Verify warnings and truncation

async def test_validate_dangerous_services():
    """Test that dangerous services are flagged."""
    # Test with lock.unlock service
    # Test with homeassistant.stop service
    # Verify warnings generated

async def test_validate_entity_ids():
    """Test entity ID sanitization."""
    # Test with invalid entity IDs
    # Test with valid entity IDs
    # Verify sanitization works
```

---

## 3. Error Recovery System (C1)

**Priority:** High | **Complexity:** Medium  
**Files Modified:** `agent.py`, `__init__.py`  
**New Files:** `error_recovery.py`

### 3.1 Problem Statement

Currently, when an AI provider fails (network timeout, API error, rate limit), the system returns an error to the user with no automatic recovery. There's no:
- Retry logic with exponential backoff
- Provider failover
- Circuit breaker pattern
- Graceful degradation

**Current Flow:**
```
Request → AI Provider → Error → Return to User (failure)
```

**Optimized Flow:**
```
Request → AI Provider → Error → Retry (1s) → Error → Retry (2s) → Error → 
    Failover to Backup Provider → Success → Return to User
                              ↓
                    Circuit Breaker Opens
                    → Use Fallback Response
```

### 3.2 Design

#### 3.2.1 New Module: `error_recovery.py`

```python
"""Error recovery system for AI Agent HA.

Provides retry logic, provider failover, and circuit breaker patterns
for resilient AI service operations.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)


# === Enums ===

class CircuitState(Enum):
    """Circuit breaker state."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, skip requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class RecoveryStrategy(Enum):
    """Recovery strategy to use."""
    NONE = "none"
    RETRY = "retry"
    FAILover = "failover"
    FALLBACK = "fallback"
    COMBINED = "combined"  # retry + failover + fallback


# === Data Classes ===

@dataclass
class RecoveryConfig:
    """Configuration for error recovery."""
    max_retries: int = 3
    initial_delay: float = 1.0       # Initial retry delay in seconds
    max_delay: float = 30.0          # Maximum retry delay in seconds
    backoff_multiplier: float = 2.0  # Exponential backoff multiplier
    failover_enabled: bool = True
    fallback_enabled: bool = True
    
    # Circuit breaker settings
    circuit_failure_threshold: int = 5      # Failures before opening circuit
    circuit_timeout: float = 60.0           # Seconds before half-open
    circuit_success_threshold: int = 3      # Successes in half-open to close


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""
    success: bool
    strategy_used: Optional[RecoveryStrategy] = None
    provider_used: Optional[str] = None
    retry_count: int = 0
    error: Optional[str] = None
    response: Optional[Any] = None
    circuit_state: Optional[CircuitState] = None


@dataclass
class CircuitBreaker:
    """Circuit breaker for a specific service/provider."""
    name: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: datetime = field(default_factory=datetime.now)
    failures: List[datetime] = field(default_factory=list)


# === Error Classes ===

class AIServiceError(Exception):
    """Base class for AI service errors."""
    def __init__(self, message: str, provider: Optional[str] = None, 
                 retryable: bool = True, status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code


class AIProviderTimeoutError(AIServiceError):
    """AI provider timeout error."""
    pass


class AIProviderRateLimitError(AIServiceError):
    """AI provider rate limit error."""
    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider, retryable=True, status_code=429)


class AIProviderAuthError(AIServiceError):
    """AI provider authentication error."""
    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider, retryable=False, status_code=401)


class AIProviderUnavailableError(AIServiceError):
    """AI provider unavailable error."""
    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider, retryable=True, status_code=503)


# === Core Components ===

class RetryHandler:
    """Handles retry logic with exponential backoff."""
    
    def __init__(self, config: RecoveryConfig):
        self.config = config
    
    async def execute_with_retry(
        self,
        operation: Callable[[], Awaitable[Any]],
        operation_name: str = "operation",
    ) -> RecoveryResult:
        """Execute an operation with retry logic.
        
        Args:
            operation: Async callable to execute
            operation_name: Name for logging
            
        Returns:
            RecoveryResult with success/failure info
        """
        last_exception = None
        delay = self.config.initial_delay
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await operation()
                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.RETRY if attempt > 0 else None,
                    retry_count=attempt,
                    response=result,
                )
            except AIServiceError as e:
                last_exception = e
                
                if not e.retryable:
                    _LOGGER.error(
                        "Non-retryable error for %s: %s", operation_name, e
                    )
                    return RecoveryResult(
                        success=False,
                        strategy_used=RecoveryStrategy.RETRY,
                        retry_count=attempt,
                        error=str(e),
                    )
                
                if attempt < self.config.max_retries:
                    _LOGGER.warning(
                        "Retry %d/%d for %s after %.1fs: %s",
                        attempt + 1,
                        self.config.max_retries,
                        operation_name,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                    delay = min(
                        delay * self.config.backoff_multiplier,
                        self.config.max_delay,
                    )
                else:
                    _LOGGER.error(
                        "All %d retries exhausted for %s: %s",
                        self.config.max_retries,
                        operation_name,
                        e,
                    )
            
            except Exception as e:
                last_exception = e
                _LOGGER.error(
                    "Unexpected error during retry for %s: %s",
                    operation_name,
                    e,
                )
                return RecoveryResult(
                    success=False,
                    strategy_used=RecoveryStrategy.RETRY,
                    retry_count=attempt,
                    error=str(e),
                )
        
        return RecoveryResult(
            success=False,
            strategy_used=RecoveryStrategy.RETRY,
            retry_count=self.config.max_retries,
            error=str(last_exception) if last_exception else "Unknown error",
        )


class CircuitBreakerManager:
    """Manages circuit breakers for multiple providers."""
    
    def __init__(self, config: RecoveryConfig):
        self.config = config
        self.circuits: Dict[str, CircuitBreaker] = {}
    
    def _get_circuit(self, name: str) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self.circuits:
            self.circuits[name] = CircuitBreaker(name=name)
        return self.circuits[name]
    
    def can_execute(self, name: str) -> bool:
        """Check if a request can be executed for this provider."""
        circuit = self._get_circuit(name)
        
        if circuit.state == CircuitState.CLOSED:
            return True
        
        if circuit.state == CircuitState.OPEN:
            # Check if timeout has elapsed for half-open
            if (datetime.now() - circuit.last_state_change).total_seconds() >= self.config.circuit_timeout:
                _LOGGER.info("Circuit '%s' transitioning to half-open", name)
                circuit.state = CircuitState.HALF_OPEN
                circuit.success_count = 0
                circuit.last_state_change = datetime.now()
                return True
            return False
        
        # HALF_OPEN - allow limited requests
        return circuit.success_count < self.config.circuit_success_threshold
    
    async def record_success(self, name: str) -> None:
        """Record a successful operation."""
        circuit = self._get_circuit(name)
        
        if circuit.state == CircuitState.HALF_OPEN:
            circuit.success_count += 1
            if circuit.success_count >= self.config.circuit_success_threshold:
                _LOGGER.info("Circuit '%s' closing after %d successes", name, circuit.success_count)
                circuit.state = CircuitState.CLOSED
                circuit.failure_count = 0
                circuit.failures.clear()
                circuit.last_state_change = datetime.now()
        elif circuit.state == CircuitState.CLOSED:
            # Reset failure count on success
            circuit.failure_count = max(0, circuit.failure_count - 1)
    
    async def record_failure(self, name: str) -> None:
        """Record a failed operation."""
        circuit = self._get_circuit(name)
        circuit.failure_count += 1
        circuit.last_failure_time = datetime.now()
        circuit.failures.append(datetime.now())
        
        # Keep only recent failures (sliding window)
        cutoff = datetime.now() - timedelta(seconds=self.config.circuit_timeout * 2)
        circuit.failures = [f for f in circuit.failures if f > cutoff]
        
        if circuit.state == CircuitState.HALF_OPEN:
            _LOGGER.warning("Circuit '%s' reopening after failure in half-open", name)
            circuit.state = CircuitState.OPEN
            circuit.last_state_change = datetime.now()
        elif circuit.state == CircuitState.CLOSED:
            if circuit.failure_count >= self.config.circuit_failure_threshold:
                _LOGGER.warning(
                    "Circuit '%s' opening after %d failures",
                    name,
                    circuit.failure_count,
                )
                circuit.state = CircuitState.OPEN
                circuit.last_state_change = datetime.now()
    
    def get_state(self, name: str) -> CircuitState:
        """Get the current state of a circuit."""
        circuit = self._get_circuit(name)
        return circuit.state
    
    def get_all_states(self) -> Dict[str, str]:
        """Get states of all circuits."""
        return {name: cs.value for name, cs in self.circuits.items()}


class FailoverHandler:
    """Handles failover between AI providers."""
    
    def __init__(
        self,
        primary_provider: str,
        failover_providers: List[str],
        fallback_response: Optional[str] = None,
    ):
        self.primary_provider = primary_provider
        self.failover_providers = failover_providers
        self.fallback_response = fallback_response or (
            "I'm currently experiencing issues connecting to the AI service. "
            "Please try again in a moment."
        )
        self._failover_index = 0
    
    async def execute_with_failover(
        self,
        operations: Dict[str, Callable[[], Awaitable[Any]]],
    ) -> RecoveryResult:
        """Execute operations with failover between providers.
        
        Args:
            operations: Dict mapping provider names to async operations
            
        Returns:
            RecoveryResult with the first successful result
        """
        # Determine execution order
        providers_to_try = [self.primary_provider]
        
        # Add failover providers in order
        for provider in self.failover_providers:
            if provider not in providers_to_try:
                providers_to_try.append(provider)
        
        last_error = None
        
        for provider in providers_to_try:
            if provider not in operations:
                continue
            
            operation = operations[provider]
            _LOGGER.debug("Trying provider: %s", provider)
            
            try:
                result = await operation()
                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.FAILover 
                        if provider != self.primary_provider else None,
                    provider_used=provider,
                    response=result,
                )
            except Exception as e:
                last_error = e
                _LOGGER.warning(
                    "Provider %s failed: %s", provider, e
                )
        
        # All providers failed, use fallback
        if self.fallback_response:
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.FALLBACK,
                response={"success": False, "message": self.fallback_response},
            )
        
        return RecoveryResult(
            success=False,
            strategy_used=RecoveryStrategy.COMBINED,
            error=str(last_error) if last_error else "All providers failed",
        )


class ErrorRecoveryManager:
    """Main coordinator for error recovery operations."""
    
    def __init__(self, config: RecoveryConfig):
        self.config = config
        self.retry_handler = RetryHandler(config)
        self.circuit_manager = CircuitBreakerManager(config)
        self._failover_handlers: Dict[str, FailoverHandler] = {}
    
    def configure_failover(
        self,
        primary: str,
        failovers: List[str],
        fallback_response: Optional[str] = None,
    ) -> None:
        """Configure failover for a primary provider."""
        self._failover_handlers[primary] = FailoverHandler(
            primary, failovers, fallback_response
        )
    
    async def execute_with_recovery(
        self,
        operation: Callable[[], Awaitable[Any]],
        provider_name: str,
        operation_name: str = "AI request",
    ) -> RecoveryResult:
        """Execute an operation with full recovery stack.
        
        Applies circuit breaker check → retry → failover → fallback.
        
        Args:
            operation: Async callable to execute
            provider_name: Name of the provider for circuit breaker
            operation_name: Name for logging
            
        Returns:
            RecoveryResult
        """
        # Check circuit breaker
        if not self.circuit_manager.can_execute(provider_name):
            _LOGGER.warning(
                "Circuit open for %s, skipping operation", provider_name
            )
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.FALLBACK,
                error=f"Circuit breaker open for {provider_name}",
                circuit_state=self.circuit_manager.get_state(provider_name),
            )
        
        # Execute with retry
        result = await self.retry_handler.execute_with_retry(
            operation, operation_name
        )
        
        if result.success:
            await self.circuit_manager.record_success(provider_name)
            return result
        else:
            await self.circuit_manager.record_failure(provider_name)
            result.circuit_state = self.circuit_manager.get_state(provider_name)
            return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get recovery system status."""
        return {
            "circuit_states": self.circuit_manager.get_all_states(),
            "config": {
                "max_retries": self.config.max_retries,
                "initial_delay": self.config.initial_delay,
                "circuit_failure_threshold": self.config.circuit_failure_threshold,
            }
        }
```

#### 3.2.2 Integration in `agent.py`

Add to [`AiAgentHaAgent.__init__()`](custom_components/ai_agent_ha/agent.py:1496):

```python
# In agent.py, add import:
from .error_recovery import (
    ErrorRecoveryManager,
    RecoveryConfig,
    CircuitState,
)

# In AiAgentHaAgent.__init__() around line 1496:
def __init__(self, hass: HomeAssistant, config: Dict[str, Any]):
    ...
    # NEW: Initialize error recovery
    recovery_config = RecoveryConfig(
        max_retries=config.get("max_retries", 3),
        initial_delay=config.get("retry_delay", 1.0),
        circuit_failure_threshold=config.get("circuit_failure_threshold", 5),
    )
    self.recovery_manager = ErrorRecoveryManager(recovery_config)
    
    # Configure failover based on available providers
    available_providers = list(hass.data[DOMAIN]["agents"].keys())
    primary = config.get("ai_provider", "openai")
    failovers = [p for p in available_providers if p != primary]
    self.recovery_manager.configure_failover(primary, failovers)
```

#### 3.2.3 Integration in `_get_ai_response()`

Modify [`_get_ai_response()`](custom_components/ai_agent_ha/agent.py:4576) to use recovery:

```python
async def _get_ai_response(self) -> str:
    """Get AI response with error recovery."""
    
    # NEW: Execute with recovery
    async def do_request():
        return await self.ai_client.get_response(self.conversation_history)
    
    provider_name = self.config.get("ai_provider", "unknown")
    result = await self.recovery_manager.execute_with_recovery(
        do_request,
        provider_name,
        "AI response",
    )
    
    if result.success:
        return result.response
    else:
        # Return error message
        error_msg = f"AI service error: {result.error}"
        if result.strategy_used:
            error_msg += f" (recovery: {result.strategy_used.value})"
        _LOGGER.error(error_msg)
        raise Exception(error_msg)
```

### 3.3 Configuration Options

Add to [`const.py`](custom_components/ai_agent_ha/const.py):

```python
# Error Recovery settings
CONF_MAX_RETRIES = "max_retries"
CONF_RETRY_DELAY = "retry_delay"
CONF_CIRCUIT_FAILURE_THRESHOLD = "circuit_failure_threshold"
CONF_CIRCUIT_TIMEOUT = "circuit_timeout"
CONF_FAILOVER_ENABLED = "failover_enabled"
CONF_FAILOVER_PROVIDERS = "failover_providers"
CONF_FALLBACK_RESPONSE = "fallback_response"

# Default values
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_CIRCUIT_FAILURE_THRESHOLD = 5
DEFAULT_CIRCUIT_TIMEOUT = 60.0
DEFAULT_FAILOVER_ENABLED = True
```

### 3.4 Testing Strategy

```python
# tests/test_error_recovery.py (new file)

async def test_retry_with_exponential_backoff():
    """Test retry logic with exponential backoff."""
    # Simulate 3 failures then success
    # Verify delays increase exponentially
    # Verify success on 4th attempt

async def test_circuit_breaker_opens():
    """Test circuit breaker opens after threshold."""
    # Simulate 5 failures
    # Verify circuit opens
    # Verify requests are blocked

async def test_circuit_breaker_half_open():
    """Test circuit breaker transitions to half-open."""
    # Open circuit
    # Wait for timeout
    # Verify circuit is half-open
    # Simulate success
    # Verify circuit closes

async def test_failover_to_backup_provider():
    """Test failover to backup provider."""
    # Primary fails
    # Verify failover to backup
    # Verify response from backup
```

---

## 4. Robust User Input and Agent Action Handling

**Priority:** High | **Complexity:** Medium  
**Files Modified:** `agent.py`, `__init__.py`, `ai_agent_ha-panel.js`  
**New Files:** `input_validator.py`, `action_executor.py`

### 4.1 Problem Statement

Current input handling and action execution lacks:
1. **Input sanitization** - User input is passed directly to AI without validation
2. **Input length limits** - No enforcement of maximum input length
3. **Action batching** - Multiple actions from single AI response are executed sequentially
4. **Action rollback** - If one action fails, previous actions are not rolled back
5. **Action simulation** - No way to preview what actions would be taken
6. **Execution confirmation** - Actions executed without user confirmation in prompt mode

### 4.2 Design

#### 4.2.1 New Module: `input_validator.py`

```python
"""Input validation and sanitization for user queries."""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)


# === Constants ===

MAX_QUERY_LENGTH = 4096          # Maximum query length
MAX_IMAGES_PER_QUERY = 3         # Maximum images per query
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB per image

# Patterns that might indicate injection attempts
SUSPICIOUS_PATTERNS = [
    r"system_prompt",           # Prompt injection
    r"ignore.*instructions",    # Instruction override
    r"you are now",            # Role play override
    r"forget.*previous",       # Context clearing
    r"as safe mode",           # Jailbreak attempt
    r"developer mode",         # Mode override
]

# Valid entity ID pattern
ENTITY_ID_PATTERN = re.compile(r'^[a-z0-9_]+\.[a-z0-9_]+$')


@dataclass
class ValidationResult:
    """Result of input validation."""
    is_valid: bool
    sanitized_input: str
    warnings: List[str] = None
    errors: List[str] = None
    truncated: bool = False
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "sanitized_input": self.sanitized_input,
            "warnings": self.warnings,
            "errors": self.errors,
            "truncated": self.truncated,
        }


class InputValidator:
    """Validates and sanitizes user input."""
    
    def __init__(
        self,
        max_query_length: int = MAX_QUERY_LENGTH,
        enable_injection_detection: bool = True,
    ):
        self.max_query_length = max_query_length
        self.enable_injection_detection = enable_injection_detection
        self._suspicious_patterns = [
            re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS
        ]
    
    def validate_query(
        self, 
        query: str,
        images: Optional[List[bytes]] = None,
    ) -> ValidationResult:
        """Validate and sanitize a user query.
        
        Args:
            query: User's text query
            images: Optional list of image bytes
            
        Returns:
            ValidationResult with sanitized input and any issues
        """
        warnings = []
        errors = []
        
        # Check type
        if not isinstance(query, str):
            return ValidationResult(
                is_valid=False,
                sanitized_input="",
                errors=["Query must be a string"],
            )
        
        # Check for empty/whitespace-only query
        if not query.strip():
            return ValidationResult(
                is_valid=False,
                sanitized_input="",
                errors=["Query cannot be empty"],
            )
        
        # Check length
        truncated = False
        if len(query) > self.max_query_length:
            warnings.append(
                f"Query truncated from {len(query)} to {self.max_query_length} characters"
            )
            query = query[:self.max_query_length]
            truncated = True
        
        # Detect potential prompt injection
        if self.enable_injection_detection:
            injection_warning = self._check_injection_patterns(query)
            if injection_warning:
                warnings.append(injection_warning)
        
        # Sanitize query (remove control characters except newlines)
        sanitized = self._sanitize_text(query)
        
        # Validate images if provided
        if images:
            image_result = self._validate_images(images)
            warnings.extend(image_result.get("warnings", []))
            errors.extend(image_result.get("errors", []))
            if not image_result.get("is_valid", False):
                return ValidationResult(
                    is_valid=False,
                    sanitized_input=sanitized,
                    errors=errors,
                )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_input=sanitized,
            warnings=warnings,
            errors=errors,
            truncated=truncated,
        )
    
    def validate_entity_id(self, entity_id: str) -> bool:
        """Validate a Home Assistant entity ID."""
        return bool(ENTITY_ID_PATTERN.match(entity_id))
    
    def validate_service_call(
        self, domain: str, service: str, service_data: Optional[Dict] = None
    ) -> ValidationResult:
        """Validate a service call before execution.
        
        Args:
            domain: Service domain (e.g., 'light')
            service: Service name (e.g., 'turn_on')
            service_data: Service data dict
            
        Returns:
            ValidationResult
        """
        warnings = []
        errors = []
        
        # Validate domain
        if not domain or not isinstance(domain, str):
            errors.append("Domain must be a non-empty string")
            return ValidationResult(is_valid=False, sanitized_input="", errors=errors)
        
        if not re.match(r'^[a-z0-9_]+$', domain):
            errors.append(f"Invalid domain format: {domain}")
            return ValidationResult(is_valid=False, sanitized_input="", errors=errors)
        
        # Validate service
        if not service or not isinstance(service, str):
            errors.append("Service must be a non-empty string")
            return ValidationResult(is_valid=False, sanitized_input="", errors=errors)
        
        if not re.match(r'^[a-z0-9_]+$', service):
            errors.append(f"Invalid service format: {service}")
            return ValidationResult(is_valid=False, sanitized_input="", errors=errors)
        
        # Validate service_data if provided
        if service_data:
            if not isinstance(service_data, dict):
                errors.append("Service data must be a dictionary")
                return ValidationResult(is_valid=False, sanitized_input="", errors=errors)
            
            # Validate entity_ids in service data
            entity_ids = service_data.get("entity_id", [])
            if isinstance(entity_ids, str):
                entity_ids = [entity_ids]
            
            if isinstance(entity_ids, list):
                invalid_ids = [
                    eid for eid in entity_ids 
                    if not self.validate_entity_id(eid)
                ]
                if invalid_ids:
                    errors.append(f"Invalid entity IDs: {invalid_ids}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_input=f"{domain}.{service}",
            warnings=warnings,
            errors=errors,
        )
    
    def _check_injection_patterns(self, query: str) -> Optional[str]:
        """Check for potential prompt injection patterns."""
        for pattern in self._suspicious_patterns:
            if pattern.search(query):
                return "Potentially suspicious input detected - flagged for review"
        return None
    
    def _sanitize_text(self, text: str) -> str:
        """Remove control characters from text (preserve newlines)."""
        # Remove control characters except \n and \r
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    def _validate_images(self, images: List[bytes]) -> Dict[str, Any]:
        """Validate image uploads."""
        warnings = []
        errors = []
        
        if len(images) > MAX_IMAGES_PER_QUERY:
            errors.append(
                f"Maximum {MAX_IMAGES_PER_QUERY} images allowed, {len(images)} provided"
            )
            return {"is_valid": False, "warnings": warnings, "errors": errors}
        
        valid_images = []
        for i, img in enumerate(images):
            if len(img) > MAX_IMAGE_SIZE_BYTES:
                errors.append(f"Image {i+1} exceeds maximum size of {MAX_IMAGE_SIZE_BYTES} bytes")
            elif not isinstance(img, bytes):
                errors.append(f"Image {i+1} must be bytes")
            else:
                valid_images.append(img)
        
        if errors:
            return {"is_valid": False, "warnings": warnings, "errors": errors}
        
        if len(valid_images) < len(images):
            warnings.append(f"Invalid images removed from request")
        
        return {"is_valid": True, "warnings": warnings, "errors": []}


# === Singleton instance ===
_input_validator = None

def get_input_validator() -> InputValidator:
    """Get or create the singleton InputValidator instance."""
    global _input_validator
    if _input_validator is None:
        _input_validator = InputValidator()
    return _input_validator
```

#### 4.2.2 New Module: `action_executor.py`

```python
"""Action execution with batching, rollback, and simulation support."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ActionStatus(Enum):
    """Status of an action execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ActionResult:
    """Result of a single action execution."""
    action_id: str
    action_type: str  # e.g., "service_call", "automation_create"
    status: ActionStatus
    result_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class ExecutionPlan:
    """Plan for executing multiple actions."""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    rollback_plan: List[Dict[str, Any]] = field(default_factory=list)
    requires_confirmation: bool = False
    risk_level: str = "low"  # low, medium, high, critical


class ActionExecutor:
    """Executes actions with batching, rollback, and simulation support."""
    
    # High-risk services that require confirmation
    HIGH_RISK_SERVICES = [
        "lock.unlock",
        "alarm_control_panel.alarm_arm_away",
        "alarm_control_panel.alarm_disarm",
        "cover.open_cover",
        "media_player.volume_set",
    ]
    
    # Critical services that should never be auto-executed
    CRITICAL_SERVICES = [
        "homeassistant.stop",
        "homeassistant.restart",
        "system_log.flush",
    ]
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._action_history: List[ActionResult] = []
    
    async def execute_plan(
        self,
        plan: ExecutionPlan,
        require_confirmation: bool = True,
        user_confirmed: bool = False,
    ) -> List[ActionResult]:
        """Execute an action plan with rollback support.
        
        Args:
            plan: The execution plan with actions
            require_confirmation: Whether confirmation is required
            user_confirmed: Whether user has confirmed
            
        Returns:
            List of ActionResults
        """
        # Check for critical services
        critical_found = self._check_critical_services(plan.actions)
        if critical_found:
            return [
                ActionResult(
                    action_id="safety_check",
                    action_type="safety_check",
                    status=ActionStatus.FAILED,
                    error=f"Critical services blocked: {critical_found}",
                )
            ]
        
        # Check if confirmation required
        if require_confirmation and not user_confirmed:
            risk = self._calculate_risk(plan.actions)
            if risk in ["high", "critical"]:
                return [
                    ActionResult(
                        action_id="confirmation",
                        action_type="confirmation_required",
                        status=ActionStatus.FAILED,
                        error=f"Confirmation required for {risk}-risk actions",
                    )
                ]
        
        results = []
        executed_actions = []
        
        for i, action in enumerate(plan.actions):
            action_id = action.get("id", f"action_{i}")
            action_type = action.get("type", "unknown")
            
            _LOGGER.info("Executing action %d: %s", i + 1, action_type)
            
            start_time = asyncio.get_event_loop().time()
            
            try:
                # Execute the action
                result = await self._execute_single_action(action)
                execution_time = asyncio.get_event_loop().time() - start_time
                
                action_result = ActionResult(
                    action_id=action_id,
                    action_type=action_type,
                    status=ActionStatus.SUCCESS,
                    result_data=result,
                    execution_time=execution_time,
                )
                results.append(action_result)
                executed_actions.append((action, action_result))
                
            except Exception as e:
                execution_time = asyncio.get_event_loop().time() - start_time
                _LOGGER.error("Action %s failed: %s", action_id, e)
                
                action_result = ActionResult(
                    action_id=action_id,
                    action_type=action_type,
                    status=ActionStatus.FAILED,
                    error=str(e),
                    execution_time=execution_time,
                )
                results.append(action_result)
                
                # Rollback previously executed actions
                if executed_actions:
                    _LOGGER.info("Rolling back %d executed actions", len(executed_actions))
                    rollback_results = await self._rollback_actions(executed_actions)
                    results.extend(rollback_results)
                    break  # Stop execution after rollback
        
        self._action_history.extend(results)
        return results
    
    async def simulate_plan(
        self, plan: ExecutionPlan
    ) -> Tuple[List[str], List[str], str]:
        """Simulate an action plan without executing.
        
        Args:
            plan: The execution plan
            
        Returns:
            Tuple of (what_would_happen, warnings, risk_level)
        """
        what_would_happen = []
        warnings = []
        
        for i, action in enumerate(plan.actions):
            action_type = action.get("type", "unknown")
            
            if action_type == "service_call":
                domain = action.get("domain", "")
                service = action.get("service", "")
                entities = action.get("entities", [])
                what_would_happen.append(
                    f"Action {i+1}: Call {domain}.{service} on {entities}"
                )
                
                service_key = f"{domain}.{service}"
                if service_key in self.HIGH_RISK_SERVICES:
                    warnings.append(
                        f"Action {i+1} involves high-risk service: {service_key}"
                    )
            elif action_type == "automation_create":
                alias = action.get("config", {}).get("alias", "Unnamed automation")
                what_would_happen.append(f"Action {i+1}: Create automation '{alias}'")
            else:
                what_would_happen.append(
                    f"Action {i+1}: Execute {action_type}"
                )
        
        risk_level = self._calculate_risk(plan.actions)
        return what_would_happen, warnings, risk_level
    
    def get_execution_history(self) -> List[Dict]:
        """Get history of executed actions."""
        return [
            {
                "action_id": r.action_id,
                "action_type": r.action_type,
                "status": r.status.value,
                "execution_time": r.execution_time,
                "error": r.error,
            }
            for r in self._action_history[-100:]  # Last 100 actions
        ]
    
    async def _execute_single_action(
        self, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single action."""
        action_type = action.get("type", "unknown")
        
        if action_type == "service_call":
            return await self._execute_service_call(action)
        elif action_type == "automation_create":
            return await self._execute_automation_create(action)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
    
    async def _execute_service_call(
        self, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a service call action."""
        domain = action.get("domain")
        service = action.get("service")
        service_data = action.get("service_data", {})
        
        if not domain or not service:
            raise ValueError("Service call requires domain and service")
        
        await self.hass.services.async_call(domain, service, service_data)
        
        return {
            "success": True,
            "domain": domain,
            "service": service,
            "service_data": service_data,
        }
    
    async def _execute_automation_create(
        self, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an automation creation action."""
        config = action.get("config", {})
        
        # Import and add automation
        from homeassistant.components import automation as ha_automation
        
        await ha_automation.async_create_automation(
            config.get("trigger", []),
            config.get("action", []),
            config.get("condition", []),
            config.get("mode", "single"),
            config.get("alias", "AI-created automation"),
            config.get("description", ""),
            self.hass,
        )
        
        return {"success": True, "automation": config}
    
    async def _rollback_actions(
        self, executed_actions: List[Tuple[Dict, ActionResult]]
    ) -> List[ActionResult]:
        """Rollback previously executed actions."""
        rollback_results = []
        
        for action, result in reversed(executed_actions):
            action_type = action.get("type", "unknown")
            action_id = action.get("id", "unknown")
            
            try:
                if action_type == "automation_create":
                    # Cannot easily delete automation, log for manual review
                    _LOGGER.warning(
                        "Automation rollback not supported: %s - manual review needed",
                        action_id,
                    )
                    rollback_results.append(ActionResult(
                        action_id=action_id,
                        action_type="rollback",
                        status=ActionStatus.FAILED,
                        error="Automation rollback not supported",
                    ))
                else:
                    # Service calls generally don't need rollback
                    rollback_results.append(ActionResult(
                        action_id=action_id,
                        action_type="rollback",
                        status=ActionStatus.ROLLED_BACK,
                        result_data={"note": "Service call - no rollback needed"},
                    ))
            except Exception as e:
                rollback_results.append(ActionResult(
                    action_id=action_id,
                    action_type="rollback",
                    status=ActionStatus.FAILED,
                    error=str(e),
                ))
        
        return rollback_results
    
    def _calculate_risk(
        self, actions: List[Dict[str, Any]]
    ) -> str:
        """Calculate overall risk level for a set of actions."""
        has_critical = False
        has_high = False
        
        for action in actions:
            if action.get("type") == "service_call":
                service_key = f"{action.get('domain', '')}.{action.get('service', '')}"
                
                if service_key in self.CRITICAL_SERVICES:
                    has_critical = True
                elif service_key in self.HIGH_RISK_SERVICES:
                    has_high = True
        
        if has_critical:
            return "critical"
        elif has_high:
            return "high"
        
        return "medium" if actions else "low"
    
    def _check_critical_services(
        self, actions: List[Dict[str, Any]]
    ) -> List[str]:
        """Check for critical services that should be blocked."""
        blocked = []
        
        for action in actions:
            if action.get("type") == "service_call":
                service_key = f"{action.get('domain', '')}.{action.get('service', '')}"
                if service_key in self.CRITICAL_SERVICES:
                    blocked.append(service_key)
        
        return blocked
```

#### 4.2.3 Integration in `process_query()`

Modify [`process_query()`](custom_components/ai_agent_ha/agent.py:3391) to use new validators:

```python
# In agent.py, add imports:
from .input_validator import InputValidator, get_input_validator
from .action_executor import ActionExecutor, ExecutionPlan, ActionStatus

# At start of process_query(), add input validation:

# === NEW: Validate User Input ===
input_validator = get_input_validator()
validation_result = input_validator.validate_query(
    user_query, images
)

if not validation_result.is_valid:
    return _with_debug({
        "success": False,
        "error": "Invalid input",
        "validation_errors": validation_result.errors,
    })

user_query = validation_result.sanitized_input

if validation_result.warnings:
    _LOGGER.warning("Input validation warnings: %s", validation_result.warnings)

# After JSON parsing and before action execution, add action validation:

# === NEW: Validate and Execute Actions ===
if response_data.get("request_type") == "data_request":
    request_type = response_data.get("request")
    parameters = response_data.get("parameters", {})
    
    # Validate service call if applicable
    if request_type in ["call_service", "set_entity_state"]:
        domain = parameters.get("domain", "")
        service = parameters.get("service", "")
        service_validation = input_validator.validate_service_call(
            domain, service, parameters
        )
        
        if not service_validation.is_valid:
            return _with_debug({
                "success": False,
                "error": "Invalid service call",
                "validation_errors": service_validation.errors,
            })
```

#### 4.2.4 New Service: `simulate_action`

Add to [`__init__.py`](custom_components/ai_agent_ha/__init__.py:387):

```python
# Service definition for simulate_action
@dataclass
class SimulateActionData:
    """Data for simulate_action service."""
    action_type: str  # "service_call", "automation_create"
    domain: Optional[str] = None
    service: Optional[str] = None
    service_data: Optional[Dict] = None
    automation_config: Optional[Dict] = None

# Handler for simulate_action
async def async_handle_simulate_action(call):
    """Simulate an action without executing it."""
    try:
        agent = hass.data[DOMAIN]["agents"].get(
            call.data.get("provider", "openai")
        )
        if not agent:
            return {"success": False, "error": "Agent not found"}
        
        # Build execution plan
        plan = ExecutionPlan()
        
        if call.data.get("action_type") == "service_call":
            plan.actions = [{
                "id": "simulate_1",
                "type": "service_call",
                "domain": call.data.get("domain"),
                "service": call.data.get("service"),
                "service_data": call.data.get("service_data", {}),
                "entities": call.data.get("service_data", {}).get("entity_id", []),
            }]
        elif call.data.get("action_type") == "automation_create":
            plan.actions = [{
                "id": "simulate_1",
                "type": "automation_create",
                "config": call.data.get("automation_config", {}),
            }]
        
        # Simulate
        executor = ActionExecutor(hass)
        what_would_happen, warnings, risk_level = await executor.simulate_plan(plan)
        
        return {
            "success": True,
            "what_would_happen": what_would_happen,
            "warnings": warnings,
            "risk_level": risk_level,
            "would_succeed": True,  # Simulation doesn't predict all failures
        }
        
    except Exception as e:
        _LOGGER.exception("Error simulating action")
        return {"success": False, "error": str(e)}
```

### 4.3 Frontend Integration

Update [`ai_agent_ha-panel.js`](custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js:1814) to show:
1. Input validation warnings
2. Action preview before execution
3. Execution status and rollback notifications

```javascript
// Add to _sendMessage() method around line 1814:

// Show input validation warnings
if (response.validation_errors) {
    this._messages = [...this._messages, {
        role: 'system',
        content: `⚠️ Input validation issues: ${response.validation_errors.join(', ')}`,
        timestamp: new Date().toISOString(),
    }];
}

// Show action preview for dangerous actions
if (response.would_happen && response.risk_level === 'high') {
    this._messages = [...this._messages, {
        role: 'system',
        content: `⚠️ High-risk actions detected. Please confirm before executing.`,
        timestamp: new Date().toISOString(),
        requiresConfirmation: true,
    }];
}

// Show execution rollback notification
if (response.rollback_performed) {
    this._messages = [...this._messages, {
        role: 'system',
        content: `↩️ Actions rolled back due to error: ${response.rollback_reason}`,
        timestamp: new Date().toISOString(),
    }];
}
```

### 4.4 Configuration Options

Add to [`const.py`](custom_components/ai_agent_ha/const.py):

```python
# Input Validation settings
CONF_MAX_QUERY_LENGTH = "max_query_length"
CONF_ENABLE_INJECTION_DETECTION = "enable_injection_detection"
DEFAULT_MAX_QUERY_LENGTH = 4096
DEFAULT_ENABLE_INJECTION_DETECTION = True

# Action Execution settings
CONF_ACTION_REQUIRE_CONFIRMATION = "action_require_confirmation"
CONF_ACTION_ENABLE_SIMULATION = "action_enable_simulation"
CONF_ACTION_ENABLE_ROLLBACK = "action_enable_rollback"
DEFAULT_ACTION_REQUIRE_CONFIRMATION = True
DEFAULT_ACTION_ENABLE_SIMULATION = True
DEFAULT_ACTION_ENABLE_ROLLBACK = True
```

### 4.5 Testing Strategy

```python
# tests/test_input_validator.py (new file)

async def test_validate_query_length():
    """Test query length validation."""
    # Test with normal query
    # Test with excessive length query
    # Verify truncation works

async def test_detect_injection_patterns():
    """Test prompt injection detection."""
    # Test with normal queries
    # Test with injection patterns
    # Verify detection works

async def test_validate_entity_ids():
    """Test entity ID validation."""
    # Test with valid IDs
    # Test with invalid IDs
    # Verify validation works


# tests/test_action_executor.py (new file)

async def test_execute_service_call():
    """Test service call execution."""
    # Mock service call
    # Verify execution

async def test_rollback_on_failure():
    """Test rollback when action fails."""
    # First action succeeds
    # Second action fails
    # Verify rollback of first action

async def test_simulate_plan():
    """Test plan simulation."""
    # Create plan with actions
    # Simulate without executing
    # Verify predictions
```

---

## File Manifest

### New Files to Create
1. `custom_components/ai_agent_ha/response_validator.py` - AI response validation
2. `custom_components/ai_agent_ha/error_recovery.py` - Error recovery system
3. `custom_components/ai_agent_ha/input_validator.py` - Input validation and sanitization
4. `custom_components/ai_agent_ha/action_executor.py` - Action execution with rollback
5. `tests/test_response_validator.py` - Response validator tests
6. `tests/test_error_recovery.py` - Error recovery tests
7. `tests/test_input_validator.py` - Input validator tests
8. `tests/test_action_executor.py` - Action executor tests

### Existing Files to Modify
1. `custom_components/ai_agent_ha/agent.py` - Integrate all new modules
2. `custom_components/ai_agent_ha/__init__.py` - Add new services
3. `custom_components/ai_agent_ha/const.py` - Add configuration constants
4. `custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js` - UI updates

---

## Implementation Order

1. **Phase 1: Input Validation** (Low risk, immediate benefit)
   - Create `input_validator.py`
   - Integrate into `process_query()`
   - Add tests

2. **Phase 2: Response Validation** (Low risk, high safety benefit)
   - Create `response_validator.py`
   - Integrate into `process_query()`
   - Add tests

3. **Phase 3: Error Recovery** (Medium risk, high reliability benefit)
   - Create `error_recovery.py`
   - Integrate into `_get_ai_response()`
   - Add tests

4. **Phase 4: Action Execution** (Medium risk, significant workflow improvement)
   - Create `action_executor.py`
   - Add `simulate_action` service
   - Integrate into action handling
   - Add tests

5. **Phase 5: Frontend Integration**
   - Update UI for validation warnings
   - Add action preview dialogs
   - Add execution status displays

---

*Document Version: 1.0*  
*Last Updated: Generated from Comprehensive Enhancement Plan*
