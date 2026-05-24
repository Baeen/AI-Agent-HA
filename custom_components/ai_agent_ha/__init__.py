"""The AI Agent HA integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .agent import AiAgentHaAgent
from .const import DOMAIN, CONF_AUDIT_LOG_ENABLED, CONF_AUDIT_LOG_RETENTION_DAYS, CONF_AUDIT_LOG_MAX_ENTRIES, CONF_AUDIT_LOG_PERSISTENCE_ENABLED
from .chat_history import ChatHistoryManager
from .audit_log import AuditLogManager, RetentionPolicy

_LOGGER = logging.getLogger(__name__)

# Config schema - this integration only supports config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Define service schema to accept a custom prompt
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("prompt"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the AI Agent HA component."""
    return True


# Schema for new services
REVIEW_SCHEMA = vol.Schema(
    {
        vol.Required("yaml_content"): cv.string,
        vol.Optional("review_type", default="automation"): vol.In(
            ["automation", "dashboard", "script", "scene"]
        ),
        vol.Optional("provider"): cv.string,
    }
)

DOCUMENTATION_SCHEMA = vol.Schema(
    {
        vol.Optional("section"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

LOG_ANALYSIS_SCHEMA = vol.Schema(
    {
        vol.Optional("hours", default=24): vol.All(int, vol.Range(min=1, max=720)),
        vol.Optional("search_terms"): cv.string,
        vol.Optional("generate_ai_summary", default=True): cv.boolean,
        vol.Optional("provider"): cv.string,
    }
)

SEARCH_LOGS_SCHEMA = vol.Schema(
    {
        vol.Required("search_term"): cv.string,
        vol.Optional("hours", default=24): vol.All(int, vol.Range(min=1, max=720)),
        vol.Optional("levels"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

DIAGNOSE_ERROR_SCHEMA = vol.Schema(
    {
        vol.Required("error_message"): cv.string,
        vol.Optional("context"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

DIAGNOSE_MULTIPLE_ERRORS_SCHEMA = vol.Schema(
    {
        vol.Required("error_messages"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

TROUBLESHOOTING_GUIDE_SCHEMA = vol.Schema(
    {
        vol.Required("error_type"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

TROUBLESHOOT_AUTOMATION_SCHEMA = vol.Schema(
    {
        vol.Required("automation"): dict,
        vol.Optional("provider"): cv.string,
    }
)

TROUBLESHOOT_MULTIPLE_AUTOMATIONS_SCHEMA = vol.Schema(
    {
        vol.Required("automations"): [dict],
        vol.Optional("provider"): cv.string,
    }
)

AUTOMATION_FIX_SCHEMA = vol.Schema(
    {
        vol.Required("automation"): dict,
        vol.Optional("issue_type"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

ENTITY_DISCOVERY_SCHEMA = vol.Schema(
    {
        vol.Optional("area_name"): cv.string,
        vol.Optional("domain"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

ROOM_ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Optional("room_name"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

FUNCTION_ENTITIES_SCHEMA = vol.Schema(
    {
        vol.Required("function"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

AUTOMATION_SUGGESTION_SCHEMA = vol.Schema(
    {
        vol.Optional("user_query"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

PERSONALIZED_SUGGESTION_SCHEMA = vol.Schema(
    {
        vol.Required("user_query"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

# Configuration validator schemas
VALIDATE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional("config_type", default="all"): vol.In(
            ["all", "configuration", "automations", "scripts", "groups"]
        ),
        vol.Optional("provider"): cv.string,
    }
)

VALIDATE_AUTOMATIONS_SCHEMA = vol.Schema(
    {
        vol.Required("automations"): [dict],
        vol.Optional("provider"): cv.string,
    }
)

VALIDATE_SCRIPTS_SCHEMA = vol.Schema(
    {
        vol.Required("scripts"): dict,
        vol.Optional("provider"): cv.string,
    }
)

IMPROVEMENT_SUGGESTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("config_type", default="all"): vol.In(
            ["all", "configuration", "automations", "scripts", "groups"]
        ),
        vol.Optional("provider"): cv.string,
    }
)

# Backup & Restore Advisor schemas
BACKUP_RECOMMENDATION_SCHEMA = vol.Schema(
    {
        vol.Required("changes_description"): cv.string,
        vol.Optional("include_database", default=True): cv.boolean,
        vol.Optional("provider"): cv.string,
    }
)

VERIFY_AFTER_CHANGES_SCHEMA = vol.Schema(
    {
        vol.Required("changes_made"): [dict],
        vol.Optional("current_config"): dict,
        vol.Optional("provider"): cv.string,
    }
)

ROLLBACK_SUGGESTION_SCHEMA = vol.Schema(
    {
        vol.Required("issue"): cv.string,
        vol.Required("changes_made"): [dict],
        vol.Optional("backup_path"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

GENERATE_BACKUP_SCRIPT_SCHEMA = vol.Schema(
    {
        vol.Optional("backup_path", default="/backup"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

# Energy Optimization schemas
ANALYZE_ENERGY_SCHEMA = vol.Schema(
    {
        vol.Optional("time_period", default="month"): vol.In(
            ["day", "week", "month"]
        ),
        vol.Optional("provider"): cv.string,
    }
)

GET_ENERGY_SUGGESTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("provider"): cv.string,
    }
)

GET_DEVICE_ENERGY_ANALYSIS_SCHEMA = vol.Schema(
    {
        vol.Optional("domain"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

# Security Audit schemas
SECURITY_AUDIT_SCHEMA = vol.Schema(
    {
        vol.Required("automations"): [dict],
        vol.Optional("provider"): cv.string,
    }
)

CHECK_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required("configurations"): [dict],
        vol.Optional("provider"): cv.string,
    }
)
GET_SECURITY_SCORE_SCHEMA = vol.Schema(
    {
        vol.Optional("provider"): cv.string,
    }
)

# Natural Language to Automation schemas
CONVERT_NL_TO_AUTOMATION_SCHEMA = vol.Schema(
    {
        vol.Required("natural_language"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

CREATE_AUTOMATION_FROM_NL_SCHEMA = vol.Schema(
    {
        vol.Required("natural_language"): cv.string,
        vol.Optional("require_review", default=True): cv.boolean,
        vol.Optional("provider"): cv.string,
    }
)

# Dashboard Advisor schemas
ANALYZE_DASHBOARD_SCHEMA = vol.Schema(
    {
        vol.Required("dashboard_url"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

GET_CARD_RECOMMENDATIONS_SCHEMA = vol.Schema(
    {
        vol.Required("entities"): [dict],
        vol.Optional("provider"): cv.string,
    }
)

SUGGEST_DASHBOARD_LAYOUT_SCHEMA = vol.Schema(
    {
        vol.Optional("dashboard_type", default="general"): vol.In(
            ["general", "energy", "security", "climate", "room", "media", "automation"]
        ),
        vol.Optional("provider"): cv.string,
    }
)

# Integration Guide schemas
INTEGRATION_GUIDE_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

CONFIG_SNIPPET_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

SEARCH_INTEGRATIONS_SCHEMA = vol.Schema(
    {
        vol.Required("query"): cv.string,
        vol.Optional("provider"): cv.string,
    }
)

# Chat History schemas
GET_CONVERSATIONS_SCHEMA = vol.Schema({})
DELETE_CONVERSATION_SCHEMA = vol.Schema(
    {
        vol.Required("conversation_id"): cv.string,
    }
)
RENAME_CONVERSATION_SCHEMA = vol.Schema(
    {
        vol.Required("conversation_id"): cv.string,
        vol.Required("name"): cv.string,
    }
)
EXPORT_CONVERSATION_SCHEMA = vol.Schema(
    {
        vol.Required("conversation_id"): cv.string,
    }
)
SEARCH_CONVERSATIONS_SCHEMA = vol.Schema(
    {
        vol.Required("query"): cv.string,
    }
)
CLEAR_OLD_CONVERSATIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("days_threshold", default=30): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=365)
        ),
    }
)
PIN_CONVERSATION_SCHEMA = vol.Schema(
    {
        vol.Required("conversation_id"): cv.string,
    }
)
ADD_TAG_SCHEMA = vol.Schema(
    {
        vol.Required("conversation_id"): cv.string,
        vol.Required("tag"): cv.string,
    }
)

# Audit Log schemas
GET_AUDIT_LOGS_SCHEMA = vol.Schema(
    {
        vol.Optional("action_type"): cv.string,
        vol.Optional("severity"): cv.string,
        vol.Optional("component"): cv.string,
        vol.Optional("start_time"): cv.string,
        vol.Optional("end_time"): cv.string,
        vol.Optional("entity"): cv.string,
        vol.Optional("provider"): cv.string,
        vol.Optional("limit", default=100): vol.All(int, vol.Range(min=1, max=10000)),
        vol.Optional("offset", default=0): vol.All(int, vol.Range(min=0)),
    }
)

GET_AUDIT_LOG_STATISTICS_SCHEMA = vol.Schema({})

EXPORT_AUDIT_LOGS_SCHEMA = vol.Schema(
    {
        vol.Optional("format_type", default="json"): vol.In(["json", "csv"]),
        vol.Optional("action_type"): cv.string,
        vol.Optional("start_time"): cv.string,
        vol.Optional("end_time"): cv.string,
    }
)

CLEAR_AUDIT_LOGS_SCHEMA = vol.Schema({})

CLEAR_OLD_AUDIT_LOGS_SCHEMA = vol.Schema(
    {
        vol.Optional("days_threshold", default=30): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=365)
        ),
    }
)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to new version."""
    _LOGGER.debug("Migrating config entry from version %s", entry.version)

    if entry.version == 1:
        # No migration needed for version 1
        return True

    # Future migrations would go here
    # if entry.version < 2:
    #     # Migrate from version 1 to 2
    #     new_data = dict(entry.data)
    #     # Add migration logic here
    #     hass.config_entries.async_update_entry(entry, data=new_data, version=2)

    _LOGGER.info("Migration to version %s successful", entry.version)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AI Agent HA from a config entry."""
    try:
        # Handle version compatibility
        if not hasattr(entry, "version") or entry.version != 1:
            _LOGGER.warning(
                "Config entry has version %s, expected 1. Attempting compatibility mode.",
                getattr(entry, "version", "unknown"),
            )

        # Convert ConfigEntry to dict and ensure all required keys exist
        config_data = dict(entry.data)

        # Ensure backward compatibility - check for required keys
        if "ai_provider" not in config_data:
            _LOGGER.error(
                "Config entry missing required 'ai_provider' key. Entry data: %s",
                config_data,
            )
            raise ConfigEntryNotReady("Config entry missing required 'ai_provider' key")

        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {"agents": {}, "configs": {}}

        provider = config_data["ai_provider"]

        # Validate provider
        if provider not in [
            "llama",
            "openai",
            "gemini",
            "openrouter",
            "anthropic",
            "alter",
            "zai",
            "local_ollama",
            "openai_compatible",
        ]:
            _LOGGER.error("Unknown AI provider: %s", provider)
            raise ConfigEntryNotReady(f"Unknown AI provider: {provider}")

        # Store config for this provider
        hass.data[DOMAIN]["configs"][provider] = config_data

        # Create agent for this provider
        _LOGGER.debug(
            "Creating AI agent for provider %s with config: %s",
            provider,
            {
                k: v
                for k, v in config_data.items()
                if k
                not in [
                    "llama_token",
                    "openai_token",
                    "gemini_token",
                    "openrouter_token",
                    "anthropic_token",
                    "zai_token",
                ]
            },
        )
        hass.data[DOMAIN]["agents"][provider] = AiAgentHaAgent(hass, config_data)

        # Initialize chat history manager
        if "chat_history_manager" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["chat_history_manager"] = ChatHistoryManager(hass)
        
        # Initialize audit log manager
        if "audit_log_manager" not in hass.data[DOMAIN]:
            from .const import (
                DEFAULT_AUDIT_LOG_ENABLED,
                DEFAULT_AUDIT_LOG_RETENTION_DAYS,
                DEFAULT_AUDIT_LOG_MAX_ENTRIES,
                DEFAULT_AUDIT_LOG_PERSISTENCE_ENABLED,
            )
            audit_log_enabled = entry.options.get(
                CONF_AUDIT_LOG_ENABLED,
                entry.data.get(CONF_AUDIT_LOG_ENABLED, DEFAULT_AUDIT_LOG_ENABLED)
            )
            if audit_log_enabled:
                retention_policy = RetentionPolicy(
                    max_age_days=entry.options.get(
                        CONF_AUDIT_LOG_RETENTION_DAYS,
                        entry.data.get(CONF_AUDIT_LOG_RETENTION_DAYS, DEFAULT_AUDIT_LOG_RETENTION_DAYS)
                    ),
                    max_entries=entry.options.get(
                        CONF_AUDIT_LOG_MAX_ENTRIES,
                        entry.data.get(CONF_AUDIT_LOG_MAX_ENTRIES, DEFAULT_AUDIT_LOG_MAX_ENTRIES)
                    ),
                )
                hass.data[DOMAIN]["audit_log_manager"] = AuditLogManager(
                    hass,
                    retention_policy=retention_policy,
                    persistence_enabled=entry.options.get(
                        CONF_AUDIT_LOG_PERSISTENCE_ENABLED,
                        entry.data.get(CONF_AUDIT_LOG_PERSISTENCE_ENABLED, DEFAULT_AUDIT_LOG_PERSISTENCE_ENABLED)
                    ),
                )
                _LOGGER.info("Audit log manager initialized successfully")
            else:
                hass.data[DOMAIN]["audit_log_manager"] = None
                _LOGGER.info("Audit log disabled")

        _LOGGER.info("Successfully set up AI Agent HA for provider: %s", provider)

    except KeyError as err:
        _LOGGER.error("Missing required configuration key: %s", err)
        raise ConfigEntryNotReady(f"Missing required configuration key: {err}")
    except Exception as err:
        _LOGGER.exception("Unexpected error setting up AI Agent HA")
        raise ConfigEntryNotReady(f"Error setting up AI Agent HA: {err}")

    # Modify the query service handler to use the correct provider
    async def async_handle_query(call):
        """Handle the query service call."""
        try:
            # Check if agents are available
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                _LOGGER.error(
                    "No AI agents available. Please configure the integration first."
                )
                result = {"error": "No AI agents configured"}
                hass.bus.async_fire("ai_agent_ha_response", result)
                return

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                # Get the first available provider
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    _LOGGER.error("No AI agents available")
                    result = {"error": "No AI agents configured"}
                    hass.bus.async_fire("ai_agent_ha_response", result)
                    return
                provider = available_providers[0]
                _LOGGER.debug(f"Using fallback provider: {provider}")

            agent = hass.data[DOMAIN]["agents"][provider]
            
            # Process images if provided
            images = None
            image_mime_types = None
            if call.data.get("images"):
                import base64
                images = []
                image_mime_types = call.data.get("mime_types", ["image/jpeg"] * len(call.data["images"]))
                for i, img_data in enumerate(call.data["images"]):
                    try:
                        decoded = base64.b64decode(img_data)
                        images.append(decoded)
                    except Exception as e:
                        _LOGGER.error(f"Invalid base64 image data at index {i}: {e}")
                        return _with_debug({"success": False, "error": f"Invalid image data: {str(e)}"})
            
            result = await agent.process_query(
                call.data.get("prompt", ""),
                provider=provider,
                debug=call.data.get("debug", False),
                images=images,
                image_mime_types=image_mime_types,
            )
            hass.bus.async_fire("ai_agent_ha_response", result)
        except Exception as e:
            _LOGGER.error(f"Error processing query: {e}")
            result = {"error": str(e)}
            hass.bus.async_fire("ai_agent_ha_response", result)

    async def async_handle_create_automation(call):
        """Handle the create_automation service call."""
        try:
            # Check if agents are available
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                _LOGGER.error(
                    "No AI agents available. Please configure the integration first."
                )
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                # Get the first available provider
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    _LOGGER.error("No AI agents available")
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]
                _LOGGER.debug(f"Using fallback provider: {provider}")

            agent = hass.data[DOMAIN]["agents"][provider]
            result = await agent.create_automation(call.data.get("automation", {}))
            return result
        except Exception as e:
            _LOGGER.error(f"Error creating automation: {e}")
            return {"error": str(e)}

    async def async_handle_save_prompt_history(call):
        """Handle the save_prompt_history service call."""
        try:
            # Check if agents are available
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                _LOGGER.error(
                    "No AI agents available. Please configure the integration first."
                )
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                # Get the first available provider
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    _LOGGER.error("No AI agents available")
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]
                _LOGGER.debug(f"Using fallback provider: {provider}")

            agent = hass.data[DOMAIN]["agents"][provider]
            user_id = call.context.user_id if call.context.user_id else "default"
            result = await agent.save_user_prompt_history(
                user_id, call.data.get("history", [])
            )
            return result
        except Exception as e:
            _LOGGER.error(f"Error saving prompt history: {e}")
            return {"error": str(e)}

    async def async_handle_load_prompt_history(call):
        """Handle the load_prompt_history service call."""
        try:
            # Check if agents are available
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                _LOGGER.error(
                    "No AI agents available. Please configure the integration first."
                )
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                # Get the first available provider
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    _LOGGER.error("No AI agents available")
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]
                _LOGGER.debug(f"Using fallback provider: {provider}")

            agent = hass.data[DOMAIN]["agents"][provider]
            user_id = call.context.user_id if call.context.user_id else "default"
            result = await agent.load_user_prompt_history(user_id)
            _LOGGER.debug("Load prompt history result: %s", result)
            return result
        except Exception as e:
            _LOGGER.error(f"Error loading prompt history: {e}")
            return {"error": str(e)}

    async def async_handle_create_dashboard(call):
        """Handle the create_dashboard service call."""
        try:
            # Check if agents are available
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                _LOGGER.error(
                    "No AI agents available. Please configure the integration first."
                )
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                # Get the first available provider
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    _LOGGER.error("No AI agents available")
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]
                _LOGGER.debug(f"Using fallback provider: {provider}")

            agent = hass.data[DOMAIN]["agents"][provider]

            # Parse dashboard config if it's a string
            dashboard_config = call.data.get("dashboard_config", {})
            if isinstance(dashboard_config, str):
                try:
                    import json

                    dashboard_config = json.loads(dashboard_config)
                except json.JSONDecodeError as e:
                    _LOGGER.error(f"Invalid JSON in dashboard_config: {e}")
                    return {"error": f"Invalid JSON in dashboard_config: {e}"}

            result = await agent.create_dashboard(dashboard_config)
            return result
        except Exception as e:
            _LOGGER.error(f"Error creating dashboard: {e}")
            return {"error": str(e)}

    async def async_handle_update_dashboard(call):
        """Handle the update_dashboard service call."""
        try:
            # Check if agents are available
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                _LOGGER.error(
                    "No AI agents available. Please configure the integration first."
                )
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                # Get the first available provider
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    _LOGGER.error("No AI agents available")
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]
                _LOGGER.debug(f"Using fallback provider: {provider}")

            agent = hass.data[DOMAIN]["agents"][provider]

            # Parse dashboard config if it's a string
            dashboard_config = call.data.get("dashboard_config", {})
            if isinstance(dashboard_config, str):
                try:
                    import json

                    dashboard_config = json.loads(dashboard_config)
                except json.JSONDecodeError as e:
                    _LOGGER.error(f"Invalid JSON in dashboard_config: {e}")
                    return {"error": f"Invalid JSON in dashboard_config: {e}"}

            dashboard_url = call.data.get("dashboard_url", "")
            if not dashboard_url:
                return {"error": "Dashboard URL is required"}

            result = await agent.update_dashboard(dashboard_url, dashboard_config)
            return result
        except Exception as e:
            _LOGGER.error(f"Error updating dashboard: {e}")
            return {"error": str(e)}

    # Register services
    hass.services.async_register(DOMAIN, "query", async_handle_query)
    
    # Schema for multimodal query service (with images)
    MULTIMODAL_QUERY_SCHEMA = vol.Schema({
        vol.Required("prompt"): cv.string,
        vol.Optional("images"): [cv.string],  # Base64 encoded images
        vol.Optional("mime_types"): [cv.string],  # MIME types of images
        vol.Optional("provider"): cv.string,
        vol.Optional("debug", default=False): cv.boolean,
    })
    
    hass.services.async_register(
        DOMAIN, "multimodal_query", async_handle_query, schema=MULTIMODAL_QUERY_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "create_automation", async_handle_create_automation
    )
    hass.services.async_register(
        DOMAIN, "save_prompt_history", async_handle_save_prompt_history
    )
    hass.services.async_register(
        DOMAIN, "load_prompt_history", async_handle_load_prompt_history
    )
    hass.services.async_register(
        DOMAIN, "create_dashboard", async_handle_create_dashboard
    )
    hass.services.async_register(
        DOMAIN, "update_dashboard", async_handle_update_dashboard
    )
    
    # New services for YAML review and documentation
    async def async_handle_review_yaml(call):
        """Handle the review_yaml service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                _LOGGER.error("No AI agents available")
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    _LOGGER.error("No AI agents available")
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]
                _LOGGER.debug(f"Using fallback provider: {provider}")

            agent = hass.data[DOMAIN]["agents"][provider]
            yaml_content = call.data.get("yaml_content", "")
            review_type = call.data.get("review_type", "automation")
            
            result = await agent.review_yaml(yaml_content, review_type)
            return result
        except Exception as e:
            _LOGGER.error(f"Error reviewing YAML: {e}")
            return {"error": str(e)}

    async def async_handle_review_automation(call):
        """Handle the review_automation service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            automation_config = call.data.get("automation", {})
            
            result = await agent.review_automation(automation_config)
            return result
        except Exception as e:
            _LOGGER.error(f"Error reviewing automation: {e}")
            return {"error": str(e)}

    async def async_handle_get_documentation(call):
        """Handle the get_documentation service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            section = call.data.get("section")
            
            if section:
                result = agent.get_ha_documentation()
                # Return just the section if specified
                if f"## {section}" in result:
                    start = result.find(f"## {section}")
                    end = result.find("## ", start + 4)
                    if end == -1:
                        result = result[start:]
                    else:
                        result = result[start:end]
            else:
                result = agent.get_ha_documentation()
            
            return {"documentation": result, "success": True}
        except Exception as e:
            _LOGGER.error(f"Error getting documentation: {e}")
            return {"error": str(e), "success": False}

    async def async_handle_create_automation_with_review(call):
        """Handle the create_automation_with_review service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            automation_config = call.data.get("automation", {})
            require_review = call.data.get("require_review", True)
            
            result = await agent.create_automation_with_review(automation_config, require_review)
            return result
        except Exception as e:
            _LOGGER.error(f"Error creating automation with review: {e}")
            return {"error": str(e)}

    hass.services.async_register(DOMAIN, "review_yaml", async_handle_review_yaml)
    hass.services.async_register(DOMAIN, "review_automation", async_handle_review_automation)
    hass.services.async_register(DOMAIN, "get_documentation", async_handle_get_documentation)
    hass.services.async_register(DOMAIN, "create_automation_with_review", async_handle_create_automation_with_review)

    # Log analysis services
    async def async_handle_analyze_logs(call):
        """Handle the analyze_logs service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            hours = call.data.get("hours", 24)
            search_terms_str = call.data.get("search_terms", "")
            search_terms = [t.strip() for t in search_terms_str.split(",") if t.strip()] if search_terms_str else None
            generate_ai_summary = call.data.get("generate_ai_summary", True)
            
            result = await agent.analyze_logs(
                hours=hours,
                search_terms=search_terms,
                generate_ai_summary=generate_ai_summary
            )
            return result
        except Exception as e:
            _LOGGER.error(f"Error analyzing logs: {e}")
            return {"error": str(e)}

    async def async_handle_search_logs(call):
        """Handle the search_logs service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            search_term = call.data.get("search_term", "")
            hours = call.data.get("hours", 24)
            levels_str = call.data.get("levels", "")
            levels = [l.strip().upper() for l in levels_str.split(",") if l.strip()] if levels_str else None
            
            result = await agent.search_logs(
                search_term=search_term,
                hours=hours,
                levels=levels
            )
            return result
        except Exception as e:
            _LOGGER.error(f"Error searching logs: {e}")
            return {"error": str(e)}

    async def async_handle_get_error_summary(call):
        """Handle the get_error_summary service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            hours = call.data.get("hours", 24)
            
            result = await agent.get_error_summary(hours=hours)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting error summary: {e}")
            return {"error": str(e)}

    hass.services.async_register(DOMAIN, "analyze_logs", async_handle_analyze_logs)
    hass.services.async_register(DOMAIN, "search_logs", async_handle_search_logs)
    hass.services.async_register(DOMAIN, "get_error_summary", async_handle_get_error_summary)

    # Error diagnosis services
    async def async_handle_diagnose_error(call):
        """Handle the diagnose_error service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            error_message = call.data.get("error_message", "")
            context_str = call.data.get("context", "")
            
            # Parse context if provided
            context = None
            if context_str:
                try:
                    import json
                    context = json.loads(context_str)
                except json.JSONDecodeError:
                    context = {"raw": context_str}
            
            result = await agent.diagnose_error(
                error_message=error_message,
                context=context
            )
            return result
        except Exception as e:
            _LOGGER.error(f"Error diagnosing error: {e}")
            return {"error": str(e)}

    async def async_handle_diagnose_multiple_errors(call):
        """Handle the diagnose_multiple_errors service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            error_messages_str = call.data.get("error_messages", "")
            
            # Parse error messages
            try:
                import json
                error_messages = json.loads(error_messages_str)
                if not isinstance(error_messages, list):
                    error_messages = [error_messages_str]
            except json.JSONDecodeError:
                # Treat as comma-separated if not JSON
                error_messages = [m.strip() for m in error_messages_str.split(",") if m.strip()]
            
            result = await agent.diagnose_multiple_errors(error_messages=error_messages)
            return result
        except Exception as e:
            _LOGGER.error(f"Error diagnosing multiple errors: {e}")
            return {"error": str(e)}

    async def async_handle_get_troubleshooting_guide(call):
        """Handle the get_troubleshooting_guide service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            error_type = call.data.get("error_type", "")
            
            result = await agent.get_troubleshooting_guide(error_type=error_type)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting troubleshooting guide: {e}")
            return {"error": str(e)}

    hass.services.async_register(DOMAIN, "diagnose_error", async_handle_diagnose_error)
    hass.services.async_register(DOMAIN, "diagnose_multiple_errors", async_handle_diagnose_multiple_errors)
    hass.services.async_register(DOMAIN, "get_troubleshooting_guide", async_handle_get_troubleshooting_guide)

    # Automation troubleshooter services
    async def async_handle_troubleshoot_automation(call):
        """Handle the troubleshoot_automation service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            automation = call.data.get("automation", {})
            
            result = await agent.troubleshoot_automation(automation_config=automation)
            return result
        except Exception as e:
            _LOGGER.error(f"Error troubleshooting automation: {e}")
            return {"error": str(e)}

    async def async_handle_troubleshoot_multiple_automations(call):
        """Handle the troubleshoot_multiple_automations service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            automations = call.data.get("automations", [])
            
            result = await agent.troubleshoot_multiple_automations(automation_configs=automations)
            return result
        except Exception as e:
            _LOGGER.error(f"Error troubleshooting multiple automations: {e}")
            return {"error": str(e)}

    async def async_handle_get_automation_fix(call):
        """Handle the get_automation_fix service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            automation = call.data.get("automation", {})
            issue_type = call.data.get("issue_type")
            
            result = await agent.get_automation_fix(
                automation_config=automation,
                issue_type=issue_type
            )
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting automation fix: {e}")
            return {"error": str(e)}

    hass.services.async_register(DOMAIN, "troubleshoot_automation", async_handle_troubleshoot_automation)
    hass.services.async_register(DOMAIN, "troubleshoot_multiple_automations", async_handle_troubleshoot_multiple_automations)
    hass.services.async_register(DOMAIN, "get_automation_fix", async_handle_get_automation_fix)

    # Entity discovery services
    async def async_handle_discover_entities(call):
        """Handle the discover_entities service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            area_name = call.data.get("area_name")
            domain = call.data.get("domain")
            
            result = await agent.discover_entities(area_name=area_name, domain=domain)
            return result
        except Exception as e:
            _LOGGER.error(f"Error discovering entities: {e}")
            return {"error": str(e)}

    async def async_handle_get_entities_by_room(call):
        """Handle the get_entities_by_room service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            room_name = call.data.get("room_name")
            
            result = await agent.get_entities_by_room(room_name=room_name)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting entities by room: {e}")
            return {"error": str(e)}

    async def async_handle_get_entities_by_function(call):
        """Handle the get_entities_by_function service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            function = call.data.get("function", "")
            
            result = await agent.get_entities_by_function(function=function)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting entities by function: {e}")
            return {"error": str(e)}

    async def async_handle_suggest_automations(call):
        """Handle the suggest_automations service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            user_query = call.data.get("user_query")
            
            result = await agent.suggest_automations(user_query=user_query)
            return result
        except Exception as e:
            _LOGGER.error(f"Error suggesting automations: {e}")
            return {"error": str(e)}

    async def async_handle_get_personalized_suggestions(call):
        """Handle the get_personalized_suggestions service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            user_query = call.data.get("user_query", "")
            
            result = await agent.get_personalized_suggestions(user_query=user_query)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting personalized suggestions: {e}")
            return {"error": str(e)}

    # Configuration validator services
    async def async_handle_validate_configuration(call):
        """Handle the validate_configuration service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            config_type = call.data.get("config_type", "all")
            
            result = await agent.validate_configuration(config_type=config_type)
            return result
        except Exception as e:
            _LOGGER.error(f"Error validating configuration: {e}")
            return {"error": str(e)}

    async def async_handle_validate_automations(call):
        """Handle the validate_automations service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            automations = call.data.get("automations", [])
            
            result = await agent.validate_automations(automations=automations)
            return result
        except Exception as e:
            _LOGGER.error(f"Error validating automations: {e}")
            return {"error": str(e)}

    async def async_handle_validate_scripts(call):
        """Handle the validate_scripts service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            scripts = call.data.get("scripts", {})
            
            result = await agent.validate_scripts(scripts=scripts)
            return result
        except Exception as e:
            _LOGGER.error(f"Error validating scripts: {e}")
            return {"error": str(e)}

    async def async_handle_get_improvement_suggestions(call):
        """Handle the get_improvement_suggestions service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            config_type = call.data.get("config_type", "all")
            
            result = await agent.get_improvement_suggestions(config_type=config_type)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting improvement suggestions: {e}")
            return {"error": str(e)}

    hass.services.async_register(DOMAIN, "discover_entities", async_handle_discover_entities)
    hass.services.async_register(DOMAIN, "get_entities_by_room", async_handle_get_entities_by_room)
    hass.services.async_register(DOMAIN, "get_entities_by_function", async_handle_get_entities_by_function)
    hass.services.async_register(DOMAIN, "suggest_automations", async_handle_suggest_automations)
    hass.services.async_register(DOMAIN, "get_personalized_suggestions", async_handle_get_personalized_suggestions)
    
    # Register configuration validator services
    hass.services.async_register(DOMAIN, "validate_configuration", async_handle_validate_configuration)
    hass.services.async_register(DOMAIN, "validate_automations", async_handle_validate_automations)
    hass.services.async_register(DOMAIN, "validate_scripts", async_handle_validate_scripts)
    hass.services.async_register(DOMAIN, "get_improvement_suggestions", async_handle_get_improvement_suggestions)

    # Dashboard Advisor services
    async def async_handle_analyze_dashboard(call):
        """Handle the analyze_dashboard service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            dashboard_url = call.data.get("dashboard_url", "")

            result = await agent.analyze_dashboard(dashboard_url=dashboard_url)
            return result
        except Exception as e:
            _LOGGER.error(f"Error analyzing dashboard: {e}")
            return {"error": str(e)}

    async def async_handle_get_card_recommendations(call):
        """Handle the get_card_recommendations service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            entities = call.data.get("entities", [])

            result = await agent.get_card_recommendations(entities=entities)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting card recommendations: {e}")
            return {"error": str(e)}

    async def async_handle_suggest_dashboard_layout(call):
        """Handle the suggest_dashboard_layout service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            dashboard_type = call.data.get("dashboard_type", "general")

            result = await agent.suggest_dashboard_layout(dashboard_type=dashboard_type)
            return result
        except Exception as e:
            _LOGGER.error(f"Error suggesting dashboard layout: {e}")
            return {"error": str(e)}

    hass.services.async_register(DOMAIN, "analyze_dashboard", async_handle_analyze_dashboard)
    hass.services.async_register(DOMAIN, "get_card_recommendations", async_handle_get_card_recommendations)
    hass.services.async_register(DOMAIN, "suggest_dashboard_layout", async_handle_suggest_dashboard_layout)

    # Backup & Restore Advisor services
    async def async_handle_get_backup_recommendation(call):
        """Handle the get_backup_recommendation service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            changes_description = call.data.get("changes_description", "")
            include_database = call.data.get("include_database", True)

            result = await agent.get_backup_recommendation(
                changes_description, include_database
            )
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting backup recommendation: {e}")
            return {"error": str(e)}

    async def async_handle_verify_after_changes(call):
        """Handle the verify_after_changes service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            changes_made = call.data.get("changes_made", [])
            current_config = call.data.get("current_config")

            result = await agent.verify_after_changes(
                changes_made, current_config
            )
            return result
        except Exception as e:
            _LOGGER.error(f"Error verifying after changes: {e}")
            return {"error": str(e)}

    async def async_handle_get_rollback_suggestion(call):
        """Handle the get_rollback_suggestion service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            issue = call.data.get("issue", "")
            changes_made = call.data.get("changes_made", [])
            backup_path = call.data.get("backup_path")

            result = await agent.get_rollback_suggestion(
                issue, changes_made, backup_path
            )
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting rollback suggestion: {e}")
            return {"error": str(e)}

    async def async_handle_generate_backup_script(call):
        """Handle the generate_backup_script service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            backup_path = call.data.get("backup_path", "/backup")

            result = await agent.generate_backup_script(backup_path)
            return result
        except Exception as e:
            _LOGGER.error(f"Error generating backup script: {e}")
            return {"error": str(e)}

    # Energy Optimization service handlers
    async def async_handle_analyze_energy_usage(call):
        """Handle the analyze_energy_usage service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            time_period = call.data.get("time_period", "month")

            result = await agent.analyze_energy_usage(time_period=time_period)
            return result
        except Exception as e:
            _LOGGER.error(f"Error analyzing energy usage: {e}")
            return {"error": str(e)}

    async def async_handle_get_energy_suggestions(call):
        """Handle the get_energy_suggestions service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]

            result = await agent.get_energy_suggestions()
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting energy suggestions: {e}")
            return {"error": str(e)}

    async def async_handle_get_device_energy_analysis(call):
        """Handle the get_device_energy_analysis service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            domain = call.data.get("domain")

            result = await agent.get_device_energy_analysis(domain=domain)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting device energy analysis: {e}")
            return {"error": str(e)}

    # Security Audit service handlers
    async def async_handle_security_audit(call):
        """Handle the security_audit service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            automations = call.data.get("automations", [])

            result = await agent.security_audit(automations=automations)
            return result
        except Exception as e:
            _LOGGER.error(f"Error running security audit: {e}")
            return {"error": str(e)}

    async def async_handle_check_credentials(call):
        """Handle the check_credentials service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            configurations = call.data.get("configurations", [])

            result = await agent.check_credentials(configurations=configurations)
            return result
        except Exception as e:
            _LOGGER.error(f"Error checking credentials: {e}")
            return {"error": str(e)}

    async def async_handle_get_security_score(call):
        """Handle the get_security_score service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]

            result = await agent.get_security_score()
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting security score: {e}")
            return {"error": str(e)}

    # Natural Language to Automation service handlers
    async def async_handle_convert_nl_to_automation(call):
        """Handle the convert_nl_to_automation service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            natural_language = call.data.get("natural_language", "")

            result = await agent.convert_nl_to_automation(natural_language)
            return result
        except Exception as e:
            _LOGGER.error(f"Error converting natural language to automation: {e}")
            return {"error": str(e)}

    async def async_handle_create_automation_from_nl(call):
        """Handle the create_automation_from_nl service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            natural_language = call.data.get("natural_language", "")
            require_review = call.data.get("require_review", True)

            result = await agent.create_automation_from_nl(natural_language, require_review)
            return result
        except Exception as e:
            _LOGGER.error(f"Error creating automation from natural language: {e}")
            return {"error": str(e)}

    hass.services.async_register(
        DOMAIN, "get_backup_recommendation", async_handle_get_backup_recommendation
    )
    hass.services.async_register(
        DOMAIN, "verify_after_changes", async_handle_verify_after_changes
    )
    hass.services.async_register(
        DOMAIN, "get_rollback_suggestion", async_handle_get_rollback_suggestion
    )
    hass.services.async_register(
        DOMAIN, "generate_backup_script", async_handle_generate_backup_script
    )

    # Register energy optimization services
    hass.services.async_register(
        DOMAIN,
        "analyze_energy_usage",
        async_handle_analyze_energy_usage,
        ANALYZE_ENERGY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "get_energy_suggestions",
        async_handle_get_energy_suggestions,
        GET_ENERGY_SUGGESTIONS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "get_device_energy_analysis",
        async_handle_get_device_energy_analysis,
        GET_DEVICE_ENERGY_ANALYSIS_SCHEMA,
    )

    # Register security audit services
    hass.services.async_register(
        DOMAIN,
        "security_audit",
        async_handle_security_audit,
        SECURITY_AUDIT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "check_credentials",
        async_handle_check_credentials,
        CHECK_CREDENTIALS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "get_security_score",
        async_handle_get_security_score,
        GET_SECURITY_SCORE_SCHEMA,
    )

    # Register Natural Language to Automation services
    hass.services.async_register(
        DOMAIN,
        "convert_nl_to_automation",
        async_handle_convert_nl_to_automation,
        CONVERT_NL_TO_AUTOMATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "create_automation_from_nl",
        async_handle_create_automation_from_nl,
        CREATE_AUTOMATION_FROM_NL_SCHEMA,
    )

    # Integration Guide services
    async def async_handle_get_integration_guide(call):
        """Handle the get_integration_guide service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            domain = call.data.get("domain", "")

            result = await agent.get_integration_guide(domain)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting integration guide: {e}")
            return {"error": str(e)}

    async def async_handle_get_config_snippet(call):
        """Handle the get_config_snippet service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            domain = call.data.get("domain", "")

            result = await agent.get_config_snippet(domain)
            return result
        except Exception as e:
            _LOGGER.error(f"Error getting config snippet: {e}")
            return {"error": str(e)}

    async def async_handle_search_integrations(call):
        """Handle the search_integrations service call."""
        try:
            if DOMAIN not in hass.data or not hass.data[DOMAIN].get("agents"):
                return {"error": "No AI agents configured"}

            provider = call.data.get("provider")
            if provider not in hass.data[DOMAIN]["agents"]:
                available_providers = list(hass.data[DOMAIN]["agents"].keys())
                if not available_providers:
                    return {"error": "No AI agents configured"}
                provider = available_providers[0]

            agent = hass.data[DOMAIN]["agents"][provider]
            query = call.data.get("query", "")

            result = await agent.search_integrations(query)
            return result
        except Exception as e:
            _LOGGER.error(f"Error searching integrations: {e}")
            return {"error": str(e)}

    hass.services.async_register(
        DOMAIN,
        "get_integration_guide",
        async_handle_get_integration_guide,
        INTEGRATION_GUIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "get_config_snippet",
        async_handle_get_config_snippet,
        CONFIG_SNIPPET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "search_integrations",
        async_handle_search_integrations,
        SEARCH_INTEGRATIONS_SCHEMA,
    )

    # Prompt Compaction status service
    COMPACTION_STATUS_SCHEMA = vol.Schema({})

    async def async_handle_get_compaction_status(call):
        """Handle the get_compaction_status service call."""
        try:
            provider = call.data.get("provider")
            if provider and provider in hass.data[DOMAIN]["agents"]:
                agent = hass.data[DOMAIN]["agents"][provider]
            elif "agents" in hass.data[DOMAIN]:
                # If no specific provider, get the first available agent
                agent = next(iter(hass.data[DOMAIN]["agents"].values()), None)
            else:
                return {"error": "No AI agent configured"}
            
            if agent is None:
                return {"error": "No AI agent available"}
            
            # Get compaction statistics
            compaction_stats = agent.prompt_compactor.get_compaction_stats()
            
            # Get current token estimate
            current_tokens = agent.prompt_compactor.estimate_messages_tokens(
                agent.conversation_history
            )
            max_tokens = agent._get_max_tokens_for_provider(
                agent.config.get("ai_provider", "openai")
            )
            
            return {
                "current_tokens": current_tokens,
                "max_tokens": max_tokens,
                "threshold": agent.prompt_compactor.threshold_pct,
                "compaction_enabled": agent.prompt_compactor.enabled,
                "compaction_stats": compaction_stats,
            }
        except Exception as e:
            _LOGGER.error(f"Error getting compaction status: {e}")
            return {"error": str(e)}

    hass.services.async_register(
        DOMAIN,
        "get_compaction_status",
        async_handle_get_compaction_status,
        COMPACTION_STATUS_SCHEMA,
    )

    # Chat History services
    
    # Schema for save_conversation service
    SAVE_CONVERSATION_SCHEMA = vol.Schema(
        {
            vol.Required("conversation_id"): cv.string,
            vol.Required("messages"): [dict],
            vol.Optional("name"): cv.string,
        }
    )
    
    # Schema for get_conversation service
    GET_CONVERSATION_SCHEMA = vol.Schema(
        {
            vol.Required("conversation_id"): cv.string,
        }
    )
    
    async def async_handle_save_conversation(call):
        """Save a conversation."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            success = await manager.save_conversation(
                call.data["conversation_id"],
                call.data["messages"],
                call.data.get("name", ""),
            )
            return {"success": success}
        except Exception as e:
            _LOGGER.error("Error saving conversation: %s", str(e))
            return {"success": False, "error": str(e)}
    
    async def async_handle_get_conversation(call):
        """Get a specific conversation."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            messages = await manager.get_conversation(call.data["conversation_id"])
            if messages is None:
                return {"success": False, "error": "Conversation not found"}
            return {"success": True, "messages": messages}
        except Exception as e:
            _LOGGER.error("Error getting conversation: %s", str(e))
            return {"success": False, "error": str(e)}
    
    async def async_handle_get_conversations(call):
        """Get list of all saved conversations."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            conversations = await manager.load_conversations()
            return {
                "success": True,
                "conversations": [
                    {
                        "conversation_id": c.conversation_id,
                        "name": c.name,
                        "created_at": c.created_at,
                        "updated_at": c.updated_at,
                        "message_count": c.message_count,
                        "preview": c.preview,
                        "tags": c.tags,
                        "is_pinned": c.is_pinned,
                    }
                    for c in conversations
                ],
            }
        except Exception as e:
            _LOGGER.error("Error getting conversations: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_delete_conversation(call):
        """Delete a specific conversation."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            success = await manager.delete_conversation(call.data["conversation_id"])
            return {"success": success}
        except Exception as e:
            _LOGGER.error("Error deleting conversation: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_rename_conversation(call):
        """Rename a conversation."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            success = await manager.rename_conversation(
                call.data["conversation_id"],
                call.data["name"],
            )
            return {"success": success}
        except Exception as e:
            _LOGGER.error("Error renaming conversation: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_export_conversation(call):
        """Export a conversation to JSON."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            export_data = await manager.export_conversation(call.data["conversation_id"])
            return {"success": True, "data": export_data}
        except Exception as e:
            _LOGGER.error("Error exporting conversation: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_search_conversations(call):
        """Search conversations by query."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            conversations = await manager.search_conversations(call.data["query"])
            return {
                "success": True,
                "conversations": [
                    {
                        "conversation_id": c.conversation_id,
                        "name": c.name,
                        "preview": c.preview,
                        "tags": c.tags,
                    }
                    for c in conversations
                ],
            }
        except Exception as e:
            _LOGGER.error("Error searching conversations: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_clear_old_conversations(call):
        """Clear conversations older than threshold."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            days = call.data.get("days_threshold", 30)
            count = await manager.clear_old_conversations(days)
            return {"success": True, "deleted_count": count}
        except Exception as e:
            _LOGGER.error("Error clearing old conversations: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_pin_conversation(call):
        """Pin a conversation."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            success = await manager.pin_conversation(call.data["conversation_id"])
            return {"success": success}
        except Exception as e:
            _LOGGER.error("Error pinning conversation: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_add_tag(call):
        """Add a tag to a conversation."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                return {"success": False, "error": "Chat history manager not initialized"}
            
            success = await manager.add_tag(
                call.data["conversation_id"],
                call.data["tag"],
            )
            return {"success": success}
        except Exception as e:
            _LOGGER.error("Error adding tag: %s", str(e))
            return {"success": False, "error": str(e)}

    # Register chat history services
    hass.services.async_register(
        DOMAIN, "save_conversation", async_handle_save_conversation, schema=SAVE_CONVERSATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "get_conversation", async_handle_get_conversation, schema=GET_CONVERSATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "get_conversations", async_handle_get_conversations, schema=GET_CONVERSATIONS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "delete_conversation", async_handle_delete_conversation, schema=DELETE_CONVERSATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "rename_conversation", async_handle_rename_conversation, schema=RENAME_CONVERSATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "export_conversation", async_handle_export_conversation, schema=EXPORT_CONVERSATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "search_conversations", async_handle_search_conversations, schema=SEARCH_CONVERSATIONS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "clear_old_conversations", async_handle_clear_old_conversations, schema=CLEAR_OLD_CONVERSATIONS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "pin_conversation", async_handle_pin_conversation, schema=PIN_CONVERSATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "add_tag", async_handle_add_tag, schema=ADD_TAG_SCHEMA
    )

    # WebSocket command handlers for chat history
    async def async_handle_ws_get_conversations(message):
        """WebSocket handler to get all conversations."""
        try:
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                hass.async_add_job(
                    message.client.send_error("HOME_ASSISTANT_ERROR", "Chat history manager not initialized")
                )
                return
            
            conversations = await manager.load_conversations()
            hass.async_add_job(
                message.client.send_result(
                    message.id,
                    {
                        "success": True,
                        "conversations": [
                            {
                                "conversation_id": c.conversation_id,
                                "name": c.name,
                                "created_at": c.created_at,
                                "updated_at": c.updated_at,
                                "message_count": c.message_count,
                                "preview": c.preview,
                                "tags": c.tags,
                                "is_pinned": c.is_pinned,
                            }
                            for c in conversations
                        ],
                    }
                )
            )
        except Exception as e:
            _LOGGER.error("Error getting conversations via WebSocket: %s", str(e))
            hass.async_add_job(
                message.client.send_error("HOME_ASSISTANT_ERROR", str(e))
            )

    async def async_handle_ws_get_conversation(message):
        """WebSocket handler to get a specific conversation."""
        try:
            conversation_id = message.data.get("conversation_id")
            if not conversation_id:
                hass.async_add_job(
                    message.client.send_error("INVALID_INPUT", "conversation_id is required")
                )
                return
            
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                hass.async_add_job(
                    message.client.send_error("HOME_ASSISTANT_ERROR", "Chat history manager not initialized")
                )
                return
            
            messages = await manager.get_conversation(conversation_id)
            if messages is None:
                hass.async_add_job(
                    message.client.send_error("NOT_FOUND", "Conversation not found")
                )
                return
            
            hass.async_add_job(
                message.client.send_result(
                    message.id,
                    {"success": True, "messages": messages}
                )
            )
        except Exception as e:
            _LOGGER.error("Error getting conversation via WebSocket: %s", str(e))
            hass.async_add_job(
                message.client.send_error("HOME_ASSISTANT_ERROR", str(e))
            )

    async def async_handle_ws_save_conversation(message):
        """WebSocket handler to save a conversation."""
        try:
            conversation_id = message.data.get("conversation_id")
            messages = message.data.get("messages", [])
            name = message.data.get("name", "")
            
            if not conversation_id:
                hass.async_add_job(
                    message.client.send_error("INVALID_INPUT", "conversation_id is required")
                )
                return
            
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                hass.async_add_job(
                    message.client.send_error("HOME_ASSISTANT_ERROR", "Chat history manager not initialized")
                )
                return
            
            success = await manager.save_conversation(conversation_id, messages, name)
            
            hass.async_add_job(
                message.client.send_result(
                    message.id,
                    {"success": success, "conversation_id": conversation_id}
                )
            )
        except Exception as e:
            _LOGGER.error("Error saving conversation via WebSocket: %s", str(e))
            hass.async_add_job(
                message.client.send_error("HOME_ASSISTANT_ERROR", str(e))
            )

    async def async_handle_ws_delete_conversation(message):
        """WebSocket handler to delete a conversation."""
        try:
            conversation_id = message.data.get("conversation_id")
            if not conversation_id:
                hass.async_add_job(
                    message.client.send_error("INVALID_INPUT", "conversation_id is required")
                )
                return
            
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                hass.async_add_job(
                    message.client.send_error("HOME_ASSISTANT_ERROR", "Chat history manager not initialized")
                )
                return
            
            success = await manager.delete_conversation(conversation_id)
            
            hass.async_add_job(
                message.client.send_result(message.id, {"success": success})
            )
        except Exception as e:
            _LOGGER.error("Error deleting conversation via WebSocket: %s", str(e))
            hass.async_add_job(
                message.client.send_error("HOME_ASSISTANT_ERROR", str(e))
            )

    async def async_handle_ws_rename_conversation(message):
        """WebSocket handler to rename a conversation."""
        try:
            conversation_id = message.data.get("conversation_id")
            name = message.data.get("name")
            
            if not conversation_id or not name:
                hass.async_add_job(
                    message.client.send_error("INVALID_INPUT", "conversation_id and name are required")
                )
                return
            
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                hass.async_add_job(
                    message.client.send_error("HOME_ASSISTANT_ERROR", "Chat history manager not initialized")
                )
                return
            
            success = await manager.rename_conversation(conversation_id, name)
            
            hass.async_add_job(
                message.client.send_result(message.id, {"success": success})
            )
        except Exception as e:
            _LOGGER.error("Error renaming conversation via WebSocket: %s", str(e))
            hass.async_add_job(
                message.client.send_error("HOME_ASSISTANT_ERROR", str(e))
            )

    async def async_handle_ws_export_conversation(message):
        """WebSocket handler to export a conversation."""
        try:
            conversation_id = message.data.get("conversation_id")
            if not conversation_id:
                hass.async_add_job(
                    message.client.send_error("INVALID_INPUT", "conversation_id is required")
                )
                return
            
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                hass.async_add_job(
                    message.client.send_error("HOME_ASSISTANT_ERROR", "Chat history manager not initialized")
                )
                return
            
            export_data = await manager.export_conversation(conversation_id)
            if export_data is None:
                hass.async_add_job(
                    message.client.send_error("NOT_FOUND", "Conversation not found")
                )
                return
            
            hass.async_add_job(
                message.client.send_result(message.id, {"success": True, "data": export_data})
            )
        except Exception as e:
            _LOGGER.error("Error exporting conversation via WebSocket: %s", str(e))
            hass.async_add_job(
                message.client.send_error("HOME_ASSISTANT_ERROR", str(e))
            )

    async def async_handle_ws_pin_conversation(message):
        """WebSocket handler to pin a conversation."""
        try:
            conversation_id = message.data.get("conversation_id")
            if not conversation_id:
                hass.async_add_job(
                    message.client.send_error("INVALID_INPUT", "conversation_id is required")
                )
                return
            
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                hass.async_add_job(
                    message.client.send_error("HOME_ASSISTANT_ERROR", "Chat history manager not initialized")
                )
                return
            
            success = await manager.pin_conversation(conversation_id)
            
            hass.async_add_job(
                message.client.send_result(message.id, {"success": success})
            )
        except Exception as e:
            _LOGGER.error("Error pinning conversation via WebSocket: %s", str(e))
            hass.async_add_job(
                message.client.send_error("HOME_ASSISTANT_ERROR", str(e))
            )

    async def async_handle_ws_add_tag(message):
        """WebSocket handler to add a tag to a conversation."""
        try:
            conversation_id = message.data.get("conversation_id")
            tag = message.data.get("tag")
            
            if not conversation_id or not tag:
                hass.async_add_job(
                    message.client.send_error("INVALID_INPUT", "conversation_id and tag are required")
                )
                return
            
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                hass.async_add_job(
                    message.client.send_error("HOME_ASSISTANT_ERROR", "Chat history manager not initialized")
                )
                return
            
            success = await manager.add_tag(conversation_id, tag)
            
            hass.async_add_job(
                message.client.send_result(message.id, {"success": success})
            )
        except Exception as e:
            _LOGGER.error("Error adding tag via WebSocket: %s", str(e))
            hass.async_add_job(
                message.client.send_error("HOME_ASSISTANT_ERROR", str(e))
            )

    async def async_handle_ws_search_conversations(message):
        """WebSocket handler to search conversations."""
        try:
            query = message.data.get("query", "")
            
            manager = hass.data[DOMAIN].get("chat_history_manager")
            if not manager:
                hass.async_add_job(
                    message.client.send_error("HOME_ASSISTANT_ERROR", "Chat history manager not initialized")
                )
                return
            
            conversations = await manager.search_conversations(query)
            hass.async_add_job(
                message.client.send_result(
                    message.id,
                    {
                        "success": True,
                        "conversations": [
                            {
                                "conversation_id": c.conversation_id,
                                "name": c.name,
                                "created_at": c.created_at,
                                "updated_at": c.updated_at,
                                "message_count": c.message_count,
                                "preview": c.preview,
                                "tags": c.tags,
                                "is_pinned": c.is_pinned,
                            }
                            for c in conversations
                        ],
                    }
                )
            )
        except Exception as e:
            _LOGGER.error("Error searching conversations via WebSocket: %s", str(e))
            hass.async_add_job(
                message.client.send_error("HOME_ASSISTANT_ERROR", str(e))
            )

    # Register WebSocket commands
    from homeassistant.components.websocket_api import async_register_command
    
    async_register_command(hass, "ai_agent_ha/get_conversations", async_handle_ws_get_conversations)
    async_register_command(hass, "ai_agent_ha/get_conversation", async_handle_ws_get_conversation)
    async_register_command(hass, "ai_agent_ha/save_conversation", async_handle_ws_save_conversation)
    async_register_command(hass, "ai_agent_ha/delete_conversation", async_handle_ws_delete_conversation)
    async_register_command(hass, "ai_agent_ha/rename_conversation", async_handle_ws_rename_conversation)
    async_register_command(hass, "ai_agent_ha/export_conversation", async_handle_ws_export_conversation)
    async_register_command(hass, "ai_agent_ha/pin_conversation", async_handle_ws_pin_conversation)
    async_register_command(hass, "ai_agent_ha/add_tag", async_handle_ws_add_tag)
    async_register_command(hass, "ai_agent_ha/search_conversations", async_handle_ws_search_conversations)

    # Permission System schemas
    APPROVE_PERMISSION_SCHEMA = vol.Schema({
        vol.Required("request_id"): str,
    })

    DENY_PERMISSION_SCHEMA = vol.Schema({
        vol.Required("request_id"): str,
    })

    GET_PENDING_PERMISSIONS_SCHEMA = vol.Schema({})

    # Permission System services
    async def async_handle_approve_permission(call):
        """Approve a pending permission request."""
        try:
            agent = hass.data[DOMAIN]["agents"].get("default")
            if not agent:
                # Try to get any available agent
                agents = hass.data[DOMAIN].get("agents", {})
                if agents:
                    agent = list(agents.values())[0]
                else:
                    return {"success": False, "error": "No agent available"}
            
            success = agent.permission_checker.approve_request(call.data["request_id"])
            return {"success": success, "request_id": call.data["request_id"]}
        except Exception as e:
            _LOGGER.error("Error approving permission: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_deny_permission(call):
        """Deny a pending permission request."""
        try:
            agent = hass.data[DOMAIN]["agents"].get("default")
            if not agent:
                # Try to get any available agent
                agents = hass.data[DOMAIN].get("agents", {})
                if agents:
                    agent = list(agents.values())[0]
                else:
                    return {"success": False, "error": "No agent available"}
            
            success = agent.permission_checker.deny_request(call.data["request_id"])
            return {"success": success, "request_id": call.data["request_id"]}
        except Exception as e:
            _LOGGER.error("Error denying permission: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_get_pending_permissions(call):
        """Get all pending permission requests."""
        try:
            agent = hass.data[DOMAIN]["agents"].get("default")
            if not agent:
                # Try to get any available agent
                agents = hass.data[DOMAIN].get("agents", {})
                if agents:
                    agent = list(agents.values())[0]
                else:
                    return {"success": False, "error": "No agent available"}
            
            requests = agent.permission_checker.get_pending_requests()
            return {
                "success": True,
                "requests": [
                    {
                        "request_id": r.request_id,
                        "action": r.action,
                        "target_entities": r.target_entities,
                        "reason": r.reason,
                        "risk_level": r.risk_level,
                        "risk_description": agent.permission_checker.get_risk_description(r.risk_level),
                        "timestamp": r.timestamp,
                        "expires_at": r.expires_at,
                    }
                    for r in requests
                ]
            }
        except Exception as e:
            _LOGGER.error("Error getting pending permissions: %s", str(e))
            return {"success": False, "error": str(e)}

    hass.services.async_register(DOMAIN, "approve_permission", async_handle_approve_permission, schema=APPROVE_PERMISSION_SCHEMA)
    hass.services.async_register(DOMAIN, "deny_permission", async_handle_deny_permission, schema=DENY_PERMISSION_SCHEMA)
    hass.services.async_register(DOMAIN, "get_pending_permissions", async_handle_get_pending_permissions, schema=GET_PENDING_PERMISSIONS_SCHEMA)

    # Audit Log services
    async def async_handle_get_audit_logs(call):
        """Handle the get_audit_logs service call."""
        try:
            audit_manager = hass.data[DOMAIN].get("audit_log_manager")
            if not audit_manager:
                return {
                    "success": False,
                    "error": "Audit log manager not initialized",
                    "entries": [],
                    "total": 0,
                }
            
            result = audit_manager.get_entries(
                action_type=call.data.get("action_type"),
                severity=call.data.get("severity"),
                component=call.data.get("component"),
                start_time=call.data.get("start_time"),
                end_time=call.data.get("end_time"),
                entity=call.data.get("entity"),
                provider=call.data.get("provider"),
                limit=call.data.get("limit", 100),
                offset=call.data.get("offset", 0),
            )
            
            return {
                "success": True,
                "entries": [e.to_dict() for e in result["entries"]],
                "total": result["total"],
                "limit": result["limit"],
                "offset": result["offset"],
            }
        except Exception as e:
            _LOGGER.error("Error getting audit logs: %s", str(e))
            return {"success": False, "error": str(e), "entries": [], "total": 0}

    async def async_handle_get_audit_log_statistics(call):
        """Handle the get_audit_log_statistics service call."""
        try:
            audit_manager = hass.data[DOMAIN].get("audit_log_manager")
            if not audit_manager:
                return {
                    "success": False,
                    "error": "Audit log manager not initialized",
                }
            
            stats = audit_manager.get_statistics()
            return {
                "success": True,
                "statistics": stats,
            }
        except Exception as e:
            _LOGGER.error("Error getting audit log statistics: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_export_audit_logs(call):
        """Handle the export_audit_logs service call."""
        try:
            audit_manager = hass.data[DOMAIN].get("audit_log_manager")
            if not audit_manager:
                return {
                    "success": False,
                    "error": "Audit log manager not initialized",
                }
            
            export_data = audit_manager.export_logs(
                format_type=call.data.get("format_type", "json"),
                action_type=call.data.get("action_type"),
                start_time=call.data.get("start_time"),
                end_time=call.data.get("end_time"),
            )
            
            return {
                "success": True,
                "export_data": export_data,
                "format": call.data.get("format_type", "json"),
            }
        except Exception as e:
            _LOGGER.error("Error exporting audit logs: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_clear_audit_logs(call):
        """Handle the clear_audit_logs service call."""
        try:
            audit_manager = hass.data[DOMAIN].get("audit_log_manager")
            if not audit_manager:
                return {
                    "success": False,
                    "error": "Audit log manager not initialized",
                }
            
            count = audit_manager.clear_all()
            return {
                "success": True,
                "entries_cleared": count,
            }
        except Exception as e:
            _LOGGER.error("Error clearing audit logs: %s", str(e))
            return {"success": False, "error": str(e)}

    async def async_handle_clear_old_audit_logs(call):
        """Handle the clear_old_audit_logs service call."""
        try:
            audit_manager = hass.data[DOMAIN].get("audit_log_manager")
            if not audit_manager:
                return {
                    "success": False,
                    "error": "Audit log manager not initialized",
                }
            
            days = call.data.get("days_threshold", 30)
            count = audit_manager.clear_old_entries(days)
            return {
                "success": True,
                "entries_cleared": count,
                "days_threshold": days,
            }
        except Exception as e:
            _LOGGER.error("Error clearing old audit logs: %s", str(e))
            return {"success": False, "error": str(e)}

    hass.services.async_register(DOMAIN, "get_audit_logs", async_handle_get_audit_logs, schema=GET_AUDIT_LOGS_SCHEMA)
    hass.services.async_register(DOMAIN, "get_audit_log_statistics", async_handle_get_audit_log_statistics, schema=GET_AUDIT_LOG_STATISTICS_SCHEMA)
    hass.services.async_register(DOMAIN, "export_audit_logs", async_handle_export_audit_logs, schema=EXPORT_AUDIT_LOGS_SCHEMA)
    hass.services.async_register(DOMAIN, "clear_audit_logs", async_handle_clear_audit_logs, schema=CLEAR_AUDIT_LOGS_SCHEMA)
    hass.services.async_register(DOMAIN, "clear_old_audit_logs", async_handle_clear_old_audit_logs, schema=CLEAR_OLD_AUDIT_LOGS_SCHEMA)

    # Register static path for frontend
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/frontend/ai_agent_ha",
                hass.config.path("custom_components/ai_agent_ha/frontend"),
                False,
            )
        ]
    )

    # Panel registration with proper error handling
    panel_name = "ai_agent_ha"
    try:
        if await _panel_exists(hass, panel_name):
            _LOGGER.debug("AI Agent HA panel already exists, skipping registration")
            return True

        _LOGGER.debug("Registering AI Agent HA panel")
        async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="AI Agent HA",
            sidebar_icon="mdi:robot",
            frontend_url_path=panel_name,
            require_admin=False,
            config={
                "_panel_custom": {
                    "name": "ai_agent_ha-panel",
                    "module_url": "/frontend/ai_agent_ha/ai_agent_ha-panel.js",
                    "embed_iframe": False,
                }
            },
        )
        _LOGGER.debug("AI Agent HA panel registered successfully")
    except Exception as e:
        _LOGGER.warning("Panel registration error: %s", str(e))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await _panel_exists(hass, "ai_agent_ha"):
        try:
            from homeassistant.components.frontend import async_remove_panel

            async_remove_panel(hass, "ai_agent_ha")
            _LOGGER.debug("AI Agent HA panel removed successfully")
        except Exception as e:
            _LOGGER.debug("Error removing panel: %s", str(e))

    # Remove services
    hass.services.async_remove(DOMAIN, "query")
    hass.services.async_remove(DOMAIN, "create_automation")
    hass.services.async_remove(DOMAIN, "save_prompt_history")
    hass.services.async_remove(DOMAIN, "load_prompt_history")
    hass.services.async_remove(DOMAIN, "create_dashboard")
    hass.services.async_remove(DOMAIN, "update_dashboard")
    hass.services.async_remove(DOMAIN, "review_yaml")
    hass.services.async_remove(DOMAIN, "review_automation")
    hass.services.async_remove(DOMAIN, "get_documentation")
    hass.services.async_remove(DOMAIN, "create_automation_with_review")
    hass.services.async_remove(DOMAIN, "analyze_logs")
    hass.services.async_remove(DOMAIN, "search_logs")
    hass.services.async_remove(DOMAIN, "get_error_summary")
    hass.services.async_remove(DOMAIN, "diagnose_error")
    hass.services.async_remove(DOMAIN, "diagnose_multiple_errors")
    hass.services.async_remove(DOMAIN, "get_troubleshooting_guide")
    hass.services.async_remove(DOMAIN, "troubleshoot_automation")
    hass.services.async_remove(DOMAIN, "troubleshoot_multiple_automations")
    hass.services.async_remove(DOMAIN, "get_automation_fix")
    hass.services.async_remove(DOMAIN, "discover_entities")
    hass.services.async_remove(DOMAIN, "get_entities_by_room")
    hass.services.async_remove(DOMAIN, "get_entities_by_function")
    hass.services.async_remove(DOMAIN, "suggest_automations")
    hass.services.async_remove(DOMAIN, "get_personalized_suggestions")
    hass.services.async_remove(DOMAIN, "validate_configuration")
    hass.services.async_remove(DOMAIN, "validate_automations")
    hass.services.async_remove(DOMAIN, "validate_scripts")
    hass.services.async_remove(DOMAIN, "get_improvement_suggestions")
    hass.services.async_remove(DOMAIN, "get_backup_recommendation")
    hass.services.async_remove(DOMAIN, "verify_after_changes")
    hass.services.async_remove(DOMAIN, "get_rollback_suggestion")
    hass.services.async_remove(DOMAIN, "generate_backup_script")
    # Remove energy optimization services
    hass.services.async_remove(DOMAIN, "analyze_energy_usage")
    hass.services.async_remove(DOMAIN, "get_energy_suggestions")
    hass.services.async_remove(DOMAIN, "get_device_energy_analysis")
    # Remove security audit services
    hass.services.async_remove(DOMAIN, "security_audit")
    hass.services.async_remove(DOMAIN, "check_credentials")
    hass.services.async_remove(DOMAIN, "get_security_score")
    # Remove Natural Language to Automation services
    hass.services.async_remove(DOMAIN, "convert_nl_to_automation")
    hass.services.async_remove(DOMAIN, "create_automation_from_nl")
    # Remove Integration Guide services
    hass.services.async_remove(DOMAIN, "get_integration_guide")
    hass.services.async_remove(DOMAIN, "get_config_snippet")
    hass.services.async_remove(DOMAIN, "search_integrations")
    # Remove Prompt Compaction services
    hass.services.async_remove(DOMAIN, "get_compaction_status")
    # Remove Chat History services
    hass.services.async_remove(DOMAIN, "save_conversation")
    hass.services.async_remove(DOMAIN, "get_conversation")
    hass.services.async_remove(DOMAIN, "get_conversations")
    hass.services.async_remove(DOMAIN, "delete_conversation")
    hass.services.async_remove(DOMAIN, "rename_conversation")
    hass.services.async_remove(DOMAIN, "export_conversation")
    hass.services.async_remove(DOMAIN, "search_conversations")
    hass.services.async_remove(DOMAIN, "clear_old_conversations")
    hass.services.async_remove(DOMAIN, "pin_conversation")
    hass.services.async_remove(DOMAIN, "add_tag")
    
    # Remove Chat History WebSocket commands (no-op if not registered, so safe to call)
    # WebSocket commands are automatically unregistered when the integration is unloaded
    
    hass.services.async_remove(DOMAIN, "approve_permission")
    hass.services.async_remove(DOMAIN, "deny_permission")
    hass.services.async_remove(DOMAIN, "get_pending_permissions")
    # Remove Audit Log services
    hass.services.async_remove(DOMAIN, "get_audit_logs")
    hass.services.async_remove(DOMAIN, "get_audit_log_statistics")
    hass.services.async_remove(DOMAIN, "export_audit_logs")
    hass.services.async_remove(DOMAIN, "clear_audit_logs")
    hass.services.async_remove(DOMAIN, "clear_old_audit_logs")
    # Remove data
    if DOMAIN in hass.data:
        hass.data.pop(DOMAIN)

    return True


async def _panel_exists(hass: HomeAssistant, panel_name: str) -> bool:
    """Check if a panel already exists."""
    try:
        return hasattr(hass.data, "frontend_panels") and panel_name in hass.data.get(
            "frontend_panels", {}
        )
    except Exception as e:
        _LOGGER.debug("Error checking panel existence: %s", str(e))
        return False
