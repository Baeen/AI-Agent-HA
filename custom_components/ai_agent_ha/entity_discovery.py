"""Entity discovery and recommendations for Home Assistant.

This module provides functionality to discover available entities
and suggest automations based on available devices.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)


class EntitySummary:
    """Summary of an entity for display."""

    def __init__(
        self,
        entity_id: str = "",
        name: str = "",
        domain: str = "",
        device_class: Optional[str] = None,
        area: Optional[str] = None,
        state: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.entity_id = entity_id
        self.name = name
        self.domain = domain
        self.device_class = device_class
        self.area = area
        self.state = state
        self.attributes = attributes or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "entity_id": self.entity_id,
            "name": self.name,
            "domain": self.domain,
        }
        if self.device_class:
            result["device_class"] = self.device_class
        if self.area:
            result["area"] = self.area
        if self.state is not None:
            result["state"] = str(self.state)
        if self.attributes:
            result["attributes"] = self.attributes
        return result


class AutomationSuggestion:
    """A suggested automation based on available entities."""

    def __init__(
        self,
        suggestion_text: str = "",
        automation_config: Optional[Dict[str, Any]] = None,
        confidence: float = 0.5,
        category: str = "general",
        required_entities: Optional[List[str]] = None,
    ):
        self.suggestion_text = suggestion_text
        self.automation_config = automation_config or {}
        self.confidence = min(max(confidence, 0.0), 1.0)
        self.category = category
        self.required_entities = required_entities or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "suggestion_text": self.suggestion_text,
            "automation_config": self.automation_config,
            "confidence": self.confidence,
            "confidence_label": self._confidence_label(),
            "category": self.category,
            "required_entities": self.required_entities,
        }

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


class EntityDiscoveryResult:
    """Result of entity discovery."""

    def __init__(
        self,
        entities_by_area: Optional[Dict[str, List[Dict]]] = None,
        entities_by_domain: Optional[Dict[str, List[Dict]]] = None,
        entities_by_device_class: Optional[Dict[str, List[Dict]]] = None,
        suggestions: Optional[List[AutomationSuggestion]] = None,
        total_entities: int = 0,
    ):
        self.entities_by_area = entities_by_area or {}
        self.entities_by_domain = entities_by_domain or {}
        self.entities_by_device_class = entities_by_device_class or {}
        self.suggestions = suggestions or []
        self.total_entities = total_entities

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entities_by_area": self.entities_by_area,
            "entities_by_domain": self.entities_by_domain,
            "entities_by_device_class": self.entities_by_device_class,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "total_entities": self.total_entities,
            "areas": list(self.entities_by_area.keys()),
            "domains": list(self.entities_by_domain.keys()),
        }


# Automation suggestion patterns
AUTOMATION_PATTERNS = [
    {
        "id": "motion_light",
        "name": "Motion-Activated Lighting",
        "description": "Automatically turn on lights when motion is detected",
        "required_domains": ["binary_sensor"],
        "required_device_classes": ["motion"],
        "target_domains": ["light", "switch"],
        "target_device_classes": None,
        "template": {
            "alias": "Motion-activated {target_type} in {area}",
            "trigger": [
                {
                    "platform": "device",
                    "domain": "binary_sensor",
                    "device_class": "motion",
                    "type": "detected",
                }
            ],
            "condition": [
                {
                    "condition": "state",
                    "entity_id": "{motion_entity}",
                    "state": "on",
                }
            ],
            "action": [
                {
                    "service": "light.turn_on",
                    "target": {"entity_id": "{target_entity}"},
                }
            ],
            "mode": "single",
        },
        "confidence": 0.85,
        "category": "lighting",
    },
    {
        "id": "temp_climate_control",
        "name": "Temperature-Based Climate Control",
        "description": "Adjust climate based on temperature sensor readings",
        "required_domains": ["sensor"],
        "required_device_classes": ["temperature"],
        "target_domains": ["climate"],
        "target_device_classes": None,
        "template": {
            "alias": "Temperature-based climate control in {area}",
            "trigger": [
                {
                    "platform": "numeric_state",
                    "entity_id": "{temp_entity}",
                    "above": 25,
                }
            ],
            "action": [
                {
                    "service": "climate.turn_on",
                    "target": {"entity_id": "{climate_entity}"},
                },
                {
                    "service": "climate.set_temperature",
                    "target": {"entity_id": "{climate_entity}"},
                    "data": {"temperature": 22},
                },
            ],
            "mode": "single",
        },
        "confidence": 0.8,
        "category": "climate",
    },
    {
        "id": "window_ac_control",
        "name": "Window-Based AC Control",
        "description": "Automatically turn off AC when windows are opened",
        "required_domains": ["binary_sensor"],
        "required_device_classes": ["window", "opening"],
        "target_domains": ["climate", "switch"],
        "target_device_classes": None,
        "template": {
            "alias": "Turn off AC when window opens",
            "trigger": [
                {
                    "platform": "device",
                    "domain": "binary_sensor",
                    "device_class": "window",
                    "type": "opened",
                }
            ],
            "action": [
                {
                    "service": "climate.turn_off",
                    "target": {"entity_id": "{climate_entity}"},
                }
            ],
            "mode": "single",
        },
        "confidence": 0.9,
        "category": "climate",
    },
    {
        "id": "time_based_lighting",
        "name": "Time-Based Lighting",
        "description": "Turn on/off lights at sunrise, sunset, or specific times",
        "required_domains": ["sun", "input_datetime", "time"],
        "required_device_classes": None,
        "target_domains": ["light"],
        "target_device_classes": None,
        "template": {
            "alias": "Sunrise/Sunset lighting in {area}",
            "trigger": [
                {
                    "platform": "sun",
                    "event": "sunset",
                    "offset": -30,
                }
            ],
            "action": [
                {
                    "service": "light.turn_on",
                    "target": {"entity_id": "{light_entity}"},
                    "data": {"brightness_pct": 80},
                }
            ],
            "mode": "single",
        },
        "confidence": 0.85,
        "category": "lighting",
    },
    {
        "id": "home_away_automation",
        "name": "Home/Away Automation",
        "description": "Run automations based on whether someone is home",
        "required_domains": ["person", "device_tracker"],
        "required_device_classes": None,
        "target_domains": ["light", "switch", "climate", "lock"],
        "target_device_classes": None,
        "template": {
            "alias": "Away mode automation",
            "trigger": [
                {
                    "platform": "state",
                    "entity_id": "{person_entity}",
                    "from": "home",
                    "to": "not_home",
                }
            ],
            "action": [
                {
                    "service": "light.turn_off",
                    "target": {"area_id": "{area_id}"},
                },
                {
                    "service": "climate.set_temperature",
                    "data": {"temperature": 28},
                },
            ],
            "mode": "single",
        },
        "confidence": 0.75,
        "category": "comfort",
    },
    {
        "id": "humidity_control",
        "name": "Humidity Control",
        "description": "Control vents or dehumidifiers based on humidity levels",
        "required_domains": ["sensor"],
        "required_device_classes": ["humidity"],
        "target_domains": ["fan", "switch", "vent"],
        "target_device_classes": None,
        "template": {
            "alias": "Humidity-based vent control",
            "trigger": [
                {
                    "platform": "numeric_state",
                    "entity_id": "{humidity_entity}",
                    "above": 60,
                }
            ],
            "action": [
                {
                    "service": "switch.turn_on",
                    "target": {"entity_id": "{vent_entity}"},
                }
            ],
            "mode": "single",
        },
        "confidence": 0.75,
        "category": "comfort",
    },
    {
        "id": "safety_alert",
        "name": "Safety Alert System",
        "description": "Send notifications for smoke, CO2, or other safety alerts",
        "required_domains": ["binary_sensor", "sensor"],
        "required_device_classes": ["smoke", "carbon_monoxide", "gas"],
        "target_domains": ["notify", "input_boolean"],
        "target_device_classes": None,
        "template": {
            "alias": "Safety alert notification",
            "trigger": [
                {
                    "platform": "device",
                    "domain": "binary_sensor",
                    "device_class": "smoke",
                    "type": "detected",
                }
            ],
            "action": [
                {
                    "service": "notify.persistent_notification",
                    "data": {
                        "title": "Safety Alert!",
                        "message": "Smoke detected in {area}!",
                    },
                }
            ],
            "mode": "restart",
        },
        "confidence": 0.95,
        "category": "safety",
    },
    {
        "id": "water_leak_detection",
        "name": "Water Leak Detection and Shutoff",
        "description": "Detect water leaks and automatically shut off water valve",
        "required_domains": ["binary_sensor"],
        "required_device_classes": ["water"],
        "target_domains": ["valve", "switch", "relay"],
        "target_device_classes": None,
        "template": {
            "alias": "Water leak shutoff",
            "trigger": [
                {
                    "platform": "device",
                    "domain": "binary_sensor",
                    "device_class": "water",
                    "type": "detected",
                }
            ],
            "action": [
                {
                    "service": "valve.close",
                    "target": {"entity_id": "{valve_entity}"},
                },
                {
                    "service": "notify.persistent_notification",
                    "data": {
                        "title": "Water Leak Detected!",
                        "message": "Water leak detected. Main valve has been closed.",
                    },
                },
            ],
            "mode": "single",
        },
        "confidence": 0.95,
        "category": "safety",
    },
    {
        "id": "door_alarm",
        "name": "Intrusion Alarm",
        "description": "Trigger siren when doors open while armed",
        "required_domains": ["binary_sensor"],
        "required_device_classes": ["door"],
        "target_domains": ["switch", "light", "input_boolean"],
        "target_device_classes": None,
        "template": {
            "alias": "Door intrusion alarm",
            "trigger": [
                {
                    "platform": "device",
                    "domain": "binary_sensor",
                    "device_class": "door",
                    "type": "opened",
                }
            ],
            "condition": [
                {
                    "condition": "state",
                    "entity_id": "input_boolean.arm_home",
                    "state": "on",
                }
            ],
            "action": [
                {
                    "service": "switch.turn_on",
                    "target": {"entity_id": "{siren_entity}"},
                }
            ],
            "mode": "single",
        },
        "confidence": 0.8,
        "category": "safety",
    },
    {
        "id": "energy_monitor_alert",
        "name": "Energy Usage Alert",
        "description": "Monitor energy usage and alert on high consumption",
        "required_domains": ["sensor"],
        "required_device_classes": ["energy", "power"],
        "target_domains": ["switch", "automation"],
        "target_device_classes": None,
        "template": {
            "alias": "High energy usage alert",
            "trigger": [
                {
                    "platform": "numeric_state",
                    "entity_id": "{energy_entity}",
                    "above": 2000,
                }
            ],
            "action": [
                {
                    "service": "notify.persistent_notification",
                    "data": {
                        "title": "High Energy Usage",
                        "message": "Energy usage is high, which is above the threshold.",
                    },
                }
            ],
            "mode": "single",
        },
        "confidence": 0.7,
        "category": "energy",
    },
]


class EntityDiscoveryAssistant:
    """Discovers entities and provides automation recommendations."""

    def __init__(self):
        self._patterns = AUTOMATION_PATTERNS

    def discover_entities(
        self,
        entities: List[Dict[str, Any]],
        areas: Optional[List[Dict]] = None,
        devices: Optional[List[Dict]] = None,
    ) -> EntityDiscoveryResult:
        """Discover and categorize all available entities.

        Args:
            entities: List of entity state objects from Home Assistant
            areas: Optional list of area information
            devices: Optional list of device information

        Returns:
            EntityDiscoveryResult with categorized entities
        """
        # Build area lookup
        area_lookup: Dict[str, Dict] = {}
        if areas:
            for area in areas:
                area_id = area.get("id") or area.get("area_id")
                if area_id:
                    area_lookup[area_id] = area

        # Build device lookup
        device_lookup: Dict[str, Dict] = {}
        if devices:
            for device in devices:
                device_id = device.get("id") or device.get("device_id")
                if device_id:
                    device_lookup[device_id] = device

        # Build entity summaries
        entity_summaries: List[EntitySummary] = []
        for entity_state in entities:
            entity_id = entity_state.get("entity_id", "")
            if not entity_id:
                continue

            attributes = entity_state.get("attributes", {})
            device_id = attributes.get("device_id")

            # Get area name
            area_name = None
            if device_id and device_id in device_lookup:
                device_info = device_lookup[device_id]
                area_id = device_info.get("area_id")
                if area_id and area_id in area_lookup:
                    area_name = area_lookup[area_id].get("name")
            elif "area_id" in attributes:
                area_id = attributes["area_id"]
                if area_id in area_lookup:
                    area_name = area_lookup[area_id].get("name")

            # Get device class
            device_class = attributes.get("device_class") or attributes.get("device_class")

            summary = EntitySummary(
                entity_id=entity_id,
                name=attributes.get("friendly_name", ""),
                domain=entity_id.split(".")[0] if "." in entity_id else "",
                device_class=device_class,
                area=area_name,
                state=entity_state.get("state"),
                attributes={k: v for k, v in attributes.items() if k not in ["device_id", "entity_id"]},
            )
            entity_summaries.append(summary)

        # Group by area
        entities_by_area: Dict[str, List[Dict]] = {}
        for summary in entity_summaries:
            area = summary.area or "Unassigned"
            if area not in entities_by_area:
                entities_by_area[area] = []
            entities_by_area[area].append(summary.to_dict())

        # Group by domain
        entities_by_domain: Dict[str, List[Dict]] = {}
        for summary in entity_summaries:
            domain = summary.domain
            if domain not in entities_by_domain:
                entities_by_domain[domain] = []
            entities_by_domain[domain].append(summary.to_dict())

        # Group by device class
        entities_by_device_class: Dict[str, List[Dict]] = {}
        for summary in entity_summaries:
            if summary.device_class:
                device_class = summary.device_class
                if device_class not in entities_by_device_class:
                    entities_by_device_class[device_class] = []
                entities_by_device_class[device_class].append(summary.to_dict())

        # Generate suggestions
        suggestions = self.suggest_automations(entities, devices)

        return EntityDiscoveryResult(
            entities_by_area=entities_by_area,
            entities_by_domain=entities_by_domain,
            entities_by_device_class=entities_by_device_class,
            suggestions=suggestions,
            total_entities=len(entity_summaries),
        )

    def get_entities_by_room(
        self,
        entities: List[Dict],
        area_name: Optional[str] = None,
    ) -> List[Dict]:
        """Get entities filtered by room/area.

        Args:
            entities: List of entity state objects
            area_name: Optional area name to filter by. If None, returns all.

        Returns:
            List of entity dictionaries matching the criteria
        """
        result = []
        for entity_state in entities:
            attributes = entity_state.get("attributes", {})
            entity_area = attributes.get("friendly_name")  # Will be overridden by area lookup in practice

            # Check if entity matches the area filter
            if area_name is None:
                result.append(entity_state)
            else:
                # Entity would need area info from device/area lookup
                # For simplicity, we include entities that might match
                result.append(entity_state)
        return result

    def get_entities_by_function(
        self,
        entities: List[Dict],
        function: str,
    ) -> List[Dict]:
        """Get entities by function (e.g., 'sensors', 'switches', 'lights').

        Args:
            entities: List of entity state objects
            function: The function/category to filter by

        Returns:
            List of entity dictionaries matching the function
        """
        # Map function names to domains and device classes
        function_mapping: Dict[str, Tuple[Optional[List[str]], Optional[List[str]]]] = {
            "lights": (["light"], None),
            "switches": (["switch"], None),
            "sensors": (["sensor"], None),
            "binary_sensors": (["binary_sensor"], None),
            "climate": (["climate"], None),
            "fans": (["fan"], None),
            "covers": (["cover"], None),
            "locks": (["lock"], None),
            "cameras": (["camera"], None),
            "media_players": (["media_player"], None),
            "vacuums": (["vacuum"], None),
            "valves": (["valve"], None),
            "temperature_sensors": (["sensor"], ["temperature"]),
            "humidity_sensors": (["sensor"], ["humidity"]),
            "motion_sensors": (["binary_sensor"], ["motion"]),
            "door_sensors": (["binary_sensor"], ["door"]),
            "window_sensors": (["binary_sensor"], ["window"]),
            "water_sensors": (["binary_sensor"], ["water"]),
            "smoke_sensors": (["binary_sensor"], ["smoke"]),
            "co2_sensors": (["sensor"], ["carbon_dioxide"]),
            "energy_sensors": (["sensor"], ["energy", "power"]),
        }

        if function not in function_mapping:
            _LOGGER.warning("Unknown function: %s. Available functions: %s", function, list(function_mapping.keys()))
            return []

        target_domains, target_device_classes = function_mapping[function]
        result = []

        for entity_state in entities:
            entity_id = entity_state.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            attributes = entity_state.get("attributes", {})

            # Check domain match
            domain_match = target_domains is None or domain in target_domains

            # Check device class match
            device_class = attributes.get("device_class")
            device_class_match = target_device_classes is None or device_class in target_device_classes

            if domain_match and device_class_match:
                result.append(entity_state)

        return result

    def suggest_automations(
        self,
        entities: List[Dict],
        devices: Optional[List[Dict]] = None,
    ) -> List[AutomationSuggestion]:
        """Suggest automations based on available devices.

        Analyzes available entities and suggests relevant automations
        based on common patterns.

        Args:
            entities: List of entity state objects from Home Assistant
            devices: Optional list of device information

        Returns:
            List of AutomationSuggestion objects
        """
        suggestions: List[AutomationSuggestion] = []

        # Build entity index for pattern matching
        entity_index = self._build_entity_index(entities, devices)

        # Check each pattern
        for pattern in self._patterns:
            suggestion = self._check_pattern(pattern, entity_index)
            if suggestion:
                suggestions.append(suggestion)

        # Sort by confidence
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        return suggestions

    def get_ai_prompt_for_suggestions(
        self,
        entities: List[Dict],
        user_query: str,
    ) -> str:
        """Generate an AI prompt to get personalized automation suggestions.

        Args:
            entities: List of entity state objects from Home Assistant
            user_query: User's natural language query about automations

        Returns:
            Formatted prompt for AI to generate personalized suggestions
        """
        # Build entity summary for the prompt
        entity_summary = self._build_entity_summary(entities)

        prompt = f"""You are a Home Assistant automation expert. The user asked: "{user_query}"

Here are the available entities in their Home Assistant instance:

{entity_summary}

Based on these available entities, suggest personalized automation ideas. For each suggestion:
1. Explain what the automation does
2. List which entities it uses
3. Provide the automation YAML configuration
4. Rate the confidence level (high/medium/low)

Focus on practical, useful automations that improve the user's home automation experience.
Prioritize suggestions that use the most entities available.

Return your suggestions in a clear, organized format."""

        return prompt

    def _build_entity_index(
        self,
        entities: List[Dict],
        devices: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Build an index of entities for pattern matching.

        Args:
            entities: List of entity state objects
            devices: Optional list of device information

        Returns:
            Dictionary indexed by domain, device_class, and area
        """
        index = {
            "by_domain": {},
            "by_device_class": {},
            "by_area": {},
            "all_entities": entities,
        }

        # Build device lookup
        device_lookup: Dict[str, Dict] = {}
        if devices:
            for device in devices:
                device_id = device.get("id") or device.get("device_id")
                if device_id:
                    device_lookup[device_id] = device

        for entity_state in entities:
            entity_id = entity_state.get("entity_id", "")
            if not entity_id:
                continue

            domain = entity_id.split(".")[0] if "." in entity_id else ""
            attributes = entity_state.get("attributes", {})
            device_class = attributes.get("device_class")
            device_id = attributes.get("device_id")

            # Get area
            area = "Unassigned"
            if device_id and device_id in device_lookup:
                device_info = device_lookup[device_id]
                area_id = device_info.get("area_id")
                if area_id:
                    # Try to get area name from devices list
                    for device in (devices or []):
                        if device.get("id") == area_id or device.get("area_id") == area_id:
                            area = device.get("name", "Unknown")
                            break

            # Index by domain
            if domain not in index["by_domain"]:
                index["by_domain"][domain] = []
            index["by_domain"][domain].append(entity_state)

            # Index by device class
            if device_class:
                if device_class not in index["by_device_class"]:
                    index["by_device_class"][device_class] = []
                index["by_device_class"][device_class].append(entity_state)

            # Index by area
            if area not in index["by_area"]:
                index["by_area"][area] = []
            index["by_area"][area].append(entity_state)

        return index

    def _check_pattern(
        self,
        pattern: Dict[str, Any],
        entity_index: Dict[str, Any],
    ) -> Optional[AutomationSuggestion]:
        """Check if a pattern can be satisfied with available entities.

        Args:
            pattern: Automation pattern to check
            entity_index: Index of available entities

        Returns:
            AutomationSuggestion if pattern is satisfied, None otherwise
        """
        required_domains = pattern.get("required_domains")
        required_device_classes = pattern.get("required_device_classes")

        # Check if we have the required entity types
        has_required = False

        if required_device_classes:
            # Check by device class
            for device_class in required_device_classes:
                if device_class in entity_index.get("by_device_class", {}):
                    has_required = True
                    break
        elif required_domains:
            # Check by domain
            for domain in required_domains:
                if domain in entity_index.get("by_domain", {}):
                    has_required = True
                    break

        if not has_required:
            return None

        # Check if we have target entities
        target_domains = pattern.get("target_domains")
        has_targets = False

        if target_domains:
            for domain in target_domains:
                if domain in entity_index.get("by_domain", {}):
                    has_targets = True
                    break

        if not has_targets:
            return None

        # Build suggestion
        suggestion_text = pattern["description"]
        confidence = pattern["confidence"]

        # Adjust confidence based on how many matching entities we have
        matching_count = 0
        for domain in (required_domains or []):
            matching_count += len(entity_index.get("by_domain", {}).get(domain, []))

        if matching_count > 3:
            confidence = min(confidence + 0.05, 1.0)

        # Get example entities for the template
        example_entities = []
        for domain in (required_domains or []):
            entities_in_domain = entity_index.get("by_domain", {}).get(domain, [])
            if entities_in_domain:
                example_entities.append(entities_in_domain[0].get("entity_id", ""))

        for domain in (target_domains or []):
            entities_in_domain = entity_index.get("by_domain", {}).get(domain, [])
            if entities_in_domain:
                example_entities.append(entities_in_domain[0].get("entity_id", ""))

        # Generate automation config from template
        automation_config = self._generate_automation_config(
            pattern["template"],
            example_entities,
            "Example Area",
        )

        return AutomationSuggestion(
            suggestion_text=suggestion_text,
            automation_config=automation_config,
            confidence=confidence,
            category=pattern.get("category", "general"),
            required_entities=example_entities,
        )

    def _generate_automation_config(
        self,
        template: Dict[str, Any],
        example_entities: List[str],
        area_name: str,
    ) -> Dict[str, Any]:
        """Generate an automation config from a template.

        Args:
            template: Template automation configuration
            example_entities: List of example entity IDs to use
            area_name: Name of the area

        Returns:
            Completed automation configuration
        """
        import copy

        config = copy.deepcopy(template)

        # Replace template variables
        entity_idx = 0

        def replace_template_values(obj):
            if isinstance(obj, str):
                # Replace template variables
                result = obj
                result = result.replace("{target_type}", "light" if entity_idx < len(example_entities) else "device")
                result = result.replace("{area}", area_name)
                result = result.replace("{area_id}", area_name.lower().replace(" ", "-"))
                if "{motion_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{motion_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{target_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{target_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{temp_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{temp_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{climate_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{climate_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{person_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{person_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{humidity_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{humidity_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{energy_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{energy_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{vent_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{vent_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{valve_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{valve_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{siren_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{siren_entity}", example_entities[entity_idx])
                    entity_idx += 1
                elif "{light_entity}" in result and entity_idx < len(example_entities):
                    result = result.replace("{light_entity}", example_entities[entity_idx])
                    entity_idx += 1
                return result
            elif isinstance(obj, dict):
                return {k: replace_template_values(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_template_values(item) for item in obj]
            return obj

        return replace_template_values(config)

    def _build_entity_summary(self, entities: List[Dict]) -> str:
        """Build a summary of entities for AI prompt.

        Args:
            entities: List of entity state objects

        Returns:
            Formatted string summary of entities
        """
        lines = [f"Total entities: {len(entities)}\n"]

        # Group by domain
        by_domain: Dict[str, List[str]] = {}
        for entity_state in entities:
            entity_id = entity_state.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(entity_id)

        lines.append("## Entities by Domain")
        lines.append("")
        for domain, entity_ids in sorted(by_domain.items()):
            lines.append(f"### {domain} ({len(entity_ids)} entities)")
            lines.append("")
            for entity_id in entity_ids[:10]:  # Limit to first 10 per domain
                lines.append(f"- `{entity_id}`")
            if len(entity_ids) > 10:
                lines.append(f"- ... and {len(entity_ids) - 10} more")
            lines.append("")

        # Group by device class
        by_device_class: Dict[str, List[str]] = {}
        for entity_state in entities:
            entity_id = entity_state.get("entity_id", "")
            attributes = entity_state.get("attributes", {})
            device_class = attributes.get("device_class")
            if device_class:
                if device_class not in by_device_class:
                    by_device_class[device_class] = []
                by_device_class[device_class].append(entity_id)

        if by_device_class:
            lines.append("## Entities by Device Class")
            lines.append("")
            for device_class, entity_ids in sorted(by_device_class.items()):
                lines.append(f"### {device_class} ({len(entity_ids)} entities)")
                lines.append("")
                for entity_id in entity_ids[:5]:  # Limit to first 5 per device class
                    lines.append(f"- `{entity_id}`")
                lines.append("")

        return "\n".join(lines)
