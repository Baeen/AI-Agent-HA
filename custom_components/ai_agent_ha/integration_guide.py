"""Integration setup guide for Home Assistant.

This module provides step-by-step setup guides for integrations,
generates configuration snippets, and creates initial automations.
"""

import logging
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class IntegrationInfo:
    """Information about an integration."""

    def __init__(
        self,
        domain: str = "",
        name: str = "",
        description: str = "",
        setup_required: bool = True,
        config_flow: bool = True,
        documentation_url: str = "",
    ):
        self.domain = domain
        self.name = name
        self.description = description
        self.setup_required = setup_required
        self.config_flow = config_flow
        self.documentation_url = documentation_url

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "domain": self.domain,
            "name": self.name,
            "description": self.description,
            "setup_required": self.setup_required,
            "config_flow": self.config_flow,
            "documentation_url": self.documentation_url,
        }


class SetupStep:
    """A step in the setup process."""

    def __init__(
        self,
        step_number: int,
        title: str,
        description: str = "",
        code_snippet: str = "",
        required: bool = True,
    ):
        self.step_number = step_number
        self.title = title
        self.description = description
        self.code_snippet = code_snippet
        self.required = required

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_number": self.step_number,
            "title": self.title,
            "description": self.description,
            "code_snippet": self.code_snippet,
            "required": self.required,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = []
        prefix = "" if self.required else "[OPTIONAL] "
        lines.append(f"### Step {self.step_number}: {self.title}")
        lines.append("")
        if self.description:
            lines.append(self.description)
            lines.append("")
        if self.code_snippet:
            lines.append("```yaml")
            lines.append(self.code_snippet)
            lines.append("```")
            lines.append("")
        return "\n".join(lines)


class IntegrationGuide:
    """Complete setup guide for an integration."""

    def __init__(
        self,
        integration: IntegrationInfo = None,
        steps: List[SetupStep] = None,
        config_snippets: Dict = None,
        initial_automations: List[Dict] = None,
        tips: List[str] = None,
    ):
        self.integration = integration or IntegrationInfo()
        self.steps = steps or []
        self.config_snippets = config_snippets or {}
        self.initial_automations = initial_automations or []
        self.tips = tips or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "integration": self.integration.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
            "config_snippets": self.config_snippets,
            "initial_automations": self.initial_automations,
            "tips": self.tips,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = []

        # Header
        lines.append(f"# Setup Guide: {self.integration.name}")
        lines.append("")
        lines.append(f"**Domain:** `{self.integration.domain}`")
        lines.append("")
        if self.integration.description:
            lines.append(self.integration.description)
            lines.append("")
        if self.integration.documentation_url:
            lines.append(
                f"[Official Documentation]({self.integration.documentation_url})"
            )
            lines.append("")

        # Setup Steps
        if self.steps:
            lines.append("## Setup Steps")
            lines.append("")
            for step in self.steps:
                lines.append(step.to_markdown())

        # Configuration Snippets
        if self.config_snippets:
            lines.append("## Configuration Snippets")
            lines.append("")
            for name, snippet in self.config_snippets.items():
                lines.append(f"### {name}")
                lines.append("")
                lines.append("```yaml")
                lines.append(snippet)
                lines.append("```")
                lines.append("")

        # Initial Automations
        if self.initial_automations:
            lines.append("## Suggested Initial Automations")
            lines.append("")
            for i, automation in enumerate(self.initial_automations, 1):
                lines.append(f"### Automation {i}: {automation.get('alias', 'Unnamed')}")
                lines.append("")
                if automation.get("description"):
                    lines.append(automation["description"])
                    lines.append("")
                lines.append("```yaml")
                lines.append(f"alias: {automation.get('alias', '')}")
                lines.append(f"description: {automation.get('description', '')}")
                lines.append("trigger:")
                for trigger in automation.get("trigger", []):
                    lines.append(f"  - {self._dict_to_yaml(trigger, indent=4)}")
                lines.append("action:")
                for action in automation.get("action", []):
                    lines.append(f"  - {self._dict_to_yaml(action, indent=4)}")
                lines.append("condition:")
                for condition in automation.get("condition", []):
                    lines.append(f"  - {self._dict_to_yaml(condition, indent=4)}")
                lines.append("```")
                lines.append("")

        # Tips
        if self.tips:
            lines.append("## Setup Tips")
            lines.append("")
            for tip in self.tips:
                lines.append(f"- {tip}")
            lines.append("")

        return "\n".join(lines)

    def _dict_to_yaml(self, data: Dict, indent: int = 0) -> str:
        """Convert a dictionary to YAML-like string for display."""
        prefix = " " * indent
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._dict_to_yaml(value, indent + 2))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{prefix}  -")
                        lines.append(self._dict_to_yaml(item, indent + 4))
                    else:
                        lines.append(f"{prefix}  - {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)


class IntegrationGuideProvider:
    """Provides integration setup guides."""

    # Integration database
    INTEGRATION_DATABASE = {
        "zha": IntegrationInfo(
            domain="zha",
            name="Zigbee Home Automation (ZHA)",
            description="Set up Zigbee devices using Home Assistant's built-in ZHA integration",
            setup_required=True,
            config_flow=True,
            documentation_url="https://www.home-assistant.io/integrations/zha/",
        ),
        "deconz": IntegrationInfo(
            domain="deconz",
            name="deCONZ",
            description="Set up deCONZ (ConBee/RaspBee) for Zigbee devices",
            setup_required=True,
            config_flow=True,
            documentation_url="https://www.home-assistant.io/integrations/deconz/",
        ),
        "mqtt": IntegrationInfo(
            domain="mqtt",
            name="MQTT",
            description="Set up MQTT broker and devices",
            setup_required=True,
            config_flow=False,
            documentation_url="https://www.home-assistant.io/integrations/mqtt/",
        ),
        "bluetooth": IntegrationInfo(
            domain="bluetooth",
            name="Bluetooth",
            description="Set up Bluetooth devices and sensors",
            setup_required=False,
            config_flow=True,
            documentation_url="https://www.home-assistant.io/integrations/bluetooth/",
        ),
        "tuya": IntegrationInfo(
            domain="tuya",
            name="Tuya",
            description="Set up Tuya smart home devices",
            setup_required=True,
            config_flow=True,
            documentation_url="https://www.home-assistant.io/integrations/tuya/",
        ),
        "xiaomi_miio": IntegrationInfo(
            domain="xiaomi_miio",
            name="Xiaomi Miio",
            description="Set up Xiaomi and Mi smart home devices",
            setup_required=True,
            config_flow=True,
            documentation_url="https://www.home-assistant.io/integrations/xiaomi_miio/",
        ),
        "nanoleaf": IntegrationInfo(
            domain="nanoleaf",
            name="Nanoleaf",
            description="Set up Nanoleaf light panels",
            setup_required=True,
            config_flow=True,
            documentation_url="https://www.home-assistant.io/integrations/nanoleaf/",
        ),
        "cast": IntegrationInfo(
            domain="cast",
            name="Google Cast",
            description="Set up Google Cast devices (Chromecast, Nest Hub, etc.)",
            setup_required=False,
            config_flow=True,
            documentation_url="https://www.home-assistant.io/integrations/cast/",
        ),
        "webostv": IntegrationInfo(
            domain="webostv",
            name="LG webOS TV",
            description="Set up LG Smart TV integration",
            setup_required=True,
            config_flow=True,
            documentation_url="https://www.home-assistant.io/integrations/webostv/",
        ),
        "spotify": IntegrationInfo(
            domain="spotify",
            name="Spotify",
            description="Set up Spotify media integration",
            setup_required=True,
            config_flow=True,
            documentation_url="https://www.home-assistant.io/integrations/spotify/",
        ),
    }

    # Configuration snippets for common integrations
    CONFIG_SNIPPETS = {
        "mqtt": """# MQTT Broker Configuration
mqtt:
  broker: 192.168.1.100
  port: 1883
  username: your_username
  password: your_password
  discovery: true
  discovery_prefix: homeassistant
""",
        "zha": """# ZHA Configuration (usually done via UI)
# No YAML configuration needed for basic setup
# Just provide the serial port path in the UI
# Example for USB dongle:
# serial:
#   port: /dev/ttyUSB0
""",
        "template": """# Template Sensor Example
template:
  - sensor:
      - name: "Indoor Temperature"
        unit_of_measurement: "°C"
        state: "{{ states('sensor.indoor_temp') }}"

# Template Binary Sensor Example
template:
  - binary_sensor:
      - name: "Front Door"
        device_class: door
        state: "{{ is_state('sensor.front_door_sensor', 'open') }}"
""",
        "rest_command": """# REST Command Example
rest_command:
  turn_on_light:
    url: http://192.168.1.50/light/on
    method: POST
""",
    }

    # Initial automation templates for common integrations
    INITIAL_AUTOMATION_TEMPLATES = {
        "mqtt": [
            {
                "alias": "MQTT Device Online Notification",
                "description": "Notify when an MQTT device comes online",
                "trigger": {
                    "platform": "event",
                    "event_type": "mqtt_topic_published",
                    "event_data": {
                        "topic": "homeassistant/status",
                    },
                },
                "action": [
                    {
                        "service": "notify.persistent_notification",
                        "data": {
                            "message": "An MQTT device has come online",
                        },
                    }
                ],
                "condition": [],
            }
        ],
        "zha": [
            {
                "alias": "ZHA Device Battery Low",
                "description": "Alert when a ZHA device battery is low",
                "trigger": [
                    {
                        "platform": "device",
                        "domain": "sensor",
                        "device_id": "",
                        "entity_id": "",
                        "type": "low_battery",
                    }
                ],
                "action": [
                    {
                        "service": "notify.persistent_notification",
                        "data": {
                            "message": "Battery low on {{ device_name }}",
                            "title": "Low Battery Alert",
                        },
                    }
                ],
            }
        ],
        "bluetooth": [
            {
                "alias": "Bluetooth Device Nearby",
                "description": "Trigger when a specific Bluetooth device is nearby",
                "trigger": [
                    {
                        "platform": "device",
                        "domain": "device_tracker",
                        "device_id": "",
                        "entity_id": "",
                        "type": "entered",
                    }
                ],
                "action": [
                    {
                        "service": "light.turn_on",
                        "target": {
                            "entity_id": "light.entryway",
                        },
                        "data": {
                            "brightness": 255,
                        },
                    }
                ],
            }
        ],
    }

    # Setup tips for common integrations
    SETUP_TIPS = {
        "zha": [
            "Use a quality Zigbee dongle (Sonoff ZBDongle or SkyConnect recommended)",
            "Place the dongle in a USB extension cable to avoid interference",
            "Start with a few devices and add them gradually",
            "Consider using Zigbee2MQTT for more advanced features",
        ],
        "mqtt": [
            "Use a dedicated MQTT broker (Mosquitto add-on recommended)",
            "Set up username and password for security",
            "Enable discovery for automatic entity creation",
            "Use meaningful topic names for better organization",
        ],
        "tuya": [
            "Ensure devices are in pairing mode before adding",
            "Use the correct region in Tuya settings",
            "Some devices may require cloud connection for full functionality",
            "Consider local control options for critical devices",
        ],
    }

    def get_integration_info(self, domain: str) -> Optional[IntegrationInfo]:
        """Get information about an integration.

        Args:
            domain: Integration domain

        Returns:
            IntegrationInfo or None if not found
        """
        integration = self.INTEGRATION_DATABASE.get(domain)
        if integration:
            _LOGGER.debug("Found integration info for domain: %s", domain)
            return integration
        _LOGGER.debug("No integration info found for domain: %s", domain)
        return None

    def get_setup_guide(
        self,
        domain: str,
        custom_config: Optional[Dict] = None,
    ) -> IntegrationGuide:
        """Get a complete setup guide for an integration.

        Args:
            domain: Integration domain
            custom_config: Optional custom configuration values

        Returns:
            IntegrationGuide with setup steps
        """
        integration = self.get_integration_info(domain)
        if not integration:
            _LOGGER.warning("No integration found for domain: %s", domain)
            integration = IntegrationInfo(
                domain=domain,
                name=domain,
                description=f"Setup guide for {domain} integration",
            )

        steps = self.get_setup_steps(domain)
        config_snippet = self.get_config_snippet(domain, custom_config)
        if config_snippet:
            config_snippets = {"default": config_snippet}
        else:
            config_snippets = {}

        initial_automations = self.get_initial_automations(domain)
        tips = self.get_setup_tips(domain)

        guide = IntegrationGuide(
            integration=integration,
            steps=steps,
            config_snippets=config_snippets,
            initial_automations=initial_automations,
            tips=tips,
        )

        _LOGGER.debug("Generated setup guide for domain: %s", domain)
        return guide

    def get_setup_steps(self, domain: str) -> List[SetupStep]:
        """Get step-by-step setup instructions.

        Args:
            domain: Integration domain

        Returns:
            List of SetupStep objects
        """
        steps = []
        step_number = 1

        integration = self.INTEGRATION_DATABASE.get(domain)

        if not integration:
            _LOGGER.debug("No setup steps for unknown domain: %s", domain)
            return [
                SetupStep(
                    step_number=step_number,
                    title="Search for Integration",
                    description=f"Go to **Settings > Devices & Services** in Home Assistant and search for `{domain}` in the integration list.",
                )
            ]

        # Step 1: Check prerequisites
        if integration.setup_required:
            steps.append(
                SetupStep(
                    step_number=step_number,
                    title="Check Prerequisites",
                    description=f"Before setting up {integration.name}, ensure you have:\n- A compatible device or hardware\n- Network access to the device\n- Any required accounts or subscriptions",
                )
            )
            step_number += 1

        # Step 2: Add integration
        if integration.config_flow:
            steps.append(
                SetupStep(
                    step_number=step_number,
                    title="Add Integration via UI",
                    description=f"Go to **Settings > Devices & Services**, click **Add Integration**, and search for **{integration.name}**.",
                    code_snippet="",
                )
            )
            step_number += 1
        else:
            steps.append(
                SetupStep(
                    step_number=step_number,
                    title="Add YAML Configuration",
                    description=f"Add the following configuration to your `configuration.yaml` file:",
                    code_snippet=self.get_config_snippet(domain),
                )
            )
            step_number += 1

        # Step 3: Configure device
        steps.append(
            SetupStep(
                step_number=step_number,
                title="Configure Your Device",
                description=f"Follow the on-screen instructions to connect your {integration.name} device. This may involve:\n- Entering network credentials\n- Scanning QR codes\n- Pressing pairing buttons on your device",
            )
        )
        step_number += 1

        # Step 4: Verify setup
        steps.append(
            SetupStep(
                step_number=step_number,
                title="Verify Setup",
                description="After setup is complete:\n- Check that devices appear in the Home Assistant UI\n- Test that devices are responding correctly\n- Review the [documentation]({}) for advanced configuration".format(
                    integration.documentation_url
                ),
            )
        )

        _LOGGER.debug("Generated %d setup steps for domain: %s", len(steps), domain)
        return steps

    def get_config_snippet(
        self, domain: str, custom_values: Dict = None
    ) -> str:
        """Get configuration snippet for an integration.

        Args:
            domain: Integration domain
            custom_values: Optional custom values to replace defaults

        Returns:
            Configuration YAML string
        """
        snippet = self.CONFIG_SNIPPETS.get(domain)

        if not snippet:
            _LOGGER.debug("No config snippet for domain: %s", domain)
            return f"# No YAML configuration needed for {domain}. Set up via UI or check documentation."

        if custom_values:
            for key, value in custom_values.items():
                placeholder = str(value).split(":")[0] if ":" in str(value) else str(value)
                snippet = snippet.replace(placeholder, str(value))

        return snippet

    def get_initial_automations(
        self, domain: str, device_info: Dict = None
    ) -> List[Dict]:
        """Get initial automation suggestions for an integration.

        Args:
            domain: Integration domain
            device_info: Optional device information

        Returns:
            List of automation configurations
        """
        automations = self.INITIAL_AUTOMATION_TEMPLATES.get(domain, [])

        if device_info and automations:
            # Customize automations with device info
            customized = []
            for automation in automations:
                auto_copy = dict(automation)
                if auto_copy.get("trigger"):
                    triggers = auto_copy["trigger"]
                    if isinstance(triggers, list):
                        for trigger in triggers:
                            if isinstance(trigger, dict):
                                device_id = device_info.get("device_id")
                                entity_id = device_info.get("entity_id")
                                if device_id and "device_id" in trigger:
                                    trigger["device_id"] = device_id
                                if entity_id and "entity_id" in trigger:
                                    trigger["entity_id"] = entity_id
                customized.append(auto_copy)
            automations = customized

        _LOGGER.debug(
            "Retrieved %d initial automations for domain: %s",
            len(automations),
            domain,
        )
        return automations

    def get_setup_tips(self, domain: str) -> List[str]:
        """Get setup tips for an integration.

        Args:
            domain: Integration domain

        Returns:
            List of tip strings
        """
        tips = self.SETUP_TIPS.get(domain, [])
        _LOGGER.debug("Retrieved %d tips for domain: %s", len(tips), domain)
        return tips

    def search_integrations(self, query: str) -> List[IntegrationInfo]:
        """Search for integrations by keyword.

        Args:
            query: Search query

        Returns:
            List of matching IntegrationInfo objects
        """
        query_lower = query.lower()
        results = []

        for domain, integration in self.INTEGRATION_DATABASE.items():
            search_text = f"{domain} {integration.name} {integration.description}".lower()
            if (
                query_lower in search_text
                or query_lower in domain
                or query_lower in integration.name.lower()
            ):
                results.append(integration)
                _LOGGER.debug(
                    "Found matching integration: %s (%s)",
                    integration.name,
                    domain,
                )

        _LOGGER.debug(
            "Search for '%s' returned %d results", query, len(results)
        )
        return results

    def get_ai_setup_guide(self, domain: str, user_requirements: str) -> str:
        """Generate an AI-powered personalized setup guide.

        This method provides a placeholder for AI-powered personalized
        setup guidance based on user requirements.

        Args:
            domain: Integration domain
            user_requirements: User's specific requirements or preferences

        Returns:
            Formatted setup guide string
        """
        integration = self.get_integration_info(domain)
        guide = self.get_setup_guide(domain)

        lines = []
        lines.append(f"# Personalized Setup Guide for {domain}")
        lines.append("")

        if integration:
            lines.append(f"**Integration:** {integration.name}")
            lines.append("")
            lines.append(f"**Description:** {integration.description}")
            lines.append("")

        lines.append("## Your Requirements")
        lines.append("")
        lines.append(user_requirements)
        lines.append("")

        lines.append("## Recommended Setup Steps")
        lines.append("")
        lines.append(
            "Based on your requirements, here are the recommended steps:"
        )
        lines.append("")

        for step in guide.steps:
            lines.append(step.to_markdown())

        if integration and integration.documentation_url:
            lines.append(
                f"For more details, see the [official documentation]({integration.documentation_url})."
            )
            lines.append("")

        result = "\n".join(lines)
        _LOGGER.debug(
            "Generated AI setup guide for domain: %s", domain
        )
        return result
