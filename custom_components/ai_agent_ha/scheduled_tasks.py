"""Scheduled tasks and reminders system for AI Agent HA integration.

This module provides natural language-based reminder and scheduled task
creation that integrates with Home Assistant's calendar and timer entities.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Priority levels for scheduled tasks."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(Enum):
    """Status of a scheduled task."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ReminderType(Enum):
    """Types of reminders."""

    ONE_TIME = "one_time"  # Single occurrence
    DAILY = "daily"  # Repeat daily
    WEEKLY = "weekly"  # Repeat weekly
    MONTHLY = "monthly"  # Repeat monthly
    CUSTOM = "custom"  # Custom recurrence


@dataclass
class ScheduledTask:
    """Represents a scheduled task or reminder."""

    task_id: str
    title: str
    description: str
    scheduled_time: datetime
    reminder_type: ReminderType = ReminderType.ONE_TIME
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    calendar_entity: Optional[str] = None
    notification_entity: Optional[str] = None
    action_service: Optional[str] = None
    action_data: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "scheduled_time": self.scheduled_time.isoformat(),
            "reminder_type": self.reminder_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "calendar_entity": self.calendar_entity,
            "notification_entity": self.notification_entity,
            "action_service": self.action_service,
            "action_data": self.action_data,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        """Create from dictionary representation."""
        scheduled_time = data.get("scheduled_time")
        if isinstance(scheduled_time, str):
            scheduled_time = datetime.fromisoformat(scheduled_time)

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        completed_at = data.get("completed_at")
        if isinstance(completed_at, str) and completed_at:
            completed_at = datetime.fromisoformat(completed_at)

        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            scheduled_time=scheduled_time or datetime.now(),
            reminder_type=ReminderType(data.get("reminder_type", "one_time")),
            priority=TaskPriority(data.get("priority", "normal")),
            status=TaskStatus(data.get("status", "pending")),
            calendar_entity=data.get("calendar_entity"),
            notification_entity=data.get("notification_entity"),
            action_service=data.get("action_service"),
            action_data=data.get("action_data"),
            created_at=created_at or datetime.now(),
            completed_at=completed_at,
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskCreationResult:
    """Result of task creation operation."""

    success: bool
    task: Optional[ScheduledTask] = None
    message: str = ""
    clarification_questions: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "task": self.task.to_dict() if self.task else None,
            "message": self.message,
            "clarification_questions": self.clarification_questions,
            "suggestions": self.suggestions,
            "confidence": self.confidence,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = ["## Scheduled Task Creation"]
        lines.append("")

        if not self.success:
            lines.append("### ⚠️ Clarification Needed")
            lines.append("")
            for question in self.clarification_questions:
                lines.append(f"- {question}")
            lines.append("")
            if self.suggestions:
                lines.append("### Suggestions")
                lines.append("")
                for suggestion in self.suggestions:
                    lines.append(f"- {suggestion}")
                lines.append("")
            return "\n".join(lines)

        if self.task:
            lines.append(f"**Task:** {self.task.title}")
            lines.append(f"**Description:** {self.task.description}")
            lines.append(f"**Scheduled Time:** {self.task.scheduled_time.strftime('%Y-%m-%d %H:%M')}")
            lines.append(f"**Priority:** {self.task.priority.value}")
            lines.append(f"**Type:** {self.task.reminder_type.value}")
            lines.append(f"**Status:** {self.task.status.value}")
            lines.append("")

            if self.task.tags:
                lines.append(f"**Tags:** {', '.join(self.task.tags)}")
                lines.append("")

            if self.task.action_service:
                lines.append("### Action")
                lines.append(f"- Service: `{self.task.action_service}`")
                if self.task.action_data:
                    lines.append("- Data:")
                    for key, value in self.task.action_data.items():
                        lines.append(f"  - `{key}`: `{value}`")
                lines.append("")

            lines.append(f"```\nTask ID: {self.task.task_id}\n```")
            lines.append("")

        if self.suggestions:
            lines.append("### Suggestions")
            lines.append("")
            for suggestion in self.suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

        return "\n".join(lines)


class TimeExpressionParser:
    """Parse natural language time expressions."""

    # Time patterns
    TIME_PATTERNS = {
        "at_time": re.compile(
            r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.IGNORECASE
        ),
        "tomorrow": re.compile(
            r"tomorrow\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.IGNORECASE
        ),
        "today": re.compile(
            r"today\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.IGNORECASE
        ),
        "in_minutes": re.compile(
            r"in\s+(\d+)\s+(minute|min|minute\s+from\s+now|mins?)\b", re.IGNORECASE
        ),
        "in_hours": re.compile(
            r"in\s+(\d+)\s+(hour|hr|hours?|hrs?)\b", re.IGNORECASE
        ),
        "next_day": re.compile(
            r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?",
            re.IGNORECASE,
        ),
        "daily": re.compile(
            r"(daily|every\s+day|each\s+day)(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?",
            re.IGNORECASE,
        ),
        "weekly": re.compile(
            r"(weekly|every\s+week|each\s+week)(?:\s+(?:on\s+(\w+))?(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?)?",
            re.IGNORECASE,
        ),
        "sunrise_sunset": re.compile(
            r"(sunrise|sunset)(\s+(before|after)\s+(\d+)\s+minutes)?", re.IGNORECASE
        ),
    }

    def parse_time_expression(self, text: str, base_time: Optional[datetime] = None) -> Tuple[datetime, Optional[str]]:
        """Parse time expression from text.

        Args:
            text: The text containing time expression
            base_time: Base time for parsing (defaults to now)

        Returns:
            Tuple of (scheduled_time, reminder_type)
        """
        if base_time is None:
            base_time = dt_util.now()

        text_lower = text.lower()

        # Check patterns in priority order
        # In X minutes
        match = self.TIME_PATTERNS["in_minutes"].search(text_lower)
        if match:
            minutes = int(match.group(1))
            return base_time + timedelta(minutes=minutes), None

        # In X hours
        match = self.TIME_PATTERNS["in_hours"].search(text_lower)
        if match:
            hours = int(match.group(1))
            return base_time + timedelta(hours=hours), None

        # Today at X
        match = self.TIME_PATTERNS["today"].search(text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3)
            if am_pm and am_pm.lower() == "pm" and hour < 12:
                hour += 12
            elif am_pm and am_pm.lower() == "am" and hour == 12:
                hour = 0
            return base_time.replace(hour=hour, minute=minute, second=0, microsecond=0), None

        # Tomorrow at X
        match = self.TIME_PATTERNS["tomorrow"].search(text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3)
            if am_pm and am_pm.lower() == "pm" and hour < 12:
                hour += 12
            elif am_pm and am_pm.lower() == "am" and hour == 12:
                hour = 0
            tomorrow = base_time + timedelta(days=1)
            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0), None

        # Next day of week
        match = self.TIME_PATTERNS["next_day"].search(text_lower)
        if match:
            day_name = match.group(1)
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            target_day = day_map.get(day_name.lower())
            if target_day is not None:
                today = base_time.weekday()
                days_ahead = (target_day - today) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week if same day
                target_date = base_time + timedelta(days=days_ahead)
                if match.group(2):
                    hour = int(match.group(2))
                    minute = int(match.group(3)) if match.group(3) else 0
                    am_pm = match.group(4)
                    if am_pm and am_pm.lower() == "pm" and hour < 12:
                        hour += 12
                    elif am_pm and am_pm.lower() == "am" and hour == 12:
                        hour = 0
                    target_date = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return target_date, None

        # Daily
        match = self.TIME_PATTERNS["daily"].search(text_lower)
        if match:
            hour = int(match.group(2)) if match.group(2) else 9
            minute = int(match.group(3)) if match.group(3) else 0
            am_pm = match.group(4)
            if am_pm and am_pm.lower() == "pm" and hour < 12:
                hour += 12
            elif am_pm and am_pm.lower() == "am" and hour == 12:
                hour = 0
            today_today = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if today_today <= base_time:
                today_today += timedelta(days=1)
            return today_today, "daily"

        # Weekly
        match = self.TIME_PATTERNS["weekly"].search(text_lower)
        if match:
            day_name = match.group(2) if match.group(2) else "monday"
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            target_day = day_map.get(day_name.lower())
            if target_day is not None:
                today = base_time.weekday()
                days_ahead = (target_day - today) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = base_time + timedelta(days=days_ahead)
                if match.group(3):
                    hour = int(match.group(3))
                    minute = int(match.group(4)) if match.group(4) else 0
                    am_pm = match.group(5)
                    if am_pm and am_pm.lower() == "pm" and hour < 12:
                        hour += 12
                    elif am_pm and am_pm.lower() == "am" and hour == 12:
                        hour = 0
                    target_date = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return target_date, "weekly"

        # At specific time (default to today/tomorrow)
        match = self.TIME_PATTERNS["at_time"].search(text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3)
            if am_pm and am_pm.lower() == "pm" and hour < 12:
                hour += 12
            elif am_pm and am_pm.lower() == "am" and hour == 12:
                hour = 0
            target_time = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target_time <= base_time:
                target_time += timedelta(days=1)
            return target_time, None

        # Default: return tomorrow at 9 AM
        return base_time.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1), None

    def extract_priority(self, text: str) -> TaskPriority:
        """Extract priority from text."""
        text_lower = text.lower()
        if "urgent" in text_lower or "asap" in text_lower or "immediately" in text_lower:
            return TaskPriority.URGENT
        elif "high" in text_lower or "important" in text_lower or "priority" in text_lower:
            return TaskPriority.HIGH
        elif "low" in text_lower or "when you can" in text_lower:
            return TaskPriority.LOW
        return TaskPriority.NORMAL

    def extract_tags(self, text: str) -> List[str]:
        """Extract tags from text."""
        tags = []
        text_lower = text.lower()
        tag_patterns = {
            "health": r"\b(health|medical|medicine|doctor|appointment)\b",
            "work": r"\b(work|job|meeting|office|business)\b",
            "home": r"\b(home|house|chores|cleaning)\b",
            "personal": r"\b(personal|self|me)\b",
            "reminder": r"\b(reminder|remind|note)\b",
        }
        for tag, pattern in tag_patterns.items():
            if re.search(pattern, text_lower):
                tags.append(tag)
        return tags


class ScheduledTaskManager:
    """Manages scheduled tasks and reminders."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the task manager."""
        self.hass = hass
        self._tasks: Dict[str, ScheduledTask] = {}
        self._time_parser = TimeExpressionParser()
        self._task_store_key = "ai_agent_ha_scheduled_tasks"

    async def create_task_from_nl(
        self,
        natural_language: str,
        user_id: Optional[str] = None,
    ) -> TaskCreationResult:
        """Create a scheduled task from natural language.

        Args:
            natural_language: Natural language description of the task
            user_id: Optional user ID for task ownership

        Returns:
            TaskCreationResult with the created task or clarification questions
        """
        if not natural_language or not natural_language.strip():
            return TaskCreationResult(
                success=False,
                message="Please provide a description for the task or reminder.",
                clarification_questions=["What would you like to be reminded about?"],
            )

        # Parse time
        scheduled_time, reminder_type = self._time_parser.parse_time_expression(natural_language)

        # Extract priority
        priority = self._time_parser.extract_priority(natural_language)

        # Extract tags
        tags = self._time_parser.extract_tags(natural_language)

        # Parse title and description
        title, description = self._parse_task_description(natural_language)

        # Check if we have enough information
        if not title:
            return TaskCreationResult(
                success=False,
                message="Could not determine what the task is about.",
                clarification_questions=[
                    "What would you like to be reminded about?",
                    "When should I remind you?"
                ],
                suggestions=[
                    "Try: 'Remind me to take medicine at 8pm'",
                    "Try: 'Set a reminder for tomorrow at 9am'",
                    "Try: 'Remind me in 30 minutes to answer calls'"
                ],
                confidence=0.2,
            )

        # Create the task
        task = ScheduledTask(
            task_id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            scheduled_time=scheduled_time,
            reminder_type=ReminderType(reminder_type or "one_time"),
            priority=priority,
            tags=tags,
            metadata={"user_id": user_id} if user_id else {},
        )

        self._tasks[task.task_id] = task
        await self._persist_tasks()

        # Create calendar event if calendar entity available
        calendar_entity = await self._get_default_calendar_entity()
        if calendar_entity:
            await self._create_calendar_event(task, calendar_entity)

        # Set up notification
        task.notification_entity = await self._get_notification_entity()

        return TaskCreationResult(
            success=True,
            task=task,
            message=f"Reminder created: {title} at {scheduled_time.strftime('%Y-%m-%d %H:%M')}",
            suggestions=self._generate_suggestions(task),
            confidence=0.9,
        )

    def _parse_task_description(self, text: str) -> Tuple[str, str]:
        """Parse task title and description from text."""
        # Remove time expressions to get the task description
        description = text.strip()

        # Remove common time prefixes
        time_prefixes = [
            r"remind\s+me\s+(?:to\s+)?",
            r"set\s+a\s+reminder\s+(?:to\s+)?",
            r"create\s+a\s+reminder\s+(?:to\s+)?",
            r"set\s+reminder\s+(?:to\s+)?",
            r"i\s+need\s+to\s+",
            r"i\s+should\s+",
        ]

        title = description
        for prefix in time_prefixes:
            match = re.match(prefix, description, re.IGNORECASE)
            if match:
                description = description[match.end():].strip()
                # Capitalize first letter
                description = description[0].upper() + description[1:] if description else description
                break

        # Use first part as title (up to first period or comma)
        title_end = min(
            description.find(". "),
            description.find(", "),
            len(description)
        )
        if title_end > 0 and title_end < 50:
            title = description[:title_end]
        else:
            title = description[:50] if len(description) > 50 else description

        if not title:
            title = "Reminder"

        return title, description

    def _generate_suggestions(self, task: ScheduledTask) -> List[str]:
        """Generate suggestions based on task."""
        suggestions = []

        # Suggest related automations
        if "medicine" in task.description.lower() or "medicine" in task.title.lower():
            suggestions.append("Would you like me to create an automation that triggers this reminder automatically?")
        elif "take" in task.description.lower():
            suggestions.append("You can also create a recurring automation for this task.")

        # Suggest calendar integration
        if not task.calendar_entity:
            suggestions.append("Connect a calendar entity for automatic calendar event creation.")

        return suggestions

    async def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        tags: Optional[List[str]] = None,
    ) -> List[ScheduledTask]:
        """List tasks with optional filters."""
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]
        if priority:
            tasks = [t for t in tasks if t.priority == priority]
        if tags:
            tasks = [t for t in tasks if any(tag in t.tags for tag in tags)]

        # Sort by scheduled time
        return sorted(tasks, key=lambda t: t.scheduled_time)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self._tasks.get(task_id)
        if task and task.status in (TaskStatus.PENDING, TaskStatus.ACTIVE):
            task.status = TaskStatus.CANCELLED
            task.completed_at = dt_util.now()
            await self._persist_tasks()
            _LOGGER.info("Task cancelled: %s", task_id)
            return True
        return False

    async def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        task = self._tasks.get(task_id)
        if task and task.status in (TaskStatus.PENDING, TaskStatus.ACTIVE):
            task.status = TaskStatus.COMPLETED
            task.completed_at = dt_util.now()
            await self._persist_tasks()
            _LOGGER.info("Task completed: %s", task_id)
            return True
        return False

    async def clear_completed_tasks(self, older_than_days: int = 30) -> int:
        """Clear completed tasks older than specified days."""
        cutoff = dt_util.now() - timedelta(days=older_than_days)
        to_remove = [
            task_id for task_id, task in self._tasks.items()
            if task.status == TaskStatus.COMPLETED and task.completed_at and task.completed_at < cutoff
        ]
        for task_id in to_remove:
            del self._tasks[task_id]
        if to_remove:
            await self._persist_tasks()
        return len(to_remove)

    async def get_upcoming_tasks(self, hours_ahead: int = 24) -> List[ScheduledTask]:
        """Get tasks scheduled within the next N hours."""
        now = dt_util.now()
        cutoff = now + timedelta(hours=hours_ahead)
        return [
            task for task in self._tasks.values()
            if task.scheduled_time >= now and task.scheduled_time <= cutoff
            and task.status in (TaskStatus.PENDING, TaskStatus.ACTIVE)
        ]

    async def check_and_notify(self) -> List[ScheduledTask]:
        """Check for tasks that need notification and send notifications."""
        now = dt_util.now()
        notified = []

        for task_id, task in self._tasks.items():
            if task.status != TaskStatus.PENDING:
                continue

            # Check if task is due (within 1 minute)
            if abs((now - task.scheduled_time).total_seconds()) < 60:
                await self._send_notification(task)
                task.status = TaskStatus.ACTIVE
                notified.append(task)

        if notified:
            await self._persist_tasks()

        return notified

    async def _send_notification(self, task: ScheduledTask):
        """Send notification for a task."""
        notification_entity = task.notification_entity
        if not notification_entity:
            _LOGGER.warning("No notification entity configured for task: %s", task.task_id)
            return

        # Send notification via Home Assistant
        try:
            await self.hass.services.async_call(
                "notify",
                notification_entity,
                {
                    "title": f"Reminder: {task.title}",
                    "message": task.description,
                },
            )
            _LOGGER.info("Notification sent for task: %s", task.task_id)
        except Exception as e:
            _LOGGER.error("Failed to send notification for task %s: %s", task.task_id, e)

    async def _create_calendar_event(self, task: ScheduledTask, calendar_entity: str):
        """Create a calendar event for the task."""
        try:
            await self.hass.services.async_call(
                "calendar",
                "create_event",
                {
                    "entity_id": calendar_entity,
                    "summary": task.title,
                    "description": task.description,
                    "start_time": task.scheduled_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": (task.scheduled_time + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
        except Exception as e:
            _LOGGER.error("Failed to create calendar event: %s", e)

    async def _get_default_calendar_entity(self) -> Optional[str]:
        """Get the default calendar entity."""
        try:
            states = self.hass.states.async_all("calendar")
            if states:
                return states[0].entity_id
        except Exception as e:
            _LOGGER.error("Error getting calendar entities: %s", e)
        return None

    async def _get_notification_entity(self) -> Optional[str]:
        """Get the default notification entity."""
        try:
            states = self.hass.states.async_all("notify")
            if states:
                # Prefer mobile_app entities
                for state in states:
                    if "mobile_app" in state.entity_id:
                        return state.entity_id.split(".")[1] if "." in state.entity_id else "mobile_app"
                # Fall back to first notify entity
                if states:
                    return states[0].entity_id.split(".")[1] if "." in states[0].entity_id else "persistent_notifications"
        except Exception as e:
            _LOGGER.error("Error getting notification entities: %s", e)
        return "persistent_notifications"

    async def _persist_tasks(self):
        """Persist tasks to Home Assistant storage."""
        try:
            from homeassistant.helpers.storage import Store
            store = Store(self.hass, 1, f"{self.hass.config.config_dir}/ai_agent_ha_tasks.json")
            await store.async_save({
                "tasks": {task_id: task.to_dict() for task_id, task in self._tasks.items()},
                "version": 1,
            })
        except Exception as e:
            _LOGGER.error("Failed to persist tasks: %s", e)

    async def load_tasks(self):
        """Load tasks from Home Assistant storage."""
        try:
            from homeassistant.helpers.storage import Store
            store = Store(self.hass, 1, f"{self.hass.config.config_dir}/ai_agent_ha_tasks.json")
            data = await store.async_load()
            if data and "tasks" in data:
                for task_id, task_data in data["tasks"].items():
                    self._tasks[task_id] = ScheduledTask.from_dict(task_data)
                _LOGGER.info("Loaded %d tasks from storage", len(self._tasks))
        except Exception as e:
            _LOGGER.error("Failed to load tasks: %s", e)

    def get_statistics(self) -> Dict[str, Any]:
        """Get task statistics."""
        stats = {
            "total": len(self._tasks),
            "by_status": {},
            "by_priority": {},
            "by_type": {},
            "upcoming_24h": 0,
        }

        now = dt_util.now()
        cutoff = now + timedelta(hours=24)

        for task in self._tasks.values():
            status_key = task.status.value
            stats["by_status"][status_key] = stats["by_status"].get(status_key, 0) + 1

            priority_key = task.priority.value
            stats["by_priority"][priority_key] = stats["by_priority"].get(priority_key, 0) + 1

            type_key = task.reminder_type.value
            stats["by_type"][type_key] = stats["by_type"].get(type_key, 0) + 1

            if task.scheduled_time >= now and task.scheduled_time <= cutoff:
                stats["upcoming_24h"] += 1

        return stats
