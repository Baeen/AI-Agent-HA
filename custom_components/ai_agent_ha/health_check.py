"""Health check and monitoring system for AI Agent HA integration.

This module provides health check endpoints and monitoring for the integration
to detect and report issues proactively.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckCategory(Enum):
    """Categories of health checks."""

    CONNECTIVITY = "connectivity"
    PERFORMANCE = "performance"
    RESOURCES = "resources"
    CONFIGURATION = "configuration"
    PROVIDER = "provider"
    STORAGE = "storage"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    category: CheckCategory
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=dt_util.now)
    duration_ms: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
        }


@dataclass
class HealthReport:
    """Overall health report."""

    overall_status: HealthStatus
    check_results: List[HealthCheckResult] = field(default_factory=list)
    generated_at: datetime = field(default_factory=dt_util.now)
    integration_version: str = "1.08"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall_status": self.overall_status.value,
            "check_results": [r.to_dict() for r in self.check_results],
            "generated_at": self.generated_at.isoformat(),
            "integration_version": self.integration_version,
            "summary": self._generate_summary(),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = ["## AI Agent HA Health Report"]
        lines.append("")
        lines.append(f"**Overall Status:** {self.overall_status.value.upper()}")
        lines.append(f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Version:** {self.integration_version}")
        lines.append("")

        # Status indicator
        status_emoji = {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.DEGRADED: "⚠️",
            HealthStatus.UNHEALTHY: "❌",
            HealthStatus.UNKNOWN: "❓",
        }
        lines.append(f"Status: {status_emoji.get(self.overall_status, '❓')} {self.overall_status.value}")
        lines.append("")

        lines.append("| Category | Status | Message |")
        lines.append("|----------|--------|---------|")
        for result in self.check_results:
            lines.append(
                f"| {result.category.value} | {result.status.value} | {result.message} |"
            )
        lines.append("")

        # Details for failed checks
        failed = [r for r in self.check_results if r.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)]
        if failed:
            lines.append("### Failed/Degraded Checks")
            lines.append("")
            for result in failed:
                lines.append(f"#### {result.category.value}: {result.message}")
                lines.append("")
                if result.details:
                    lines.append("```")
                    for key, value in result.details.items():
                        lines.append(f"{key}: {value}")
                    lines.append("```")
                lines.append("")

        return "\n".join(lines)

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        return {
            "total_checks": len(self.check_results),
            "healthy": sum(1 for r in self.check_results if r.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for r in self.check_results if r.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for r in self.check_results if r.status == HealthStatus.UNHEALTHY),
        }


class PerformanceMetrics:
    """Track performance metrics for the integration."""

    def __init__(self):
        """Initialize metrics tracker."""
        self._response_times: List[Tuple[datetime, float]] = []
        self._api_call_count: int = 0
        self._error_count: int = 0
        self._task_count: int = 0
        self._last_reset: datetime = dt_util.now()
        self._max_entries = 1000

    def record_response_time(self, duration_ms: float):
        """Record a response time measurement."""
        self._response_times.append((dt_util.now(), duration_ms))
        # Trim old entries
        cutoff = dt_util.now() - timedelta(hours=24)
        self._response_times = [
            (t, d) for t, d in self._response_times if t >= cutoff
        ]
        if len(self._response_times) > self._max_entries:
            self._response_times = self._response_times[-self._max_entries:]

    def record_api_call(self, success: bool = True):
        """Record an API call."""
        self._api_call_count += 1
        if not success:
            self._error_count += 1

    def record_task(self):
        """Record a task execution."""
        self._task_count += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        now = dt_util.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(hours=24)

        # Calculate statistics
        recent_times = [d for t, d in self._response_times if t >= hour_ago]
        daily_times = [d for t, d in self._response_times if t >= day_ago]

        return {
            "response_times": {
                "last_hour_count": len(recent_times),
                "last_hour_avg_ms": sum(recent_times) / len(recent_times) if recent_times else 0,
                "last_hour_max_ms": max(recent_times) if recent_times else 0,
                "last_hour_min_ms": min(recent_times) if recent_times else 0,
                "last_24h_count": len(daily_times),
                "last_24h_avg_ms": sum(daily_times) / len(daily_times) if daily_times else 0,
            },
            "api_calls": {
                "total": self._api_call_count,
                "errors": self._error_count,
                "success_rate": (self._api_call_count - self._error_count) / self._api_call_count * 100 if self._api_call_count > 0 else 100,
            },
            "tasks": {
                "total": self._task_count,
            },
            "period_start": self._last_reset.isoformat(),
            "period_end": now.isoformat(),
        }


class HealthCheckManager:
    """Manages health checks for the integration."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the health check manager."""
        self.hass = hass
        self._check_results: Dict[str, HealthCheckResult] = {}
        self._performance_metrics = PerformanceMetrics()
        self._health_check_callbacks: List = []
        self._last_full_check: Optional[datetime] = None
        self._entity_registry: Optional[Dict[str, Any]] = {}

    def register_check(self, name: str, check_func):
        """Register a custom health check function."""
        self._health_check_callbacks.append((name, check_func))

    async def run_full_health_check(self) -> HealthReport:
        """Run all health checks and return a report."""
        self._last_full_check = dt_util.now()
        results = []

        # Run built-in checks
        results.append(await self._check_api_connectivity())
        results.append(await self._check_provider_status())
        results.append(await self._check_storage())
        results.append(await self._check_configuration())
        results.append(await self._check_performance())

        # Run custom checks
        for name, check_func in self._health_check_callbacks:
            try:
                result = check_func()
                if asyncio.iscoroutine(result):
                    result = await result
                if isinstance(result, HealthCheckResult):
                    results.append(result)
            except Exception as e:
                _LOGGER.error("Custom health check '%s' failed: %s", name, e)
                results.append(HealthCheckResult(
                    category=CheckCategory.CONFIGURATION,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Custom check '{name}' failed: {str(e)}",
                ))

        # Store results
        self._check_results = {r.category.value: r for r in results}

        # Determine overall status
        statuses = [r.status for r in results]
        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        report = HealthReport(
            overall_status=overall,
            check_results=results,
        )

        # Update entity states
        await self._update_health_entities(report)

        return report

    async def _check_api_connectivity(self) -> HealthCheckResult:
        """Check connectivity to Home Assistant API."""
        start_time = time.time()
        try:
            # Try to get a simple state
            states = self.hass.states.async_all()
            duration = (time.time() - start_time) * 1000

            if states is not None:
                return HealthCheckResult(
                    category=CheckCategory.CONNECTIVITY,
                    status=HealthStatus.HEALTHY,
                    message="Home Assistant API is accessible",
                    details={
                        "entity_count": len(states),
                        "response_time_ms": round(duration, 2),
                    },
                )
            else:
                return HealthCheckResult(
                    category=CheckCategory.CONNECTIVITY,
                    status=HealthStatus.UNHEALTHY,
                    message="Cannot access Home Assistant API",
                    details={"response_time_ms": round(duration, 2)},
                )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return HealthCheckResult(
                category=CheckCategory.CONNECTIVITY,
                status=HealthStatus.UNHEALTHY,
                message=f"API connectivity check failed: {str(e)}",
                details={"response_time_ms": round(duration, 2)},
            )

    async def _check_provider_status(self) -> HealthCheckResult:
        """Check AI provider status."""
        start_time = time.time()
        try:
            # Get the agent instance to check provider configuration
            domain_data = self.hass.data.get("ai_agent_ha")
            if not domain_data or "agents" not in domain_data:
                return HealthCheckResult(
                    category=CheckCategory.PROVIDER,
                    status=HealthStatus.DEGRADED,
                    message="No AI agent configured",
                    details={"response_time_ms": 0},
                )

            agents = domain_data["agents"]
            if not agents:
                return HealthCheckResult(
                    category=CheckCategory.PROVIDER,
                    status=HealthStatus.DEGRADED,
                    message="No AI agent instances available",
                )

            # Check the first agent's provider
            agent = list(agents.values())[0]
            provider = getattr(agent, "config", {}).get("ai_provider", "unknown")

            # Check if API key is configured
            api_key_configured = hasattr(agent, "config") and "api_key" in agent.config

            duration = (time.time() - start_time) * 1000

            if api_key_configured:
                return HealthCheckResult(
                    category=CheckCategory.PROVIDER,
                    status=HealthStatus.HEALTHY,
                    message=f"AI provider '{provider}' is configured",
                    details={
                        "provider": provider,
                        "api_key_configured": True,
                        "response_time_ms": round(duration, 2),
                    },
                )
            else:
                return HealthCheckResult(
                    category=CheckCategory.PROVIDER,
                    status=HealthStatus.DEGRADED,
                    message=f"AI provider '{provider}' configured but API key missing",
                    details={
                        "provider": provider,
                        "api_key_configured": False,
                        "response_time_ms": round(duration, 2),
                    },
                )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return HealthCheckResult(
                category=CheckCategory.PROVIDER,
                status=HealthStatus.UNHEALTHY,
                message=f"Provider check failed: {str(e)}",
                details={"response_time_ms": round(duration, 2)},
            )

    async def _check_storage(self) -> HealthCheckResult:
        """Check storage availability."""
        start_time = time.time()
        try:
            # Try to access the storage
            storage_path = self.hass.config.path("custom_components/ai_agent_ha_storage")
            import os
            exists = os.path.exists(os.path.dirname(storage_path) if os.path.dirname(storage_path) else "/")

            duration = (time.time() - start_time) * 1000

            if exists:
                return HealthCheckResult(
                    category=CheckCategory.STORAGE,
                    status=HealthStatus.HEALTHY,
                    message="Storage is available",
                    details={"response_time_ms": round(duration, 2)},
                )
            else:
                return HealthCheckResult(
                    category=CheckCategory.STORAGE,
                    status=HealthStatus.DEGRADED,
                    message="Storage path verification failed",
                    details={"response_time_ms": round(duration, 2)},
                )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return HealthCheckResult(
                category=CheckCategory.STORAGE,
                status=HealthStatus.UNHEALTHY,
                message=f"Storage check failed: {str(e)}",
                details={"response_time_ms": round(duration, 2)},
            )

    async def _check_configuration(self) -> HealthCheckResult:
        """Check configuration validity."""
        start_time = time.time()
        try:
            domain_data = self.hass.data.get("ai_agent_ha")
            if not domain_data:
                return HealthCheckResult(
                    category=CheckCategory.CONFIGURATION,
                    status=HealthStatus.DEGRADED,
                    message="Integration not fully initialized",
                )

            # Check for config entries
            config_entries = self.hass.config_entries.async_entries("ai_agent_ha")
            if not config_entries:
                return HealthCheckResult(
                    category=CheckCategory.CONFIGURATION,
                    status=HealthStatus.DEGRADED,
                    message="No configuration entries found",
                )

            # Check each config entry
            unhealthy_entries = []
            for entry in config_entries:
                if entry.state.value == "loaded":
                    continue
                else:
                    unhealthy_entries.append({
                        "entry_id": entry.entry_id,
                        "state": entry.state.value,
                    })

            duration = (time.time() - start_time) * 1000

            if unhealthy_entries:
                return HealthCheckResult(
                    category=CheckCategory.CONFIGURATION,
                    status=HealthStatus.DEGRADED,
                    message=f"Some config entries not properly loaded",
                    details={
                        "entries": unhealthy_entries,
                        "response_time_ms": round(duration, 2),
                    },
                )

            return HealthCheckResult(
                category=CheckCategory.CONFIGURATION,
                status=HealthStatus.HEALTHY,
                message="Configuration is valid",
                details={
                    "config_entries": len(config_entries),
                    "response_time_ms": round(duration, 2),
                },
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return HealthCheckResult(
                category=CheckCategory.CONFIGURATION,
                status=HealthStatus.UNHEALTHY,
                message=f"Configuration check failed: {str(e)}",
                details={"response_time_ms": round(duration, 2)},
            )

    async def _check_performance(self) -> HealthCheckResult:
        """Check performance metrics."""
        metrics = self._performance_metrics.get_metrics()
        avg_response = metrics["response_times"]["last_hour_avg_ms"]

        # Determine status based on response time
        if avg_response < 1000:  # Less than 1 second
            status = HealthStatus.HEALTHY
            message = "Performance is optimal"
        elif avg_response < 5000:  # Less than 5 seconds
            status = HealthStatus.DEGRADED
            message = "Performance is degraded"
        else:
            status = HealthStatus.UNHEALTHY
            message = "Performance is poor"

        return HealthCheckResult(
            category=CheckCategory.PERFORMANCE,
            status=status,
            message=message,
            details={
                "avg_response_time_ms": round(avg_response, 2),
                "last_hour_calls": metrics["response_times"]["last_hour_count"],
                "success_rate": round(metrics["api_calls"]["success_rate"], 2),
            },
        )

    async def _update_health_entities(self, report: HealthReport):
        """Update health sensor entities."""
        # Create/update sensor entities for health status
        try:
            # This would typically create Home Assistant sensor entities
            # For now, just log the status
            _LOGGER.debug("Health report: %s - %d checks", report.overall_status.value, len(report.check_results))
        except Exception as e:
            _LOGGER.error("Failed to update health entities: %s", e)

    def record_response_time(self, duration_ms: float):
        """Record a response time measurement."""
        self._performance_metrics.record_response_time(duration_ms)

    def record_api_call(self, success: bool = True):
        """Record an API call."""
        self._performance_metrics.record_api_call(success)

    def record_task(self):
        """Record a task execution."""
        self._performance_metrics.record_task()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return self._performance_metrics.get_metrics()

    def get_latest_report(self) -> Optional[HealthReport]:
        """Get the latest health report."""
        if not self._check_results:
            return None

        # Determine overall status
        results = list(self._check_results.values())
        statuses = [r.status for r in results]

        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return HealthReport(
            overall_status=overall,
            check_results=results,
        )

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostic information for debugging."""
        report = await self.run_full_health_check()

        # Get system information
        import sys
        import platform

        diagnostics = {
            "health_report": report.to_dict(),
            "performance_metrics": self._performance_metrics.get_metrics(),
            "system_info": {
                "python_version": sys.version,
                "platform": platform.platform(),
                "homeassistant_config_dir": self.hass.config.config_dir,
            },
            "integration_data": {
                "config_entries": [
                    {
                        "entry_id": entry.entry_id,
                        "domain": entry.domain,
                        "state": entry.state.value,
                        "title": entry.title,
                    }
                    for entry in self.hass.config_entries.async_entries("ai_agent_ha")
                ],
            },
        }

        return diagnostics
