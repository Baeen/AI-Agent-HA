"""Config flow for AI Agent HA integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    BooleanSelector,
)

from .agent import (
    fetch_gemini_models,
    fetch_openai_compatible_models,
    fetch_openai_models,
)
from .const import (
    CONF_LOCAL_OLLAMA_URL,
    CONF_OPENAI_BASE_URL,
    CONF_OPENAI_COMPATIBLE_URL,
    DOMAIN,
    CONF_PROMPT_COMPACTION_ENABLED,
    CONF_PROMPT_COMPACTION_THRESHOLD,
    DEFAULT_PROMPT_COMPACTION_ENABLED,
    DEFAULT_COMPACTION_THRESHOLD,
    # Chat History settings
    CONF_CHAT_HISTORY_ENABLED,
    CONF_CHAT_HISTORY_MAX_CONVERSATIONS,
    CONF_CHAT_HISTORY_AUTO_CLEAR_DAYS,
    DEFAULT_CHAT_HISTORY_ENABLED,
    DEFAULT_MAX_CONVERSATIONS,
    DEFAULT_AUTO_CLEAR_DAYS,
    # Permission System settings
    CONF_PERMISSION_MODE,
    CONF_PERMISSION_TIMEOUT,
    DEFAULT_PERMISSION_MODE,
    DEFAULT_PERMISSION_TIMEOUT,
    # Multimedia settings
    CONF_MULTIMODAL_ENABLED,
    CONF_IMAGE_UPLOAD_ENABLED,
    CONF_MAX_IMAGE_SIZE,
    CONF_MAX_IMAGES_PER_MESSAGE,
    CONF_IMAGE_COMPRESSION_QUALITY,
    DEFAULT_MULTIMODAL_ENABLED,
    DEFAULT_IMAGE_UPLOAD_ENABLED,
    DEFAULT_MAX_IMAGE_SIZE,
    DEFAULT_MAX_IMAGES_PER_MESSAGE,
    DEFAULT_IMAGE_COMPRESSION_QUALITY,
)

_LOGGER = logging.getLogger(__name__)

PROVIDERS = {
    "llama": "Llama",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "openrouter": "OpenRouter",
    "anthropic": "Anthropic (Claude)",
    "alter": "Alter",
    "zai": "z.ai",
    "local_ollama": "Local Ollama",
    "openai_compatible": "Local OpenAI-Compatible (e.g. LM Studio, vLLM)",
}

TOKEN_FIELD_NAMES = {
    "llama": "llama_token",
    "openai": "openai_token",
    "gemini": "gemini_token",
    "openrouter": "openrouter_token",
    "anthropic": "anthropic_token",
    "alter": "alter_token",
    "zai": "zai_token",
    "zai_endpoint": "zai_endpoint",
    "local_ollama": CONF_LOCAL_OLLAMA_URL,  # For local Ollama models, we use URL instead of token
    "openai_compatible": CONF_OPENAI_COMPATIBLE_URL,  # For OpenAI-compatible endpoints
}

TOKEN_LABELS = {
    "llama": "Llama API Token",
    "openai": "OpenAI API Key",
    "gemini": "Google Gemini API Key",
    "openrouter": "OpenRouter API Key",
    "anthropic": "Anthropic API Key",
    "alter": "Alter API Key",
    "zai": "z.ai API Key",
    "zai_endpoint": "z.ai API Endpoint Type",
    "local_ollama": "Local Ollama API URL (e.g., http://localhost:11434/api/generate)",
    "openai_compatible": "OpenAI-Compatible URL (e.g., http://example.com/v1/ or http://localhost:8080/v1/). Must end with /v1/",
}

DEFAULT_MODELS = {
    "llama": "Llama-4-Maverick-17B-128E-Instruct-FP8",
    "openai": "gpt-5",
    "gemini": "gemini-2.5-flash",
    "openrouter": "openai/gpt-4o",
    "anthropic": "claude-sonnet-4-5-20250929",
    "alter": "",  # User enters custom model
    "zai": "glm-4.7",  # Z.ai's latest flagship model
    "local_ollama": "llama3.2",  # Updated to use llama3.2 as default for local Ollama
    "openai_compatible": "",  # User enters custom model for OpenAI-compatible endpoint
}

AVAILABLE_MODELS = {
    "openai": [
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "o3",
        "o3-mini",
        "o4-mini",
        "o1",
        "o1-preview",
        "o1-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
    ],
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
        "gemini-2.5-flash-preview",
        "gemini-2.5-pro-preview",
    ],
    "openrouter": [
        "openai/gpt-4o",
        "openai/gpt-4-turbo",
        "openai/gpt-3.5-turbo",
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3-sonnet",
        "anthropic/claude-3-haiku",
        "meta-llama/llama-3.1-70b-instruct",
        "meta-llama/llama-3.2-90b-instruct",
        "google/gemini-pro",
        "mistralai/mixtral-8x7b-instruct",
        "deepseek/deepseek-r1",
    ],
    "anthropic": [
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
        "claude-sonnet-4-5-20250929",
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ],
    "llama": [
        "Llama-4-Maverick-17B-128E-Instruct-FP8",
        "Llama-3.1-70B-Instruct",
        "Llama-3.1-8B-Instruct",
        "Llama-3.2-90B-Instruct",
    ],
    # Alter - user enters custom model name only
    "alter": [
        "Custom...",
    ],
    # z.ai - available models
    "zai": [
        "glm-4.7",
        "glm-4.6",
        "glm-4.5",
        "glm-4.5-air",
        "glm-4.5-x",
        "glm-4.5-airx",
        "glm-4.5-flash",
        "glm-4-32b-0414-128k",
        "Custom...",
    ],
    # For local Ollama models, provide common models with llama3.2 as the default
    "local_ollama": [
        "llama3.2",
        "llama3",
        "llama3.1",
        "mistral",
        "mixtral",
        "deepseek-coder",
        "Custom...",
    ],
    # For OpenAI-compatible endpoints, user should specify their model
    "openai_compatible": [
        "Custom...",
    ],
}

DEFAULT_PROVIDER = "openai"


class AiAgentHaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg,misc]
    """Handle a config flow for AI Agent HA."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        try:
            return AiAgentHaOptionsFlowHandler()
        except Exception as e:
            _LOGGER.error("Error creating options flow: %s", e)
            return None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Check if this provider is already configured
            await self.async_set_unique_id(f"ai_agent_ha_{user_input['ai_provider']}")
            self._abort_if_unique_id_configured()

            self.config_data = {"ai_provider": user_input["ai_provider"]}
            return await self.async_step_configure()

        # Show provider selection form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("ai_provider"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": k, "label": v} for k, v in PROVIDERS.items()
                            ]
                        )
                    ),
                }
            ),
        )

    async def async_step_configure(self, user_input=None):
        """Handle the configuration step for the selected provider."""
        errors = {}
        provider = self.config_data["ai_provider"]
        token_field = TOKEN_FIELD_NAMES[provider]
        token_label = TOKEN_LABELS[provider]
        default_model = DEFAULT_MODELS[provider]
        # For Alter provider, default to "Custom..." for the dropdown since model is user-provided
        dropdown_default = "Custom..." if provider == "alter" else default_model
        available_models = AVAILABLE_MODELS.get(provider, [default_model])

        if user_input is not None:
            try:
                # Validate the token
                token_value = user_input.get(token_field)
                if not token_value:
                    errors[token_field] = "required"
                    raise InvalidApiKey

                # Store the configuration data
                self.config_data[token_field] = token_value

                # For z.ai, store endpoint type
                if provider == "zai":
                    endpoint_type = user_input.get("zai_endpoint", "general")
                    self.config_data["zai_endpoint"] = endpoint_type

                # For OpenAI, store Base URL (defaults to official endpoint if unchanged)
                if provider == "openai":
                    base_url = (user_input.get(CONF_OPENAI_BASE_URL) or "").strip()
                    self.config_data[CONF_OPENAI_BASE_URL] = (
                        base_url or "https://api.openai.com/v1"
                    )
                    # For OpenAI, move to next step to select model from dynamic list
                    return await self.async_step_configure_openai_models()

                # For OpenAI-Compatible, store Base URL and move to model selection
                if provider == "openai_compatible":
                    base_url = (
                        user_input.get(CONF_OPENAI_COMPATIBLE_URL) or ""
                    ).strip()
                    self.config_data[CONF_OPENAI_COMPATIBLE_URL] = base_url
                    # Move to next step to select model from dynamic list
                    return await self.async_step_configure_openai_compatible_models()

                # Add model configuration if provided
                selected_model = user_input.get("model")
                custom_model = user_input.get("custom_model")

                _LOGGER.debug(
                    f"Config flow - Provider: {provider}, Selected model: {selected_model}, Custom model: {custom_model}"
                )

                # Initialize models dict if it doesn't exist
                if "models" not in self.config_data:
                    self.config_data["models"] = {}

                if custom_model and custom_model.strip():
                    # Use custom model if provided and not empty
                    self.config_data["models"][provider] = custom_model.strip()
                elif selected_model and selected_model != "Custom...":
                    # Use selected model if it's not the "Custom..." option
                    self.config_data["models"][provider] = selected_model
                else:
                    # For local_ollama, openai_compatible, alter, and zai providers, allow empty model name
                    if provider in (
                        "local_ollama",
                        "openai_compatible",
                        "alter",
                        "zai",
                    ):
                        self.config_data["models"][provider] = ""
                    else:
                        # Fallback to default model for other providers
                        self.config_data["models"][provider] = default_model

                return self.async_create_entry(
                    title=f"AI Agent HA ({PROVIDERS[provider]})",
                    data=self.config_data,
                )
            except InvalidApiKey:
                errors["base"] = "invalid_api_key"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        if provider == "zai":
            # For z.ai provider, we need token, endpoint type, and optional model name
            model_options = AVAILABLE_MODELS.get("zai", ["Custom..."])
            schema_dict = {
                vol.Required(token_field): TextSelector(
                    TextSelectorConfig(type="password")
                ),
                vol.Optional("zai_endpoint", default="general"): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "general", "label": "General Purpose"},
                            {"value": "coding", "label": "Coding (3× usage, 1/7 cost)"},
                        ]
                    )
                ),
                vol.Optional("model", default="glm-4.7"): SelectSelector(
                    SelectSelectorConfig(options=model_options)
                ),
                vol.Optional("custom_model"): TextSelector(
                    TextSelectorConfig(type="text")
                ),
            }

            return self.async_show_form(
                step_id="configure",
                data_schema=vol.Schema(schema_dict),
                errors=errors,
                description_placeholders={
                    "token_label": token_label,
                    "provider": PROVIDERS[provider],
                },
            )

        if provider == "local_ollama":
            # For local_ollama provider, we need both URL and optional model name
            schema_dict = {
                vol.Required(CONF_LOCAL_OLLAMA_URL): TextSelector(
                    TextSelectorConfig(type="text")
                ),
            }

            # Add model selection
            model_options = AVAILABLE_MODELS.get("local_ollama", ["Custom..."])
            schema_dict[vol.Optional("model", default="Custom...")] = SelectSelector(
                SelectSelectorConfig(options=model_options)
            )
            schema_dict[vol.Optional("custom_model")] = TextSelector(
                TextSelectorConfig(type="text")
            )

            return self.async_show_form(
                step_id="configure",
                data_schema=vol.Schema(schema_dict),
                errors=errors,
                description_placeholders={
                    "token_label": "Local Ollama API URL",  # nosec B105 - UI label string shown next to the URL field, not a credential
                    "provider": PROVIDERS[provider],
                },
            )

        if provider == "openai_compatible":
            # For openai_compatible provider, we need base URL and optional model name
            # We'll fetch models dynamically in the next step if the endpoint supports it
            schema_dict = {
                vol.Required(CONF_OPENAI_COMPATIBLE_URL): TextSelector(
                    TextSelectorConfig(type="text")
                ),
            }

            return self.async_show_form(
                step_id="configure",
                data_schema=vol.Schema(schema_dict),
                errors=errors,
                description_placeholders={
                    "token_label": "Local OpenAI-Compatible URL",  # nosec B105 - UI label for config form, not a credential
                    "provider": PROVIDERS[provider],
                },
            )

        if provider == "openai":
            # For OpenAI provider, first step: API Key + Base URL
            # Model selection happens in the next step after we fetch available models
            schema_dict = {
                vol.Required(token_field): TextSelector(
                    TextSelectorConfig(type="password")
                ),
                vol.Optional(
                    CONF_OPENAI_BASE_URL,
                    default="https://api.openai.com/v1",
                ): TextSelector(TextSelectorConfig(type="text")),
            }

            return self.async_show_form(
                step_id="configure",
                data_schema=vol.Schema(schema_dict),
                errors=errors,
                description_placeholders={
                    "token_label": token_label,
                    "provider": PROVIDERS[provider],
                },
            )

        # Build schema for other providers
        schema_dict = {
            vol.Required(token_field): TextSelector(
                TextSelectorConfig(type="password")
            ),
        }

        # Add model selection if available
        if available_models:
            # For Gemini, fetch models dynamically
            if provider == "gemini":
                token_value = self.config_data.get("gemini_token")
                model_list = await fetch_gemini_models(token_value)
                if "Custom..." not in model_list:
                    model_list.insert(0, "Custom...")
                model_options = model_list
            else:
                # Add predefined models + custom option (avoid duplicating "Custom...")
                if "Custom..." in available_models:
                    model_options = available_models
                else:
                    model_options = available_models + ["Custom..."]

            schema_dict[vol.Optional("model", default=dropdown_default)] = (
                SelectSelector(SelectSelectorConfig(options=model_options))
            )
            schema_dict[vol.Optional("custom_model")] = TextSelector(
                TextSelectorConfig(type="text")
            )

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "token_label": token_label,
                "provider": PROVIDERS[provider],
            },
        )

    async def async_step_configure_openai_models(self, user_input=None):
        """Handle the OpenAI model selection step with dynamic model list."""
        errors = {}
        provider = "openai"
        token = self.config_data.get("openai_token")
        base_url = self.config_data.get(
            CONF_OPENAI_BASE_URL, "https://api.openai.com/v1"
        )

        # Fetch available models dynamically
        model_list = await fetch_openai_models(base_url, token)

        # Ensure "Custom..." is always available
        if "Custom..." not in model_list:
            model_list.insert(0, "Custom...")

        if user_input is not None:
            try:
                selected_model = user_input.get("model")
                custom_model = user_input.get("custom_model")

                # Initialize models dict if it doesn't exist
                if "models" not in self.config_data:
                    self.config_data["models"] = {}

                if custom_model and custom_model.strip():
                    self.config_data["models"][provider] = custom_model.strip()
                elif selected_model and selected_model != "Custom...":
                    self.config_data["models"][provider] = selected_model
                else:
                    self.config_data["models"][provider] = ""

                return self.async_create_entry(
                    title=f"AI Agent HA ({PROVIDERS[provider]})",
                    data=self.config_data,
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception in OpenAI model selection")
                errors["base"] = "unknown"

        schema_dict = {
            vol.Optional("model", default="Custom..."): SelectSelector(
                SelectSelectorConfig(options=model_list)
            ),
            vol.Optional("custom_model"): TextSelector(TextSelectorConfig(type="text")),
        }

        return self.async_show_form(
            step_id="configure_openai_models",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "provider": PROVIDERS[provider],
            },
        )

    async def async_step_configure_openai_compatible_models(self, user_input=None):
        """Handle the OpenAI-Compatible model selection step with dynamic model list."""
        errors = {}
        provider = "openai_compatible"
        base_url = self.config_data.get(CONF_OPENAI_COMPATIBLE_URL, "")
        api_key = self.config_data.get("openai_compatible_api_key") or ""

        # Fetch available models dynamically if the endpoint supports it
        model_list = await fetch_openai_compatible_models(base_url, api_key or None)

        # Ensure "Custom..." is always available
        if "Custom..." not in model_list:
            model_list.insert(0, "Custom...")

        if user_input is not None:
            try:
                selected_model = user_input.get("model")
                custom_model = user_input.get("custom_model")

                # Initialize models dict if it doesn't exist
                if "models" not in self.config_data:
                    self.config_data["models"] = {}

                if custom_model and custom_model.strip():
                    self.config_data["models"][provider] = custom_model.strip()
                elif selected_model and selected_model != "Custom...":
                    self.config_data["models"][provider] = selected_model
                else:
                    self.config_data["models"][provider] = ""

                return self.async_create_entry(
                    title=f"AI Agent HA ({PROVIDERS[provider]})",
                    data=self.config_data,
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Unexpected exception in OpenAI-Compatible model selection"
                )
                errors["base"] = "unknown"

        schema_dict = {
            vol.Optional("model", default="Custom..."): SelectSelector(
                SelectSelectorConfig(options=model_list)
            ),
            vol.Optional("custom_model"): TextSelector(TextSelectorConfig(type="text")),
        }

        return self.async_show_form(
            step_id="configure_openai_compatible_models",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "provider": PROVIDERS[provider],
            },
        )


class InvalidApiKey(HomeAssistantError):
    """Error to indicate there is an invalid API key."""


class AiAgentHaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for AI Agent HA."""

    def __init__(self):
        """Initialize options flow."""
        self.options_data = {}

    async def async_step_init(self, user_input=None):
        """Handle the initial options step - provider selection."""
        current_provider = self.config_entry.data.get("ai_provider", DEFAULT_PROVIDER)

        if user_input is not None:
            # Store selected provider and move to configure step
            self.options_data = {
                "ai_provider": user_input["ai_provider"],
                "current_provider": current_provider,
            }
            return await self.async_step_configure_options()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "ai_provider", default=current_provider
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": k, "label": v} for k, v in PROVIDERS.items()
                            ]
                        )
                    ),
                }
            ),
            description_placeholders={"current_provider": PROVIDERS[current_provider]},
        )

    async def async_step_configure_options(self, user_input=None):
        """Handle the configuration step for the selected provider in options."""
        errors = {}
        provider = self.options_data["ai_provider"]
        current_provider = self.options_data["current_provider"]
        token_field = TOKEN_FIELD_NAMES[provider]
        token_label = TOKEN_LABELS[provider]

        # Get current configuration
        current_models = self.config_entry.data.get("models", {})
        current_model = current_models.get(provider, DEFAULT_MODELS[provider])
        # For Alter provider, if model is empty, default to "Custom..." for the dropdown
        if provider == "alter" and not current_model:
            current_model = "Custom..."
        current_token = self.config_entry.data.get(token_field, "")
        available_models = AVAILABLE_MODELS.get(provider, [DEFAULT_MODELS[provider]])

        # Use current token if provider hasn't changed, otherwise empty
        display_token = current_token if provider == current_provider else ""

        # Determine if current model is a custom model (not in available models list)
        # and prepare model dropdown and custom model field defaults
        model_options = available_models
        if "Custom..." not in model_options:
            model_options = model_options + ["Custom..."]

        # Check if current_model is a custom model (not in the available models)
        # Remove "Custom..." from the check since it's the selector option, not a real model
        available_models_without_custom = [
            m for m in available_models if m != "Custom..."
        ]
        is_custom_model = (
            current_model
            and current_model not in available_models_without_custom
            and current_model != "Custom..."
        )

        if is_custom_model:
            # Current model is a custom model - show "Custom..." in dropdown and populate custom field
            model_default = "Custom..."
            custom_model_default = current_model
        else:
            # Current model is a standard model or empty
            model_default = current_model if current_model else "Custom..."
            custom_model_default = ""

        if user_input is not None:
            try:
                token_value = user_input.get(token_field)
                if not token_value:
                    errors[token_field] = "required"
                else:
                    # Prepare the updated configuration
                    updated_data = dict(self.config_entry.data)
                    updated_data["ai_provider"] = provider
                    updated_data[token_field] = token_value

                    # Update model configuration
                    selected_model = user_input.get("model")
                    custom_model = user_input.get("custom_model")

                    # For zai, update endpoint type
                    if provider == "zai":
                        endpoint_type = user_input.get("zai_endpoint", "general")
                        updated_data["zai_endpoint"] = endpoint_type

                    # For OpenAI, update Base URL (default to official if blank)
                    if provider == "openai":
                        base_url = (user_input.get(CONF_OPENAI_BASE_URL) or "").strip()
                        updated_data[CONF_OPENAI_BASE_URL] = (
                            base_url or "https://api.openai.com/v1"
                        )

                    # Initialize models dict if it doesn't exist
                    if "models" not in updated_data:
                        updated_data["models"] = {}

                    if custom_model and custom_model.strip():
                        # Use custom model if provided and not empty
                        updated_data["models"][provider] = custom_model.strip()
                    elif selected_model and selected_model != "Custom...":
                        # Use selected model if it's not the "Custom..." option
                        updated_data["models"][provider] = selected_model
                    else:
                        # For local_ollama, openai_compatible, alter, and zai providers, allow empty model name
                        if provider in (
                            "local_ollama",
                            "openai_compatible",
                            "alter",
                            "zai",
                        ):
                            updated_data["models"][provider] = ""
                        else:
                            # Ensure we keep the current model or use default for other providers
                            if provider not in updated_data["models"]:
                                updated_data["models"][provider] = DEFAULT_MODELS[
                                    provider
                                ]

                    _LOGGER.debug(
                        f"Options flow - Final model config for {provider}: {updated_data['models'].get(provider)}"
                    )

                    # Update the config entry data
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=updated_data
                    )

                    # Store updated data for options and move to chat history step
                    self.options_data = {
                        "ai_provider": provider,
                        "current_provider": current_provider,
                        CONF_CHAT_HISTORY_ENABLED: self.config_entry.options.get(
                            CONF_CHAT_HISTORY_ENABLED, DEFAULT_CHAT_HISTORY_ENABLED
                        ),
                        CONF_CHAT_HISTORY_MAX_CONVERSATIONS: self.config_entry.options.get(
                            CONF_CHAT_HISTORY_MAX_CONVERSATIONS, DEFAULT_MAX_CONVERSATIONS
                        ),
                        CONF_CHAT_HISTORY_AUTO_CLEAR_DAYS: self.config_entry.options.get(
                            CONF_CHAT_HISTORY_AUTO_CLEAR_DAYS, DEFAULT_AUTO_CLEAR_DAYS
                        ),
                        CONF_PROMPT_COMPACTION_ENABLED: self.config_entry.options.get(
                            CONF_PROMPT_COMPACTION_ENABLED, DEFAULT_PROMPT_COMPACTION_ENABLED
                        ),
                        CONF_PROMPT_COMPACTION_THRESHOLD: self.config_entry.options.get(
                            CONF_PROMPT_COMPACTION_THRESHOLD, DEFAULT_COMPACTION_THRESHOLD
                        ),
                    }
                    return await self.async_step_chat_history()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception in options flow")
                errors["base"] = "unknown"

        # Build schema for the selected provider in options
        if provider == "zai":
            current_endpoint = self.config_entry.data.get("zai_endpoint", "general")
            model_options = AVAILABLE_MODELS.get("zai", ["glm-4.7"])
            # Ensure "Custom..." is in model options
            if "Custom..." not in model_options:
                model_options = model_options + ["Custom..."]
            schema_dict = {
                vol.Required(token_field, default=display_token): TextSelector(
                    TextSelectorConfig(type="password")
                ),
                vol.Optional("zai_endpoint", default=current_endpoint): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "general", "label": "General Purpose"},
                            {"value": "coding", "label": "Coding (3× usage, 1/7 cost)"},
                        ]
                    )
                ),
                vol.Optional("model", default=model_default): SelectSelector(
                    SelectSelectorConfig(options=model_options)
                ),
                vol.Optional(
                    "custom_model", default=custom_model_default
                ): TextSelector(TextSelectorConfig(type="text")),
            }

            return self.async_show_form(
                step_id="configure_options",
                data_schema=vol.Schema(schema_dict),
                errors=errors,
                description_placeholders={
                    "token_label": token_label,
                    "provider": PROVIDERS[provider],
                },
            )

        if provider == "local_ollama":
            # For local_ollama provider, we need both URL and optional model name
            current_url = self.config_entry.data.get(CONF_LOCAL_OLLAMA_URL, "")

            schema_dict = {
                vol.Required(CONF_LOCAL_OLLAMA_URL, default=current_url): TextSelector(
                    TextSelectorConfig(type="text")
                ),
            }

            # Add model selection
            model_options = AVAILABLE_MODELS.get("local_ollama", ["Custom..."])
            # Ensure "Custom..." is in model options
            if "Custom..." not in model_options:
                model_options = model_options + ["Custom..."]
            schema_dict[vol.Optional("model", default=model_default)] = SelectSelector(
                SelectSelectorConfig(options=model_options)
            )
            schema_dict[vol.Optional("custom_model", default=custom_model_default)] = (
                TextSelector(TextSelectorConfig(type="text"))
            )

            return self.async_show_form(
                step_id="configure_options",
                data_schema=vol.Schema(schema_dict),
                errors=errors,
                description_placeholders={
                    "token_label": "Local Ollama API URL",  # nosec B105 - UI label string shown next to the URL field, not a credential
                    "provider": PROVIDERS[provider],
                },
            )

        if provider == "openai_compatible":
            # For openai_compatible provider, we need URL and optional model name
            current_url = self.config_entry.data.get(CONF_OPENAI_COMPATIBLE_URL, "")

            # Fetch available models dynamically if the endpoint supports it
            api_key = self.config_entry.data.get("openai_compatible_api_key") or ""
            model_list = await fetch_openai_compatible_models(
                current_url, api_key or None
            )

            # Ensure "Custom..." is always available
            if "Custom..." not in model_list:
                model_list.insert(0, "Custom...")

            schema_dict = {
                vol.Required(
                    CONF_OPENAI_COMPATIBLE_URL, default=current_url
                ): TextSelector(TextSelectorConfig(type="text")),
            }

            # Add model selection with dynamic list
            schema_dict[vol.Optional("model", default=model_default)] = SelectSelector(
                SelectSelectorConfig(options=model_list)
            )
            schema_dict[vol.Optional("custom_model", default=custom_model_default)] = (
                TextSelector(TextSelectorConfig(type="text"))
            )

            return self.async_show_form(
                step_id="configure_options",
                data_schema=vol.Schema(schema_dict),
                errors=errors,
                description_placeholders={
                    "token_label": "Local OpenAI-Compatible URL",  # nosec B105 - UI label for config form, not a credential
                    "provider": PROVIDERS[provider],
                },
            )

        if provider == "openai":
            # For OpenAI provider, we need token and optional Base URL
            # Pre-fill with official endpoint if not set
            current_base_url = (
                self.config_entry.data.get(CONF_OPENAI_BASE_URL)
                or "https://api.openai.com/v1"
            )

            # Fetch available models dynamically
            current_token = self.config_entry.data.get("openai_token", "")
            model_list = await fetch_openai_models(current_base_url, current_token)

            # Ensure "Custom..." is always available
            if "Custom..." not in model_list:
                model_list.insert(0, "Custom...")

            schema_dict = {
                vol.Required(token_field, default=display_token): TextSelector(
                    TextSelectorConfig(type="password")
                ),
                vol.Optional(
                    CONF_OPENAI_BASE_URL, default=current_base_url
                ): TextSelector(TextSelectorConfig(type="text")),
            }

            # Add model selection with dynamic list
            schema_dict[vol.Optional("model", default=model_default)] = SelectSelector(
                SelectSelectorConfig(options=model_list)
            )
            schema_dict[vol.Optional("custom_model", default=custom_model_default)] = (
                TextSelector(TextSelectorConfig(type="text"))
            )

            return self.async_show_form(
                step_id="configure_options",
                data_schema=vol.Schema(schema_dict),
                errors=errors,
                description_placeholders={
                    "token_label": token_label,
                    "provider": PROVIDERS[provider],
                },
            )

        # Build schema for other providers
        schema_dict = {
            vol.Required(token_field, default=display_token): TextSelector(
                TextSelectorConfig(type="password")
            ),
        }

        # Add model selection if available
        if available_models:
            # For Gemini, fetch models dynamically
            if provider == "gemini":
                current_token = self.config_entry.data.get("gemini_token", "")
                model_list = await fetch_gemini_models(current_token)
                if "Custom..." not in model_list:
                    model_list.insert(0, "Custom...")
                model_options = model_list
            # model_options already has "Custom..." added above for other providers

            schema_dict[vol.Optional("model", default=model_default)] = SelectSelector(
                SelectSelectorConfig(options=model_options)
            )
            schema_dict[vol.Optional("custom_model", default=custom_model_default)] = (
                TextSelector(TextSelectorConfig(type="text"))
            )

        return self.async_show_form(
            step_id="configure_options",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "token_label": token_label,
                "provider": PROVIDERS[provider],
            },
        )

    async def async_step_chat_history(self, user_input=None):
        """Handle the chat history options step."""
        errors = {}

        if user_input is not None:
            # Store the chat history options
            self.options_data.update(user_input)
            return await self.async_step_permission_options()

        current_enabled = self.config_entry.options.get(
            CONF_CHAT_HISTORY_ENABLED, DEFAULT_CHAT_HISTORY_ENABLED
        )
        current_max = self.config_entry.options.get(
            CONF_CHAT_HISTORY_MAX_CONVERSATIONS, DEFAULT_MAX_CONVERSATIONS
        )
        current_clear_days = self.config_entry.options.get(
            CONF_CHAT_HISTORY_AUTO_CLEAR_DAYS, DEFAULT_AUTO_CLEAR_DAYS
        )

        schema_dict = {
            vol.Required(
                CONF_CHAT_HISTORY_ENABLED, default=current_enabled
            ): BooleanSelector(),
            vol.Required(
                CONF_CHAT_HISTORY_MAX_CONVERSATIONS, default=current_max
            ): NumberSelector(
                NumberSelectorConfig(min=5, max=500, step=5, mode="slider")
            ),
            vol.Required(
                CONF_CHAT_HISTORY_AUTO_CLEAR_DAYS, default=current_clear_days
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=365, step=1, mode="slider")
            ),
        }

        return self.async_show_form(
            step_id="chat_history",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_permission_options(self, user_input=None):
        """Handle the permission system options step."""
        errors = {}

        if user_input is not None:
            # Store the permission options
            self.options_data.update(user_input)
            return await self.async_step_prompt_compaction()

        current_mode = self.config_entry.options.get(
            CONF_PERMISSION_MODE, DEFAULT_PERMISSION_MODE
        )
        current_timeout = self.config_entry.options.get(
            CONF_PERMISSION_TIMEOUT, DEFAULT_PERMISSION_TIMEOUT
        )

        schema_dict = {
            vol.Required(
                CONF_PERMISSION_MODE, default=current_mode
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "prompt", "label": "Prompt - Always ask for permission"},
                        {"value": "auto_allow", "label": "Auto Allow - Allow all by default"},
                        {"value": "auto_deny", "label": "Auto Deny - Deny all by default"},
                    ]
                )
            ),
            vol.Required(
                CONF_PERMISSION_TIMEOUT, default=current_timeout
            ): NumberSelector(
                NumberSelectorConfig(min=10, max=300, step=10, mode="slider")
            ),
        }

        return self.async_show_form(
            step_id="permission_options",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_prompt_compaction(self, user_input=None):
        """Handle the prompt compaction options step."""
        errors = {}

        if user_input is not None:
            # Store the compaction options in the config entry options
            self.options_data.update(user_input)
            return await self.async_step_multimedia_options()

        current_enabled = self.config_entry.options.get(
            CONF_PROMPT_COMPACTION_ENABLED, DEFAULT_PROMPT_COMPACTION_ENABLED
        )
        current_threshold = self.config_entry.options.get(
            CONF_PROMPT_COMPACTION_THRESHOLD, DEFAULT_COMPACTION_THRESHOLD
        )

        schema_dict = {
            vol.Required(
                CONF_PROMPT_COMPACTION_ENABLED, default=current_enabled
            ): BooleanSelector(),
            vol.Required(
                CONF_PROMPT_COMPACTION_THRESHOLD, default=current_threshold
            ): NumberSelector(
                NumberSelectorConfig(min=0.5, max=0.95, step=0.05, mode="slider")
            ),
        }

        return self.async_show_form(
            step_id="prompt_compaction",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_multimedia_options(self, user_input=None):
        """Handle the multimedia options step."""
        errors = {}

        if user_input is not None:
            # Store the multimedia options in the config entry options
            self.options_data.update(user_input)
            return self.async_create_entry(title="", data=self.options_data)

        current_multimodal_enabled = self.config_entry.options.get(
            CONF_MULTIMODAL_ENABLED, DEFAULT_MULTIMODAL_ENABLED
        )
        current_image_upload_enabled = self.config_entry.options.get(
            CONF_IMAGE_UPLOAD_ENABLED, DEFAULT_IMAGE_UPLOAD_ENABLED
        )
        current_max_image_size = self.config_entry.options.get(
            CONF_MAX_IMAGE_SIZE, DEFAULT_MAX_IMAGE_SIZE
        )
        current_max_images = self.config_entry.options.get(
            CONF_MAX_IMAGES_PER_MESSAGE, DEFAULT_MAX_IMAGES_PER_MESSAGE
        )
        current_quality = self.config_entry.options.get(
            CONF_IMAGE_COMPRESSION_QUALITY, DEFAULT_IMAGE_COMPRESSION_QUALITY
        )

        # Convert max_image_size to MB for user-friendly display
        size_options = [
            {"value": 1 * 1024 * 1024, "label": "1 MB"},
            {"value": 5 * 1024 * 1024, "label": "5 MB"},
            {"value": 10 * 1024 * 1024, "label": "10 MB"},
            {"value": 20 * 1024 * 1024, "label": "20 MB"},
        ]
        # Ensure current value is in the list
        if not any(opt["value"] == current_max_image_size for opt in size_options):
            size_mb = current_max_image_size / (1024 * 1024)
            size_options.append({"value": current_max_image_size, "label": f"{size_mb:.0f} MB"})

        schema_dict = {
            vol.Required(
                CONF_MULTIMODAL_ENABLED, default=current_multimodal_enabled
            ): BooleanSelector(),
            vol.Required(
                CONF_IMAGE_UPLOAD_ENABLED, default=current_image_upload_enabled
            ): BooleanSelector(),
            vol.Required(
                CONF_MAX_IMAGE_SIZE, default=current_max_image_size
            ): SelectSelector(
                SelectSelectorConfig(options=size_options)
            ),
            vol.Required(
                CONF_MAX_IMAGES_PER_MESSAGE, default=current_max_images
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=10, step=1, mode="slider")
            ),
            vol.Required(
                CONF_IMAGE_COMPRESSION_QUALITY, default=current_quality
            ): NumberSelector(
                NumberSelectorConfig(min=50, max=100, step=5, mode="slider")
            ),
        }

        return self.async_show_form(
            step_id="multimedia_options",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
