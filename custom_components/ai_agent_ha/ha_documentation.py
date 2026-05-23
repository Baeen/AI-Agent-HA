"""Home Assistant documentation provider for AI Agent HA.

This module provides the AI with access to Home Assistant documentation,
including service schemas, automation triggers, conditions, actions,
and best practices.
"""

import logging
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# Embedded Home Assistant documentation for AI reference
# This includes commonly used services, triggers, conditions, and actions
HA_DOCUMENTATION = {
    "version_info": {
        "description": "Home Assistant 2024+ documentation",
        "note": "Always use the latest Home Assistant syntax and patterns",
    },
    "automation_structure": {
        "description": "Standard Home Assistant automation structure",
        "example": {
            "id": "auto_id",
            "alias": "Automation Name",
            "description": "Description of what this automation does",
            "trigger": [...],
            "condition": [...],
            "action": [...],
            "mode": "single|restart|queued|parallel",
        },
    },
    "triggers": {
        "time": {
            "description": "Trigger at a specific time",
            "schema": {
                "platform": "time",
                "at": "sensor.time" or "23:59:59",
            },
        },
        "time_pattern": {
            "description": "Trigger at a pattern interval",
            "schema": {
                "platform": "time_pattern",
                "minutes": "/5",  # Every 5 minutes
            },
        },
        "state": {
            "description": "Trigger when entity state changes",
            "schema": {
                "platform": "state",
                "entity_id": "sensor.temperature",
                "to": "25",  # Optional: specific state
                "from": "20",  # Optional: from state
                "for": {"seconds": 60},  # Optional: duration
            },
        },
        "numeric_state": {
            "description": "Trigger when numeric entity value changes",
            "schema": {
                "platform": "numeric_state",
                "entity_id": "sensor.temperature",
                "above": 20,
                "below": 30,
                "for": {"seconds": 60},
            },
        },
        "device": {
            "description": "Trigger based on device automation",
            "schema": {
                "platform": "device",
                "domain": "light",
                "device_id": "device_id_here",
                "type": "turned_on",
                "entity_id": "light.name",
            },
        },
        "zone": {
            "description": "Trigger when entering or leaving a zone",
            "schema": {
                "platform": "zone",
                "entity_id": "device_tracker.phone",
                "zone": "zone.home",
                "event": "enter" or "leave",
            },
        },
        "homeassistant": {
            "description": "Trigger on Home Assistant events",
            "schema": {
                "platform": "homeassistant",
                "event": "start" or "stop",
            },
        },
        "webhook": {
            "description": "Trigger on webhook call",
            "schema": {
                "platform": "webhook",
                "webhook_id": "your_webhook_id",
            },
        },
    },
    "conditions": {
        "state": {
            "description": "Check entity state",
            "schema": {
                "condition": "state",
                "entity_id": "light.tv_backlight",
                "state": "off",
            },
        },
        "numeric_state": {
            "description": "Check numeric value",
            "schema": {
                "condition": "numeric_state",
                "entity_id": "sensor.battery",
                "above": 20,
            },
        },
        "time": {
            "description": "Check time",
            "schema": {
                "condition": "time",
                "after": "08:00:00",
                "before": "22:00:00",
                "weekday": [1, 2, 3, 4, 5],  # Monday to Friday
            },
        },
        "device": {
            "description": "Check device state",
            "schema": {
                "condition": "device",
                "device_id": "device_id_here",
                "domain": "binary_sensor",
                "type": "is_off",
                "entity_id": "binary_sensor.motion",
            },
        },
        "template": {
            "description": "Check with Jinja2 template",
            "schema": {
                "condition": "template",
                "value_template": "{{ states('sensor.temperature') > 20 }}",
            },
        },
        "and": {
            "description": "Combine multiple conditions",
            "schema": {
                "condition": "and",
                "conditions": [...],
            },
        },
        "or": {
            "description": "Alternative to and",
            "schema": {
                "condition": "or",
                "conditions": [...],
            },
        },
    },
    "actions": {
        "call_service": {
            "description": "Call a Home Assistant service",
            "schema": {
                "service": "light.turn_on",
                "target": {
                    "entity_id": "light.living_room",
                },
                "data": {
                    "brightness": 200,
                    "color_temp": 370,
                },
            },
            "alternative_schema": {
                "service": "light.turn_on",
                "entity_id": "light.living_room",
                "brightness": 200,
            },
        },
        "delay": {
            "description": "Delay execution",
            "schema": {
                "delay": {"seconds": 5},
            },
        },
        "wait_for_trigger": {
            "description": "Wait for a trigger",
            "schema": {
                "wait_for_trigger": [
                    {
                        "platform": "state",
                        "entity_id": "binary_sensor.motion",
                        "to": "on",
                    }
                ],
                "timeout": {"seconds": 30},
            },
        },
        "repeat": {
            "description": "Repeat actions",
            "schema": {
                "repeat": {
                    "count": 5,
                    "sequence": [
                        {
                            "service": "light.turn_on",
                            "entity_id": "light.to_repeat",
                        }
                    ],
                },
            },
        },
        "choose": {
            "description": "Choose between action sequences",
            "schema": {
                "choose": [
                    {
                        "conditions": {"condition": "state", "entity_id": "climate.thermostat", "state": "heat"},
                        "sequence": [{"service": "light.turn_on", "entity_id": "light.red"}],
                    },
                    {
                        "conditions": {"condition": "state", "entity_id": "climate.thermostat", "state": "cool"},
                        "sequence": [{"service": "light.turn_on", "entity_id": "light.blue"}],
                    },
                ],
                "default": [{"service": "light.turn_on", "entity_id": "light.white"}],
            },
        },
        "event": {
            "description": "Fire an event",
            "schema": {
                "event": "ai_agent_ha_automation_created",
                "event_data": {"automation_id": "auto_123"},
            },
        },
        "set_variable": {
            "description": "Set an input variable (requires variables trigger)",
            "schema": {
                "variables": {"temperature": "{{ states('sensor.temperature') }}"},
            },
        },
    },
    "common_services": {
        "light": {
            "turn_on": ["entity_id", "brightness", "color_temp", "rgb_color", "transition"],
            "turn_off": ["entity_id", "transition"],
        },
        "switch": {
            "turn_on": ["entity_id"],
            "turn_off": ["entity_id"],
        },
        "climate": {
            "turn_on": ["entity_id"],
            "turn_off": ["entity_id"],
            "set_temperature": ["entity_id", "temperature", "target_temp_high", "target_temp_low"],
            "set_hvac_mode": ["entity_id", "hvac_mode"],
        },
        "cover": {
            "open_cover": ["entity_id"],
            "close_cover": ["entity_id"],
            "set_cover_position": ["entity_id", "position"],
        },
        "media_player": {
            "turn_on": ["entity_id"],
            "turn_off": ["entity_id"],
            "media_play_pause": ["entity_id"],
            "volume_set": ["entity_id", "volume_level"],
        },
        "homeassistant": {
            "turn_off": ["entity_id"],
            "turn_on": ["entity_id"],
            "stop": [],
            "restart": [],
        },
        "input_boolean": {
            "turn_on": ["entity_id"],
            "turn_off": ["entity_id"],
            "toggle": ["entity_id"],
        },
        "input_number": {
            "set_value": ["entity_id", "value"],
        },
        "automation": {
            "turn_on": ["entity_id"],
            "turn_off": ["entity_id"],
            "toggle": ["entity_id"],
            "trigger": ["entity_id", "skip_condition"],
        },
        "scene": {
            "turn_on": ["entity_id"],
        },
        "logger": {
            "set_level": {"domain": "string", "default": "info"},
        },
    },
    "best_practices": {
        "automation": [
            "Always include an 'alias' for easy identification",
            "Use descriptive 'description' to explain purpose",
            "Choose appropriate 'mode': 'single' for most cases, 'restart' for state changes, 'queued' for frequent triggers",
            "Use 'condition' to prevent unwanted executions",
            "Add 'for' duration to state triggers to avoid flapping",
            "Use 'target' instead of 'entity_id' in service calls for multiple entities",
            "Consider using device automations for simpler setups",
        ],
        "security": [
            "Never expose API keys or tokens in automations",
            "Use input helpers for user-configurable values",
            "Restrict automation creation to trusted sources",
            "Review automations with dangerous services (restart, purge, etc.)",
            "Avoid infinite loops (state trigger -> same entity action)",
        ],
        "performance": [
            "Use 'time_pattern' triggers sparingly",
            "Avoid polling sensors too frequently",
            "Use 'debounce' or 'for' to prevent rapid executions",
            "Consider using template sensors instead of complex templates in automations",
        ],
    },
    "dashboard_structure": {
        "description": "Standard Home Assistant dashboard/YAML structure",
        "example": {
            "title": "Dashboard Name",
            "url_path": "dashboard-name",
            "icon": "mdi:home",
            "show_in_sidebar": True,
            "require_admin": False,
            "views": [
                {
                    "title": "View Name",
                    "type": "default|panel|brick",
                    "icon": "mdi:room",
                    "path": "view-url-path",  # For nested views
                    "cards": [...],
                }
            ],
        },
    },
    "card_types": {
        "entities": {
            "description": "Show entities with their states",
            "example": {
                "type": "entities",
                "title": "Living Room",
                "entities": ["light.living_room", "switch.fan"],
            },
        },
        "glance": {
            "description": "Compact entity display",
            "example": {
                "type": "glance",
                "title": "Sensors",
                "entities": ["sensor.temperature", "sensor.humidity"],
            },
        },
        "thermostat": {
            "description": "Climate control card",
            "example": {"type": "thermostat", "entity": "climate.thermostat"},
        },
        "picture-entity": {
            "description": "Entity with background image",
            "example": {
                "type": "picture-entity",
                "entity": "camera.front_door",
                "image": "/local/camera_preview.jpg",
            },
        },
        "gauge": {
            "description": "Gauge display for numeric values",
            "example": {
                "type": "gauge",
                "entity": "sensor.power_consumption",
                "name": "Power",
                "min": 0,
                "max": 1000,
            },
        },
        "history-graph": {
            "description": "Graph of entity history",
            "example": {
                "type": "history-graph",
                "entities": ["sensor.temperature"],
                "hours_to_show": 24,
            },
        },
        "button": {
            "description": "Button to trigger actions",
            "example": {
                "type": "button",
                "name": "Reset",
                "tap_action": {"action": "call-service", "service": "script.reset"},
            },
        },
    },
}


class HADocumentationProvider:
    """Provides Home Assistant documentation to the AI."""

    def __init__(self):
        """Initialize the documentation provider."""
        self._documentation_cache = None

    def get_full_documentation(self) -> str:
        """Get the full documentation as a formatted string."""
        lines = [
            "# Home Assistant AI Reference Documentation",
            "",
            f"## Version: {HA_DOCUMENTATION['version_info']['description']}",
            "",
            f"Note: {HA_DOCUMENTATION['version_info']['note']}",
            "",
            "## Automation Structure",
            "",
            "```yaml",
            yaml.dump(HA_DOCUMENTATION["automation_structure"]["example"]),
            "```",
            "",
        ]

        # Triggers
        lines.append("## Available Triggers")
        lines.append("")
        for trigger_name, trigger_info in HA_DOCUMENTATION["triggers"].items():
            lines.append(f"### {trigger_name}")
            lines.append(f"{trigger_info['description']}")
            lines.append("")
            lines.append("```yaml")
            lines.append(yaml.dump(trigger_info["schema"]))
            lines.append("```")
            lines.append("")

        # Conditions
        lines.append("## Available Conditions")
        lines.append("")
        for cond_name, cond_info in HA_DOCUMENTATION["conditions"].items():
            lines.append(f"### {cond_name}")
            lines.append(f"{cond_info['description']}")
            lines.append("")
            lines.append("```yaml")
            lines.append(yaml.dump(cond_info["schema"]))
            lines.append("```")
            lines.append("")

        # Actions
        lines.append("## Available Actions")
        lines.append("")
        for action_name, action_info in HA_DOCUMENTATION["actions"].items():
            lines.append(f"### {action_name}")
            lines.append(f"{action_info['description']}")
            lines.append("")
            lines.append("```yaml")
            lines.append(yaml.dump(action_info["schema"]))
            lines.append("```")
            lines.append("")

        # Common Services
        lines.append("## Common Services")
        lines.append("")
        for domain, services in HA_DOCUMENTATION["common_services"].items():
            lines.append(f"### {domain}")
            lines.append("")
            for service, params in services.items():
                if isinstance(params, list):
                    lines.append(f"- `{service}`: {params}")
                else:
                    lines.append(f"- `{service}`: {params}")
            lines.append("")

        # Best Practices
        lines.append("## Best Practices")
        lines.append("")
        for category, practices in HA_DOCUMENTATION["best_practices"].items():
            lines.append(f"### {category.capitalize()}")
            lines.append("")
            for practice in practices:
                lines.append(f"- {practice}")
            lines.append("")

        # Card Types
        lines.append("## Dashboard Card Types")
        lines.append("")
        for card_type, card_info in HA_DOCUMENTATION["card_types"].items():
            lines.append(f"### {card_type}")
            lines.append(f"{card_info['description']}")
            lines.append("")
            lines.append("```yaml")
            lines.append(yaml.dump(card_info["example"]))
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    def get_section(self, section: str) -> str:
        """Get a specific section of the documentation."""
        if section not in HA_DOCUMENTATION:
            return f"Documentation section '{section}' not found."

        import yaml

        return yaml.dump(HA_DOCUMENTATION[section], default_flow_style=False)

    def get_prompt_for_automation_review(self) -> str:
        """Get a prompt for the AI to review automation YAML."""
        return f"""You are a Home Assistant automation expert reviewing YAML configurations.

{self.get_full_documentation()}

When reviewing automation YAML:
1. Check for valid trigger, condition, and action syntax
2. Verify service calls use correct parameters
3. Identify potential security issues
4. Suggest improvements based on best practices
5. Check for infinite loops or unintended behavior

Respond in JSON format:
{{
    "safe": true/false,
    "approved": true/false,
    "issues": ["list of critical issues"],
    "warnings": ["list of warnings"],
    "suggestions": ["list of improvements"],
    "risk_level": "low|medium|high",
    "corrected_yaml": "corrected version if issues found (null if none)"
}}"""

    def get_prompt_for_automation_creation(self) -> str:
        """Get a prompt for the AI to create automation YAML."""
        return f"""You are a Home Assistant automation expert.

{self.get_full_documentation()}

When creating automations:
1. Use valid trigger syntax from the available triggers
2. Use proper condition syntax if needed
3. Use correct service call format with valid parameters
4. Include alias and description
5. Choose appropriate mode (single, restart, queued, parallel)
6. Follow best practices for security and performance

Respond ONLY with valid YAML, no markdown formatting, no explanation.
The YAML should be a single automation entry, not a list.

Example format:
id: auto_description
alias: "Automation Name"
description: "What this automation does"
trigger: [...]
condition: [...]
action: [...]
mode: single"""

    def get_prompt_for_dashboard_creation(self) -> str:
        """Get a prompt for the AI to create dashboard YAML."""
        return f"""You are a Home Assistant dashboard expert.

{self.get_full_documentation()}

When creating dashboards:
1. Use valid dashboard structure with title and url_path
2. Use appropriate card types for each entity
3. Follow the card type examples provided
4. Organize cards logically by room or function
5. Use meaningful titles for views and cards

Respond ONLY with valid YAML, no markdown formatting, no explanation.
The YAML should be a complete dashboard configuration."""


# Import yaml at module level for the documentation provider
import yaml
