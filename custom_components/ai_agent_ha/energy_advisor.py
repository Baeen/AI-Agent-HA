"""Energy optimization advisor for Home Assistant.

This module analyzes energy dashboard data, suggests automations
to reduce consumption, and identifies efficiency opportunities.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class EnergySummary:
    """Summary of energy usage."""

    def __init__(
        self,
        total_usage: float = 0,
        total_cost: float = 0,
        usage_by_source: Dict = None,
        usage_by_period: Dict = None,
    ):
        self.total_usage = total_usage
        self.total_cost = total_cost
        self.usage_by_source = usage_by_source or {}
        self.usage_by_period = usage_by_period or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_usage": self.total_usage,
            "total_cost": self.total_cost,
            "usage_by_source": self.usage_by_source,
            "usage_by_period": self.usage_by_period,
            "timestamp": datetime.now().isoformat(),
        }


class EnergySuggestion:
    """Suggestion for energy optimization."""

    def __init__(
        self,
        title: str,
        description: str,
        potential_savings: str = "",
        automation_config: Dict = None,
        priority: str = "medium",
        category: str = "automation",
    ):
        self.title = title
        self.description = description
        self.potential_savings = potential_savings
        self.automation_config = automation_config
        self.priority = priority
        self.category = category

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "potential_savings": self.potential_savings,
            "automation_config": self.automation_config,
            "priority": self.priority,
            "category": self.category,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [
            f"## {self.title}",
            "",
            f"**Category:** {self.category} | **Priority:** {self.priority}",
            "",
            self.description,
            "",
        ]
        if self.potential_savings:
            lines.append(f"**Potential Savings:** {self.potential_savings}")
            lines.append("")
        if self.automation_config:
            lines.append("**Suggested Automation:**")
            lines.append("```yaml")
            if isinstance(self.automation_config, dict):
                import yaml as pyyaml  # type: ignore[import-untyped]

                lines.append(pyyaml.dump(self.automation_config, default_flow_style=False))
            lines.append("```")
            lines.append("")
        return "\n".join(lines)


class DeviceEnergyAnalysis:
    """Analysis of a device's energy usage."""

    def __init__(
        self,
        entity_id: str,
        name: str,
        domain: str,
        avg_usage: float = 0,
        cost_per_period: float = 0,
        optimization_potential: str = "",
        is_automatable: bool = False,
    ):
        self.entity_id = entity_id
        self.name = name
        self.domain = domain
        self.avg_usage = avg_usage
        self.cost_per_period = cost_per_period
        self.optimization_potential = optimization_potential
        self.is_automatable = is_automatable

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "domain": self.domain,
            "avg_usage_kwh": self.avg_usage,
            "cost_per_period": self.cost_per_period,
            "optimization_potential": self.optimization_potential,
            "is_automatable": self.is_automatable,
        }


class EnergyOptimizationResult:
    """Result of energy optimization analysis."""

    def __init__(
        self,
        energy_summary: EnergySummary = None,
        suggestions: List[EnergySuggestion] = None,
        device_analysis: List[DeviceEnergyAnalysis] = None,
    ):
        self.energy_summary = energy_summary or EnergySummary()
        self.suggestions = suggestions or []
        self.device_analysis = device_analysis or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "energy_summary": self.energy_summary.to_dict(),
            "suggestions": [s.to_dict() for s in self.suggestions],
            "device_analysis": [d.to_dict() for d in self.device_analysis],
            "total_suggestions": len(self.suggestions),
            "total_devices_analyzed": len(self.device_analysis),
            "timestamp": datetime.now().isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = ["# Energy Optimization Report", ""]

        # Energy Summary
        summary = self.energy_summary
        lines.append("## Energy Usage Summary")
        lines.append("")
        lines.append(f"- **Total Usage:** {summary.total_usage:.2f} kWh")
        lines.append(f"- **Total Cost:** ${summary.total_cost:.2f}")
        lines.append("")

        if summary.usage_by_source:
            lines.append("### Usage by Source")
            for source, usage in summary.usage_by_source.items():
                lines.append(f"- {source}: {usage:.2f} kWh")
            lines.append("")

        # Suggestions
        if self.suggestions:
            lines.append("## Energy Optimization Suggestions")
            lines.append("")
            for suggestion in self.suggestions:
                lines.append(suggestion.to_markdown())

        # Device Analysis
        if self.device_analysis:
            lines.append("## Device Energy Analysis")
            lines.append("")
            lines.append(
                "| Device | Domain | Avg Usage (kWh) | Cost/Period | Automatable |"
            )
            lines.append(
                "|--------|--------|-----------------|-------------|-------------|"
            )
            for device in self.device_analysis:
                auto_str = "Yes" if device.is_automatable else "No"
                lines.append(
                    f"| {device.name} | {device.domain} | {device.avg_usage:.2f} | ${device.cost_per_period:.2f} | {auto_str} |"
                )
            lines.append("")

        lines.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        return "\n".join(lines)


class EnergyAdvisor:
    """Advises on energy optimization."""

    # Energy optimization patterns
    OPTIMIZATION_PATTERNS = [
        {
            "title": "HVAC Optimization",
            "description": "Optimize heating/cooling based on occupancy and weather",
            "priority": "high",
            "category": "hvac",
            "conditions": ["climate", "person", "weather"],
            "potential_savings": "10-30% on HVAC costs",
        },
        {
            "title": "Lighting Automation",
            "description": "Turn off lights when rooms are unoccupied",
            "priority": "medium",
            "category": "lighting",
            "conditions": ["light", "motion", "person"],
            "potential_savings": "5-15% on lighting costs",
        },
        {
            "title": "Standby Power Reduction",
            "description": "Reduce standby power by automating device shutdown",
            "priority": "medium",
            "category": "power",
            "conditions": ["switch", "plug"],
            "potential_savings": "5-10% on standby power",
        },
        {
            "title": "Water Heating Optimization",
            "description": "Optimize water heating schedule",
            "priority": "medium",
            "category": "water_heating",
            "conditions": ["water_heater", "schedule"],
            "potential_savings": "10-20% on water heating",
        },
        {
            "title": "Peak Hour Shifting",
            "description": "Shift energy usage to off-peak hours",
            "priority": "high",
            "category": "scheduling",
            "conditions": ["energy", "time"],
            "potential_savings": "10-25% on energy costs",
        },
        {
            "title": "Window-Based Climate Control",
            "description": "Turn off HVAC when windows are open",
            "priority": "high",
            "category": "hvac",
            "conditions": ["climate", "window"],
            "potential_savings": "10-20% on HVAC costs",
        },
    ]

    # Domains that are considered automatable for energy savings
    AUTOMATABLE_DOMAINS = {
        "light",
        "switch",
        "plug",
        "climate",
        "fan",
        "valve",
        "water_heater",
        "cover",
    }

    def analyze_energy_data(
        self,
        energy_entities: List[Dict],
        device_entities: List[Dict],
        time_period: str = "month",
    ) -> EnergyOptimizationResult:
        """Analyze energy data and provide optimization suggestions.

        Args:
            energy_entities: List of energy meter entities
            device_entities: List of device entities
            time_period: Time period for analysis (day, week, month)

        Returns:
            EnergyOptimizationResult with analysis
        """
        _LOGGER.debug(
            "Analyzing energy data: %d energy entities, %d device entities, period: %s",
            len(energy_entities),
            len(device_entities),
            time_period,
        )

        # Get energy summary
        energy_summary = self.get_energy_summary(energy_entities)

        # Analyze device energy usage
        device_analysis = self.analyze_device_energy(device_entities)

        # Get optimization suggestions based on available devices
        suggestions = self.get_optimization_suggestions(device_entities, energy_summary.to_dict())

        result = EnergyOptimizationResult(
            energy_summary=energy_summary,
            suggestions=suggestions,
            device_analysis=device_analysis,
        )

        _LOGGER.debug(
            "Energy analysis complete: %d suggestions, %d devices analyzed",
            len(suggestions),
            len(device_analysis),
        )

        return result

    def get_energy_summary(
        self, energy_entities: List[Dict]
    ) -> EnergySummary:
        """Get summary of energy usage from entities.

        Args:
            energy_entities: List of energy meter entities with state info

        Returns:
            EnergySummary with usage data
        """
        total_usage = 0.0
        total_cost = 0.0
        usage_by_source: Dict[str, float] = {}
        usage_by_period: Dict[str, float] = {}

        for entity in energy_entities:
            entity_id = entity.get("entity_id", "")
            state = entity.get("state")
            usage = entity.get("usage", 0)
            cost = entity.get("cost", 0)
            source_name = entity.get("source_name", entity_id)

            # Parse state value
            try:
                if state is not None:
                    current_usage = float(state)
                else:
                    current_usage = 0.0
            except (ValueError, TypeError):
                current_usage = 0.0

            # Use usage if available, otherwise state
            entity_total = usage if usage > 0 else current_usage
            total_usage += entity_total

            # Parse cost
            try:
                if cost is not None:
                    entity_cost = float(cost)
                else:
                    entity_cost = 0.0
            except (ValueError, TypeError):
                entity_cost = 0.0

            total_cost += entity_cost

            # Track by source
            if source_name:
                usage_by_source[source_name] = entity_total

            # Track by period (using available period info)
            period = entity.get("period", "unknown")
            if period:
                usage_by_period[period] = usage_by_period.get(period, 0) + entity_total

        return EnergySummary(
            total_usage=total_usage,
            total_cost=total_cost,
            usage_by_source=usage_by_source,
            usage_by_period=usage_by_period,
        )

    def analyze_device_energy(
        self, device_entities: List[Dict]
    ) -> List[DeviceEnergyAnalysis]:
        """Analyze energy usage of individual devices.

        Args:
            device_entities: List of device entities

        Returns:
            List of DeviceEnergyAnalysis objects
        """
        analyses: List[DeviceEnergyAnalysis] = []

        for device in device_entities:
            entity_id = device.get("entity_id", "")
            name = device.get("name", entity_id)
            domain = device.get("domain", "unknown")
            state = device.get("state")
            attributes = device.get("attributes", {})

            # Calculate average usage based on domain and state
            avg_usage = 0.0
            is_automatable = domain in self.AUTOMATABLE_DOMAINS

            # Parse current power usage if available
            power = attributes.get("power")
            if power is not None:
                try:
                    avg_usage = float(power)
                except (ValueError, TypeError):
                    avg_usage = 0.0
            elif state is not None:
                # Estimate based on state for on/off devices
                if state in ("on", "active", "heating", "cooling"):
                    # Use typical values based on domain
                    typical_usage = {
                        "light": 10,  # 10W average
                        "switch": 5,  # 5W standby
                        "fan": 50,  # 50W
                        "climate": 100,  # 100W when active
                        "water_heater": 200,  # 200W when active
                    }
                    avg_usage = typical_usage.get(domain, 10)

            # Calculate cost per period (assuming 30 days, $0.15/kWh)
            cost_per_period = (avg_usage * 24 * 30 / 1000) * 0.15

            # Determine optimization potential
            optimization_potential = ""
            if is_automatable and avg_usage > 0:
                if avg_usage > 100:
                    optimization_potential = "High - Device has significant standby/active consumption"
                elif avg_usage > 10:
                    optimization_potential = "Medium - Device could benefit from automation"
                else:
                    optimization_potential = "Low - Minor savings possible"

            analysis = DeviceEnergyAnalysis(
                entity_id=entity_id,
                name=name,
                domain=domain,
                avg_usage=avg_usage,
                cost_per_period=cost_per_period,
                optimization_potential=optimization_potential,
                is_automatable=is_automatable,
            )
            analyses.append(analysis)

        # Sort by cost per period (highest first)
        analyses.sort(key=lambda d: d.cost_per_period, reverse=True)

        return analyses

    def get_optimization_suggestions(
        self,
        available_devices: List[Dict],
        energy_data: Optional[Dict] = None,
    ) -> List[EnergySuggestion]:
        """Get energy optimization suggestions based on available devices.

        Args:
            available_devices: List of available device entities
            energy_data: Optional energy usage data

        Returns:
            List of EnergySuggestion objects
        """
        suggestions: List[EnergySuggestion] = []

        # Collect available domains from devices
        available_domains: set = set()
        available_entities: Dict[str, List[str]] = {}

        for device in available_devices:
            domain = device.get("domain", "")
            entity_id = device.get("entity_id", "")
            if domain:
                available_domains.add(domain)
                if domain not in available_entities:
                    available_entities[domain] = []
                available_entities[domain].append(entity_id)

        # Check each optimization pattern
        for pattern in self.OPTIMIZATION_PATTERNS:
            required_conditions = pattern.get("conditions", [])

            # Check if we have enough matching devices for this pattern
            matching_domains = set(required_conditions) & available_domains
            has_match = len(matching_domains) > 0

            # For patterns with multiple conditions, check if at least one matches
            if has_match:
                suggestion = self._create_suggestion_from_pattern(
                    pattern, available_devices, energy_data
                )
                if suggestion:
                    suggestions.append(suggestion)

        # Always add general suggestions even if no specific devices match
        if not suggestions:
            # Add general standby power reduction
            if "switch" in available_domains or "plug" in available_domains:
                general_suggestion = EnergySuggestion(
                    title="General Energy Monitoring",
                    description="Set up energy monitoring to track consumption patterns and identify waste.",
                    potential_savings="Varies based on usage",
                    priority="low",
                    category="monitoring",
                )
                suggestions.append(general_suggestion)

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 3))

        return suggestions

    def _create_suggestion_from_pattern(
        self,
        pattern: Dict,
        available_devices: List[Dict],
        energy_data: Optional[Dict] = None,
    ) -> Optional[EnergySuggestion]:
        """Create a suggestion from an optimization pattern."""
        title = pattern.get("title", "")
        description = pattern.get("description", "")
        priority = pattern.get("priority", "medium")
        category = pattern.get("category", "automation")
        potential_savings = pattern.get("potential_savings", "")
        conditions = pattern.get("conditions", [])

        # Generate automation config based on pattern
        automation_config = self._generate_automation_config(pattern, available_devices)

        suggestion = EnergySuggestion(
            title=title,
            description=description,
            potential_savings=potential_savings,
            automation_config=automation_config,
            priority=priority,
            category=category,
        )

        return suggestion

    def _generate_automation_config(
        self, pattern: Dict, available_devices: List[Dict]
    ) -> Optional[Dict]:
        """Generate automation YAML config for a pattern."""
        category = pattern.get("category", "")
        conditions = pattern.get("conditions", [])

        if category == "hvac" and "window" in conditions:
            # Window-based HVAC control
            return {
                "alias": "Turn off HVAC when windows open",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": ["binary_window_entities"],
                        "from": "off",
                        "to": "on",
                    }
                ],
                "condition": [],
                "action": [
                    {
                        "service": "climate.turn_off",
                        "target": {
                            "entity_id": "climate_entities"
                        },
                    }
                ],
                "mode": "single",
            }

        elif category == "lighting":
            # Lighting automation
            return {
                "alias": "Turn off lights when room empty",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": ["motion_sensor_entities"],
                        "from": "on",
                        "to": "off",
                    }
                ],
                "condition": [
                    {
                        "condition": "numeric_state",
                        "entity_id": ["humidity_or_temperature_entities"],
                        "above": 0,
                    }
                ],
                "action": [
                    {
                        "service": "light.turn_off",
                        "target": {
                            "area_id": "room_area_id"
                        },
                    }
                ],
                "mode": "single",
                "trigger_delay": 15,  # minutes
            }

        elif category == "power":
            # Standby power reduction
            return {
                "alias": "Reduce standby power usage",
                "trigger": [
                    {
                        "platform": "time",
                        "at": "23:00:00",  # 11 PM
                    }
                ],
                "condition": [
                    {
                        "condition": "state",
                        "entity_id": ["person_entities"],
                        "state": "not_home",
                    }
                ],
                "action": [
                    {
                        "service": "switch.turn_off",
                        "target": {
                            "entity_id": ["switch_entities"]
                        },
                    }
                ],
                "mode": "single",
            }

        elif category == "scheduling":
            # Peak hour shifting
            return {
                "alias": "Shift energy usage to off-peak",
                "trigger": [
                    {
                        "platform": "time",
                        "at": "00:00:00",  # Midnight
                    }
                ],
                "condition": [
                    {
                        "condition": "state",
                        "entity_id": "sensor.energy_price",
                        "state": "low",
                    }
                ],
                "action": [
                    {
                        "service": "input_boolean.turn_on",
                        "target": {
                            "entity_id": "boolean.off_peak_mode"
                        },
                    }
                ],
                "mode": "single",
            }

        else:
            # Generic automation template
            return {
                "alias": f"Energy optimization: {pattern.get('title', '')}",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": conditions if conditions else [],
                    }
                ],
                "condition": [],
                "action": [
                    {
                        "service": "homeassistant.turn_off",
                        "target": {},
                    }
                ],
                "mode": "single",
            }

    def suggest_automation_for_device(
        self, device: Dict
    ) -> Optional[Dict]:
        """Suggest an automation for a specific device to save energy.

        Args:
            device: Device entity information

        Returns:
            Automation configuration or None
        """
        entity_id = device.get("entity_id", "")
        domain = device.get("domain", "")
        name = device.get("name", entity_id)

        if domain not in self.AUTOMATABLE_DOMAINS:
            return None

        if domain == "light":
            return {
                "alias": f"Auto-off {name}",
                "description": f"Turn off {name} when no longer needed to save energy",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": ["binary_sensor.motion_sensor"],
                        "from": "on",
                        "to": "off",
                    }
                ],
                "condition": [
                    {
                        "condition": "state",
                        "entity_id": ["person.home"],
                        "state": "not_home",
                    }
                ],
                "action": [
                    {
                        "service": "light.turn_off",
                        "target": {"entity_id": entity_id},
                    }
                ],
                "mode": "single",
            }

        elif domain in ("switch", "plug"):
            return {
                "alias": f"Standby reduction for {name}",
                "description": f"Turn off {name} during off-peak hours to reduce standby power",
                "trigger": [
                    {
                        "platform": "time",
                        "at": "23:00:00",
                    }
                ],
                "action": [
                    {
                        "service": "switch.turn_off",
                        "target": {"entity_id": entity_id},
                    }
                ],
                "condition": [
                    {
                        "condition": "time",
                        "after": "22:00:00",
                        "before": "06:00:00",
                    }
                ],
                "mode": "single",
            }

        elif domain == "climate":
            return {
                "alias": f"Eco mode for {name}",
                "description": f"Set {name} to eco mode when away",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": ["person.home"],
                        "from": "home",
                        "to": "not_home",
                    }
                ],
                "action": [
                    {
                        "service": "climate.set_temperature",
                        "target": {"entity_id": entity_id},
                        "data": {"temperature": 22},
                    }
                ],
                "mode": "single",
            }

        elif domain == "fan":
            return {
                "alias": f"Auto-off fan: {name}",
                "description": f"Turn off {name} when room is empty",
                "trigger": [
                    {
                        "platform": "state",
                        "entity_id": ["binary_sensor.motion_sensor"],
                        "from": "on",
                        "to": "off",
                    }
                ],
                "condition": [
                    {
                        "condition": "time",
                        "after": "22:00:00",
                    }
                ],
                "action": [
                    {
                        "service": "fan.turn_off",
                        "target": {"entity_id": entity_id},
                    }
                ],
                "mode": "single",
            }

        return None

    def get_ai_prompt_for_energy_analysis(
        self, energy_summary: Dict, suggestions: List[Dict]
    ) -> str:
        """Generate an AI prompt for personalized energy analysis.

        Args:
            energy_summary: Energy usage summary data
            suggestions: List of optimization suggestions

        Returns:
            AI prompt string for personalized analysis
        """
        prompt = """You are an energy optimization expert. Please analyze the following Home Assistant energy data and provide personalized recommendations.

## Energy Usage Summary
"""
        if energy_summary:
            prompt += f"- Total Usage: {energy_summary.get('total_usage', 0):.2f} kWh\n"
            prompt += f"- Total Cost: ${energy_summary.get('total_cost', 0):.2f}\n"
            prompt += f"- Usage by Source: {energy_summary.get('usage_by_source', {})}\n"
        else:
            prompt += "No energy data available.\n"

        prompt += "\n## Optimization Suggestions\n"
        if suggestions:
            for i, suggestion in enumerate(suggestions, 1):
                prompt += f"\n### {i}. {suggestion.get('title', 'Untitled')}\n"
                prompt += f"**Priority:** {suggestion.get('priority', 'medium')}\n"
                prompt += f"**Category:** {suggestion.get('category', 'general')}\n"
                prompt += f"**Description:** {suggestion.get('description', '')}\n"
                if suggestion.get('potential_savings'):
                    prompt += f"**Potential Savings:** {suggestion.get('potential_savings')}\n"
        else:
            prompt += "No suggestions available.\n"

        prompt += """
## Your Task
Based on the data above, please provide:

1. **Top 3 Priority Actions** - What should the user address first for maximum savings?
2. **Personalized Automation Recommendations** - Specific automations tailored to this home's setup
3. **Usage Pattern Analysis** - Any unusual patterns or opportunities
4. **Implementation Steps** - How to implement the top recommendations

Please be specific and actionable, referencing the actual devices and data available."""

        return prompt
