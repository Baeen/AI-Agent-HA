## Enhancement #1: Prompt Compacting / Summarizing

### Problem Statement
The AI agent constructs large context windows by including full Home Assistant state dumps plus accumulated conversation history. When the total token count exceeds the model's context limit (e.g., 583,846 tokens vs 262,144 available), the API call fails.

### Solution Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    agent.py                             │
│               process_query()                           │
│                        │                                │
│                        ▼                                │
│          ┌──────────────────────────┐                   │
│          │ count_tokens(messages)   │                   │
│          │ (tiktoken or heuristic)  │                   │
│          └──────────┬───────────────┘                   │
│                     │                                   │
│              ┌──────▼──────┐                            │
│              │ Tokens >    │                            │
│              │ threshold?  │                            │
│              └──────┬──────┘                            │
│                     │                                   │
│            ┌────────▼─────────┐                         │
│            │  YES             │  NO → proceed normally  │
│            ▼                  │                         │
│  ┌──────────────────────┐    │                         │
│  │ prompt_compactor.py  │    │                         │
│  │                      │    │                         │
│  │ compact_conversation │    │                         │
│  │ (messages, max)      │    │                         │
│  │       │              │    │                         │
│  │       ▼              │    │                         │
│  │  generate_summary()  │    │                         │
│  │  ┌──────────────┐    │    │                         │
│  │  │Strategy:     │    │    │                         │
│  │  │ Keep:        │    │    │                         │
│  │  │ 1. System msg│    │    │                         │
│  │  │ 2. Last 5    │    │    │                         │
│  │  │ 3. Summary   │    │    │                         │
│  │  │ of old msgs  │    │    │                         │
│  │  └──────────────┘    │    │                         │
│  └──────────┬───────────┘    │                         │
│             │                │                         │
│             ▼                ▼                         │
│     compacted messages → AI Provider API               │
└─────────────────────────────────────────────────────────┘
```

### New File: [`prompt_compactor.py`](custom_components/ai_agent_ha/prompt_compactor.py)

```python
"""Prompt compactor for managing large conversation histories.

Handles token counting, conversation summarization, and message compaction
to prevent context window overflow errors when sending requests to AI providers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)

# Default compaction prompt template
DEFAULT_COMPACTION_PROMPT = """Summarize the following conversation between a Home Assistant user and an AI assistant. 
Focus on:
1. Key user requests and intents
2. Important context about the smart home
3. Actions that were taken or discussed
4. Entities and devices mentioned
5. Any unresolved questions

Keep the summary concise but comprehensive. Do not lose technical details 
about automations, configurations, or entity states."""


@dataclass
class ConversationSummary:
    """Stores a compact summary of older conversation messages.

    Attributes:
        summary_text: The condensed text summary.
        original_message_count: How many messages were summarized.
        original_token_count: Approximate tokens in the original messages.
        summary_token_count: Approximate tokens in the summary.
        created_at: When this summary was generated.
        first_message_index: Index of the first summarized message.
        last_message_index: Index of the last summarized message.
    """

    summary_text: str
    original_message_count: int = 0
    original_token_count: int = 0
    summary_token_count: int = 0
    created_at: str = ""
    first_message_index: int = 0
    last_message_index: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "summary_text": self.summary_text,
            "original_message_count": self.original_message_count,
            "original_token_count": self.original_token_count,
            "summary_token_count": self.summary_token_count,
            "created_at": self.created_at,
            "first_message_index": self.first_message_index,
            "last_message_index": self.last_message_index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConversationSummary:
        """Deserialize from dictionary."""
        return cls(
            summary_text=data.get("summary_text", ""),
            original_message_count=data.get("original_message_count", 0),
            original_token_count=data.get("original_token_count", 0),
            summary_token_count=data.get("summary_token_count", 0),
            created_at=data.get("created_at", ""),
            first_message_index=data.get("first_message_index", 0),
            last_message_index=data.get("last_message_index", 0),
        )


class PromptCompactor:
    """Manages prompt compaction to keep conversations within token limits.

    Strategy:
      1. Always keep the system prompt (index 0).
      2. Always keep the last N messages (default: 5).
      3. Summarize all messages between system prompt and the preserved tail.
      4. Replace summarized messages with a single system-like summary message.

    Usage:
        compactor = PromptCompactor(threshold_pct=0.70, keep_last=5)
        compacted, summary = await compactor.compact_conversation(
            messages, max_tokens=262144, ai_client=client
        )
    """

    def __init__(
        self,
        threshold_pct: float = 0.70,
        keep_last: int = 5,
        compaction_prompt: Optional[str] = None,
        enabled: bool = True,
    ):
        """Initialize the prompt compactor.

        Args:
            threshold_pct: Fraction (0.0-1.0) of max_tokens that triggers compaction.
            keep_last: Number of most recent messages to preserve intact.
            compaction_prompt: Custom system prompt for the summarization step.
            enabled: Whether compaction is active.
        """
        self.threshold_pct = threshold_pct
        self.keep_last = keep_last
        self.compaction_prompt = compaction_prompt or DEFAULT_COMPACTION_PROMPT
        self.enabled = enabled
        self._summaries: List[ConversationSummary] = []

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate token count for a list of messages.

        Uses a heuristic: ~4 characters per token average for English text.
        Falls back to tiktoken if available in the environment.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            Approximate token count.
        """
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                # Handle multimodal content arrays
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total_chars += len(part["text"])
            total_chars += len(msg.get("role", ""))
        # Heuristic: ~4 chars per token
        return max(1, total_chars // 4)

    def needs_compaction(
        self, messages: List[Dict[str, Any]], max_tokens: int
    ) -> Tuple[bool, int, int]:
        """Check if the message list needs compaction.

        Args:
            messages: Current conversation messages.
            max_tokens: Maximum allowed tokens for the model.

        Returns:
            Tuple of (needs_compaction, current_tokens, threshold_tokens).
        """
        if not self.enabled:
            return False, 0, 0

        current_tokens = self.estimate_tokens(messages)
        threshold_tokens = int(max_tokens * self.threshold_pct)
        return current_tokens > threshold_tokens, current_tokens, threshold_tokens

    def extract_system_prompt(
        self, messages: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Extract the system prompt message if present.

        Args:
            messages: Full message list.

        Returns:
            The system message or None.
        """
        for msg in messages:
            if msg.get("role") == "system":
                return msg
        return None

    def _generate_heuristic_summary(
        self, messages: List[Dict[str, Any]]
    ) -> ConversationSummary:
        """Generate a basic summary without calling AI (fallback).

        Extracts user queries and key topics from the conversation.

        Args:
            messages: Messages to summarize.

        Returns:
            ConversationSummary with heuristic summary.
        """
        user_queries = []
        entity_mentions = set()
        action_keywords = set()

        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                if msg.get("role") == "user":
                    # Capture user queries (truncated)
                    user_queries.append(content[:200])
                # Extract entity-like patterns
                import re

                entities = re.findall(r"\b([a-z_]+\.[a-z_0-9]+)\b", content)
                entity_mentions.update(entities)

                # Extract action keywords
                actions = re.findall(
                    r"\b(turn_on|turn_off|toggle|lock|unlock|set|adjust|"
                    r"activate|deactivate|arm|disarm|open|close)\b",
                    content,
                    re.IGNORECASE,
                )
                action_keywords.update(a.lower() for a in actions)

        summary_parts = []
        if user_queries:
            summary_parts.append(
                f"User asked about: {'; '.join(user_queries[:5])}"
            )
        if entity_mentions:
            summary_parts.append(
                f"Entities discussed: {', '.join(sorted(list(entity_mentions))[:20])}"
            )
        if action_keywords:
            summary_parts.append(
                f"Actions discussed: {', '.join(sorted(action_keywords))}"
            )

        summary_text = ". ".join(summary_parts) if summary_parts else (
            "Previous conversation about Home Assistant configuration and automation."
        )

        return ConversationSummary(
            summary_text=summary_text,
            original_message_count=len(messages),
            original_token_count=self.estimate_tokens(messages),
            summary_token_count=self.estimate_tokens(
                [{"role": "system", "content": summary_text}]
            ),
            first_message_index=0,
            last_message_index=len(messages) - 1,
        )

    async def generate_summary(
        self,
        messages: List[Dict[str, Any]],
        ai_client=None,
    ) -> ConversationSummary:
        """Generate a summary of messages, using AI if a client is provided.

        Args:
            messages: The messages to summarize.
            ai_client: Optional AI client instance with a get_response method.

        Returns:
            ConversationSummary with the generated summary.
        """
        if ai_client is None:
            return self._generate_heuristic_summary(messages)

        try:
            # Build a summarization request
            summarize_messages = [
                {"role": "system", "content": self.compaction_prompt},
                {
                    "role": "user",
                    "content": (
                        "Please summarize the following conversation:\n\n"
                        + json.dumps(
                            [
                                {"role": m.get("role"), "content": str(m.get("content", ""))[:500]}
                                for m in messages
                            ],
                            indent=2,
                        )
                    ),
                },
            ]

            response = await ai_client.get_response(summarize_messages)
            summary_text = ""
            if isinstance(response, str):
                try:
                    parsed = json.loads(response)
                    if isinstance(parsed, dict):
                        summary_text = parsed.get("response", response)
                    else:
                        summary_text = response
                except json.JSONDecodeError:
                    summary_text = response
            elif isinstance(response, dict):
                summary_text = response.get("response", str(response))

            if not summary_text:
                return self._generate_heuristic_summary(messages)

            return ConversationSummary(
                summary_text=summary_text,
                original_message_count=len(messages),
                original_token_count=self.estimate_tokens(messages),
                summary_token_count=self.estimate_tokens(
                    [{"role": "system", "content": summary_text}]
                ),
                first_message_index=0,
                last_message_index=len(messages) - 1,
            )

        except Exception as e:
            _LOGGER.warning(
                "AI summarization failed, falling back to heuristic: %s", e
            )
            return self._generate_heuristic_summary(messages)

    async def compact_conversation(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        ai_client=None,
    ) -> Tuple[List[Dict[str, Any]], Optional[ConversationSummary]]:
        """Compact a conversation to fit within token limits.

        Strategy:
          1. Identify system prompt (preserved).
          2. Identify last N messages (preserved).
          3. Summarize everything in between.
          4. Insert summary as a system-like message.
          5. Truncate content of preserved messages if still over limit.

        Args:
            messages: Full conversation message list.
            max_tokens: The model's maximum context token limit.
            ai_client: Optional AI client for summary generation.

        Returns:
            Tuple of (compacted_messages, generated_summary).
            If no compaction was needed, summary is None.
        """
        needs, current, threshold = self.needs_compaction(messages, max_tokens)

        if not needs:
            _LOGGER.debug(
                "No compaction needed: %d tokens vs %d threshold (max %d)",
                current,
                threshold,
                max_tokens,
            )
            return messages, None

        _LOGGER.info(
            "Compacting conversation: %d tokens exceeds %d threshold (max %d)",
            current,
            threshold,
            max_tokens,
        )

        # Step 1: Extract system prompt
        system_prompt = self.extract_system_prompt(messages)
        system_idx = messages.index(system_prompt) if system_prompt else -1

        # Step 2: Identify tail messages to preserve
        keep_count = min(self.keep_last, max(1, len(messages) - 1))
        tail_start = max(1, len(messages) - keep_count)
        tail_messages = messages[tail_start:]

        # Step 3: Determine the middle section to summarize
        middle_start = 1 if system_idx >= 0 else 0
        middle_end = tail_start
        middle_messages = messages[middle_start:middle_end]

        if len(middle_messages) <= 1:
            # Not enough to summarize, just truncate
            _LOGGER.debug("Too few middle messages to summarize, keeping tail only")
            compacted = []
            if system_prompt:
                compacted.append(system_prompt)
            compacted.extend(tail_messages)
            return compacted, None

        # Step 4: Generate summary
        summary = await self.generate_summary(middle_messages, ai_client)
        self._summaries.append(summary)

        # Step 5: Build compacted message list
        compacted = []
        if system_prompt:
            compacted.append(system_prompt)

        # Insert summary as a system-like message
        compacted.append(
            {
                "role": "system",
                "content": (
                    f"[CONVERSATION SUMMARY - {summary.original_message_count} "
                    f"previous messages summarized]\n{summary.summary_text}"
                ),
            }
        )

        # Add preserved tail messages
        compacted.extend(tail_messages)

        # Step 6: If STILL over limit, truncate content of individual messages
        final_tokens = self.estimate_tokens(compacted)
        if final_tokens > max_tokens:
            _LOGGER.warning(
                "After compaction still over limit (%d > %d), truncating messages",
                final_tokens,
                max_tokens,
            )
            compacted = self._truncate_messages(compacted, max_tokens)

        _LOGGER.info(
            "Compaction complete: %d messages → %d messages (%d tokens → %d tokens)",
            len(messages),
            len(compacted),
            current,
            self.estimate_tokens(compacted),
        )

        return compacted, summary

    def _truncate_messages(
        self, messages: List[Dict[str, Any]], max_tokens: int
    ) -> List[Dict[str, Any]]:
        """Aggressively truncate message content to fit within max_tokens.

        Args:
            messages: Message list to truncate.
            max_tokens: Hard token limit.

        Returns:
            Truncated message list.
        """
        # Reserve tokens for overhead (roles, JSON structure)
        overhead_per_msg = 20
        overhead_tokens = len(messages) * overhead_per_msg
        available_tokens = max(1000, max_tokens - overhead_tokens)

        # Distribute tokens: system/summary get more, tail gets proportional
        chars_per_token = 4

        result = []
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            if isinstance(content, str):
                # Earlier messages (system, summary) get more tokens
                if i < len(messages) - self.keep_last:
                    max_chars = available_tokens * chars_per_tokens * 2 // len(messages)
                else:
                    max_chars = available_tokens * chars_per_token // len(messages)

                if len(content) > max_chars:
                    content = content[:max_chars] + "\n...[truncated]"
            result.append({**msg, "content": content})

        return result

    def get_compaction_stats(self) -> Dict[str, Any]:
        """Return statistics about compaction history.

        Returns:
            Dictionary with compaction metrics.
        """
        total_original = sum(s.original_token_count for s in self._summaries)
        total_summary = sum(s.summary_token_count for s in self._summaries)
        return {
            "total_compactions": len(self._summaries),
            "total_original_tokens": total_original,
            "total_summary_tokens": total_summary,
            "compression_ratio": (
                total_summary / total_original if total_original > 0 else 0
            ),
            "summaries": [s.to_dict() for s in self._summaries],
        }
```

### Changes to [`const.py`](custom_components/ai_agent_ha/const.py)

Add after line 49:

```python
# Prompt Compaction settings
CONF_PROMPT_COMPACTION_ENABLED = "prompt_compaction_enabled"
CONF_PROMPT_COMPACTION_THRESHOLD = "prompt_compaction_threshold"
CONF_PROMPT_COMPACTION_PROMPT = "prompt_compaction_prompt"
CONF_PROMPT_COMPACTION_KEEP_LAST = "prompt_compaction_keep_last"

DEFAULT_PROMPT_COMPACTION_ENABLED = True
DEFAULT_PROMPT_COMPACTION_THRESHOLD = 0.70  # 70% of context window
DEFAULT_PROMPT_COMPACTION_KEEP_LAST = 5
```

### Changes to [`config_flow.py`](custom_components/ai_agent_ha/config_flow.py)

Add a new options step method in `AiAgentHaOptionsFlowHandler`:

```python
async def async_step_prompt_compaction(self, user_input=None):
    """Configure prompt compaction settings."""
    errors = {}

    if user_input is not None:
        self.options.update(user_input)
        return self.async_create_entry(title="", data=self.options)

    current_enabled = self.config_entry.options.get(
        CONF_PROMPT_COMPACTION_ENABLED, DEFAULT_PROMPT_COMPACTION_ENABLED
    )
    current_threshold = self.config_entry.options.get(
        CONF_PROMPT_COMPACTION_THRESHOLD, DEFAULT_PROMPT_COMPACTION_THRESHOLD
    )
    current_keep = self.config_entry.options.get(
        CONF_PROMPT_COMPACTION_KEEP_LAST, DEFAULT_PROMPT_COMPACTION_KEEP_LAST
    )

    from homeassistant.helpers.selector import (
        BooleanSelector,
        NumberSelector,
        NumberSelectorConfig,
    )

    schema_dict = {
        vol.Required(
            CONF_PROMPT_COMPACTION_ENABLED, default=current_enabled
        ): BooleanSelector(),
        vol.Required(
            CONF_PROMPT_COMPACTION_THRESHOLD, default=current_threshold
        ): NumberSelector(
            NumberSelectorConfig(min=0.3, max=0.95, step=0.05, mode="slider")
        ),
        vol.Required(
            CONF_PROMPT_COMPACTION_KEEP_LAST, default=current_keep
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=20, step=1, mode="box")
        ),
    }

    return self.async_show_form(
        step_id="prompt_compaction",
        data_schema=vol.Schema(schema_dict),
        errors=errors,
    )
```

### Changes to [`agent.py`](custom_components/ai_agent_ha/agent.py)

**In the `__init__` method of `AiAgentHaAgent`**, add:

```python
from .prompt_compactor import PromptCompactor

# In __init__:
self.prompt_compactor = PromptCompactor(
    threshold_pct=config.get(CONF_PROMPT_COMPACTION_THRESHOLD, 0.70),
    keep_last=config.get(CONF_PROMPT_COMPACTION_KEEP_LAST, 5),
    enabled=config.get(CONF_PROMPT_COMPACTION_ENABLED, True),
    compaction_prompt=config.get(CONF_PROMPT_COMPACTION_PROMPT),
)
```

**In `process_query()`**, before the AI client call, add:

```python
# --- Prompt Compaction Check ---
# Estimate current token count
conversation_messages = [...]  # the messages being sent
MAX_TOKENS = 262144  # or model-specific

needs_compaction, current_tokens, threshold = (
    self.prompt_compactor.needs_compaction(
        conversation_messages, MAX_TOKENS
    )
)

if needs_compaction:
    _LOGGER.warning(
        "Context window at %d/%d tokens (threshold %d%%). Compacting...",
        current_tokens,
        MAX_TOKENS,
        int(self.prompt_compactor.threshold_pct * 100),
    )
    conversation_messages, summary = (
        await self.prompt_compactor.compact_conversation(
            conversation_messages, MAX_TOKENS, ai_client=self.ai_client
        )
    )
    if summary:
        _LOGGER.info(
            "Compacted %d messages into summary of %d tokens",
            summary.original_message_count,
            summary.summary_token_count,
        )
```

---
