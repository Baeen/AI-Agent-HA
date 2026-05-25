"""Performance monitoring dashboard templates for AI Agent HA integration.

This module provides dashboard templates and analysis tools for monitoring
Home Assistant system performance (CPU, memory, disk, network, database).
"""

import logging
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


# Performance dashboard template
PERFORMANCE_DASHBOARD_TEMPLATE = {
    "id": "ai_agent_ha_performance",
    "title": "AI Agent HA Performance",
    "mode": "yaml",
    "panels": [
        {
            "title": "System Overview",
            "type": "vertical-stack",
            "cards": [
                {
                    "type": "gauge",
                    "entity": "sensor.home_assistant_cpu",
                    "name": "CPU Usage",
                    "min": 0,
                    "max": 100,
                    "severity": {
                        "green": 0,
                        "yellow": 50,
                        "red": 80
                    }
                },
                {
                    "type": "gauge",
                    "entity": "sensor.home_assistant_memory",
                    "name": "Memory Usage",
                    "min": 0,
                    "max": 100,
                    "severity": {
                        "green": 0,
                        "yellow": 60,
                        "red": 85
                    }
                },
                {
                    "type": "gauge",
                    "entity": "sensor.home_assistant_disk",
                    "name": "Disk Usage",
                    "min": 0,
                    "max": 100,
                    "severity": {
                        "green": 0,
                        "yellow": 70,
                        "red": 90
                    }
                }
            ]
        },
        {
            "title": "Response Times",
            "type": "history-graph",
            "entities": [
                "sensor.ai_agent_response_time",
                "sensor.home_assistant_api_response"
            ],
            "hours_to_show": 24
        },
        {
            "title": "AI Agent Statistics",
            "type": "vertical-stack",
            "cards": [
                {
                    "type": "statistic-card",
                    "entities": [
                        {
                            "entity": "sensor.ai_agent_api_calls",
                            "name": "API Calls (Hour)"
                        }
                    ],
                    "stats": ["last_hour"]
                },
                {
                    "type": "statistic-card",
                    "entities": [
                        {
                            "entity": "sensor.ai_agent_token_usage",
                            "name": "Tokens Used (Day)"
                        }
                    ],
                    "stats": ["last_24h"]
                }
            ]
        },
        {
            "title": "Performance Alerts",
            "type": "entities",
            "entities": [
                "binary_sensor.ai_agent_performance_degraded",
                "binary_sensor.ai_agent_api_errors",
                "binary_sensor.ai_agent_high_latency"
            ]
        }
    ]
}

# System monitoring sensors template
SYSTEM_SENSORS_TEMPLATE = """
# System Monitoring Sensors for Home Assistant
# Add to configuration.yaml or include in a separate sensors.yaml file

sensor:
  # Home Assistant Core Resources
  - platform: systemmonitor
    resources:
      - type: processor_use
        name: Home Assistant CPU
      - type: memory_use_percent
        name: Home Assistant Memory
      - type: disk_use_percent
        name: Home Assistant Disk
      - type: processor_load
        name: Home Assistant Load
      - type: throughput_network_in
        name: Network In
      - type: throughput_network_out
        name: Network Out

  # AI Agent Specific Metrics
  - platform: statistics
    entity_id: sensor.ai_agent_response_time
    name: AI Response Time Stats
    state_characteristic: mean
    max_samples: 100

  # Database Performance
  - platform: postgresql
    host: localhost
    port: 5432
    database: homeassistant
    user: hass
    monitored_variables:
      - table: states
        count: true
        name: State Count
"""

# Dashboard YAML for Lovelace
PERFORMANCE_DASHBOARD_YAML = """
# Performance Monitoring Dashboard
# Add to your lovelace configurations in configuration.yaml

# Option 1: YAML mode dashboard
# Add to your ui-lovelace.yaml or through UI

# Option 2: Add via AI Agent service
# ai_agent_ha_create_dashboard with:
#   dashboard_type: performance
#   title: "System Performance"

cards:
  # System Resources Overview
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.home_assistant_cpu
        name: CPU
        min: 0
        max: 100
        severity:
          green: 0
          yellow: 50
          red: 80

      - type: gauge
        entity: sensor.home_assistant_memory
        name: Memory
        min: 0
        max: 100
        severity:
          green: 0
          yellow: 60
          red: 85

      - type: gauge
        entity: sensor.home_assistant_disk
        name: Disk
        min: 0
        max: 100
        severity:
          green: 0
          yellow: 70
          red: 90

  # Response Time Trend
  - type: history-graph
    title: "AI Response Times (24h)"
    entities:
      - sensor.ai_agent_response_time

  # API Call Statistics
  - type: statistic-card
    title: "API Calls"
    entities:
      - entity: sensor.ai_agent_api_calls
        name: Last Hour
    stats:
      - last_hour

  # Performance Alerts
  - type: entities
    title: "Performance Alerts"
    entities:
      - binary_sensor.ai_agent_performance_degraded
      - binary_sensor.ai_agent_api_errors
      - binary_sensor.ai_agent_high_latency
"""


class PerformanceDashboardProvider:
    """Provides performance dashboard templates and configurations."""

    def __init__(self):
        """Initialize the dashboard provider."""
        self._templates = {
            "performance": PERFORMANCE_DASHBOARD_TEMPLATE,
            "sensors": SYSTEM_SENSORS_TEMPLATE,
            "yaml": PERFORMANCE_DASHBOARD_YAML,
        }

    def get_dashboard_template(self, dashboard_type: str = "performance") -> Optional[Dict]:
        """Get a dashboard template by type.

        Args:
            dashboard_type: Type of dashboard template.

        Returns:
            Dashboard template dictionary or None.
        """
        return self._templates.get(dashboard_type)

    def get_sensor_configuration(self) -> str:
        """Get sensor configuration YAML for system monitoring.

        Returns:
            YAML string for sensor configuration.
        """
        return SYSTEM_SENSORS_TEMPLATE

    def get_dashboard_yaml(self) -> str:
        """Get complete dashboard YAML configuration.

        Returns:
            YAML string for dashboard.
        """
        return PERFORMANCE_DASHBOARD_YAML

    def get_recommended_sensors(self) -> List[Dict[str, Any]]:
        """Get list of recommended sensors for performance monitoring.

        Returns:
            List of sensor configurations.
        """
        return [
            {
                "name": "Home Assistant CPU",
                "entity_id": "sensor.home_assistant_cpu",
                "source": "systemmonitor",
                "description": "CPU usage percentage of Home Assistant",
            },
            {
                "name": "Home Assistant Memory",
                "entity_id": "sensor.home_assistant_memory",
                "source": "systemmonitor",
                "description": "Memory usage percentage of Home Assistant",
            },
            {
                "name": "Home Assistant Disk",
                "entity_id": "sensor.home_assistant_disk",
                "source": "systemmonitor",
                "description": "Disk usage percentage of Home Assistant",
            },
            {
                "name": "AI Agent Response Time",
                "entity_id": "sensor.ai_agent_response_time",
                "source": "custom",
                "description": "Average response time for AI agent requests",
            },
            {
                "name": "AI Agent API Calls",
                "entity_id": "sensor.ai_agent_api_calls",
                "source": "custom",
                "description": "Number of API calls made by AI agent",
            },
        ]

    def get_alerting_rules(self) -> List[Dict[str, Any]]:
        """Get recommended alerting rules for performance monitoring.

        Returns:
            List of alerting rule configurations.
        """
        return [
            {
                "name": "High CPU Usage",
                "condition": "numeric_state",
                "entity_id": "sensor.home_assistant_cpu",
                "above": 80,
                "duration": "00:05:00",
                "message": "Home Assistant CPU usage is above 80%",
            },
            {
                "name": "High Memory Usage",
                "condition": "numeric_state",
                "entity_id": "sensor.home_assistant_memory",
                "above": 85,
                "duration": "00:05:00",
                "message": "Home Assistant memory usage is above 85%",
            },
            {
                "name": "High Disk Usage",
                "condition": "numeric_state",
                "entity_id": "sensor.home_assistant_disk",
                "above": 90,
                "duration": "00:01:00",
                "message": "Home Assistant disk usage is above 90%",
            },
            {
                "name": "High AI Response Time",
                "condition": "numeric_state",
                "entity_id": "sensor.ai_agent_response_time",
                "above": 10000,  # 10 seconds
                "duration": "00:05:00",
                "message": "AI agent response time is above 10 seconds",
            },
            {
                "name": "AI Agent API Errors",
                "condition": "state",
                "entity_id": "binary_sensor.ai_agent_api_errors",
                "to": "on",
                "message": "AI agent is experiencing API errors",
            },
        ]

    def generate_performance_report(self, metrics: Dict[str, Any]) -> str:
        """Generate a performance report from metrics.

        Args:
            metrics: Dictionary of performance metrics.

        Returns:
            Markdown formatted performance report.
        """
        lines = ["## Performance Report"]
        lines.append("")

        # System resources
        lines.append("### System Resources")
        lines.append("")

        cpu = metrics.get("cpu", {})
        memory = metrics.get("memory", {})
        disk = metrics.get("disk", {})

        lines.append(f"- **CPU Usage:** {cpu.get('value', 'N/A')}%")
        lines.append(f"- **Memory Usage:** {memory.get('value', 'N/A')}%")
        lines.append(f"- **Disk Usage:** {disk.get('value', 'N/A')}%")
        lines.append("")

        # AI Agent metrics
        lines.append("### AI Agent Metrics")
        lines.append("")

        response_time = metrics.get("response_time", {})
        api_calls = metrics.get("api_calls", {})

        lines.append(f"- **Avg Response Time:** {response_time.get('avg', 'N/A')}ms")
        lines.append(f"- **Max Response Time:** {response_time.get('max', 'N/A')}ms")
        lines.append(f"- **API Calls (hour):** {api_calls.get('last_hour', 'N/A')}")
        lines.append(f"- **Success Rate:** {api_calls.get('success_rate', 'N/A')}%")
        lines.append("")

        # Recommendations
        lines.append("### Recommendations")
        lines.append("")

        if cpu.get("value", 0) > 80:
            lines.append("- ⚠️ CPU usage is high. Consider optimizing automations or upgrading hardware.")
        if memory.get("value", 0) > 85:
            lines.append("- ⚠️ Memory usage is high. Consider restarting Home Assistant or reducing add-ons.")
        if disk.get("value", 0) > 90:
            lines.append("- 🚨 Disk usage is critical. Clean up snapshots and backups.")
        if response_time.get("avg", 0) > 10000:
            lines.append("- ⚠️ AI response times are high. Check network connectivity and API status.")

        if not any(lines[-1].startswith(c) for c in ["-", "⚠", "🚨"]):
            lines.append("- ✅ All systems are performing within normal parameters.")

        lines.append("")
        return "\n".join(lines)
