"""Error recovery mechanisms for the AI Agent HA integration.

This module provides comprehensive error recovery mechanisms including:
- Circuit breaker pattern for AI providers
- Retry handler with exponential backoff and jitter
- Error recovery manager for coordinating recovery actions

The circuit breaker pattern prevents repeated failures by opening the circuit
after a threshold of consecutive failures, blocking further attempts until
a reset timeout elapses.

The retry handler implements exponential backoff with jitter to handle
transient failures, where delay = base_delay * 2^attempt + random_jitter.
"""

import asyncio
import logging
import random
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

from .const import (
    CONF_CIRCUIT_FAILURE_THRESHOLD,
    CONF_CIRCUIT_TIMEOUT,
    CONF_MAX_RETRIES,
    CONF_RETRY_DELAY,
    AI_PROVIDERS,
)

# Default values for error recovery
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0
DEFAULT_CIRCUIT_FAILURE_THRESHOLD = 5
DEFAULT_CIRCUIT_RESET_TIMEOUT = 60
DEFAULT_BACKOFF_BASE_DELAY = 1
DEFAULT_BACKOFF_MAX_DELAY = 30

_LOGGER = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Enum representing the state of a circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open and execution is blocked."""

    def __init__(self, provider: str, state: str, reset_after: float = 0):
        """Initialize the exception.

        Args:
            provider: The AI provider name
            state: Current circuit state
            reset_after: Seconds until circuit resets to half-open
        """
        self.provider = provider
        self.state = state
        self.reset_after = reset_after
        super().__init__(
            f"Circuit breaker for '{provider}' is {state}. "
            f"Reset after {reset_after:.1f}s" if reset_after > 0
            else f"Circuit breaker for '{provider}' is {state}"
        )


class CircuitBreaker:
    """Circuit breaker implementation for AI provider calls.

    The circuit breaker monitors failures for a specific AI provider and
    opens the circuit after reaching the failure threshold. This prevents
    cascading failures when a provider is unavailable.

    States:
        - CLOSED: Normal operation, requests pass through
        - OPEN: Circuit tripped, requests are blocked
        - HALF_OPEN: Test mode, one request allowed through

    Example:
        >>> cb = CircuitBreaker(failure_threshold=5, reset_timeout=60)
        >>> if cb.can_execute():
        ...     try:
        ...         result = await call_provider()
        ...         cb.record_success()
        ...     except Exception as e:
        ...         cb.record_failure()
        """

    def __init__(
        self,
        failure_threshold: int = DEFAULT_CIRCUIT_FAILURE_THRESHOLD,
        reset_timeout: float = DEFAULT_CIRCUIT_RESET_TIMEOUT,
    ):
        """Initialize the circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            reset_timeout: Seconds to wait before transitioning to half-open state
        """
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = CircuitState.CLOSED
        self._opened_at: Optional[float] = None
        self._total_failures = 0
        self._total_successes = 0
        self._total_tripped = 0

        _LOGGER.debug(
            "CircuitBreaker initialized: threshold=%d, timeout=%ds",
            failure_threshold,
            reset_timeout,
        )

    def record_success(self) -> None:
        """Record a successful operation.

        Resets the circuit breaker to closed state if it was half-open,
        and resets the consecutive failure counter.
        """
        self._success_count += 1
        self._total_successes += 1

        if self._state == CircuitState.HALF_OPEN:
            # Test request succeeded, close the circuit
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._opened_at = None
            _LOGGER.info(
                "Circuit breaker CLOSED after half-open test success"
            )
        else:
            # Reset consecutive failure count in closed state
            self._failure_count = 0

        _LOGGER.debug(
            "Success recorded: state=%s, failures=%d/%d",
            self._state.value,
            self._failure_count,
            self._failure_threshold,
        )

    def record_failure(self) -> None:
        """Record a failed operation.

        Increments the failure counter and opens the circuit if the
        threshold is reached.
        """
        self._failure_count += 1
        self._total_failures += 1
        self._last_failure_time = time.monotonic()

        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._total_tripped += 1
            _LOGGER.warning(
                "Circuit breaker OPENED after %d consecutive failures "
                "(threshold: %d)",
                self._failure_count,
                self._failure_threshold,
            )

    def can_execute(self) -> bool:
        """Check if the circuit breaker allows execution.

        Returns:
            True if execution is allowed, False otherwise

        Raises:
            CircuitBreakerOpenError: If circuit is open and timeout hasn't elapsed
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if reset timeout has elapsed
            if self._opened_at is not None:
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self._reset_timeout:
                    # Transition to half-open state
                    self._state = CircuitState.HALF_OPEN
                    _LOGGER.info(
                        "Circuit breaker transitioned to HALF_OPEN after %.1fs",
                        elapsed,
                    )
                    return True
                else:
                    remaining = self._reset_timeout - elapsed
                    raise CircuitBreakerOpenError(
                        provider="unknown",
                        state=self._state.value,
                        reset_after=remaining,
                    )
            return False

        # HALF_OPEN state - allow one request through
        return True

    def get_state(self) -> str:
        """Return the current circuit breaker state.

        Checks for automatic transition from open to half-open before
        returning the state.

        Returns:
            State string: "closed", "open", or "half_open"
        """
        # Check for automatic transition
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._reset_timeout:
                self._state = CircuitState.HALF_OPEN
                _LOGGER.debug(
                    "Auto-transitioned to HALF_OPEN (elapsed: %.1fs)", elapsed
                )

        return self._state.value

    async def reset(self) -> None:
        """Manually reset the circuit breaker to closed state.

        This is an async method for consistency with the ErrorRecoveryManager
        interface, but it completes immediately.
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        self._last_failure_time = None
        _LOGGER.info("Circuit breaker manually RESET")

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics.

        Returns:
            Dictionary containing circuit breaker statistics
        """
        state = self.get_state()
        stats = {
            "state": state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "total_tripped": self._total_tripped,
            "failure_threshold": self._failure_threshold,
        }

        if self._opened_at is not None and state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._opened_at
            stats["reset_after"] = max(
                0, self._reset_timeout - elapsed
            )
        elif state == CircuitState.HALF_OPEN:
            stats["reset_after"] = 0

        return stats


class RetryHandler:
    """Retry handler with exponential backoff and jitter.

    Implements retry logic for transient failures with exponential backoff
    to avoid overwhelming the service. The delay formula is:
        delay = min(base_delay * 2^attempt, max_delay) + random_jitter

    Where jitter is a random value between 0 and 1 seconds to prevent
    the "thundering herd" problem.

    Example:
        >>> handler = RetryHandler(max_retries=3, base_delay=1, max_delay=30)
        >>> async def my_func():
        ...     return await some_async_operation()
        >>> result = await handler.execute(my_func)
        """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BACKOFF_BASE_DELAY,
        max_delay: float = DEFAULT_BACKOFF_MAX_DELAY,
        jitter_range: float = 1.0,
    ):
        """Initialize the retry handler.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds
            jitter_range: Maximum jitter in seconds (0 to jitter_range)
        """
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._jitter_range = jitter_range
        self._attempt_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._last_error: Optional[Exception] = None
        self._total_wait_time = 0.0

        _LOGGER.debug(
            "RetryHandler initialized: max_retries=%d, base_delay=%ds, max_delay=%ds",
            max_retries,
            base_delay,
            max_delay,
        )

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate the delay for a given attempt number.

        Uses exponential backoff with optional jitter:
            delay = min(base_delay * 2^attempt, max_delay) + random_jitter

        Args:
            attempt: The attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base_delay * 2^attempt
        exponential_delay = self._base_delay * (2 ** attempt)

        # Cap at max_delay
        capped_delay = min(exponential_delay, self._max_delay)

        # Add jitter (random value between 0 and jitter_range)
        jitter = random.uniform(0, self._jitter_range)

        total_delay = capped_delay + jitter
        _LOGGER.debug(
            "Delay calculation: attempt=%d, exponential=%.2fs, capped=%.2fs, jitter=%.2fs, total=%.2fs",
            attempt,
            exponential_delay,
            capped_delay,
            jitter,
            total_delay,
        )

        return total_delay

    async def execute(
        self,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a function with retries.

        Attempts to execute the given function up to max_retries times,
        applying exponential backoff between attempts.

        Args:
            func: Async callable to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            Exception: The last exception if all retries are exhausted
        """
        last_exception = None

        for attempt in range(self._max_retries + 1):
            self._attempt_count += 1

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                self._success_count += 1
                _LOGGER.debug(
                    "Function executed successfully on attempt %d/%d",
                    attempt + 1,
                    self._max_retries + 1,
                )
                return result

            except Exception as e:
                last_exception = e
                self._failure_count += 1
                self._last_error = e

                _LOGGER.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt + 1,
                    self._max_retries + 1,
                    func.__name__,
                    str(e),
                )

                # Don't wait after the last attempt
                if attempt < self._max_retries:
                    delay = self._calculate_delay(attempt)
                    self._total_wait_time += delay
                    _LOGGER.info(
                        "Retrying %s in %.2fs (attempt %d/%d)",
                        func.__name__,
                        delay,
                        attempt + 2,
                        self._max_retries + 1,
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        _LOGGER.error(
            "All %d retries exhausted for %s. Last error: %s",
            self._max_retries,
            func.__name__,
            str(self._last_error),
        )
        raise last_exception

    def get_stats(self) -> Dict[str, Any]:
        """Get retry handler statistics.

        Returns:
            Dictionary containing retry statistics
        """
        return {
            "total_attempts": self._attempt_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "last_error": str(self._last_error) if self._last_error else None,
            "total_wait_time": self._total_wait_time,
            "max_retries": self._max_retries,
            "base_delay": self._base_delay,
            "max_delay": self._max_delay,
        }


class ErrorRecoveryManager:
    """Main coordinator for error recovery mechanisms.

    Manages circuit breakers for each AI provider and coordinates
    retry logic with exponential backoff. Provides health status
    reporting for the entire recovery system.

    The manager maintains:
    - A circuit breaker per AI provider
    - A shared retry handler for retry operations
    - Statistics for monitoring and debugging

    Example:
        >>> config = {
        ...     CONF_MAX_RETRIES: 3,
        ...     CONF_CIRCUIT_FAILURE_THRESHOLD: 5,
        ... }
        >>> manager = ErrorRecoveryManager(config)
        >>> async def call_provider():
        ...     return await ai_provider.call()
        >>> result = await manager.execute_with_recovery(
        ...     call_provider,
        ...     recovery_action=lambda: fallback_provider.call()
        ... )
        """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the error recovery manager.

        Args:
            config: Configuration dictionary with optional keys:
                - CONF_MAX_RETRIES: Maximum retry attempts (default: 3)
                - CONF_RETRY_DELAY: Base retry delay in seconds (default: 2)
                - CONF_CIRCUIT_FAILURE_THRESHOLD: Failure threshold (default: 5)
                - CONF_CIRCUIT_TIMEOUT: Circuit reset timeout in seconds (default: 60)
        """
        self._config = config or {}
        self._max_retries = self._config.get(
            CONF_MAX_RETRIES, DEFAULT_MAX_RETRIES
        )
        self._retry_delay = self._config.get(CONF_RETRY_DELAY, DEFAULT_RETRY_DELAY)
        self._circuit_threshold = self._config.get(
            CONF_CIRCUIT_FAILURE_THRESHOLD, DEFAULT_CIRCUIT_FAILURE_THRESHOLD
        )
        self._circuit_timeout = self._config.get(
            CONF_CIRCUIT_TIMEOUT, DEFAULT_CIRCUIT_RESET_TIMEOUT
        )

        # Initialize retry handler
        self._retry_handler = RetryHandler(
            max_retries=self._max_retries,
            base_delay=self._retry_delay,
        )

        # Initialize circuit breakers for each AI provider
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        for provider in AI_PROVIDERS:
            self._circuit_breakers[provider] = CircuitBreaker(
                failure_threshold=self._circuit_threshold,
                reset_timeout=self._circuit_timeout,
            )

        # Default circuit breaker for unknown providers
        self._default_circuit = CircuitBreaker(
            failure_threshold=self._circuit_threshold,
            reset_timeout=self._circuit_timeout,
        )

        _LOGGER.info(
            "ErrorRecoveryManager initialized: max_retries=%d, circuit_threshold=%d, circuit_timeout=%ds",
            self._max_retries,
            self._circuit_threshold,
            self._circuit_timeout,
        )

    def _get_circuit_breaker(self, provider: Optional[str] = None) -> CircuitBreaker:
        """Get the circuit breaker for a provider.

        Returns the circuit breaker for the specified provider, or the
        default circuit breaker if the provider is unknown.

        Args:
            provider: AI provider name, or None for default

        Returns:
            CircuitBreaker instance for the provider
        """
        if provider and provider in self._circuit_breakers:
            return self._circuit_breakers[provider]
        return self._default_circuit

    async def execute_with_recovery(
        self,
        func: Callable,
        *args: Any,
        recovery_action: Optional[Callable] = None,
        provider: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a function with full error recovery.

        This is the main entry point for error recovery. It:
        1. Checks the circuit breaker for the provider
        2. Executes the function with retries
        3. Records success or failure on the circuit breaker
        4. Executes recovery action if all retries fail

        Args:
            func: Async callable to execute
            *args: Positional arguments for the function
            recovery_action: Optional async callable to execute on failure
            provider: AI provider name for circuit breaker selection
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            Exception: The last exception if all retries and recovery fail
        """
        circuit = self._get_circuit_breaker(provider)

        # Check if circuit allows execution
        try:
            if not circuit.can_execute():
                _LOGGER.warning(
                    "Circuit breaker blocking execution for provider '%s'",
                    provider,
                )
                if recovery_action:
                    return await self._execute_recovery(recovery_action)
                raise CircuitBreakerOpenError(
                    provider=provider or "unknown",
                    state=circuit.get_state(),
                    reset_after=circuit.get_stats().get("reset_after", 0),
                )
        except CircuitBreakerOpenError:
            if recovery_action:
                return await self._execute_recovery(recovery_action)
            raise

        _LOGGER.debug(
            "Executing %s with recovery (provider: %s)",
            func.__name__,
            provider,
        )

        try:
            # Execute with retries
            result = await self._retry_handler.execute(func, *args, **kwargs)

            # Record success
            circuit.record_success()
            _LOGGER.debug(
                "Execution successful for %s (provider: %s)",
                func.__name__,
                provider,
            )
            return result

        except CircuitBreakerOpenError:
            # Circuit was open, recovery action should handle this
            _LOGGER.warning(
                "Circuit breaker opened during execution for %s",
                func.__name__,
            )
            if recovery_action:
                return await self._execute_recovery(recovery_action)
            raise

        except Exception as e:
            # Record failure
            circuit.record_failure()
            _LOGGER.warning(
                "Execution failed for %s (provider: %s): %s",
                func.__name__,
                provider,
                str(e),
            )

            # Execute recovery action if provided
            if recovery_action:
                return await self._execute_recovery(recovery_action)

            raise

    async def _execute_recovery(
        self,
        recovery_action: Callable,
    ) -> Any:
        """Execute a recovery action with retries.

        Args:
            recovery_action: Async callable to execute

        Returns:
            The result of the recovery action

        Raises:
            Exception: If recovery action fails
        """
        _LOGGER.info("Executing recovery action")
        try:
            if asyncio.iscoroutinefunction(recovery_action):
                return await recovery_action()
            else:
                return recovery_action()
        except Exception as e:
            _LOGGER.error("Recovery action failed: %s", str(e))
            raise

    def get_health_status(self) -> Dict[str, Any]:
        """Get the health status of the entire recovery system.

        Returns comprehensive status including:
        - Overall system health
        - Individual circuit breaker states per provider
        - Retry handler statistics

        Returns:
            Dictionary containing health status
        """
        circuit_statuses = {}
        healthy_providers = 0
        unhealthy_providers = 0

        for provider, circuit in self._circuit_breakers.items():
            stats = circuit.get_stats()
            circuit_statuses[provider] = stats

            if stats["state"] == CircuitState.CLOSED.value:
                healthy_providers += 1
            else:
                unhealthy_providers += 1

        # Check default circuit
        default_stats = self._default_circuit.get_stats()

        # Determine overall health
        if unhealthy_providers == 0:
            overall_health = "healthy"
        elif unhealthy_providers <= len(AI_PROVIDERS) // 2:
            overall_health = "degraded"
        else:
            overall_health = "unhealthy"

        health_status = {
            "overall_health": overall_health,
            "total_providers": len(AI_PROVIDERS),
            "healthy_providers": healthy_providers,
            "unhealthy_providers": unhealthy_providers,
            "circuit_breakers": circuit_statuses,
            "default_circuit": default_stats,
            "retry_handler": self._retry_handler.get_stats(),
        }

        _LOGGER.debug("Health status: %s", overall_health)
        return health_status

    def reset_all_circuits(self) -> None:
        """Reset all circuit breakers to closed state.

        This is useful after a provider outage is resolved or
        for maintenance purposes.
        """
        _LOGGER.info("Resetting all circuit breakers")

        for provider, circuit in self._circuit_breakers.items():
            asyncio.create_task(circuit.reset())
            _LOGGER.debug("Reset circuit breaker for '%s'", provider)

        # Reset default circuit
        asyncio.create_task(self._default_circuit.reset())
        _LOGGER.debug("Reset default circuit breaker")

    def reset_circuit(self, provider: str) -> None:
        """Reset the circuit breaker for a specific provider.

        Args:
            provider: AI provider name
        """
        circuit = self._get_circuit_breaker(provider)
        asyncio.create_task(circuit.reset())
        _LOGGER.debug("Reset circuit breaker for '%s'", provider)

    def get_circuit_state(self, provider: str) -> str:
        """Get the circuit breaker state for a provider.

        Args:
            provider: AI provider name

        Returns:
            State string: "closed", "open", or "half_open"
        """
        circuit = self._get_circuit_breaker(provider)
        return circuit.get_state()

    def get_retry_stats(self) -> Dict[str, Any]:
        """Get the retry handler statistics.

        Returns:
            Dictionary containing retry statistics
        """
        return self._retry_handler.get_stats()

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update the configuration and recreate affected components.

        Args:
            config: New configuration dictionary
        """
        _LOGGER.info("Updating ErrorRecoveryManager config")
        self._config = {**self._config, **config}

        # Update max retries if changed
        new_max_retries = self._config.get(
            CONF_MAX_RETRIES, self._max_retries
        )
        if new_max_retries != self._max_retries:
            self._max_retries = new_max_retries
            self._retry_handler = RetryHandler(
                max_retries=self._max_retries,
                base_delay=self._retry_delay,
            )
            _LOGGER.info("Updated max_retries to %d", self._max_retries)

        # Update circuit thresholds if changed
        new_threshold = self._config.get(
            CONF_CIRCUIT_FAILURE_THRESHOLD, self._circuit_threshold
        )
        if new_threshold != self._circuit_threshold:
            self._circuit_threshold = new_threshold
            for circuit in self._circuit_breakers.values():
                circuit._failure_threshold = new_threshold
            self._default_circuit._failure_threshold = new_threshold
            _LOGGER.info("Updated circuit threshold to %d", self._circuit_threshold)


def get_error_recovery_manager(
    config: Optional[Dict[str, Any]] = None,
) -> ErrorRecoveryManager:
    """Get or create the ErrorRecoveryManager singleton.

    Args:
        config: Optional configuration dictionary

    Returns:
        ErrorRecoveryManager instance
    """
    if not hasattr(get_error_recovery_manager, "_instance"):
        get_error_recovery_manager._instance = ErrorRecoveryManager(config)
    return get_error_recovery_manager._instance
