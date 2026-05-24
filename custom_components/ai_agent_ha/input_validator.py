"""Input validation and sanitization for user queries.

This module provides comprehensive input validation for user queries,
including length limits, injection detection, entity ID validation,
and service call validation.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# === Constants ===

MAX_QUERY_LENGTH = 4096  # Maximum query length
MAX_IMAGES_PER_QUERY = 3  # Maximum images per query
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB per image

# Patterns that might indicate injection attempts
SUSPICIOUS_PATTERNS = [
    r"system_prompt",  # Prompt injection
    r"ignore.*instructions",  # Instruction override
    r"you are now",  # Role play override
    r"forget.*previous",  # Context clearing
    r"as safe mode",  # Jailbreak attempt
    r"developer mode",  # Mode override
]

# Valid entity ID pattern
ENTITY_ID_PATTERN = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


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
        """Convert to dictionary representation."""
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
        """Initialize the input validator.

        Args:
            max_query_length: Maximum allowed query length
            enable_injection_detection: Whether to detect potential injection patterns
        """
        self.max_query_length = max_query_length
        self.enable_injection_detection = enable_injection_detection
        self._suspicious_patterns = [
            re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS
        ]

    def validate_query(
        self, query: str, images: Optional[List[bytes]] = None
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
            query = query[: self.max_query_length]
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
        """Validate a Home Assistant entity ID.

        Args:
            entity_id: The entity ID to validate (e.g., 'light.living_room')

        Returns:
            True if valid, False otherwise
        """
        return bool(ENTITY_ID_PATTERN.match(entity_id))

    def validate_service_call(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict] = None,
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
            return ValidationResult(
                is_valid=False, sanitized_input="", errors=errors
            )

        if not re.match(r"^[a-z0-9_]+$", domain):
            errors.append(f"Invalid domain format: {domain}")
            return ValidationResult(
                is_valid=False, sanitized_input="", errors=errors
            )

        # Validate service
        if not service or not isinstance(service, str):
            errors.append("Service must be a non-empty string")
            return ValidationResult(
                is_valid=False, sanitized_input="", errors=errors
            )

        if not re.match(r"^[a-z0-9_]+$", service):
            errors.append(f"Invalid service format: {service}")
            return ValidationResult(
                is_valid=False, sanitized_input="", errors=errors
            )

        # Validate service_data if provided
        if service_data:
            if not isinstance(service_data, dict):
                errors.append("Service data must be a dictionary")
                return ValidationResult(
                    is_valid=False, sanitized_input="", errors=errors
                )

            # Validate entity_ids in service data
            entity_ids = service_data.get("entity_id", [])
            if isinstance(entity_ids, str):
                entity_ids = [entity_ids]

            if isinstance(entity_ids, list):
                invalid_ids = [eid for eid in entity_ids if not self.validate_entity_id(eid)]
                if invalid_ids:
                    errors.append(f"Invalid entity IDs: {invalid_ids}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            sanitized_input=f"{domain}.{service}",
            warnings=warnings,
            errors=errors,
        )

    def _check_injection_patterns(self, query: str) -> Optional[str]:
        """Check for potential prompt injection patterns.

        Args:
            query: The query to check

        Returns:
            Warning message if suspicious patterns found, None otherwise
        """
        for pattern in self._suspicious_patterns:
            if pattern.search(query):
                return "Potentially suspicious input detected - flagged for review"
        return None

    def _sanitize_text(self, text: str) -> str:
        """Remove control characters from text (preserve newlines).

        Args:
            text: The text to sanitize

        Returns:
            Sanitized text
        """
        # Remove control characters except \n and \r
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    def _validate_images(self, images: List[bytes]) -> Dict[str, Any]:
        """Validate image uploads.

        Args:
            images: List of image bytes

        Returns:
            Dict with is_valid, warnings, errors
        """
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
            warnings.append("Invalid images removed from request")

        return {"is_valid": True, "warnings": warnings, "errors": []}


# === Singleton instance ===
_input_validator = None


def get_input_validator() -> InputValidator:
    """Get or create the singleton InputValidator instance.

    Returns:
        InputValidator singleton instance
    """
    global _input_validator
    if _input_validator is None:
        _input_validator = InputValidator()
    return _input_validator
