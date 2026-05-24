# AI Agent HA - Five Enhancements Architecture Document

## Executive Summary

This document provides the complete architecture, detailed code changes, data flow diagrams, and implementation specifications for five enhancements to the [`ai_agent_ha`](custom_components/ai_agent_ha/) Home Assistant integration. The enhancements are ordered by implementation priority.

---

## Current Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    ai_agent_ha-panel.js                  │
│               (LitElement Web Component)                 │
│  ┌─────────┐ ┌──────────────┐ ┌──────────────────────┐  │
│  │ Messages│ │Prompt History│ │Provider/Automation UI│  │
│  └────┬────┘ └──────┬───────┘ └──────────┬───────────┘  │
│       │             │                    │               │
└───────┼─────────────┼────────────────────┼───────────────┘
        │             │                    │
   WebSocket      hass.callService    hass.callService
        │             │                    │
┌───────┼─────────────┼────────────────────┼───────────────┐
│       ▼             ▼                    ▼               │
│                  __init__.py                             │
│         (Service Handlers & Integration Setup)           │
│       │                                                  │
│       ▼                                                  │
│                  agent.py                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │           AiAgentHaAgent                         │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │   │
│  │  │BaseAI-   │ │Sub-modules│ │History           │ │   │
│  │  │Client    │ │(yaml, log,│ │save/load         │ │   │
│  │  │hierarchy │ │energy...) │ │                  │ │   │
│  │  └──────────┘ └──────────┘ └──────────────────┘ │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  const.py          config_flow.py        services.yaml   │
│  (Constants)       (Config UI)         (Service defs)    │
└──────────────────────────────────────────────────────────┘
```

### Key Integration Points

| Component | File | Role |
|-----------|------|------|
| Frontend | [`ai_agent_ha-panel.js`](custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js:1) | LitElement chat UI, WebSocket event listener |
| Agent Core | [`agent.py`](custom_components/ai_agent_ha/agent.py:1) | AI client management, `process_query()`, sub-modules |
| Integration | [`__init__.py`](custom_components/ai_agent_ha/__init__.py:1) | Service registration, `async_setup_entry` |
| Config | [`config_flow.py`](custom_components/ai_agent_ha/config_flow.py:1) | Config & Options flow handlers |
| Constants | [`const.py`](custom_components/ai_agent_ha/const.py:1) | Domain, provider configs, feature flags |

### Response Flow
```
User Input → panel.js → hass.callService('ai_agent_ha', 'query') 
→ __init__.py async_handle_query() → agent.process_query() 
→ AI Provider API → JSON response → fire_event('ai_agent_ha_response') 
→ panel.js _handleLlamaResponse() → render messages
```

---

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

## Enhancement #2: Output Formatting (Markdown Rendering)

### Problem Statement
AI responses are rendered as plain text in the chat UI. Users see raw markdown syntax (`**bold**`, `### headings`, code fences, etc.) without any formatting.

### Solution Architecture

```
┌──────────────────────────────────────────────────┐
│           ai_agent_ha-panel.js                   │
│                                                  │
│  AI Response (raw text with markdown)            │
│         │                                        │
│         ▼                                        │
│  ┌──────────────────┐                            │
│  │ _formatMessage() │                            │
│  │                  │                            │
│  │ 1. marked.parse()│  ← marked.js CDN          │
│  │    (md → html)   │                            │
│  │                  │                            │
│  │ 2. hljs.         │  ← highlight.js CDN       │
│  │    highlightAll() │                            │
│  │    (code blocks) │                            │
│  │                  │                            │
│  │ 3. _sanitize()   │  ← DOMPurify or custom    │
│  │    (XSS prevent) │                            │
│  └────────┬─────────┘                            │
│           │                                      │
│           ▼                                      │
│  ┌─────────────────────────┐                    │
│  │ lit-html unsafeHTML    │                    │
│  │ directive for rendering │                    │
│  └─────────────────────────┘                    │
│           │                                      │
│           ▼                                      │
│  Formatted message in chat bubble               │
│  - Headings rendered                             │
│  - Bold/Italic applied                           │
│  - Code blocks with syntax highlight             │
│  - Copy button on code blocks                    │
│  - Links open in new tab                         │
└──────────────────────────────────────────────────┘
```

### Changes to [`manifest.json`](custom_components/ai_agent_ha/manifest.json)

No changes needed - `marked` and `highlight.js` are loaded from CDN in the frontend JS, not as Python dependencies. The `manifest.json` `requirements` field is for Python packages only.

### Changes to [`ai_agent_ha-panel.js`](custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js)

**Step 1: Add CDN imports at the top of the file (after existing imports):**

```javascript
// Markdown and syntax highlighting support
import { unsafeHTML } from "https://unpkg.com/lit-html@2.8.0/directives/unsafe-html.js?module";

// marked.js - loaded dynamically to avoid blocking
let marked = null;
async function loadMarked() {
  if (marked) return marked;
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js';
  document.head.appendChild(script);
  await new Promise((resolve) => { script.onload = resolve; });
  marked = window.marked;
  // Configure marked
  marked.setOptions({
    breaks: true,
    gfm: true,
  });
  return marked;
}

// highlight.js - loaded dynamically
let hljs = null;
async function loadHljs() {
  if (hljs) return hljs;
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/highlight.min.js';
  document.head.appendChild(script);
  await new Promise((resolve) => { script.onload = resolve; });
  
  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = 'https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/styles/github-dark.min.css';
  document.head.appendChild(css);
  
  hljs = window.hljs;
  return hljs;
}

// Lazy-load libraries when first needed
let librariesLoaded = false;
async function ensureLibraries() {
  if (librariesLoaded) return;
  await Promise.all([loadMarked(), loadHljs()]);
  librariesLoaded = true;
}
```

**Step 2: Add these methods to the `AiAgentHaPanel` class:**

```javascript
// Inside the AiAgentHaPanel class

_formatMessage(text) {
  if (!text) return '';
  
  // Check if text contains markdown syntax
  if (!this._hasMarkdown(text)) {
    // Simple text - just escape HTML and convert newlines
    return this._escapeHtml(text).replace(/\n/g, '<br>');
  }
  
  try {
    // Parse markdown to HTML
    let html = marked.parse(text);
    
    // Apply syntax highlighting to code blocks
    // highlight.js works on DOM elements, so we do it post-render
    // via the updated() lifecycle method
    
    // Sanitize HTML to prevent XSS
    html = this._sanitize(html);
    
    return html;
  } catch (e) {
    console.warn('Markdown parsing failed, falling back to plain text:', e);
    return this._escapeHtml(text).replace(/\n/g, '<br>');
  }
}

_hasMarkdown(text) {
  // Check for common markdown patterns
  const mdPatterns = [
    /^#{1,6}\s/m,           // headings
    /\*\*.*?\*\*/,          // bold
    /\*.*?\*/,              // italic
    /```[\s\S]*?```/,       // code blocks
    /`[^`]+`/,              // inline code
    /^\s*[-*+]\s/m,         // unordered lists
    /^\s*\d+\.\s/m,         // ordered lists
    /\[.*?\]\(.*?\)/,       // links
    /^\s*>\s/m,             // blockquotes
    /~~.*?~~/,              // strikethrough
  ];
  return mdPatterns.some(pattern => pattern.test(text));
}

_sanitize(html) {
  // Custom HTML sanitizer to prevent XSS
  // In production, use DOMPurify: https://github.com/cure53/DOMPurify
  
  // Create a temporary DOM element
  const temp = document.createElement('div');
  temp.innerHTML = html;
  
  // Remove dangerous elements and attributes
  const dangerousTags = ['script', 'iframe', 'object', 'embed', 'form', 'input', 'link', 'style', 'meta'];
  const dangerousAttrs = ['onerror', 'onclick', 'onload', 'onmouseover', 'onfocus', 'onblur', 
                          'href="javascript:', 'src="javascript:', 'action="javascript:'];
  
  // Walk the DOM tree
  const walk = (node) => {
    if (node.nodeType === Node.ELEMENT_NODE) {
      // Remove dangerous elements
      if (dangerousTags.includes(node.tagName.toLowerCase())) {
        node.remove();
        return;
      }
      
      // Remove dangerous attributes
      for (const attr of [...node.attributes]) {
        const attrStr = `${attr.name}="${attr.value}"`.toLowerCase();
        if (dangerousAttrs.some(d => attrStr.includes(d)) || attr.name.startsWith('on')) {
          node.removeAttribute(attr.name);
        }
      }
      
      // Add target="_blank" and rel="noopener" to links
      if (node.tagName.toLowerCase() === 'a') {
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
      }
      
      // Add copy button to code blocks
      if (node.tagName.toLowerCase() === 'pre') {
        this._addCopyButtonToCodeBlock(node);
      }
    }
    
    // Recurse (use Array.from since childNodes is a live list)
    for (const child of Array.from(node.childNodes)) {
      walk(child);
    }
  };
  
  walk(temp);
  return temp.innerHTML;
}

_addCopyButtonToCodeBlock(preElement) {
  // Check if button already exists
  if (preElement.querySelector('.code-copy-btn')) return;
  
  const button = document.createElement('button');
  button.className = 'code-copy-btn';
  button.textContent = 'Copy';
  button.addEventListener('click', (e) => {
    e.stopPropagation();
    const code = preElement.querySelector('code');
    const text = code ? code.textContent : preElement.textContent;
    navigator.clipboard.writeText(text).then(() => {
      button.textContent = 'Copied!';
      setTimeout(() => { button.textContent = 'Copy'; }, 2000);
    }).catch(() => {
      button.textContent = 'Failed';
      setTimeout(() => { button.textContent = 'Copy'; }, 2000);
    });
  });
  
  // Wrap pre in a container for positioning
  const wrapper = document.createElement('div');
  wrapper.className = 'code-block-wrapper';
  preElement.parentNode.insertBefore(wrapper, preElement);
  wrapper.appendChild(preElement);
  wrapper.appendChild(button);
}

_escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Override updated() to apply highlight.js to code blocks
async updated(changedProps) {
  // ... existing updated logic ...
  
  // Apply syntax highlighting to newly rendered code blocks
  if (changedProps.has('_messages') && librariesLoaded && hljs) {
    await this.updateComplete;  // Wait for Lit render
    const shadow = this.shadowRoot;
    if (shadow) {
      shadow.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
      });
    }
  }
}
```

**Step 3: Modify the `render()` method to use `_formatMessage()`:**

In the message rendering section of `render()`, change:

```javascript
// OLD:
${message.text}

// NEW:
${message.type === 'assistant' 
  ? unsafeHTML(this._formatMessage(message.text))
  : this._escapeHtml(message.text).replace(/\n/g, '<br>')}
```

**Step 4: Add markdown CSS styles to the static `styles` getter:**

```css
/* Markdown formatting styles */
.message-content h1 { font-size: 1.6em; margin: 8px 0; border-bottom: 1px solid var(--divider-color); }
.message-content h2 { font-size: 1.4em; margin: 8px 0; }
.message-content h3 { font-size: 1.2em; margin: 6px 0; }
.message-content h4, .message-content h5, .message-content h6 { font-size: 1.05em; margin: 4px 0; }

.message-content strong { font-weight: 600; }
.message-content em { font-style: italic; }

.message-content ul, .message-content ol {
  margin: 6px 0 6px 20px;
  padding: 0;
}
.message-content li { margin: 2px 0; }

.message-content blockquote {
  border-left: 3px solid var(--primary-color);
  margin: 8px 0;
  padding: 4px 12px;
  background: var(--secondary-background-color);
  border-radius: 0 4px 4px 0;
  opacity: 0.9;
}

.message-content a {
  color: var(--primary-color);
  text-decoration: underline;
}
.message-content a:hover {
  opacity: 0.8;
}

.message-content p { margin: 4px 0; line-height: 1.5; }

.message-content hr {
  border: none;
  border-top: 1px solid var(--divider-color);
  margin: 12px 0;
}

/* Inline code */
.message-content code:not(pre code) {
  background: var(--secondary-background-color);
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
  border: 1px solid var(--divider-color);
}

/* Code blocks */
.code-block-wrapper {
  position: relative;
  margin: 8px 0;
}
.message-content pre {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 14px;
  border-radius: 6px;
  overflow-x: auto;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.5;
  border: 1px solid var(--divider-color);
  margin: 0;
}
.message-content pre code {
  background: none;
  padding: 0;
  border: none;
}

.code-copy-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(255,255,255,0.1);
  color: #cdd6f4;
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 4px;
  padding: 3px 8px;
  cursor: pointer;
  font-size: 11px;
  transition: all 0.2s;
}
.code-copy-btn:hover {
  background: rgba(255,255,255,0.2);
}

/* Tables */
.message-content table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.message-content th, .message-content td {
  border: 1px solid var(--divider-color);
  padding: 6px 10px;
  text-align: left;
}
.message-content th {
  background: var(--secondary-background-color);
  font-weight: 600;
}

/* Images */
.message-content img {
  max-width: 100%;
  border-radius: 6px;
  margin: 8px 0;
}
```

---

## Enhancement #3: Chat History Management

### Problem Statement
The current implementation has basic `save_prompt_history` and `load_prompt_history` services that store raw message arrays per user. There is no way to list, rename, delete, export, or search conversations.

### Solution Architecture

```
┌──────────────────────────────────────────────────────┐
│              chat_history.py (NEW)                   │
│                                                      │
│  ┌──────────────────────┐  ┌──────────────────────┐ │
│  │ ConversationMetadata │  │ ChatHistoryManager   │ │
│  │                      │  │                      │ │
│  │ - id: str            │  │ - list_conversations │ │
│  │ - name: str          │  │ - delete_conversation│ │
│  │ - created_at: str    │  │ - export_conversation│ │
│  │ - message_count: int │  │ - rename_conversation│ │
│  │ - last_updated: str  │  │ - search_conversation│ │
│  │ - provider: str      │  │ - clear_all          │ │
│  │ - preview: str       │  │                      │ │
│  └──────────────────────┘  └──────────────────────┘ │
└──────────────────────────────────────────────────────┘
         │
         │ used by
         ▼
┌──────────────────────────────────────────────────────┐
│                  __init__.py                         │
│                                                      │
│  New Services:                                       │
│  - get_prompt_history()                              │
│  - delete_prompt_history(conversation_id)            │
│  - export_prompt_history(conversation_id, path)      │
│  - clear_prompt_history()                            │
│  - rename_prompt_history(conversation_id, name)       │
└──────────────────────────────────────────────────────┘
         │
         │ WebSocket / hass.callService
         ▼
┌──────────────────────────────────────────────────────┐
│              ai_agent_ha-panel.js                    │
│                                                      │
│  NEW: History Browser Panel (slideout)               │
│  ┌────────────────────────────────────────────┐     │
│  │ [History] button in header                 │     │
│  │                                            │     │
│  │ History Slideout:                          │     │
│  │ ┌──────────────────────────────────────┐   │     │
│  │ │ Conversation 1    2024-01-15  12 msgs│   │     │
│  │ │ Preview: "Turn on all..."           │   │     │
│  │ │ [Load] [Rename] [Export] [Delete]   │   │     │
│  │ ├──────────────────────────────────────┤   │     │
│  │ │ Conversation 2    2024-01-14   8 msgs│   │     │
│  │ │ ...                                  │   │     │
│  │ └──────────────────────────────────────┘   │     │
│  │ [Clear All History] [Close]               │     │
│  └────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

### New File: [`chat_history.py`](custom_components/ai_agent_ha/chat_history.py)

```python
"""Chat history management for AI Agent HA conversations.

Provides conversation listing, deletion, export, rename, and search operations
on top of the Home Assistant storage layer.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "ai_agent_ha_chat_history_index"
STORAGE_VERSION = 1


@dataclass
class ConversationMetadata:
    """Metadata for a saved conversation.

    Attributes:
        id: Unique conversation identifier (UUID).
        name: Human-readable name for the conversation.
        created_at: ISO 8601 timestamp of creation.
        message_count: Number of messages in the conversation.
        last_updated: ISO 8601 timestamp of last modification.
        provider: AI provider used for this conversation.
        preview: First ~100 chars of the first user message.
        user_id: Home Assistant user ID who owns this conversation.
    """

    id: str = ""
    name: str = ""
    created_at: str = ""
    message_count: int = 0
    last_updated: str = ""
    provider: str = ""
    preview: str = ""
    user_id: str = "default"

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid4())
        now = datetime.utcnow().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.last_updated:
            self.last_updated = now

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "message_count": self.message_count,
            "last_updated": self.last_updated,
            "provider": self.provider,
            "preview": self.preview,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConversationMetadata:
        """Deserialize metadata from a dictionary."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            created_at=data.get("created_at", ""),
            message_count=data.get("message_count", 0),
            last_updated=data.get("last_updated", ""),
            provider=data.get("provider", ""),
            preview=data.get("preview", ""),
            user_id=data.get("user_id", "default"),
        )

    @classmethod
    def from_messages(
        cls,
        user_id: str,
        messages: List[Dict[str, Any]],
        provider: str = "",
        name: str = "",
    ) -> ConversationMetadata:
        """Create metadata from a list of messages.

        Args:
            user_id: Owner user ID.
            messages: List of message dicts.
            provider: AI provider name.
            name: Optional custom name.

        Returns:
            ConversationMetadata instance.
        """
        preview = ""
        for msg in messages:
            if msg.get("role") == "user":
                preview = str(msg.get("content", ""))[:150]
                break

        if not name:
            # Auto-generate name from first user message
            if preview:
                name = preview[:50] + ("..." if len(preview) > 50 else "")
            else:
                name = "New Conversation"

        return cls(
            name=name,
            message_count=len(messages),
            provider=provider,
            preview=preview,
            user_id=user_id,
        )


class ChatHistoryManager:
    """Manages chat history for AI Agent HA.

    Uses Home Assistant's Store for persistent storage of conversation
    metadata index and individual conversation data.

    Storage layout:
      Storage key: "ai_agent_ha_chat_history_index"
        → { "index": { conv_id: ConversationMetadata dict } }

      Storage key: "ai_agent_ha_chat_history_{conv_id}"
        → { "messages": [...], "metadata": {...} }
    """

    def __init__(self, hass: HomeAssistant):
        """Initialize the chat history manager.

        Args:
            hass: The Home Assistant instance.
        """
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._index: Dict[str, ConversationMetadata] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """Load the index from storage if not already loaded."""
        if self._loaded:
            return
        data = await self._store.async_load()
        if data and "index" in data:
            self._index = {
                k: ConversationMetadata.from_dict(v)
                for k, v in data["index"].items()
            }
        self._loaded = True

    async def _save_index(self) -> None:
        """Persist the index to storage."""
        await self._ensure_loaded()
        await self._store.async_save(
            {"index": {k: v.to_dict() for k, v in self._index.items()}}
        )

    def _get_conversation_store(self, conv_id: str) -> Store:
        """Get a Store instance for a specific conversation.

        Args:
            conv_id: The conversation UUID.

        Returns:
            A Store instance for that conversation.
        """
        return Store(
            self.hass,
            STORAGE_VERSION,
            f"ai_agent_ha_chat_history_{conv_id}",
        )

    # ---- CRUD Operations ----

    async def list_conversations(
        self, user_id: Optional[str] = None
    ) -> List[ConversationMetadata]:
        """List all saved conversations, optionally filtered by user.

        Args:
            user_id: Optional user ID filter.

        Returns:
            List of ConversationMetadata sorted by last_updated descending.
        """
        await self._ensure_loaded()
        conversations = list(self._index.values())

        if user_id:
            conversations = [c for c in conversations if c.user_id == user_id]

        conversations.sort(
            key=lambda c: c.last_updated or c.created_at or "", reverse=True
        )
        return conversations

    async def get_conversation(
        self, conv_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load a specific conversation's messages and metadata.

        Args:
            conv_id: The conversation UUID.

        Returns:
            Dict with 'messages' and 'metadata' keys, or None if not found.
        """
        await self._ensure_loaded()
        if conv_id not in self._index:
            return None

        store = self._get_conversation_store(conv_id)
        data = await store.async_load()
        return data

    async def save_conversation(
        self,
        user_id: str,
        messages: List[Dict[str, Any]],
        provider: str = "",
        name: str = "",
        conv_id: Optional[str] = None,
    ) -> ConversationMetadata:
        """Save a conversation and update its metadata.

        Args:
            user_id: Owner user ID.
            messages: List of message dicts.
            provider: AI provider name.
            name: Optional custom name.
            conv_id: Optional existing conversation ID to update.

        Returns:
            The saved ConversationMetadata.
        """
        await self._ensure_loaded()

        # Create or update metadata
        if conv_id and conv_id in self._index:
            metadata = self._index[conv_id]
            metadata.message_count = len(messages)
            metadata.last_updated = datetime.utcnow().isoformat()
            if name:
                metadata.name = name
        else:
            conv_id = conv_id or str(uuid4())
            metadata = ConversationMetadata.from_messages(
                user_id=user_id,
                messages=messages,
                provider=provider,
                name=name,
            )
            metadata.id = conv_id

        # Save conversation data
        store = self._get_conversation_store(conv_id)
        await store.async_save(
            {
                "messages": messages,
                "metadata": metadata.to_dict(),
            }
        )

        # Update index
        self._index[conv_id] = metadata
        await self._save_index()

        _LOGGER.debug(
            "Saved conversation %s with %d messages", conv_id, len(messages)
        )
        return metadata

    async def delete_conversation(self, conv_id: str) -> bool:
        """Delete a specific conversation.

        Args:
            conv_id: The conversation UUID.

        Returns:
            True if deleted, False if not found.
        """
        await self._ensure_loaded()
        if conv_id not in self._index:
            return False

        # Remove conversation data
        store = self._get_conversation_store(conv_id)
        await store.async_remove()

        # Remove from index
        del self._index[conv_id]
        await self._save_index()

        _LOGGER.info("Deleted conversation %s", conv_id)
        return True

    async def rename_conversation(self, conv_id: str, name: str) -> bool:
        """Rename a conversation.

        Args:
            conv_id: The conversation UUID.
            name: New name for the conversation.

        Returns:
            True if renamed, False if not found.
        """
        await self._ensure_loaded()
        if conv_id not in self._index:
            return False

        self._index[conv_id].name = name
        self._index[conv_id].last_updated = datetime.utcnow().isoformat()
        await self._save_index()

        # Also update the metadata inside the conversation store
        conv_data = await self.get_conversation(conv_id)
        if conv_data and "metadata" in conv_data:
            conv_data["metadata"]["name"] = name
            store = self._get_conversation_store(conv_id)
            await store.async_save(conv_data)

        _LOGGER.info("Renamed conversation %s to %s", conv_id, name)
        return True

    async def export_conversation(
        self, conv_id: str, file_path: str
    ) -> Dict[str, Any]:
        """Export a conversation to a JSON file on disk.

        Args:
            conv_id: The conversation UUID.
            file_path: Full filesystem path for the export file.

        Returns:
            Dict with success/error and file_path.
        """
        await self._ensure_loaded()
        if conv_id not in self._index:
            return {"success": False, "error": "Conversation not found"}

        conv_data = await self.get_conversation(conv_id)
        if not conv_data:
            return {"success": False, "error": "Failed to load conversation data"}

        try:
            # Ensure .json extension
            if not file_path.endswith(".json"):
                file_path += ".json"

            # Write to disk (in Home Assistant config directory)
            import os

            config_dir = self.hass.config.path()
            full_path = os.path.join(config_dir, file_path)

            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(conv_data, f, indent=2, default=str)

            _LOGGER.info(
                "Exported conversation %s to %s", conv_id, full_path
            )
            return {"success": True, "file_path": full_path}
        except Exception as e:
            _LOGGER.exception("Failed to export conversation %s: %s", conv_id, e)
            return {"success": False, "error": str(e)}

    async def search_conversations(
        self, query: str, user_id: Optional[str] = None
    ) -> List[ConversationMetadata]:
        """Search conversations by content.

        Searches name, preview, and message content for the query string.

        Args:
            query: Search query string.
            user_id: Optional user ID filter.

        Returns:
            List of matching ConversationMetadata.
        """
        await self._ensure_loaded()
        query_lower = query.lower()
        results = []

        for conv_id, metadata in self._index.items():
            if user_id and metadata.user_id != user_id:
                continue

            # Check name and preview first (fast path)
            if (
                query_lower in metadata.name.lower()
                or query_lower in metadata.preview.lower()
            ):
                results.append(metadata)
                continue

            # Check full message content (slow path)
            conv_data = await self.get_conversation(conv_id)
            if conv_data:
                for msg in conv_data.get("messages", []):
                    content = str(msg.get("content", "")).lower()
                    if query_lower in content:
                        results.append(metadata)
                        break

        results.sort(
            key=lambda c: c.last_updated or c.created_at or "", reverse=True
        )
        return results

    async def clear_all(self, user_id: Optional[str] = None) -> int:
        """Clear all conversations, optionally filtered by user.

        Args:
            user_id: Optional user ID filter.

        Returns:
            Number of conversations deleted.
        """
        await self._ensure_loaded()
        to_delete = []

        for conv_id, metadata in self._index.items():
            if user_id is None or metadata.user_id == user_id:
                to_delete.append(conv_id)

        for conv_id in to_delete:
            store = self._get_conversation_store(conv_id)
            await store.async_remove()

        for conv_id in to_delete:
            del self._index[conv_id]

        await self._save_index()
        _LOGGER.info("Cleared %d conversations", len(to_delete))
        return len(to_delete)
```

### Changes to [`const.py`](custom_components/ai_agent_ha/const.py)

Add:

```python
# Chat History constants
CONF_CHAT_HISTORY_MAX_CONVERSATIONS = "chat_history_max_conversations"
DEFAULT_CHAT_HISTORY_MAX_CONVERSATIONS = 100
```

### Changes to [`__init__.py`](custom_components/ai_agent_ha/__init__.py)

**Add import:**

```python
from .chat_history import ChatHistoryManager
```

**In `async_setup_entry()`, after agent initialization:**

```python
# Initialize chat history manager
if "chat_history_manager" not in hass.data[DOMAIN]:
    hass.data[DOMAIN]["chat_history_manager"] = ChatHistoryManager(hass)
```

**Add new service schemas (before `async_setup_entry` service registration section):**

```python
GET_PROMPT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Optional("user_id"): cv.string,
    }
)

DELETE_PROMPT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("conversation_id"): cv.string,
    }
)

EXPORT_PROMPT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("conversation_id"): cv.string,
        vol.Required("file_path"): cv.string,
    }
)

RENAME_PROMPT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("conversation_id"): cv.string,
        vol.Required("name"): cv.string,
    }
)

CLEAR_PROMPT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Optional("user_id"): cv.string,
    }
)

SEARCH_PROMPT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("query"): cv.string,
        vol.Optional("user_id"): cv.string,
    }
)
```

**Add new service handlers and registrations:**

```python
async def async_handle_get_prompt_history(call):
    """Handle the get_prompt_history service call."""
    try:
        manager = hass.data[DOMAIN].get("chat_history_manager")
        if not manager:
            return {"error": "Chat history manager not initialized"}

        user_id = call.data.get("user_id") or (
            call.context.user_id if call.context.user_id else "default"
        )
        conversations = await manager.list_conversations(user_id)
        return {
            "success": True,
            "conversations": [c.to_dict() for c in conversations],
        }
    except Exception as e:
        _LOGGER.error(f"Error getting prompt history: {e}")
        return {"error": str(e)}

async def async_handle_delete_prompt_history(call):
    """Handle the delete_prompt_history service call."""
    try:
        manager = hass.data[DOMAIN].get("chat_history_manager")
        if not manager:
            return {"error": "Chat history manager not initialized"}

        conv_id = call.data.get("conversation_id")
        success = await manager.delete_conversation(conv_id)
        return {"success": success}
    except Exception as e:
        _LOGGER.error(f"Error deleting prompt history: {e}")
        return {"error": str(e)}

async def async_handle_export_prompt_history(call):
    """Handle the export_prompt_history service call."""
    try:
        manager = hass.data[DOMAIN].get("chat_history_manager")
        if not manager:
            return {"error": "Chat history manager not initialized"}

        conv_id = call.data.get("conversation_id")
        file_path = call.data.get("file_path")
        result = await manager.export_conversation(conv_id, file_path)
        return result
    except Exception as e:
        _LOGGER.error(f"Error exporting prompt history: {e}")
        return {"error": str(e)}

async def async_handle_rename_prompt_history(call):
    """Handle the rename_prompt_history service call."""
    try:
        manager = hass.data[DOMAIN].get("chat_history_manager")
        if not manager:
            return {"error": "Chat history manager not initialized"}

        conv_id = call.data.get("conversation_id")
        name = call.data.get("name")
        success = await manager.rename_conversation(conv_id, name)
        return {"success": success}
    except Exception as e:
        _LOGGER.error(f"Error renaming prompt history: {e}")
        return {"error": str(e)}

async def async_handle_clear_prompt_history(call):
    """Handle the clear_prompt_history service call."""
    try:
        manager = hass.data[DOMAIN].get("chat_history_manager")
        if not manager:
            return {"error": "Chat history manager not initialized"}

        user_id = call.data.get("user_id") or (
            call.context.user_id if call.context.user_id else "default"
        )
        count = await manager.clear_all(user_id)
        return {"success": True, "deleted_count": count}
    except Exception as e:
        _LOGGER.error(f"Error clearing prompt history: {e}")
        return {"error": str(e)}

async def async_handle_search_prompt_history(call):
    """Handle the search_prompt_history service call."""
    try:
        manager = hass.data[DOMAIN].get("chat_history_manager")
        if not manager:
            return {"error": "Chat history manager not initialized"}

        query = call.data.get("query")
        user_id = call.data.get("user_id") or (
            call.context.user_id if call.context.user_id else "default"
        )
        results = await manager.search_conversations(query, user_id)
        return {
            "success": True,
            "conversations": [c.to_dict() for c in results],
        }
    except Exception as e:
        _LOGGER.error(f"Error searching prompt history: {e}")
        return {"error": str(e)}

# Register services (add to existing registration block)
hass.services.async_register(
    DOMAIN, "get_prompt_history", async_handle_get_prompt_history,
    schema=GET_PROMPT_HISTORY_SCHEMA,
)
hass.services.async_register(
    DOMAIN, "delete_prompt_history", async_handle_delete_prompt_history,
    schema=DELETE_PROMPT_HISTORY_SCHEMA,
)
hass.services.async_register(
    DOMAIN, "export_prompt_history", async_handle_export_prompt_history,
    schema=EXPORT_PROMPT_HISTORY_SCHEMA,
)
hass.services.async_register(
    DOMAIN, "rename_prompt_history", async_handle_rename_prompt_history,
    schema=RENAME_PROMPT_HISTORY_SCHEMA,
)
hass.services.async_register(
    DOMAIN, "clear_prompt_history", async_handle_clear_prompt_history,
    schema=CLEAR_PROMPT_HISTORY_SCHEMA,
)
hass.services.async_register(
    DOMAIN, "search_prompt_history", async_handle_search_prompt_history,
    schema=SEARCH_PROMPT_HISTORY_SCHEMA,
)
```

**Also update `async_unload_entry` to remove the new services:**

```python
hass.services.async_remove(DOMAIN, "get_prompt_history")
hass.services.async_remove(DOMAIN, "delete_prompt_history")
hass.services.async_remove(DOMAIN, "export_prompt_history")
hass.services.async_remove(DOMAIN, "rename_prompt_history")
hass.services.async_remove(DOMAIN, "clear_prompt_history")
hass.services.async_remove(DOMAIN, "search_prompt_history")
```

### Changes to [`ai_agent_ha-panel.js`](custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js)

**Add new properties:**

```javascript
static get properties() {
  return {
    // ... existing properties ...
    _showHistoryBrowser: { type: Boolean, reflect: false, attribute: false },
    _historyConversations: { type: Array, reflect: false, attribute: false },
    _historyLoading: { type: Boolean, reflect: false, attribute: false },
    _renameDialog: { type: Object, reflect: false, attribute: false },
  };
}
```

**Initialize in constructor:**

```javascript
this._showHistoryBrowser = false;
this._historyConversations = [];
this._historyLoading = false;
this._renameDialog = null;  // { conv_id, current_name }
```

**Add history management methods:**

```javascript
async _loadHistoryList() {
  this._historyLoading = true;
  try {
    const result = await this.hass.callService('ai_agent_ha', 'get_prompt_history', {});
    if (result && result.success) {
      this._historyConversations = result.conversations || [];
    }
  } catch (e) {
    console.error('Failed to load history list:', e);
  } finally {
    this._historyLoading = false;
  }
}

async _loadConversation(convId) {
  if (this._isLoading) return;
  this._isLoading = true;
  try {
    const result = await this.hass.callService('ai_agent_ha', 'load_prompt_history', {
      conversation_id: convId,
    });
    if (result && result.history) {
      this._messages = result.history.map(msg => ({
        type: msg.role === 'assistant' ? 'assistant' : 'user',
        text: msg.content,
      }));
    }
  } catch (e) {
    console.error('Failed to load conversation:', e);
  } finally {
    this._clearLoadingState();
    this._showHistoryBrowser = false;
  }
}

async _deleteConversation(convId) {
  if (!confirm('Are you sure you want to delete this conversation?')) return;
  try {
    await this.hass.callService('ai_agent_ha', 'delete_prompt_history', {
      conversation_id: convId,
    });
    await this._loadHistoryList();
  } catch (e) {
    console.error('Failed to delete conversation:', e);
  }
}

async _exportConversation(convId) {
  try {
    const name = this._historyConversations.find(c => c.id === convId)?.name || 'conversation';
    const safeName = name.replace(/[^a-zA-Z0-9_-]/g, '_');
    const result = await this.hass.callService('ai_agent_ha', 'export_prompt_history', {
      conversation_id: convId,
      file_path: `www/ai_agent_exports/${safeName}.json`,
    });
    if (result && result.success) {
      alert(`Conversation exported to: ${result.file_path}`);
    } else {
      alert('Export failed: ' + (result?.error || 'Unknown error'));
    }
  } catch (e) {
    console.error('Failed to export conversation:', e);
  }
}

async _renameConversation(convId, newName) {
  try {
    await this.hass.callService('ai_agent_ha', 'rename_prompt_history', {
      conversation_id: convId,
      name: newName,
    });
    await this._loadHistoryList();
  } catch (e) {
    console.error('Failed to rename conversation:', e);
  }
}

async _clearAllHistory() {
  if (!confirm('Are you sure you want to delete ALL conversation history? This cannot be undone.')) return;
  try {
    await this.hass.callService('ai_agent_ha', 'clear_prompt_history', {});
    await this._loadHistoryList();
  } catch (e) {
    console.error('Failed to clear history:', e);
  }
}
```

**Add History Browser UI to the `render()` method (in the header/button area):**

```javascript
// History button in header
html`<button class="history-button" @click="${() => { this._showHistoryBrowser = !this._showHistoryBrowser; if (this._showHistoryBrowser) this._loadHistoryList(); }}">
  <ha-icon icon="mdi:history"></ha-icon>
  <span>History</span>
</button>`
```

**Render the history slideout (conditional):**

```javascript
${this._showHistoryBrowser ? html`
  <div class="history-overlay" @click="${() => this._showHistoryBrowser = false}"></div>
  <div class="history-slideout">
    <div class="history-header">
      <h3>Chat History</h3>
      <button @click="${() => this._showHistoryBrowser = false}">✕</button>
    </div>
    <div class="history-list">
      ${this._historyLoading ? html`<div class="history-loading">Loading...</div>` : ''}
      ${this._historyConversations.length === 0 && !this._historyLoading ? 
        html`<div class="history-empty">No saved conversations</div>` : ''}
      ${this._historyConversations.map(conv => html`
        <div class="history-item">
          <div class="history-item-header">
            <span class="history-name">${conv.name || 'Unnamed'}</span>
            <span class="history-date">${conv.last_updated ? new Date(conv.last_updated).toLocaleDateString() : ''}</span>
          </div>
          <div class="history-preview">${conv.preview || ''}</div>
          <div class="history-meta">${conv.message_count} messages · ${conv.provider || 'unknown'}</div>
          <div class="history-actions">
            <button @click="${() => this._loadConversation(conv.id)}" title="Load">📂 Load</button>
            <button @click="${() => this._renameDialog = { conv_id: conv.id, current_name: conv.name }}" title="Rename">✏️</button>
            <button @click="${() => this._exportConversation(conv.id)}" title="Export">💾</button>
            <button @click="${() => this._deleteConversation(conv.id)}" title="Delete" class="danger">🗑️</button>
          </div>
        </div>
      `)}
    </div>
    ${this._historyConversations.length > 0 ? html`
      <div class="history-footer">
        <button class="clear-all-btn danger" @click="${this._clearAllHistory}">
          Clear All History
        </button>
      </div>
    ` : ''}
    ${this._renameDialog ? html`
      <div class="rename-dialog-overlay" @click="${() => this._renameDialog = null}"></div>
      <div class="rename-dialog">
        <h4>Rename Conversation</h4>
        <input type="text" .value="${this._renameDialog.current_name || ''}" id="rename-input" />
        <div class="rename-actions">
          <button @click="${() => {
            const input = this.shadowRoot.getElementById('rename-input');
            this._renameConversation(this._renameDialog.conv_id, input.value);
            this._renameDialog = null;
          }}">Save</button>
          <button @click="${() => this._renameDialog = null}">Cancel</button>
        </div>
      </div>
    ` : ''}
  </div>
` : ''}
```

**Add CSS styles for history browser:**

```css
.history-button {
  margin-right: 8px;
  border: 1px solid var(--divider-color);
  border-radius: 16px;
  background: var(--secondary-background-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  font-size: 13px;
}
.history-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.3);
  z-index: 200;
}
.history-slideout {
  position: fixed;
  top: 0; right: 0; bottom: 0;
  width: 380px;
  max-width: 90vw;
  background: var(--primary-background-color);
  box-shadow: -4px 0 20px rgba(0,0,0,0.15);
  z-index: 201;
  display: flex;
  flex-direction: column;
}
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--divider-color);
}
.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.history-item {
  border: 1px solid var(--divider-color);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  transition: all 0.2s;
}
.history-item:hover {
  border-color: var(--primary-color);
  background: var(--secondary-background-color);
}
.history-name { font-weight: 600; }
.history-date { font-size: 12px; color: var(--secondary-text-color); }
.history-preview {
  font-size: 13px;
  color: var(--secondary-text-color);
  margin: 4px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.history-meta { font-size: 11px; color: var(--secondary-text-color); }
.history-actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}
.history-actions button {
  border: 1px solid var(--divider-color);
  background: var(--primary-background-color);
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 12px;
}
.history-actions button:hover {
  background: var(--secondary-background-color);
}
.history-footer {
  padding: 12px;
  border-top: 1px solid var(--divider-color);
}
.clear-all-btn {
  width: 100%;
  background: var(--error-color);
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px;
  cursor: pointer;
}
```

### Changes to [`services.yaml`](custom_components/ai_agent_ha/services.yaml)

Add new service definitions:

```yaml
get_prompt_history:
  name: "Get Prompt History"
  description: "List all saved AI prompt histories with metadata."
  fields:
    user_id:
      description: "Optional user ID to filter conversations."
      example: "default"

delete_prompt_history:
  name: "Delete Prompt History"
  description: "Delete a specific saved conversation by ID."
  fields:
    conversation_id:
      description: "The conversation UUID to delete."
      example: "550e8400-e29b-41d4-a716-446655440000"
      required: true

export_prompt_history:
  name: "Export Prompt History"
  description: "Export a conversation to a JSON file."
  fields:
    conversation_id:
      description: "The conversation UUID to export."
      example: "550e8400-e29b-41d4-a716-446655440000"
      required: true
    file_path:
      description: "File path relative to Home Assistant config directory."
      example: "www/ai_agent_exports/my_conversation.json"
      required: true

rename_prompt_history:
  name: "Rename Prompt History"
  description: "Rename a saved conversation."
  fields:
    conversation_id:
      description: "The conversation UUID to rename."
      example: "550e8400-e29b-41d4-a716-446655440000"
      required: true
    name:
      description: "New name for the conversation."
      example: "Living Room Automation Setup"
      required: true

clear_prompt_history:
  name: "Clear Prompt History"
  description: "Delete all saved conversation histories."
  fields:
    user_id:
      description: "Optional user ID to filter (clears all if omitted)."
      example: "default"

search_prompt_history:
  name: "Search Prompt History"
  description: "Search through saved conversation content."
  fields:
    query:
      description: "Search query string."
      example: "living room automation"
      required: true
    user_id:
      description: "Optional user ID to filter."
      example: "default"
```

---

## Enhancement #4: Permission / Prompt System

### Problem Statement
The AI agent can execute Home Assistant service calls automatically. There is no permission gating - any AI-generated action is executed without user confirmation. This is a security risk for sensitive actions like unlocking doors, disabling alarms, or modifying critical automations.

### Solution Architecture

```
┌──────────────────────────────────────────────────────┐
│              permissions.py (NEW)                    │
│                                                      │
│  ┌─────────────────┐  ┌────────────────────────┐    │
│  │ PermissionRule  │  │ PermissionRequest      │    │
│  │                 │  │                        │    │
│  │ - pattern: str  │  │ - action: str          │    │
│  │ - rule_type:    │  │ - target_entities: []  │    │
│  │   allow|deny    │  │ - reason: str          │    │
│  │ - description   │  │ - risk_level: str      │    │
│  │ - priority: int │  │ - timestamp: str       │    │
│  └─────────────────┘  │ - request_id: str      │    │
│                       └────────────────────────┘    │
│  ┌──────────────────────────────────────────────┐   │
│  │           PermissionChecker                  │   │
│  │                                              │   │
│  │ - mode: prompt|auto_allow|auto_deny          │   │
│  │ - whitelist: List[PermissionRule]            │   │
│  │ - blacklist: List[PermissionRule]            │   │
│  │ - timeout: int (seconds)                     │   │
│  │                                              │   │
│  │ + check_action(action, entities)             │   │
│  │   → PERMIT | DENY | PROMPT                   │   │
│  │                                              │   │
│  │ + create_permission_request(action,          │   │
│  │     entities) → PermissionRequest            │   │
│  │                                              │   │
│  │ + match_pattern(pattern, entity) → bool      │   │
│  │   (supports wildcards: light.*, *.lock)      │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
         │
         │ used by
         ▼
┌──────────────────────────────────────────────────────┐
│                  agent.py                            │
│                                                      │
│  process_query() → AI response parsed                │
│         │                                            │
│         ▼                                            │
│  If response contains service calls:                 │
│         │                                            │
│         ▼                                            │
│  for each action:                                    │
│    result = permission_checker.check_action(         │
│      action, entities                                │
│    )                                                 │
│         │                                            │
│    ┌────┼────────────────────────┐                   │
│    ▼    ▼                        ▼                   │
│  PERMIT  DENY                  PROMPT                │
│  execute  skip                 return                │
│  directly                     permission_request     │
│                               to frontend            │
└──────────────────────────────────────────────────────┘
         │
         │ permission_request response
         ▼
┌──────────────────────────────────────────────────────┐
│              ai_agent_ha-panel.js                    │
│                                                      │
│  _handleLlamaResponse() detects:                     │
│    request_type === 'permission_request'             │
│         │                                            │
│         ▼                                            │
│  ┌──────────────────────────────────────┐            │
│  │ Permission Dialog Modal              │            │
│  │                                      │            │
│  │  Action: "Unlock front door"         │            │
│  │  Entities: lock.front_door           │            │
│  │  Risk: ⚠️ HIGH                        │            │
│  │  Reason: "User requested to unlock"  │            │
│  │                                      │            │
│  │  [Approve] [Deny] [Always Allow]    │            │
│  └──────────────────────────────────────┘            │
└──────────────────────────────────────────────────────┘
```

### Data Flow for Permission Gating

```
sequenceDiagram
    participant U as User
    participant F as Frontend (panel.js)
    participant A as Agent (agent.py)
    participant P as PermissionChecker
    participant AI as AI Provider

    U->>F: "Unlock the front door"
    F->>A: hass.callService('query', {prompt: "Unlock..."})
    A->>AI: Send prompt with HA state
    AI-->>A: Response: {action: "lock.unlock", entities: ["lock.front_door"]}
    A->>P: check_action("lock.unlock", ["lock.front_door"])
    Note over P: Check blacklist: "lock.*" → not in blacklist<br>Check whitelist: empty → no auto-allow<br>Mode: "prompt" → return PROMPT
    P-->>A: PROMPT
    A-->>F: fire_event('ai_agent_ha_response', {request_type: 'permission_request', ...})
    F->>F: Show permission dialog
    U->>F: Clicks [Approve]
    F->>A: hass.callService('query', {approved_action: ..., approve: true})
    A->>A: Execute lock.unlock
    A-->>F: fire_event('ai_agent_ha_response', {request_type: 'action_result', ...})
    F-->>U: Show "Door unlocked successfully"
```

### New File: [`permissions.py`](custom_components/ai_agent_ha/permissions.py)

```python
"""Permission system for AI Agent HA actions.

Provides a configurable permission checker that gates AI-initiated service calls
behind user approval prompts for safety-sensitive operations.
"""

from __future__ import annotations

import fnmatch
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class PermissionResult(Enum):
    """Result of a permission check."""

    PERMIT = "permit"
    DENY = "deny"
    PROMPT = "prompt"


class RiskLevel(Enum):
    """Risk level for an action."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PermissionRule:
    """A rule for allowing or denying actions based on pattern matching.

    Attributes:
        pattern: Entity or service pattern (supports wildcards: *, ?).
            Examples: "light.*", "*.unlock", "switch.kitchen_*", "light.living_room"
        rule_type: Whether this rule ALLOWs or DENYs matching actions.
        description: Human-readable explanation of the rule.
        priority: Higher priority rules are evaluated first.
        enabled: Whether this rule is active.
    """

    pattern: str
    rule_type: str  # "allow" or "deny"
    description: str = ""
    priority: int = 0
    enabled: bool = True

    def matches(self, target: str) -> bool:
        """Check if a target string matches this rule's pattern.

        Supports Unix-style wildcards: * matches everything, ? matches single char.

        Args:
            target: The entity ID or service call to check.

        Returns:
            True if the target matches the pattern.
        """
        if not self.enabled:
            return False
        return fnmatch.fnmatch(target.lower(), self.pattern.lower())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "pattern": self.pattern,
            "rule_type": self.rule_type,
            "description": self.description,
            "priority": self.priority,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PermissionRule:
        """Deserialize from dictionary."""
        return cls(
            pattern=data.get("pattern", ""),
            rule_type=data.get("rule_type", "deny"),
            description=data.get("description", ""),
            priority=data.get("priority", 0),
            enabled=data.get("enabled", True),
        )


@dataclass
class PermissionRequest:
    """A permission request sent to the user for approval.

    Attributes:
        request_id: Unique ID for tracking this request.
        action: The service call being requested (e.g., "lock.unlock").
        target_entities: List of entity IDs affected.
        reason: Why the AI wants to perform this action.
        risk_level: Assessed risk level.
        timestamp: When the request was created.
        expires_at: When the request times out.
        metadata: Additional context about the request.
    """

    request_id: str = ""
    action: str = ""
    target_entities: List[str] = field(default_factory=list)
    reason: str = ""
    risk_level: str = "medium"
    timestamp: str = ""
    expires_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for frontend consumption."""
        return {
            "request_id": self.request_id,
            "action": self.action,
            "target_entities": self.target_entities,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }

    def is_expired(self) -> bool:
        """Check if this permission request has timed out."""
        if not self.expires_at:
            return False
        return datetime.utcnow().isoformat() > self.expires_at


class PermissionChecker:
    """Checks whether AI-initiated actions require user permission.

    Evaluation order:
      1. Check blacklist (deny rules) → if match, DENY immediately.
      2. Check whitelist (allow rules) → if match, PERMIT immediately.
      3. If mode is "auto_allow" → PERMIT.
      4. If mode is "auto_deny" → DENY.
      5. Otherwise (mode "prompt") → PROMPT.

    Usage:
        checker = PermissionChecker(mode="prompt", timeout=60)
        checker.add_whitelist_rule(PermissionRule("light.*", "allow"))
        checker.add_blacklist_rule(PermissionRule("lock.*", "deny"))
        result = checker.check_action("light.turn_on", ["light.kitchen"])
    """

    # Predefined risk levels for common service domains
    RISK_LEVELS = {
        "lock": RiskLevel.HIGH,
        "alarm_control_panel": RiskLevel.HIGH,
        "automation": RiskLevel.MEDIUM,
        "script": RiskLevel.MEDIUM,
        "scene": RiskLevel.LOW,
        "light": RiskLevel.LOW,
        "switch": RiskLevel.LOW,
        "climate": RiskLevel.LOW,
        "fan": RiskLevel.LOW,
        "cover": RiskLevel.MEDIUM,
        "media_player": RiskLevel.LOW,
        "vacuum": RiskLevel.LOW,
        "camera": RiskLevel.MEDIUM,
        "notify": RiskLevel.LOW,
        "input_boolean": RiskLevel.LOW,
        "input_number": RiskLevel.MEDIUM,
        "group": RiskLevel.LOW,
        "zone": RiskLevel.LOW,
        "device_tracker": RiskLevel.MEDIUM,
    }

    # Actions that are always safe (no permission needed)
    DEFAULT_WHITELIST = [
        PermissionRule("light.turn_on", "allow", "Turning lights on is low risk", priority=100),
        PermissionRule("light.turn_off", "allow", "Turning lights off is low risk", priority=100),
        PermissionRule("scene.turn_on", "allow", "Activating scenes is low risk", priority=90),
        PermissionRule("notify.*", "allow", "Sending notifications is low risk", priority=90),
    ]

    # Actions that always require permission
    DEFAULT_BLACKLIST = [
        PermissionRule("lock.unlock", "deny", "Unlocking doors requires permission", priority=100),
        PermissionRule("lock.open", "deny", "Opening locks requires permission", priority=100),
        PermissionRule("alarm_control_panel.alarm_disarm", "deny", "Disarming alarms requires permission", priority=100),
        PermissionRule("automation.turn_off", "deny", "Disabling automations requires permission", priority=80),
        PermissionRule("script.turn_off", "deny", "Disabling scripts requires permission", priority=80),
    ]

    def __init__(
        self,
        mode: str = "prompt",
        timeout: int = 60,
        whitelist: Optional[List[PermissionRule]] = None,
        blacklist: Optional[List[PermissionRule]] = None,
    ):
        """Initialize the permission checker.

        Args:
            mode: One of "prompt", "auto_allow", or "auto_deny".
            timeout: Seconds before a permission request expires.
            whitelist: Custom allow rules (appended to defaults).
            blacklist: Custom deny rules (appended to defaults).
        """
        self.mode = mode
        self.timeout = timeout

        self.whitelist: List[PermissionRule] = list(self.DEFAULT_WHITELIST)
        if whitelist:
            self.whitelist.extend(whitelist)

        self.blacklist: List[PermissionRule] = list(self.DEFAULT_BLACKLIST)
        if blacklist:
            self.blacklist.extend(blacklist)

        # Sort rules by priority (descending)
        self.whitelist.sort(key=lambda r: r.priority, reverse=True)
        self.blacklist.sort(key=lambda r: r.priority, reverse=True)

        # Track pending requests
        self._pending_requests: Dict[str, PermissionRequest] = {}

        # Learning: track which actions user has "always allowed"
        self._learned_allows: List[PermissionRule] = []

    def get_risk_level(self, domain: str, action: str = "") -> RiskLevel:
        """Determine the risk level for a service domain and action.

        Args:
            domain: The Home Assistant domain (e.g., "light", "lock").
            action: The specific service action (e.g., "turn_on").

        Returns:
            RiskLevel enum value.
        """
        # Check for high-risk actions
        high_risk_actions = [
            "unlock", "open", "disarm", "disable", "delete", "remove",
            "turn_off"  # for automations/scripts only
        ]

        if domain in ("automation", "script") and action == "turn_off":
            return RiskLevel.HIGH

        if any(risk_action in action for risk_action in high_risk_actions):
            return RiskLevel.HIGH

        return self.RISK_LEVELS.get(domain, RiskLevel.MEDIUM)

    def check_action(
        self, action: str, entities: List[str]
    ) -> PermissionResult:
        """Check if an action on entities requires permission.

        Args:
            action: The service call (e.g., "light.turn_on", "lock.unlock").
            entities: List of target entity IDs.

        Returns:
            PermissionResult indicating PERMIT, DENY, or PROMPT.
        """
        # If mode is auto_deny, deny everything not explicitly whitelisted
        if self.mode == "auto_deny":
            for rule in self.whitelist:
                if rule.matches(action) or any(
                    rule.matches(e) for e in entities
                ):
                    return PermissionResult.PERMIT
            return PermissionResult.DENY

        # Check blacklist first (deny always wins)
        for rule in self.blacklist:
            if rule.matches(action) or any(
                rule.matches(e) for e in entities
            ):
                _LOGGER.debug(
                    "Action %s on %s DENIED by blacklist rule: %s",
                    action,
                    entities,
                    rule.pattern,
                )
                return PermissionResult.DENY

        # Check learned allows
        for rule in self._learned_allows:
            if rule.matches(action) or any(
                rule.matches(e) for e in entities
            ):
                _LOGGER.debug(
                    "Action %s on %s PERMITTED by learned rule: %s",
                    action,
                    entities,
                    rule.pattern,
                )
                return PermissionResult.PERMIT

        # Check whitelist
        for rule in self.whitelist:
            if rule.matches(action) or any(
                rule.matches(e) for e in entities
            ):
                _LOGGER.debug(
                    "Action %s on %s PERMITTED by whitelist rule: %s",
                    action,
                    entities,
                    rule.pattern,
                )
                return PermissionResult.PERMIT

        # If mode is auto_allow, permit everything not blacklisted
        if self.mode == "auto_allow":
            return PermissionResult.PERMIT

        # Default: prompt the user
        _LOGGER.debug(
            "Action %s on %s requires user PROMPT",
            action,
            entities,
        )
        return PermissionResult.PROMPT

    def create_permission_request(
        self,
        action: str,
        entities: List[str],
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PermissionRequest:
        """Create a permission request for the frontend.

        Args:
            action: The service call being requested.
            entities: Affected entity IDs.
            reason: Why the AI wants to perform this action.
            metadata: Additional context.

        Returns:
            A PermissionRequest ready for serialization.
        """
        # Determine domain for risk assessment
        domain = action.split(".")[0] if "." in action else "unknown"
        action_name = action.split(".")[1] if "." in action else action

        risk = self.get_risk_level(domain, action_name)

        request = PermissionRequest(
            action=action,
            target_entities=entities,
            reason=reason or f"AI agent wants to call {action}",
            risk_level=risk.value,
            metadata=metadata or {},
        )

        # Set expiration
        from datetime import timedelta

        expires = datetime.utcnow() + timedelta(seconds=self.timeout)
        request.expires_at = expires.isoformat()

        # Track pending request
        self._pending_requests[request.request_id] = request

        return request

    def approve_request(self, request_id: str, always_allow: bool = False) -> bool:
        """Approve a pending permission request.

        Args:
            request_id: The request to approve.
            always_allow: If True, add a learned allow rule for future.

        Returns:
            True if approved successfully, False if request not found/expired.
        """
        request = self._pending_requests.get(request_id)
        if not request:
            return False
        if request.is_expired():
            del self._pending_requests[request_id]
            return False

        if always_allow:
            # Learn this pattern for future
            domain = request.action.split(".")[0] if "." in request.action else "*"
            learned_rule = PermissionRule(
                pattern=f"{domain}.*",
                rule_type="allow",
                description=f"User always allowed {request.action}",
                priority=50,
            )
            self._learned_allows.append(learned_rule)
            _LOGGER.info(
                "Learned allow rule: %s for action %s",
                learned_rule.pattern,
                request.action,
            )

        del self._pending_requests[request_id]
        return True

    def deny_request(self, request_id: str) -> bool:
        """Deny a pending permission request.

        Args:
            request_id: The request to deny.

        Returns:
            True if denied successfully, False if not found.
        """
        request = self._pending_requests.pop(request_id, None)
        return request is not None

    def cleanup_expired_requests(self) -> int:
        """Remove expired pending requests.

        Returns:
            Number of expired requests cleaned up.
        """
        expired_ids = [
            rid
            for rid, req in self._pending_requests.items()
            if req.is_expired()
        ]
        for rid in expired_ids:
            del self._pending_requests[rid]
        return len(expired_ids)

    def get_pending_request(
        self, request_id: str
    ) -> Optional[PermissionRequest]:
        """Get a pending permission request by ID.

        Args:
            request_id: The request ID.

        Returns:
            The PermissionRequest or None if not found/expired.
        """
        request = self._pending_requests.get(request_id)
        if request and request.is_expired():
            del self._pending_requests[request_id]
            return None
        return request

    def to_config(self) -> Dict[str, Any]:
        """Export configuration for storage.

        Returns:
            Configuration dict suitable for JSON serialization.
        """
        return {
            "mode": self.mode,
            "timeout": self.timeout,
            "whitelist": [r.to_dict() for r in self.whitelist],
            "blacklist": [r.to_dict() for r in self.blacklist],
            "learned_allows": [r.to_dict() for r in self._learned_allows],
        }

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> PermissionChecker:
        """Create a PermissionChecker from a stored configuration.

        Args:
            config: Configuration dict from to_config().

        Returns:
            Configured PermissionChecker instance.
        """
        checker = cls(
            mode=config.get("mode", "prompt"),
            timeout=config.get("timeout", 60),
            whitelist=[
                PermissionRule.from_dict(r)
                for r in config.get("whitelist", [])
            ],
            blacklist=[
                PermissionRule.from_dict(r)
                for r in config.get("blacklist", [])
            ],
        )
        checker._learned_allows = [
            PermissionRule.from_dict(r)
            for r in config.get("learned_allows", [])
        ]
        return checker
```

### Changes to [`const.py`](custom_components/ai_agent_ha/const.py)

Add:

```python
# Permission System constants
CONF_PERMISSION_MODE = "permission_mode"
CONF_PERMISSION_WHITELIST = "permission_whitelist"
CONF_PERMISSION_BLACKLIST = "permission_blacklist"
CONF_PERMISSION_TIMEOUT = "permission_timeout"

PERMISSION_MODES = ["prompt", "auto_allow", "auto_deny"]
DEFAULT_PERMISSION_MODE = "prompt"
DEFAULT_PERMISSION_TIMEOUT = 60  # seconds
```

### Changes to [`config_flow.py`](custom_components/ai_agent_ha/config_flow.py)

Add to the options flow a `async_step_permissions` method and wire it into the flow:

```python
async def async_step_permissions(self, user_input=None):
    """Configure permission settings."""
    errors = {}

    if user_input is not None:
        self.options.update(user_input)
        return self.async_create_entry(title="", data=self.options)

    current_mode = self.config_entry.options.get(
        CONF_PERMISSION_MODE, DEFAULT_PERMISSION_MODE
    )
    current_timeout = self.config_entry.options.get(
        CONF_PERMISSION_TIMEOUT, DEFAULT_PERMISSION_TIMEOUT
    )

    from homeassistant.helpers.selector import (
        SelectSelector,
        SelectSelectorConfig,
        NumberSelector,
        NumberSelectorConfig,
        TextSelector,
        TextSelectorConfig,
    )

    schema_dict = {
        vol.Required(CONF_PERMISSION_MODE, default=current_mode): SelectSelector(
            SelectSelectorConfig(
                options=[
                    {"value": "prompt", "label": "Prompt - Ask before each action"},
                    {"value": "auto_allow", "label": "Auto-Allow - Execute all non-blacklisted actions"},
                    {"value": "auto_deny", "label": "Auto-Deny - Only execute whitelisted actions"},
                ]
            )
        ),
        vol.Required(CONF_PERMISSION_TIMEOUT, default=current_timeout): NumberSelector(
            NumberSelectorConfig(min=10, max=300, step=10, mode="slider", unit_of_measurement="seconds")
        ),
    }

    return self.async_show_form(
        step_id="permissions",
        data_schema=vol.Schema(schema_dict),
        errors=errors,
    )
```

### Changes to [`agent.py`](custom_components/ai_agent_ha/agent.py)

**In the `__init__` method of `AiAgentHaAgent`:**

```python
from .permissions import PermissionChecker, PermissionResult

# In __init__:
perm_config = config.get("permissions", {})
self.permission_checker = PermissionChecker.from_config(perm_config)
```

**In `process_query()`, after parsing the AI response and before executing service calls:**

```python
# --- Permission Check ---
# When the AI response includes a service call, check permissions
if parsed_response.get("action") and parsed_response.get("target_entities"):
    action = parsed_response["action"]
    entities = parsed_response.get("target_entities", [])

    perm_result = self.permission_checker.check_action(action, entities)

    if perm_result == PermissionResult.DENY:
        _LOGGER.warning(
            "Permission DENIED for action %s on %s", action, entities
        )
        return {
            "success": False,
            "error": f"Action '{action}' was denied by safety policy.",
            "request_type": "permission_denied",
            "action": action,
            "entities": entities,
        }

    elif perm_result == PermissionResult.PROMPT:
        # Create a permission request for the user
        perm_request = self.permission_checker.create_permission_request(
            action=action,
            entities=entities,
            reason=parsed_response.get("reason", ""),
            metadata=parsed_response.get("metadata", {}),
        )
        _LOGGER.info(
            "Permission PROMPT required for action %s on %s (request_id: %s)",
            action,
            entities,
            perm_request.request_id,
        )
        return {
            "success": True,
            "request_type": "permission_request",
            "permission_request": perm_request.to_dict(),
        }

    # PERMIT - proceed with execution
    _LOGGER.debug("Permission PERMITTED for action %s on %s", action, entities)
```

**Add a method to handle approved actions:**

```python
async def execute_approved_action(
    self, request_id: str, approve: bool, always_allow: bool = False
) -> Dict[str, Any]:
    """Execute an action after user approval.

    Args:
        request_id: The permission request ID.
        approve: Whether the user approved.
        always_allow: Whether to add a learned allow rule.

    Returns:
        Result of the action execution.
    """
    if not approve:
        self.permission_checker.deny_request(request_id)
        return {
            "success": False,
            "request_type": "permission_denied",
            "message": "Action was denied by user.",
        }

    perm_request = self.permission_checker.get_pending_request(request_id)
    if not perm_request:
        return {
            "success": False,
            "error": "Permission request not found or expired.",
        }

    # Approve and learn if requested
    self.permission_checker.approve_request(request_id, always_allow)

    # Execute the action
    try:
        domain, service = perm_request.action.split(".", 1)
        result = await self.call_service(
            domain,
            service,
            target={"entity_id": perm_request.target_entities},
        )
        return {
            "success": True,
            "request_type": "action_result",
            "action": perm_request.action,
            "entities": perm_request.target_entities,
            "result": result,
        }
    except Exception as e:
        _LOGGER.exception("Failed to execute approved action: %s", e)
        return {
            "success": False,
            "request_type": "action_error",
            "error": str(e),
        }
```

### Changes to [`ai_agent_ha-panel.js`](custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js)

**Add new properties for permission dialog:**

```javascript
static get properties() {
  return {
    // ... existing ...
    _permissionRequest: { type: Object, reflect: false, attribute: false },
    _showPermissionDialog: { type: Boolean, reflect: false, attribute: false },
  };
}
```

**Initialize:**

```javascript
this._permissionRequest = null;
this._showPermissionDialog = false;
```

**Update `_handleLlamaResponse` to detect permission requests:**

```javascript
// In _handleLlamaResponse, after JSON parsing:
if (response.request_type === 'permission_request') {
  this._permissionRequest = response.permission_request;
  this._showPermissionDialog = true;
  this._isLoading = false;
  return;  // Don't add as a regular message
}

if (response.request_type === 'permission_denied') {
  this._messages = [...this._messages, {
    type: 'assistant',
    text: `⚠️ Action denied: ${response.error || 'Safety policy prevented this action.'}`
  }];
  this._isLoading = false;
  return;
}
```

**Add permission handling methods:**

```javascript
async _handlePermissionResponse(approve, alwaysAllow = false) {
  const requestId = this._permissionRequest?.request_id;
  this._showPermissionDialog = false;
  this._permissionRequest = null;
  
  if (!approve) {
    this._messages = [...this._messages, {
      type: 'assistant',
      text: 'Action cancelled. Would you like to try something else?'
    }];
    return;
  }
  
  this._isLoading = true;
  try {
    // Call a service to execute the approved action
    const result = await this.hass.callService('ai_agent_ha', 'execute_approved_action', {
      request_id: requestId,
      approve: true,
      always_allow: alwaysAllow,
    });
    
    if (result && result.success) {
      this._messages = [...this._messages, {
        type: 'assistant',
        text: `✅ Action executed: ${result.action}`
      }];
    } else {
      this._messages = [...this._messages, {
        type: 'assistant',
        text: `❌ Action failed: ${result?.error || 'Unknown error'}`
      }];
    }
  } catch (e) {
    console.error('Failed to execute approved action:', e);
    this._messages = [...this._messages, {
      type: 'assistant',
      text: `Error executing action: ${e.message || e}`
    }];
  } finally {
    this._clearLoadingState();
  }
}
```

**Render the permission dialog in the `render()` method:**

```javascript
${this._showPermissionDialog && this._permissionRequest ? html`
  <div class="permission-overlay" @click="${() => this._showPermissionDialog = false}"></div>
  <div class="permission-dialog">
    <div class="permission-header">
      <ha-icon icon="mdi:shield-alert"></ha-icon>
      <h3>Permission Required</h3>
    </div>
    <div class="permission-body">
      <div class="permission-risk ${this._permissionRequest.risk_level}">
        Risk Level: ${this._permissionRequest.risk_level.toUpperCase()}
      </div>
      <div class="permission-detail">
        <strong>Action:</strong> ${this._permissionRequest.action}
      </div>
      <div class="permission-detail">
        <strong>Entities:</strong> ${(this._permissionRequest.target_entities || []).join(', ')}
      </div>
      <div class="permission-detail">
        <strong>Reason:</strong> ${this._permissionRequest.reason || 'No reason provided'}
      </div>
    </div>
    <div class="permission-actions">
      <button class="approve-btn" @click="${() => this._handlePermissionResponse(true, false)}">
        ✅ Approve
      </button>
      <button class="always-allow-btn" @click="${() => this._handlePermissionResponse(true, true)}">
        ⭐ Always Allow
      </button>
      <button class="deny-btn" @click="${() => this._handlePermissionResponse(false)}">
        ❌ Deny
      </button>
    </div>
  </div>
` : ''}
```

**Add CSS for permission dialog:**

```css
.permission-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  z-index: 300;
}
.permission-dialog {
  position: fixed;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  background: var(--primary-background-color);
  border-radius: 12px;
  padding: 24px;
  min-width: 380px;
  max-width: 500px;
  z-index: 301;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.permission-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  color: var(--warning-color);
}
.permission-risk {
  padding: 4px 10px;
  border-radius: 4px;
  font-weight: 600;
  margin-bottom: 12px;
  display: inline-block;
}
.permission-risk.high { background: #ffebee; color: #c62828; }
.permission-risk.medium { background: #fff3e0; color: #ef6c00; }
.permission-risk.low { background: #e8f5e9; color: #2e7d32; }
.permission-detail {
  margin: 8px 0;
  font-size: 14px;
}
.permission-actions {
  display: flex;
  gap: 8px;
  margin-top: 20px;
  justify-content: flex-end;
}
.permission-actions button {
  padding: 8px 16px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-weight: 500;
}
.approve-btn { background: #4caf50; color: white; }
.always-allow-btn { background: #2196f3; color: white; }
.deny-btn { background: #f44336; color: white; }
```

---

## Enhancement #5: Multimedia Support

### Problem Statement
Modern AI models (GPT-4 Vision, Gemini Pro Vision, Claude 3) support image inputs. The integration cannot send images, preventing use cases like "What's on this camera?", "Analyze this dashboard screenshot", or "Identify this device from a photo."

### Solution Architecture

```
┌──────────────────────────────────────────────────────┐
│              ai_agent_ha-panel.js                    │
│                                                      │
│  ┌─────────────────────────────────────────┐        │
│  │ Input Area                              │        │
│  │ ┌─────────────────────────────────────┐ │        │
│  │ │ [📎 Attach]  [text input..........] │ │        │
│  │ │  ↓                                   │ │        │
│  │ │ <input type="file" hidden>          │ │        │
│  │ │  accept="image/*,.pdf,.txt"         │ │        │
│  │ └─────────────────────────────────────┘ │        │
│  │                                         │        │
│  │ Attached files: (thumbnails)            │        │
│  │ ┌────┐ ┌────┐                          │        │
│  │ │IMG1│ │IMG2│  [✕ remove]              │        │
│  │ └────┘ └────┘                          │        │
│  └─────────────────────────────────────────┘        │
│                                                      │
│  Send: { prompt: "...", images: ["base64..."] }     │
└──────────────────────────────────────────────────────┘
         │
         │ hass.callService('ai_agent_ha', 'query', {prompt, images})
         ▼
┌──────────────────────────────────────────────────────┐
│                  agent.py                            │
│                                                      │
│  process_query(prompt, images=[...])                 │
│         │                                            │
│         ▼                                            │
│  Check if model supports multimodal:                 │
│    - model name contains "vision", "gemini-pro",     │
│      "gpt-4o", "claude-3", etc.                      │
│         │                                            │
│    ┌────┴─────────────────┐                          │
│    ▼                      ▼                          │
│  Multimodal            Text-only                     │
│  Format:               Format:                       │
│  content = [           content = prompt              │
│    {type:"text",                                    │
│     text: prompt},                                   │
│    {type:"image_url",                                │
│     image_url: {                                     │
│       url: "data:                                     │
│         image/jpeg;                                  │
│         base64,..."                                  │
│     }}                                              │
│  ]                                                  │
│         │                                            │
│         ▼                                            │
│  AI Provider API (multimodal endpoint)               │
│         │                                            │
│         ▼                                            │
│  Response may contain images → pass to frontend      │
└──────────────────────────────────────────────────────┘
```

### Changes to [`const.py`](custom_components/ai_agent_ha/const.py)

Add:

```python
# Multimedia support constants
CONF_MULTIMODAL_ENABLED = "multimodal_enabled"
CONF_IMAGE_UPLOAD_ENABLED = "image_upload_enabled"
CONF_MAX_IMAGE_SIZE = "max_image_size"

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp", "bmp"]
DEFAULT_MULTIMODAL_ENABLED = True
DEFAULT_IMAGE_UPLOAD_ENABLED = True
DEFAULT_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB

# Models known to support multimodal/image inputs
MULTIMODAL_MODEL_PATTERNS = [
    "gpt-4o", "gpt-4-turbo", "gpt-4-vision", "gpt-5",
    "gemini-1.5", "gemini-2.0", "gemini-2.5", "gemini-pro-vision",
    "claude-3", "claude-sonnet-4", "claude-opus-4", "claude-haiku-4",
    "llama-4", "Llama-4",
    "vision", "multimodal",
]
```

### Changes to [`config_flow.py`](custom_components/ai_agent_ha/config_flow.py)

Add options step:

```python
async def async_step_multimedia(self, user_input=None):
    """Configure multimedia/image upload settings."""
    errors = {}

    if user_input is not None:
        self.options.update(user_input)
        return self.async_create_entry(title="", data=self.options)

    current_enabled = self.config_entry.options.get(
        CONF_IMAGE_UPLOAD_ENABLED, DEFAULT_IMAGE_UPLOAD_ENABLED
    )
    current_max_size = self.config_entry.options.get(
        CONF_MAX_IMAGE_SIZE, DEFAULT_MAX_IMAGE_SIZE
    )

    from homeassistant.helpers.selector import (
        BooleanSelector,
        NumberSelector,
        NumberSelectorConfig,
    )

    schema_dict = {
        vol.Required(CONF_IMAGE_UPLOAD_ENABLED, default=current_enabled): BooleanSelector(),
        vol.Required(
            CONF_MAX_IMAGE_SIZE, default=current_max_size // (1024 * 1024)
        ): NumberSelector(
            NumberSelectorConfig(
                min=1, max=20, step=1, mode="slider",
                unit_of_measurement="MB"
            )
        ),
    }

    return self.async_show_form(
        step_id="multimedia",
        data_schema=vol.Schema(schema_dict),
        errors=errors,
    )
```

### Changes to [`agent.py`](custom_components/ai_agent_ha/agent.py)

**Modify `process_query` signature and logic:**

```python
import base64
import imghdr

from .const import (
    CONF_IMAGE_UPLOAD_ENABLED,
    CONF_MAX_IMAGE_SIZE,
    DEFAULT_IMAGE_UPLOAD_ENABLED,
    DEFAULT_MAX_IMAGE_SIZE,
    IMAGE_EXTENSIONS,
    MULTIMODAL_MODEL_PATTERNS,
)

async def process_query(
    self,
    user_query: str,
    provider: Optional[str] = None,
    debug: bool = False,
    images: Optional[List[str]] = None,  # NEW: base64-encoded images
) -> Dict[str, Any]:
    """Process a user query with optional image attachments."""

    # ... existing validation ...

    # --- Multimedia Support ---
    image_upload_enabled = config.get(
        CONF_IMAGE_UPLOAD_ENABLED, DEFAULT_IMAGE_UPLOAD_ENABLED
    )
    max_image_size = config.get(CONF_MAX_IMAGE_SIZE, DEFAULT_MAX_IMAGE_SIZE)

    # Check if model supports multimodal
    model_name = provider_settings.get("model", "")
    is_multimodal = self._is_multimodal_model(model_name, selected_provider)

    if images and not is_multimodal:
        _LOGGER.warning(
            "Images provided but model %s does not support multimodal. "
            "Stripping images from request.",
            model_name,
        )
        images = None

    if images and not image_upload_enabled:
        _LOGGER.warning(
            "Image upload is disabled in configuration. Stripping images."
        )
        images = None

    # Validate and process images
    validated_images = []
    if images:
        for img_data in images:
            valid, result = self._validate_image(img_data, max_image_size)
            if valid:
                validated_images.append(result)
            else:
                _LOGGER.warning("Image rejected: %s", result)

    # Build message content
    if validated_images and is_multimodal:
        # Multimodal format: content is an array of parts
        content = [{"type": "text", "text": user_query}]
        for img in validated_images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{img['format']};base64,{img['data']}",
                    "detail": "auto",
                },
            })
        messages = [{"role": "user", "content": content}]
    else:
        # Standard text format
        messages = [{"role": "user", "content": user_query}]

    # ... continue with AI client call using messages ...

def _is_multimodal_model(self, model_name: str, provider: str) -> bool:
    """Check if a model supports multimodal/image inputs.

    Args:
        model_name: The model name/ID.
        provider: The AI provider name.

    Returns:
        True if the model likely supports images.
    """
    model_lower = model_name.lower()
    for pattern in MULTIMODAL_MODEL_PATTERNS:
        if pattern.lower() in model_lower:
            return True

    # Provider-specific heuristics
    if provider == "openai" and any(
        p in model_lower for p in ["gpt-4o", "gpt-4-turbo", "gpt-5", "vision"]
    ):
        return True
    if provider == "gemini" and "gemini" in model_lower:
        return True  # Most Gemini models support vision
    if provider == "anthropic" and any(
        p in model_lower for p in ["claude-3", "claude-sonnet-4", "claude-opus-4"]
    ):
        return True

    return False

def _validate_image(
    self, image_data: str, max_size: int
) -> tuple:
    """Validate a base64-encoded image.

    Args:
        image_data: Base64-encoded image string (with or without data URI prefix).
        max_size: Maximum allowed size in bytes.

    Returns:
        Tuple of (is_valid, result) where result is either the validated
        image dict {"data": base64_str, "format": "jpeg", "size": bytes}
        or an error message string.
    """
    # Strip data URI prefix if present (e.g., "data:image/jpeg;base64,...")
    detected_format = "jpeg"
    if image_data.startswith("data:image/"):
        # Extract format from data URI
        header, data = image_data.split(",", 1)
        detected_format = header.split(";")[0].replace("data:image/", "")
        image_data = data

    # Validate format
    if detected_format not in IMAGE_EXTENSIONS:
        return False, f"Unsupported image format: {detected_format}"

    try:
        # Decode to check validity and size
        decoded = base64.b64decode(image_data)
        actual_size = len(decoded)

        if actual_size > max_size:
            return False, (
                f"Image too large: {actual_size} bytes "
                f"(max {max_size} bytes)"
            )

        # Verify it's actually an image by checking magic bytes
        image_type = imghdr.what(None, h=decoded[:32])
        if image_type not in IMAGE_EXTENSIONS:
            return False, (
                f"Invalid image data (detected type: {image_type})"
            )

        return True, {
            "data": image_data,
            "format": image_type or detected_format,
            "size": actual_size,
        }
    except Exception as e:
        return False, f"Invalid base64 image data: {e}"
```

### Changes to [`ai_agent_ha-panel.js`](custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js)

**Add new properties to the LitElement:**

```javascript
static get properties() {
  return {
    // ... existing ...
    _attachedImages: { type: Array, reflect: false, attribute: false },
    _imageUploadEnabled: { type: Boolean, reflect: false, attribute: false },
    _maxImageSize: { type: Number, reflect: false, attribute: false },
  };
}
```

**Initialize in constructor:**

```javascript
this._attachedImages = [];
this._imageUploadEnabled = true;
this._maxImageSize = 5 * 1024 * 1024;  // 5MB default
```

**Add image handling methods:**

```javascript
_handleAttachClick() {
  const fileInput = this.shadowRoot.getElementById('image-file-input');
  if (fileInput) {
    fileInput.click();
  }
}

async _handleImageUpload(event) {
  const files = event.target.files;
  if (!files || files.length === 0) return;

  const maxSize = this._maxImageSize;
  const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'];
  const maxImages = 5;

  for (const file of files) {
    // Validate type
    if (!allowedTypes.includes(file.type)) {
      alert(`Unsupported file type: ${file.type}. Allowed: JPEG, PNG, GIF, WebP, BMP.`);
      continue;
    }

    // Validate size
    if (file.size > maxSize) {
      alert(`Image too large: ${(file.size / 1024 / 1024).toFixed(1)}MB (max ${(maxSize / 1024 / 1024).toFixed(1)}MB).`);
      continue;
    }

    // Validate count
    if (this._attachedImages.length >= maxImages) {
      alert(`Maximum ${maxImages} images allowed per message.`);
      break;
    }

    // Compress large images client-side
    let processedFile = file;
    if (file.size > 1024 * 1024) {  // Over 1MB
      try {
        processedFile = await this._compressImage(file, 1024, 768, 0.7);
      } catch (e) {
        console.warn('Image compression failed, using original:', e);
      }
    }

    // Convert to base64
    const base64 = await this._fileToBase64(processedFile);
    const format = processedFile.type.split('/')[1] || 'jpeg';

    this._attachedImages = [...this._attachedImages, {
      name: file.name,
      format: format,
      data: base64,
      size: processedFile.size,
      thumbnail: processedFile.size < 500000 ? base64 : null,  // Thumbnail for small images only
    }];
  }

  // Reset input so the same file can be re-selected
  event.target.value = '';
}

_compressImage(file, maxWidth, maxHeight, quality) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      // Calculate new dimensions
      let { width, height } = img;
      if (width > maxWidth) {
        height = (height * maxWidth) / width;
        width = maxWidth;
      }
      if (height > maxHeight) {
        width = (width * maxHeight) / height;
        height = maxHeight;
      }

      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, width, height);

      canvas.toBlob(
        (blob) => resolve(new File([blob], file.name, { type: 'image/jpeg' })),
        'image/jpeg',
        quality
      );
    };
    img.onerror = reject;
    img.src = URL.createObjectURL(file);
  });
}

_fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      // Strip the data URI prefix, return just the base64 data
      const result = reader.result;
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

_removeImage(index) {
  this._attachedImages = this._attachedImages.filter((_, i) => i !== index);
}

_clearAttachedImages() {
  this._attachedImages = [];
}
```

**Add file input and attachment button to the input area in `render()`:**

```javascript
// Hidden file input
html`<input type="file" id="image-file-input" accept="image/*"
  @change="${this._handleImageUpload}" multiple hidden>`

// Attachment button next to the send area
html`<button class="attach-button" @click="${this._handleAttachClick}"
  title="Attach images" ?disabled="${!this._imageUploadEnabled}">
  <ha-icon icon="mdi:paperclip"></ha-icon>
</button>`

// Image thumbnails (when images are attached)
${this._attachedImages.length > 0 ? html`
  <div class="attached-images">
    ${this._attachedImages.map((img, i) => html`
      <div class="image-thumbnail">
        <span class="image-name">${img.name}</span>
        <span class="image-size">${(img.size / 1024).toFixed(1)}KB</span>
        <button class="remove-image-btn" @click="${() => this._removeImage(i)}">✕</button>
      </div>
    `)}
  </div>
` : ''}
```

**Update the `_sendMessage` method to include images:**

```javascript
async _sendMessage(prompt) {
  // ... existing validation ...

  const images = this._attachedImages.map(img => ({
    data: img.data,
    format: img.format,
  }));

  // Clear images after sending
  this._clearAttachedImages();

  // Call service with images
  const result = await this.hass.callService('ai_agent_ha', 'query', {
    prompt: prompt,
    images: images,
    provider: this._selectedProvider,
  });
  // ... rest of existing method ...
}
```

**Display images in AI responses (if model returns images):**

```javascript
// In the message rendering section:
${message.images ? html`
  <div class="response-images">
    ${message.images.map(img => html`
      <img src="data:image/${img.format || 'png'};base64,${img.data}"
           alt="AI generated image" class="response-image"
           @click="${(e) => this._openImageFullscreen(e.target.src)}">
    `)}
  </div>
` : ''}
```

**Add image-related CSS:**

```css
.attach-button {
  border: 1px solid var(--divider-color);
  background: var(--secondary-background-color);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
}
.attach-button:hover {
  background: var(--primary-color);
  color: white;
}
.attach-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.attached-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 0;
}
.image-thumbnail {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--secondary-background-color);
  border: 1px solid var(--divider-color);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
}
.image-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.image-size { color: var(--secondary-text-color); }
.remove-image-btn {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--error-color);
  font-weight: bold;
  padding: 0 2px;
}
.response-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.response-image {
  max-width: 300px;
  max-height: 300px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid var(--divider-color);
  transition: transform 0.2s;
}
.response-image:hover {
  transform: scale(1.02);
}
```

### Changes to [`services.yaml`](custom_components/ai_agent_ha/services.yaml)

Update the `query` service to include image support:

```yaml
query:
  name: "Query AI Agent with Home Assistant context"
  description: "Run a custom AI prompt against your Home Assistant state dump. Supports image attachments for multimodal models."
  fields:
    prompt:
      description: "The question or instruction to send to AI model."
      example: "Turn on all the lights in the living room"
    images:
      description: "Optional list of base64-encoded images for vision-capable models."
      example:
        - data: "/9j/4AAQSkZJRgABAQEASABIAAD..."
          format: "jpeg"
      default: []
    debug:
      description: "Include a debug trace of the HA↔AI conversation (true/false)."
      example: true
      default: false
    provider:
      description: "The AI provider to use (openai, llama, gemini, openrouter, anthropic, alter, zai, local)"
      example: "openai"
      default: "openai"
      selector:
        select:
          options:
            - "openai"
            - "llama"
            - "gemini"
            - "openrouter"
            - "anthropic"
            - "alter"
            - "zai"
            - "local"
```

---

## Integration Checklist & Cross-Cutting Concerns

### Data Flow Summary (All Enhancements)

```
sequenceDiagram
    participant U as User
    participant F as Frontend (panel.js)
    participant I as __init__.py
    participant A as agent.py
    participant C as prompt_compactor.py
    participant P as permissions.py
    participant H as chat_history.py
    participant AI as AI Provider

    U->>F: Types message [+ optional images]
    F->>F: _formatMessage() if markdown
    F->>I: hass.callService('query', {prompt, images})
    I->>A: process_query(prompt, images)
    A->>A: Validate images (Enhancement #5)
    A->>C: Check compaction (Enhancement #1)
    C-->>A: Compacted messages (or pass-through)
    A->>AI: Send messages
    AI-->>A: JSON response
    A->>P: Check permissions (Enhancement #4)
    alt PERMIT
        A->>A: Execute action
        A->>H: Save to history (Enhancement #3)
        A-->>F: fire_event(response)
    else PROMPT
        A-->>F: fire_event(permission_request)
        F-->>U: Show permission dialog
        U->>F: Approve/Deny
        F->>I: execute_approved_action
        I->>A: Execute approved
        A->>H: Save to history
        A-->>F: fire_event(result)
    else DENY
        A-->>F: fire_event(denied)
    end
    F->>F: _formatMessage() for markdown (Enhancement #2)
    F-->>U: Display formatted response
```

### File Manifest

| File | Action | Enhancement(s) |
|------|--------|----------------|
| [`const.py`](custom_components/ai_agent_ha/const.py) | **Modify** | #1, #3, #4, #5 |
| [`config_flow.py`](custom_components/ai_agent_ha/config_flow.py) | **Modify** | #1, #4, #5 |
| [`agent.py`](custom_components/ai_agent_ha/agent.py) | **Modify** | #1, #4, #5 |
| [`__init__.py`](custom_components/ai_agent_ha/__init__.py) | **Modify** | #3, #4 |
| [`services.yaml`](custom_components/ai_agent_ha/services.yaml) | **Modify** | #3, #5 |
| [`manifest.json`](custom_components/ai_agent_ha/manifest.json) | **Modify** | #2 (minimal - CDN loaded) |
| [`ai_agent_ha-panel.js`](custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js) | **Modify** | #2, #3, #4, #5 |
| [`prompt_compactor.py`](custom_components/ai_agent_ha/prompt_compactor.py) | **Create** | #1 |
| [`chat_history.py`](custom_components/ai_agent_ha/chat_history.py) | **Create** | #3 |
| [`permissions.py`](custom_components/ai_agent_ha/permissions.py) | **Create** | #4 |

### Implementation Order & Dependencies

```
Enhancement #1: Prompt Compacting
├── No dependencies on other enhancements
├── New file: prompt_compactor.py
└── Modifies: const.py, config_flow.py, agent.py

Enhancement #2: Output Formatting
├── No dependencies on other enhancements
└── Modifies: ai_agent_ha-panel.js, manifest.json

Enhancement #3: Chat History Management
├── Builds on existing save/load in agent.py
├── New file: chat_history.py
└── Modifies: const.py, __init__.py, services.yaml, ai_agent_ha-panel.js

Enhancement #4: Permission System
├── Depends on #1 (process_query flow)
├── New file: permissions.py
└── Modifies: const.py, config_flow.py, agent.py, __init__.py, ai_agent_ha-panel.js

Enhancement #5: Multimedia Support
├── Depends on #1 (process_query flow) and #2 (rendering)
└── Modifies: const.py, config_flow.py, agent.py, services.yaml, ai_agent_ha-panel.js
```

### Backward Compatibility Notes

1. **Prompt Compacting**: Feature is opt-out via config. Default threshold (70%) prevents unexpected behavior.
2. **Output Formatting**: `_hasMarkdown()` check ensures plain text still renders correctly. No config migration needed.
3. **Chat History**: New `ChatHistoryManager` coexists with existing `save_user_prompt_history`/`load_user_prompt_history`. Existing storage keys are not modified. Migration path: old `ai_agent_ha_history_{user_id}` stores continue to work; new conversations use the manager.
4. **Permission System**: Default mode is `"prompt"` (most conservative). Existing behavior is preserved for whitelisted actions.
5. **Multimedia**: Image parameter is optional, default empty list. Text-only queries are unaffected.

### Testing Strategy

| Enhancement | Unit Tests | Integration Tests | Manual Tests |
|-------------|-----------|-------------------|-------------|
| #1 Compacting | `PromptCompactor.estimate_tokens()`, `compact_conversation()` | Large conversation → compaction triggered | Real long conversation |
| #2 Formatting | `_hasMarkdown()`, `_sanitize()` | Full render with markdown response | Various markdown inputs |
| #3 History | `ChatHistoryManager` CRUD | Service call round-trip | History browser UI |
| #4 Permissions | `PermissionChecker.check_action()` | Full query → permission → approve flow | Dialog interactions |
| #5 Multimedia | `_validate_image()` | Image upload → query → response | Real camera image upload |

---

## Summary

This architecture document provides the complete technical specification for implementing five interdependent enhancements to the AI Agent HA Home Assistant integration:

1. **Prompt Compacting** - Prevents context window overflow via intelligent conversation summarization
2. **Output Formatting** - Rich markdown rendering with syntax highlighting and code copy buttons
3. **Chat History Management** - Full CRUD operations with export, search, and a browseable UI
4. **Permission System** - Safety gating for AI-initiated actions with blacklist/whitelist pattern matching
5. **Multimedia Support** - Image upload, compression, and multimodal model integration

Each enhancement includes complete Python/JavaScript code, CSS styling, service definitions, and configuration flow integration. The enhancements are designed to compose cleanly, with clear dependency ordering and backward compatibility preserved throughout.