"""Natural language to automation converter for Home Assistant.

This module converts natural language descriptions into proper
Home Assistant automation YAML with review capabilities.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class NLToAutomationResult:
    """Result of natural language to automation conversion."""

    def __init__(
        self,
        original_query: str = "",
        automation_config: Dict = None,
        yaml_output: str = "",
        confidence: float = 0.0,
        suggestions: List[str] = None,
        needs_clarification: bool = False,
        clarification_questions: List[str] = None,
    ):
        self.original_query = original_query
        self.automation_config = automation_config or {}
        self.yaml_output = yaml_output
        self.confidence = confidence
        self.suggestions = suggestions or []
        self.needs_clarification = needs_clarification
        self.clarification_questions = clarification_questions or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "original_query": self.original_query,
            "automation_config": self.automation_config,
            "yaml_output": self.yaml_output,
            "confidence": self.confidence,
            "suggestions": self.suggestions,
            "needs_clarification": self.needs_clarification,
            "clarification_questions": self.clarification_questions,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = ["## Natural Language to Automation Conversion"]
        lines.append("")
        lines.append(f"**Original Query:** {self.original_query}")
        lines.append("")

        if self.needs_clarification:
            lines.append("### ⚠️ Clarification Needed")
            lines.append("")
            for question in self.clarification_questions:
                lines.append(f"- {question}")
            lines.append("")
            return "\n".join(lines)

        lines.append(f"**Confidence:** {self.confidence:.1%}")
        lines.append("")

        if self.suggestions:
            lines.append("### Suggestions")
            lines.append("")
            for suggestion in self.suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

        if self.automation_config:
            lines.append("### Generated Automation")
            lines.append("")
            lines.append("```yaml")
            lines.append(self.yaml_output)
            lines.append("```")
            lines.append("")

        return "\n".join(lines)


class NLToAutomationConverter:
    """Converts natural language to Home Assistant automations."""

    # Time patterns
    TIME_PATTERNS = {
        "at_specific_time": re.compile(
            r"at\s+(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(am|pm)?", re.IGNORECASE
        ),
        "sunrise_sunset": re.compile(
            r"(sunrise|sunset)(\s+(before|after)\s+(\d+)\s+minutes)?", re.IGNORECASE
        ),
        "every_day": re.compile(
            r"(every\s+day|daily|each\s+day)", re.IGNORECASE
        ),
        "weekdays": re.compile(
            r"(weekdays|monday\s+to\s+friday)", re.IGNORECASE
        ),
        "weekends": re.compile(
            r"(weekends|saturday\s+and\s+sunday)", re.IGNORECASE
        ),
    }

    # Action patterns
    ACTION_PATTERNS = {
        "turn_on": re.compile(
            r"turn\s+on\s+(the\s+)?(.+?)(?:\s+(?:with|at|to)\s+(.+))?(?:\s+\.|,|$)",
            re.IGNORECASE,
        ),
        "turn_off": re.compile(
            r"turn\s+off\s+(the\s+)?(.+?)(?:\s+\.|,|$)", re.IGNORECASE
        ),
        "open": re.compile(
            r"open\s+(the\s+)?(.+?)(?:\s+\.|,|$)", re.IGNORECASE
        ),
        "close": re.compile(
            r"close\s+(the\s+)?(.+?)(?:\s+\.|,|$)", re.IGNORECASE
        ),
        "set_temperature": re.compile(
            r"set\s+(the\s+)?(?:temperature|thermostat)\s+(?:to|at)\s+(\d+\.?\d*)\s*(°?F|°?C)?",
            re.IGNORECASE,
        ),
        "set_volume": re.compile(
            r"set\s+(the\s+)?(?:volume|media)\s+(?:to|at)\s+(\d+)", re.IGNORECASE
        ),
    }

    # Entity type mappings
    ENTITY_TYPE_MAP = {
        "light": ["light", "lights", "lamp", "lamps", "bulb", "bulbs"],
        "switch": ["switch", "switches", "outlet", "outlets", "plug", "plugs"],
        "cover": [
            "cover",
            "covers",
            "blind",
            "blinds",
            "curtain",
            "curtains",
            "shutter",
            "shutters",
            "garage",
        ],
        "climate": [
            "climate",
            "thermostat",
            "heating",
            "cooling",
            "ac",
            "air conditioning",
        ],
        "media_player": [
            "media player",
            "media_player",
            "tv",
            "television",
            "speaker",
            "speakers",
        ],
        "lock": ["lock", "locks", "door lock", "smart lock"],
        "sensor": ["sensor", "sensors", "detector", "detectors"],
        "person": ["person", "people", "me", "myself", "you"],
        "vacuum": ["vacuum", "roomba", "robot vacuum"],
    }

    # Trigger type mappings
    TRIGGER_TYPE_MAP = {
        "arrive_home": re.compile(
            r"(?:arrive|come\s+home|get\s+home|get\s+home)", re.IGNORECASE
        ),
        "leave_home": re.compile(
            r"(?:leave|go\s+home|depart|leave\s+home)", re.IGNORECASE
        ),
        "sleep": re.compile(
            r"(?:go\s+to\s+bed|sleep|nighttime|good\s+night)", re.IGNORECASE
        ),
        "wake_up": re.compile(
            r"(?:wake\s+up|morning|get\s+up|good\s+morning)", re.IGNORECASE
        ),
        "motion": re.compile(
            r"(?:motion|movement|detected|moved)", re.IGNORECASE
        ),
    }

    def convert(
        self,
        natural_language: str,
        available_entities: Optional[List[Dict]] = None,
    ) -> NLToAutomationResult:
        """Convert natural language to automation configuration.

        Args:
            natural_language: The natural language description
            available_entities: Optional list of available entities for better matching

        Returns:
            NLToAutomationResult with the generated automation
        """
        if not natural_language or not natural_language.strip():
            return NLToAutomationResult(
                original_query=natural_language,
                needs_clarification=True,
                clarification_questions=["Please provide a natural language description of the automation you want to create."],
            )

        # Parse components
        time_info = self.parse_time_expression(natural_language)
        entities = self.identify_entities(natural_language, available_entities)
        action_info = self.identify_action(natural_language)
        trigger_info = self.identify_trigger(natural_language)

        # Check if clarification is needed
        needs_clarification, clarification_questions = self.check_clarification_needed(
            trigger_info, action_info, entities
        )

        if needs_clarification:
            return NLToAutomationResult(
                original_query=natural_language,
                needs_clarification=True,
                clarification_questions=clarification_questions,
                confidence=0.3,
            )

        # Generate automation config
        automation_config = self.generate_automation(
            trigger_info, action_info, entities, time_info
        )

        # Generate YAML
        yaml_output = self.generate_yaml(automation_config)

        # Calculate confidence
        confidence = self._calculate_confidence(
            trigger_info, action_info, entities, time_info
        )

        # Generate suggestions
        suggestions = self._generate_suggestions(
            trigger_info, action_info, entities, time_info
        )

        return NLToAutomationResult(
            original_query=natural_language,
            automation_config=automation_config,
            yaml_output=yaml_output,
            confidence=confidence,
            suggestions=suggestions,
            needs_clarification=False,
        )

    def parse_time_expression(self, text: str) -> Dict[str, Any]:
        """Parse time expressions from text.

        Args:
            text: Text containing time expression

        Returns:
            Dictionary with time information
        """
        time_info = {
            "trigger_type": None,
            "at_time": None,
            "sun_offset": None,
            "sun_direction": None,
            "schedule": None,
        }

        # Check for specific time (e.g., "at 6 PM", "at 18:00")
        time_match = self.TIME_PATTERNS["at_specific_time"].search(text)
        if time_match:
            hour = int(time_match.group(1))
            minutes = int(time_match.group(2)) if time_match.group(2) else 0
            seconds = int(time_match.group(3)) if time_match.group(3) else 0
            am_pm = time_match.group(4)

            # Convert to 24-hour format
            if am_pm:
                am_pm = am_pm.lower()
                if am_pm == "pm" and hour != 12:
                    hour += 12
                elif am_pm == "am" and hour == 12:
                    hour = 0

            time_info["at_time"] = f"{hour:02d}:{minutes:02d}:{seconds:02d}"
            time_info["trigger_type"] = "time"

        # Check for sunrise/sunset
        sunrise_match = self.TIME_PATTERNS["sunrise_sunset"].search(text)
        if sunrise_match:
            sun_event = sunrise_match.group(1).lower()
            time_info["trigger_type"] = "sun"
            time_info["sun_direction"] = sun_event

            if sunrise_match.group(3):  # before/after
                offset = int(sunrise_match.group(4))
                direction = sunrise_match.group(3).lower()
                time_info["sun_offset"] = f"-{offset}" if direction == "before" else f"+{offset}"

        # Check for daily/weekly patterns
        if self.TIME_PATTERNS["every_day"].search(text):
            time_info["schedule"] = "daily"

        if self.TIME_PATTERNS["weekdays"].search(text):
            time_info["schedule"] = "weekdays"

        if self.TIME_PATTERNS["weekends"].search(text):
            time_info["schedule"] = "weekends"

        return time_info

    def identify_entities(
        self,
        text: str,
        available_entities: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """Identify entities mentioned in text.

        Args:
            text: Text containing entity references
            available_entities: Optional list of available entities for matching

        Returns:
            List of matched entities
        """
        matched_entities = []
        text_lower = text.lower()

        # Search for entity mentions in the text
        for domain, keywords in self.ENTITY_TYPE_MAP.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Try to match against available entities
                    if available_entities:
                        matching = [
                            e
                            for e in available_entities
                            if e.get("domain") == domain
                            or keyword.lower() in e.get("name", "").lower()
                            or keyword.lower() in e.get("entity_id", "").lower()
                        ]
                        if matching:
                            for m in matching:
                                matched_entities.append(
                                    {
                                        "entity_id": m.get("entity_id"),
                                        "domain": domain,
                                        "name": m.get("name", m.get("entity_id")),
                                        "matched_keyword": keyword,
                                    }
                                )
                        else:
                            # Create a placeholder entity
                            matched_entities.append(
                                {
                                    "entity_id": f"{domain}.{keyword.replace(' ', '_')}",
                                    "domain": domain,
                                    "name": keyword.replace("_", " ").title(),
                                    "matched_keyword": keyword,
                                    "placeholder": True,
                                }
                            )
                    else:
                        # No available entities, create placeholder
                        matched_entities.append(
                            {
                                "entity_id": f"{domain}.{keyword.replace(' ', '_')}",
                                "domain": domain,
                                "name": keyword.replace("_", " ").title(),
                                "matched_keyword": keyword,
                                "placeholder": True,
                            }
                        )

        # Remove duplicates by entity_id
        seen = set()
        unique_entities = []
        for entity in matched_entities:
            if entity["entity_id"] not in seen:
                seen.add(entity["entity_id"])
                unique_entities.append(entity)

        return unique_entities

    def identify_action(self, text: str) -> Dict[str, Any]:
        """Identify the action to perform.

        Args:
            text: Text containing action description

        Returns:
            Dictionary with action information
        """
        action_info = {
            "action_type": None,
            "service": None,
            "service_data": None,
        }

        # Check for turn on
        turn_on_match = self.ACTION_PATTERNS["turn_on"].search(text)
        if turn_on_match:
            action_info["action_type"] = "turn_on"
            action_info["service"] = "homeassistant.turn_on"
            return action_info

        # Check for turn off
        turn_off_match = self.ACTION_PATTERNS["turn_off"].search(text)
        if turn_off_match:
            action_info["action_type"] = "turn_off"
            action_info["service"] = "homeassistant.turn_off"
            return action_info

        # Check for open
        open_match = self.ACTION_PATTERNS["open"].search(text)
        if open_match:
            action_info["action_type"] = "open"
            action_info["service"] = "cover.open_cover"
            return action_info

        # Check for close
        close_match = self.ACTION_PATTERNS["close"].search(text)
        if close_match:
            action_info["action_type"] = "close"
            action_info["service"] = "cover.close_cover"
            return action_info

        # Check for temperature setting
        temp_match = self.ACTION_PATTERNS["set_temperature"].search(text)
        if temp_match:
            action_info["action_type"] = "set_temperature"
            action_info["service"] = "climate.set_temperature"
            temperature = float(temp_match.group(2))
            unit = temp_match.group(3)

            # Convert Fahrenheit to Celsius if needed
            if unit and "F" in unit:
                temperature = (temperature - 32) * 5 / 9

            action_info["service_data"] = {"temperature": round(temperature, 1)}
            return action_info

        # Check for volume setting
        volume_match = self.ACTION_PATTERNS["set_volume"].search(text)
        if volume_match:
            action_info["action_type"] = "set_volume"
            action_info["service"] = "media_player.volume_set"
            action_info["service_data"] = {
                "volume_level": int(volume_match.group(1)) / 100
            }
            return action_info

        return action_info

    def identify_trigger(self, text: str) -> Dict[str, Any]:
        """Identify the trigger condition.

        Args:
            text: Text containing trigger description

        Returns:
            Dictionary with trigger information
        """
        trigger_info = {
            "trigger_type": None,
            "platform": None,
            "entity_id": None,
            "zone": None,
        }

        # Check for home/away triggers
        for trigger_name, pattern in self.TRIGGER_TYPE_MAP.items():
            if pattern.search(text):
                trigger_info["trigger_type"] = trigger_name

                if trigger_name == "arrive_home":
                    trigger_info["platform"] = "state"
                    trigger_info["entity_id"] = "device_tracker.phone"
                    trigger_info["to_state"] = "home"
                elif trigger_name == "leave_home":
                    trigger_info["platform"] = "state"
                    trigger_info["entity_id"] = "device_tracker.phone"
                    trigger_info["from_state"] = "home"
                elif trigger_name == "motion":
                    trigger_info["platform"] = "state"
                    trigger_info["entity_id"] = "binary_sensor.motion_sensor"
                    trigger_info["to_state"] = "on"
                elif trigger_name in ("sleep", "wake_up"):
                    trigger_info["platform"] = "time"

                return trigger_info

        # Default to no specific trigger
        return trigger_info

    def generate_automation(
        self,
        trigger_info: Dict,
        action_info: Dict,
        entities: List[Dict],
        time_info: Dict,
    ) -> Dict[str, Any]:
        """Generate automation configuration from parsed components.

        Args:
            trigger_info: Parsed trigger information
            action_info: Parsed action information
            entities: Identified entities
            time_info: Parsed time information

        Returns:
            Automation configuration dictionary
        """
        automation = {
            "alias": self._generate_alias(trigger_info, action_info, entities),
            "description": f"Auto-generated automation: {self._generate_description(trigger_info, action_info, entities)}",
            "trigger": [],
            "condition": [],
            "action": [],
            "options": {},
            "mode": "single",
        }

        # Build trigger
        trigger = self._build_trigger(trigger_info, time_info)
        if trigger:
            automation["trigger"].append(trigger)

        # Build action
        action = self._build_action(action_info, entities)
        if action:
            automation["action"].append(action)

        # Add default condition if needed
        if len(entities) > 1:
            automation["condition"].append(
                {
                    "condition": "state",
                    "entity_id": entities[0]["entity_id"],
                    "state": "off",
                }
            )

        return automation

    def generate_yaml(self, automation_config: Dict) -> str:
        """Generate YAML output from automation configuration.

        Args:
            automation_config: Automation configuration dictionary

        Returns:
            YAML string
        """
        # Simple YAML generation (no external dependencies)
        yaml_lines = []

        for key, value in automation_config.items():
            if key in ("trigger", "action", "condition"):
                yaml_lines.append(f"{key}:")
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            yaml_lines.append("  -")
                            for sub_key, sub_value in item.items():
                                if isinstance(sub_value, dict):
                                    yaml_lines.append(f"    {sub_key}:")
                                    for sk, sv in sub_value.items():
                                        yaml_lines.append(f"      {sk}: {self._format_yaml_value(sv)}")
                                else:
                                    yaml_lines.append(f"    {sub_key}: {self._format_yaml_value(sub_value)}")
            else:
                yaml_lines.append(f"{key}: {self._format_yaml_value(value)}")

        return "\n".join(yaml_lines)

    def check_clarification_needed(
        self,
        trigger_info: Dict,
        action_info: Dict,
        entities: List[Dict],
    ) -> tuple:
        """Check if clarification is needed.

        Args:
            trigger_info: Parsed trigger information
            action_info: Parsed action information
            entities: Identified entities

        Returns:
            Tuple of (needs_clarification: bool, questions: List[str])
        """
        questions = []

        if not trigger_info.get("trigger_type"):
            questions.append(
                "What should trigger this automation? (e.g., 'when I arrive home', 'at 6 PM', 'when motion is detected')"
            )

        if not action_info.get("action_type"):
            questions.append(
                "What action should the automation perform? (e.g., 'turn on the lights', 'set temperature to 72°F')"
            )

        if not entities and not action_info.get("action_type"):
            questions.append(
                "Which devices or entities should be affected? (e.g., 'living room lights', 'thermostat')"
            )

        return (len(questions) > 0, questions)

    def get_ai_conversion_prompt(
        self,
        natural_language: str,
        available_entities: List[Dict],
    ) -> str:
        """Generate an AI prompt for complex conversions."""
        entity_list = "\n".join(
            [f"- {e.get('entity_id')}: {e.get('name')} ({e.get('domain')})"
             for e in available_entities]
        )

        prompt = f"""You are a Home Assistant automation expert. Convert the following natural language description into a valid Home Assistant automation configuration.

User's request: "{natural_language}"

Available entities:
{entity_list}

Please provide:
1. A clear automation alias
2. Appropriate trigger(s)
3. Any necessary conditions
4. The action(s) to perform
5. Recommended mode (single, restart, parallel)

Return the automation as a valid YAML configuration.
"""
        return prompt

    # === Private Helper Methods ===

    def _generate_alias(self, trigger_info: Dict, action_info: Dict, entities: List[Dict]) -> str:
        """Generate an automation alias."""
        parts = []

        if trigger_info.get("trigger_type"):
            trigger_map = {
                "arrive_home": "On Arrival",
                "leave_home": "On Departure",
                "motion": "On Motion",
                "sleep": "Bedtime",
                "wake_up": "Morning",
            }
            parts.append(trigger_map.get(trigger_info["trigger_type"], "Triggered"))

        if action_info.get("action_type"):
            action_map = {
                "turn_on": "Turn On",
                "turn_off": "Turn Off",
                "open": "Open",
                "close": "Close",
                "set_temperature": "Set Temperature",
                "set_volume": "Set Volume",
            }
            parts.append(action_map.get(action_info["action_type"], "Action"))

        if entities:
            domain = entities[0].get("domain", "device")
            parts.append(domain.title())

        return " ".join(parts) if parts else "Auto-Generated Automation"

    def _generate_description(self, trigger_info: Dict, action_info: Dict, entities: List[Dict]) -> str:
        """Generate an automation description."""
        parts = []

        if trigger_info.get("trigger_type"):
            parts.append(f"triggered by {trigger_info['trigger_type'].replace('_', ' ')}")

        if action_info.get("action_type"):
            parts.append(f"to {action_info['action_type'].replace('_', ' ')}")

        if entities:
            entity_names = [e.get("name", e.get("domain")) for e in entities[:2]]
            parts.append(f"for {', '.join(entity_names)}")

        return " ".join(parts) if parts else "Auto-generated automation"

    def _build_trigger(self, trigger_info: Dict, time_info: Dict) -> Dict:
        """Build the trigger configuration."""
        trigger = {}

        if time_info.get("trigger_type") == "time":
            trigger = {
                "platform": "time",
            }
            if time_info.get("at_time"):
                trigger["at"] = time_info["at_time"]

        elif time_info.get("trigger_type") == "sun":
            trigger = {
                "platform": "sun",
                "event": time_info.get("sun_direction", "sunset"),
            }
            if time_info.get("sun_offset"):
                trigger["offset"] = int(time_info["sun_offset"])

        elif trigger_info.get("platform") == "state":
            trigger = {
                "platform": "state",
                "entity_id": trigger_info.get("entity_id", "device_tracker.phone"),
            }
            if "to_state" in trigger_info:
                trigger["to"] = trigger_info["to_state"]
            if "from_state" in trigger_info:
                trigger["from"] = trigger_info["from_state"]

        elif trigger_info.get("trigger_type") in ("sleep", "wake_up"):
            trigger = {
                "platform": "time",
                "at": "22:00:00" if trigger_info["trigger_type"] == "sleep" else "07:00:00",
            }

        return trigger

    def _build_action(self, action_info: Dict, entities: List[Dict]) -> Dict:
        """Build the action configuration."""
        if not action_info.get("service"):
            return {}

        action = {
            "service": action_info["service"],
        }

        # Build target from entities
        if entities:
            entity_ids = [e["entity_id"] for e in entities if not e.get("placeholder")]
            if entity_ids:
                action["target"] = {"entity_id": entity_ids}
            else:
                # Use placeholder entities
                entity_ids = [e["entity_id"] for e in entities]
                action["target"] = {"entity_id": entity_ids}

        # Add service data
        if action_info.get("service_data"):
            action["data"] = action_info["service_data"]

        return action

    def _calculate_confidence(
        self,
        trigger_info: Dict,
        action_info: Dict,
        entities: List[Dict],
        time_info: Dict,
    ) -> float:
        """Calculate confidence score for the conversion."""
        score = 0.0
        max_score = 4.0

        if trigger_info.get("trigger_type"):
            score += 1.0
        if action_info.get("action_type"):
            score += 1.0
        if entities:
            score += 1.0
        if time_info.get("at_time") or time_info.get("sun_direction"):
            score += 1.0

        return score / max_score

    def _generate_suggestions(
        self,
        trigger_info: Dict,
        action_info: Dict,
        entities: List[Dict],
        time_info: Dict,
    ) -> List[str]:
        """Generate suggestions for improving the automation."""
        suggestions = []

        if not time_info.get("at_time") and not time_info.get("sun_direction"):
            suggestions.append("Consider adding a time constraint for more precise control.")

        if not entities:
            suggestions.append("Specify which devices should be affected.")

        if len(entities) > 0 and any(e.get("placeholder") for e in entities):
            suggestions.append("Replace placeholder entities with actual Home Assistant entity IDs.")

        if not any(c.get("condition") for c in [{"condition": []}]):
            suggestions.append("Consider adding conditions (e.g., only during certain hours, only when someone is home).")

        return suggestions

    def _format_yaml_value(self, value: Any) -> str:
        """Format a value for YAML output."""
        if isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            # Quote strings that might be ambiguous
            if value.lower() in ("true", "false", "yes", "no", "on", "off", "null", "none"):
                return f'"{value}"'
            return value
        return str(value)
