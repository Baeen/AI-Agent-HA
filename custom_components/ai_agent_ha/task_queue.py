"""Async task queue for long-running operations in AI Agent HA integration.

This module provides background task management with status polling,
cancellation support, and progress tracking.
"""

import asyncio
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Coroutine
from uuid import uuid4

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a queued task."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TaskPriority(Enum):
    """Priority levels for queued tasks."""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class TaskProgress:
    """Progress information for a task."""

    current: int = 0
    total: Optional[int] = None
    percentage: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current": self.current,
            "total": self.total,
            "percentage": self.percentage,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class TaskResult:
    """Result of a task execution."""

    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    traceback_str: Optional[str] = None
    execution_time_ms: float = 0
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "traceback": self.traceback_str,
            "execution_time_ms": self.execution_time_ms,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class QueuedTask:
    """A task in the queue."""

    task_id: str
    name: str
    callback: Callable
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    progress: TaskProgress = field(default_factory=TaskProgress)
    created_at: datetime = field(default_factory=dt_util.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout_seconds: int = 300  # 5 minutes default
    result: Optional[TaskResult] = None
    cancellation_event: Optional[asyncio.Event] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without callback)."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "priority": self.priority.value,
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "timeout_seconds": self.timeout_seconds,
            "result": self.result.to_dict() if self.result else None,
        }


class AsyncTaskQueue:
    """Async task queue for managing long-running operations."""

    def __init__(self, hass: HomeAssistant, max_concurrent_tasks: int = 3):
        """Initialize the task queue.

        Args:
            hass: Home Assistant instance.
            max_concurrent_tasks: Maximum number of tasks to run concurrently.
        """
        self.hass = hass
        self._max_concurrent = max_concurrent_tasks
        self._tasks: Dict[str, QueuedTask] = {}
        self._task_queue: List[QueuedTask] = []
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._processing_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the task queue processor."""
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_queue())
            _LOGGER.info("Task queue started")

    async def stop(self):
        """Stop the task queue processor."""
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        self._processing_task = None
        _LOGGER.info("Task queue stopped")

    async def add_task(
        self,
        name: str,
        callback: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_seconds: int = 300,
    ) -> str:
        """Add a task to the queue.

        Args:
            name: Human-readable task name.
            callback: Async callable to execute.
            args: Positional arguments for the callback.
            kwargs: Keyword arguments for the callback.
            priority: Task priority.
            timeout_seconds: Task timeout in seconds.

        Returns:
            Task ID.
        """
        task_id = str(uuid4())[:8]
        task = QueuedTask(
            task_id=task_id,
            name=name,
            callback=callback,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            timeout_seconds=timeout_seconds,
            cancellation_event=asyncio.Event(),
        )

        self._tasks[task_id] = task
        self._task_queue.append(task)

        # Sort queue by priority (higher priority first)
        self._task_queue.sort(key=lambda t: t.priority.value, reverse=True)

        _LOGGER.info("Added task '%s' (%s) with priority %s", task_id, name, priority.name)

        # Start queue processor if not running
        await self.start()

        return task_id

    async def _process_queue(self):
        """Main queue processing loop."""
        try:
            while True:
                # Check for cancelled tasks
                self._task_queue = [
                    t for t in self._task_queue
                    if t.status != TaskStatus.CANCELLED
                ]

                if not self._task_queue and not self._running_tasks:
                    break

                # Process queued tasks
                while self._task_queue and len(self._running_tasks) < self._max_concurrent:
                    task = self._task_queue.pop(0)

                    if task.status == TaskStatus.CANCELLED:
                        continue

                    task.status = TaskStatus.QUEUED
                    await self._execute_task(task)

                # Wait for a running task to complete
                if self._running_tasks:
                    done, pending = await asyncio.wait(
                        self._running_tasks.values(),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in done:
                        task_id = task.get_kwargs().get("task_id") if hasattr(task, "get_kwargs") else None
                        # Clean up completed tasks
                        self._running_tasks = {
                            k: v for k, v in self._running_tasks.items()
                            if not v.done()
                        }
                else:
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            _LOGGER.debug("Queue processor cancelled")
        except Exception as e:
            _LOGGER.error("Queue processor error: %s", e)

    async def _execute_task(self, task: QueuedTask):
        """Execute a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = dt_util.now()

        _LOGGER.info("Executing task '%s': %s", task.task_id, task.name)

        # Create async wrapper
        async def task_wrapper():
            async with self._semaphore:
                start_time = dt_util.now()
                try:
                    # Check for cancellation
                    if task.cancellation_event and task.cancellation_event.is_set():
                        task.status = TaskStatus.CANCELLED
                        return

                    # Execute with timeout
                    try:
                        result = await asyncio.wait_for(
                            task.callback(*task.args, **task.kwargs),
                            timeout=task.timeout_seconds,
                        )
                        task.result = TaskResult(
                            task_id=task.task_id,
                            success=True,
                            result=result,
                            completed_at=dt_util.now(),
                        )
                        task.result.execution_time_ms = (
                            (task.result.completed_at - start_time).total_seconds() * 1000
                        )
                        task.status = TaskStatus.COMPLETED

                    except asyncio.TimeoutError:
                        task.result = TaskResult(
                            task_id=task.task_id,
                            success=False,
                            error="Task timed out",
                            completed_at=dt_util.now(),
                        )
                        task.status = TaskStatus.TIMED_OUT

                except Exception as e:
                    task.result = TaskResult(
                        task_id=task.task_id,
                        success=False,
                        error=str(e),
                        traceback_str=traceback.format_exc(),
                        completed_at=dt_util.now(),
                    )
                    task.result.execution_time_ms = (
                        (task.result.completed_at - start_time).total_seconds() * 1000
                    )
                    task.status = TaskStatus.FAILED
                    _LOGGER.error("Task '%s' failed: %s", task.task_id, e)

                finally:
                    task.completed_at = dt_util.now()
                    task.progress.percentage = 100.0

        # Create and track the async task
        async_task = asyncio.create_task(task_wrapper())
        self._running_tasks[task.task_id] = async_task

    async def get_task(self, task_id: str) -> Optional[QueuedTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a completed task."""
        task = self._tasks.get(task_id)
        if task and task.result:
            return task.result
        return None

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a task."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "name": task.name,
            "status": task.status.value,
            "progress": task.progress.to_dict(),
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "result": task.result.to_dict() if task.result else None,
        }

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or queued task.

        Args:
            task_id: The task ID to cancel.

        Returns:
            True if cancelled, False otherwise.
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            _LOGGER.warning("Task '%s' cannot be cancelled in state %s", task_id, task.status.value)
            return False

        if task.cancellation_event:
            task.cancellation_event.set()

        if task_id in self._running_tasks:
            # Cancel the async task
            async_task = self._running_tasks[task_id]
            async_task.cancel()
            del self._running_tasks[task_id]

        task.status = TaskStatus.CANCELLED
        task.completed_at = dt_util.now()

        _LOGGER.info("Task '%s' cancelled", task_id)
        return True

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List tasks with optional status filter.

        Args:
            status: Filter by status.
            limit: Maximum number of tasks to return.

        Returns:
            List of task status dictionaries.
        """
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        # Sort by created_at descending
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return [t.to_dict() for t in tasks[:limit]]

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the task queue."""
        stats = {
            "total": len(self._tasks),
            "by_status": {},
            "queued": len(self._task_queue),
            "running": len(self._running_tasks),
            "max_concurrent": self._max_concurrent,
        }

        for task in self._tasks.values():
            status_key = task.status.value
            stats["by_status"][status_key] = stats["by_status"].get(status_key, 0) + 1

        return stats

    async def clear_completed_tasks(self, older_than_hours: int = 24) -> int:
        """Clear completed tasks older than specified hours.

        Args:
            older_than_hours: Clear tasks older than this many hours.

        Returns:
            Number of tasks cleared.
        """
        cutoff = dt_util.now() - timedelta(hours=older_than_hours)
        to_remove = []

        for task_id, task in self._tasks.items():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                if task.completed_at and task.completed_at < cutoff:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._tasks[task_id]

        _LOGGER.info("Cleared %d completed tasks", len(to_remove))
        return len(to_remove)

    async def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[TaskResult]:
        """Wait for a task to complete.

        Args:
            task_id: The task ID to wait for.
            timeout: Maximum time to wait in seconds.

        Returns:
            TaskResult or None if timeout/exceeded.
        """
        start_time = dt_util.now()

        while True:
            task = self._tasks.get(task_id)
            if not task:
                return None

            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return task.result

            if timeout:
                elapsed = (dt_util.now() - start_time).total_seconds()
                if elapsed > timeout:
                    return None

            await asyncio.sleep(0.5)
