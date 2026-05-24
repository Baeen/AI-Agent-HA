"""Audit Log Module for AI Agent HA integration.

This module provides a comprehensive audit logging system to track and log all
AI agent actions, service calls, and permission decisions for security compliance.
Logs are stored in-memory with JSON persistence support.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)


class AuditLogQueryResult(TypedDict):
    """TypedDict for the return value of get_entries method."""
    
    entries: List[AuditLogEntry]
    total: int
    limit: int
    offset: int

# Store key for audit logs
STORE_KEY = "ai_agent_ha_audit_log"

# Retention constants
DEFAULT_RETENTION_DAYS = 90
DEFAULT_MAX_ENTRIES = 10000

# Action types for audit logs
class ActionType(str, Enum):
    """Action types that can be logged."""
    
    # Service call actions
    SERVICE_CALL = "service_call"
    SERVICE_CALL_ALLOWED = "service_call_allowed"
    SERVICE_CALL_DENIED = "service_call_denied"
    
    # Permission actions
    PERMISSION_CHECK = "permission_check"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    PERMISSION_REQUESTED = "permission_requested"
    PERMISSION_APPROVED = "permission_approved"
    PERMISSION_DENIED_MANUAL = "permission_denied_manual"
    
    # Provider actions
    PROVIDER_CHANGED = "provider_changed"
    PROVIDER_FAILED_OVER = "provider_failover"
    PROVIDER_VALIDATED = "provider_validated"
    
    # Configuration actions
    CONFIG_MODIFIED = "config_modified"
    AUTOMATION_CREATED = "automation_created"
    AUTOMATION_MODIFIED = "automation_modified"
    DASHBOARD_CREATED = "dashboard_created"
    DASHBOARD_MODIFIED = "dashboard_modified"
    
    # Security actions
    SECURITY_SCAN = "security_scan"
    CREDENTIAL_DETECTED = "credential_detected"
    SECURITY_VIOLATION = "security_violation"
    
    # System actions
    INTEGRATION_STARTED = "integration_started"
    INTEGRATION_STOPPED = "integration_stopped"
    CONFIG_ENTRY_UPDATED = "config_entry_updated"
    
    # Chat actions
    QUERY_SENT = "query_sent"
    QUERY_RESPONSE_RECEIVED = "query_response_received"
    ACTION_EXECUTED = "action_executed"
    ACTION_SIMULATED = "action_simulated"
    ACTION_ROLLED_BACK = "action_rolled_back"


@dataclass
class AuditLogEntry:
    """A single audit log entry."""
    
    # Required fields
    timestamp: str  # ISO format timestamp
    action_type: str  # ActionType or custom action type
    severity: str = "info"  # info, warning, error, critical
    
    # Context fields
    component: str = ""  # Component that generated the log (e.g., "permissions", "agent")
    user: str = ""  # User involved (if applicable)
    
    # Action details
    action: str = ""  # The action that was performed
    target_entities: List[str] = field(default_factory=list)  # Target entities
    service_domain: str = ""  # Service domain (e.g., "light", "lock")
    service_name: str = ""  # Service name (e.g., "turn_on")
    
    # Result fields
    result: str = ""  # Result of the action (allowed, denied, etc.)
    result_details: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    # Additional fields
    provider: str = ""  # AI provider involved (if applicable)
    risk_level: str = ""  # Risk level (low, medium, high, critical)
    reason: str = ""  # Reason for the action/decision
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AuditLogEntry":
        """Create entry from dictionary."""
        return AuditLogEntry(**{k: v for k, v in data.items() 
                               if k in AuditLogEntry.__dataclass_fields__})
    
    def to_json(self) -> str:
        """Convert entry to JSON string."""
        return json.dumps(self.to_dict())
    
    @staticmethod
    def from_json(json_str: str) -> "AuditLogEntry":
        """Create entry from JSON string."""
        data = json.loads(json_str)
        return AuditLogEntry.from_dict(data)


class RetentionPolicy:
    """Configuration for log retention policies."""
    
    def __init__(
        self,
        max_age_days: int = DEFAULT_RETENTION_DAYS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_size_mb: float = 50.0,
        auto_cleanup: bool = True,
    ):
        self.max_age_days = max_age_days
        self.max_entries = max_entries
        self.max_size_mb = max_size_mb
        self.auto_cleanup = auto_cleanup
    
    def should_retain(self, entry: AuditLogEntry) -> bool:
        """Check if an entry should be retained based on age."""
        try:
            entry_time = datetime.fromisoformat(entry.timestamp)
            cutoff_time = datetime.now() - timedelta(days=self.max_age_days)
            return entry_time >= cutoff_time
        except (ValueError, TypeError):
            return True  # Keep entries with invalid timestamps
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary."""
        return {
            "max_age_days": self.max_age_days,
            "max_entries": self.max_entries,
            "max_size_mb": self.max_size_mb,
            "auto_cleanup": self.auto_cleanup,
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RetentionPolicy":
        """Create retention policy from dictionary."""
        return RetentionPolicy(
            max_age_days=data.get("max_age_days", DEFAULT_RETENTION_DAYS),
            max_entries=data.get("max_entries", DEFAULT_MAX_ENTRIES),
            max_size_mb=data.get("max_size_mb", 50.0),
            auto_cleanup=data.get("auto_cleanup", True),
        )


class AuditLogManager:
    """Manages audit logs for the AI Agent HA integration."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        retention_policy: Optional[RetentionPolicy] = None,
        persistence_enabled: bool = True,
        storage_path: Optional[str] = None,
    ):
        """Initialize the audit log manager.
        
        Args:
            hass: HomeAssistant instance
            retention_policy: Retention policy for log entries
            persistence_enabled: Whether to persist logs to storage
            storage_path: Custom storage path (uses HA storage helper if None)
        """
        self.hass = hass
        # Initialize _logs BEFORE setting retention_policy to avoid AttributeError
        # when the setter calls _apply_retention()
        self._logs: List[AuditLogEntry] = []
        self._lock = False  # Simple lock for thread safety
        self._event_listeners: List[Callable[[AuditLogEntry], None]] = []
        self._entry_counter = 0
        self.persistence_enabled = persistence_enabled
        
        # Storage helper for persistence
        self._store = Store(
            hass,
            version=1,
            key=STORE_KEY,
            atomic_writes=True,
        )
        
        # Set retention policy AFTER _logs is initialized
        self.retention_policy = retention_policy or RetentionPolicy()
        
        # Load persisted logs if enabled (defer to avoid Store.data not being ready)
        if persistence_enabled:
            # Defer loading to after initialization completes
            import asyncio
            try:
                # Try to schedule async load if event loop is running
                asyncio.create_task(self._async_load_logs())
            except RuntimeError:
                # No event loop running, skip auto-load
                _LOGGER.debug("No event loop available for async log loading")
    
    def log(
        self,
        action_type: str,
        severity: str = "info",
        component: str = "",
        user: str = "",
        action: str = "",
        target_entities: Optional[List[str]] = None,
        service_domain: str = "",
        service_name: str = "",
        result: str = "",
        result_details: Optional[Dict[str, Any]] = None,
        provider: str = "",
        risk_level: str = "",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Create and store a new audit log entry.
        
        Args:
            action_type: Type of action (ActionType or string)
            severity: Severity level (info, warning, error, critical)
            component: Component that generated the log
            user: User involved
            action: The action performed
            target_entities: Target entities
            service_domain: Service domain
            service_name: Service name
            result: Result of the action
            result_details: Additional result details
            provider: AI provider involved
            risk_level: Risk level
            reason: Reason for the action
            metadata: Additional metadata
            
        Returns:
            The created AuditLogEntry
        """
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            action_type=action_type,
            severity=severity,
            component=component,
            user=user,
            action=action,
            target_entities=target_entities or [],
            service_domain=service_domain,
            service_name=service_name,
            result=result,
            result_details=result_details or {},
            provider=provider,
            risk_level=risk_level,
            reason=reason,
            metadata=metadata or {},
        )
        
        self._add_entry(entry)
        return entry
    
    def _add_entry(self, entry: AuditLogEntry) -> None:
        """Add an entry to the log internally."""
        self._lock = True
        try:
            self._logs.append(entry)
            self._entry_counter += 1
            
            # Apply retention policy
            if self.retention_policy.auto_cleanup:
                self._apply_retention()
            
            # Notify listeners
            for listener in self._event_listeners:
                try:
                    listener(entry)
                except Exception as e:
                    _LOGGER.warning("Error notifying audit log listener: %s", e)
            
            # Persist if enabled
            if self.persistence_enabled:
                self._save_logs()
            
            _LOGGER.debug(
                "Audit log entry added: type=%s, component=%s, action=%s",
                entry.action_type,
                entry.component,
                entry.action,
            )
        finally:
            self._lock = False
    
    def _apply_retention(self) -> int:
        """Apply retention policy and remove old entries.
        
        Returns:
            Number of entries removed
        """
        # Guard: Skip if _logs not initialized (e.g., during early initialization)
        if not hasattr(self, '_logs') or self._logs is None:
            return 0
        
        removed = 0
        
        # Remove old entries based on age
        if self.retention_policy.max_age_days > 0:
            original_count = len(self._logs)
            self._logs = [
                entry for entry in self._logs
                if self.retention_policy.should_retain(entry)
            ]
            removed += original_count - len(self._logs)
        
        # Remove oldest entries if over max
        if len(self._logs) > self.retention_policy.max_entries:
            excess = len(self._logs) - self.retention_policy.max_entries
            self._logs = self._logs[excess:]
            removed += excess
        
        if removed > 0:
            _LOGGER.debug(
                "Retention policy applied: removed %d entries", removed
            )
        
        return removed
    
    def _save_logs(self) -> None:
        """Persist logs to storage."""
        try:
            logs_data = [entry.to_dict() for entry in self._logs]
            self._store.async_save(logs_data)
        except Exception as e:
            _LOGGER.error("Error saving audit logs: %s", e)
    
    async def _async_load_logs(self) -> None:
        """Asynchronously load logs from storage.
        
        This method should be called after initialization to avoid
        accessing Store.data before it's ready.
        """
        try:
            # Get stored data asynchronously
            stored_data = await self._store.async_load()
            if stored_data:
                self._logs = [AuditLogEntry.from_dict(data) for data in stored_data]
                self._entry_counter = len(self._logs)
                _LOGGER.info(
                    "Loaded %d audit log entries from storage", len(self._logs)
                )
            else:
                _LOGGER.debug("No persisted audit logs found")
        except Exception as e:
            _LOGGER.error("Error loading audit logs: %s", e)
    
    def _load_logs(self) -> None:
        """Load logs from storage (synchronous, deprecated).
        
        Deprecated: Use _async_load_logs() instead.
        This method is kept for backward compatibility.
        """
        try:
            stored_data = self._store.data
            if stored_data:
                self._logs = [AuditLogEntry.from_dict(data) for data in stored_data]
                self._entry_counter = len(self._logs)
                _LOGGER.info(
                    "Loaded %d audit log entries from storage", len(self._logs)
                )
            else:
                _LOGGER.debug("No persisted audit logs found")
        except Exception as e:
            _LOGGER.error("Error loading audit logs: %s", e)
    
    def get_entries(
        self,
        action_type: Optional[str] = None,
        severity: Optional[str] = None,
        component: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        entity: Optional[str] = None,
        provider: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AuditLogQueryResult:
        """Query audit log entries with filters.
        
        Args:
            action_type: Filter by action type
            severity: Filter by severity
            component: Filter by component
            start_time: Filter by start time (ISO format)
            end_time: Filter by end time (ISO format)
            entity: Filter by target entity
            provider: Filter by provider
            limit: Maximum number of entries to return
            offset: Offset for pagination
            
        Returns:
            Dictionary with keys: entries, total, limit, offset
        """
        filtered = self._logs
        
        # Apply filters
        if action_type:
            filtered = [e for e in filtered if e.action_type == action_type]
        
        if severity:
            filtered = [e for e in filtered if e.severity == severity]
        
        if component:
            filtered = [e for e in filtered if e.component == component]
        
        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]
        
        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]
        
        if entity:
            filtered = [e for e in filtered if entity in e.target_entities]
        
        if provider:
            filtered = [e for e in filtered if e.provider == provider]
        
        # Apply pagination
        total = len(filtered)
        paginated = filtered[offset:offset + limit]
        
        return {
            "entries": paginated,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    
    def export_logs(
        self,
        format_type: str = "json",
        action_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> str:
        """Export audit logs in specified format.
        
        Args:
            format_type: Export format ("json", "csv")
            action_type: Optional filter by action type
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            Exported logs as string
        """
        entries = self.get_entries(
            action_type=action_type,
            start_time=start_time,
            end_time=end_time,
            limit=100000,  # Large limit for export
        )
        
        if format_type == "json":
            return json.dumps(
                [entry.to_dict() for entry in entries["entries"]],
                indent=2,
            )
        elif format_type == "csv":
            return self._export_to_csv(entries["entries"])
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def _export_to_csv(self, entries: List[AuditLogEntry]) -> str:
        """Export entries to CSV format."""
        if not entries:
            return ""
        
        # Define CSV headers
        headers = [
            "timestamp", "action_type", "severity", "component", "user",
            "action", "target_entities", "service_domain", "service_name",
            "result", "provider", "risk_level", "reason",
        ]
        
        lines = [",".join(headers)]
        
        for entry in entries:
            row = [
                entry.timestamp,
                entry.action_type,
                entry.severity,
                entry.component,
                entry.user,
                entry.action,
                ";".join(entry.target_entities),
                entry.service_domain,
                entry.service_name,
                entry.result,
                entry.provider,
                entry.risk_level,
                entry.reason,
            ]
            lines.append(",".join(str(v) for v in row))
        
        return "\n".join(lines)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit log statistics.
        
        Returns:
            Dictionary with log statistics
        """
        total = len(self._logs)
        
        # Count by action type
        action_counts: Dict[str, int] = {}
        for entry in self._logs:
            action_counts[entry.action_type] = action_counts.get(entry.action_type, 0) + 1
        
        # Count by severity
        severity_counts: Dict[str, int] = {}
        for entry in self._logs:
            severity_counts[entry.severity] = severity_counts.get(entry.severity, 0) + 1
        
        # Count by component
        component_counts: Dict[str, int] = {}
        for entry in self._logs:
            component_counts[entry.component] = component_counts.get(entry.component, 0) + 1
        
        # Recent activity (last 24 hours)
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        recent_count = sum(1 for e in self._logs if e.timestamp >= cutoff)
        
        return {
            "total_entries": total,
            "entries_by_action_type": action_counts,
            "entries_by_severity": severity_counts,
            "entries_by_component": component_counts,
            "recent_24h": recent_count,
            "retention_policy": self.retention_policy.to_dict(),
        }
    
    def clear_old_entries(self, days_threshold: int) -> int:
        """Clear entries older than the specified days.
        
        Args:
            days_threshold: Number of days to retain
            
        Returns:
            Number of entries removed
        """
        cutoff = (datetime.now() - timedelta(days=days_threshold)).isoformat()
        original_count = len(self._logs)
        self._logs = [e for e in self._logs if e.timestamp >= cutoff]
        removed = original_count - len(self._logs)
        
        if removed > 0:
            self._save_logs()
            _LOGGER.info("Cleared %d entries older than %d days", removed, days_threshold)
        
        return removed
    
    def clear_all(self) -> int:
        """Clear all audit logs.
        
        Returns:
            Number of entries cleared
        """
        count = len(self._logs)
        self._logs = []
        self._save_logs()
        _LOGGER.info("Cleared all %d audit log entries", count)
        return count
    
    def add_listener(self, listener: Callable[[AuditLogEntry], None]) -> None:
        """Add a listener for new audit log entries.
        
        Args:
            listener: Callback function that receives new entries
        """
        self._event_listeners.append(listener)
        _LOGGER.debug("Added audit log listener. Total listeners: %d", len(self._event_listeners))
    
    def remove_listener(self, listener: Callable[[AuditLogEntry], None]) -> bool:
        """Remove a listener.
        
        Args:
            listener: Callback function to remove
            
        Returns:
            True if listener was found and removed
        """
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)
            _LOGGER.debug("Removed audit log listener. Total listeners: %d", len(self._event_listeners))
            return True
        return False
    
    @property
    def entry_count(self) -> int:
        """Return the current number of log entries."""
        return len(self._logs)
    
    @property
    def retention_policy(self) -> RetentionPolicy:
        """Return the current retention policy."""
        return self._retention_policy
    
    @retention_policy.setter
    def retention_policy(self, policy: RetentionPolicy) -> None:
        """Set a new retention policy."""
        self._retention_policy = policy
        self._apply_retention()


# Convenience functions for common audit log operations

def log_service_call(
    manager: AuditLogManager,
    service_domain: str,
    service_name: str,
    target_entities: List[str],
    result: str,
    provider: str = "",
    risk_level: str = "",
    reason: str = "",
) -> AuditLogEntry:
    """Log a service call.
    
    Args:
        manager: AuditLogManager instance
        service_domain: Service domain (e.g., "light")
        service_name: Service name (e.g., "turn_on")
        target_entities: List of target entities
        result: Result (allowed, denied, executed)
        provider: AI provider
        risk_level: Risk level
        reason: Reason for the decision
        
    Returns:
        Created AuditLogEntry
    """
    return manager.log(
        action_type=ActionType.SERVICE_CALL,
        severity="info" if result == "allowed" else "warning",
        component="service_executor",
        action=f"{service_domain}.{service_name}",
        target_entities=target_entities,
        service_domain=service_domain,
        service_name=service_name,
        result=result,
        provider=provider,
        risk_level=risk_level,
        reason=reason,
    )


def log_permission_decision(
    manager: AuditLogManager,
    action: str,
    target_entities: List[str],
    decision: str,
    risk_level: str,
    reason: str,
) -> AuditLogEntry:
    """Log a permission decision.
    
    Args:
        manager: AuditLogManager instance
        action: The action that was checked
        target_entities: List of target entities
        decision: Decision (permit, deny, prompt)
        risk_level: Risk level of the action
        reason: Reason for the decision
        
    Returns:
        Created AuditLogEntry
    """
    action_type = (
        ActionType.PERMISSION_GRANTED if decision == "permit"
        else ActionType.PERMISSION_DENIED if decision == "deny"
        else ActionType.PERMISSION_REQUESTED
    )
    
    return manager.log(
        action_type=action_type,
        severity="warning" if decision == "deny" else "info",
        component="permissions",
        action=action,
        target_entities=target_entities,
        result=decision,
        risk_level=risk_level,
        reason=reason,
    )


def log_provider_change(
    manager: AuditLogManager,
    old_provider: str,
    new_provider: str,
    reason: str,
    is_failover: bool = False,
) -> AuditLogEntry:
    """Log a provider change.
    
    Args:
        manager: AuditLogManager instance
        old_provider: Previous provider
        new_provider: New provider
        reason: Reason for the change
        is_failover: Whether this was a failover
        
    Returns:
        Created AuditLogEntry
    """
    action_type = (
        ActionType.PROVIDER_FAILED_OVER if is_failover
        else ActionType.PROVIDER_CHANGED
    )
    
    return manager.log(
        action_type=action_type,
        severity="warning" if is_failover else "info",
        component="provider_manager",
        action=f"provider_change:{old_provider}->{new_provider}",
        result="success",
        reason=reason,
        metadata={
            "old_provider": old_provider,
            "new_provider": new_provider,
            "is_failover": is_failover,
        },
    )
