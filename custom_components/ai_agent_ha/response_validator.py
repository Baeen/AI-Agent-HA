"""Response validation for AI agent responses.

This module provides comprehensive validation for AI responses before they
are used or displayed, including JSON format validation, service call
structure validation, and response sanitization.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .input_validator import ValidationResult

_LOGGER = logging.getLogger(__name__)

# === Constants ===

# Minimum length for response text fields
MIN_RESPONSE_LENGTH = 1

# Maximum length for response text
MAX_RESPONSE_LENGTH = 32768

# Maximum depth for nested validation
MAX_NESTED_DEPTH = 10

# Maximum number of actions in automation
MAX_AUTOMATION_ACTIONS = 100

# Maximum number of views in dashboard
MAX_DASHBOARD_VIEWS = 50

# Patterns for sanitization
WHITESPACE_PATTERN = re.compile(r"\s+")
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass
class ResponseValidationResult:
    """Result of response validation.

    Attributes:
        is_valid: Whether the response is valid
        validated_data: The validated and potentially modified response data
        warnings: List of warning messages
        errors: List of error messages
        sanitized: Whether the response was sanitized
    """

    is_valid: bool
    validated_data: Optional[Dict[str, Any]] = None
    warnings: List[str] = None
    errors: List[str] = None
    sanitized: bool = False

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []

    @classmethod
    def from_validation_result(cls, result: ValidationResult) -> "ResponseValidationResult":
        """Create a ResponseValidationResult from a ValidationResult.

        Args:
            result: The ValidationResult to convert

        Returns:
            ResponseValidationResult instance
        """
        return cls(
            is_valid=result.is_valid,
            validated_data={"response": result.sanitized_input},
            warnings=result.warnings,
            errors=result.errors,
            sanitized=result.sanitized_input != result.sanitized_input,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation of the result
        """
        return {
            "is_valid": self.is_valid,
            "validated_data": self.validated_data,
            "warnings": self.warnings,
            "errors": self.errors,
            "sanitized": self.sanitized,
        }

    def add_warning(self, warning: str):
        """Add a warning to the result.

        Args:
            warning: Warning message to add
        """
        self.warnings.append(warning)

    def add_error(self, error: str):
        """Add an error to the result.

        Args:
            error: Error message to add
        """
        self.errors.append(error)
        self.is_valid = False


class ResponseStructureValidator:
    """Validates and sanitizes AI responses.

    This validator ensures that AI responses conform to expected structures
    before they are used or displayed. It supports both lenient and strict
    validation modes.

    Args:
        strict_mode: If True, apply stricter validation rules
    """

    def __init__(self, strict_mode: bool = False):
        """Initialize the response structure validator.

        Args:
            strict_mode: Whether to enable strict validation mode.
                        In strict mode, additional checks are performed
                        such as verifying service data schemas and
                        requiring all optional fields to be present.
        """
        self.strict_mode = strict_mode
        _LOGGER.debug(
            "Initialized ResponseStructureValidator with strict_mode=%s",
            strict_mode,
        )

    def validate_json_response(self, response: str) -> ResponseValidationResult:
        """Validate JSON format of a response.

        Attempts to parse the response as JSON and validates its structure.
        Handles common JSON formatting issues like trailing commas and
        single quotes.

        Args:
            response: The response string to validate

        Returns:
            ResponseValidationResult indicating success or failure
        """
        if not response or not isinstance(response, str):
            return ResponseValidationResult(
                is_valid=False,
                errors=["Response must be a non-empty string"],
            )

        # Trim whitespace
        response = response.strip()

        # Try direct JSON parse
        try:
            parsed = json.loads(response)
            _LOGGER.debug("Successfully parsed JSON response")
            return ResponseValidationResult(
                is_valid=True,
                validated_data=parsed if isinstance(parsed, dict) else {"raw": parsed},
            )
        except json.JSONDecodeError as e:
            _LOGGER.debug("Initial JSON parse failed: %s", e)

        # Try fixing common JSON issues
        fixed_response = self._try_fix_json(response)

        if fixed_response != response:
            self.sanitized = True
            try:
                parsed = json.loads(fixed_response)
                _LOGGER.debug("Successfully parsed fixed JSON response")
                return ResponseValidationResult(
                    is_valid=True,
                    validated_data=parsed if isinstance(parsed, dict) else {"raw": parsed},
                    sanitized=True,
                    warnings=["Response JSON was auto-fixed"],
                )
            except json.JSONDecodeError as e:
                _LOGGER.debug("Fixed JSON parse still failed: %s", e)

        return ResponseValidationResult(
            is_valid=False,
            errors=[f"Invalid JSON format: {str(e)}"],
        )

    def validate_service_call(self, response_data: dict) -> ResponseValidationResult:
        """Validate service call response structure.

        Validates that a service call response contains all required fields
        and that the values are of the correct types.

        Args:
            response_data: The response data to validate

        Returns:
            ResponseValidationResult indicating success or failure
        """
        if not isinstance(response_data, dict):
            return ResponseValidationResult(
                is_valid=False,
                errors=["Response data must be a dictionary"],
            )

        warnings = []
        errors = []

        # Check for required fields
        if "domain" not in response_data:
            errors.append("Missing required field: 'domain'")
        elif not isinstance(response_data["domain"], str) or not response_data["domain"].strip():
            errors.append("Field 'domain' must be a non-empty string")

        if "service" not in response_data:
            errors.append("Missing required field: 'service'")
        elif not isinstance(response_data["service"], str) or not response_data["service"].strip():
            errors.append("Field 'service' must be a non-empty string")

        # Validate optional fields if present
        if "target" in response_data:
            if not isinstance(response_data["target"], dict):
                errors.append("Field 'target' must be a dictionary")
            elif self.strict_mode and not response_data["target"]:
                warnings.append("Empty 'target' dictionary provided")

        if "service_data" in response_data:
            if not isinstance(response_data["service_data"], dict):
                errors.append("Field 'service_data' must be a dictionary")
            elif self.strict_mode:
                # In strict mode, validate service_data values
                for key, value in response_data["service_data"].items():
                    if not isinstance(key, str):
                        errors.append(f"Service data key '{key}' must be a string")
                        break

        # Check for entity_id in target or service_data (common pattern)
        has_entity = (
            ("entity_id" in response_data.get("target", {}) or
             "entity_id" in response_data.get("service_data", {}))
            if self.strict_mode
            else False
        )

        if self.strict_mode and not has_entity:
            if "domain" in response_data and response_data.get("domain") == "light":
                warnings.append("Consider including 'entity_id' in target or service_data for light service calls")

        if errors:
            return ResponseValidationResult(is_valid=False, errors=errors)

        if warnings:
            return ResponseValidationResult(
                is_valid=True,
                validated_data=response_data,
                warnings=warnings,
            )

        return ResponseValidationResult(is_valid=True, validated_data=response_data)

    def validate_final_response(self, response_data: dict) -> ResponseValidationResult:
        """Validate final response structure.

        Validates that a final AI response contains a valid response or
        answer field with non-empty content.

        Args:
            response_data: The response data to validate

        Returns:
            ResponseValidationResult indicating success or failure
        """
        if not isinstance(response_data, dict):
            return ResponseValidationResult(
                is_valid=False,
                errors=["Response data must be a dictionary"],
            )

        # Check for response or answer field
        response_text = None
        response_field = None

        for field_name in ["response", "answer", "text", "message"]:
            if field_name in response_data:
                value = response_data[field_name]
                if isinstance(value, str) and value.strip():
                    response_text = value.strip()
                    response_field = field_name
                    break

        if response_text is None:
            # Check if there's any string field we can use
            for key, value in response_data.items():
                if isinstance(value, str) and value.strip():
                    response_text = value.strip()
                    response_field = key
                    warnings = [f"Using unexpected field '{key}' for response text"]
                    return ResponseValidationResult(
                        is_valid=True,
                        validated_data=response_data,
                        warnings=warnings,
                    )

            return ResponseValidationResult(
                is_valid=False,
                errors=["No valid response text found. Expected 'response', 'answer', 'text', or 'message' field"],
            )

        # Check response length
        if len(response_text) < MIN_RESPONSE_LENGTH:
            return ResponseValidationResult(
                is_valid=False,
                errors=["Response text is empty"],
            )

        if len(response_text) > MAX_RESPONSE_LENGTH:
            return ResponseValidationResult(
                is_valid=False,
                errors=[f"Response text exceeds maximum length of {MAX_RESPONSE_LENGTH} characters"],
            )

        if self.strict_mode:
            # In strict mode, check for additional metadata
            if "type" not in response_data:
                response_data["type"] = "response"

            # Check for action fields
            action_fields = ["actions", "service_calls", "suggestions"]
            has_action = any(field in response_data for field in action_fields)

            if not has_action:
                # Pure text response is valid, just a warning
                pass

        validated_data = response_data.copy()
        validated_data["response"] = response_text

        return ResponseValidationResult(
            is_valid=True,
            validated_data=validated_data,
        )

    def validate_automation_suggestion(self, response_data: dict) -> ResponseValidationResult:
        """Validate automation suggestion structure.

        Validates that an automation suggestion contains the required
        automation fields including alias and actions.

        Args:
            response_data: The response data to validate

        Returns:
            ResponseValidationResult indicating success or failure
        """
        if not isinstance(response_data, dict):
            return ResponseValidationResult(
                is_valid=False,
                errors=["Response data must be a dictionary"],
            )

        # Check for automation field
        if "automation" not in response_data:
            return ResponseValidationResult(
                is_valid=False,
                errors=["Missing required field: 'automation'"],
            )

        automation = response_data["automation"]

        if not isinstance(automation, dict):
            return ResponseValidationResult(
                is_valid=False,
                errors=["Field 'automation' must be a dictionary"],
            )

        warnings = []
        errors = []

        # Check for alias
        if "alias" not in automation:
            errors.append("Automation missing required field: 'alias'")
        elif not isinstance(automation["alias"], str) or not automation["alias"].strip():
            errors.append("Automation 'alias' must be a non-empty string")

        # Check for actions
        if "actions" not in automation:
            errors.append("Automation missing required field: 'actions'")
        elif not isinstance(automation["actions"], list):
            errors.append("Automation 'actions' must be a list")
        elif len(automation["actions"]) == 0:
            errors.append("Automation 'actions' cannot be empty")
        elif len(automation["actions"]) > MAX_AUTOMATION_ACTIONS:
            errors.append(
                f"Automation 'actions' exceeds maximum count of {MAX_AUTOMATION_ACTIONS}"
            )
        elif self.strict_mode:
            # In strict mode, validate each action has at least a service or action field
            for i, action in enumerate(automation["actions"]):
                if not isinstance(action, dict):
                    errors.append(f"Automation action at index {i} must be a dictionary")
                    break
                if "service" not in action and "action" not in action:
                    errors.append(f"Automation action at index {i} must have 'service' or 'action' field")
                    break

        if errors:
            return ResponseValidationResult(is_valid=False, errors=errors)

        # Validate nested structure depth
        if self.strict_mode:
            max_depth = self._check_nested_depth(automation)
            if max_depth > MAX_NESTED_DEPTH:
                return ResponseValidationResult(
                    is_valid=False,
                    errors=[f"Automation structure exceeds maximum depth of {MAX_NESTED_DEPTH}"],
                )

        validated_data = response_data.copy()
        validated_data["automation"] = automation

        return ResponseValidationResult(
            is_valid=True,
            validated_data=validated_data,
            warnings=warnings,
        )

    def validate_dashboard_suggestion(self, response_data: dict) -> ResponseValidationResult:
        """Validate dashboard suggestion structure.

        Validates that a dashboard suggestion contains the required
        dashboard fields including title and views.

        Args:
            response_data: The response data to validate

        Returns:
            ResponseValidationResult indicating success or failure
        """
        if not isinstance(response_data, dict):
            return ResponseValidationResult(
                is_valid=False,
                errors=["Response data must be a dictionary"],
            )

        # Check for dashboard field
        if "dashboard" not in response_data:
            return ResponseValidationResult(
                is_valid=False,
                errors=["Missing required field: 'dashboard'"],
            )

        dashboard = response_data["dashboard"]

        if not isinstance(dashboard, dict):
            return ResponseValidationResult(
                is_valid=False,
                errors=["Field 'dashboard' must be a dictionary"],
            )

        warnings = []
        errors = []

        # Check for title
        if "title" not in dashboard:
            errors.append("Dashboard missing required field: 'title'")
        elif not isinstance(dashboard["title"], str) or not dashboard["title"].strip():
            errors.append("Dashboard 'title' must be a non-empty string")

        # Check for views
        if "views" not in dashboard:
            errors.append("Dashboard missing required field: 'views'")
        elif not isinstance(dashboard["views"], list):
            errors.append("Dashboard 'views' must be a list")
        elif len(dashboard["views"]) == 0:
            errors.append("Dashboard 'views' cannot be empty")
        elif len(dashboard["views"]) > MAX_DASHBOARD_VIEWS:
            errors.append(
                f"Dashboard 'views' exceeds maximum count of {MAX_DASHBOARD_VIEWS}"
            )
        elif self.strict_mode:
            # In strict mode, validate each view has a title
            for i, view in enumerate(dashboard["views"]):
                if not isinstance(view, dict):
                    errors.append(f"Dashboard view at index {i} must be a dictionary")
                    break
                if "title" not in view:
                    errors.append(f"Dashboard view at index {i} missing required field: 'title'")
                    break

        if errors:
            return ResponseValidationResult(is_valid=False, errors=errors)

        validated_data = response_data.copy()
        validated_data["dashboard"] = dashboard

        return ResponseValidationResult(
            is_valid=True,
            validated_data=validated_data,
            warnings=warnings,
        )

    def sanitize_response(self, response: str) -> str:
        """Sanitize a response string.

        Removes control characters, normalizes whitespace, and performs
        other cleanup operations on the response text.

        Args:
            response: The response string to sanitize

        Returns:
            Sanitized response string
        """
        if not response or not isinstance(response, str):
            return response if response else ""

        original = response

        # Remove control characters (except newlines and tabs)
        response = CONTROL_CHAR_PATTERN.sub("", response)

        # Normalize whitespace
        response = WHITESPACE_PATTERN.sub(" ", response)

        # Trim whitespace
        response = response.strip()

        # Remove multiple newlines (keep only single newlines)
        response = re.sub(r"\n{3,}", "\n\n", response)

        if response != original:
            _LOGGER.debug("Response was sanitized")

        return response

    def _try_fix_json(self, response: str) -> str:
        """Attempt to fix common JSON issues.

        Tries to fix common JSON formatting issues like single quotes,
        trailing commas, and missing quotes around keys.

        Args:
            response: The potentially malformed JSON string

        Returns:
            Fixed JSON string if fixes were applied, otherwise original
        """
        fixed = response

        # Replace single quotes with double quotes
        if "'" in fixed and '"' not in fixed:
            fixed = fixed.replace("'", '"')

        # Remove trailing commas before closing braces/brackets
        fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

        # Fix unquoted keys (basic case)
        fixed = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r' "\1":', fixed)

        # Try to balance braces/brackets
        fixed = self._balance_brackets(fixed)

        if fixed != response:
            _LOGGER.debug("Applied JSON fixes to response")

        return fixed

    def _balance_brackets(self, response: str) -> str:
        """Balance unmatched brackets in a JSON string.

        Args:
            response: The JSON string to balance

        Returns:
            Balanced JSON string
        """
        stack = []
        brackets_map = {"{": "}", "[": "]", "(": ")"}
        closing_map = {"}": "{", "]": "[", ")": "("}

        for i, char in enumerate(response):
            if char in brackets_map:
                stack.append((char, i))
            elif char in closing_map:
                if stack and stack[-1][0] == closing_map[char]:
                    stack.pop()
                else:
                    # Unmatched closing bracket, remove it
                    response = response[:i] + response[i+1:]

        # Add missing opening brackets
        while stack:
            bracket, _ = stack.pop()
            response = brackets_map[bracket] + response

        # Add missing closing brackets
        closing_needed = []
        for bracket, _ in stack:
            closing_needed.append(brackets_map[bracket])

        return response + "".join(reversed(closing_needed))

    def _check_nested_depth(self, data: Any, current_depth: int = 0) -> int:
        """Check the maximum nested depth of a data structure.

        Args:
            data: The data structure to check
            current_depth: Current depth level

        Returns:
            Maximum depth found
        """
        if current_depth > MAX_NESTED_DEPTH:
            return current_depth

        max_depth = current_depth

        if isinstance(data, dict):
            for value in data.values():
                depth = self._check_nested_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)
        elif isinstance(data, list):
            for item in data:
                depth = self._check_nested_depth(item, current_depth + 1)
                max_depth = max(max_depth, depth)

        return max_depth


# === Singleton ===

_response_validator_instance: Optional[ResponseStructureValidator] = None


def get_response_validator(strict_mode: bool = False) -> ResponseStructureValidator:
    """Get or create a ResponseStructureValidator singleton.

    Returns a cached instance if one exists with the same strict_mode setting,
    otherwise creates a new instance.

    Args:
        strict_mode: Whether to enable strict validation mode

    Returns:
        ResponseStructureValidator instance
    """
    global _response_validator_instance

    if _response_validator_instance is None or _response_validator_instance.strict_mode != strict_mode:
        _response_validator_instance = ResponseStructureValidator(strict_mode=strict_mode)
        _LOGGER.debug(
            "Created new ResponseStructureValidator with strict_mode=%s",
            strict_mode,
        )

    return _response_validator_instance
