"""The AI Agent implementation with multiple provider support.

Example config:
ai_agent_ha:
  ai_provider: openai  # or 'llama', 'gemini', 'openrouter', 'anthropic', 'alter', 'zai', 'local_ollama', 'openai_compatible'
  llama_token: "..."
  openai_token: "..."
  gemini_token: "..."
  openrouter_token: "..."
  anthropic_token: "..."
  alter_token: "..."
  zai_token: "..."
  zai_endpoint: "general"  # or 'coding' for z.ai (3× usage, 1/7 cost)
  local_ollama_url: "http://localhost:11434/api/generate"  # Required for local_ollama provider
  openai_compatible_url: "http://example.com/v1/" or "http://localhost/v1/"  # (Url must end with /v1/)
  # Model configuration (optional, defaults will be used if not specified)
  models:
    openai: "gpt-3.5-turbo"  # or "gpt-4", "gpt-4-turbo", etc.
    llama: "Llama-4-Maverick-17B-128E-Instruct-FP8"
    gemini: "gemini-2.5-flash"  # or "gemini-2.5-pro", "gemini-2.0-flash", etc.
    openrouter: "openai/gpt-4o"  # or any model available on OpenRouter
    anthropic: "claude-sonnet-4-5-20250929"  # or "claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229", etc.
    alter: "your-model-name"  # model name for Alter API
    zai: "glm-4.7"  # model name for z.ai API (glm-4.7, glm-4.6, glm-4.5, etc.)
    local_ollama: "llama3.2"  # model name for local_ollama provider (optional if your API doesn't require it)
    openai_compatible: "model unique-id or your-model-name"  # model name for your OpenAI-compatible endpoint
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

import aiohttp
import yaml  # type: ignore[import-untyped]
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_OPENAI_BASE_URL,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    CONF_PROMPT_COMPACTION_THRESHOLD,
    DEFAULT_PROMPT_COMPACTION_ENABLED,
    CONF_PERMISSION_MODE,
    CONF_PERMISSION_TIMEOUT,
    CONF_PERMISSION_WHITELIST,
    CONF_PERMISSION_BLACKLIST,
    DEFAULT_PERMISSION_MODE,
    DEFAULT_PERMISSION_TIMEOUT,
    # Multimedia settings
    CONF_MULTIMODAL_ENABLED,
    CONF_IMAGE_UPLOAD_ENABLED,
    CONF_MAX_IMAGE_SIZE,
    CONF_MAX_IMAGES_PER_MESSAGE,
    CONF_IMAGE_COMPRESSION_QUALITY,
)
from .yaml_review import YAMLReviewer
from .permissions import (
    PermissionChecker,
    PermissionRule,
    PermissionRequest,
    PERMIT,
    DENY,
    PROMPT,
    PERMISSION_MODE_PROMPT,
)
from .ha_documentation import HADocumentationProvider
from .log_analyzer import LogAnalyzer
from .error_diagnosis import ErrorDiagnosisAssistant
from .automation_troubleshooter import AutomationTroubleshooter
from .entity_discovery import EntityDiscoveryAssistant
from .config_validator import ConfigurationValidator
from .backup_advisor import BackupAdvisor
from .energy_advisor import EnergyAdvisor
from .security_audit import SecurityAuditor
from .nl_to_automation import NLToAutomationConverter
from .dashboard_advisor import DashboardAdvisor
from .integration_guide import IntegrationGuideProvider
from .prompt_compactor import PromptCompactor, ConversationSummary
from .chat_history import ChatHistoryManager
from .multimedia import MultimediaProcessor, ImageAttachment

_LOGGER = logging.getLogger(__name__)


# === Security Utilities ===
def sanitize_for_logging(data: Any, mask: str = "***REDACTED***") -> Any:
    """Sanitize sensitive data for safe logging.

    Recursively masks sensitive fields like API keys, tokens, passwords, etc.
    This prevents accidental exposure of credentials in debug logs.

    Args:
        data: The data structure to sanitize (dict, list, str, etc.)
        mask: The string to use for masking sensitive values

    Returns:
        A sanitized copy of the data with sensitive fields masked

    Example:
        >>> config = {"openai_token": "sk-abc123", "ai_provider": "openai"}
        >>> sanitize_for_logging(config)
        {"openai_token": "***REDACTED***", "ai_provider": "openai"}
    """
    # Sensitive field patterns (case-insensitive)
    sensitive_patterns = {
        "token",
        "key",
        "password",
        "secret",
        "credential",
        "auth",
        "authorization",
        "api_key",
        "apikey",
        "llama_token",
        "openai_token",
        "gemini_token",
        "anthropic_token",
        "openrouter_token",
        "alter_token",
        "zai_token",
    }

    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Check if key matches any sensitive pattern
            key_lower = str(key).lower()
            is_sensitive = any(pattern in key_lower for pattern in sensitive_patterns)

            if is_sensitive:
                sanitized[key] = mask
            else:
                # Recursively sanitize nested structures
                sanitized[key] = sanitize_for_logging(value, mask)
        return sanitized

    elif isinstance(data, list):
        return [sanitize_for_logging(item, mask) for item in data]

    elif isinstance(data, tuple):
        return tuple(sanitize_for_logging(item, mask) for item in data)

    else:
        # Primitive types (str, int, bool, etc.) - return as-is
        return data


# === AI Client Abstractions ===
class BaseAIClient:
    async def get_response(self, messages, **kwargs):
        raise NotImplementedError


class LocalOllamaClient(BaseAIClient):
    """Client for Ollama-style local models using /api/generate style endpoints."""

    def __init__(self, url, model=""):
        self.url = url
        self.model = model

    async def get_response(self, messages, **kwargs):
        _LOGGER.debug(
            "Making request to local Ollama API with model: '%s' at URL: %s",
            self.model or "[NO MODEL SPECIFIED]",
            self.url,
        )

        if not self.model:
            _LOGGER.warning(
                "No model specified for local Ollama API request. Some APIs (like Ollama) require a model name."
            )
        headers = {"Content-Type": "application/json"}

        # Format user prompt from messages
        prompt = ""
        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")

            # Simple formatting: prefixing each message with its role
            if role == "system":
                prompt += f"System: {content}\n\n"
            elif role == "user":
                prompt += f"User: {content}\n\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n\n"

        # Add final prompt prefix for the assistant's response
        prompt += "Assistant: "

        # Build a generic payload that works with most local Ollama-style API servers
        payload = {
            "prompt": prompt,
            "stream": False,  # Disable streaming to get a single complete response
            # max_tokens omitted - let local model use its default capacity
        }

        # Add model if specified
        if self.model:
            payload["model"] = self.model

        # Note: Payloads don't contain auth tokens (those are in headers), but may contain user prompts
        _LOGGER.debug(
            "Local Ollama API request payload: %s", json.dumps(payload, indent=2)
        )

        # Ollama-specific validation
        if "model" not in payload or not payload["model"]:
            _LOGGER.warning(
                "Missing 'model' field in request to local Ollama API. This may cause issues with Ollama."
            )
        elif self.url and "ollama" in self.url.lower():
            _LOGGER.debug(
                "Detected Ollama URL, ensuring model is specified: %s",
                payload.get("model"),
            )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    _LOGGER.error(
                        "Local Ollama API error %d: %s", resp.status, error_text
                    )

                    # Provide more specific error messages for common Ollama issues
                    if resp.status == 404:
                        if "model" in payload and payload["model"]:
                            raise Exception(
                                f"Model '{payload['model']}' not found. Please ensure the model is installed in Ollama using: ollama pull {payload['model']}"
                            )
                        else:
                            raise Exception(
                                "Local Ollama API endpoint not found. Please check the URL and ensure Ollama is running."
                            )
                    elif resp.status == 400:
                        raise Exception(
                            f"Bad request to local Ollama API. Error: {error_text}"
                        )
                    else:
                        raise Exception(
                            f"Local Ollama API error {resp.status}: {error_text}"
                        )

                try:
                    response_text = await resp.text()
                    _LOGGER.debug(
                        "Local Ollama API response (first 200 chars): %s",
                        response_text[:200],
                    )
                    _LOGGER.debug("Local Ollama API response status: %d", resp.status)
                    # Sanitize headers to avoid logging any auth tokens
                    _LOGGER.debug(
                        "Local Ollama API response headers: %s",
                        sanitize_for_logging(dict(resp.headers)),
                    )

                    # Try to parse as JSON
                    try:
                        data = json.loads(response_text)

                        # Try common response formats
                        # Ollama format - return only the response text
                        if "response" in data:
                            response_content = data["response"]
                            _LOGGER.debug(
                                "Extracted response content: %s",
                                (
                                    response_content[:100]
                                    if response_content
                                    else "[EMPTY]"
                                ),
                            )

                            # Check if response is empty or None
                            if not response_content or response_content.strip() == "":
                                _LOGGER.warning(
                                    "Ollama returned empty response. Full data: %s",
                                    data,
                                )
                                # Check if this is a loading response
                                if data.get("done_reason") == "load":
                                    _LOGGER.warning(
                                        "Ollama is still loading the model. Please wait and try again."
                                    )
                                    return json.dumps(
                                        {
                                            "request_type": "final_response",
                                            "response": "The AI model is still loading. Please wait a moment and try again.",
                                        }
                                    )
                                elif data.get("done") is False:
                                    _LOGGER.warning(
                                        "Ollama response indicates it's not done yet."
                                    )
                                    return json.dumps(
                                        {
                                            "request_type": "final_response",
                                            "response": "The AI is still processing your request. Please try again.",
                                        }
                                    )
                                else:
                                    return json.dumps(
                                        {
                                            "request_type": "final_response",
                                            "response": "The AI returned an empty response. Please try rephrasing your question.",
                                        }
                                    )

                            # Check if the response looks like JSON
                            response_content = response_content.strip()
                            if response_content.startswith(
                                "{"
                            ) and response_content.endswith("}"):
                                try:
                                    # Validate that it's actually JSON and contains valid request_type
                                    parsed_json = json.loads(response_content)
                                    if (
                                        isinstance(parsed_json, dict)
                                        and "request_type" in parsed_json
                                    ):
                                        _LOGGER.debug(
                                            "Local Ollama model provided valid JSON response"
                                        )
                                        return response_content
                                    else:
                                        _LOGGER.debug(
                                            "JSON missing request_type, treating as plain text"
                                        )
                                except json.JSONDecodeError:
                                    _LOGGER.debug(
                                        "Invalid JSON from local Ollama model, treating as plain text"
                                    )
                                    pass

                            # If it's plain text, wrap it in the expected JSON format
                            wrapped_response = {
                                "request_type": "final_response",
                                "response": response_content,
                            }
                            _LOGGER.debug("Wrapped plain text response in JSON format")
                            return json.dumps(wrapped_response)

                        # OpenAI-like format
                        elif "choices" in data and len(data["choices"]) > 0:
                            choice = data["choices"][0]
                            if "message" in choice and "content" in choice["message"]:
                                content = choice["message"]["content"]
                            elif "text" in choice:
                                content = choice["text"]
                            else:
                                content = str(data)

                            # Check if it's valid JSON with request_type
                            content = content.strip()
                            if content.startswith("{") and content.endswith("}"):
                                try:
                                    parsed_json = json.loads(content)
                                    if (
                                        isinstance(parsed_json, dict)
                                        and "request_type" in parsed_json
                                    ):
                                        _LOGGER.debug(
                                            "Local Ollama model provided valid JSON response (OpenAI format)"
                                        )
                                        return content
                                    else:
                                        _LOGGER.debug(
                                            "JSON missing request_type, treating as plain text (OpenAI format)"
                                        )
                                except json.JSONDecodeError:
                                    _LOGGER.debug(
                                        "Invalid JSON from local Ollama model, treating as plain text (OpenAI format)"
                                    )
                                    pass

                            # Wrap in expected format if plain text
                            wrapped_response = {
                                "request_type": "final_response",
                                "response": content,
                            }
                            return json.dumps(wrapped_response)

                        # Generic content field
                        elif "content" in data:
                            content = data["content"]
                            content = content.strip()
                            if content.startswith("{") and content.endswith("}"):
                                try:
                                    parsed_json = json.loads(content)
                                    if (
                                        isinstance(parsed_json, dict)
                                        and "request_type" in parsed_json
                                    ):
                                        _LOGGER.debug(
                                            "Local Ollama model provided valid JSON response (generic format)"
                                        )
                                        return content
                                    else:
                                        _LOGGER.debug(
                                            "JSON missing request_type, treating as plain text (generic format)"
                                        )
                                except json.JSONDecodeError:
                                    _LOGGER.debug(
                                        "Invalid JSON from local Ollama model, treating as plain text (generic format)"
                                    )
                                    pass

                            wrapped_response = {
                                "request_type": "final_response",
                                "response": content,
                            }
                            return json.dumps(wrapped_response)

                        # Handle case where no standard fields are found
                        _LOGGER.warning(
                            "No standard response fields found in local Ollama API response. Full response: %s",
                            data,
                        )

                        # Check for Ollama-specific edge cases
                        if data.get("done_reason") == "load":
                            return json.dumps(
                                {
                                    "request_type": "final_response",
                                    "response": "The AI model is still loading. Please wait a moment and try again.",
                                }
                            )
                        elif data.get("done") is False:
                            return json.dumps(
                                {
                                    "request_type": "final_response",
                                    "response": "The AI is still processing your request. Please try again.",
                                }
                            )
                        elif "message" in data:
                            # Some APIs use "message" field
                            message_content = data["message"]
                            if (
                                isinstance(message_content, dict)
                                and "content" in message_content
                            ):
                                content = message_content["content"]
                            else:
                                content = str(message_content)
                            return json.dumps(
                                {"request_type": "final_response", "response": content}
                            )

                        # Return the whole data as string if we can't find a specific field
                        return json.dumps(
                            {
                                "request_type": "final_response",
                                "response": f"Received unexpected response format from local Ollama API: {str(data)}",
                            }
                        )

                    except json.JSONDecodeError:
                        # If not JSON, check if it's a JSON response that got corrupted by wrapping
                        response_text = response_text.strip()
                        if response_text.startswith("{") and response_text.endswith(
                            "}"
                        ):
                            try:
                                parsed_json = json.loads(response_text)
                                if (
                                    isinstance(parsed_json, dict)
                                    and "request_type" in parsed_json
                                ):
                                    _LOGGER.debug(
                                        "Local Ollama model provided valid JSON response (direct)"
                                    )
                                    return response_text
                            except json.JSONDecodeError:
                                pass

                        # If not valid JSON, wrap the raw text in expected format
                        _LOGGER.debug("Response is not JSON, wrapping plain text")
                        wrapped_response = {
                            "request_type": "final_response",
                            "response": response_text,
                        }
                        return json.dumps(wrapped_response)

                except Exception as e:
                    _LOGGER.error(
                        "Failed to parse local Ollama API response: %s", str(e)
                    )
                    raise Exception(
                        f"Failed to parse local Ollama API response: {str(e)}"
                    )


class OpenaiCompatibleClient(BaseAIClient):
    """Client for OpenAI-compatible endpoints (e.g., LM Studio, vLLM, etc.).

    Expected URL format: http://example.com/v1/
    This client sends chat completions requests to: {url}/chat/completions
    No API key is required by default, but can be provided if needed.
    """

    def __init__(self, base_url, model="", api_key=None):
        # Ensure base_url ends with /v1/ style segment
        base_url = (base_url or "").strip().rstrip("/")
        if not base_url:
            raise Exception("openai_compatible_url is required and must not be empty")
        self.base_url = base_url
        # Derive chat completions endpoint
        self.api_url = f"{self.base_url}/chat/completions"
        self.model = model
        self.api_key = api_key or ""  # Optional; many local endpoints don’t require it

    async def get_response(self, messages, **kwargs):
        _LOGGER.debug(
            "Making request to OpenAI-compatible endpoint at %s with model: %s",
            self.api_url,
            self.model or "[NO MODEL SPECIFIED]",
        )

        if not self.model:
            _LOGGER.warning(
                "No model specified for OpenAI-compatible request. Some servers require a model name."
            )

        headers = {
            "Content-Type": "application/json",
        }

        # Add Authorization header only if an API key is set
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.9,
            # max_tokens omitted - let server/model use its default capacity
        }

        _LOGGER.debug(
            "OpenAI-compatible request payload: %s",
            json.dumps(payload, indent=2),
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                response_text = await resp.text()
                _LOGGER.debug("OpenAI-compatible API response status: %d", resp.status)
                _LOGGER.debug(
                    "OpenAI-compatible API response (first 500 chars): %s",
                    response_text[:500],
                )

                if resp.status != 200:
                    _LOGGER.error(
                        "OpenAI-compatible API error %d: %s",
                        resp.status,
                        response_text,
                    )
                    raise Exception(
                        f"OpenAI-compatible API error {resp.status}: {response_text}"
                    )

                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    _LOGGER.error(
                        "Failed to parse OpenAI-compatible response as JSON: %s", str(e)
                    )
                    raise Exception(
                        f"Invalid JSON response from OpenAI-compatible API: {response_text[:200]}"
                    )

                # Extract text from OpenAI-compatible response
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "")
                    if not content:
                        _LOGGER.warning(
                            "OpenAI-compatible API returned empty content in message"
                        )
                        _LOGGER.debug(
                            "Full OpenAI-compatible API response: %s",
                            json.dumps(data, indent=2),
                        )
                    return content
                else:
                    _LOGGER.warning(
                        "OpenAI-compatible API response missing expected structure"
                    )
                    _LOGGER.debug(
                        "Full OpenAI-compatible API response: %s",
                        json.dumps(data, indent=2),
                    )
                    return str(data)


class LlamaClient(BaseAIClient):
    def __init__(self, token, model="Llama-4-Maverick-17B-128E-Instruct-FP8"):
        self.token = token
        self.model = model
        self.api_url = "https://api.llama.com/v1/chat/completions"

    async def get_response(self, messages, **kwargs):
        _LOGGER.debug("Making request to Llama API with model: %s", self.model)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.9,
            # max_tokens omitted - let Llama use the model's default capacity
        }

        _LOGGER.debug("Llama request payload: %s", json.dumps(payload, indent=2))

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    _LOGGER.error("Llama API error %d: %s", resp.status, error_text)
                    raise Exception(f"Llama API error {resp.status}")
                data = await resp.json()
                # Extract text from Llama response
                completion = data.get("completion_message", {})
                content = completion.get("content", {})
                return content.get("text", str(data))


async def fetch_openai_models(base_url, api_key, timeout=10):
    """Fetch available OpenAI models dynamically.

    Returns a list of model IDs suitable for chat (gpt-*, o*). On failure,
    returns a small safe fallback list.
    """
    if not base_url:
        base_url = "https://api.openai.com/v1"
    url = f"{base_url.rstrip('/')}/models"

    fallback_models = [
        "gpt-4.1-mini",
        "gpt-4o-mini",
        "o4-mini",
    ]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "Failed to fetch OpenAI models (status=%d), using fallback list",
                        resp.status,
                    )
                    return fallback_models

                data = await resp.json()
                models = data.get("data", [])
                if not isinstance(models, list):
                    return fallback_models

                # Filter likely chat-capable models
                chat_models = []
                for m in models:
                    mid = m.get("id", "")
                    if isinstance(mid, str) and (
                        mid.startswith("gpt-") or mid.startswith("o")
                    ):
                        chat_models.append(mid)

                if not chat_models:
                    return fallback_models

                chat_models.sort()
                _LOGGER.debug("Fetched %d OpenAI chat models", len(chat_models))
                return chat_models

    except Exception as e:
        _LOGGER.warning("Error fetching OpenAI models, using fallback list: %s", e)
        return fallback_models


async def fetch_gemini_models(api_key, timeout=10):
    """Fetch available Gemini models dynamically.

    Returns a list of model IDs suitable for chat. On failure,
    returns a small safe fallback list.
    """
    if not api_key:
        return [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ]

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

    fallback_models = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "Failed to fetch Gemini models (status=%d), using fallback list",
                        resp.status,
                    )
                    return fallback_models

                data = await resp.json()
                models = data.get("models", [])
                if not isinstance(models, list):
                    return fallback_models

                # Filter likely chat-capable models
                chat_models = []
                for m in models:
                    mid = m.get("name", "")
                    if isinstance(mid, str) and "gemini" in mid.lower():
                        # Extract model ID from name like "models/gemini-2.5-flash"
                        model_id = mid.split("/")[-1] if "/" in mid else mid
                        chat_models.append(model_id)

                if not chat_models:
                    return fallback_models

                chat_models.sort()
                _LOGGER.debug("Fetched %d Gemini models", len(chat_models))
                return chat_models

    except Exception as e:
        _LOGGER.warning("Error fetching Gemini models, using fallback list: %s", e)
        return fallback_models


async def fetch_openai_compatible_models(base_url, api_key=None, timeout=10):
    """Fetch available models from an OpenAI-compatible endpoint.

    Many local/self-hosted endpoints (LM Studio, vLLM, etc.) support /v1/models.
    If the endpoint does not support it, fall back to ["Custom..."] only.
    """
    if not base_url:
        return ["Custom..."]

    url = f"{base_url.rstrip('/')}/models"

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status not in (200, 201):
                    _LOGGER.debug(
                        "OpenAI-compatible endpoint did not support /v1/models (status=%d)",
                        resp.status,
                    )
                    return ["Custom..."]

                data = await resp.json()
                models = data.get("data", [])
                if not isinstance(models, list):
                    return ["Custom..."]

                # Collect all model IDs
                model_ids = []
                for m in models:
                    mid = m.get("id", "")
                    if isinstance(mid, str) and mid:
                        model_ids.append(mid)

                if not model_ids:
                    return ["Custom..."]

                model_ids.sort()
                _LOGGER.debug(
                    "Fetched %d models from OpenAI-compatible endpoint", len(model_ids)
                )
                return model_ids

    except Exception as e:
        _LOGGER.debug(
            "Error fetching models from OpenAI-compatible endpoint, using Custom only: %s",
            e,
        )
        return ["Custom..."]


class OpenAIClient(BaseAIClient):
    def __init__(self, token, model="gpt-4.1-mini", base_url=None):
        self.token = token
        self.model = model
        # Use custom base_url if provided; otherwise default to official OpenAI endpoint
        if base_url and base_url.strip():
            base = base_url.strip().rstrip("/")
            self.api_url = f"{base}/responses"
        else:
            self.api_url = "https://api.openai.com/v1/responses"

    def _is_restricted_model(self):
        """Check if the model has restricted parameters (no temperature, top_p, etc.)."""
        # Models that don't support temperature, top_p and other parameters
        restricted_models = ["o3-mini", "o3", "o1-mini", "o1-preview", "o1", "gpt-5"]

        model_lower = self.model.lower()
        return any(model_id in model_lower for model_id in restricted_models)

    async def get_response(self, messages, **kwargs):
        _LOGGER.debug("Making request to OpenAI API with model: %s", self.model)

        # Validate token
        if not self.token or not self.token.startswith("sk-"):
            raise Exception("Invalid OpenAI API key format")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Build input string from messages for the Responses API
        # Preserve system instructions and conversation history in a simple format
        parts = []
        for msg in messages:
            role = (msg.get("role") or "user").lower()
            content = msg.get("content") or ""
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"{role.capitalize()}: {content}")

        input_text = "\n\n".join(parts)

        # Build payload for /v1/responses
        payload = {
            "model": self.model,
            "input": input_text,
        }

        _LOGGER.debug("OpenAI request payload: %s", json.dumps(payload, indent=2))

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                response_text = await resp.text()
                _LOGGER.debug("OpenAI API response status: %d", resp.status)
                _LOGGER.debug("OpenAI API response: %s", response_text[:500])

                if resp.status != 200:
                    _LOGGER.error("OpenAI API error %d: %s", resp.status, response_text)
                    raise Exception(f"OpenAI API error {resp.status}: {response_text}")

                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    _LOGGER.error("Failed to parse OpenAI response as JSON: %s", str(e))
                    raise Exception(
                        f"Invalid JSON response from OpenAI: {response_text[:200]}"
                    )

                # Extract text from OpenAI Responses API
                # Primary field: output_text
                content = data.get("output_text")
                if content:
                    return content

                # Fallback: if response has 'output' list with text content
                output = data.get("output")
                if isinstance(output, list):
                    for item in output:
                        if isinstance(item, dict):
                            tc = item.get("text") or item.get("content")
                            if tc:
                                return tc

                # Last resort: return full response as string
                _LOGGER.warning("OpenAI response missing expected structure")
                _LOGGER.debug("Full OpenAI response: %s", json.dumps(data, indent=2))
                return str(data)


class GeminiClient(BaseAIClient):
    def __init__(self, token, model="gemini-2.5-flash"):
        self.token = token.strip() if token else token  # Strip whitespace from token
        self.model = model
        # Use v1beta for all models as per Google's current API documentation
        # All Gemini 2.0/2.5 models are available on v1beta endpoint
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    async def get_response(self, messages, **kwargs):
        _LOGGER.debug("Making request to Gemini API with model: %s", self.model)

        # Validate token
        if not self.token:
            raise Exception("Missing Gemini API key")

        headers = {"Content-Type": "application/json"}

        # Convert OpenAI-style messages to Gemini format
        gemini_contents = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                # Gemini doesn't have a system role, so we prepend it to the first user message
                if not gemini_contents:
                    gemini_contents.append(
                        {"role": "user", "parts": [{"text": f"System: {content}"}]}
                    )
                else:
                    # Add system message as user message
                    gemini_contents.append(
                        {"role": "user", "parts": [{"text": f"System: {content}"}]}
                    )
            elif role == "user":
                gemini_contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                gemini_contents.append({"role": "model", "parts": [{"text": content}]})

        payload = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.9,
                # maxOutputTokens omitted - let Gemini use model's maximum capacity
            },
        }

        # Add API key as query parameter (URL encoded)
        url_with_key = f"{self.api_url}?key={quote(self.token)}"

        _LOGGER.debug("Gemini request payload: %s", json.dumps(payload, indent=2))

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url_with_key,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                response_text = await resp.text()
                _LOGGER.debug("Gemini API response status: %d", resp.status)
                _LOGGER.debug("Gemini API response: %s", response_text[:500])

                if resp.status != 200:
                    _LOGGER.error("Gemini API error %d: %s", resp.status, response_text)
                    raise Exception(f"Gemini API error {resp.status}: {response_text}")

                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    _LOGGER.error("Failed to parse Gemini response as JSON: %s", str(e))
                    raise Exception(
                        f"Invalid JSON response from Gemini: {response_text[:200]}"
                    )

                # Log token usage for debugging, especially for Gemini 2.5 extended thinking
                usage_metadata = data.get("usageMetadata", {})
                if usage_metadata:
                    _LOGGER.debug(
                        "Gemini token usage - prompt: %d, total: %d, thoughts: %d",
                        usage_metadata.get("promptTokenCount", 0),
                        usage_metadata.get("totalTokenCount", 0),
                        usage_metadata.get("thoughtsTokenCount", 0),
                    )

                # Extract text from Gemini response
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    # Check finish reason for potential issues
                    finish_reason = candidates[0].get("finishReason", "")
                    if finish_reason == "MAX_TOKENS":
                        _LOGGER.warning(
                            "Gemini response truncated due to MAX_TOKENS limit. "
                            "Thoughts used: %d tokens. Consider increasing maxOutputTokens.",
                            usage_metadata.get("thoughtsTokenCount", 0),
                        )

                    parts = candidates[0]["content"].get("parts", [])
                    if parts:
                        content = parts[0].get("text", "")
                        if not content:
                            _LOGGER.warning("Gemini returned empty text content")
                            _LOGGER.debug(
                                "Full Gemini response: %s", json.dumps(data, indent=2)
                            )
                        return content
                    else:
                        _LOGGER.warning("Gemini response missing parts")
                        _LOGGER.debug(
                            "Full Gemini response: %s", json.dumps(data, indent=2)
                        )
                else:
                    _LOGGER.warning("Gemini response missing expected structure")
                    _LOGGER.debug(
                        "Full Gemini response: %s", json.dumps(data, indent=2)
                    )
                return str(data)


class AnthropicClient(BaseAIClient):
    def __init__(self, token, model="claude-sonnet-4-5-20250929"):
        self.token = token
        self.model = model
        self.api_url = "https://api.anthropic.com/v1/messages"

    async def get_response(self, messages, **kwargs):
        _LOGGER.debug("Making request to Anthropic API with model: %s", self.model)
        headers = {
            "x-api-key": self.token,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        # Convert OpenAI-style messages to Anthropic format
        system_message = None
        anthropic_messages = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                # Anthropic uses a separate system parameter
                system_message = content
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content})

        payload = {
            "model": self.model,
            "max_tokens": 8192,  # Maximum for Anthropic Claude models
            "temperature": 0.7,
            "messages": anthropic_messages,
        }

        # Add system message if present
        if system_message:
            payload["system"] = system_message

        _LOGGER.debug("Anthropic request payload: %s", json.dumps(payload, indent=2))

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    _LOGGER.error("Anthropic API error %d: %s", resp.status, error_text)
                    raise Exception(f"Anthropic API error {resp.status}")
                data = await resp.json()
                # Extract text from Anthropic response
                content_blocks = data.get("content", [])
                if content_blocks and isinstance(content_blocks, list):
                    # Get the text from the first content block
                    for block in content_blocks:
                        if block.get("type") == "text":
                            return block.get("text", str(data))
                return str(data)


class OpenRouterClient(BaseAIClient):
    def __init__(self, token, model="openai/gpt-4o"):
        self.token = token
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    async def get_response(self, messages, **kwargs):
        _LOGGER.debug("Making request to OpenRouter API with model: %s", self.model)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://home-assistant.io",  # Optional for OpenRouter rankings
            "X-Title": "Home Assistant AI Agent",  # Optional for OpenRouter rankings
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.9,
            # max_tokens omitted - let OpenRouter use the model's maximum capacity
        }

        _LOGGER.debug("OpenRouter request payload: %s", json.dumps(payload, indent=2))

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    _LOGGER.error(
                        "OpenRouter API error %d: %s", resp.status, error_text
                    )
                    raise Exception(f"OpenRouter API error {resp.status}")
                data = await resp.json()
                # Extract text from OpenRouter response (OpenAI-compatible format)
                choices = data.get("choices", [])
                if not choices:
                    _LOGGER.warning("OpenRouter response missing choices")
                    _LOGGER.debug(
                        "Full OpenRouter response: %s", json.dumps(data, indent=2)
                    )
                    return str(data)
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", str(data))
                return str(data)


class AlterClient(BaseAIClient):
    def __init__(self, token, model=""):
        self.token = token
        self.model = model
        self.api_url = "https://alterhq.com/api/v1/chat/completions"

    async def get_response(self, messages, **kwargs):
        _LOGGER.debug("Making request to Alter API with model: %s", self.model)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.9,
        }

        _LOGGER.debug("Alter request payload: %s", json.dumps(payload, indent=2))

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    _LOGGER.error("Alter API error %d: %s", resp.status, error_text)
                    raise Exception(f"Alter API error {resp.status}")
                data = await resp.json()
                # Extract text from Alter response (OpenAI-compatible format)
                choices = data.get("choices", [])
                if not choices:
                    _LOGGER.warning("Alter response missing choices")
                    _LOGGER.debug("Full Alter response: %s", json.dumps(data, indent=2))
                    return str(data)
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", str(data))
                return str(data)


class ZaiClient(BaseAIClient):
    def __init__(self, token, model="", endpoint_type="general"):
        self.token = token
        self.model = model
        self.endpoint_type = endpoint_type
        # General endpoint: https://api.z.ai/api/paas/v4/chat/completions
        # Coding endpoint: https://api.z.ai/api/coding/paas/v4/chat/completions
        if endpoint_type == "coding":
            self.api_url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
        else:
            self.api_url = "https://api.z.ai/api/paas/v4/chat/completions"

    async def get_response(self, messages, **kwargs):
        _LOGGER.debug(
            "Making request to z.ai API with model: %s, endpoint: %s",
            self.model,
            self.endpoint_type,
        )
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.9,
        }

        _LOGGER.debug("z.ai request payload: %s", json.dumps(payload, indent=2))

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    _LOGGER.error("z.ai API error %d: %s", resp.status, error_text)
                    raise Exception(f"z.ai API error {resp.status}")
                data = await resp.json()
                # Extract text from z.ai response (OpenAI-compatible format)
                choices = data.get("choices", [])
                if not choices:
                    _LOGGER.warning("z.ai response missing choices")
                    _LOGGER.debug("Full z.ai response: %s", json.dumps(data, indent=2))
                    return str(data)
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", str(data))
                return str(data)


# === Main Agent ===
class AiAgentHaAgent:
    """Agent for handling queries with dynamic data requests and multiple AI providers."""

    SYSTEM_PROMPT = {
        "role": "system",
        "content": (
            "You are an AI assistant integrated with Home Assistant.\n"
            "You can request specific data by using only these commands:\n"
            "- get_entity_state(entity_id): Get state of a specific entity\n"
            "- get_entities_by_domain(domain): Get all entities in a domain\n"
            "- get_entities_by_device_class(device_class, domain?): Get entities with specific device_class (e.g., 'temperature', 'humidity', 'motion')\n"
            "- get_climate_related_entities(): Get all climate-related entities (climate.* entities + temperature/humidity sensors)\n"
            "- get_entities_by_area(area_id): Get all entities in a specific area\n"
            "- get_entities(area_id or area_ids): Get entities by area(s) - supports single area_id or list of area_ids\n"
            "  Use as: get_entities(area_ids=['area1', 'area2']) for multiple areas or get_entities(area_id='single_area')\n"
            "- get_calendar_events(entity_id?): Get calendar events\n"
            "- get_automations(): Get all automations\n"
            "- get_weather_data(): Get current weather and forecast data\n"
            "- get_entity_registry(): Get entity registry entries (now includes device_class, state_class, unit_of_measurement)\n"
            "- get_device_registry(): Get device registry entries\n"
            "- get_area_registry(): Get room/area information\n"
            "- get_history(entity_id, hours): Get historical state changes\n"
            "- get_person_data(): Get person tracking information\n"
            "- get_statistics(entity_id): Get sensor statistics\n"
            "- get_scenes(): Get scene configurations\n"
            "- get_dashboards(): Get list of all dashboards\n"
            "- get_dashboard_config(dashboard_url): Get configuration of a specific dashboard\n"
            "- set_entity_state(entity_id, state, attributes?): Set state of an entity (e.g., turn on/off lights, open/close covers)\n"
            "- call_service(domain, service, target?, service_data?): Call any Home Assistant service directly\n"
            "- create_automation(automation): Create a new automation with the provided configuration\n"
            "- create_dashboard(dashboard_config): Create a new dashboard with the provided configuration\n"
            "- update_dashboard(dashboard_url, dashboard_config): Update an existing dashboard configuration\n\n"
            "IMPORTANT DEVICE_CLASS GUIDANCE:\n"
            "- Many sensors have a 'device_class' attribute (temperature, humidity, motion, etc.)\n"
            "- Use get_climate_related_entities() for climate dashboards (includes climate.* entities and temperature/humidity sensors)\n"
            "- Use get_entities_by_device_class(device_class) to filter by device_class (e.g., 'temperature', 'humidity', 'motion')\n"
            "- For climate dashboards, use history-graph and gauge cards for temperature/humidity sensors\n\n"
            "DASHBOARD CREATION:\n"
            "When a user asks to create a dashboard:\n"
            "1. Gather entities using get_climate_related_entities() or other get_* commands\n"
            "2. Respond with JSON using request_type: 'dashboard_suggestion' (NEVER use 'final_response'!)\n"
            "3. Use Lovelace JSON format (NOT YAML!)\n"
            "4. Example response structure:\n"
            '{"request_type": "dashboard_suggestion", "message": "Dashboard created", "dashboard": {"title": "...", "views": [...]}}\n'
            "5. Do NOT include YAML, markdown, or code blocks - only pure JSON\n\n"
            "IMPORTANT AREA/FLOOR GUIDANCE:\n"
            "- When users ask for entities from a specific floor, use get_area_registry() first\n"
            "- Areas have both 'area_id' and 'floor_id' - these are different concepts\n"
            "- Filter areas by their floor_id to find all areas on a specific floor\n"
            "- Use get_entities() with area_ids parameter to get entities from multiple areas efficiently\n"
            "- Example: get_entities(area_ids=['area1', 'area2', 'area3']) for multiple areas at once\n"
            "- This is more efficient than calling get_entities_by_area() multiple times\n\n"
            "AUTOMATION CREATION:\n"
            "When creating automations, request entities first to know the entity IDs.\n"
            "For days, use: ['fri', 'mon', 'sat', 'sun', 'thu', 'tue', 'wed']\n\n"
            "RESPONSE FORMATS - You must ALWAYS respond with valid JSON:\n\n"
            "For automations:\n"
            "{\n"
            '  "request_type": "automation_suggestion",\n'
            '  "message": "I\'ve created an automation that might help you. Would you like me to create it?",\n'
            '  "automation": {\n'
            '    "alias": "Name of the automation",\n'
            '    "description": "Description of what the automation does",\n'
            '    "trigger": [...],  // Array of trigger conditions\n'
            '    "condition": [...], // Optional array of conditions\n'
            '    "action": [...]     // Array of actions to perform\n'
            "  }\n"
            "}\n\n"
            "For dashboards (WHEN USER ASKS TO CREATE A DASHBOARD):\n"
            "{\n"
            '  "request_type": "dashboard_suggestion",\n'
            '  "message": "Description of the dashboard you created",\n'
            '  "dashboard": {\n'
            '    "title": "Dashboard Title",\n'
            '    "url_path": "url-path",\n'
            '    "icon": "mdi:icon-name",\n'
            '    "show_in_sidebar": true,\n'
            '    "views": [{\n'
            '      "title": "View Title",\n'
            '      "cards": [...]\n'
            "    }]\n"
            "  }\n"
            "}\n\n"
            "For data requests, use this exact JSON format:\n"
            "{\n"
            '  "request_type": "data_request",\n'
            '  "request": "command_name",\n'
            '  "parameters": {...}\n'
            "}\n"
            'For get_entities with multiple areas: {"request_type": "get_entities", "parameters": {"area_ids": ["area1", "area2"]}}\n'
            'For get_entities with single area: {"request_type": "get_entities", "parameters": {"area_id": "single_area"}}\n\n'
            "For service calls, use this exact JSON format:\n"
            "{\n"
            '  "request_type": "call_service",\n'
            '  "domain": "light",\n'
            '  "service": "turn_on",\n'
            '  "target": {"entity_id": ["entity1", "entity2"]},\n'
            '  "service_data": {"brightness": 255}\n'
            "}\n\n"
            "For answering questions (NOT creating dashboards/automations):\n"
            "{\n"
            '  "request_type": "final_response",\n'
            '  "response": "your answer to the user"\n'
            "}\n\n"
            "IMPORTANT: Use 'dashboard_suggestion' when creating dashboards, NOT 'final_response'!\n\n"
            "CRITICAL FORMATTING RULES:\n"
            "- You must ALWAYS respond with ONLY a valid JSON object\n"
            "- DO NOT include any text before the JSON\n"
            "- DO NOT include any text after the JSON\n"
            "- DO NOT include explanations or descriptions outside the JSON\n"
            "- Your entire response must be parseable as JSON\n"
            "- Use the 'message' field inside the JSON for user-facing text\n"
            "- NEVER mix regular text with JSON in your response\n\n"
            "WRONG: 'I'll create this for you. {\"request_type\": ...}'\n"
            'CORRECT: \'{"request_type": "dashboard_suggestion", "message": "I\'ll create this for you.", ...}\''
        ),
    }

    SYSTEM_PROMPT_LOCAL = {
        "role": "system",
        "content": (
            "You are an AI assistant integrated with Home Assistant.\n"
            "You can request specific data by using only these commands:\n"
            "- get_entity_state(entity_id): Get state of a specific entity\n"
            "- get_entities_by_domain(domain): Get all entities in a domain\n"
            "- get_entities_by_device_class(device_class, domain?): Get entities with specific device_class (e.g., 'temperature', 'humidity', 'motion')\n"
            "- get_climate_related_entities(): Get all climate-related entities (climate.* entities + temperature/humidity sensors)\n"
            "- get_entities_by_area(area_id): Get all entities in a specific area\n"
            "- get_entities(area_id or area_ids): Get entities by area(s) - supports single area_id or list of area_ids\n"
            "  Use as: get_entities(area_ids=['area1', 'area2']) for multiple areas or get_entities(area_id='single_area')\n"
            "- get_calendar_events(entity_id?): Get calendar events\n"
            "- get_automations(): Get all automations\n"
            "- get_weather_data(): Get current weather and forecast data\n"
            "- get_entity_registry(): Get entity registry entries (now includes device_class, state_class, unit_of_measurement)\n"
            "- get_device_registry(): Get device registry entries\n"
            "- get_area_registry(): Get room/area information\n"
            "- get_history(entity_id, hours): Get historical state changes\n"
            "- get_person_data(): Get person tracking information\n"
            "- get_statistics(entity_id): Get sensor statistics\n"
            "- get_scenes(): Get scene configurations\n"
            "- get_dashboards(): Get list of all dashboards\n"
            "- get_dashboard_config(dashboard_url): Get configuration of a specific dashboard\n"
            "- set_entity_state(entity_id, state, attributes?): Set state of an entity (e.g., turn on/off lights, open/close covers)\n"
            "- call_service(domain, service, target?, service_data?): Call any Home Assistant service directly\n"
            "- create_automation(automation): Create a new automation with the provided configuration\n"
            "- create_dashboard(dashboard_config): Create a new dashboard with the provided configuration\n"
            "- update_dashboard(dashboard_url, dashboard_config): Update an existing dashboard configuration\n\n"
            "IMPORTANT DEVICE_CLASS GUIDANCE:\n"
            "- Many sensors have a 'device_class' attribute (temperature, humidity, motion, etc.)\n"
            "- Use get_climate_related_entities() for climate dashboards (includes climate.* entities and temperature/humidity sensors)\n"
            "- Use get_entities_by_device_class(device_class) to filter by device_class (e.g., 'temperature', 'humidity', 'motion')\n"
            "- For climate dashboards, use history-graph and gauge cards for temperature/humidity sensors\n\n"
            "DASHBOARD CREATION:\n"
            "When a user asks to create a dashboard:\n"
            "1. Gather entities using get_climate_related_entities() or other get_* commands\n"
            "2. Respond with JSON using request_type: 'dashboard_suggestion' (NEVER use 'final_response'!)\n"
            "3. Use Lovelace JSON format (NOT YAML!)\n"
            "4. Example response structure:\n"
            '{"request_type": "dashboard_suggestion", "message": "Dashboard created", "dashboard": {"title": "...", "views": [...]}}\n'
            "5. Do NOT include YAML, markdown, or code blocks - only pure JSON\n\n"
            "IMPORTANT AREA/FLOOR GUIDANCE:\n"
            "- When users ask for entities from a specific floor, use get_area_registry() first\n"
            "- Areas have both 'area_id' and 'floor_id' - these are different concepts\n"
            "- Filter areas by their floor_id to find all areas on a specific floor\n"
            "- Use get_entities() with area_ids parameter to get entities from multiple areas efficiently\n"
            "- Example: get_entities(area_ids=['area1', 'area2', 'area3']) for multiple areas at once\n"
            "- This is more efficient than calling get_entities_by_area() multiple times\n\n"
            "AUTOMATION CREATION:\n"
            "When creating automations, request entities first to know the entity IDs.\n"
            "For days, use: ['fri', 'mon', 'sat', 'sun', 'thu', 'tue', 'wed']\n\n"
            "RESPONSE FORMATS - You must ALWAYS respond with valid JSON:\n\n"
            "For automations:\n"
            "{\n"
            '  "request_type": "automation_suggestion",\n'
            '  "message": "I\'ve created an automation that might help you. Would you like me to create it?",\n'
            '  "automation": {\n'
            '    "alias": "Name of the automation",\n'
            '    "description": "Description of what the automation does",\n'
            '    "trigger": [...],  // Array of trigger conditions\n'
            '    "condition": [...], // Optional array of conditions\n'
            '    "action": [...]     // Array of actions to perform\n'
            "  }\n"
            "}\n\n"
            "For dashboards (WHEN USER ASKS TO CREATE A DASHBOARD):\n"
            "{\n"
            '  "request_type": "dashboard_suggestion",\n'
            '  "message": "Description of the dashboard you created",\n'
            '  "dashboard": {\n'
            '    "title": "Dashboard Title",\n'
            '    "url_path": "url-path",\n'
            '    "icon": "mdi:icon-name",\n'
            '    "show_in_sidebar": true,\n'
            '    "views": [{\n'
            '      "title": "View Title",\n'
            '      "cards": [...]\n'
            "    }]\n"
            "  }\n"
            "}\n\n"
            "For data requests, use this exact JSON format:\n"
            "{\n"
            '  "request_type": "data_request",\n'
            '  "request": "command_name",\n'
            '  "parameters": {...}\n'
            "}\n"
            'For get_entities with multiple areas: {"request_type": "get_entities", "parameters": {"area_ids": ["area1", "area2"]}}\n'
            'For get_entities with single area: {"request_type": "get_entities", "parameters": {"area_id": "single_area"}}\n\n'
            "For service calls, use this exact JSON format:\n"
            "{\n"
            '  "request_type": "call_service",\n'
            '  "domain": "light",\n'
            '  "service": "turn_on",\n'
            '  "target": {"entity_id": ["entity1", "entity2"]},\n'
            '  "service_data": {"brightness": 255}\n'
            "}\n\n"
            "For answering questions (NOT creating dashboards/automations):\n"
            "{\n"
            '  "request_type": "final_response",\n'
            '  "response": "your answer to the user"\n'
            "}\n\n"
            "IMPORTANT: Use 'dashboard_suggestion' when creating dashboards, NOT 'final_response'!\n\n"
            "CRITICAL FORMATTING RULES:\n"
            "- You must ALWAYS respond with ONLY a valid JSON object\n"
            "- DO NOT include any text before the JSON\n"
            "- DO NOT include any text after the JSON\n"
            "- DO NOT include explanations or descriptions outside the JSON\n"
            "- Your entire response must be parseable as JSON\n"
            "- Use the 'message' field inside the JSON for user-facing text\n"
            "- NEVER mix regular text with JSON in your response\n\n"
            "WRONG: 'I'll create this for you. {\"request_type\": ...}'\n"
            'CORRECT: \'{"request_type": "dashboard_suggestion", "message": "I\'ll create this for you.", ...}\''
        ),
    }

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any]):
        """Initialize the agent with provider selection."""
        self.hass = hass
        self.config = config
        self.conversation_history: List[Dict[str, Any]] = []
        self._cache: Dict[str, Any] = {}
        self.ai_client: BaseAIClient
        self._cache_timeout = 300  # 5 minutes
        self._max_retries = 10
        self._retry_delay = 1  # seconds
        self._rate_limit = 60  # requests per minute
        self._last_request_time = 0
        self._request_count = 0
        self._request_window_start = time.time()

        provider = config.get("ai_provider", "openai")
        models_config = config.get("models", {})

        _LOGGER.debug("Initializing AiAgentHaAgent with provider: %s", provider)
        _LOGGER.debug("Models config loaded: %s", models_config)

        # Set the appropriate system prompt based on provider
        if provider in ("local_ollama", "openai_compatible"):
            self.system_prompt = self.SYSTEM_PROMPT_LOCAL
            _LOGGER.debug(
                "Using local-optimized system prompt for provider: %s", provider
            )
        else:
            self.system_prompt = self.SYSTEM_PROMPT
            _LOGGER.debug("Using standard system prompt")

        # Initialize the appropriate AI client with model selection
        if provider == "openai":
            model = models_config.get("openai", "gpt-3.5-turbo")
            base_url = config.get(CONF_OPENAI_BASE_URL) or ""
            self.ai_client = OpenAIClient(
                config.get("openai_token"), model, base_url or None
            )
        elif provider == "gemini":
            model = models_config.get("gemini", "gemini-2.5-flash")
            self.ai_client = GeminiClient(config.get("gemini_token"), model)
        elif provider == "openrouter":
            model = models_config.get("openrouter", "openai/gpt-4o")
            self.ai_client = OpenRouterClient(config.get("openrouter_token"), model)
        elif provider == "anthropic":
            model = models_config.get("anthropic", "claude-sonnet-4-5-20250929")
            self.ai_client = AnthropicClient(config.get("anthropic_token"), model)
        elif provider == "alter":
            model = models_config.get("alter", "")
            self.ai_client = AlterClient(config.get("alter_token"), model)
        elif provider == "zai":
            model = models_config.get("zai", "glm-4.7")
            endpoint_type = config.get("zai_endpoint", "general")
            self.ai_client = ZaiClient(config.get("zai_token"), model, endpoint_type)
        elif provider == "local_ollama":
            # Support both new local_ollama_url and legacy local_url
            url = config.get("local_ollama_url") or config.get("local_url")
            model = models_config.get("local_ollama") or models_config.get("local", "")
            if not url:
                _LOGGER.error("Missing local_ollama_url for local_ollama provider")
                raise Exception(
                    "Missing local_ollama_url configuration for local_ollama provider"
                )
            self.ai_client = LocalOllamaClient(url, model)
        elif provider == "openai_compatible":
            url = config.get("openai_compatible_url")
            model = models_config.get("openai_compatible", "")
            api_key = config.get("openai_compatible_api_key", "") or ""
            if not url:
                _LOGGER.error(
                    "Missing openai_compatible_url for openai_compatible provider"
                )
                raise Exception(
                    "Missing openai_compatible_url configuration for openai_compatible provider"
                )
            self.ai_client = OpenaiCompatibleClient(url, model, api_key or None)
        else:  # default to llama if somehow specified
            model = models_config.get("llama", "Llama-4-Maverick-17B-128E-Instruct-FP8")
            self.ai_client = LlamaClient(config.get("llama_token"), model)

        # Initialize dashboard advisor
        self.dashboard_advisor = DashboardAdvisor()

        # Initialize prompt compactor
        self.prompt_compactor = PromptCompactor(
            threshold_pct=config.get(CONF_PROMPT_COMPACTION_THRESHOLD, DEFAULT_PROMPT_COMPACTION_ENABLED),
            enabled=True,
        )

        # Initialize multimedia processor for multimodal support
        self.multimodal_enabled = config.get(
            CONF_MULTIMODAL_ENABLED,
            True
        )
        self.image_upload_enabled = config.get(
            CONF_IMAGE_UPLOAD_ENABLED,
            True
        )

        self.multimedia_processor = MultimediaProcessor(
            max_image_size=config.get(CONF_MAX_IMAGE_SIZE, 5 * 1024 * 1024),
            max_images_per_message=config.get(CONF_MAX_IMAGES_PER_MESSAGE, 3),
            compression_quality=config.get(CONF_IMAGE_COMPRESSION_QUALITY, 80)
        )

        # Track attached images for current message
        self._current_image_attachments: List[ImageAttachment] = []

        # Initialize permission checker
        from .const import (
            CONF_PERMISSION_MODE,
            CONF_PERMISSION_TIMEOUT,
            CONF_PERMISSION_WHITELIST,
            CONF_PERMISSION_BLACKLIST,
        )

        whitelist_rules = []
        if CONF_PERMISSION_WHITELIST in config:
            for item in config[CONF_PERMISSION_WHITELIST]:
                whitelist_rules.append(PermissionRule(
                    pattern=item.get("pattern", ""),
                    rule_type=item.get("type", "allow"),
                    description=item.get("description", ""),
                    priority=item.get("priority", 0)
                ))

        blacklist_rules = []
        if CONF_PERMISSION_BLACKLIST in config:
            for item in config[CONF_PERMISSION_BLACKLIST]:
                blacklist_rules.append(PermissionRule(
                    pattern=item.get("pattern", ""),
                    rule_type=item.get("type", "deny"),
                    description=item.get("description", ""),
                    priority=item.get("priority", 0)
                ))

        self.permission_checker = PermissionChecker(
            mode=config.get(CONF_PERMISSION_MODE, PERMISSION_MODE_PROMPT),
            whitelist=whitelist_rules,
            blacklist=blacklist_rules,
            timeout=config.get(CONF_PERMISSION_TIMEOUT, 60)
        )

        _LOGGER.debug(
            "AiAgentHaAgent initialized successfully with provider: %s, model: %s",
            provider,
            model,
        )

    def _validate_api_key(self) -> bool:
        """Validate the API key format."""
        provider = self.config.get("ai_provider", "openai")

        if provider == "openai":
            token = self.config.get("openai_token")
        elif provider == "gemini":
            token = self.config.get("gemini_token")
        elif provider == "openrouter":
            token = self.config.get("openrouter_token")
        elif provider == "anthropic":
            token = self.config.get("anthropic_token")
        elif provider == "alter":
            token = self.config.get("alter_token")
        elif provider == "zai":
            token = self.config.get("zai_token")
        elif provider == "local_ollama":
            # For local_ollama, the “token” is actually the URL; support legacy local_url
            token = self.config.get("local_ollama_url") or self.config.get("local_url")
        elif provider == "openai_compatible":
            # For openai_compatible, validate the URL is present
            token = self.config.get("openai_compatible_url")
        else:
            token = self.config.get("llama_token")

        if not token or not isinstance(token, str):
            return False

        # For local_ollama and openai_compatible, validate URL format
        if provider in ("local_ollama", "openai_compatible"):
            return bool(token.startswith(("http://", "https://")))

        # Add more specific validation based on your API key format
        return len(token) >= 32

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        current_time = time.time()
        if current_time - self._request_window_start >= 60:
            self._request_count = 0
            self._request_window_start = current_time

        if self._request_count >= self._rate_limit:
            return False

        self._request_count += 1
        return True

    def _get_cached_data(self, key: str) -> Optional[Any]:
        """Get data from cache if it's still valid."""
        if key in self._cache:
            timestamp, data = self._cache[key]
            if time.time() - timestamp < self._cache_timeout:
                return data
            del self._cache[key]
        return None

    def _set_cached_data(self, key: str, data: Any) -> None:
        """Store data in cache with timestamp."""
        self._cache[key] = (time.time(), data)
    
    def _generate_fallback_response(self, action_details: Optional[list] = None) -> str:
        """Generate a fallback response when the AI returns an empty final_response.
        
        This method analyzes the conversation history and action details to generate
        a meaningful response based on the actions that were taken and their results.
        
        Args:
            action_details: Optional list of action detail dicts with 'domain', 'service',
                           'target', 'service_data', and 'result' keys.
        
        Returns:
            A string containing the fallback response message.
        """
        _LOGGER.debug("Generating fallback response from conversation history, action_details=%s", action_details)
        
        # If we have action_details with results, use those for success/failure info
        if action_details and isinstance(action_details, list) and len(action_details) > 0:
            return self._generate_fallback_from_action_details(action_details)
        
        # Fall back to analyzing conversation history
        return self._generate_fallback_from_history()
    
    def _generate_fallback_from_action_details(self, action_details: list) -> str:
        """Generate fallback response from action details with results.
        
        Args:
            action_details: List of action detail dicts with results.
            
        Returns:
            A string containing the fallback response with success/failure status.
        """
        successful_actions = []
        failed_actions = []
        
        for detail in action_details:
            domain = detail.get("domain", "")
            service = detail.get("service", "")
            target = detail.get("target", {})
            service_data = detail.get("service_data", {})
            result = detail.get("result", {})
            
            # Check if the action was successful
            is_success = True
            error_msg = None
            
            if isinstance(result, dict):
                if result.get("error"):
                    is_success = False
                    error_msg = result["error"]
                elif not result.get("success", True):
                    is_success = False
                    error_msg = result.get("message", "Unknown error")
            elif result is None or result == {}:
                # Empty result might indicate failure
                is_success = False
                error_msg = "No result returned"
            
            # Generate human-readable description of the action
            action_description = self._format_action_description(domain, service, target, service_data)
            
            if is_success:
                successful_actions.append(action_description)
            else:
                failed_actions.append((action_description, error_msg or "Unknown error"))
        
        # Build the response message
        parts = []
        
        if successful_actions:
            if len(successful_actions) == 1:
                parts.append(f"{successful_actions[0]} succeeded.")
            else:
                parts.append(f"I successfully completed: {'; '.join(successful_actions)}.")
        
        if failed_actions:
            for action, error in failed_actions:
                parts.append(f"However, {action} failed with error: {error}")
        
        if parts:
            return " ".join(parts)
        
        return "I processed your request but encountered an issue generating a response. Please try again."
    
    def _generate_fallback_from_history(self) -> str:
        """Generate fallback response by analyzing conversation history.
        
        Returns:
            A string containing the fallback response message.
        """
        _LOGGER.debug("Generating fallback response from conversation history")
        
        # Look at the conversation history to find what actions were requested
        last_service_calls = []
        for msg in reversed(self.conversation_history):
            content = msg.get("content", "")
            if msg.get("role") == "assistant" and content.startswith("{"):
                try:
                    data = json.loads(content)
                    if data.get("request_type") == "call_service":
                        domain = data.get("domain", "")
                        service = data.get("service", "")
                        target = data.get("target", {})
                        last_service_calls.append({
                            "domain": domain,
                            "service": service,
                            "target": target,
                        })
                except (json.JSONDecodeError, ValueError):
                    pass
        
        if not last_service_calls:
            return "I processed your request but encountered an issue generating a response. Please try again."
        
        # Generate a meaningful response based on the service calls
        # Note: This doesn't have result info, so it's less precise
        responses = []
        for call in last_service_calls:
            domain = call["domain"]
            service = call["service"]
            target = call["target"]
            service_data = call.get("service_data", {})
            
            response = self._format_action_description(domain, service, target, service_data)
            if response:
                responses.append(f"{response} (status unknown - please verify)")
        
        if responses:
            return " ".join(responses)
        
        return "I processed your request but encountered an issue generating a response. Please try again."
    
    def _format_action_description(self, domain: str, service: str, target: dict, service_data: dict) -> str:
        """Format an action description for display in fallback responses.
        
        Args:
            domain: The service domain (e.g., 'homeassistant', 'renamed_entity')
            service: The service name (e.g., 'rename', 'turn_on')
            target: The target dict with entity_id
            service_data: The service data
            
        Returns:
            A human-readable action description.
        """
        # Handle renamed_entity.rename service (Home Assistant entity renaming)
        if domain == "renamed_entity" and service == "rename":
            new_object_id = service_data.get("new_object_id", "") if isinstance(service_data, dict) else ""
            original_entity = target.get("entity_id", "") if isinstance(target, dict) else ""
            if new_object_id and original_entity:
                return f"I renamed {original_entity} to '{new_object_id}'"
            elif new_object_id:
                return f"I renamed the entity to '{new_object_id}'"
            else:
                return "I renamed the entity"
        
        # Handle homeassistant.rename_entity service
        if domain == "homeassistant" and service == "rename_entity":
            new_entity_id = target.get("entity_id", "") if isinstance(target, dict) else ""
            if new_entity_id:
                return f"I renamed the device to '{new_entity_id}'"
            else:
                return "I renamed the device"
        
        # Handle turn_on/turn_off
        if domain == "homeassistant" and service == "turn_on":
            if isinstance(target, dict) and "entity_id" in target:
                return f"I turned on {target['entity_id']}"
            return "I turned on the device"
        
        if domain == "homeassistant" and service == "turn_off":
            if isinstance(target, dict) and "entity_id" in target:
                return f"I turned off {target['entity_id']}"
            return "I turned off the device"
        
        # Handle generic call_service
        if domain == "homeassistant" and service == "call_service":
            if isinstance(target, dict):
                target_entity = target.get("entity_id", "")
                if target_entity:
                    return f"I called {target_entity}"
            return "I executed the service call"
        
        # Generic response for other service types
        service_name = service.replace("_", " ")
        if isinstance(target, dict) and target.get("entity_id"):
            entities = target.get("entity_id", [])
            if isinstance(entities, list):
                entities_str = ", ".join(entities)
            else:
                entities_str = entities
            return f"I {service_name} for {entities_str}"
        
        return f"I executed {domain}.{service}"

    def _sanitize_automation_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize automation configuration to prevent injection attacks."""
        sanitized: Dict[str, Any] = {}
        for key, value in config.items():
            if key in ["alias", "description"]:
                # Sanitize strings
                sanitized[key] = str(value).strip()[:100]  # Limit length
            elif key in ["trigger", "condition", "action"]:
                # Validate arrays
                if isinstance(value, list):
                    sanitized[key] = value
            elif key == "mode":
                # Validate mode
                if value in ["single", "restart", "queued", "parallel"]:
                    sanitized[key] = value
        return sanitized

    async def get_entity_state(self, entity_id: str) -> Dict[str, Any]:
        """Get the state of a specific entity."""
        try:
            _LOGGER.debug("Requesting entity state for: %s", entity_id)
            state = self.hass.states.get(entity_id)
            if not state:
                _LOGGER.warning("Entity not found: %s", entity_id)
                return {"error": f"Entity {entity_id} not found"}

            # Get area information from entity/device registry
            # Wrapped in try-except to handle cases where registries aren't available (e.g., in tests)
            area_id = None
            area_name = None

            try:
                from homeassistant.helpers import area_registry as ar
                from homeassistant.helpers import device_registry as dr
                from homeassistant.helpers import entity_registry as er

                entity_registry = er.async_get(self.hass)
                device_registry = dr.async_get(self.hass)
                area_registry = ar.async_get(self.hass)

                if entity_registry and hasattr(entity_registry, "async_get"):
                    # Try to find the entity in the registry
                    entity_entry = entity_registry.async_get(entity_id)
                    if entity_entry:
                        _LOGGER.debug("Entity %s found in registry", entity_id)
                        # Check if entity has a direct area assignment
                        if hasattr(entity_entry, "area_id") and entity_entry.area_id:
                            area_id = entity_entry.area_id
                            _LOGGER.debug(
                                "Entity %s has direct area assignment: %s",
                                entity_id,
                                area_id,
                            )
                        # Otherwise check if the entity's device has an area
                        elif (
                            hasattr(entity_entry, "device_id")
                            and entity_entry.device_id
                            and device_registry
                            and hasattr(device_registry, "async_get")
                        ):
                            _LOGGER.debug(
                                "Entity %s has device_id: %s, checking device area",
                                entity_id,
                                entity_entry.device_id,
                            )
                            device_entry = device_registry.async_get(
                                entity_entry.device_id
                            )
                            if device_entry:
                                if (
                                    hasattr(device_entry, "area_id")
                                    and device_entry.area_id
                                ):
                                    area_id = device_entry.area_id
                                    _LOGGER.debug(
                                        "Device %s has area: %s",
                                        entity_entry.device_id,
                                        area_id,
                                    )
                                else:
                                    _LOGGER.debug(
                                        "Device %s has no area assigned",
                                        entity_entry.device_id,
                                    )
                            else:
                                _LOGGER.debug(
                                    "Device %s not found in registry",
                                    entity_entry.device_id,
                                )
                        else:
                            _LOGGER.debug(
                                "Entity %s has no area_id and no device_id", entity_id
                            )
                    else:
                        _LOGGER.debug(
                            "Entity %s not found in entity registry", entity_id
                        )
                else:
                    _LOGGER.debug("Entity registry not available for %s", entity_id)

                # Get area name from area_id
                if (
                    area_id
                    and area_registry
                    and hasattr(area_registry, "async_get_area")
                ):
                    area_entry = area_registry.async_get_area(area_id)
                    if area_entry and hasattr(area_entry, "name"):
                        area_name = area_entry.name
                        _LOGGER.debug(
                            "Resolved area_id %s to area_name: %s", area_id, area_name
                        )
                    else:
                        _LOGGER.debug("Could not resolve area_id %s to name", area_id)
                elif area_id:
                    _LOGGER.debug(
                        "Have area_id %s but area_registry not available", area_id
                    )
            except Exception as e:
                # Registries not available (likely in test environment) - skip area information
                _LOGGER.warning(
                    "Exception retrieving area information for %s: %s",
                    entity_id,
                    str(e),
                )

            result = {
                "entity_id": state.entity_id,
                "state": state.state,
                "last_changed": (
                    state.last_changed.isoformat() if state.last_changed else None
                ),
                "friendly_name": state.attributes.get("friendly_name"),
                "area_id": area_id,
                "area_name": area_name,
                "attributes": {
                    k: (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in state.attributes.items()
                },
            }
            _LOGGER.debug(
                "Retrieved entity state for %s: area_id=%s, area_name=%s",
                entity_id,
                area_id,
                area_name,
            )
            return result
        except Exception as e:
            _LOGGER.exception("Error getting entity state: %s", str(e))
            return {"error": f"Error getting entity state: {str(e)}"}

    async def get_entities_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all entities for a specific domain."""
        try:
            _LOGGER.debug("Requesting all entities for domain: %s", domain)
            states = [
                state
                for state in self.hass.states.async_all()
                if state.entity_id.startswith(f"{domain}.")
            ]
            _LOGGER.debug("Found %d entities in domain %s", len(states), domain)
            return [await self.get_entity_state(state.entity_id) for state in states]
        except Exception as e:
            _LOGGER.exception("Error getting entities by domain: %s", str(e))
            return [{"error": f"Error getting entities for domain {domain}: {str(e)}"}]

    async def get_entities_by_device_class(
        self, device_class: str, domain: str = None
    ) -> List[Dict[str, Any]]:
        """Get all entities with a specific device_class.

        Args:
            device_class: The device class to filter by (e.g., 'temperature', 'humidity', 'motion')
            domain: Optional domain to restrict search (e.g., 'sensor', 'binary_sensor')

        Returns:
            List of entity state dictionaries that match the device_class
        """
        try:
            _LOGGER.debug(
                "Requesting all entities with device_class: %s (domain: %s)",
                device_class,
                domain or "all",
            )
            matching_entities = []

            for state in self.hass.states.async_all():
                # Filter by domain if specified
                if domain and not state.entity_id.startswith(f"{domain}."):
                    continue

                # Check if this entity has the matching device_class
                entity_device_class = state.attributes.get("device_class")
                if entity_device_class == device_class:
                    matching_entities.append(state.entity_id)

            _LOGGER.debug(
                "Found %d entities with device_class %s",
                len(matching_entities),
                device_class,
            )

            # Get full state information for each matching entity
            return [
                await self.get_entity_state(entity_id)
                for entity_id in matching_entities
            ]

        except Exception as e:
            _LOGGER.exception("Error getting entities by device_class: %s", str(e))
            return [
                {
                    "error": f"Error getting entities with device_class {device_class}: {str(e)}"
                }
            ]

    async def get_climate_related_entities(self) -> List[Dict[str, Any]]:
        """Get all climate-related entities including climate domain and temperature/humidity sensors.

        Returns:
            List of entity state dictionaries for:
            - All climate.* entities (thermostats, HVAC systems)
            - All sensor.* entities with device_class: temperature
            - All sensor.* entities with device_class: humidity
        """
        try:
            _LOGGER.debug("Requesting all climate-related entities")
            climate_entities = []

            # Get all climate domain entities (thermostats, HVAC)
            climate_domain = await self.get_entities_by_domain("climate")
            climate_entities.extend(climate_domain)

            # Get temperature sensors
            temp_sensors = await self.get_entities_by_device_class(
                "temperature", "sensor"
            )
            climate_entities.extend(temp_sensors)

            # Get humidity sensors
            humidity_sensors = await self.get_entities_by_device_class(
                "humidity", "sensor"
            )
            climate_entities.extend(humidity_sensors)

            # Deduplicate by entity_id (edge case: if an entity appears in multiple categories)
            seen_entity_ids = set()
            unique_entities = []
            for entity in climate_entities:
                entity_id = entity.get("entity_id")
                if entity_id and entity_id not in seen_entity_ids:
                    seen_entity_ids.add(entity_id)
                    unique_entities.append(entity)

            _LOGGER.debug(
                "Found %d total climate-related entities (deduplicated from %d)",
                len(unique_entities),
                len(climate_entities),
            )
            return unique_entities

        except Exception as e:
            _LOGGER.exception("Error getting climate-related entities: %s", str(e))
            return [{"error": f"Error getting climate-related entities: {str(e)}"}]

    async def get_entities_by_area(self, area_id: str) -> List[Dict[str, Any]]:
        """Get all entities for a specific area."""
        try:
            _LOGGER.debug("Requesting all entities for area: %s", area_id)

            # Get entity registry to find entities assigned to the area
            from homeassistant.helpers import device_registry as dr
            from homeassistant.helpers import entity_registry as er

            entity_registry = er.async_get(self.hass)
            device_registry = dr.async_get(self.hass)

            entities_in_area = []

            # Find entities assigned to the area (directly or through their device)
            for entity in entity_registry.entities.values():
                # Check if entity is directly assigned to the area
                if entity.area_id == area_id:
                    entities_in_area.append(entity.entity_id)
                # Check if entity's device is assigned to the area
                elif entity.device_id:
                    device = device_registry.devices.get(entity.device_id)
                    if device and device.area_id == area_id:
                        entities_in_area.append(entity.entity_id)

            _LOGGER.debug(
                "Found %d entities in area %s", len(entities_in_area), area_id
            )

            # Get state information for each entity
            result = []
            for entity_id in entities_in_area:
                state_info = await self.get_entity_state(entity_id)
                if not state_info.get("error"):  # Only include entities that exist
                    result.append(state_info)

            return result

        except Exception as e:
            _LOGGER.exception("Error getting entities by area: %s", str(e))
            return [{"error": f"Error getting entities for area {area_id}: {str(e)}"}]

    async def get_entities(self, area_id=None, area_ids=None) -> List[Dict[str, Any]]:
        """Get entities by area(s) - flexible method that supports single area or multiple areas."""
        try:
            # Handle different parameter formats
            areas_to_process = []

            if area_ids:
                # Multiple areas provided
                if isinstance(area_ids, list):
                    areas_to_process = area_ids
                else:
                    areas_to_process = [area_ids]
            elif area_id:
                # Single area provided
                if isinstance(area_id, list):
                    areas_to_process = area_id
                else:
                    areas_to_process = [area_id]
            else:
                return [{"error": "No area_id or area_ids provided"}]

            _LOGGER.debug("Requesting entities for areas: %s", areas_to_process)

            all_entities = []
            for area in areas_to_process:
                entities_in_area = await self.get_entities_by_area(area)
                all_entities.extend(entities_in_area)

            # Remove duplicates based on entity_id
            seen_entities = set()
            unique_entities = []
            for entity in all_entities:
                if isinstance(entity, dict) and "entity_id" in entity:
                    if entity["entity_id"] not in seen_entities:
                        seen_entities.add(entity["entity_id"])
                        unique_entities.append(entity)
                else:
                    unique_entities.append(entity)  # Keep error messages

            _LOGGER.debug(
                "Found %d unique entities across %d areas",
                len(unique_entities),
                len(areas_to_process),
            )
            return unique_entities

        except Exception as e:
            _LOGGER.exception("Error getting entities: %s", str(e))
            return [{"error": f"Error getting entities: {str(e)}"}]

    async def get_calendar_events(
        self, entity_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get calendar events, optionally filtered by entity_id."""
        try:
            if entity_id:
                _LOGGER.debug(
                    "Requesting calendar events for specific entity: %s", entity_id
                )
                return [await self.get_entity_state(entity_id)]

            _LOGGER.debug("Requesting all calendar events")
            return await self.get_entities_by_domain("calendar")
        except Exception as e:
            _LOGGER.exception("Error getting calendar events: %s", str(e))
            return [{"error": f"Error getting calendar events: {str(e)}"}]

    async def get_automations(self) -> List[Dict[str, Any]]:
        """Get all automations."""
        try:
            _LOGGER.debug("Requesting all automations")
            return await self.get_entities_by_domain("automation")
        except Exception as e:
            _LOGGER.exception("Error getting automations: %s", str(e))
            return [{"error": f"Error getting automations: {str(e)}"}]

    async def get_entity_registry(self) -> List[Dict]:
        """Get entity registry entries with device_class and other metadata.

        Area information is resolved from the entity or its device.
        """
        _LOGGER.debug("Requesting all entity registry entries")
        try:
            from homeassistant.helpers import area_registry as ar
            from homeassistant.helpers import device_registry as dr
            from homeassistant.helpers import entity_registry as er

            entity_registry = er.async_get(self.hass)
            if not entity_registry:
                return []

            device_registry = dr.async_get(self.hass)
            area_registry = ar.async_get(self.hass)

            result = []
            for entry in entity_registry.entities.values():
                # Get the current state to access device_class and other attributes
                state = self.hass.states.get(entry.entity_id)
                device_class = state.attributes.get("device_class") if state else None
                state_class = state.attributes.get("state_class") if state else None
                unit_of_measurement = (
                    state.attributes.get("unit_of_measurement") if state else None
                )

                # Resolve area_id and area_name
                # First check entity's direct area assignment
                area_id = entry.area_id
                area_name = None

                # If entity doesn't have area, check device's area
                if not area_id and entry.device_id and device_registry:
                    device_entry = device_registry.async_get(entry.device_id)
                    if device_entry and hasattr(device_entry, "area_id"):
                        area_id = device_entry.area_id

                # Resolve area_name from area_id
                if area_id and area_registry:
                    area_entry = area_registry.async_get_area(area_id)
                    if area_entry and hasattr(area_entry, "name"):
                        area_name = area_entry.name

                result.append(
                    {
                        "entity_id": entry.entity_id,
                        "device_id": entry.device_id,
                        "platform": entry.platform,
                        "disabled": entry.disabled,
                        "area_id": area_id,
                        "area_name": area_name,
                        "original_name": entry.original_name,
                        "unique_id": entry.unique_id,
                        "device_class": device_class,
                        "state_class": state_class,
                        "unit_of_measurement": unit_of_measurement,
                    }
                )

            return result
        except Exception as e:
            _LOGGER.exception("Error getting entity registry entries: %s", str(e))
            return [{"error": f"Error getting entity registry entries: {str(e)}"}]

    async def get_device_registry(self) -> List[Dict]:
        """Get device registry entries"""
        _LOGGER.debug("Requesting all device registry entries")
        try:
            from homeassistant.helpers import device_registry as dr

            registry = dr.async_get(self.hass)
            if not registry:
                return []
            return [
                {
                    "id": device.id,
                    "name": device.name,
                    "model": device.model,
                    "manufacturer": device.manufacturer,
                    "sw_version": device.sw_version,
                    "hw_version": device.hw_version,
                    "connections": (
                        list(device.connections) if device.connections else []
                    ),
                    "identifiers": (
                        list(device.identifiers) if device.identifiers else []
                    ),
                    "area_id": device.area_id,
                    "disabled": device.disabled_by is not None,
                    "entry_type": (
                        device.entry_type.value if device.entry_type else None
                    ),
                    "name_by_user": device.name_by_user,
                }
                for device in registry.devices.values()
            ]
        except Exception as e:
            _LOGGER.exception("Error getting device registry entries: %s", str(e))
            return [{"error": f"Error getting device registry entries: {str(e)}"}]

    async def get_history(self, entity_id: str, hours: int = 24) -> List[Dict]:
        """Get historical state changes for an entity"""
        _LOGGER.debug("Requesting historical state changes for entity: %s", entity_id)
        try:
            from homeassistant.components.recorder.history import get_significant_states

            now = dt_util.utcnow()
            start = now - timedelta(hours=hours)

            # Get history using the recorder history module
            history_data = await self.hass.async_add_executor_job(
                get_significant_states,
                self.hass,
                start,
                now,
                [entity_id],
            )

            # Convert to serializable format
            result = []
            for entity_id_key, states in history_data.items():
                for state in states:
                    # Skip if it's a dict (mypy type narrowing)
                    if isinstance(state, dict):
                        continue
                    result.append(
                        {
                            "entity_id": state.entity_id,
                            "state": state.state,
                            "last_changed": state.last_changed.isoformat(),
                            "last_updated": state.last_updated.isoformat(),
                            "attributes": dict(state.attributes),
                        }
                    )
            return result
        except Exception as e:
            _LOGGER.exception("Error getting history: %s", str(e))
            return [{"error": f"Error getting history: {str(e)}"}]

    async def get_area_registry(self) -> Dict[str, Any]:
        """Get area registry information"""
        _LOGGER.debug("Get area registry information")
        try:
            from homeassistant.helpers import area_registry as ar

            registry = ar.async_get(self.hass)
            if not registry:
                return {}

            result = {}
            for area in registry.areas.values():
                result[area.id] = {
                    "name": area.name,
                    "normalized_name": area.normalized_name,
                    "picture": area.picture,
                    "icon": area.icon,
                    "floor_id": area.floor_id,
                    "labels": list(area.labels) if area.labels else [],
                }
            return result
        except Exception as e:
            _LOGGER.exception("Error getting area registry: %s", str(e))
            return {"error": f"Error getting area registry: {str(e)}"}

    async def get_person_data(self) -> List[Dict]:
        """Get person tracking information"""
        _LOGGER.debug("Requesting person tracking information")
        try:
            result = []
            for state in self.hass.states.async_all("person"):
                result.append(
                    {
                        "entity_id": state.entity_id,
                        "name": state.attributes.get("friendly_name", state.entity_id),
                        "state": state.state,
                        "latitude": state.attributes.get("latitude"),
                        "longitude": state.attributes.get("longitude"),
                        "source": state.attributes.get("source"),
                        "gps_accuracy": state.attributes.get("gps_accuracy"),
                        "last_changed": (
                            state.last_changed.isoformat()
                            if state.last_changed
                            else None
                        ),
                    }
                )
            return result
        except Exception as e:
            _LOGGER.exception("Error getting person tracking information: %s", str(e))
            return [{"error": f"Error getting person tracking information: {str(e)}"}]

    async def get_statistics(self, entity_id: str) -> Dict:
        """Get statistics for an entity"""
        _LOGGER.debug("Requesting statistics for entity: %s", entity_id)
        try:
            from homeassistant.components import recorder

            # Check if recorder is available
            if not self.hass.data.get(recorder.DATA_INSTANCE):
                return {"error": "Recorder component is not available"}

            # from homeassistant.components.recorder.statistics import get_latest_short_term_statistics
            import homeassistant.components.recorder.statistics as stats_module

            # Get latest statistics
            stats = await self.hass.async_add_executor_job(
                # get_latest_short_term_statistics,
                stats_module.get_last_short_term_statistics,
                self.hass,
                1,
                entity_id,
                True,
                set(),
            )

            if entity_id in stats:
                stat_data = stats[entity_id][0] if stats[entity_id] else {}
                return {
                    "entity_id": entity_id,
                    "start": stat_data.get("start"),
                    "mean": stat_data.get("mean"),
                    "min": stat_data.get("min"),
                    "max": stat_data.get("max"),
                    "last_reset": stat_data.get("last_reset"),
                    "state": stat_data.get("state"),
                    "sum": stat_data.get("sum"),
                }
            else:
                return {"error": f"No statistics available for entity {entity_id}"}
        except Exception as e:
            _LOGGER.exception("Error getting statistics: %s", str(e))
            return {"error": f"Error getting statistics: {str(e)}"}

    async def get_scenes(self) -> List[Dict]:
        """Get scene configurations"""
        _LOGGER.debug("Requesting scene configurations")
        try:
            result = []
            for state in self.hass.states.async_all("scene"):
                result.append(
                    {
                        "entity_id": state.entity_id,
                        "name": state.attributes.get("friendly_name", state.entity_id),
                        "last_activated": state.attributes.get("last_activated"),
                        "icon": state.attributes.get("icon"),
                        "last_changed": (
                            state.last_changed.isoformat()
                            if state.last_changed
                            else None
                        ),
                    }
                )
            return result
        except Exception as e:
            _LOGGER.exception("Error getting scene configurations: %s", str(e))
            return [{"error": f"Error getting scene configurations: {str(e)}"}]

    async def get_weather_data(self) -> Dict[str, Any]:
        """Get weather data from any available weather entity in the system."""
        try:
            # Find all weather entities
            weather_entities = [
                state
                for state in self.hass.states.async_all()
                if state.domain == "weather"
            ]

            if not weather_entities:
                return {
                    "error": "No weather entities found in the system. Please add a weather integration."
                }

            # Use the first available weather entity
            state = weather_entities[0]
            _LOGGER.debug("Using weather entity: %s", state.entity_id)

            # Get all available attributes
            all_attributes = state.attributes
            _LOGGER.debug(
                "Available weather attributes: %s", json.dumps(all_attributes)
            )

            # Get forecast data
            forecast = all_attributes.get("forecast", [])

            # Process forecast data
            processed_forecast = []
            for day in forecast:
                forecast_entry = {
                    "datetime": day.get("datetime"),
                    "temperature": day.get("temperature"),
                    "condition": day.get("condition"),
                    "precipitation": day.get("precipitation"),
                    "precipitation_probability": day.get("precipitation_probability"),
                    "humidity": day.get("humidity"),
                    "wind_speed": day.get("wind_speed"),
                    "wind_bearing": day.get("wind_bearing"),
                }
                # Only add entries that have at least some data
                if any(v is not None for v in forecast_entry.values()):
                    processed_forecast.append(forecast_entry)

            # Get current weather data
            current = {
                "entity_id": state.entity_id,
                "temperature": all_attributes.get("temperature"),
                "humidity": all_attributes.get("humidity"),
                "pressure": all_attributes.get("pressure"),
                "wind_speed": all_attributes.get("wind_speed"),
                "wind_bearing": all_attributes.get("wind_bearing"),
                "condition": state.state,
                "forecast_available": len(processed_forecast) > 0,
            }

            # Log the processed data for debugging
            _LOGGER.debug(
                "Processed weather data: %s",
                json.dumps(
                    {"current": current, "forecast_count": len(processed_forecast)}
                ),
            )

            return {"current": current, "forecast": processed_forecast}
        except Exception as e:
            _LOGGER.exception("Error getting weather data: %s", str(e))
            return {"error": f"Error getting weather data: {str(e)}"}

    async def create_automation(
        self, automation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new automation with validation and sanitization."""
        try:
            _LOGGER.debug(
                "Creating automation with config: %s", json.dumps(automation_config)
            )

            # Validate required fields
            if not all(
                key in automation_config for key in ["alias", "trigger", "action"]
            ):
                return {"error": "Missing required fields in automation configuration"}

            # Sanitize configuration
            sanitized_config = self._sanitize_automation_config(automation_config)

            # Generate a unique ID for the automation
            automation_id = f"ai_agent_auto_{int(time.time() * 1000)}"

            # Create the automation entry
            automation_entry = {
                "id": automation_id,
                "alias": sanitized_config["alias"],
                "description": sanitized_config.get("description", ""),
                "trigger": sanitized_config["trigger"],
                "condition": sanitized_config.get("condition", []),
                "action": sanitized_config["action"],
                "mode": sanitized_config.get("mode", "single"),
            }

            # Read current automations.yaml using async executor
            automations_path = self.hass.config.path("automations.yaml")
            try:
                current_automations = await self.hass.async_add_executor_job(
                    lambda: yaml.safe_load(open(automations_path, "r")) or []
                )
            except FileNotFoundError:
                current_automations = []

            # Check for duplicate automation names
            if any(
                auto.get("alias") == automation_entry["alias"]
                for auto in current_automations
            ):
                return {
                    "error": f"An automation with the name '{automation_entry['alias']}' already exists"
                }

            # Append new automation
            current_automations.append(automation_entry)

            # Write back to file using async executor
            await self.hass.async_add_executor_job(
                lambda: yaml.dump(
                    current_automations,
                    open(automations_path, "w"),
                    default_flow_style=False,
                )
            )

            # Reload automations
            await self.hass.services.async_call("automation", "reload")

            # Clear automation-related caches
            self._cache.clear()

            return {
                "success": True,
                "message": f"Automation '{automation_entry['alias']}' created successfully",
            }

        except Exception as e:
            _LOGGER.exception("Error creating automation: %s", str(e))
            return {"error": f"Error creating automation: {str(e)}"}

    async def get_dashboards(self) -> List[Dict[str, Any]]:
        """Get list of all dashboards."""
        try:
            _LOGGER.debug("Requesting all dashboards")

            # Get dashboards via WebSocket API
            ws_api = self.hass.data.get("websocket_api")
            if not ws_api:
                return [{"error": "WebSocket API not available"}]

            # Use the lovelace service to get dashboards
            try:
                from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN

                # Get lovelace data using property access (required for HA 2026.2+)
                # lovelace_data is a LovelaceData dataclass with a 'dashboards' attribute
                lovelace_data = self.hass.data.get(LOVELACE_DOMAIN)
                if lovelace_data is None:
                    return [{"error": "Lovelace not available"}]

                # Safety check for dashboards attribute (backward compatibility)
                if not hasattr(lovelace_data, "dashboards"):
                    return [{"error": "Lovelace dashboards not available"}]

                # Use property access instead of dictionary access
                dashboards = lovelace_data.dashboards

                # Get YAML dashboard configs for metadata (title, icon, etc.)
                # yaml_dashboards contains the configuration with metadata
                yaml_configs = getattr(lovelace_data, "yaml_dashboards", {}) or {}

                dashboard_list = []

                # Iterate over all dashboards (None key = default dashboard)
                for url_path, dashboard_obj in dashboards.items():
                    # Try to get metadata from yaml_dashboards first
                    yaml_config = yaml_configs.get(url_path, {}) or {}

                    # Get title - check yaml config, then use defaults
                    title = yaml_config.get("title")
                    if not title:
                        title = (
                            "Overview"
                            if url_path is None
                            else (url_path or "Dashboard")
                        )

                    # Get icon - check yaml config, then use defaults
                    icon = yaml_config.get("icon")
                    if not icon:
                        icon = "mdi:home" if url_path is None else "mdi:view-dashboard"

                    # Get sidebar/admin settings from yaml config or defaults
                    show_in_sidebar = yaml_config.get("show_in_sidebar", True)
                    require_admin = yaml_config.get("require_admin", False)

                    dashboard_list.append(
                        {
                            "url_path": url_path,
                            "title": title,
                            "icon": icon,
                            "show_in_sidebar": show_in_sidebar,
                            "require_admin": require_admin,
                        }
                    )

                _LOGGER.debug("Found %d dashboards", len(dashboard_list))
                return dashboard_list

            except Exception as e:
                _LOGGER.warning("Could not get dashboards via lovelace: %s", str(e))
                return [{"error": f"Could not retrieve dashboards: {str(e)}"}]

        except Exception as e:
            _LOGGER.exception("Error getting dashboards: %s", str(e))
            return [{"error": f"Error getting dashboards: {str(e)}"}]

    async def get_dashboard_config(
        self, dashboard_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get configuration of a specific dashboard."""
        try:
            _LOGGER.debug(
                "Requesting dashboard config for: %s", dashboard_url or "default"
            )

            # Get dashboard configuration
            try:
                from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN

                # Get lovelace data using property access (required for HA 2026.2+)
                lovelace_data = self.hass.data.get(LOVELACE_DOMAIN)
                if lovelace_data is None:
                    return {"error": "Lovelace not available"}

                # Safety check for dashboards attribute (backward compatibility)
                if not hasattr(lovelace_data, "dashboards"):
                    return {"error": "Lovelace dashboards not available"}

                # Use property access instead of dictionary access
                # The dashboards dict uses None as key for the default dashboard
                dashboards = lovelace_data.dashboards

                # Get the dashboard (None key = default dashboard)
                dashboard_key = None if dashboard_url is None else dashboard_url
                if dashboard_key in dashboards:
                    dashboard = dashboards[dashboard_key]
                    config = await dashboard.async_get_info()
                    return dict(config) if config else {"error": "No dashboard config"}
                else:
                    if dashboard_url is None:
                        return {"error": "Default dashboard not found"}
                    else:
                        return {"error": f"Dashboard '{dashboard_url}' not found"}

            except Exception as e:
                _LOGGER.warning("Could not get dashboard config: %s", str(e))
                return {"error": f"Could not retrieve dashboard config: {str(e)}"}

        except Exception as e:
            _LOGGER.exception("Error getting dashboard config: %s", str(e))
            return {"error": f"Error getting dashboard config: {str(e)}"}

    async def create_dashboard(
        self, dashboard_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new dashboard using Home Assistant's Lovelace WebSocket API."""
        try:
            _LOGGER.debug(
                "Creating dashboard with config: %s",
                json.dumps(dashboard_config, default=str),
            )

            # Validate required fields
            if not dashboard_config.get("title"):
                return {"error": "Dashboard title is required"}

            if not dashboard_config.get("url_path"):
                return {"error": "Dashboard URL path is required"}

            # Sanitize the URL path
            url_path = (
                dashboard_config["url_path"].lower().replace(" ", "-").replace("_", "-")
            )

            # Prepare dashboard configuration for Lovelace
            dashboard_data = {
                "title": dashboard_config["title"],
                "icon": dashboard_config.get("icon", "mdi:view-dashboard"),
                "show_in_sidebar": dashboard_config.get("show_in_sidebar", True),
                "require_admin": dashboard_config.get("require_admin", False),
                "views": dashboard_config.get("views", []),
            }

            try:
                # Create dashboard file directly - this is the most reliable method
                import os

                import yaml

                # Create the dashboard YAML file
                lovelace_config_file = self.hass.config.path(
                    f"ui-lovelace-{url_path}.yaml"
                )

                # Use async_add_executor_job to perform file I/O asynchronously
                def write_dashboard_file():
                    with open(lovelace_config_file, "w") as f:
                        yaml.dump(
                            dashboard_data,
                            f,
                            default_flow_style=False,
                            allow_unicode=True,
                        )

                await self.hass.async_add_executor_job(write_dashboard_file)

                _LOGGER.info(
                    "Successfully created dashboard file: %s", lovelace_config_file
                )

                # Now update configuration.yaml
                try:
                    config_file = self.hass.config.path("configuration.yaml")
                    dashboard_config_entry = {
                        url_path: {
                            "mode": "yaml",
                            "title": dashboard_config["title"],
                            "icon": dashboard_config.get("icon", "mdi:view-dashboard"),
                            "show_in_sidebar": dashboard_config.get(
                                "show_in_sidebar", True
                            ),
                            "filename": f"ui-lovelace-{url_path}.yaml",
                        }
                    }

                    def update_config_file():
                        try:
                            with open(config_file, "r") as f:
                                content = f.read()

                            # Dashboard configuration to add
                            dashboard_yaml = f"""    {url_path}:
      mode: yaml
      title: {dashboard_config['title']}
      icon: {dashboard_config.get('icon', 'mdi:view-dashboard')}
      show_in_sidebar: {str(dashboard_config.get('show_in_sidebar', True)).lower()}
      filename: ui-lovelace-{url_path}.yaml"""

                            # Check if lovelace section exists
                            if "lovelace:" not in content:
                                # Add complete lovelace section at the end
                                lovelace_section = f"""
# Lovelace dashboards configuration added by AI Agent
lovelace:
  dashboards:
{dashboard_yaml}
"""
                                with open(config_file, "a") as f:
                                    f.write(lovelace_section)
                                return True

                            # If lovelace exists, check for dashboards section
                            lines = content.split("\n")
                            new_lines = []
                            dashboard_added = False
                            in_lovelace = False
                            lovelace_indent = 0

                            for i, line in enumerate(lines):
                                new_lines.append(line)

                                # Detect lovelace section
                                if (
                                    line.strip() == "lovelace:"
                                    or line.strip().startswith("lovelace:")
                                ):
                                    in_lovelace = True
                                    lovelace_indent = len(line) - len(line.lstrip())
                                    continue

                                # If we're in lovelace section
                                if in_lovelace:
                                    current_indent = (
                                        len(line) - len(line.lstrip())
                                        if line.strip()
                                        else 0
                                    )

                                    # If we hit another top-level section, we're out of lovelace
                                    if (
                                        line.strip()
                                        and current_indent <= lovelace_indent
                                        and not line.startswith(" ")
                                    ):
                                        if line.strip() != "lovelace:":
                                            in_lovelace = False

                                    # Look for dashboards section
                                    if in_lovelace and "dashboards:" in line:
                                        # Add our dashboard after the dashboards: line
                                        new_lines.append(dashboard_yaml)
                                        dashboard_added = True
                                        in_lovelace = False  # We're done
                                        break

                            # If we found lovelace but no dashboards section, add it
                            if not dashboard_added and "lovelace:" in content:
                                # Find lovelace section and add dashboards
                                new_lines = []
                                for line in lines:
                                    new_lines.append(line)
                                    if (
                                        line.strip() == "lovelace:"
                                        or line.strip().startswith("lovelace:")
                                    ):
                                        # Add dashboards section right after lovelace
                                        new_lines.append("  dashboards:")
                                        new_lines.append(dashboard_yaml)
                                        dashboard_added = True
                                        break

                            if dashboard_added:
                                with open(config_file, "w") as f:
                                    f.write("\n".join(new_lines))
                                return True
                            else:
                                # Last resort: append to end of file
                                with open(config_file, "a") as f:
                                    f.write(f"\n  dashboards:\n{dashboard_yaml}\n")
                                return True

                        except Exception as e:
                            _LOGGER.error(
                                "Failed to update configuration.yaml: %s", str(e)
                            )
                            # Fallback to simple append method
                            try:
                                with open(config_file, "r") as f:
                                    content = f.read()

                                # Check if lovelace section exists
                                if "lovelace:" not in content:
                                    # Add lovelace section
                                    lovelace_config = f"""
# Lovelace dashboards
lovelace:
  dashboards:
    {url_path}:
      mode: yaml
      title: {dashboard_config['title']}
      icon: {dashboard_config.get('icon', 'mdi:view-dashboard')}
      show_in_sidebar: {str(dashboard_config.get('show_in_sidebar', True)).lower()}
      filename: ui-lovelace-{url_path}.yaml
"""
                                    with open(config_file, "a") as f:
                                        f.write(lovelace_config)
                                else:
                                    # Add to existing lovelace section (simple approach)
                                    dashboard_entry = f"""    {url_path}:
      mode: yaml
      title: {dashboard_config['title']}
      icon: {dashboard_config.get('icon', 'mdi:view-dashboard')}
      show_in_sidebar: {str(dashboard_config.get('show_in_sidebar', True)).lower()}
      filename: ui-lovelace-{url_path}.yaml
"""
                                    # Find the dashboards section and add to it
                                    lines = content.split("\n")
                                    new_lines = []
                                    in_dashboards = False
                                    dashboards_indented = False

                                    for line in lines:
                                        new_lines.append(line)
                                        if (
                                            "dashboards:" in line
                                            and "lovelace"
                                            in content[: content.find(line)]
                                        ):
                                            in_dashboards = True
                                            # Add our dashboard entry after dashboards:
                                            new_lines.append(dashboard_entry.rstrip())
                                            in_dashboards = False

                                    # If we couldn't find dashboards section, add it under lovelace
                                    if not any("dashboards:" in line for line in lines):
                                        for i, line in enumerate(new_lines):
                                            if line.strip() == "lovelace:":
                                                new_lines.insert(i + 1, "  dashboards:")
                                                new_lines.insert(
                                                    i + 2, dashboard_entry.rstrip()
                                                )
                                                break

                                    with open(config_file, "w") as f:
                                        f.write("\n".join(new_lines))

                                return True
                            except Exception as fallback_error:
                                _LOGGER.error(
                                    "Fallback config update also failed: %s",
                                    str(fallback_error),
                                )
                                return False

                    config_updated = await self.hass.async_add_executor_job(
                        update_config_file
                    )

                    if config_updated:
                        success_message = f"""Dashboard '{dashboard_config['title']}' created successfully!

✅ Dashboard file created: ui-lovelace-{url_path}.yaml
✅ Configuration.yaml updated automatically

🔄 Please restart Home Assistant to see your new dashboard in the sidebar."""

                        return {
                            "success": True,
                            "message": success_message,
                            "url_path": url_path,
                            "restart_required": True,
                        }
                    else:
                        # Config update failed, provide manual instructions
                        config_instructions = f"""Dashboard '{dashboard_config['title']}' created successfully!

✅ Dashboard file created: ui-lovelace-{url_path}.yaml
⚠️  Could not automatically update configuration.yaml

Please manually add this to your configuration.yaml:

lovelace:
  dashboards:
    {url_path}:
      mode: yaml
      title: {dashboard_config['title']}
      icon: {dashboard_config.get('icon', 'mdi:view-dashboard')}
      show_in_sidebar: {str(dashboard_config.get('show_in_sidebar', True)).lower()}
      filename: ui-lovelace-{url_path}.yaml

Then restart Home Assistant to see your new dashboard in the sidebar."""

                        return {
                            "success": True,
                            "message": config_instructions,
                            "url_path": url_path,
                            "restart_required": True,
                        }

                except Exception as config_error:
                    _LOGGER.error(
                        "Error updating configuration.yaml: %s", str(config_error)
                    )
                    # Provide manual instructions as fallback
                    config_instructions = f"""Dashboard '{dashboard_config['title']}' created successfully!

✅ Dashboard file created: ui-lovelace-{url_path}.yaml
⚠️  Could not automatically update configuration.yaml

Please manually add this to your configuration.yaml:

lovelace:
  dashboards:
    {url_path}:
      mode: yaml
      title: {dashboard_config['title']}
      icon: {dashboard_config.get('icon', 'mdi:view-dashboard')}
      show_in_sidebar: {str(dashboard_config.get('show_in_sidebar', True)).lower()}
      filename: ui-lovelace-{url_path}.yaml

Then restart Home Assistant to see your new dashboard in the sidebar."""

                    return {
                        "success": True,
                        "message": config_instructions,
                        "url_path": url_path,
                        "restart_required": True,
                    }

            except Exception as e:
                _LOGGER.error("Failed to create dashboard file: %s", str(e))
                return {"error": f"Failed to create dashboard file: {str(e)}"}

        except Exception as e:
            _LOGGER.exception("Error creating dashboard: %s", str(e))
            return {"error": f"Error creating dashboard: {str(e)}"}

    async def update_dashboard(
        self, dashboard_url: str, dashboard_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing dashboard using Home Assistant's Lovelace WebSocket API."""
        try:
            _LOGGER.debug(
                "Updating dashboard %s with config: %s",
                dashboard_url,
                json.dumps(dashboard_config, default=str),
            )

            # Prepare updated dashboard configuration
            dashboard_data = {
                "title": dashboard_config.get("title", "Updated Dashboard"),
                "icon": dashboard_config.get("icon", "mdi:view-dashboard"),
                "show_in_sidebar": dashboard_config.get("show_in_sidebar", True),
                "require_admin": dashboard_config.get("require_admin", False),
                "views": dashboard_config.get("views", []),
            }

            try:
                # Update dashboard file directly
                import os

                import yaml

                # Try updating the YAML file
                dashboard_file = self.hass.config.path(
                    f"ui-lovelace-{dashboard_url}.yaml"
                )

                # Check if file exists asynchronously
                def check_file_exists():
                    return os.path.exists(dashboard_file)

                file_exists = await self.hass.async_add_executor_job(check_file_exists)

                if not file_exists:
                    dashboard_file = self.hass.config.path(
                        f"dashboards/{dashboard_url}.yaml"
                    )
                    file_exists = await self.hass.async_add_executor_job(
                        lambda: os.path.exists(dashboard_file)
                    )

                if file_exists:
                    # Use async_add_executor_job to perform file I/O asynchronously
                    def update_dashboard_file():
                        with open(dashboard_file, "w") as f:
                            yaml.dump(
                                dashboard_data,
                                f,
                                default_flow_style=False,
                                allow_unicode=True,
                            )

                    await self.hass.async_add_executor_job(update_dashboard_file)

                    _LOGGER.info(
                        "Successfully updated dashboard file: %s", dashboard_file
                    )
                    return {
                        "success": True,
                        "message": f"Dashboard '{dashboard_url}' updated successfully!",
                    }
                else:
                    return {"error": f"Dashboard file for '{dashboard_url}' not found"}

            except Exception as e:
                _LOGGER.error("Failed to update dashboard file: %s", str(e))
                return {"error": f"Failed to update dashboard file: {str(e)}"}

        except Exception as e:
            _LOGGER.exception("Error updating dashboard: %s", str(e))
            return {"error": f"Error updating dashboard: {str(e)}"}

    async def analyze_dashboard(self, dashboard_url: str) -> Dict[str, Any]:
        """Analyze a dashboard's layout and content.

        Args:
            dashboard_url: URL path of the dashboard to analyze

        Returns:
            Dictionary with analysis results
        """
        try:
            # Get dashboard configuration
            if not hasattr(self, "_lovelace_api"):
                from .ha_documentation import HADocumentationProvider

            # Get dashboards list first
            dashboards_result = await self.get_dashboards()
            if "error" in dashboards_result:
                return {
                    "error": f"Failed to get dashboards: {dashboards_result['error']}"
                }

            # Find the specific dashboard
            dashboard_url_path = dashboard_url
            dashboard_config = None

            for dashboard in dashboards_result.get("dashboards", []):
                if dashboard.get("url_path") == dashboard_url_path:
                    dashboard_config = dashboard
                    break

            if dashboard_config is None:
                # Try to load from file
                import os

                dashboard_file = self.hass.config.path(
                    f"ui-lovelace-{dashboard_url_path}.yaml"
                )
                if os.path.exists(dashboard_file):
                    import yaml as pyyaml

                    with open(dashboard_file, "r") as f:
                        dashboard_config = pyyaml.safe_load(f)
                else:
                    return {
                        "error": f"Dashboard '{dashboard_url_path}' not found"
                    }

            # Get entity list for analysis
            entity_list_result = await self.get_entity_registry()
            entity_list = entity_list_result.get("entities", [])

            # Perform analysis using DashboardAdvisor
            analysis = self.dashboard_advisor.analyze_dashboard(
                dashboard_config, entity_list
            )
            improvements = self.dashboard_advisor.get_improvement_suggestions(
                dashboard_config, analysis
            )

            return {
                "success": True,
                "dashboard_url": dashboard_url_path,
                "dashboard_title": analysis.dashboard_title,
                "analysis": analysis.to_dict(),
                "improvements": [imp.to_dict() for imp in improvements],
                "markdown": analysis.to_markdown(),
            }

        except Exception as e:
            _LOGGER.exception("Error analyzing dashboard: %s", str(e))
            return {"error": f"Error analyzing dashboard: {str(e)}"}

    async def get_card_recommendations(
        self, entities: List[Dict]
    ) -> Dict[str, Any]:
        """Get card type recommendations for entities.

        Args:
            entities: List of entities to create cards for

        Returns:
            Dictionary with card recommendations
        """
        try:
            # Get current cards if we have dashboard context
            current_cards = []
            # Note: In a real implementation, you might want to pass current cards
            # from the dashboard being edited

            recommendations = self.dashboard_advisor.get_card_recommendations(
                entities, current_cards
            )

            return {
                "success": True,
                "recommendations": [rec.to_dict() for rec in recommendations],
                "total_recommendations": len(recommendations),
                "markdown": "\n\n".join(rec.to_markdown() for rec in recommendations),
            }

        except Exception as e:
            _LOGGER.exception("Error getting card recommendations: %s", str(e))
            return {"error": f"Error getting card recommendations: {str(e)}"}

    async def suggest_dashboard_layout(
        self, dashboard_type: str = "general"
    ) -> Dict[str, Any]:
        """Suggest a complete dashboard layout.

        Args:
            dashboard_type: Type of dashboard (general, energy, security, climate, etc.)

        Returns:
            Dictionary with suggested layout
        """
        try:
            # Get relevant entities based on dashboard type
            entity_list_result = await self.get_entity_registry()
            all_entities = entity_list_result.get("entities", [])

            # Filter entities based on dashboard type
            if dashboard_type == "security":
                relevant_entities = [
                    e
                    for e in all_entities
                    if e.get("entity_id", "").startswith(
                        ("camera.", "binary_sensor.", "lock.", "alarm_control_panel.")
                    )
                ]
            elif dashboard_type == "climate":
                relevant_entities = [
                    e
                    for e in all_entities
                    if e.get("entity_id", "").startswith(
                        ("climate.", "sensor.temperature", "sensor.humidity", "fan.")
                    )
                ]
            elif dashboard_type == "energy":
                relevant_entities = [
                    e
                    for e in all_entities
                    if "energy" in e.get("entity_id", "").lower()
                    or "power" in e.get("entity_id", "").lower()
                ]
            elif dashboard_type == "media":
                relevant_entities = [
                    e
                    for e in all_entities
                    if e.get("entity_id", "").startswith("media_player.")
                ]
            else:
                # General - use all entities
                relevant_entities = all_entities

            # Get suggested layout
            suggested_layout = self.dashboard_advisor.suggest_dashboard_layout(
                relevant_entities, dashboard_type
            )

            # Get template if available
            template = self.dashboard_advisor.get_dashboard_template(
                dashboard_type, relevant_entities
            )

            return {
                "success": True,
                "dashboard_type": dashboard_type,
                "suggested_layout": suggested_layout,
                "template": template,
                "entity_count": len(relevant_entities),
                "total_entities": len(all_entities),
            }

        except Exception as e:
            _LOGGER.exception(
                "Error suggesting dashboard layout: %s", str(e)
            )
            return {"error": f"Error suggesting dashboard layout: {str(e)}"}

    async def process_query(
        self,
        user_query: str,
        provider: Optional[str] = None,
        debug: bool = False,
        images: Optional[List[bytes]] = None,
        image_mime_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Process a user query with input validation and rate limiting.

        Args:
            user_query: The user's text query
            provider: Optional AI provider override
            debug: Whether to include debug information
            images: Optional list of raw image bytes for multimodal processing
            image_mime_types: Optional list of MIME types for the images
        """
        try:
            if not user_query or not isinstance(user_query, str):
                return {"success": False, "error": "Invalid query format"}

            # Get the correct configuration for the requested provider
            if provider and provider in self.hass.data[DOMAIN]["configs"]:
                config = self.hass.data[DOMAIN]["configs"][provider]
            else:
                config = self.config

            _LOGGER.debug(f"Processing query with provider: {provider}")
            # Log sanitized config (masks all tokens/keys for security)
            _LOGGER.debug(
                f"Using config: {json.dumps(sanitize_for_logging(config), default=str)}"
            )

            selected_provider = provider or config.get("ai_provider", "llama")
            models_config = config.get("models", {})

            # Process images if provided and multimodal is enabled
            image_attachments = []
            if (
                images
                and self.multimodal_enabled
                and self.image_upload_enabled
            ):
                for i, img_data in enumerate(images):
                    mime_type = (
                        image_mime_types[i]
                        if image_mime_types and i < len(image_mime_types)
                        else "image/jpeg"
                    )

                    result = await self.multimedia_processor.process_image_upload(
                        img_data, mime_type
                    )
                    if result["success"]:
                        image_attachments.append(result["image"])
                    else:
                        return _with_debug(
                            {
                                "success": False,
                                "error": f"Image {i+1} processing failed: {result['error']}",
                            }
                        )

            _LOGGER.debug(
                "Processed %d image attachments for query", len(image_attachments)
            )

            provider_config = {
                "openai": {
                    "token_key": "openai_token",  # nosec B105 - dict-key field name, not a credential value (false positive)
                    "model": models_config.get("openai", "gpt-3.5-turbo"),
                    "client_class": OpenAIClient,
                },
                "gemini": {
                    "token_key": "gemini_token",  # nosec B105 - dict-key field name, not a credential value (false positive)
                    "model": models_config.get("gemini", "gemini-1.5-flash"),
                    "client_class": GeminiClient,
                },
                "openrouter": {
                    "token_key": "openrouter_token",  # nosec B105 - dict-key field name, not a credential value (false positive)
                    "model": models_config.get("openrouter", "openai/gpt-4o"),
                    "client_class": OpenRouterClient,
                },
                "llama": {
                    "token_key": "llama_token",  # nosec B105 - dict-key field name, not a credential value (false positive)
                    "model": models_config.get(
                        "llama", "Llama-4-Maverick-17B-128E-Instruct-FP8"
                    ),
                    "client_class": LlamaClient,
                },
                "anthropic": {
                    "token_key": "anthropic_token",  # nosec B105 - dict-key field name, not a credential value (false positive)
                    "model": models_config.get(
                        "anthropic", "claude-sonnet-4-5-20250929"
                    ),
                    "client_class": AnthropicClient,
                },
                "alter": {
                    "token_key": "alter_token",  # nosec B105 - dict-key field name, not a credential value (false positive)
                    "model": models_config.get("alter", ""),
                    "client_class": AlterClient,
                },
                "zai": {
                    "token_key": "zai_token",  # nosec B105 - dict-key field name, not a credential value (false positive)
                    "model": models_config.get("zai", ""),
                    "client_class": ZaiClient,
                },
                "local_ollama": {
                    "token_key": "local_ollama_url",  # nosec B105 - dict-key field name, not a credential value (false positive)
                    "model": models_config.get("local_ollama", ""),
                    "client_class": LocalOllamaClient,
                },
                "openai_compatible": {
                    "token_key": "openai_compatible_url",  # nosec B105 - dict-key field name, not a credential value (false positive)
                    "model": models_config.get("openai_compatible", ""),
                    "client_class": OpenaiCompatibleClient,
                },
            }

            # Validate provider and get configuration
            if selected_provider not in provider_config:
                _LOGGER.warning(
                    f"Invalid provider {selected_provider}, falling back to llama"
                )
                selected_provider = "llama"

            provider_settings = provider_config[selected_provider]
            token = self.config.get(provider_settings["token_key"])

            def _with_debug(result: Dict[str, Any]) -> Dict[str, Any]:
                """Attach a sanitized trace when UI requests debug info."""
                if debug and "debug" not in result:
                    result["debug"] = self._build_debug_trace(
                        selected_provider,
                        provider_settings,
                        config.get("zai_endpoint", "general"),
                    )
                return result

            # Validate token/URL
            if not token:
                is_url_provider = selected_provider in (
                    "local_ollama",
                    "openai_compatible",
                )
                error_msg = f"No {'URL' if is_url_provider else 'token'} configured for provider {selected_provider}"
                _LOGGER.error(error_msg)
                return _with_debug({"success": False, "error": error_msg})

            # Initialize client
            try:
                if selected_provider == "zai":
                    # ZaiClient takes (token, model, endpoint_type)
                    endpoint_type = config.get("zai_endpoint", "general")
                    self.ai_client = provider_settings["client_class"](
                        token=token,
                        model=provider_settings["model"],
                        endpoint_type=endpoint_type,
                    )
                    _LOGGER.debug(
                        f"Initialized {selected_provider} client with model {provider_settings['model']}, endpoint_type {endpoint_type}"
                    )
                elif selected_provider in ("local_ollama", "openai_compatible"):
                    # LocalOllamaClient and OpenaiCompatibleClient take (url, model)
                    if selected_provider == "local_ollama":
                        # Support legacy local_url
                        url = token or config.get("local_url")
                    else:
                        url = token
                    self.ai_client = provider_settings["client_class"](
                        url, provider_settings["model"]
                    )
                    _LOGGER.debug(
                        f"Initialized {selected_provider} client with model {provider_settings['model']}"
                    )
                else:
                    # Other clients take (token, model)
                    self.ai_client = provider_settings["client_class"](
                        token=token, model=provider_settings["model"]
                    )
                    _LOGGER.debug(
                        f"Initialized {selected_provider} client with model {provider_settings['model']}"
                    )
            except Exception as e:
                error_msg = f"Error initializing {selected_provider} client: {str(e)}"
                _LOGGER.error(error_msg)
                return _with_debug({"success": False, "error": error_msg})

            # Process the query with rate limiting and retries
            if not self._check_rate_limit():
                return _with_debug(
                    {
                        "success": False,
                        "error": "Rate limit exceeded. Please wait before trying again.",
                    }
                )

            # Sanitize user input
            user_query = user_query.strip()[:1000]  # Limit length and trim whitespace

            _LOGGER.debug("Processing new query: %s", user_query)

            # Check cache for identical query
            cache_key = f"query_{hash(user_query)}_{provider}_{debug}"
            cached_result = self._get_cached_data(cache_key)
            if cached_result:
                return (
                    dict(cached_result)
                    if isinstance(cached_result, dict)
                    else {"error": "Invalid cached result"}
                )

            # Add system message to conversation if it's the first message
            if not self.conversation_history:
                _LOGGER.debug("Adding system message to new conversation")
                self.conversation_history.append(self.system_prompt)

            # Add user query to conversation
            self.conversation_history.append({"role": "user", "content": user_query})
            _LOGGER.debug("Added user query to conversation history")

            max_iterations = 5  # Prevent infinite loops
            iteration = 0
            
            # Track action details for frontend display
            action_details = []

            while iteration < max_iterations:
                iteration += 1
                _LOGGER.debug(f"Processing iteration {iteration} of {max_iterations}")

                try:
                    # Get AI response (use multimodal method if images are present)
                    _LOGGER.debug("Requesting response from AI provider")
                    if image_attachments:
                        _LOGGER.debug("Using multimodal AI response with %d images", len(image_attachments))
                        response = await self._get_ai_response_with_images(user_query, image_attachments)
                    else:
                        response = await self._get_ai_response()
                    _LOGGER.debug("Received response from AI provider: %s", response)

                    try:
                        # Try to parse the response as JSON with simplified approach
                        response_clean = response.strip()

                        # Remove potential BOM and other invisible characters
                        import codecs

                        if response_clean.startswith(codecs.BOM_UTF8.decode("utf-8")):
                            response_clean = response_clean[1:]

                        # Remove other common invisible characters
                        invisible_chars = [
                            "\ufeff",
                            "\u200b",
                            "\u200c",
                            "\u200d",
                            "\u2060",
                        ]
                        for char in invisible_chars:
                            response_clean = response_clean.replace(char, "")

                        _LOGGER.debug(
                            "Cleaned response length: %d", len(response_clean)
                        )
                        _LOGGER.debug(
                            "Cleaned response first 100 chars: %s", response_clean[:100]
                        )
                        _LOGGER.debug(
                            "Cleaned response last 100 chars: %s", response_clean[-100:]
                        )

                        # Simple strategy: try to parse the cleaned response directly
                        response_data = None
                        try:
                            _LOGGER.debug("Attempting basic JSON parse...")
                            response_data = json.loads(response_clean)
                            _LOGGER.debug("Basic JSON parse succeeded!")
                        except json.JSONDecodeError as e:
                            _LOGGER.warning("Basic JSON parse failed: %s", str(e))
                            _LOGGER.debug("JSON error position: %d", e.pos)
                            if e.pos < len(response_clean):
                                _LOGGER.debug(
                                    "Character at error position: %s (ord: %d)",
                                    repr(response_clean[e.pos]),
                                    ord(response_clean[e.pos]),
                                )
                                _LOGGER.debug(
                                    "Context around error: %s",
                                    repr(
                                        response_clean[max(0, e.pos - 10) : e.pos + 10]
                                    ),
                                )

                            # Fallback: try to extract JSON by finding the first { and last }
                            json_start = response_clean.find("{")
                            json_end = response_clean.rfind("}")

                            if (
                                json_start != -1
                                and json_end != -1
                                and json_end > json_start
                            ):
                                json_part = response_clean[json_start : json_end + 1]
                                _LOGGER.debug(
                                    "Trying fallback extraction from pos %d to %d",
                                    json_start,
                                    json_end,
                                )
                                _LOGGER.debug("Extracted JSON: %s", json_part[:200])

                                try:
                                    response_data = json.loads(json_part)
                                    _LOGGER.debug("Fallback JSON extraction succeeded!")
                                except json.JSONDecodeError as e2:
                                    _LOGGER.warning(
                                        "Fallback JSON extraction also failed: %s",
                                        str(e2),
                                    )
                                    raise e  # Re-raise the original error
                            else:
                                _LOGGER.warning(
                                    "Could not find JSON boundaries in response"
                                )
                                raise e  # Re-raise the original error

                        if response_data is None:
                            raise json.JSONDecodeError(
                                "All parsing strategies failed", response_clean, 0
                            )

                        _LOGGER.debug("Successfully parsed JSON response")
                        _LOGGER.debug(
                            "Parsed response type: %s",
                            response_data.get("request_type", "unknown"),
                        )

                        # Check if this is a data request (either format)
                        data_request_types = [
                            "get_entity_state",
                            "get_entities_by_domain",
                            "get_entities_by_device_class",
                            "get_climate_related_entities",
                            "get_entities_by_area",
                            "get_entities",
                            "get_calendar_events",
                            "get_automations",
                            "get_entity_registry",
                            "get_device_registry",
                            "get_weather_data",
                            "get_area_registry",
                            "get_history",
                            "get_person_data",
                            "get_statistics",
                            "get_scenes",
                            "get_dashboards",
                            "get_dashboard_config",
                            "set_entity_state",
                            "create_automation",
                            "create_dashboard",
                            "update_dashboard",
                        ]

                        if (
                            response_data.get("request_type") == "data_request"
                            or response_data.get("request_type") in data_request_types
                        ):
                            # Handle data request (both standard format and direct request type)
                            if response_data.get("request_type") == "data_request":
                                request_type = response_data.get("request")
                            else:
                                request_type = response_data.get("request_type")
                            parameters = response_data.get("parameters", {})
                            _LOGGER.debug(
                                "Processing data request: %s with parameters: %s",
                                request_type,
                                json.dumps(parameters),
                            )

                            # Add AI's response to conversation history
                            self.conversation_history.append(
                                {
                                    "role": "assistant",
                                    "content": json.dumps(
                                        response_data
                                    ),  # Store clean JSON
                                }
                            )

                            # Get requested data
                            data: Union[Dict[str, Any], List[Dict[str, Any]]]
                            if request_type == "get_entity_state":
                                data = await self.get_entity_state(
                                    parameters.get("entity_id")
                                )
                            elif request_type == "get_entities_by_domain":
                                data = await self.get_entities_by_domain(
                                    parameters.get("domain")
                                )
                            elif request_type == "get_entities_by_area":
                                data = await self.get_entities_by_area(
                                    parameters.get("area_id")
                                )
                            elif request_type == "get_entities":
                                data = await self.get_entities(
                                    area_id=parameters.get("area_id"),
                                    area_ids=parameters.get("area_ids"),
                                )
                            elif request_type == "get_entities_by_device_class":
                                data = await self.get_entities_by_device_class(
                                    parameters.get("device_class"),
                                    parameters.get("domain"),
                                )
                            elif request_type == "get_climate_related_entities":
                                data = await self.get_climate_related_entities()
                            elif request_type == "get_calendar_events":
                                data = await self.get_calendar_events(
                                    parameters.get("entity_id")
                                )
                            elif request_type == "get_automations":
                                data = await self.get_automations()
                            elif request_type == "get_entity_registry":
                                data = await self.get_entity_registry()
                            elif request_type == "get_device_registry":
                                data = await self.get_device_registry()
                            elif request_type == "get_weather_data":
                                data = await self.get_weather_data()
                            elif request_type == "get_area_registry":
                                data = await self.get_area_registry()
                            elif request_type == "get_history":
                                data = await self.get_history(
                                    parameters.get("entity_id"),
                                    parameters.get("hours", 24),
                                )
                            elif request_type == "get_person_data":
                                data = await self.get_person_data()
                            elif request_type == "get_statistics":
                                data = await self.get_statistics(
                                    parameters.get("entity_id")
                                )
                            elif request_type == "get_scenes":
                                data = await self.get_scenes()
                            elif request_type == "get_dashboards":
                                data = await self.get_dashboards()
                            elif request_type == "get_dashboard_config":
                                data = await self.get_dashboard_config(
                                    parameters.get("dashboard_url")
                                )
                            elif request_type == "set_entity_state":
                                data = await self.set_entity_state(
                                    parameters.get("entity_id"),
                                    parameters.get("state"),
                                    parameters.get("attributes"),
                                )
                            elif request_type == "create_automation":
                                data = await self.create_automation(
                                    parameters.get("automation")
                                )
                            elif request_type == "create_dashboard":
                                data = await self.create_dashboard(
                                    parameters.get("dashboard_config")
                                )
                            elif request_type == "update_dashboard":
                                data = await self.update_dashboard(
                                    parameters.get("dashboard_url"),
                                    parameters.get("dashboard_config"),
                                )
                            else:
                                data = {
                                    "error": f"Unknown request type: {request_type}"
                                }
                                _LOGGER.warning(
                                    "Unknown request type: %s", request_type
                                )

                            # Check if any data request resulted in an error
                            if isinstance(data, dict) and "error" in data:
                                return _with_debug(
                                    {"success": False, "error": data["error"]}
                                )
                            elif isinstance(data, list) and any(
                                "error" in item
                                for item in data
                                if isinstance(item, dict)
                            ):
                                errors = [
                                    item["error"]
                                    for item in data
                                    if isinstance(item, dict) and "error" in item
                                ]
                                return _with_debug(
                                    {"success": False, "error": "; ".join(errors)}
                                )

                            _LOGGER.debug(
                                "Retrieved data for request: %s",
                                json.dumps(data, default=str),
                            )

                            # Add data to conversation as a user message (not system to avoid overwriting system prompt in Anthropic API)
                            self.conversation_history.append(
                                {
                                    "role": "user",
                                    "content": json.dumps({"data": data}, default=str),
                                }
                            )
                            continue

                        elif response_data.get("request_type") == "final_response":
                            # Add final response to conversation history
                            self.conversation_history.append(
                                {
                                    "role": "assistant",
                                    "content": json.dumps(
                                        response_data
                                    ),  # Store clean JSON
                                }
                            )

                            # Return final response
                            final_response_text = response_data.get("response", "")
                            _LOGGER.info(
                                "=== FINAL RESPONSE DEBUG === response_type=%s, response_length=%d, response_preview=%s, full_response_data=%s",
                                type(final_response_text).__name__,
                                len(final_response_text) if final_response_text else 0,
                                repr(final_response_text[:200]) if final_response_text else "None",
                                json.dumps(response_data, default=str),
                            )
                            if not final_response_text or final_response_text.strip() == "":
                                _LOGGER.warning(
                                    "WARNING: AI returned empty final_response! Generating fallback message. Full response_data: %s",
                                    json.dumps(response_data, default=str),
                                )
                                # Generate a fallback message based on action details
                                fallback_message = self._generate_fallback_response(action_details)
                                final_response_text = fallback_message
                                _LOGGER.info(
                                    "Generated fallback response: %s", fallback_message
                                )
                            result = {
                                "success": True,
                                "answer": final_response_text,
                                "action_details": action_details if action_details else None,
                            }
                            result = _with_debug(result)
                            self._set_cached_data(cache_key, result)
                            
                            # Auto-save conversation to chat history
                            try:
                                import uuid
                                
                                # Get chat history manager from hass.data
                                chat_manager = self.hass.data.get(DOMAIN, {}).get("chat_history_manager")
                                if chat_manager:
                                    # Generate or use existing conversation ID
                                    if not hasattr(self, '_current_conversation_id'):
                                        self._current_conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
                                    
                                    # Build messages list for storage
                                    messages_to_save = []
                                    for msg in self.conversation_history:
                                        content = msg.get("content", "")
                                        role = msg.get("role", "unknown")
                                        # Map role to type for storage
                                        if role == "system":
                                            continue  # Skip system messages
                                        elif role == "user":
                                            msg_type = "user"
                                        elif role == "assistant":
                                            msg_type = "assistant"
                                        else:
                                            msg_type = "unknown"
                                        
                                        # Try to parse JSON content for cleaner storage
                                        text = content
                                        if content.startswith("{"):
                                            try:
                                                parsed = json.loads(content)
                                                if isinstance(parsed, dict) and "response" in parsed:
                                                    text = parsed["response"]
                                                elif isinstance(parsed, dict) and "answer" in parsed:
                                                    text = parsed["answer"]
                                            except (json.JSONDecodeError, ValueError):
                                                pass
                                        
                                        messages_to_save.append({
                                            "type": msg_type,
                                            "text": text,
                                        })
                                    
                                    # Auto-generate name from first user message
                                    auto_name = "Conversation"
                                    for msg in self.conversation_history:
                                        if msg.get("role") == "user":
                                            preview = msg.get("content", "")[:50]
                                            auto_name = f'"{preview}{"..." if len(preview) >= 50 else ""}"'
                                            break
                                    
                                    await chat_manager.save_conversation(
                                        self._current_conversation_id,
                                        messages_to_save,
                                        auto_name,
                                    )
                                    _LOGGER.debug(
                                        "Auto-saved conversation %s with %d messages",
                                        self._current_conversation_id,
                                        len(messages_to_save),
                                    )
                            except Exception as e:
                                _LOGGER.debug("Failed to auto-save conversation: %s", str(e))
                            
                            return result
                        elif (
                            response_data.get("request_type") == "automation_suggestion"
                        ):
                            # Add automation suggestion to conversation history
                            self.conversation_history.append(
                                {
                                    "role": "assistant",
                                    "content": json.dumps(
                                        response_data
                                    ),  # Store clean JSON
                                }
                            )

                            # Return automation suggestion
                            _LOGGER.debug(
                                "Received automation suggestion: %s",
                                json.dumps(response_data.get("automation")),
                            )
                            result = {
                                "success": True,
                                "answer": json.dumps(response_data),
                            }
                            result = _with_debug(result)
                            self._set_cached_data(cache_key, result)
                            return result
                        elif (
                            response_data.get("request_type") == "dashboard_suggestion"
                        ):
                            # Add dashboard suggestion to conversation history
                            self.conversation_history.append(
                                {
                                    "role": "assistant",
                                    "content": json.dumps(
                                        response_data
                                    ),  # Store clean JSON
                                }
                            )

                            # Return dashboard suggestion
                            _LOGGER.debug(
                                "Received dashboard suggestion: %s",
                                json.dumps(response_data.get("dashboard")),
                            )
                            result = {
                                "success": True,
                                "answer": json.dumps(response_data),
                            }
                            result = _with_debug(result)
                            self._set_cached_data(cache_key, result)
                            return result
                        elif response_data.get("request_type") in [
                            "get_entities",
                            "get_entities_by_area",
                        ]:
                            # Handle direct get_entities request (for backward compatibility)
                            parameters = response_data.get("parameters", {})
                            _LOGGER.debug(
                                "Processing direct get_entities request with parameters: %s",
                                json.dumps(parameters),
                            )

                            # Add AI's response to conversation history
                            self.conversation_history.append(
                                {
                                    "role": "assistant",
                                    "content": json.dumps(
                                        response_data
                                    ),  # Store clean JSON
                                }
                            )

                            # Get entities data
                            if response_data.get("request_type") == "get_entities":
                                data = await self.get_entities(
                                    area_id=parameters.get("area_id"),
                                    area_ids=parameters.get("area_ids"),
                                )
                            else:  # get_entities_by_area
                                data = await self.get_entities_by_area(
                                    parameters.get("area_id")
                                )

                            _LOGGER.debug(
                                "Retrieved %d entities",
                                len(data) if isinstance(data, list) else 1,
                            )

                            # Add data to conversation as a user message (not system to avoid overwriting system prompt in Anthropic API)
                            self.conversation_history.append(
                                {
                                    "role": "user",
                                    "content": json.dumps({"data": data}, default=str),
                                }
                            )
                            continue
                        elif response_data.get("request_type") == "call_service":
                            # Handle service call request
                            domain = response_data.get("domain")
                            service = response_data.get("service")
                            target = response_data.get("target", {})
                            service_data = response_data.get("service_data", {})

                            # Resolve nested requests in target
                            if target and "entity_id" in target:
                                entity_id_value = target["entity_id"]
                                if (
                                    isinstance(entity_id_value, dict)
                                    and "request_type" in entity_id_value
                                ):
                                    # This is a nested request, resolve it
                                    nested_request_type = entity_id_value.get(
                                        "request_type"
                                    )
                                    nested_parameters = entity_id_value.get(
                                        "parameters", {}
                                    )

                                    _LOGGER.debug(
                                        "Resolving nested request: %s with parameters: %s",
                                        nested_request_type,
                                        json.dumps(nested_parameters),
                                    )

                                    # Resolve the nested request
                                    if nested_request_type == "get_entities":
                                        entities_data = await self.get_entities(
                                            area_id=nested_parameters.get("area_id"),
                                            area_ids=nested_parameters.get("area_ids"),
                                        )
                                    elif nested_request_type == "get_entities_by_area":
                                        entities_data = await self.get_entities_by_area(
                                            nested_parameters.get("area_id")
                                        )
                                    elif (
                                        nested_request_type == "get_entities_by_domain"
                                    ):
                                        entities_data = (
                                            await self.get_entities_by_domain(
                                                nested_parameters.get("domain")
                                            )
                                        )
                                    else:
                                        _LOGGER.error(
                                            "Unsupported nested request type: %s",
                                            nested_request_type,
                                        )
                                        return {
                                            "success": False,
                                            "error": f"Unsupported nested request type: {nested_request_type}",
                                        }

                                    # Extract entity IDs from the resolved data
                                    if isinstance(entities_data, list):
                                        entity_ids = [
                                            entity.get("entity_id")
                                            for entity in entities_data
                                            if entity.get("entity_id")
                                        ]
                                        target["entity_id"] = entity_ids
                                        _LOGGER.debug(
                                            "Resolved nested request to entity IDs: %s",
                                            entity_ids,
                                        )
                                    else:
                                        _LOGGER.error(
                                            "Nested request returned unexpected data format"
                                        )
                                        return _with_debug(
                                            {
                                                "success": False,
                                                "error": "Nested request returned unexpected data format",
                                            }
                                        )

                            # Handle backward compatibility with old format
                            if not domain or not service:
                                request = response_data.get("request")
                                parameters = response_data.get("parameters", {})

                                if request and "entity_id" in parameters:
                                    entity_id = parameters["entity_id"]
                                    # Infer domain from entity_id
                                    if "." in entity_id:
                                        domain = entity_id.split(".")[0]
                                        service = request
                                        target = {"entity_id": entity_id}
                                        # Remove entity_id from parameters to avoid duplication
                                        service_data = {
                                            k: v
                                            for k, v in parameters.items()
                                            if k != "entity_id"
                                        }
                                        _LOGGER.debug(
                                            "Converted old format: domain=%s, service=%s",
                                            domain,
                                            service,
                                        )

                            _LOGGER.debug(
                                "Processing service call: %s.%s with target: %s and data: %s",
                                domain,
                                service,
                                json.dumps(target),
                                json.dumps(service_data),
                            )

                            # Add AI's response to conversation history
                            self.conversation_history.append(
                                {
                                    "role": "assistant",
                                    "content": json.dumps(
                                        response_data
                                    ),  # Store clean JSON
                                }
                            )

                            # Check permissions before executing service call
                            action = f"{domain}.{service}"
                            entities = target.get("entity_id", [])
                            if isinstance(entities, str):
                                entities = [entities]
                            if not isinstance(entities, list):
                                entities = []

                            # Check permission
                            permission_result = self.permission_checker.check_action(action, entities)

                            if permission_result == DENY:
                                _LOGGER.warning("Permission denied for action: %s", action)
                                return _with_debug({
                                    "success": False,
                                    "error": f"Permission denied for action '{action}'. This action is blacklisted.",
                                    "permission_denied": True,
                                    "action": action,
                                })
                            elif permission_result == PROMPT:
                                # Create permission request
                                request = self.permission_checker.create_permission_request(
                                    action=action,
                                    entities=entities,
                                    reason="AI agent requested this service call"
                                )
                                # Return permission request instead of executing
                                return _with_debug({
                                    "success": True,
                                    "permission_request": {
                                        "request_id": request.request_id,
                                        "action": action,
                                        "target_entities": entities,
                                        "reason": request.reason,
                                        "risk_level": request.risk_level,
                                        "risk_description": self.permission_checker.get_risk_description(request.risk_level),
                                        "expires_at": request.expires_at,
                                    },
                                    "request_type": "permission_request",
                                })

                            # Call the service
                            data = await self.call_service(
                                domain, service, target, service_data
                            )

                            # Check if service call resulted in an error
                            if isinstance(data, dict) and "error" in data:
                                return _with_debug(
                                    {"success": False, "error": data["error"]}
                                )

                            _LOGGER.info(
                                "=== SERVICE CALL DEBUG === domain=%s, service=%s, target=%s, result_success=%s, result_data=%s",
                                domain, service, json.dumps(target, default=str),
                                data.get("success", "N/A") if isinstance(data, dict) else "N/A",
                                json.dumps(data, default=str)[:500] if data else "None",
                            )
                            
                            # Track action details for frontend display
                            action_detail = {
                                "domain": domain,
                                "service": service,
                                "target": target,
                                "service_data": service_data,
                                "result": data
                            }
                            action_details.append(action_detail)

                            # Add data to conversation as a user message (not system to avoid overwriting system prompt in Anthropic API)
                            self.conversation_history.append(
                                {
                                    "role": "user",
                                    "content": json.dumps({"data": data}, default=str),
                                }
                            )
                            _LOGGER.info(
                                "=== LOOP CONTINUE DEBUG === iteration=%d, conversation_history_length=%d, last_3_history_items=%s",
                                iteration, len(self.conversation_history),
                                json.dumps(self.conversation_history[-3:], default=str),
                            )
                            # Go to next iteration to continue the loop
                            continue

                        # Unknown request type
                        _LOGGER.warning(
                            "Unknown response type: %s",
                            response_data.get("request_type"),
                        )
                        return _with_debug(
                            {
                                "success": False,
                                "error": f"Unknown response type: {response_data.get('request_type')}",
                            }
                        )

                    except json.JSONDecodeError as e:
                        # Check if this is a local provider that might have already wrapped the response
                        provider = self.config.get("ai_provider", "unknown")
                        if provider in ("local_ollama", "openai_compatible"):
                            _LOGGER.debug(
                                "Local provider returned non-JSON response (this is normal and handled): %s",
                                response[:200],
                            )
                        else:
                            # Log more of the response to help with debugging for non-local providers
                            response_preview = (
                                response[:1000] if len(response) > 1000 else response
                            )
                            _LOGGER.warning(
                                "Failed to parse response as JSON: %s. Response length: %d. Response preview: %s",
                                str(e),
                                len(response),
                                response_preview,
                            )

                            # Log additional debugging information
                            _LOGGER.debug(
                                "First 50 characters as bytes: %s",
                                response[:50].encode("utf-8") if response else b"",
                            )
                            _LOGGER.debug(
                                "Response starts with: %s",
                                repr(response[:10]) if response else "None",
                            )

                        # Also log the response to a separate debug file for detailed analysis (non-local providers only)
                        if provider not in ("local_ollama", "openai_compatible"):
                            try:
                                import os

                                debug_dir = "/config/ai_agent_ha_debug"

                                def write_debug_file():
                                    if not os.path.exists(debug_dir):
                                        os.makedirs(debug_dir)

                                    import datetime

                                    timestamp = datetime.datetime.now().strftime(
                                        "%Y%m%d_%H%M%S"
                                    )
                                    debug_file = os.path.join(
                                        debug_dir, f"failed_response_{timestamp}.txt"
                                    )

                                    with open(debug_file, "w", encoding="utf-8") as f:
                                        f.write(f"Timestamp: {timestamp}\n")
                                        f.write(f"Provider: {provider}\n")
                                        f.write(f"Error: {str(e)}\n")
                                        f.write(f"Response length: {len(response)}\n")
                                        f.write(
                                            f"Response bytes: {response.encode('utf-8') if response else b''}\n"
                                        )
                                        f.write(f"Response repr: {repr(response)}\n")
                                        f.write(f"Full response:\n{response}\n")

                                    return debug_file

                                # Run file operations in executor to avoid blocking
                                debug_file = await self.hass.async_add_executor_job(
                                    write_debug_file
                                )
                                _LOGGER.info(
                                    "Failed response saved to debug file: %s",
                                    debug_file,
                                )
                            except Exception as debug_error:
                                _LOGGER.debug(
                                    "Could not save debug file: %s", str(debug_error)
                                )

                        # Check if this looks like a corrupted automation suggestion
                        if (
                            response.strip().startswith(
                                '{"request_type": "automation_suggestion'
                            )
                            and len(response) > 10000
                            and response.count("for its use in various fields") > 50
                        ):
                            _LOGGER.warning(
                                "Detected corrupted automation suggestion response with repetitive text"
                            )
                            result = _with_debug(
                                {
                                    "success": False,
                                    "error": "AI generated corrupted automation response. Please try again with a more specific automation request.",
                                }
                            )
                            self._set_cached_data(cache_key, result)
                            return result

                        # If response is not valid JSON, try to wrap it as a final response
                        try:
                            # Truncate extremely long responses to prevent memory issues
                            response_to_wrap = response
                            if len(response) > 50000:
                                response_to_wrap = (
                                    response[:5000]
                                    + "... [Response truncated due to excessive length]"
                                )
                                _LOGGER.warning(
                                    "Truncated extremely long response from %d to 5000 characters",
                                    len(response),
                                )

                            wrapped_response = {
                                "request_type": "final_response",
                                "response": response_to_wrap,
                            }
                            result = {
                                "success": True,
                                "answer": json.dumps(wrapped_response),
                            }
                            _LOGGER.debug("Wrapped non-JSON response as final_response")
                        except Exception as wrap_error:
                            _LOGGER.error(
                                "Failed to wrap response: %s", str(wrap_error)
                            )
                            result = {
                                "success": False,
                                "error": f"Invalid response format: {str(e)}",
                            }

                        result = _with_debug(result)
                        self._set_cached_data(cache_key, result)
                        return result

                except Exception as e:
                    _LOGGER.exception("Error processing AI response: %s", str(e))
                    return _with_debug(
                        {
                            "success": False,
                            "error": f"Error processing AI response: {str(e)}",
                        }
                    )

            # If we've reached max iterations without a final response, use fallback
            _LOGGER.warning("Reached maximum iterations without final response, using fallback")
            fallback_message = self._generate_fallback_response(action_details)
            result = {
                "success": True,
                "answer": fallback_message,
                "action_details": action_details if action_details else None,
            }
            result = _with_debug(result)
            self._set_cached_data(cache_key, result)
            
            # Auto-save conversation to chat history
            try:
                import uuid
                
                # Get chat history manager from hass.data
                chat_manager = self.hass.data.get(DOMAIN, {}).get("chat_history_manager")
                if chat_manager:
                    # Generate or use existing conversation ID
                    if not hasattr(self, '_current_conversation_id'):
                        self._current_conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
                    
                    # Build messages list for storage (simplified version)
                    messages_to_save = []
                    for msg in self.conversation_history:
                        content = msg.get("content", "")
                        role = msg.get("role", "unknown")
                        if role == "system":
                            continue
                        elif role == "user":
                            msg_type = "user"
                        elif role == "assistant":
                            msg_type = "assistant"
                        else:
                            msg_type = "unknown"
                        
                        text = content
                        if content.startswith("{"):
                            try:
                                parsed = json.loads(content)
                                if isinstance(parsed, dict) and "response" in parsed:
                                    text = parsed["response"]
                                elif isinstance(parsed, dict) and "answer" in parsed:
                                    text = parsed["answer"]
                            except (json.JSONDecodeError, ValueError):
                                pass
                        
                        messages_to_save.append({
                            "type": msg_type,
                            "text": text,
                        })
                    
                    auto_name = "Conversation"
                    for msg in self.conversation_history:
                        if msg.get("role") == "user":
                            preview = msg.get("content", "")[:50]
                            auto_name = f'"{preview}{"..." if len(preview) >= 50 else ""}"'
                            break
                    
                    await chat_manager.save_conversation(
                        self._current_conversation_id,
                        messages_to_save,
                        auto_name,
                    )
            except Exception as e:
                _LOGGER.debug("Failed to auto-save conversation: %s", str(e))
            
            return result
            
        except Exception as e:
            _LOGGER.exception("Error in process_query: %s", str(e))
            return _with_debug(
                {"success": False, "error": f"Error in process_query: {str(e)}"}
            )

        except Exception as e:
            _LOGGER.exception("Error in process_query: %s", str(e))
            return _with_debug(
                {"success": False, "error": f"Error in process_query: {str(e)}"}
            )

    def _get_max_tokens_for_provider(self, provider: str) -> int:
        """Get maximum context tokens for the current provider/model.
        
        Args:
            provider: The AI provider name.
            
        Returns:
            Maximum context tokens for the provider.
        """
        MAX_TOKENS = {
            "openai": 128000,  # GPT-4 Turbo
            "gemini": 128000,  # Gemini models
            "anthropic": 200000,  # Claude 3
            "openrouter": 128000,
            "llama": 32768,  # Default Llama
            "local_ollama": 32768,  # Default for local models
            "openai_compatible": 131072,  # Default OpenAI-compatible
            "alter": 8192,
            "zai": 8192,
        }
        return MAX_TOKENS.get(provider, 32768)

    def _build_debug_trace(
        self,
        provider: Optional[str],
        provider_settings: Optional[Dict[str, Any]],
        endpoint_type: Optional[str],
    ) -> Dict[str, Any]:
        """Return a sanitized snapshot of the HA↔AI conversation for UI display."""
        history_tail = (
            self.conversation_history[-20:] if self.conversation_history else []
        )
        return {
            "provider": provider,
            "model": provider_settings.get("model") if provider_settings else None,
            "endpoint_type": endpoint_type,
            "conversation": history_tail,
        }

    async def _get_ai_response(self) -> str:
        """Get response from the selected AI provider with retries and rate limiting."""
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded. Please try again later.")
        retry_count = 0
        last_error = None
        # Limit conversation history to prevent token overflow
        recent_messages = (
            self.conversation_history[-10:]
            if len(self.conversation_history) > 10
            else self.conversation_history
        )
        # Ensure system prompt is always the first message
        if not recent_messages or recent_messages[0].get("role") != "system":
            recent_messages = [self.system_prompt] + recent_messages

        # --- Prompt Compaction Check ---
        # Get max tokens for the current provider
        current_provider = self.config.get("ai_provider", "openai")
        max_tokens = self._get_max_tokens_for_provider(current_provider)
        
        # Estimate token count and check if compaction is needed
        estimated_tokens = self.prompt_compactor.estimate_messages_tokens(recent_messages)
        
        if self.prompt_compactor.should_compact(estimated_tokens, max_tokens):
            _LOGGER.warning(
                "Context window at %d/%d tokens (threshold %.0f%%). Compacting conversation...",
                estimated_tokens,
                max_tokens,
                self.prompt_compactor.threshold_pct * 100,
            )
            try:
                recent_messages, summary = await self.prompt_compactor.compact_conversation(
                    recent_messages, max_tokens, ai_client=self.ai_client
                )
                if summary:
                    _LOGGER.info(
                        "Compacted %d messages into summary of %d tokens",
                        summary.original_message_count,
                        summary.summary_token_count,
                    )
            except Exception as e:
                _LOGGER.warning(
                    "Prompt compaction failed, proceeding with full context: %s", e
                )
        else:
            _LOGGER.debug(
                "Context window at %d/%d tokens - no compaction needed",
                estimated_tokens,
                max_tokens,
            )

        _LOGGER.debug("Sending %d messages to AI provider", len(recent_messages))
        _LOGGER.debug("AI provider: %s", self.config.get("ai_provider", "unknown"))

        while retry_count < self._max_retries:
            try:
                _LOGGER.debug(
                    "Attempt %d/%d: Calling AI client",
                    retry_count + 1,
                    self._max_retries,
                )
                response = await self.ai_client.get_response(recent_messages)
                _LOGGER.debug(
                    "AI client returned response of length: %d", len(response or "")
                )
                _LOGGER.debug("AI response preview: %s", (response or "")[:200])

                # Check for extremely long responses that might indicate model issues
                if response and len(response) > 50000:
                    _LOGGER.warning(
                        "AI returned extremely long response (%d characters), this may indicate a model issue",
                        len(response),
                    )
                    # Check for repetitive patterns that indicate a corrupted response
                    if response.count("for its use in various fields") > 50:
                        _LOGGER.error(
                            "Detected corrupted repetitive response, aborting this iteration"
                        )
                        raise Exception(
                            "AI generated corrupted response with repetitive text. Please try again with a clearer request."
                        )

                # Check if response is empty
                if not response or response.strip() == "":
                    _LOGGER.warning(
                        "AI client returned empty response on attempt %d",
                        retry_count + 1,
                    )
                    if retry_count + 1 >= self._max_retries:
                        raise Exception(
                            "AI provider returned empty response after all retries"
                        )
                    else:
                        retry_count += 1
                        await asyncio.sleep(self._retry_delay * retry_count)
                        continue

                return str(response)
            except Exception as e:
                _LOGGER.error(
                    "AI client error on attempt %d: %s", retry_count + 1, str(e)
                )
                last_error = e
                retry_count += 1
                if retry_count < self._max_retries:
                    await asyncio.sleep(self._retry_delay * retry_count)
                continue
        raise Exception(
            f"Failed after {retry_count} retries. Last error: {str(last_error)}"
        )

    def _build_messages_with_images(
        self,
        user_query: str,
        images: List[ImageAttachment],
        is_current_message: bool = True,
    ) -> List[Dict]:
        """Build messages array with multimodal content for AI models.

        Args:
            user_query: The user's text query
            images: List of ImageAttachment objects
            is_current_message: Whether this is the current user message

        Returns:
            Messages array compatible with OpenAI, Anthropic, etc. APIs
        """
        # Start with system prompt
        messages = []
        if self.system_prompt:
            messages.append({
                "role": "system",
                "content": self.system_prompt.get("content", "") if isinstance(self.system_prompt, dict) else str(self.system_prompt)
            })

        # Add conversation history
        for msg in self.conversation_history:
            if is_current_message and msg == self.conversation_history[-1]:
                # This is the current message with images
                content = MultimediaProcessor.format_multimodal_message(user_query, images)
                messages.append({
                    "role": "user",
                    "content": content
                })
            else:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        return messages

    async def _get_ai_response_with_images(
        self,
        user_query: str,
        images: List[ImageAttachment],
    ) -> str:
        """Get AI response with image attachments for multimodal models.

        Args:
            user_query: The user's text query
            images: List of processed ImageAttachment objects

        Returns:
            The AI's response text
        """
        # Build messages with multimodal content
        messages = self._build_messages_with_images(user_query, images)

        # Check rate limit
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded. Please try again later.")

        retry_count = 0
        last_error = None

        _LOGGER.debug("Sending %d multimodal messages to AI provider", len(messages))

        while retry_count < self._max_retries:
            try:
                _LOGGER.debug(
                    "Attempt %d/%d: Calling AI client for multimodal response",
                    retry_count + 1,
                    self._max_retries,
                )
                response = await self.ai_client.get_response(messages)
                _LOGGER.debug(
                    "AI client returned multimodal response of length: %d", len(response or "")
                )

                # Check for empty response
                if not response or response.strip() == "":
                    _LOGGER.warning(
                        "AI client returned empty multimodal response on attempt %d",
                        retry_count + 1,
                    )
                    if retry_count + 1 >= self._max_retries:
                        raise Exception(
                            "AI provider returned empty response after all retries"
                        )
                    retry_count += 1
                    await asyncio.sleep(self._retry_delay * retry_count)
                    continue

                return str(response)
            except Exception as e:
                _LOGGER.error(
                    "AI client error on multimodal attempt %d: %s", retry_count + 1, str(e)
                )
                last_error = e
                retry_count += 1
                if retry_count < self._max_retries:
                    await asyncio.sleep(self._retry_delay * retry_count)
                continue

        raise Exception(
            f"Failed after {retry_count} retries. Last error: {str(last_error)}"
        )

    def clear_conversation_history(self) -> None:
        """Clear the conversation history and cache."""
        self.conversation_history = []
        self._cache.clear()
        _LOGGER.debug("Conversation history and cache cleared")

    async def set_entity_state(
        self, entity_id: str, state: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Set the state of an entity."""
        try:
            _LOGGER.debug(
                "Setting state for entity %s to %s with attributes: %s",
                entity_id,
                state,
                json.dumps(attributes or {}),
            )

            # Validate entity exists
            if not self.hass.states.get(entity_id):
                return {"error": f"Entity {entity_id} not found"}

            # Call the appropriate service based on the domain
            domain = entity_id.split(".")[0]

            if domain == "light":
                service = (
                    "turn_on" if state.lower() in ["on", "true", "1"] else "turn_off"
                )
                service_data = {"entity_id": entity_id}
                if attributes and service == "turn_on":
                    service_data.update(attributes)
                await self.hass.services.async_call("light", service, service_data)

            elif domain == "switch":
                service = (
                    "turn_on" if state.lower() in ["on", "true", "1"] else "turn_off"
                )
                await self.hass.services.async_call(
                    "switch", service, {"entity_id": entity_id}
                )

            elif domain == "cover":
                if state.lower() in ["open", "up"]:
                    service = "open_cover"
                elif state.lower() in ["close", "down"]:
                    service = "close_cover"
                elif state.lower() == "stop":
                    service = "stop_cover"
                else:
                    return {"error": f"Invalid state {state} for cover entity"}
                await self.hass.services.async_call(
                    "cover", service, {"entity_id": entity_id}
                )

            elif domain == "climate":
                service_data = {"entity_id": entity_id}
                if state.lower() in ["on", "true", "1"]:
                    service = "turn_on"
                elif state.lower() in ["off", "false", "0"]:
                    service = "turn_off"
                elif state.lower() in ["heat", "cool", "dry", "fan_only", "auto"]:
                    service = "set_hvac_mode"
                    service_data["hvac_mode"] = state.lower()
                else:
                    return {"error": f"Invalid state {state} for climate entity"}
                await self.hass.services.async_call("climate", service, service_data)

            elif domain == "fan":
                service = (
                    "turn_on" if state.lower() in ["on", "true", "1"] else "turn_off"
                )
                service_data = {"entity_id": entity_id}
                if attributes and service == "turn_on":
                    service_data.update(attributes)
                await self.hass.services.async_call("fan", service, service_data)

            else:
                # For other domains, try to set the state directly
                self.hass.states.async_set(entity_id, state, attributes or {})

            # Get the new state to confirm the change
            new_state = self.hass.states.get(entity_id)
            return {
                "success": True,
                "entity_id": entity_id,
                "new_state": new_state.state,
                "new_attributes": new_state.attributes,
            }

        except Exception as e:
            _LOGGER.exception("Error setting entity state: %s", str(e))
            return {"error": f"Error setting entity state: {str(e)}"}

    async def call_service(
        self,
        domain: str,
        service: str,
        target: Optional[Dict[str, Any]] = None,
        service_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call a Home Assistant service."""
        try:
            _LOGGER.debug(
                "Calling service %s.%s with target: %s and data: %s",
                domain,
                service,
                json.dumps(target or {}),
                json.dumps(service_data or {}),
            )

            # Prepare the service call data
            call_data = {}

            # Add target entities if provided
            if target:
                if "entity_id" in target:
                    entity_ids = target["entity_id"]
                    if isinstance(entity_ids, list):
                        call_data["entity_id"] = entity_ids
                    else:
                        call_data["entity_id"] = [entity_ids]

                # Add other target properties
                for key, value in target.items():
                    if key != "entity_id":
                        call_data[key] = value

            # Add service data if provided
            if service_data:
                call_data.update(service_data)

            _LOGGER.debug("Final service call data: %s", json.dumps(call_data))

            # Call the service
            await self.hass.services.async_call(domain, service, call_data)

            # Get the updated states of affected entities
            result_entities = []
            if "entity_id" in call_data:
                for entity_id in call_data["entity_id"]:
                    state = self.hass.states.get(entity_id)
                    if state:
                        result_entities.append(
                            {
                                "entity_id": entity_id,
                                "state": state.state,
                                "attributes": dict(state.attributes),
                            }
                        )

            return {
                "success": True,
                "service": f"{domain}.{service}",
                "entities_affected": result_entities,
                "message": f"Successfully called {domain}.{service}",
            }

        except Exception as e:
            _LOGGER.exception(
                "Error calling service %s.%s: %s", domain, service, str(e)
            )
            return {"error": f"Error calling service {domain}.{service}: {str(e)}"}

    async def save_user_prompt_history(
        self, user_id: str, history: List[str]
    ) -> Dict[str, Any]:
        """Save user's prompt history to HA storage."""
        try:
            store: Store = Store(self.hass, 1, f"ai_agent_ha_history_{user_id}")
            await store.async_save({"history": history})
            return {"success": True}
        except Exception as e:
            _LOGGER.exception("Error saving prompt history: %s", str(e))
            return {"error": f"Error saving prompt history: {str(e)}"}

    async def load_user_prompt_history(self, user_id: str) -> Dict[str, Any]:
        """Load user's prompt history from HA storage."""
        try:
            store: Store = Store(self.hass, 1, f"ai_agent_ha_history_{user_id}")
            data = await store.async_load()
            history = data.get("history", []) if data else []
            return {"success": True, "history": history}
        except Exception as e:
            _LOGGER.exception("Error loading prompt history: %s", str(e))
            return {"error": f"Error loading prompt history: {str(e)}", "history": []}

    # === YAML Review Methods ===

    async def review_yaml(
        self, yaml_content: str, review_type: str = "automation"
    ) -> Dict[str, Any]:
        """Review YAML configuration using both static analysis and AI.
        
        Args:
            yaml_content: The YAML content to review
            review_type: Type of YAML ("automation", "dashboard", "script", etc.)
            
        Returns:
            Dictionary with review results including issues, warnings, and suggestions
        """
        try:
            _LOGGER.debug("Reviewing %s YAML: %s", review_type, yaml_content[:100])
            
            # Step 1: Static analysis
            reviewer = YAMLReviewer(self.hass)
            
            # First validate syntax
            syntax_result = reviewer.validate_yaml_syntax(yaml_content)
            if not syntax_result.safe:
                return {
                    "safe": False,
                    "approved": False,
                    "review_type": review_type,
                    "issues": syntax_result.issues,
                    "warnings": [],
                    "suggestions": [],
                    "risk_level": "high",
                    "requires_ai_review": False,
                    "message": "YAML syntax errors found",
                }
            
            # Parse the YAML
            parsed = reviewer.parse_yaml_content(yaml_content)
            if parsed is None:
                return {
                    "safe": False,
                    "approved": False,
                    "review_type": review_type,
                    "issues": ["Failed to parse YAML content"],
                    "warnings": [],
                    "suggestions": [],
                    "risk_level": "high",
                    "requires_ai_review": False,
                    "message": "YAML parsing failed",
                }
            
            # Run type-specific validation
            if review_type == "automation":
                static_result = reviewer.validate_automation(parsed)
            elif review_type == "dashboard":
                static_result = reviewer.validate_dashboard(parsed)
            else:
                static_result = syntax_result
            
            # Step 2: AI review (only if static analysis has warnings or suggestions)
            ai_review_needed = bool(static_result.warnings or static_result.suggestions)
            
            ai_feedback = ""
            if ai_review_needed:
                # Build the AI review prompt with embedded documentation
                docs_provider = HADocumentationProvider()
                base_prompt = docs_provider.get_prompt_for_automation_review()
                review_prompt = f"{base_prompt}\n\nPlease review the following {review_type} YAML:\n\n{yaml_content}"
                
                # Send to AI for review
                try:
                    ai_response = await self._get_ai_response_with_custom_prompt(review_prompt)
                    if isinstance(ai_response, str):
                        # Try to parse JSON from AI response
                        import json as json_module
                        
                        # Clean up response
                        response_clean = ai_response.strip()
                        json_start = response_clean.find("{")
                        json_end = response_clean.rfind("}")
                        
                        if json_start != -1 and json_end != -1:
                            json_str = response_clean[json_start:json_end + 1]
                            try:
                                ai_review_data = json_module.loads(json_str)
                                ai_feedback = ai_review_data.get("feedback", "")
                            except json_module.JSONDecodeError:
                                ai_feedback = response_clean[:500]
                except Exception as e:
                    _LOGGER.warning("AI review failed, using static analysis only: %s", e)
            
            # Combine results
            return {
                "safe": static_result.safe,
                "approved": static_result.approved,
                "review_type": review_type,
                "issues": static_result.issues,
                "warnings": static_result.warnings,
                "suggestions": static_result.suggestions,
                "risk_level": static_result.risk_level,
                "requires_ai_review": ai_review_needed,
                "message": "Review complete",
                "ai_feedback": ai_feedback,
            }
                
        except Exception as e:
            _LOGGER.exception("Error reviewing YAML: %s", str(e))
            return {
                "safe": False,
                "approved": False,
                "review_type": review_type,
                "issues": [f"Review error: {str(e)}"],
                "warnings": [],
                "suggestions": [],
                "risk_level": "high",
                "requires_ai_review": False,
                "message": "Review failed",
            }

    async def review_automation(
        self, automation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review an automation configuration.
        
        Args:
            automation_config: The automation configuration dictionary
            
        Returns:
            Dictionary with review results
        """
        try:
            import yaml as yaml_lib
            
            # Convert config to YAML string
            yaml_content = yaml_lib.dump(automation_config, default_flow_style=False)
            
            # Call the general review method
            return await self.review_yaml(yaml_content, review_type="automation")
            
        except Exception as e:
            _LOGGER.exception("Error reviewing automation: %s", str(e))
            return {
                "safe": False,
                "approved": False,
                "review_type": "automation",
                "issues": [f"Review error: {str(e)}"],
                "warnings": [],
                "suggestions": [],
                "risk_level": "high",
                "requires_ai_review": False,
                "message": "Review failed",
            }

    async def review_dashboard(
        self, dashboard_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review a dashboard configuration.
        
        Args:
            dashboard_config: The dashboard configuration dictionary
            
        Returns:
            Dictionary with review results
        """
        try:
            import yaml as yaml_lib
            
            # Convert config to YAML string
            yaml_content = yaml_lib.dump(dashboard_config, default_flow_style=False)
            
            # Call the general review method
            return await self.review_yaml(yaml_content, review_type="dashboard")
            
        except Exception as e:
            _LOGGER.exception("Error reviewing dashboard: %s", str(e))
            return {
                "safe": False,
                "approved": False,
                "review_type": "dashboard",
                "issues": [f"Review error: {str(e)}"],
                "warnings": [],
                "suggestions": [],
                "risk_level": "high",
                "requires_ai_review": False,
                "message": "Review failed",
            }

    # === HA Documentation Methods ===

    def get_ha_documentation(self) -> str:
        """Get the full Home Assistant documentation for AI reference.
        
        Returns:
            String containing the documentation
        """
        try:
            provider = HADocumentationProvider()
            return provider.get_full_documentation()
        except Exception as e:
            _LOGGER.exception("Error getting HA documentation: %s", str(e))
            return "Error loading documentation."

    def get_automation_creation_prompt(self) -> str:
        """Get the prompt for AI to create automations with embedded documentation.
        
        Returns:
            String containing the automation creation prompt with documentation
        """
        try:
            provider = HADocumentationProvider()
            return provider.get_prompt_for_automation_creation()
        except Exception as e:
            _LOGGER.exception("Error getting automation prompt: %s", str(e))
            return "Error loading prompt."

    def get_dashboard_creation_prompt(self) -> str:
        """Get the prompt for AI to create dashboards with embedded documentation.
        
        Returns:
            String containing the dashboard creation prompt with documentation
        """
        try:
            provider = HADocumentationProvider()
            return provider.get_prompt_for_dashboard_creation()
        except Exception as e:
            _LOGGER.exception("Error getting dashboard prompt: %s", str(e))
            return "Error loading prompt."

    async def create_automation_with_review(
        self, automation_config: Dict[str, Any], require_review: bool = True
    ) -> Dict[str, Any]:
        """Create an automation with optional AI review.
        
        Args:
            automation_config: The automation configuration
            require_review: Whether to require AI review before creation
            
        Returns:
            Dictionary with result
        """
        try:
            # First, review the automation
            review_result = await self.review_automation(automation_config)
            
            # Check if review rejected it
            if not review_result.get("approved", True):
                return {
                    "success": False,
                    "review_rejected": True,
                    "review_result": review_result,
                    "message": "Automation rejected by review - fix issues before creating",
                }
            
            # If review had warnings but was approved, include them
            if review_result.get("warnings"):
                _LOGGER.warning(
                    "Automation created with warnings: %s", review_result["warnings"]
                )
            
            # Proceed with original automation creation
            result = await self.create_automation(automation_config)
            
            # Add review info to result
            if isinstance(result, dict):
                result["review_result"] = review_result
                result["was_reviewed"] = True
            
            return result
            
        except Exception as e:
            _LOGGER.exception("Error creating automation with review: %s", str(e))
            return {
                "success": False,
                "error": f"Error creating automation with review: {str(e)}",
            }

    async def _get_ai_response_with_custom_prompt(self, custom_prompt: str) -> str:
        """Get AI response using a custom prompt instead of the default conversation history.
        
        Args:
            custom_prompt: The custom prompt to send to the AI
            
        Returns:
            The AI's response as a string
        """
        try:
            response = await self.ai_client.get_response([
                {"role": "system", "content": custom_prompt},
                {"role": "user", "content": "Please respond."}
            ])
            return response
        except Exception as e:
            _LOGGER.exception("Error getting AI response with custom prompt: %s", str(e))
            raise

    # === Log Analysis Methods ===

    async def analyze_logs(
        self, hours: int = 24, search_terms: Optional[List[str]] = None, generate_ai_summary: bool = True
    ) -> Dict[str, Any]:
        """Analyze Home Assistant logs for errors, warnings, and patterns.
        
        Args:
            hours: Number of hours of logs to analyze (default: 24)
            search_terms: Optional list of terms to search for
            generate_ai_summary: Whether to generate AI summary
            
        Returns:
            Dictionary with analysis results
        """
        try:
            analyzer = LogAnalyzer(self.hass)
            result = analyzer.analyze_logs(
                hours=hours,
                search_terms=search_terms,
                generate_ai_summary=generate_ai_summary
            )
            return result.to_dict()
        except Exception as e:
            _LOGGER.exception("Error analyzing logs: %s", str(e))
            return {
                "success": False,
                "error": f"Error analyzing logs: {str(e)}",
            }

    async def search_logs(
        self, search_term: str, hours: int = 24, levels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Search logs for specific terms.
        
        Args:
            search_term: Term to search for
            hours: Number of hours of logs to search (default: 24)
            levels: Optional list of log levels to include (ERROR, WARNING, etc.)
            
        Returns:
            Dictionary with search results
        """
        try:
            analyzer = LogAnalyzer(self.hass)
            entries = analyzer.search_logs(
                search_term=search_term,
                hours=hours,
                levels=levels
            )
            return {
                "success": True,
                "search_term": search_term,
                "hours": hours,
                "results": [e.to_dict() for e in entries],
                "count": len(entries),
            }
        except Exception as e:
            _LOGGER.exception("Error searching logs: %s", str(e))
            return {
                "success": False,
                "error": f"Error searching logs: {str(e)}",
            }

    async def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get a quick summary of errors from logs.
        
        Args:
            hours: Number of hours of logs to analyze (default: 24)
            
        Returns:
            Dictionary with error summary
        """
        try:
            analyzer = LogAnalyzer(self.hass)
            result = analyzer.get_error_summary(hours=hours)
            result["success"] = True
            return result
        except Exception as e:
            _LOGGER.exception("Error getting error summary: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting error summary: {str(e)}",
            }

    # === Error Diagnosis Methods ===

    async def diagnose_error(
        self, error_message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Diagnose a specific error and provide suggested fixes.
        
        Args:
            error_message: The error message to diagnose
            context: Optional context (e.g., entity_id, domain)
            
        Returns:
            Dictionary with diagnosis results
        """
        try:
            assistant = ErrorDiagnosisAssistant()
            results = assistant.diagnose(error_message=error_message, context=context)
            
            if not results:
                # No pattern match found, generate AI diagnosis prompt
                ai_prompt = assistant.get_ai_enhanced_diagnosis(error_message, [])
                ai_response = await self._get_ai_response_with_custom_prompt(ai_prompt)
                
                return {
                    "success": True,
                    "error_message": error_message,
                    "pattern_match": False,
                    "ai_diagnosis": ai_response,
                }
            
            # Generate AI-enhanced diagnosis if needed
            ai_prompt = assistant.get_ai_enhanced_diagnosis(error_message, results)
            ai_response = await self._get_ai_response_with_custom_prompt(ai_prompt)
            
            return {
                "success": True,
                "error_message": error_message,
                "pattern_match": len(results) > 0,
                "diagnoses": [r.to_dict() for r in results],
                "ai_enhanced_diagnosis": ai_response,
            }
        except Exception as e:
            _LOGGER.exception("Error diagnosing error: %s", str(e))
            return {
                "success": False,
                "error": f"Error diagnosing error: {str(e)}",
            }

    async def diagnose_multiple_errors(
        self, error_messages: List[str]
    ) -> Dict[str, Any]:
        """Diagnose multiple errors.
        
        Args:
            error_messages: List of error messages to diagnose
            
        Returns:
            Dictionary with all diagnosis results
        """
        try:
            assistant = ErrorDiagnosisAssistant()
            
            # Pattern-based diagnosis
            all_results = {}
            for msg in error_messages:
                results = assistant.diagnose(msg)
                all_results[msg] = [r.to_dict() for r in results]
            
            # Generate summary
            all_diagnoses = []
            for results in all_results.values():
                all_diagnoses.extend(results)
            
            summary = assistant.get_diagnosis_summary(
                [type('obj', (object,), {
                    'error_message': k,
                    'error_type': v[0]['error_type'] if v else 'Unknown',
                    'severity': v[0]['severity'] if v else 'unknown',
                    'suggested_fixes': v[0]['suggested_fixes'] if v else []
                })() for k, v in all_results.items() for _ in (v[:1] if v else [])]
            )
            
            # Generate AI-enhanced summary
            ai_prompt = f"""You are a Home Assistant troubleshooting expert. Please provide a comprehensive analysis of these errors:

{chr(10).join(f'- {msg}' for msg in error_messages)}

Known Pattern Matches:
{summary}

Please provide:
1. Overall system health assessment
2. Priority order for fixing errors
3. Any cascading issues (errors causing other errors)
4. Recommended action plan
5. Prevention tips for the future

Respond in a clear, structured format.
"""
            ai_response = await self._get_ai_response_with_custom_prompt(ai_prompt)
            
            return {
                "success": True,
                "error_count": len(error_messages),
                "pattern_matches": sum(1 for v in all_results.values() if v),
                "results": all_results,
                "summary": summary,
                "ai_analysis": ai_response,
            }
        except Exception as e:
            _LOGGER.exception("Error diagnosing multiple errors: %s", str(e))
            return {
                "success": False,
                "error": f"Error diagnosing multiple errors: {str(e)}",
            }

    async def get_troubleshooting_guide(
        self, error_type: str
    ) -> Dict[str, Any]:
        """Get a detailed troubleshooting guide for a specific error type.
        
        Args:
            error_type: The type of error (e.g., "Timeout", "Connection Refused")
            
        Returns:
            Dictionary with troubleshooting guide
        """
        try:
            assistant = ErrorDiagnosisAssistant()
            
            # Find matching pattern
            matching_results = assistant.diagnose(error_type)
            
            if not matching_results:
                # Generate AI troubleshooting guide
                ai_prompt = f"""You are a Home Assistant troubleshooting expert. Please provide a comprehensive troubleshooting guide for the following error type:

{error_type}

Please include:
1. What this error means
2. Common causes (prioritized)
3. Step-by-step troubleshooting procedure
4. How to prevent this error in the future
5. When to seek help from the community
6. Relevant documentation links

Respond in a clear, structured format suitable for both beginners and advanced users.
"""
                ai_response = await self._get_ai_response_with_custom_prompt(ai_prompt)
                
                return {
                    "success": True,
                    "error_type": error_type,
                    "pattern_match": False,
                    "troubleshooting_guide": ai_response,
                }
            
            result = matching_results[0]
            
            # Generate AI-enhanced troubleshooting guide
            ai_prompt = assistant.get_ai_enhanced_diagnosis(
                f"Error type: {error_type}", matching_results
            )
            ai_prompt += "\n\nPlease provide a detailed troubleshooting guide based on this analysis."
            ai_response = await self._get_ai_response_with_custom_prompt(ai_prompt)
            
            return {
                "success": True,
                "error_type": error_type,
                "pattern_match": True,
                "diagnosis": result.to_dict(),
                "troubleshooting_guide": ai_response,
            }
        except Exception as e:
            _LOGGER.exception("Error getting troubleshooting guide: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting troubleshooting guide: {str(e)}",
            }

    # === Automation Troubleshooter Methods ===

    async def troubleshoot_automation(
        self, automation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Troubleshoot an automation and identify issues.
        
        Args:
            automation_config: The automation configuration to troubleshoot
            
        Returns:
            Dictionary with troubleshooting results
        """
        try:
            troubleshooter = AutomationTroubleshooter()
            result = troubleshooter.troubleshoot(automation_config)
            
            # Generate AI-enhanced troubleshooting if there are issues
            ai_enhanced = None
            if result.issues:
                ai_prompt = troubleshooter.get_ai_enhanced_troubleshooting(
                    automation_config, result
                )
                ai_response = await self._get_ai_response_with_custom_prompt(ai_prompt)
                ai_enhanced = ai_response
            
            # Generate fixed version if possible
            fixed_version = troubleshooter.generate_fixed_automation(
                automation_config, result
            )
            
            output = result.to_dict()
            output["ai_enhanced_analysis"] = ai_enhanced
            output["fixed_version"] = fixed_version
            
            return output
        except Exception as e:
            _LOGGER.exception("Error troubleshooting automation: %s", str(e))
            return {
                "success": False,
                "error": f"Error troubleshooting automation: {str(e)}",
            }

    async def troubleshoot_multiple_automations(
        self, automation_configs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Troubleshoot multiple automations.
        
        Args:
            automation_configs: List of automation configurations
            
        Returns:
            Dictionary with all troubleshooting results
        """
        try:
            troubleshooter = AutomationTroubleshooter()
            results = troubleshooter.troubleshoot_multiple(automation_configs)
            
            # Get summary
            total_issues = sum(r.issue_count for r in results)
            critical_count = sum(r.get("critical_issues", 0) for r in [r.to_dict() for r in results])
            
            # Generate AI summary
            summary_text = "\n".join(
                f"- {r.automation_alias or r.automation_id}: Health {r.health_score:.0%}, {r.issue_count} issues"
                for r in results
            )
            
            ai_prompt = f"""You are a Home Assistant automation troubleshooting expert. Please provide a summary analysis of these automations:

{summary_text}

Detailed Results:
{json.dumps([r.to_dict() for r in results], indent=2)}

Please provide:
1. Overall automation health assessment
2. Priority issues that need immediate attention
3. Common patterns across multiple automations
4. Recommended fixes in order of importance
5. Best practices for automation maintenance

Respond in a clear, structured format.
"""
            ai_response = await self._get_ai_response_with_custom_prompt(ai_prompt)
            
            return {
                "success": True,
                "automation_count": len(results),
                "total_issues": total_issues,
                "critical_issues": critical_count,
                "results": [r.to_dict() for r in results],
                "ai_summary": ai_response,
            }
        except Exception as e:
            _LOGGER.exception("Error troubleshooting multiple automations: %s", str(e))
            return {
                "success": False,
                "error": f"Error troubleshooting multiple automations: {str(e)}",
            }

    async def get_automation_fix(
        self, automation_config: Dict[str, Any], issue_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get suggested fixes for automation issues.
        
        Args:
            automation_config: The automation configuration
            issue_type: Optional specific issue type to fix
            
        Returns:
            Dictionary with fix suggestions
        """
        try:
            troubleshooter = AutomationTroubleshooter()
            result = troubleshooter.troubleshoot(automation_config)
            
            # Filter issues if specific type requested
            if issue_type:
                result.issues = [i for i in result.issues if issue_type.lower() in i.issue_type.lower()]
            
            # Generate fixed version
            fixed_version = troubleshooter.generate_fixed_automation(
                automation_config, result
            )
            
            # Generate AI fix suggestions
            if result.issues:
                issues_text = "\n".join(
                    f"- [{i.severity}] {i.issue_type}: {i.message}"
                    for i in result.issues
                )
                
                ai_prompt = f"""You are a Home Assistant automation expert. Please provide specific fixes for these issues:

Automation: {result.automation_alias or 'Unnamed'}
Issues:
{issues_text}

Configuration:
{json.dumps(automation_config, indent=2)}

Please provide:
1. Step-by-step fixes for each issue
2. The corrected YAML for each fix
3. Explanation of why each fix is needed
4. Best practices to prevent similar issues

Respond with actionable fix instructions.
"""
                ai_response = await self._get_ai_response_with_custom_prompt(ai_prompt)
            else:
                ai_response = "No issues found. The automation looks good!"
            
            return {
                "success": True,
                "health_score": result.health_score,
                "issues": [i.to_dict() for i in result.issues],
                "fixed_version": fixed_version,
                "ai_fix_suggestions": ai_response,
            }
        except Exception as e:
            _LOGGER.exception("Error getting automation fix: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting automation fix: {str(e)}",
            }

    # === Entity Discovery Methods ===

    async def discover_entities(
        self,
        area_name: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Discover all available entities and categorize them.
        
        Args:
            area_name: Optional area name to filter by
            domain: Optional domain to filter by (e.g., 'light', 'sensor')
            
        Returns:
            Dictionary with entity discovery results
        """
        try:
            _LOGGER.debug("Discovering entities")
            
            # Get all entities from Home Assistant
            all_entities = self.hass.states.all()
            entities = []
            for entity_state in all_entities:
                entities.append({
                    "entity_id": entity_state.entity_id,
                    "state": entity_state.state,
                    "attributes": entity_state.attributes,
                })
            
            # Try to get areas and devices from Home Assistant
            areas = None
            devices = None
            
            if "areas" in self.hass.data:
                areas = self.hass.data["areas"]
            if "devices" in self.hass.data:
                devices = self.hass.data["devices"]
            
            # Use entity discovery assistant
            discovery = EntityDiscoveryAssistant()
            result = discovery.discover_entities(entities, areas, devices)
            
            # Apply filters if specified
            if area_name:
                if area_name in result.entities_by_area:
                    result.entities_by_area = {area_name: result.entities_by_area[area_name]}
                else:
                    result.entities_by_area = {}
            
            if domain:
                if domain in result.entities_by_domain:
                    result.entities_by_domain = {domain: result.entities_by_domain[domain]}
                else:
                    result.entities_by_domain = {}
            
            return {
                "success": True,
                **result.to_dict(),
            }
            
        except Exception as e:
            _LOGGER.exception("Error discovering entities: %s", str(e))
            return {
                "success": False,
                "error": f"Error discovering entities: {str(e)}",
                "entities_by_area": {},
                "entities_by_domain": {},
                "entities_by_device_class": {},
                "suggestions": [],
                "total_entities": 0,
            }

    async def get_entities_by_room(
        self,
        room_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get entities filtered by room/area.
        
        Args:
            room_name: Optional room name to filter by. If None, returns all entities grouped by room.
            
        Returns:
            Dictionary with room-filtered entities
        """
        try:
            _LOGGER.debug("Getting entities by room: %s", room_name)
            
            # Get all entities from Home Assistant
            all_entities = self.hass.states.all()
            entities = []
            for entity_state in all_entities:
                entities.append({
                    "entity_id": entity_state.entity_id,
                    "state": entity_state.state,
                    "attributes": entity_state.attributes,
                })
            
            # Use entity discovery assistant
            discovery = EntityDiscoveryAssistant()
            result = discovery.discover_entities(entities)
            
            if room_name:
                # Get entities for specific room
                room_entities = result.entities_by_area.get(room_name, [])
                return {
                    "success": True,
                    "room": room_name,
                    "entities": room_entities,
                    "count": len(room_entities),
                }
            else:
                # Return all rooms
                return {
                    "success": True,
                    "rooms": result.entities_by_area,
                    "total_rooms": len(result.entities_by_area),
                    "total_entities": result.total_entities,
                }
            
        except Exception as e:
            _LOGGER.exception("Error getting entities by room: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting entities by room: {str(e)}",
                "entities": [],
                "count": 0,
            }

    async def get_entities_by_function(
        self,
        function: str,
    ) -> Dict[str, Any]:
        """Get entities by function (e.g., 'sensors', 'lights', 'switches').
        
        Args:
            function: The function/category to filter by
            
        Returns:
            Dictionary with function-filtered entities
        """
        try:
            _LOGGER.debug("Getting entities by function: %s", function)
            
            # Get all entities from Home Assistant
            all_entities = self.hass.states.all()
            entities = []
            for entity_state in all_entities:
                entities.append({
                    "entity_id": entity_state.entity_id,
                    "state": entity_state.state,
                    "attributes": entity_state.attributes,
                })
            
            # Use entity discovery assistant
            discovery = EntityDiscoveryAssistant()
            filtered_entities = discovery.get_entities_by_function(entities, function)
            
            return {
                "success": True,
                "function": function,
                "entities": filtered_entities,
                "count": len(filtered_entities),
            }
            
        except Exception as e:
            _LOGGER.exception("Error getting entities by function: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting entities by function: {str(e)}",
                "entities": [],
                "count": 0,
            }

    async def suggest_automations(
        self,
        user_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get automation suggestions based on available devices.
        
        Args:
            user_query: Optional user query for personalized suggestions
            
        Returns:
            Dictionary with automation suggestions
        """
        try:
            _LOGGER.debug("Suggesting automations")
            
            # Get all entities from Home Assistant
            all_entities = self.hass.states.all()
            entities = []
            for entity_state in all_entities:
                entities.append({
                    "entity_id": entity_state.entity_id,
                    "state": entity_state.state,
                    "attributes": entity_state.attributes,
                })
            
            # Use entity discovery assistant
            discovery = EntityDiscoveryAssistant()
            suggestions = discovery.suggest_automations(entities)
            
            # If user query provided, generate personalized suggestions using AI
            ai_suggestions = None
            if user_query:
                prompt = discovery.get_ai_prompt_for_suggestions(entities, user_query)
                ai_response = await self._get_ai_response_with_custom_prompt(prompt)
                ai_suggestions = ai_response
            
            return {
                "success": True,
                "suggestions": [s.to_dict() for s in suggestions],
                "total_suggestions": len(suggestions),
                "ai_suggestions": ai_suggestions,
                "user_query": user_query,
            }
            
        except Exception as e:
            _LOGGER.exception("Error suggesting automations: %s", str(e))
            return {
                "success": False,
                "error": f"Error suggesting automations: {str(e)}",
                "suggestions": [],
                "total_suggestions": 0,
            }

    async def get_personalized_suggestions(
        self,
        user_query: str,
    ) -> Dict[str, Any]:
        """Get personalized automation suggestions based on user query.
        
        Args:
            user_query: User's natural language query about automations
            
        Returns:
            Dictionary with personalized suggestions
        """
        try:
            _LOGGER.debug("Getting personalized suggestions for: %s", user_query)
            
            # Get all entities from Home Assistant
            all_entities = self.hass.states.all()
            entities = []
            for entity_state in all_entities:
                entities.append({
                    "entity_id": entity_state.entity_id,
                    "state": entity_state.state,
                    "attributes": entity_state.attributes,
                })
            
            # Use entity discovery assistant
            discovery = EntityDiscoveryAssistant()
            
            # Generate AI prompt for personalized suggestions
            prompt = discovery.get_ai_prompt_for_suggestions(entities, user_query)
            ai_response = await self._get_ai_response_with_custom_prompt(prompt)
            
            # Also get pattern-based suggestions
            pattern_suggestions = discovery.suggest_automations(entities)
            
            return {
                "success": True,
                "user_query": user_query,
                "ai_suggestions": ai_response,
                "pattern_suggestions": [s.to_dict() for s in pattern_suggestions],
                "total_pattern_suggestions": len(pattern_suggestions),
            }
            
        except Exception as e:
            _LOGGER.exception("Error getting personalized suggestions: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting personalized suggestions: {str(e)}",
                "ai_suggestions": "",
                "pattern_suggestions": [],
                "total_pattern_suggestions": 0,
            }

    async def validate_configuration(self, config_type: str = "all") -> Dict[str, Any]:
        """Validate Home Assistant configuration files.

        Args:
            config_type: Type of configuration to validate ("all", "configuration",
                        "automations", "scripts", "groups")

        Returns:
            Dictionary with validation results
        """
        try:
            _LOGGER.debug("Validating configuration type: %s", config_type)
            
            validator = ConfigurationValidator()
            results = {}
            
            if config_type in ("all", "configuration"):
                # Validate main configuration.yaml
                config_path = self.hass.config.path("configuration.yaml")
                config_result = validator.validate_configuration_yaml(config_path)
                results["configuration"] = config_result.to_dict()
            
            if config_type in ("all", "automations"):
                # Try to load automations.yaml
                automations_path = self.hass.config.path("automations.yaml")
                try:
                    with open(automations_path, "r") as f:
                        automations = yaml.safe_load(f) or []
                    automations_result = validator.validate_automations_yaml(automations)
                    results["automations"] = automations_result.to_dict()
                except FileNotFoundError:
                    results["automations"] = {
                        "config_type": "automations",
                        "valid": True,
                        "issues": [],
                        "summary": {"total_issues": 0, "message": "automations.yaml not found, skipping"},
                        "timestamp": datetime.now().isoformat(),
                    }
                except Exception as e:
                    results["automations"] = {
                        "config_type": "automations",
                        "valid": False,
                        "issues": [{"issue_type": "read_error", "severity": "high", "file": "automations.yaml",
                                   "line": 0, "message": f"Error reading automations.yaml: {str(e)}",
                                   "suggestion": "Check file permissions"}],
                        "summary": {"total_issues": 1},
                        "timestamp": datetime.now().isoformat(),
                    }
            
            if config_type in ("all", "scripts"):
                # Try to load scripts.yaml
                scripts_path = self.hass.config.path("scripts.yaml")
                try:
                    with open(scripts_path, "r") as f:
                        scripts = yaml.safe_load(f) or {}
                    scripts_result = validator.validate_scripts_yaml(scripts)
                    results["scripts"] = scripts_result.to_dict()
                except FileNotFoundError:
                    results["scripts"] = {
                        "config_type": "scripts",
                        "valid": True,
                        "issues": [],
                        "summary": {"total_issues": 0, "message": "scripts.yaml not found, skipping"},
                        "timestamp": datetime.now().isoformat(),
                    }
                except Exception as e:
                    results["scripts"] = {
                        "config_type": "scripts",
                        "valid": False,
                        "issues": [{"issue_type": "read_error", "severity": "high", "file": "scripts.yaml",
                                   "line": 0, "message": f"Error reading scripts.yaml: {str(e)}",
                                   "suggestion": "Check file permissions"}],
                        "summary": {"total_issues": 1},
                        "timestamp": datetime.now().isoformat(),
                    }
            
            if config_type in ("all", "groups"):
                # Try to load groups.yaml
                groups_path = self.hass.config.path("groups.yaml")
                try:
                    with open(groups_path, "r") as f:
                        groups = yaml.safe_load(f) or {}
                    groups_result = validator.validate_groups_yaml(groups)
                    results["groups"] = groups_result.to_dict()
                except FileNotFoundError:
                    results["groups"] = {
                        "config_type": "groups",
                        "valid": True,
                        "issues": [],
                        "summary": {"total_issues": 0, "message": "groups.yaml not found, skipping"},
                        "timestamp": datetime.now().isoformat(),
                    }
                except Exception as e:
                    results["groups"] = {
                        "config_type": "groups",
                        "valid": False,
                        "issues": [{"issue_type": "read_error", "severity": "high", "file": "groups.yaml",
                                   "line": 0, "message": f"Error reading groups.yaml: {str(e)}",
                                   "suggestion": "Check file permissions"}],
                        "summary": {"total_issues": 1},
                        "timestamp": datetime.now().isoformat(),
                    }
            
            # Combine all results
            total_issues = sum(r.get("summary", {}).get("total_issues", 0) for r in results.values())
            has_critical = any(
                i.get("severity") in ("critical", "high")
                for r in results.values()
                for i in r.get("issues", [])
            )
            
            return {
                "success": True,
                "valid": not has_critical and total_issues > 0,
                "config_type": config_type,
                "results": results,
                "summary": {
                    "total_issues": total_issues,
                    "files_checked": list(results.keys()),
                },
                "markdown": self._format_validation_markdown(results),
            }
            
        except Exception as e:
            _LOGGER.exception("Error validating configuration: %s", str(e))
            return {
                "success": False,
                "error": f"Error validating configuration: {str(e)}",
                "config_type": config_type,
            }

    async def validate_automations(self, automations: List[Dict]) -> Dict[str, Any]:
        """Validate automation configurations passed as parameters.

        Args:
            automations: List of automation configurations to validate

        Returns:
            Dictionary with validation results
        """
        try:
            _LOGGER.debug("Validating %d automations", len(automations))
            
            validator = ConfigurationValidator()
            result = validator.validate_automations_yaml(automations)
            
            return {
                "success": True,
                "valid": result.valid,
                "config_type": "automations",
                "result": result.to_dict(),
                "markdown": result.to_markdown(),
            }
            
        except Exception as e:
            _LOGGER.exception("Error validating automations: %s", str(e))
            return {
                "success": False,
                "error": f"Error validating automations: {str(e)}",
                "valid": False,
            }

    async def validate_scripts(self, scripts: Dict) -> Dict[str, Any]:
        """Validate script configurations passed as parameters.

        Args:
            scripts: Dictionary of script configurations to validate

        Returns:
            Dictionary with validation results
        """
        try:
            _LOGGER.debug("Validating %d scripts", len(scripts))
            
            validator = ConfigurationValidator()
            result = validator.validate_scripts_yaml(scripts)
            
            return {
                "success": True,
                "valid": result.valid,
                "config_type": "scripts",
                "result": result.to_dict(),
                "markdown": result.to_markdown(),
            }
            
        except Exception as e:
            _LOGGER.exception("Error validating scripts: %s", str(e))
            return {
                "success": False,
                "error": f"Error validating scripts: {str(e)}",
                "valid": False,
            }

    async def get_improvement_suggestions(self, config_type: str) -> Dict[str, Any]:
        """Get AI-powered improvement suggestions for configuration.

        Args:
            config_type: Type of configuration to get suggestions for

        Returns:
            Dictionary with improvement suggestions
        """
        try:
            _LOGGER.debug("Getting improvement suggestions for: %s", config_type)
            
            # First validate the configuration
            validation_result = await self.validate_configuration(config_type)
            
            if not validation_result.get("success"):
                return validation_result
            
            # Generate AI prompt for improvements based on validation results
            validator = ConfigurationValidator()
            
            # Get the specific result for the config_type
            specific_result_data = validation_result.get("results", {}).get(config_type, {})
            if not specific_result_data:
                # Try to find first available result
                specific_result_data = next(iter(validation_result.get("results", {}).values()), {})
            
            # Create a temporary ConfigValidationResult for prompt generation
            issues_data = specific_result_data.get("issues", [])
            temp_result = ConfigValidationResult(
                config_type=specific_result_data.get("config_type", config_type),
                issues=[
                    ConfigIssue(
                        issue_type=i.get("issue_type", "unknown"),
                        severity=i.get("severity", "medium"),
                        file=i.get("file", ""),
                        line=i.get("line", 0),
                        message=i.get("message", ""),
                        suggestion=i.get("suggestion", ""),
                        deprecated=i.get("deprecated", False),
                    )
                    for i in issues_data
                ],
            )
            
            # Generate AI prompt
            prompt = validator.get_ai_prompt_for_improvements(temp_result)
            
            # Get AI response
            ai_response = await self._get_ai_response_with_custom_prompt(prompt)
            
            return {
                "success": True,
                "config_type": config_type,
                "validation_summary": validation_result.get("summary", {}),
                "ai_suggestions": ai_response,
                "has_issues": len(issues_data) > 0,
                "issue_count": len(issues_data),
            }
            
        except Exception as e:
            _LOGGER.exception("Error getting improvement suggestions: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting improvement suggestions: {str(e)}",
                "config_type": config_type,
            }

    def _format_validation_markdown(self, results: Dict[str, Any]) -> str:
        """Format validation results as markdown.
        
        Args:
            results: Dictionary of validation results
            
        Returns:
            Markdown formatted string
        """
        lines = ["# Home Assistant Configuration Validation Report\n"]
        
        for config_type, result_data in results.items():
            lines.append(f"## {config_type.title()}\n")
            lines.append(f"**Valid:** {'Yes' if result_data.get('valid') else 'No'}\n")
            
            issues = result_data.get("issues", [])
            if issues:
                lines.append("| Severity | Type | Message | Suggestion |")
                lines.append("|----------|------|---------|------------|")
                for issue in issues:
                    lines.append(
                        f"| {issue.get('severity', 'N/A').upper()} "
                        f"| {issue.get('issue_type', 'N/A')} "
                        f"| {issue.get('message', 'N/A')} "
                        f"| {issue.get('suggestion', 'N/A')} |"
                    )
            else:
                lines.append("No issues found! ✅\n")
            
            lines.append("")
        
        return "\n".join(lines)

    # === Backup & Restore Advisor Methods ===
    async def get_backup_recommendation(
        self, changes_description: str, include_database: bool = True
    ) -> Dict[str, Any]:
        """Get backup recommendation before making changes.

        Args:
            changes_description: Description of changes to be made
            include_database: Whether to recommend database backup

        Returns:
            Dictionary with backup recommendation
        """
        try:
            _LOGGER.debug(
                "Getting backup recommendation for: %s", changes_description
            )

            advisor = BackupAdvisor()
            recommendation = advisor.get_backup_recommendation(
                changes_description, include_database
            )

            return {
                "success": True,
                "recommendation": recommendation.to_dict(),
                "markdown": recommendation.to_markdown(),
                "checklist": advisor.get_pre_change_checklist(changes_description),
            }

        except Exception as e:
            _LOGGER.exception(
                "Error getting backup recommendation: %s", str(e)
            )
            return {
                "success": False,
                "error": f"Error getting backup recommendation: {str(e)}",
                "changes_description": changes_description,
            }

    async def verify_after_changes(
        self, changes_made: List[Dict], current_config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Verify system is working correctly after changes.

        Args:
            changes_made: List of changes that were made
            current_config: Current configuration to verify

        Returns:
            Dictionary with verification results
        """
        try:
            _LOGGER.debug(
                "Verifying system after %d changes", len(changes_made)
            )

            advisor = BackupAdvisor()
            verification = advisor.verify_after_changes(
                changes_made, current_config
            )

            return {
                "success": True,
                "verification": verification.to_dict(),
                "markdown": verification.to_markdown(),
                "needs_attention": verification.checks_failed > 0,
            }

        except Exception as e:
            _LOGGER.exception("Error verifying after changes: %s", str(e))
            return {
                "success": False,
                "error": f"Error verifying after changes: {str(e)}",
            }

    async def get_rollback_suggestion(
        self,
        issue: str,
        changes_made: List[Dict],
        backup_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get suggestion for rolling back changes.

        Args:
            issue: Description of the issue detected
            changes_made: List of changes that were made
            backup_path: Path to backup for restoration

        Returns:
            Dictionary with rollback suggestion
        """
        try:
            _LOGGER.debug(
                "Getting rollback suggestion for issue: %s", issue
            )

            advisor = BackupAdvisor()
            rollback_suggestion = advisor.get_rollback_suggestion(
                issue, changes_made, backup_path
            )

            # Generate AI prompt for personalized advice
            ai_prompt = advisor.get_ai_prompt_for_rollback(
                issue, changes_made, backup_path is not None
            )

            return {
                "success": True,
                "rollback_suggestion": rollback_suggestion.to_dict(),
                "markdown": rollback_suggestion.to_markdown(),
                "ai_prompt": ai_prompt,
                "priority": rollback_suggestion.priority,
            }

        except Exception as e:
            _LOGGER.exception("Error getting rollback suggestion: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting rollback suggestion: {str(e)}",
                "issue": issue,
            }

    async def generate_backup_script(
        self, backup_path: str = "/backup"
    ) -> Dict[str, Any]:
        """Generate a backup script for the user.

        Args:
            backup_path: Path to store the backup

        Returns:
            Dictionary with backup script content
        """
        try:
            _LOGGER.debug("Generating backup script for path: %s", backup_path)

            advisor = BackupAdvisor()
            script_content = advisor.generate_backup_script(backup_path)

            return {
                "success": True,
                "script": script_content,
                "backup_path": backup_path,
                "timestamp": datetime.now().isoformat(),
                "instructions": (
                    "1. Save this script to a file (e.g., ha_backup.sh)\n"
                    "2. Make it executable: chmod +x ha_backup.sh\n"
                    "3. Run it: ./ha_backup.sh\n"
                    "4. The compressed backup will be saved in the specified path"
                ),
            }

        except Exception as e:
            _LOGGER.exception("Error generating backup script: %s", str(e))
            return {
                "success": False,
                "error": f"Error generating backup script: {str(e)}",
            }

    # === Energy Optimization Advisor Methods ===
    async def analyze_energy_usage(
        self,
        energy_entities: Optional[List[Dict]] = None,
        device_entities: Optional[List[Dict]] = None,
        time_period: str = "month",
    ) -> Dict[str, Any]:
        """Analyze energy usage patterns.

        Args:
            energy_entities: List of energy meter entities (optional, will use HA state if not provided)
            device_entities: List of device entities (optional, will use HA state if not provided)
            time_period: Time period for analysis (day, week, month)

        Returns:
            Dictionary with energy analysis results
        """
        try:
            _LOGGER.debug("Analyzing energy usage for period: %s", time_period)

            advisor = EnergyAdvisor()

            # Get entities from Home Assistant if not provided
            if energy_entities is None or device_entities is None:
                all_states = hass.states.async_all() if (hass := self._hass) else []
                if energy_entities is None:
                    energy_entities = [
                        {"entity_id": e.entity_id, "state": e.state, "attributes": e.attributes}
                        for e in all_states
                        if e.domain in ("sensor", "meter", "energy")
                        and "energy" in e.entity_id.lower()
                    ]
                if device_entities is None:
                    device_entities = [
                        {"entity_id": e.entity_id, "state": e.state, "attributes": e.attributes, "domain": e.domain}
                        for e in all_states
                        if e.domain in advisor.AUTOMATABLE_DOMAINS
                    ]

            result = advisor.analyze_energy_data(
                energy_entities or [],
                device_entities or [],
                time_period,
            )

            return {
                "success": True,
                "analysis": result.to_dict(),
                "markdown": result.to_markdown(),
                "total_usage": result.energy_summary.total_usage,
                "total_cost": result.energy_summary.total_cost,
                "suggestions_count": len(result.suggestions),
            }

        except Exception as e:
            _LOGGER.exception("Error analyzing energy usage: %s", str(e))
            return {
                "success": False,
                "error": f"Error analyzing energy usage: {str(e)}",
                "time_period": time_period,
            }

    async def get_energy_suggestions(
        self,
        device_entities: Optional[List[Dict]] = None,
        energy_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Get energy optimization suggestions.

        Args:
            device_entities: List of device entities (optional, will use HA state if not provided)
            energy_data: Optional energy usage data

        Returns:
            Dictionary with energy suggestions
        """
        try:
            _LOGGER.debug("Getting energy optimization suggestions")

            advisor = EnergyAdvisor()

            # Get devices from Home Assistant if not provided
            if device_entities is None:
                all_states = self._hass.states.async_all() if hasattr(self, "_hass") else []
                device_entities = [
                    {"entity_id": e.entity_id, "state": e.state, "attributes": e.attributes, "domain": e.domain, "name": e.name or e.entity_id}
                    for e in all_states
                    if e.domain in advisor.AUTOMATABLE_DOMAINS
                ]

            suggestions = advisor.get_optimization_suggestions(
                device_entities or [],
                energy_data,
            )

            # Also get device-specific automation suggestions
            device_automations = []
            for device in device_entities or []:
                automation = advisor.suggest_automation_for_device(device)
                if automation:
                    device_automations.append({
                        "device": device.get("entity_id", ""),
                        "automation": automation,
                    })

            return {
                "success": True,
                "suggestions": [s.to_dict() for s in suggestions],
                "device_automations": device_automations,
                "total_suggestions": len(suggestions),
                "total_device_automations": len(device_automations),
                "markdown": "\n".join(s.to_markdown() for s in suggestions),
            }

        except Exception as e:
            _LOGGER.exception("Error getting energy suggestions: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting energy suggestions: {str(e)}",
            }

    async def get_device_energy_analysis(
        self,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get per-device energy analysis.

        Args:
            domain: Optional domain filter (e.g., 'light', 'switch')

        Returns:
            Dictionary with device energy analysis
        """
        try:
            _LOGGER.debug("Getting device energy analysis, domain filter: %s", domain)

            advisor = EnergyAdvisor()

            # Get devices from Home Assistant
            all_states = self._hass.states.async_all() if hasattr(self, "_hass") else []
            device_entities = [
                {
                    "entity_id": e.entity_id,
                    "state": e.state,
                    "attributes": e.attributes,
                    "domain": e.domain,
                    "name": e.name or e.entity_id,
                }
                for e in all_states
                if e.domain in advisor.AUTOMATABLE_DOMAINS
                and (domain is None or e.domain == domain)
            ]

            # Analyze all devices
            analyses = advisor.analyze_device_energy(device_entities)

            # Filter to only automatable devices with significant usage
            significant_devices = [
                d for d in analyses if d.is_automatable and d.cost_per_period > 0
            ]

            # Calculate total potential savings
            total_monthly_cost = sum(d.cost_per_period for d in significant_devices)
            estimated_savings = total_monthly_cost * 0.2  # Estimate 20% savings potential

            return {
                "success": True,
                "devices": [d.to_dict() for d in analyses],
                "significant_devices": [d.to_dict() for d in significant_devices],
                "total_devices": len(analyses),
                "automatable_devices": sum(1 for d in analyses if d.is_automatable),
                "total_monthly_cost": total_monthly_cost,
                "estimated_savings_potential": estimated_savings,
                "markdown": self._generate_device_analysis_markdown(analyses),
            }

        except Exception as e:
            _LOGGER.exception("Error getting device energy analysis: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting device energy analysis: {str(e)}",
            }

    def _generate_device_analysis_markdown(
        self, analyses: List[Any]
    ) -> str:
        """Generate markdown summary of device analysis.

        Args:
            analyses: List of DeviceEnergyAnalysis objects

        Returns:
            Markdown string
        """
        lines = ["## Device Energy Analysis Summary", ""]
        lines.append("| Device | Domain | Avg Usage (kWh) | Cost/Month | Automatable |")
        lines.append("|--------|--------|-----------------|------------|-------------|")

        for device in analyses:
            auto_str = "Yes" if device.is_automatable else "No"
            lines.append(
                f"| {device.name} | {device.domain} | {device.avg_usage:.2f} | ${device.cost_per_period:.2f} | {auto_str} |"
            )

        lines.append("")
        total_cost = sum(d.cost_per_period for d in analyses)
        lines.append(f"**Total Estimated Monthly Cost: ${total_cost:.2f}**")
        lines.append("")
        lines.append(f"*Analysis includes {len(analyses)} devices*")

        return "\n".join(lines)

    # Security Audit methods
    async def security_audit(self, automations: List[Dict]) -> Dict[str, Any]:
        """Run a comprehensive security audit on automations.

        Args:
            automations: List of automation configurations to audit.

        Returns:
            Dictionary with security audit results.
        """
        try:
            auditor = SecurityAuditor()
            audit_result = auditor.audit_automations(automations)

            return {
                "success": True,
                "score": audit_result.score,
                "summary": audit_result.summary,
                "issues": [issue.to_dict() for issue in audit_result.issues],
                "total_issues": len(audit_result.issues),
                "critical_issues": sum(
                    1 for i in audit_result.issues if i.severity == "critical"
                ),
                "high_issues": sum(
                    1 for i in audit_result.issues if i.severity == "high"
                ),
                "medium_issues": sum(
                    1 for i in audit_result.issues if i.severity == "medium"
                ),
                "low_issues": sum(
                    1 for i in audit_result.issues if i.severity == "low"
                ),
                "info_issues": sum(
                    1 for i in audit_result.issues if i.severity == "info"
                ),
                "markdown": audit_result.to_markdown(),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            _LOGGER.exception("Error running security audit: %s", str(e))
            return {
                "success": False,
                "error": f"Error running security audit: {str(e)}",
            }

    async def check_credentials(self, configurations: List[Dict]) -> Dict[str, Any]:
        """Check for exposed credentials in configurations.

        Args:
            configurations: List of configuration dictionaries to check.

        Returns:
            Dictionary with credential check results.
        """
        try:
            auditor = SecurityAuditor()
            issues = auditor.check_exposed_credentials(configurations)

            return {
                "success": True,
                "credentials_found": len(issues),
                "issues": [issue.to_dict() for issue in issues],
                "risk_level": (
                    "critical"
                    if issues
                    else "none"
                ),
                "recommendation": (
                    "Remove all hardcoded credentials and use Home Assistant secrets or environment variables."
                    if issues
                    else "No exposed credentials detected."
                ),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            _LOGGER.exception("Error checking credentials: %s", str(e))
            return {
                "success": False,
                "error": f"Error checking credentials: {str(e)}",
            }

    async def get_security_score(self) -> Dict[str, Any]:
        """Get overall security score based on all automations.

        Returns:
            Dictionary with security score and summary.
        """
        try:
            # Get all automations from Home Assistant state
            automations = []
            for state in self._hass.states.async_all("automation"):
                automation_config = state.attributes
                automation_config["id"] = state.entity_id
                automations.append(automation_config)

            if not automations:
                return {
                    "success": True,
                    "score": 100.0,
                    "message": "No automations found to audit.",
                    "timestamp": datetime.now().isoformat(),
                }

            auditor = SecurityAuditor()
            audit_result = auditor.audit_automations(automations)

            return {
                "success": True,
                "score": audit_result.score,
                "total_automations_audited": len(automations),
                "total_issues": len(audit_result.issues),
                "critical_issues": sum(
                    1 for i in audit_result.issues if i.severity == "critical"
                ),
                "high_issues": sum(
                    1 for i in audit_result.issues if i.severity == "high"
                ),
                "medium_issues": sum(
                    1 for i in audit_result.issues if i.severity == "medium"
                ),
                "low_issues": sum(
                    1 for i in audit_result.issues if i.severity == "low"
                ),
                "info_issues": sum(
                    1 for i in audit_result.issues if i.severity == "info"
                ),
                "top_issues": [
                    issue.to_dict()
                    for issue in (
                        sorted(
                            audit_result.issues,
                            key=lambda x: {
                                "critical": 0,
                                "high": 1,
                                "medium": 2,
                                "low": 3,
                                "info": 4,
                            }.get(x.severity, 5),
                        )[:5]
                    )
                ],
                "markdown": audit_result.to_markdown(),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            _LOGGER.exception("Error getting security score: %s", str(e))
            return {
                "success": False,
                "error": f"Error getting security score: {str(e)}",
            }

    # === Natural Language to Automation Converter ===
    async def convert_nl_to_automation(self, natural_language: str) -> Dict[str, Any]:
        """Convert natural language to automation configuration.

        Args:
            natural_language: The natural language description

        Returns:
            Dictionary with conversion results
        """
        try:
            if not natural_language or not natural_language.strip():
                return {
                    "success": False,
                    "error": "Empty natural language input",
                    "result": None,
                }

            # Get available entities from Home Assistant
            available_entities = self._get_available_entities()

            # Create converter and convert
            converter = NLToAutomationConverter()
            result = converter.convert(natural_language, available_entities)

            return {
                "success": True,
                "result": result.to_dict(),
                "markdown": result.to_markdown(),
            }
        except Exception as e:
            _LOGGER.exception("Error converting natural language to automation: %s", str(e))
            return {
                "success": False,
                "error": f"Error converting natural language to automation: {str(e)}",
                "result": None,
            }

    async def create_automation_from_nl(self, natural_language: str, require_review: bool = True) -> Dict[str, Any]:
        """Create automation from natural language with optional review step.

        Args:
            natural_language: The natural language description
            require_review: If True, return YAML for review before creating

        Returns:
            Dictionary with automation creation results
        """
        try:
            if not natural_language or not natural_language.strip():
                return {
                    "success": False,
                    "error": "Empty natural language input",
                    "result": None,
                }

            # Get available entities from Home Assistant
            available_entities = self._get_available_entities()

            # Create converter and convert
            converter = NLToAutomationConverter()
            result = converter.convert(natural_language, available_entities)

            if result.needs_clarification:
                return {
                    "success": True,
                    "needs_clarification": True,
                    "clarification_questions": result.clarification_questions,
                    "result": result.to_dict(),
                    "markdown": result.to_markdown(),
                }

            if require_review:
                # Return YAML for review
                return {
                    "success": True,
                    "needs_review": True,
                    "yaml_content": result.yaml_output,
                    "automation_config": result.automation_config,
                    "confidence": result.confidence,
                    "suggestions": result.suggestions,
                    "result": result.to_dict(),
                    "markdown": result.to_markdown(),
                }
            else:
                # Create automation directly
                from homeassistant.components.automation import async_validate_automation_config
                from homeassistant.core import HomeAssistant

                # Validate and create automation
                automation_config = result.automation_config

                # Note: Actual automation creation would require integration with
                # Home Assistant's automation component, which needs proper context
                return {
                    "success": True,
                    "automation_created": True,
                    "automation_config": automation_config,
                    "yaml_content": result.yaml_output,
                    "confidence": result.confidence,
                    "suggestions": result.suggestions,
                    "result": result.to_dict(),
                    "markdown": result.to_markdown(),
                }
        except Exception as e:
            _LOGGER.exception("Error creating automation from natural language: %s", str(e))
            return {
                "success": False,
                "error": f"Error creating automation from natural language: {str(e)}",
                "result": None,
            }

    def _get_available_entities(self) -> List[Dict]:
        """Get list of available entities from Home Assistant.

        Returns:
            List of entity dictionaries
        """
        try:
            entities = self.hass.states.async_all()
            entity_list = []
            for entity in entities:
                entity_list.append({
                    "entity_id": entity.entity_id,
                    "name": entity.name or entity.entity_id,
                    "domain": entity.entity_id.split(".")[0],
                    "state": entity.state,
                    "attributes": entity.attributes,
                })
            return entity_list
        except Exception as e:
            _LOGGER.warning("Error getting available entities: %s", str(e))
            return []

    # === Integration Guide Methods ===
    def _get_integration_guide_provider(self) -> IntegrationGuideProvider:
        """Get or create the integration guide provider.

        Returns:
            IntegrationGuideProvider instance
        """
        if not hasattr(self, "_integration_guide_provider"):
            self._integration_guide_provider = IntegrationGuideProvider()
        return self._integration_guide_provider

    async def get_integration_guide(self, domain: str) -> Dict[str, Any]:
        """Get a setup guide for a Home Assistant integration.

        Args:
            domain: Integration domain (e.g., 'zha', 'mqtt', 'tuya')

        Returns:
            Dictionary with integration guide information
        """
        try:
            provider = self._get_integration_guide_provider()
            guide = provider.get_setup_guide(domain)
            result = guide.to_dict()
            result["markdown"] = guide.to_markdown()
            result["success"] = True
            return result
        except Exception as e:
            _LOGGER.exception("Error getting integration guide for %s: %s", domain, str(e))
            return {
                "success": False,
                "error": f"Error getting integration guide: {str(e)}",
                "domain": domain,
            }

    async def get_config_snippet(self, domain: str) -> Dict[str, Any]:
        """Get a configuration snippet for a Home Assistant integration.

        Args:
            domain: Integration domain

        Returns:
            Dictionary with configuration snippet
        """
        try:
            provider = self._get_integration_guide_provider()
            snippet = provider.get_config_snippet(domain)
            return {
                "success": True,
                "domain": domain,
                "config_snippet": snippet,
            }
        except Exception as e:
            _LOGGER.exception("Error getting config snippet for %s: %s", domain, str(e))
            return {
                "success": False,
                "error": f"Error getting config snippet: {str(e)}",
                "domain": domain,
            }

    async def search_integrations(self, query: str) -> Dict[str, Any]:
        """Search for Home Assistant integrations by keyword.

        Args:
            query: Search query string

        Returns:
            Dictionary with search results
        """
        try:
            provider = self._get_integration_guide_provider()
            integrations = provider.search_integrations(query)
            results = [integration.to_dict() for integration in integrations]
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
            }
        except Exception as e:
            _LOGGER.exception("Error searching integrations for '%s': %s", query, str(e))
            return {
                "success": False,
                "error": f"Error searching integrations: {str(e)}",
                "query": query,
            }
