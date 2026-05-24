"""Voice Handler Module for AI Agent HA integration.

This module provides voice input/output capabilities allowing users to interact
with the AI agent using voice commands and receive spoken responses. It integrates
with Home Assistant's existing `conversation` and `tts` components.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant

from .agent import AiAgentHaAgent

_LOGGER = logging.getLogger(__name__)


@dataclass
class VoiceQueryResult:
    """Result structure for voice queries.

    Attributes:
        text_input: Original voice text that was processed
        ai_response: AI's text response
        tts_audio_url: URL to TTS audio file (if generated)
        success: Boolean indicating if the query was successful
        error: Error message if the query failed
        metadata: Additional metadata about the query (e.g., TTS engine used)
    """

    text_input: str
    ai_response: str = ""
    tts_audio_url: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation.

        Returns:
            Dictionary representation of the result
        """
        return {
            "text_input": self.text_input,
            "ai_response": self.ai_response,
            "tts_audio_url": self.tts_audio_url,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


class VoiceHandler:
    """Main handler for voice interactions with the AI agent.

    This class processes voice commands by:
    1. Sending the text to the AI agent via process_query() or _get_ai_response()
    2. Optionally converting the response to speech via TTS
    3. Returning a result with audio URL if TTS is enabled

    Attributes:
        hass: HomeAssistant instance
        agent: AiAgentHaAgent instance for processing queries
    """

    def __init__(self, hass: HomeAssistant, agent: AiAgentHaAgent):
        """Initialize the voice handler.

        Args:
            hass: HomeAssistant instance
            agent: AiAgentHaAgent instance for processing queries
        """
        self.hass = hass
        self.agent = agent
        self._tts_engines_cache: Optional[List[str]] = None
        self._tts_voices_cache: Dict[str, List[str]] = {}

    async def process_voice_command(
        self,
        text: str,
        response_tts: bool = True,
        tts_engine: str = "",
        tts_voice: str = "",
    ) -> VoiceQueryResult:
        """Process a voice command.

        Sends the text to the AI agent and optionally converts the response
        to speech using Home Assistant's TTS component.

        Args:
            text: The voice command text to process
            response_tts: Whether to convert the AI response to speech (default: True)
            tts_engine: Optional TTS engine to use (empty = default engine)
            tts_voice: Optional voice to use for TTS (empty = default voice)

        Returns:
            VoiceQueryResult containing the AI response and optionally audio URL

        Example:
            >>> result = await handler.process_voice_command(
            ...     "Turn on the living room light",
            ...     response_tts=True,
            ...     tts_engine="google_translate",
            ...     tts_voice="en-US-Standard-C"
            ... )
            >>> if result.success:
            ...     print(f"Response: {result.ai_response}")
            ...     if result.tts_audio_url:
            ...         # Play audio from result.tts_audio_url
            ...         pass
        """
        # Validate input
        if not text or not text.strip():
            _LOGGER.warning("Empty voice command received")
            return VoiceQueryResult(
                text_input=text or "",
                success=False,
                error="Empty voice command",
            )

        text = text.strip()
        _LOGGER.info("Processing voice command: %s", text)

        # Step 1: Send text to AI agent via process_query()
        try:
            query_result = await self.agent.process_query(text)

            if not query_result.get("success", False):
                error_msg = query_result.get("error", "Unknown AI agent error")
                _LOGGER.error("AI agent processing failed: %s", error_msg)
                return VoiceQueryResult(
                    text_input=text,
                    success=False,
                    error=f"AI agent error: {error_msg}",
                    metadata={"query_result": query_result},
                )

            ai_response = query_result.get("response", "")
            if not ai_response:
                _LOGGER.warning("AI agent returned empty response")
                return VoiceQueryResult(
                    text_input=text,
                    ai_response="",
                    success=True,
                    error=None,
                    metadata={"query_result": query_result},
                )

            _LOGGER.info("AI agent response: %s", ai_response[:200] + "..." if len(ai_response) > 200 else ai_response)

        except Exception as e:
            _LOGGER.exception("Error processing voice command through AI agent: %s", str(e))
            return VoiceQueryResult(
                text_input=text,
                success=False,
                error=f"Error processing command: {str(e)}",
            )

        # Step 2: Optionally convert response to speech via TTS
        tts_audio_url = None
        tts_metadata = {}

        if response_tts:
            tts_result = await self._speak_response(ai_response, tts_engine, tts_voice)
            tts_audio_url = tts_result.get("audio_url")
            tts_metadata = {
                "tts_engine_used": tts_result.get("engine", ""),
                "tts_success": tts_result.get("success", False),
            }

            if not tts_result.get("success", False):
                _LOGGER.warning("TTS generation failed, but voice command succeeded: %s", tts_result.get("error", "Unknown error"))
                # Voice command still succeeds even if TTS fails

        # Step 3: Return result
        result = VoiceQueryResult(
            text_input=text,
            ai_response=ai_response,
            tts_audio_url=tts_audio_url,
            success=True,
            metadata={**tts_metadata, "query_result": query_result},
        )

        _LOGGER.info("Voice command processed successfully: %s", text[:50])
        return result

    async def _speak_response(
        self,
        response_text: str,
        tts_engine: str = "",
        tts_voice: str = "",
    ) -> Dict[str, Any]:
        """Convert the AI response to speech using Home Assistant's TTS component.

        Args:
            response_text: The text to convert to speech
            tts_engine: Optional TTS engine to use (empty = default)
            tts_voice: Optional voice to use (empty = default)

        Returns:
            Dictionary with keys:
                - success (bool): Whether TTS was successful
                - audio_url (str): URL to the generated audio file
                - engine (str): TTS engine used
                - error (str): Error message if failed
        """
        if not response_text:
            return {
                "success": False,
                "audio_url": None,
                "engine": "",
                "error": "Empty text for TTS",
            }

        # Determine TTS engine
        engine_service_domain = "tts"
        if tts_engine:
            # TTS engine name format is typically "engine_name" or "platform.engine_name"
            if "." in tts_engine:
                engine_service_domain = tts_engine.split(".")[0]
            else:
                # Try to find the domain for this engine
                engine_service_domain = await self._find_tts_domain(tts_engine)
        else:
            # Use default TTS engine
            engine_service_domain = await self._get_default_tts_domain()

        if not engine_service_domain:
            _LOGGER.warning("No TTS engine available")
            return {
                "success": False,
                "audio_url": None,
                "engine": "",
                "error": "No TTS engine available",
            }

        # Build the service call data
        service_data: Dict[str, Any] = {
            "message": response_text,
        }

        if tts_voice:
            service_data["voice"] = tts_voice

        # Add engine if not using default
        if tts_engine:
            service_data["entity_id"] = f"tts.{tts_engine}" if "." not in tts_engine else f"tts.{tts_engine}"

        # Call the TTS service
        try:
            await self.hass.services.async_call(
                engine_service_domain,
                "say",
                service_data,
                blocking=True,
            )

            # Get the audio URL from the response
            # Home Assistant TTS services typically return the URL in the response
            # We'll store the expected URL pattern for later retrieval
            audio_url = f"/api/tts_proxy/{self._generate_tts_filename(response_text, tts_engine, tts_voice)}"

            _LOGGER.debug("TTS generated successfully using engine: %s", engine_service_domain)
            return {
                "success": True,
                "audio_url": audio_url,
                "engine": tts_engine or engine_service_domain,
            }

        except Exception as e:
            _LOGGER.exception("Error calling TTS service: %s", str(e))
            return {
                "success": False,
                "audio_url": None,
                "engine": engine_service_domain,
                "error": f"TTS error: {str(e)}",
            }

    def _generate_tts_filename(self, text: str, engine: str, voice: str) -> str:
        """Generate a filename for the TTS audio file.

        Args:
            text: The text that was converted to speech
            engine: The TTS engine used
            voice: The voice used

        Returns:
            Generated filename
        """
        import hashlib

        # Create a hash of the text+engine+voice for unique filename
        hash_input = f"{text}_{engine}_{voice}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]

        return f"ai_agent_ha_{hash_value}.mp3"

    async def _find_tts_domain(self, engine_name: str) -> Optional[str]:
        """Find the domain for a TTS engine name.

        Args:
            engine_name: Name of the TTS engine (e.g., "google_translate", "cloud")

        Returns:
            Domain for the TTS service or None if not found
        """
        # Check registered services
        services = self.hass.services.async_services()
        tts_services = services.get("tts", {})

        # Look for matching engine
        for entity_id in tts_services:
            if engine_name.lower() in entity_id.lower():
                return entity_id.split(".")[0]

        return "tts"

    async def _get_default_tts_domain(self) -> Optional[str]:
        """Get the default TTS domain.

        Returns:
            Default TTS domain or None if not available
        """
        services = self.hass.services.async_services()
        tts_services = services.get("tts", {})

        if tts_services:
            # Return the first available TTS entity's domain
            first_entity = next(iter(tts_services.keys()))
            return first_entity.split(".")[0]

        return None

    async def get_available_tts_engines(self) -> List[str]:
        """Get a list of available TTS engines.

        Queries Home Assistant for all registered TTS engines.

        Returns:
            List of TTS engine names (e.g., ["google_translate", "cloud", "piper"])

        Example:
            >>> engines = await handler.get_available_tts_engines()
            >>> print(f"Available engines: {engines}")
        """
        # Return cached result if available
        if self._tts_engines_cache is not None:
            return self._tts_engines_cache

        try:
            services = self.hass.services.async_services()
            tts_services = services.get("tts", {})

            if not tts_services:
                _LOGGER.debug("No TTS engines found")
                self._tts_engines_cache = []
                return []

            # Extract unique engine names from entity IDs
            engines = set()
            for entity_id in tts_services.keys():
                # Entity ID format is typically "tts.engine_name"
                parts = entity_id.split(".")
                if len(parts) >= 2:
                    engine_name = parts[1]
                    engines.add(engine_name)

            self._tts_engines_cache = sorted(list(engines))
            _LOGGER.debug("Found TTS engines: %s", self._tts_engines_cache)
            return self._tts_engines_cache

        except Exception as e:
            _LOGGER.exception("Error getting TTS engines: %s", str(e))
            self._tts_engines_cache = []
            return []

    async def get_available_tts_voices(self, engine: str) -> List[str]:
        """Get available voices for a specific TTS engine.

        Args:
            engine: The TTS engine name (e.g., "google_translate")

        Returns:
            List of available voice names for the engine

        Example:
            >>> voices = await handler.get_available_tts_voices("google_translate")
            >>> print(f"Available voices: {voices}")
        """
        # Return cached result if available
        if engine in self._tts_voices_cache:
            return self._tts_voices_cache[engine]

        try:
            # Call the TTS engine's get_voices service
            service_data = {}

            # Try to get voices via the TTS service
            response = await self.hass.services.async_call(
                "tts",
                "get_voices",
                {
                    "entity_id": f"tts.{engine}" if "." not in engine else f"tts.{engine}",
                },
                blocking=True,
                return_response=True,
            )

            # Extract voices from response
            voices = []
            if isinstance(response, dict):
                voices = response.get("voices", [])
                if not voices:
                    # Try alternative response format
                    voices = response.get("available_voices", [])

            self._tts_voices_cache[engine] = voices if voices else []
            _LOGGER.debug("Found %d voices for engine %s", len(voices), engine)
            return self._tts_voices_cache[engine]

        except Exception as e:
            _LOGGER.warning("Error getting voices for engine %s: %s", engine, str(e))
            self._tts_voices_cache[engine] = []
            return []


def get_voice_handler(
    hass: HomeAssistant,
    agent: AiAgentHaAgent,
) -> VoiceHandler:
    """Convenience function to get or create a VoiceHandler instance.

    This function provides a simple way to create a VoiceHandler instance
    from the HomeAssistant and AiAgentHaAgent objects.

    Args:
        hass: HomeAssistant instance
        agent: AiAgentHaAgent instance

    Returns:
        VoiceHandler instance

    Example:
        >>> from .voice_handler import get_voice_handler
        >>> handler = get_voice_handler(hass, agent)
        >>> result = await handler.process_voice_command("What time is it?")
    """
    return VoiceHandler(hass, agent)
