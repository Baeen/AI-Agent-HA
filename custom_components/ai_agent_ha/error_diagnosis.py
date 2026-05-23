"""Error diagnosis assistant for Home Assistant.

This module provides functionality to diagnose errors found in logs
and suggest fixes based on known patterns and solutions.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class DiagnosisResult:
    """Result of error diagnosis."""

    def __init__(
        self,
        error_message: str = "",
        error_type: str = "",
        severity: str = "medium",
        possible_causes: Optional[List[str]] = None,
        suggested_fixes: Optional[List[str]] = None,
        related_entities: Optional[List[str]] = None,
        documentation_url: Optional[str] = None,
        confidence: float = 0.5,
    ):
        self.error_message = error_message
        self.error_type = error_type
        self.severity = severity
        self.possible_causes = possible_causes or []
        self.suggested_fixes = suggested_fixes or []
        self.related_entities = related_entities or []
        self.documentation_url = documentation_url
        self.confidence = min(max(confidence, 0.0), 1.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_message": self.error_message,
            "error_type": self.error_type,
            "severity": self.severity,
            "possible_causes": self.possible_causes,
            "suggested_fixes": self.suggested_fixes,
            "related_entities": self.related_entities,
            "documentation_url": self.documentation_url,
            "confidence": self.confidence,
            "confidence_label": self._confidence_label(),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format for display."""
        lines = [f"## Error Diagnosis: {self.error_type}"]
        lines.append("")
        lines.append(f"**Severity:** {self.severity.upper()}")
        lines.append(f"**Confidence:** {self._confidence_label()}")
        lines.append("")
        
        if self.error_message:
            lines.append(f"**Error:** `{self.error_message}`")
            lines.append("")
        
        if self.possible_causes:
            lines.append("### Possible Causes")
            for cause in self.possible_causes:
                lines.append(f"- {cause}")
            lines.append("")
        
        if self.suggested_fixes:
            lines.append("### Suggested Fixes")
            for i, fix in enumerate(self.suggested_fixes, 1):
                lines.append(f"{i}. {fix}")
            lines.append("")
        
        if self.related_entities:
            lines.append("### Related Entities")
            for entity in self.related_entities:
                lines.append(f"- `{entity}`")
            lines.append("")
        
        if self.documentation_url:
            lines.append(f"📖 [Documentation]({self.documentation_url})")
            lines.append("")
        
        return "\n".join(lines)

    def _confidence_label(self) -> str:
        """Get confidence label."""
        if self.confidence >= 0.9:
            return "Very High"
        elif self.confidence >= 0.7:
            return "High"
        elif self.confidence >= 0.5:
            return "Medium"
        elif self.confidence >= 0.3:
            return "Low"
        else:
            return "Very Low"


# Known error patterns and their diagnoses
KNOWN_ERROR_PATTERNS = [
    {
        "pattern": r"Entity .* is not valid",
        "error_type": "Invalid Entity Reference",
        "severity": "high",
        "causes": [
            "Entity ID typo in automation or configuration",
            "Entity was removed or renamed",
            "Entity is disabled in the UI",
            "Custom integration removed the entity",
        ],
        "fixes": [
            "Check the entity ID in Developer Tools > States",
            "Verify the automation YAML for typos",
            "Check if the entity is disabled in Settings > Devices & Services",
            "Restart the integration that provides the entity",
        ],
        "url": "https://www.home-assistant.io/docs/automation/trigger/",
        "confidence": 0.9,
    },
    {
        "pattern": r"Service .* does not exist",
        "error_type": "Non-existent Service",
        "severity": "high",
        "causes": [
            "Service name typo",
            "Domain is incorrect",
            "Integration providing the service is not loaded",
            "Service was deprecated in newer HA versions",
        ],
        "fixes": [
            "Check available services in Developer Tools > Services",
            "Verify the service domain (e.g., light, switch, media_player)",
            "Ensure the integration is properly configured",
            "Check if the service was deprecated in your HA version",
        ],
        "url": "https://www.home-assistant.io/docs/scripts/service-call/",
        "confidence": 0.9,
    },
    {
        "pattern": r"Timeout",
        "error_type": "Operation Timeout",
        "severity": "medium",
        "causes": [
            "Network latency or connectivity issues",
            "Target device not responding",
            "Service timeout value too low",
            "Device is offline or sleeping",
        ],
        "fixes": [
            "Check network connectivity to the device",
            "Increase the timeout value in the integration configuration",
            "Restart the target device",
            "Check if the device is in sleep mode",
        ],
        "url": "https://www.home-assistant.io/integrations/timeout/",
        "confidence": 0.6,
    },
    {
        "pattern": r"Connection refused",
        "error_type": "Connection Refused",
        "severity": "high",
        "causes": [
            "Target service is not running",
            "Firewall blocking the connection",
            "Wrong port number",
            "Service temporarily unavailable",
        ],
        "fixes": [
            "Ensure the target service is running",
            "Check firewall settings",
            "Verify the port number in configuration",
            "Restart the target service",
        ],
        "url": "https://www.home-assistant.io/integrations/tcp/",
        "confidence": 0.85,
    },
    {
        "pattern": r"Unauthorized|401|403",
        "error_type": "Authentication Failed",
        "severity": "high",
        "causes": [
            "Invalid API key or token",
            "Expired credentials",
            "Insufficient permissions",
            "API rate limit exceeded",
        ],
        "fixes": [
            "Regenerate API key or token",
            "Check credentials in integration configuration",
            "Verify account permissions",
            "Check if rate limits have been exceeded",
        ],
        "url": "https://www.home-assistant.io/docs/authentication/",
        "confidence": 0.85,
    },
    {
        "pattern": r"Entity not found|no entity|entity.*not found",
        "error_type": "Entity Not Found",
        "severity": "medium",
        "causes": [
            "Entity ID is incorrect",
            "Entity was removed",
            "Entity is not yet available",
            "Integration not loaded",
        ],
        "fixes": [
            "Verify entity exists in Developer Tools > States",
            "Check for typos in entity ID",
            "Restart the integration that provides the entity",
            "Check integration documentation for required setup",
        ],
        "url": "https://www.home-assistant.io/docs/automation/trigger/",
        "confidence": 0.8,
    },
    {
        "pattern": r"ValueError.*not.*valid|invalid value",
        "error_type": "Invalid Value",
        "severity": "medium",
        "causes": [
            "Wrong data type passed to service",
            "Value out of acceptable range",
            "Malformed configuration",
            "Template rendering error",
        ],
        "fixes": [
            "Check service documentation for expected value types",
            "Verify values are within acceptable ranges",
            "Check template syntax",
            "Review recent configuration changes",
        ],
        "url": "https://www.home-assistant.io/docs/configuration/",
        "confidence": 0.6,
    },
    {
        "pattern": r"OOMKilled|Out of memory|MemoryError",
        "error_type": "Out of Memory",
        "severity": "critical",
        "causes": [
            "Insufficient system memory",
            "Memory leak in integration",
            "Too many entities or automations",
            "Database too large",
        ],
        "fixes": [
            "Increase system memory",
            "Restart Home Assistant",
            "Check for memory leaks in custom integrations",
            "Clean up old database entries",
            "Reduce number of entities tracked in history",
        ],
        "url": "https://www.home-assistant.io/docs/optimization/",
        "confidence": 0.95,
    },
    {
        "pattern": r"Disk space|No space left|StorageFull",
        "error_type": "Disk Space Full",
        "severity": "critical",
        "causes": [
            "Disk is full",
            "Database growing too large",
            "Log files consuming space",
            "Backup files accumulating",
        ],
        "fixes": [
            "Free up disk space",
            "Clean up old backups",
            "Compress or delete old log files",
            "Expand storage",
            "Check database size and vacuum if needed",
        ],
        "url": "https://www.home-assistant.io/docs/backup/",
        "confidence": 0.95,
    },
    {
        "pattern": r"SSL|certificate|HTTPS",
        "error_type": "SSL/Certificate Error",
        "severity": "high",
        "causes": [
            "Invalid SSL certificate",
            "Expired certificate",
            "Self-signed certificate not trusted",
            "Certificate chain incomplete",
        ],
        "fixes": [
            "Update SSL certificate",
            "Trust self-signed certificate in HA configuration",
            "Check certificate expiration dates",
            "Verify certificate chain is complete",
        ],
        "url": "https://www.home-assistant.io/integrations/ssl/",
        "confidence": 0.75,
    },
    {
        "pattern": r"Template.*error|jinja2",
        "error_type": "Template Error",
        "severity": "medium",
        "causes": [
            "Invalid Jinja2 template syntax",
            "Undefined variable in template",
            "Invalid filter usage",
            "Missing entity in template",
        ],
        "fixes": [
            "Check template syntax in Developer Tools > Templates",
            "Verify all referenced entities exist",
            "Review Jinja2 documentation for correct syntax",
            "Add default values for optional variables",
        ],
        "url": "https://www.home-assistant.io/docs/configuration/templating/",
        "confidence": 0.8,
    },
    {
        "pattern": r"Integration .* not found|Platform .* not found",
        "error_type": "Integration/Platform Not Found",
        "severity": "high",
        "causes": [
            "Integration not installed",
            "Typo in integration name",
            "Custom integration missing",
            "Dependency not installed",
        ],
        "fixes": [
            "Install the required integration via HACS or pip",
            "Check integration name for typos",
            "Verify custom integration is in custom_components folder",
            "Install required dependencies",
        ],
        "url": "https://www.home-assistant.io/integrations/",
        "confidence": 0.85,
    },
    {
        "pattern": r"Schema.*error|config.*invalid|voluptuous",
        "error_type": "Configuration Schema Error",
        "severity": "high",
        "causes": [
            "Invalid configuration format",
            "Missing required configuration key",
            "Wrong data type in configuration",
            "Deprecated configuration option",
        ],
        "fixes": [
            "Check configuration.yaml for syntax errors",
            "Verify all required keys are present",
            "Review integration documentation for correct format",
            "Check if any options are deprecated",
        ],
        "url": "https://www.home-assistant.io/docs/configuration/",
        "confidence": 0.75,
    },
    {
        "pattern": r"Device.*not found|Device.*unknown",
        "error_type": "Device Not Found",
        "severity": "medium",
        "causes": [
            "Device not discovered",
            "Device offline",
            "Integration not configured for device",
            "Device was removed from registry",
        ],
        "fixes": [
            "Check device is powered on and connected",
            "Restart device discovery",
            "Reconfigure the integration for the device",
            "Check device registry in Settings > Devices & Services",
        ],
        "url": "https://www.home-assistant.io/integrations/device_registry/",
        "confidence": 0.7,
    },
    {
        "pattern": r"Database|sqlite|sqlite3",
        "error_type": "Database Error",
        "severity": "high",
        "causes": [
            "Database corruption",
            "Database file locked",
            "Insufficient disk space for database",
            "Database version incompatibility",
        ],
        "fixes": [
            "Restart Home Assistant to release database locks",
            "Check disk space",
            "Run database vacuum: `sqlite3 home-assistant-v2.db \"VACUUM;\"`",
            "Restore database from backup if corrupted",
        ],
        "url": "https://www.home-assistant.io/integrations/recorder/",
        "confidence": 0.7,
    },
]


class ErrorDiagnosisAssistant:
    """Diagnoses errors and provides suggested fixes."""

    def __init__(self):
        """Initialize the error diagnosis assistant."""
        self.patterns = KNOWN_ERROR_PATTERNS

    def diagnose(
        self, error_message: str, context: Optional[Dict[str, Any]] = None
    ) -> List[DiagnosisResult]:
        """Diagnose an error message.
        
        Args:
            error_message: The error message to diagnose
            context: Optional context (e.g., entity_id, domain)
            
        Returns:
            List of DiagnosisResult objects (may be empty if no match found)
        """
        results = []
        
        for pattern_info in self.patterns:
            if re.search(pattern_info["pattern"], error_message, re.IGNORECASE):
                result = DiagnosisResult(
                    error_message=error_message,
                    error_type=pattern_info["error_type"],
                    severity=pattern_info["severity"],
                    possible_causes=pattern_info["causes"],
                    suggested_fixes=pattern_info["fixes"],
                    documentation_url=pattern_info["url"],
                    confidence=pattern_info["confidence"],
                )
                
                # Extract related entities from context
                if context:
                    result.related_entities = context.get("entities", [])
                    
                    # Try to extract entity IDs from error message
                    entities = re.findall(r"(\w+:\w+)", error_message)
                    if entities:
                        result.related_entities.extend(entities)
                
                results.append(result)
        
        return results

    def diagnose_multiple(
        self, error_messages: List[str]
    ) -> Dict[str, List[DiagnosisResult]]:
        """Diagnose multiple error messages.
        
        Args:
            error_messages: List of error messages
            
        Returns:
            Dictionary mapping error messages to diagnosis results
        """
        return {msg: self.diagnose(msg) for msg in error_messages}

    def get_ai_enhanced_diagnosis(
        self, error_message: str, diagnosis_results: List[DiagnosisResult]
    ) -> str:
        """Generate an AI-enhanced diagnosis prompt.
        
        This method creates a prompt that can be sent to an AI model
        for enhanced diagnosis beyond pattern matching.
        
        Args:
            error_message: The original error message
            diagnosis_results: Results from pattern matching
            
        Returns:
            Prompt string for AI diagnosis
        """
        base_prompt = f"""You are a Home Assistant troubleshooting expert. Please diagnose the following error:

Error Message:
{error_message}
"""
        
        if diagnosis_results:
            base_prompt += "\n\nKnown Pattern Matches:\n"
            for result in diagnosis_results:
                base_prompt += f"\n- {result.error_type} (confidence: {result.confidence:.0%})\n"
                base_prompt += f"  Severity: {result.severity}\n"
                base_prompt += f"  Possible causes: {', '.join(result.possible_causes[:3])}\n"
                base_prompt += f"  Suggested fixes: {', '.join(result.suggested_fixes[:3])}\n"
        else:
            base_prompt += "\n\nNo known pattern match found. Please provide a diagnosis based on your expertise.\n"
        
        base_prompt += """
Please provide:
1. A clear explanation of what the error means
2. The most likely causes (prioritized)
3. Step-by-step fixes to try
4. Any relevant documentation links
5. Whether this is a critical issue requiring immediate attention

Respond in a clear, structured format.
"""
        
        return base_prompt

    def get_diagnosis_summary(
        self, diagnosis_results: List[DiagnosisResult]
    ) -> str:
        """Get a summary of multiple diagnosis results.
        
        Args:
            diagnosis_results: List of diagnosis results
            
        Returns:
            Summary string
        """
        if not diagnosis_results:
            return "No errors diagnosed. The system appears to be running without known error patterns."
        
        critical = [r for r in diagnosis_results if r.severity == "critical"]
        high = [r for r in diagnosis_results if r.severity == "high"]
        medium = [r for r in diagnosis_results if r.severity == "medium"]
        
        lines = ["## Error Diagnosis Summary\n"]
        
        if critical:
            lines.append(f"🔴 **{len(critical)} Critical Error(s) Requiring Immediate Attention:**")
            for r in critical:
                lines.append(f"- {r.error_type}: {r.error_message[:80]}")
            lines.append("")
        
        if high:
            lines.append(f"🟠 **{len(high)} High Severity Error(s):**")
            for r in high:
                lines.append(f"- {r.error_type}: {r.error_message[:80]}")
            lines.append("")
        
        if medium:
            lines.append(f"🟡 **{len(medium)} Medium Severity Error(s):**")
            for r in medium:
                lines.append(f"- {r.error_type}: {r.error_message[:80]}")
            lines.append("")
        
        # Aggregate fixes
        all_fixes = set()
        for r in diagnosis_results:
            for fix in r.suggested_fixes:
                all_fixes.add(fix)
        
        if all_fixes:
            lines.append("### Recommended Actions")
            for i, fix in enumerate(sorted(all_fixes), 1):
                lines.append(f"{i}. {fix}")
            lines.append("")
        
        return "\n".join(lines)
