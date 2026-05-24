"""Performance optimizations for AI Agent HA integration.

This module provides caching, parallel execution, entity batch fetching,
and performance monitoring capabilities to optimize the AI Agent HA integration.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from homeassistant.core import HomeAssistant

# Singleton instances
_data_cache: Optional[DataCache] = None
_parallel_executor: Optional[ParallelExecutor] = None
_performance_monitor: Optional[PerformanceMonitor] = None


@dataclass
class CacheEntry:
    """Cache entry with expiration."""
    
    data: Any
    created_at: float
    ttl: float  # Time-to-live in seconds
    
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() - self.created_at > self.ttl


class InMemoryCache:
    """In-memory cache with TTL support."""
    
    def __init__(self, default_ttl: float = 300.0):
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry.data
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache."""
        ttl = ttl or self.default_ttl
        self._cache[key] = CacheEntry(data=value, created_at=time.time(), ttl=ttl)
    
    def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "size": len(self._cache)
        }


class DataCache:
    """Specialized cache for Home Assistant data."""
    
    # Default TTLs for different data types
    ENTITY_STATES_TTL = 30.0  # Entity states change frequently
    ENTITY_REGISTRY_TTL = 300.0  # Registry changes infrequently
    AREA_REGISTRY_TTL = 300.0
    DEVICE_REGISTRY_TTL = 300.0
    AUTOMATIONS_TTL = 60.0
    SCENES_TTL = 120.0
    CALENDAR_EVENTS_TTL = 60.0
    STATISTICS_TTL = 600.0  # Statistics don't change often
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._cache = InMemoryCache()
    
    def get_entity_states(self) -> Optional[List[Dict]]:
        """Get cached entity states."""
        return self._cache.get("entity_states")
    
    def set_entity_states(self, states: List[Dict]) -> None:
        """Cache entity states."""
        if self.enabled:
            self._cache.set("entity_states", states, ttl=self.ENTITY_STATES_TTL)
    
    def get_entity_registry(self) -> Optional[List[Dict]]:
        """Get cached entity registry."""
        return self._cache.get("entity_registry")
    
    def set_entity_registry(self, registry: List[Dict]) -> None:
        """Cache entity registry."""
        if self.enabled:
            self._cache.set("entity_registry", registry, ttl=self.ENTITY_REGISTRY_TTL)
    
    def get_area_registry(self) -> Optional[List[Dict]]:
        """Get cached area registry."""
        return self._cache.get("area_registry")
    
    def set_area_registry(self, registry: List[Dict]) -> None:
        """Cache area registry."""
        if self.enabled:
            self._cache.set("area_registry", registry, ttl=self.AREA_REGISTRY_TTL)
    
    def get_device_registry(self) -> Optional[List[Dict]]:
        """Get cached device registry."""
        return self._cache.get("device_registry")
    
    def set_device_registry(self, registry: List[Dict]) -> None:
        """Cache device registry."""
        if self.enabled:
            self._cache.set("device_registry", registry, ttl=self.DEVICE_REGISTRY_TTL)
    
    def get_automations(self) -> Optional[List[Dict]]:
        """Get cached automations."""
        return self._cache.get("automations")
    
    def set_automations(self, automations: List[Dict]) -> None:
        """Cache automations."""
        if self.enabled:
            self._cache.set("automations", automations, ttl=self.AUTOMATIONS_TTL)
    
    def get_scenes(self) -> Optional[List[Dict]]:
        """Get cached scenes."""
        return self._cache.get("scenes")
    
    def set_scenes(self, scenes: List[Dict]) -> None:
        """Cache scenes."""
        if self.enabled:
            self._cache.set("scenes", scenes, ttl=self.SCENES_TTL)
    
    def get_calendar_events(self) -> Optional[List[Dict]]:
        """Get cached calendar events."""
        return self._cache.get("calendar_events")
    
    def set_calendar_events(self, events: List[Dict]) -> None:
        """Cache calendar events."""
        if self.enabled:
            self._cache.set("calendar_events", events, ttl=self.CALENDAR_EVENTS_TTL)
    
    def get_statistics(self, key: str) -> Optional[Any]:
        """Get cached statistics."""
        return self._cache.get(f"statistics:{key}")
    
    def set_statistics(self, key: str, data: Any) -> None:
        """Cache statistics."""
        if self.enabled:
            self._cache.set(f"statistics:{key}", data, ttl=self.STATISTICS_TTL)
    
    def invalidate_all(self) -> None:
        """Invalidate all cache entries."""
        self._cache.clear()
    
    def invalidate_entity(self, entity_id: str) -> None:
        """Invalidate cache entries related to a specific entity."""
        # Invalidate entity states and any cached queries that might include this entity
        self._cache.invalidate("entity_states")
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.stats


class ParallelExecutor:
    """Execute multiple independent operations in parallel."""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
    
    async def execute_parallel(self, coroutines: List[Callable]) -> Dict[str, Any]:
        """Execute multiple coroutines in parallel with concurrency limit."""
        # Use asyncio.Semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def limited_execute(coro_func):
            async with semaphore:
                return await coro_func()
        
        tasks = [asyncio.create_task(limited_execute(coro)) for coro in coroutines]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Separate successful results from exceptions
        successful = [r for r in results if not isinstance(r, Exception)]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        return {
            "results": successful,
            "exceptions": exceptions,
            "success_count": len(successful),
            "failure_count": len(exceptions)
        }
    
    async def execute_with_timeout(self, coroutine: Callable, timeout: float) -> Any:
        """Execute a coroutine with a timeout."""
        try:
            return await asyncio.wait_for(coroutine(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {timeout} seconds")


class EntityBatchFetcher:
    """Fetch multiple entity states efficiently."""
    
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
    
    async def get_entity_states_batch(self, entity_ids: List[str]) -> Dict[str, Dict]:
        """Get states for multiple entities in a single efficient call."""
        result = {}
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            if state:
                result[entity_id] = {
                    "entity_id": entity_id,
                    "state": state.state,
                    "attributes": state.attributes,
                    "last_changed": state.last_changed.isoformat(),
                    "last_updated": state.last_updated.isoformat(),
                }
        return result
    
    async def get_entities_by_domains(self, domains: List[str]) -> Dict[str, List[Dict]]:
        """Get all entities for multiple domains."""
        result = {}
        all_states = self.hass.states.async_all()
        
        for domain in domains:
            result[domain] = [
                {
                    "entity_id": state.entity_id,
                    "state": state.state,
                    "attributes": state.attributes,
                }
                for state in all_states
                if state.entity_id.split(".")[0] == domain
            ]
        return result
    
    async def get_related_entities(self, entity_ids: List[str]) -> Dict[str, Any]:
        """Get entities related to the given entities (e.g., devices, areas)."""
        # Get device registry to find related entities
        result = {
            "entities": {},
            "devices": {},
            "areas": {}
        }
        
        # Build entity lookup
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            if state:
                result["entities"][entity_id] = {
                    "entity_id": entity_id,
                    "state": state.state,
                    "attributes": state.attributes,
                }
        
        return result


class PerformanceMonitor:
    """Track and report performance metrics."""
    
    def __init__(self):
        self._metrics: Dict[str, List[float]] = {}
        self._start_times: Dict[str, float] = {}
    
    def start_timer(self, operation: str) -> None:
        """Start timing an operation."""
        self._start_times[operation] = time.time()
    
    def end_timer(self, operation: str) -> float:
        """End timing an operation and record the duration."""
        if operation in self._start_times:
            duration = time.time() - self._start_times[operation]
            del self._start_times[operation]
            
            if operation not in self._metrics:
                self._metrics[operation] = []
            self._metrics[operation].append(duration)
            
            # Keep only last 100 measurements
            if len(self._metrics[operation]) > 100:
                self._metrics[operation] = self._metrics[operation][-100:]
            
            return duration
        return 0.0
    
    def get_metrics(self, operation: str) -> Dict[str, float]:
        """Get metrics for an operation."""
        if operation not in self._metrics:
            return {"count": 0, "avg": 0.0, "min": 0.0, "max": 0.0, "total": 0.0}
        
        values = self._metrics[operation]
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "total": sum(values)
        }
    
    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get all metrics."""
        return {op: self.get_metrics(op) for op in self._metrics}
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()
        self._start_times.clear()


def get_data_cache(enabled: bool = True) -> DataCache:
    """Get or create DataCache singleton."""
    global _data_cache
    if _data_cache is None:
        _data_cache = DataCache(enabled=enabled)
    return _data_cache


def get_parallel_executor(max_concurrent: int = 5) -> ParallelExecutor:
    """Get or create ParallelExecutor singleton."""
    global _parallel_executor
    if _parallel_executor is None:
        _parallel_executor = ParallelExecutor(max_concurrent=max_concurrent)
    return _parallel_executor


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create PerformanceMonitor singleton."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor
