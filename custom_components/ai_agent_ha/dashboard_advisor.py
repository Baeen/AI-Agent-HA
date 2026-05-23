"""Dashboard layout advisor for Home Assistant.

This module analyzes current dashboards, suggests improvements,
and recommends card types for data being displayed.
"""

import logging
from typing import Any, Dict, List, Optional

# For direct module execution (testing), use absolute import
try:
    from .dashboard_templates import DASHBOARD_TEMPLATES
except ImportError:
    from dashboard_templates import DASHBOARD_TEMPLATES

_LOGGER = logging.getLogger(__name__)


class DashboardAnalysis:
    """Analysis of a dashboard's layout and content."""

    def __init__(
        self,
        dashboard_url: str = "",
        dashboard_title: str = "",
        card_count: int = 0,
        views: int = 0,
        card_types: Dict = None,
        issues: List = None,
        recommendations: List = None,
    ):
        self.dashboard_url = dashboard_url
        self.dashboard_title = dashboard_title
        self.card_count = card_count
        self.views = views
        self.card_types = card_types or {}
        self.issues = issues or []
        self.recommendations = recommendations or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dashboard_url": self.dashboard_url,
            "dashboard_title": self.dashboard_title,
            "card_count": self.card_count,
            "views": self.views,
            "card_types": self.card_types,
            "issues": self.issues,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        md = f"# Dashboard Analysis: {self.dashboard_title}\n\n"
        md += f"- **URL**: `{self.dashboard_url}`\n"
        md += f"- **Total Cards**: {self.card_count}\n"
        md += f"- **Number of Views**: {self.views}\n\n"

        md += "## Card Types\n\n"
        for card_type, count in self.card_types.items():
            md += f"- `{card_type}`: {count}\n"
        md += "\n"

        if self.issues:
            md += "## Issues\n\n"
            for issue in self.issues:
                md += f"- {issue}\n"
            md += "\n"

        if self.recommendations:
            md += "## Recommendations\n\n"
            for rec in self.recommendations:
                md += f"- {rec}\n"
            md += "\n"

        return md


class CardRecommendation:
    """Recommendation for a dashboard card."""

    def __init__(
        self,
        card_type: str,
        title: str = "",
        entity_id: str = "",
        description: str = "",
        config: Dict = None,
        priority: str = "medium",
    ):
        self.card_type = card_type
        self.title = title
        self.entity_id = entity_id
        self.description = description
        self.config = config or {}
        self.priority = priority

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "card_type": self.card_type,
            "title": self.title,
            "entity_id": self.entity_id,
            "description": self.description,
            "config": self.config,
            "priority": self.priority,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        md = f"**Card Type**: `{self.card_type}`\n"
        if self.title:
            md += f"**Title**: {self.title}\n"
        if self.entity_id:
            md += f"**Entity**: `{self.entity_id}`\n"
        if self.description:
            md += f"**Description**: {self.description}\n"
        md += f"**Priority**: {self.priority}\n"
        return md


class DashboardImprovement:
    """Suggestion for dashboard improvement."""

    def __init__(
        self,
        improvement_type: str,
        description: str,
        current_state: str = "",
        suggested_change: str = "",
        priority: str = "medium",
    ):
        self.improvement_type = improvement_type
        self.description = description
        self.current_state = current_state
        self.suggested_change = suggested_change
        self.priority = priority

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "improvement_type": self.improvement_type,
            "description": self.description,
            "current_state": self.current_state,
            "suggested_change": self.suggested_change,
            "priority": self.priority,
        }


class DashboardAdvisor:
    """Advises on dashboard layout and improvements."""

    # Card type recommendations based on entity domain
    CARD_TYPE_RECOMMENDATIONS = {
        "light": {
            "default_card": "light",
            "alternative_cards": ["toggle", "slider"],
            "best_for": "Controlling lights",
        },
        "switch": {
            "default_card": "toggle",
            "alternative_cards": ["slider", "button"],
            "best_for": "Controlling switches and outlets",
        },
        "climate": {
            "default_card": "climate",
            "alternative_cards": ["custom:mushroom-climate-card"],
            "best_for": "HVAC control",
        },
        "sensor": {
            "default_card": "sensor",
            "alternative_cards": [
                "gauge",
                "statistic",
                "custom:mini-graph-card",
            ],
            "best_for": "Displaying sensor values and trends",
        },
        "binary_sensor": {
            "default_card": "binary-sensor",
            "alternative_cards": ["custom:mushroom-binary-sensor-card"],
            "best_for": "Motion detectors, door sensors, etc.",
        },
        "cover": {
            "default_card": "cover",
            "alternative_cards": ["button", "slider"],
            "best_for": "Blinds, curtains, garage doors",
        },
        "media_player": {
            "default_card": "media-control",
            "alternative_cards": ["custom:media-control-card"],
            "best_for": "TV, speakers, media devices",
        },
        "camera": {
            "default_card": "picture-entity",
            "alternative_cards": ["picture-glance"],
            "best_for": "Security cameras",
        },
        "person": {
            "default_card": "person",
            "alternative_cards": ["custom:mushroom-person-card"],
            "best_for": "Tracking people",
        },
        "lock": {
            "default_card": "lock",
            "alternative_cards": ["button", "custom:mushroom-lock-card"],
            "best_for": "Smart locks",
        },
        "vacuum": {
            "default_card": "custom:mushroom-vacuum-card",
            "alternative_cards": ["button"],
            "best_for": "Robot vacuums",
        },
        "weather": {
            "default_card": "weather-forecast",
            "alternative_cards": ["custom:weather-card"],
            "best_for": "Weather information",
        },
        "fan": {
            "default_card": "fan",
            "alternative_cards": ["slider", "button"],
            "best_for": "Controlling fans",
        },
        "input_boolean": {
            "default_card": "toggle",
            "alternative_cards": ["button"],
            "best_for": "Boolean toggles and switches",
        },
        "input_number": {
            "default_card": "slider",
            "alternative_cards": ["custom:bar-card"],
            "best_for": "Configurable numbers",
        },
        "input_select": {
            "default_card": "entity",
            "alternative_cards": ["custom:paper-buttons-row"],
            "best_for": "Dropdown selections",
        },
        "script": {
            "default_card": "button",
            "alternative_cards": ["custom:mushroom-script-card"],
            "best_for": "Running scripts",
        },
        "scene": {
            "default_card": "entity",
            "alternative_cards": ["button", "custom:paper-buttons-row"],
            "best_for": "Activating scenes",
        },
        "automation": {
            "default_card": "toggle",
            "alternative_cards": ["custom:mushroom-automation-card"],
            "best_for": "Toggling automations",
        },
        "timer": {
            "default_card": "timer",
            "alternative_cards": ["custom:timer-card"],
            "best_for": "Managing timers",
        },
        "input_datetime": {
            "default_card": "entity",
            "alternative_cards": ["button"],
            "best_for": "Date and time selection",
        },
    }

    # Dashboard layout best practices
    LAYOUT_BEST_PRACTICES = [
        {
            "check": "has_title",
            "description": "Dashboard should have a clear title",
            "severity": "info",
        },
        {
            "check": "logical_grouping",
            "description": "Group related entities together",
            "severity": "medium",
        },
        {
            "check": "avoid_overcrowding",
            "description": "Avoid too many cards in one view",
            "severity": "high",
        },
        {
            "check": "has_summary_cards",
            "description": "Include summary/metric cards at the top",
            "severity": "medium",
        },
        {
            "check": "responsive_layout",
            "description": "Use grid or masonry layout for responsiveness",
            "severity": "low",
        },
    ]

    def analyze_dashboard(
        self,
        dashboard_config: Dict[str, Any],
        available_entities: Optional[List[Dict]] = None,
    ) -> DashboardAnalysis:
        """Analyze a dashboard's layout and content.

        Args:
            dashboard_config: Dashboard configuration
            available_entities: Optional list of available entities

        Returns:
            DashboardAnalysis with findings
        """
        dashboard_url = dashboard_config.get("url_path", "")
        dashboard_title = dashboard_config.get("title", "Untitled Dashboard")

        # Count cards and card types
        card_count = 0
        card_types: Dict[str, int] = {}
        views = len(dashboard_config.get("views", []))
        issues: List[str] = []
        recommendations: List[str] = []

        # Check for title
        if not dashboard_title or dashboard_title == "Untitled Dashboard":
            issues.append("Dashboard is missing a clear title")

        # Analyze each view
        for view in dashboard_config.get("views", []):
            view_cards = view.get("cards", [])
            card_count += len(view_cards)

            # Check for overcrowding (more than 15 cards per view)
            if len(view_cards) > 15:
                issues.append(
                    f"View '{view.get('title', 'Untitled')}' has {len(view_cards)} cards - consider splitting into multiple views"
                )

            # Check for summary cards at the top
            if view_cards:
                first_card_type = view_cards[0].get("type", "")
                if first_card_type not in ["custom:template-entity-row", "custom:stack-in-card"]:
                    # Check if first card is a summary-type card
                    if first_card_type not in [
                        "sensor",
                        "gauge",
                        "statistic",
                        "custom:mini-graph-card",
                        "custom:card-tools",
                    ]:
                        recommendations.append(
                            f"View '{view.get('title', 'Untitled')}' could benefit from a summary/metric card at the top"
                        )

            # Count card types
            for card in view_cards:
                card_type = card.get("type", "unknown")
                card_types[card_type] = card_types.get(card_type, 0) + 1

        # Check for logical grouping - analyze entities in cards
        if available_entities:
            entity_domains = set()
            for card in dashboard_config.get("views", []):
                for item in card.get("cards", []):
                    for entity in item.get("entities", []):
                        if isinstance(entity, str) and "." in entity:
                            domain = entity.split(".")[0]
                            entity_domains.add(domain)
                    if "entity" in item:
                        entity = item["entity"]
                        if isinstance(entity, str) and "." in entity:
                            domain = entity.split(".")[0]
                            entity_domains.add(domain)

            # Check if related entities are grouped together
            if len(entity_domains) > 5:
                recommendations.append(
                    f"Dashboard contains entities from {len(entity_domains)} different domains - consider organizing by area or function"
                )

        # Check for responsive layout
        layout_type = dashboard_config.get("layout_type", "")
        if not layout_type:
            for view in dashboard_config.get("views", []):
                if "panel_layout" not in view and "column_count" not in view:
                    recommendations.append(
                        "Consider using a grid or masonry layout for better responsiveness"
                    )
                    break

        analysis = DashboardAnalysis(
            dashboard_url=dashboard_url,
            dashboard_title=dashboard_title,
            card_count=card_count,
            views=views,
            card_types=card_types,
            issues=issues,
            recommendations=recommendations,
        )

        _LOGGER.debug(
            "Analyzed dashboard '%s': %d cards, %d views, %d issues, %d recommendations",
            dashboard_title,
            card_count,
            views,
            len(issues),
            len(recommendations),
        )

        return analysis

    def get_card_recommendations(
        self,
        entities: List[Dict],
        current_cards: Optional[List[Dict]] = None,
    ) -> List[CardRecommendation]:
        """Get card type recommendations for entities.

        Args:
            entities: List of entities to create cards for
            current_cards: Optional list of existing cards to avoid duplicates

        Returns:
            List of CardRecommendation objects
        """
        recommendations: List[CardRecommendation] = []
        seen_entities = set()

        # Get current card entities to avoid duplicates
        current_entity_cards = set()
        if current_cards:
            for card in current_cards:
                entity = card.get("entity", "")
                if entity:
                    current_entity_cards.add(entity)
                for ent in card.get("entities", []):
                    if isinstance(ent, str) and "." in ent:
                        current_entity_cards.add(ent)

        for entity in entities:
            entity_id = entity.get("entity_id", "")
            if not entity_id or entity_id in seen_entities:
                continue

            # Skip if already has a card
            if entity_id in current_entity_cards:
                continue

            seen_entities.add(entity_id)

            # Get entity domain
            if "." in entity_id:
                domain = entity_id.split(".")[0]
            else:
                domain = "unknown"

            # Get recommendation for this domain
            if domain in self.CARD_TYPE_RECOMMENDATIONS:
                rec = self.CARD_TYPE_RECOMMENDATIONS[domain]
                state = entity.get("state", "")
                attributes = entity.get("attributes", {})

                # Build title from entity
                title = attributes.get("friendly_name", entity_id.split(".")[-1].replace("_", " ").title())

                # Build description
                description = rec["best_for"]
                if state:
                    description += f" (current state: {state})"

                # Create config suggestion
                config: Dict[str, Any] = {
                    "type": rec["default_card"],
                    "entity": entity_id,
                }

                # Add title for certain card types
                if rec["default_card"] in ["sensor", "gauge", "entity", "custom:mini-graph-card"]:
                    config["title"] = title

                # Add entity name for display cards
                if rec["default_card"] in ["light", "switch", "climate", "lock"]:
                    config["name"] = title

                card_rec = CardRecommendation(
                    card_type=rec["default_card"],
                    title=title,
                    entity_id=entity_id,
                    description=description,
                    config=config,
                    priority="high" if domain in ["light", "switch", "climate"] else "medium",
                )
                recommendations.append(card_rec)
            else:
                # Unknown domain - suggest generic entity card
                card_rec = CardRecommendation(
                    card_type="entity",
                    title=entity.get("attributes", {}).get("friendly_name", entity_id),
                    entity_id=entity_id,
                    description=f"Generic card for {domain} entity",
                    config={"type": "entity", "entity": entity_id},
                    priority="low",
                )
                recommendations.append(card_rec)

        return recommendations

    def get_improvement_suggestions(
        self,
        dashboard_config: Dict[str, Any],
        analysis: DashboardAnalysis,
    ) -> List[DashboardImprovement]:
        """Get improvement suggestions for a dashboard.

        Args:
            dashboard_config: Dashboard configuration
            analysis: Previous dashboard analysis

        Returns:
            List of DashboardImprovement objects
        """
        improvements: List[DashboardImprovement] = []

        # Check for title
        if not dashboard_config.get("title"):
            improvements.append(
                DashboardImprovement(
                    improvement_type="title",
                    description="Add a clear, descriptive title to the dashboard",
                    current_state="Dashboard has no title",
                    suggested_change="Add a 'title' field with a descriptive name",
                    priority="info",
                )
            )

        # Check for overcrowding
        for view in dashboard_config.get("views", []):
            view_cards = view.get("cards", [])
            if len(view_cards) > 15:
                improvements.append(
                    DashboardImprovement(
                        improvement_type="layout",
                        description=f"View '{view.get('title', 'Untitled')}' is overcrowded with {len(view_cards)} cards",
                        current_state=f"View has {len(view_cards)} cards",
                        suggested_change="Split into multiple views or use collapsible sections",
                        priority="high",
                    )
                )
            elif len(view_cards) > 10:
                improvements.append(
                    DashboardImprovement(
                        improvement_type="layout",
                        description=f"View '{view.get('title', 'Untitled')}' has many cards ({len(view_cards)})" ,
                        current_state=f"View has {len(view_cards)} cards",
                        suggested_change="Consider organizing into sub-sections or multiple views",
                        priority="medium",
                    )
                )

        # Check for missing summary cards
        for view in dashboard_config.get("views", []):
            view_cards = view.get("cards", [])
            if view_cards:
                first_card = view_cards[0]
                first_type = first_card.get("type", "")
                if first_type not in ["sensor", "gauge", "statistic", "custom:mini-graph-card"]:
                    improvements.append(
                        DashboardImprovement(
                            improvement_type="summary",
                            description=f"View '{view.get('title', 'Untitled')}' could benefit from a summary card at the top",
                            current_state=f"First card is '{first_type}'",
                            suggested_change="Add a sensor, gauge, or statistic card at the top for quick overview",
                            priority="medium",
                        )
                    )

        # Check for responsive layout
        has_responsive_layout = False
        for view in dashboard_config.get("views", []):
            if "panel_layout" in view or "column_count" in view:
                has_responsive_layout = True
                break

        if not has_responsive_layout and dashboard_config.get("views"):
            improvements.append(
                DashboardImprovement(
                    improvement_type="responsive",
                    description="Dashboard could benefit from responsive layout",
                    current_state="Using default layout",
                    suggested_change="Add 'panel_layout' or 'column_count' to views for better responsiveness",
                    priority="low",
                )
            )

        # Check for icon configuration
        if not dashboard_config.get("icon"):
            improvements.append(
                DashboardImprovement(
                    improvement_type="icon",
                    description="Dashboard could benefit from an icon",
                    current_state="No icon configured",
                    suggested_change="Add an 'icon' field with a Material Design Icon (e.g., 'mdi:home')",
                    priority="low",
                )
            )

        # Check sidebar visibility
        if dashboard_config.get("show_in_sidebar") is False:
            improvements.append(
                DashboardImprovement(
                    improvement_type="visibility",
                    description="Dashboard is not shown in sidebar",
                    current_state="show_in_sidebar is false",
                    suggested_change="Consider setting show_in_sidebar to true for easy access",
                    priority="info",
                )
            )

        return improvements

    def suggest_dashboard_layout(
        self,
        entities: List[Dict],
        dashboard_type: str = "general",
    ) -> Dict[str, Any]:
        """Suggest a complete dashboard layout.

        Args:
            entities: List of entities to display
            dashboard_type: Type of dashboard (general, energy, security, climate, etc.)

        Returns:
            Dashboard configuration dictionary
        """
        # Get template if available
        if dashboard_type in DASHBOARD_TEMPLATES:
            template = DASHBOARD_TEMPLATES[dashboard_type].copy()
            return self._populate_template(template, entities)

        # Generate a general layout
        return self._generate_general_layout(entities)

    def _populate_template(
        self,
        template: Dict[str, Any],
        entities: List[Dict],
    ) -> Dict[str, Any]:
        """Populate a template with actual entities."""
        import copy

        result = copy.deepcopy(template)

        # Group entities by domain and area
        entities_by_domain: Dict[str, List[Dict]] = {}
        entities_by_area: Dict[str, List[Dict]] = {}

        for entity in entities:
            entity_id = entity.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
            area = entity.get("attributes", {}).get("area_id", "unassigned")

            if domain not in entities_by_domain:
                entities_by_domain[domain] = []
            entities_by_domain[domain].append(entity)

            if area not in entities_by_area:
                entities_by_area[area] = []
            entities_by_area[area].append(entity)

        # Populate view entities
        for view in result.get("views", []):
            for card in view.get("cards", []):
                for i, entity_ref in enumerate(card.get("entities", [])):
                    if isinstance(entity_ref, dict) and entity_ref.get("type") == "template":
                        # Template entity - replace with actual entities
                        domain = entity_ref.get("domain", "unknown")
                        card["entities"] = [
                            e["entity_id"]
                            for e in entities_by_domain.get(domain, [])[:10]
                        ]
                    elif isinstance(entity_ref, str) and entity_ref.startswith("[]"):
                        # Placeholder - replace with entities
                        domain = entity_ref.strip("[]")
                        card["entities"] = [
                            e["entity_id"]
                            for e in entities_by_domain.get(domain, [])[:10]
                        ]
                    elif entity_ref == "":
                        # Empty placeholder - find matching entity
                        domain = entity_ref.split(".")[0] if "." in entity_ref else "unknown"
                        domain_from_ref = card.get("domain", domain)
                        matching = entities_by_domain.get(domain_from_ref, [])
                        if matching:
                            card["entity"] = matching[0]["entity_id"]
                            card.pop("domain", None)

        return result

    def _generate_general_layout(
        self,
        entities: List[Dict],
    ) -> Dict[str, Any]:
        """Generate a general-purpose dashboard layout."""
        # Group entities by domain
        entities_by_domain: Dict[str, List[Dict]] = {}
        for entity in entities:
            entity_id = entity.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
            if domain not in entities_by_domain:
                entities_by_domain[domain] = []
            entities_by_domain[domain].append(entity)

        # Create views by domain
        views = []
        current_view_entities: List[Dict] = []
        current_domain = ""

        for domain, domain_entities in entities_by_domain.items():
            if domain != current_domain and current_view_entities:
                # Save previous view
                views.append(
                    {
                        "title": f"{current_domain.title()} ({len(current_view_entities)} entities)",
                        "cards": [
                            {
                                "type": "entities",
                                "title": f"{current_domain.title()}",
                                "entities": [e["entity_id"] for e in current_view_entities[:15]],
                            }
                        ],
                    }
                )
                current_view_entities = []
                current_domain = domain

            current_view_entities.extend(domain_entities)

        # Add last view
        if current_view_entities:
            views.append(
                {
                    "title": f"{current_domain.title()} ({len(current_view_entities)} entities)",
                    "cards": [
                        {
                            "type": "entities",
                            "title": f"{current_domain.title()}",
                            "entities": [e["entity_id"] for e in current_view_entities[:15]],
                        }
                    ],
                }
            )

        # If we have too many views, combine them
        if len(views) > 5:
            views = [
                {
                    "title": "All Entities",
                    "cards": [
                        {
                            "type": "entities",
                            "title": f"{domain.title()}",
                            "entities": [e["entity_id"] for e in domain_entities[:10]],
                        }
                        for domain, domain_entities in entities_by_domain.items()
                    ],
                }
            ]

        return {
            "title": "My Dashboard",
            "url_path": "my-dashboard",
            "icon": "mdi:home",
            "show_in_sidebar": True,
            "views": views,
        }

    def get_dashboard_template(
        self,
        dashboard_type: str,
        entities: List[Dict],
    ) -> Dict[str, Any]:
        """Get a pre-built dashboard template.

        Args:
            dashboard_type: Type of dashboard
            entities: Available entities

        Returns:
            Dashboard configuration template
        """
        # Common dashboard types with custom templates
        custom_templates = {
            "energy": self._energy_dashboard_template,
            "security": self._security_dashboard_template,
            "room": self._room_dashboard_template,
            "climate": self._climate_dashboard_template,
            "automation": self._automation_dashboard_template,
            "media": self._media_dashboard_template,
        }

        if dashboard_type in custom_templates:
            return custom_templates[dashboard_type](entities)

        # Fall back to generic templates
        if dashboard_type in DASHBOARD_TEMPLATES:
            return self._populate_template(DASHBOARD_TEMPLATES[dashboard_type].copy(), entities)

        # Return a generic template
        return self._generate_general_layout(entities)

    def _energy_dashboard_template(self, entities: List[Dict]) -> Dict[str, Any]:
        """Create an energy monitoring dashboard template."""
        # Find energy-related entities
        energy_entities = [
            e for e in entities
            if e.get("entity_id", "").startswith(("sensor.energy", "sensor.power", "sensor.usage"))
            or "energy" in e.get("entity_id", "").lower()
            or "power" in e.get("entity_id", "").lower()
        ]

        return {
            "title": "Energy Monitor",
            "url_path": "energy",
            "icon": "mdi:lightning-bolt",
            "show_in_sidebar": True,
            "views": [
                {
                    "title": "Energy Overview",
                    "cards": [
                        {
                            "type": "energy-date-selection",
                        },
                        {
                            "type": "energy-distribution",
                            "energy_panel": True,
                        },
                        {
                            "type": "energy-consumption-graph",
                            "energy_panel": True,
                        },
                    ]
                    + [
                        {
                            "type": "sensor",
                            "entity": e["entity_id"],
                            "name": e.get("attributes", {}).get("friendly_name", e["entity_id"].split(".")[-1]),
                        }
                        for e in energy_entities[:5]
                    ],
                },
                {
                    "title": "Detailed Metrics",
                    "cards": [
                        {
                            "type": "entities",
                            "title": "Energy Sensors",
                            "entities": [e["entity_id"] for e in energy_entities[:15]],
                        }
                    ],
                },
            ],
        }

    def _security_dashboard_template(self, entities: List[Dict]) -> Dict[str, Any]:
        """Create a security dashboard template."""
        # Find security-related entities
        camera_entities = [e for e in entities if e.get("entity_id", "").startswith("camera.")]
        binary_sensor_entities = [
            e for e in entities
            if e.get("entity_id", "").startswith(("binary_sensor.motion", "binary_sensor.door", "binary_sensor.window", "binary_sensor.contact"))
        ]
        lock_entities = [e for e in entities if e.get("entity_id", "").startswith("lock.")]
        alarm_entities = [e for e in entities if e.get("entity_id", "").startswith("alarm_control_panel.")]

        return {
            "title": "Security Center",
            "url_path": "security",
            "icon": "mdi:shield-account",
            "show_in_sidebar": True,
            "views": [
                {
                    "title": "Security Overview",
                    "cards": [
                        {
                            "type": "custom:stack-in-card",
                            "cards": [
                                {
                                    "type": "entities",
                                    "title": "Alarm System",
                                    "entities": alarm_entities[:1],
                                }
                            ]
                            if alarm_entities
                            else [],
                        },
                        {
                            "type": "entities",
                            "title": "Motion Sensors",
                            "entities": [e["entity_id"] for e in binary_sensor_entities if "motion" in e["entity_id"]][:10],
                        },
                        {
                            "type": "entities",
                            "title": "Door/Window Sensors",
                            "entities": [e["entity_id"] for e in binary_sensor_entities if "motion" not in e["entity_id"]][:10],
                        },
                        {
                            "type": "entities",
                            "title": "Smart Locks",
                            "entities": [e["entity_id"] for e in lock_entities][:10],
                        },
                    ]
                    + [
                        {
                            "type": "picture-entity",
                            "entity": e["entity_id"],
                            "camera_view": "live",
                            "name": e.get("attributes", {}).get("friendly_name", e["entity_id"].split(".")[-1]),
                        }
                        for e in camera_entities[:4]
                    ],
                },
                {
                    "title": "Camera Feeds",
                    "cards": [
                        {
                            "type": "picture-entity",
                            "entity": e["entity_id"],
                            "camera_view": "live",
                            "name": e.get("attributes", {}).get("friendly_name", e["entity_id"].split(".")[-1]),
                        }
                        for e in camera_entities
                    ],
                },
            ],
        }

    def _room_dashboard_template(self, entities: List[Dict]) -> Dict[str, Any]:
        """Create a room-based dashboard template."""
        # Group entities by area
        entities_by_area: Dict[str, List[Dict]] = {}
        for entity in entities:
            area = entity.get("attributes", {}).get("area_id", "unassigned")
            if area not in entities_by_area:
                entities_by_area[area] = []
            entities_by_area[area].append(entity)

        views = []
        for area, area_entities in entities_by_area.items():
            # Group by domain within area
            domains: Dict[str, List[Dict]] = {}
            for entity in area_entities:
                domain = entity.get("entity_id", "").split(".")[0]
                if domain not in domains:
                    domains[domain] = []
                domains[domain].append(entity)

            cards = []
            for domain, domain_entities in domains.items():
                if domain in ("light", "switch", "script"):
                    cards.append(
                        {
                            "type": "entities",
                            "title": domain.title(),
                            "entities": [e["entity_id"] for e in domain_entities[:10]],
                        }
                    )
                elif domain == "sensor":
                    cards.append(
                        {
                            "type": "entities",
                            "title": "Sensors",
                            "entities": [e["entity_id"] for e in domain_entities[:10]],
                        }
                    )
                elif domain == "binary_sensor":
                    cards.append(
                        {
                            "type": "entities",
                            "title": "Security Sensors",
                            "entities": [e["entity_id"] for e in domain_entities[:10]],
                        }
                    )

            if cards:
                views.append(
                    {
                        "title": area.replace("_", " ").title(),
                        "cards": cards,
                    }
                )

        return {
            "title": "Rooms",
            "url_path": "rooms",
            "icon": "mdi:home",
            "show_in_sidebar": True,
            "views": views,
        }

    def _climate_dashboard_template(self, entities: List[Dict]) -> Dict[str, Any]:
        """Create a climate control dashboard template."""
        # Find climate-related entities
        climate_entities = [e for e in entities if e.get("entity_id", "").startswith("climate.")]
        temperature_entities = [
            e for e in entities
            if e.get("entity_id", "").startswith("sensor.temperature")
            or "temperature" in e.get("entity_id", "").lower()
        ]
        humidity_entities = [
            e for e in entities
            if e.get("entity_id", "").startswith("sensor.humidity")
            or "humidity" in e.get("entity_id", "").lower()
        ]
        fan_entities = [e for e in entities if e.get("entity_id", "").startswith("fan.")]

        return {
            "title": "Climate Control",
            "url_path": "climate",
            "icon": "mdi:thermometer",
            "show_in_sidebar": True,
            "views": [
                {
                    "title": "Temperature & Humidity",
                    "cards": [
                        {
                            "type": "entities",
                            "title": "Thermostats",
                            "entities": [e["entity_id"] for e in climate_entities[:5]],
                        },
                        {
                            "type": "history-graph",
                            "title": "Temperature History",
                            "entities": [e["entity_id"] for e in temperature_entities[:6]],
                            "hours_to_show": 24,
                        },
                        {
                            "type": "entities",
                            "title": "Temperature Sensors",
                            "entities": [e["entity_id"] for e in temperature_entities[:10]],
                        },
                        {
                            "type": "history-graph",
                            "title": "Humidity History",
                            "entities": [e["entity_id"] for e in humidity_entities[:6]],
                            "hours_to_show": 24,
                        },
                        {
                            "type": "entities",
                            "title": "Humidity Sensors",
                            "entities": [e["entity_id"] for e in humidity_entities[:10]],
                        },
                        {
                            "type": "entities",
                            "title": "Fans",
                            "entities": [e["entity_id"] for e in fan_entities[:10]],
                        },
                    ],
                },
            ],
        }

    def _automation_dashboard_template(self, entities: List[Dict]) -> Dict[str, Any]:
        """Create an automation management dashboard template."""
        # Find automation-related entities
        automation_entities = [e for e in entities if e.get("entity_id", "").startswith("automation.")]
        script_entities = [e for e in entities if e.get("entity_id", "").startswith("script.")]
        input_boolean_entities = [e for e in entities if e.get("entity_id", "").startswith("input_boolean.")]

        return {
            "title": "Automations",
            "url_path": "automations",
            "icon": "mdi:robot",
            "show_in_sidebar": True,
            "views": [
                {
                    "title": "Automation Control",
                    "cards": [
                        {
                            "type": "entities",
                            "title": "Automations",
                            "entities": [e["entity_id"] for e in automation_entities[:15]],
                        },
                        {
                            "type": "entities",
                            "title": "Scripts",
                            "entities": [e["entity_id"] for e in script_entities[:15]],
                        },
                        {
                            "type": "entities",
                            "title": "Boolean Toggles",
                            "entities": [e["entity_id"] for e in input_boolean_entities[:15]],
                        },
                    ],
                },
            ],
        }

    def _media_dashboard_template(self, entities: List[Dict]) -> Dict[str, Any]:
        """Create a media center dashboard template."""
        # Find media-related entities
        media_entities = [e for e in entities if e.get("entity_id", "").startswith("media_player.")]
        fan_entities = [e for e in entities if e.get("entity_id", "").startswith("fan.")]

        return {
            "title": "Media Center",
            "url_path": "media",
            "icon": "mdi:television",
            "show_in_sidebar": True,
            "views": [
                {
                    "title": "Media Control",
                    "cards": [
                        {
                            "type": "entities",
                            "title": "Media Players",
                            "entities": [e["entity_id"] for e in media_entities[:10]],
                        },
                        {
                            "type": "entities",
                            "title": "Fans",
                            "entities": [e["entity_id"] for e in fan_entities[:10]],
                        },
                    ],
                },
            ],
        }

    def get_ai_dashboard_review(self, dashboard_config: Dict, entity_list: List[Dict]) -> str:
        """Generate an AI prompt for comprehensive dashboard review.

        Args:
            dashboard_config: Dashboard configuration to review
            entity_list: List of available entities

        Returns:
            Prompt string for AI review
        """
        # Analyze the dashboard
        analysis = self.analyze_dashboard(dashboard_config, entity_list)
        improvements = self.get_improvement_suggestions(dashboard_config, analysis)

        # Build prompt
        prompt = """You are a Home Assistant dashboard layout expert. Please review the following dashboard configuration and provide comprehensive feedback.

## Dashboard Overview
- Title: {title}
- URL: {url}
- Total Cards: {card_count}
- Views: {views}

## Card Type Distribution
{card_types}

## Current Issues
{issues}

## Improvement Suggestions
{improvements}

## Available Entities
{entity_count} entities are available in Home Assistant.

## Your Task
1. Evaluate the overall layout and organization
2. Suggest specific card type improvements for better UX
3. Recommend any missing cards or features
4. Provide tips for responsive design
5. Suggest any custom cards that would enhance the dashboard

Please provide your review in a structured format with clear, actionable recommendations."""

        prompt = prompt.format(
            title=dashboard_config.get("title", "Untitled"),
            url=dashboard_config.get("url_path", ""),
            card_count=analysis.card_count,
            views=analysis.views,
            card_types="\n".join(f"- {card_type}: {count}" for card_type, count in analysis.card_types.items()),
            issues="\n".join(f"- {issue}" for issue in analysis.issues) if analysis.issues else "- No issues detected",
            improvements="\n".join(f"- [{imp.priority}] {imp.description}: {imp.suggested_change}" for imp in improvements) if improvements else "- No improvements needed",
            entity_count=len(entity_list),
        )

        return prompt
