"""Automation templates library for AI Agent HA integration.

This module provides a built-in library of common automation templates
that users can browse, search, and customize through natural language.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

_LOGGER = logging.getLogger(__name__)


@dataclass
class AutomationTemplate:
    """Represents an automation template."""

    template_id: str
    name: str
    description: str
    category: str
    tags: List[str] = field(default_factory=list)
    automation_config: Dict[str, Any] = field(default_factory=dict)
    yaml_output: str = ""
    prerequisites: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    difficulty: str = "beginner"  # beginner, intermediate, advanced
    estimated_impact: str = "medium"  # low, medium, high

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "automation_config": self.automation_config,
            "yaml_output": self.yaml_output,
            "prerequisites": self.prerequisites,
            "variables": self.variables,
            "difficulty": self.difficulty,
            "estimated_impact": self.estimated_impact,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutomationTemplate":
        """Create from dictionary."""
        return cls(
            template_id=data.get("template_id", str(uuid4())[:8]),
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            automation_config=data.get("automation_config", {}),
            yaml_output=data.get("yaml_output", ""),
            prerequisites=data.get("prerequisites", []),
            variables=data.get("variables", {}),
            difficulty=data.get("difficulty", "beginner"),
            estimated_impact=data.get("estimated_impact", "medium"),
        )


class AutomationTemplatesLibrary:
    """Library of automation templates."""

    def __init__(self):
        """Initialize the templates library."""
        self._templates: Dict[str, AutomationTemplate] = {}
        self._initialize_templates()

    def _initialize_templates(self):
        """Initialize the default templates."""
        # Lighting templates
        self._add_template(AutomationTemplate(
            template_id="auto_light_on_arrival",
            name="Auto Light on Arrival",
            description="Automatically turns on lights when you arrive home",
            category="lighting",
            tags=["lighting", "arrival", "welcome", "motion"],
            automation_config={
                "alias": "Auto Light on Arrival",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": "person.home",
                        "to": "home"
                    }
                ],
                "condition": [
                    {
                        "condition": "sun",
                        "after": "sunset",
                        "before": " sunrise"
                    },
                    {
                        "condition": "state",
                        "entity_id": "binary_sensor.morning_motion",
                        "state": "on"
                    }
                ],
                "action": [
                    {
                        "service": "light.turn_on",
                        "target": {
                            "area": "living_room"
                        },
                        "data": {
                            "brightness_pct": 70,
                            "color_temp": 370
                        }
                    }
                ],
                "mode": "single"
            },
            yaml_output="""alias: Auto Light on Arrival
trigger:
  - platform: state
    entity_id: person.home
    to: home
condition:
  - condition: sun
    after: sunset
    before: sunrise
  - condition: state
    entity_id: binary_sensor.morning_motion
    state: "on"
action:
  - service: light.turn_on
    target:
      area: living_room
    data:
      brightness_pct: 70
      color_temp: 370
mode: single""",
            prerequisites=["Person integration configured", "Lights in area"],
            difficulty="beginner",
            estimated_impact="high",
        ))

        self._add_template(AutomationTemplate(
            template_id="good_night_routine",
            name="Good Night Routine",
            description="Locks doors, turns off lights, and sets security mode",
            category="security",
            tags=["security", "night", "locks", "lights"],
            automation_config={
                "alias": "Good Night Routine",
                "trigger": [
                    {
                        "platform": "time",
                        "at": "22:00:00"
                    }
                ],
                "condition": [
                    {
                        "condition": "state",
                        "entity_id": "person.home",
                        "state": "home"
                    }
                ],
                "action": [
                    {
                        "service": "light.turn_off",
                        "target": {
                            "domain": "light",
                            "exclude": True
                        }
                    },
                    {
                        "service": "lock.lock",
                        "target": {
                            "entity_id": "all"
                        }
                    },
                    {
                        "service": "notify.mobile_app_phone",
                        "data": {
                            "title": "Good Night",
                            "message": "Doors locked and lights off"
                        }
                    }
                ],
                "mode": "single"
            },
            yaml_output="""alias: Good Night Routine
trigger:
  - platform: time
    at: "22:00:00"
condition:
  - condition: state
    entity_id: person.home
    state: home
action:
  - service: light.turn_off
    target:
      domain: light
      exclude: true
  - service: lock.lock
    target:
      entity_id: all
  - service: notify.mobile_app_phone
    data:
      title: Good Night
      message: Doors locked and lights off
mode: single""",
            prerequisites=["Smart locks", "Notification setup"],
            difficulty="intermediate",
            estimated_impact="high"
        ))

        # Climate templates
        self._add_template(AutomationTemplate(
            template_id="eco_mode_away",
            name="Eco Mode When Away",
            description="Adjusts thermostat when everyone leaves home",
            category="climate",
            tags=["climate", "eco", "energy", "away"],
            automation_config={
                "alias": "Eco Mode When Away",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": "person.*",
                        "from": "home",
                        "to": "not_home"
                    }
                ],
                "condition": [
                    {
                        "condition": "state",
                        "entity_id": "person.*",
                        "state": "not_home",
                        "for": {
                            "minutes": 5
                        }
                    }
                ],
                "action": [
                    {
                        "service": "climate.set_temperature",
                        "target": {
                            "entity_id": "climate.hvac"
                        },
                        "data": {
                            "temperature": 23,
                            "hvac_mode": "eco"
                        }
                    }
                ],
                "mode": "single"
            },
            yaml_output="""alias: Eco Mode When Away
trigger:
  - platform: state
    entity_id: person.*
    from: home
    to: not_home
condition:
  - condition: state
    entity_id: person.*
    state: not_home
    for:
      minutes: 5
action:
  - service: climate.set_temperature
    target:
      entity_id: climate.hvac
    data:
      temperature: 23
      hvac_mode: eco
mode: single""",
            prerequisites=["Climate integration", "Person tracking"],
            difficulty="beginner",
            estimated_impact="high"
        ))

        self._add_template(AutomationTemplate(
            template_id="morning_warmup",
            name="Morning Warmup",
            description="Pre-heats home before wake-up time",
            category="climate",
            tags=["climate", "morning", "comfort", "heating"],
            automation_config={
                "alias": "Morning Warmup",
                "trigger": [
                    {
                        "platform": "time",
                        "at": "06:00:00"
                    }
                ],
                "action": [
                    {
                        "service": "climate.set_temperature",
                        "target": {
                            "entity_id": "climate.hvac"
                        },
                        "data": {
                            "temperature": 21,
                            "hvac_mode": "heat"
                        }
                    },
                    {
                        "service": "notify.mobile_app_phone",
                        "data": {
                            "title": "Good Morning",
                            "message": "Home is warm and ready!"
                        }
                    }
                ],
                "mode": "single"
            },
            yaml_output="""alias: Morning Warmup
trigger:
  - platform: time
    at: "06:00:00"
action:
  - service: climate.set_temperature
    target:
      entity_id: climate.hvac
    data:
      temperature: 21
      hvac_mode: heat
  - service: notify.mobile_app_phone
    data:
      title: Good Morning
      message: Home is warm and ready!
mode: single""",
            prerequisites=["Climate integration", "Notification setup"],
            difficulty="beginner",
            estimated_impact="medium"
        ))

        # Security templates
        self._add_template(AutomationTemplate(
            template_id="security_away_mode",
            name="Security Away Mode",
            description="Activates security system when everyone leaves",
            category="security",
            tags=["security", "away", "alarm", "cameras"],
            automation_config={
                "alias": "Security Away Mode",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": "person.*",
                        "from": "home",
                        "to": "not_home"
                    }
                ],
                "condition": [
                    {
                        "condition": "state",
                        "entity_id": "input_boolean.security_enabled",
                        "state": "on"
                    }
                ],
                "action": [
                    {
                        "service": "camera.snapshot",
                        "target": {
                            "entity_id": "camera.front_door"
                        },
                        "data": {
                            "filename": "/tmp/front_door_away.jpg"
                        }
                    },
                    {
                        "service": "notify.all",
                        "data": {
                            "title": "Security Activated",
                            "message": "Away mode is now active"
                        }
                    }
                ],
                "mode": "single"
            },
            yaml_output="""alias: Security Away Mode
trigger:
  - platform: state
    entity_id: person.*
    from: home
    to: not_home
condition:
  - condition: state
    entity_id: input_boolean.security_enabled
    state: "on"
action:
  - service: camera.snapshot
    target:
      entity_id: camera.front_door
    data:
      filename: /tmp/front_door_away.jpg
  - service: notify.all
    data:
      title: Security Activated
      message: Away mode is now active
mode: single""",
            prerequisites=["Security system", "Cameras", "Input boolean"],
            difficulty="intermediate",
            estimated_impact="high"
        ))

        # Media templates
        self._add_template(AutomationTemplate(
            template_id="movie_mode",
            name="Movie Mode",
            description="Creates movie atmosphere with lights and blinds",
            category="media",
            tags=["media", "movie", "entertainment", "ambiance"],
            automation_config={
                "alias": "Movie Mode",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": "media_player.living_room_tv",
                        "to": "playing"
                    }
                ],
                "action": [
                    {
                        "service": "light.turn_on",
                        "target": {
                            "area": "living_room"
                        },
                        "data": {
                            "brightness": 50,
                            "rgb_color": [255, 200, 100]
                        }
                    },
                    {
                        "service": "cover.close_cover",
                        "target": {
                            "area": "living_room"
                        }
                    }
                ],
                "mode": "restart"
            },
            yaml_output="""alias: Movie Mode
trigger:
  - platform: state
    entity_id: media_player.living_room_tv
    to: playing
action:
  - service: light.turn_on
    target:
      area: living_room
    data:
      brightness: 50
      rgb_color:
        - 255
        - 200
        - 100
  - service: cover.close_cover
    target:
      area: living_room
mode: restart""",
            prerequisites=["Smart lights", "Smart blinds", "Media player"],
            difficulty="beginner",
            estimated_impact="medium"
        ))

        # Notification templates
        self._add_template(AutomationTemplate(
            template_id="leaving_reminder",
            name="Leaving Reminder",
            description="Reminds you to lock doors and take keys when leaving",
            category="notifications",
            tags=["notification", "reminder", "morning", "evening"],
            automation_config={
                "alias": "Leaving Reminder",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": "zone.home",
                        "to": "not_home"
                    }
                ],
                "condition": [
                    {
                        "condition": "time",
                        "after": "06:00:00",
                        "before": "23:00:00"
                    }
                ],
                "action": [
                    {
                        "service": "notify.mobile_app_phone",
                        "data": {
                            "title": "Leaving Home?",
                            "message": "Don't forget to lock doors and take your keys!",
                            "data": {
                                "actions": [
                                    {
                                        "action": "DISMISS",
                                        "title": "Dismissed"
                                    }
                                ]
                            }
                        }
                    }
                ],
                "mode": "single"
            },
            yaml_output="""alias: Leaving Reminder
trigger:
  - platform: state
    entity_id: zone.home
    to: not_home
condition:
  - condition: time
    after: "06:00:00"
    before: "23:00:00"
action:
  - service: notify.mobile_app_phone
    data:
      title: Leaving Home?
      message: Don't forget to lock doors and take your keys!
      data:
        actions:
          - action: DISMISS
            title: Dismissed
mode: single""",
            prerequisites=["Mobile notifications", "Zone tracking"],
            difficulty="beginner",
            estimated_impact="medium"
        ))

        # Maintenance templates
        self._add_template(AutomationTemplate(
            template_id="filter_reminder",
            name="Filter Replacement Reminder",
            description="Reminds to replace HVAC filter every 3 months",
            category="maintenance",
            tags=["maintenance", "reminder", "hvac", "filter"],
            automation_config={
                "alias": "Filter Replacement Reminder",
                "trigger": [
                    {
                        "platform": "time",
                        "at": "09:00:00",
                        "days": [1, 8, 15, 22]
                    }
                ],
                "condition": [
                    {
                        "condition": "time",
                        "days": [1, 7]
                    }
                ],
                "action": [
                    {
                        "service": "notify.mobile_app_phone",
                        "data": {
                            "title": "Filter Replacement Due",
                            "message": "Time to replace your HVAC filter"
                        }
                    }
                ],
                "mode": "single"
            },
            yaml_output="""alias: Filter Replacement Reminder
trigger:
  - platform: time
    at: "09:00:00"
    days:
      - Mon
      - Thu
      - Mon
      - Thu
condition:
  - condition: time
    days:
      - Monday
      - Sunday
action:
  - service: notify.mobile_app_phone
    data:
      title: Filter Replacement Due
      message: Time to replace your HVAC filter
mode: single""",
            prerequisites=["Notification setup"],
            difficulty="beginner",
            estimated_impact="low"
        ))

    def _add_template(self, template: AutomationTemplate):
        """Add a template to the library."""
        self._templates[template.template_id] = template

    def get_template(self, template_id: str) -> Optional[AutomationTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def list_templates(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
    ) -> List[AutomationTemplate]:
        """List templates with optional filters.

        Args:
            category: Filter by category.
            tags: Filter by tags.
            difficulty: Filter by difficulty level.

        Returns:
            List of matching templates.
        """
        templates = list(self._templates.values())

        if category:
            templates = [t for t in templates if t.category == category]

        if tags:
            templates = [
                t for t in templates
                if any(tag in t.tags for tag in tags)
            ]

        if difficulty:
            templates = [t for t in templates if t.difficulty == difficulty]

        return templates

    def search_templates(self, query: str) -> List[AutomationTemplate]:
        """Search templates by keyword.

        Args:
            query: Search query string.

        Returns:
            List of matching templates.
        """
        query_lower = query.lower()
        results = []

        for template in self._templates.values():
            # Search in name, description, tags, and category
            if (
                query_lower in template.name.lower()
                or query_lower in template.description.lower()
                or any(query_lower in tag.lower() for tag in template.tags)
                or query_lower in template.category.lower()
            ):
                results.append(template)

        return results

    def get_suggested_templates(self, num: int = 5) -> List[AutomationTemplate]:
        """Get suggested templates for new users.

        Args:
            num: Number of suggestions.

        Returns:
            List of suggested templates.
        """
        # Prioritize beginner templates with high impact
        candidates = [
            t for t in self._templates.values()
            if t.difficulty == "beginner" and t.estimated_impact == "high"
        ]

        return candidates[:num]

    def get_categories(self) -> List[str]:
        """Get list of all categories."""
        return list(set(t.category for t in self._templates.values()))

    def get_statistics(self) -> Dict[str, Any]:
        """Get library statistics."""
        stats = {
            "total": len(self._templates),
            "by_category": {},
            "by_difficulty": {},
        }

        for template in self._templates.values():
            cat = template.category
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

            diff = template.difficulty
            stats["by_difficulty"][diff] = stats["by_difficulty"].get(diff, 0) + 1

        return stats

    def generate_yaml_from_template(
        self,
        template_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate YAML from template with variable substitution.

        Args:
            template_id: The template ID.
            variables: Variables to substitute.

        Returns:
            YAML string or None.
        """
        template = self._templates.get(template_id)
        if not template:
            return None

        yaml_output = template.yaml_output

        if variables:
            for key, value in variables.items():
                yaml_output = yaml_output.replace(f"{{{key}}}", str(value))

        return yaml_output
