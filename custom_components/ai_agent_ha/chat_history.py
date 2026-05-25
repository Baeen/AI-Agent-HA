"""Chat history management for AI Agent HA conversations.

Provides conversation listing, deletion, export, rename, and search operations
on top of the Home Assistant storage layer.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "ai_agent_ha_conversations"
STORAGE_VERSION = 1


@dataclass
class ConversationMetadata:
    """Metadata for a saved conversation.

    Attributes:
        conversation_id: Unique conversation identifier (UUID).
        name: Human-readable name for the conversation.
        created_at: ISO 8601 timestamp of creation.
        updated_at: ISO 8601 timestamp of last modification.
        message_count: Number of messages in the conversation.
        preview: Last message preview (max 200 chars).
        tags: User-assigned tags for organization.
        is_pinned: Whether this conversation is pinned.
    """

    conversation_id: str = ""
    name: str = ""
    created_at: str = ""
    updated_at: str = ""
    message_count: int = 0
    preview: str = ""
    tags: List[str] = field(default_factory=list)
    is_pinned: bool = False

    def __post_init__(self):
        """Initialize default values if not provided."""
        if not self.conversation_id:
            self.conversation_id = str(uuid4())
        now = datetime.utcnow().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if self.tags is None:
            self.tags = []
        # Truncate preview to 200 chars
        if len(self.preview) > 200:
            self.preview = self.preview[:200]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to a dictionary."""
        return {
            "conversation_id": self.conversation_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "preview": self.preview,
            "tags": self.tags,
            "is_pinned": self.is_pinned,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMetadata":
        """Deserialize metadata from a dictionary."""
        return cls(
            conversation_id=data.get("conversation_id", ""),
            name=data.get("name", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            message_count=data.get("message_count", 0),
            preview=data.get("preview", ""),
            tags=data.get("tags", []),
            is_pinned=data.get("is_pinned", False),
        )

    @classmethod
    def from_messages(
        cls,
        messages: List[Dict[str, Any]],
        name: str = "",
    ) -> "ConversationMetadata":
        """Create metadata from a list of messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            name: Optional custom name.

        Returns:
            ConversationMetadata instance.
        """
        # Generate preview from last message
        preview = ""
        for msg in reversed(messages):
            if msg.get("type") in ("user", "assistant", "unknown"):
                preview = str(msg.get("text", ""))
                break

        if not preview and messages:
            preview = str(messages[-1].get("text", ""))

        if not name:
            # Auto-generate name from first user message
            first_user_preview = ""
            for msg in messages:
                if msg.get("type") == "user":
                    first_user_preview = str(msg.get("text", ""))[:50]
                    break

            if first_user_preview:
                name = f'"{first_user_preview}{"..." if len(first_user_preview) >= 50 else ""}"'
            else:
                name = "New Conversation"

        return cls(
            name=name,
            message_count=len(messages),
            preview=preview[:200],
        )


class ChatHistoryManager:
    """Manages chat history for AI Agent HA.

    Uses Home Assistant's Store for persistent storage of conversation
    metadata index and individual conversation data.

    Storage layout:
      Storage key: "ai_agent_ha_conversations"
        → { "conversations": { conv_id: { "metadata": {...}, "messages": [...] } } }
    """

    def __init__(self, hass: HomeAssistant):
        """Initialize the chat history manager.

        Args:
            hass: The Home Assistant instance.
        """
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """Load the data from storage if not already loaded."""
        if self._loaded:
            return
        stored = await self._store.async_load()
        if stored and "conversations" in stored:
            self._data = stored["conversations"]
        else:
            self._data = {}
        self._loaded = True

    async def _save_data(self) -> None:
        """Persist the data to storage."""
        await self._ensure_loaded()
        await self._store.async_save({"conversations": self._data})

    async def load_conversations(self) -> List[ConversationMetadata]:
        """Load all conversation metadata.

        Returns:
            List of ConversationMetadata sorted by updated_at descending (pinned first).
        """
        await self._ensure_loaded()
        metadata_list = []
        for conv_id, conv_data in self._data.items():
            meta_dict = conv_data.get("metadata", {})
            metadata_list.append(ConversationMetadata.from_dict(meta_dict))

        # Sort: pinned first, then by updated_at descending
        metadata_list.sort(
            key=lambda c: (
                not c.is_pinned,  # Pinned first
                c.updated_at or c.created_at or "",  # Then by date descending
            ),
            reverse=False,
        )
        # Fix: pinned should come first, so we need a custom sort
        pinned = [c for c in metadata_list if c.is_pinned]
        unpinned = [c for c in metadata_list if not c.is_pinned]

        def sort_key(c):
            return c.updated_at or c.created_at or ""

        pinned.sort(key=sort_key, reverse=True)
        unpinned.sort(key=sort_key, reverse=True)

        return pinned + unpinned

    async def save_conversation(
        self,
        conversation_id: str,
        messages: List[Dict[str, Any]],
        name: str = "",
    ) -> bool:
        """Save a full conversation.

        Args:
            conversation_id: Unique conversation identifier.
            messages: List of message dicts with 'type' and 'text' keys.
            name: Optional custom name (auto-generated if empty).

        Returns:
            True if saved successfully.
        """
        await self._ensure_loaded()

        # Create or update metadata
        if conversation_id in self._data:
            metadata = ConversationMetadata.from_dict(
                self._data[conversation_id].get("metadata", {})
            )
            metadata.message_count = len(messages)
            metadata.updated_at = datetime.utcnow().isoformat()
            if name:
                metadata.name = name
        else:
            metadata = ConversationMetadata.from_messages(messages, name)
            metadata.conversation_id = conversation_id

        # Save conversation data
        self._data[conversation_id] = {
            "metadata": metadata.to_dict(),
            "messages": messages,
        }

        await self._save_data()

        _LOGGER.debug(
            "Saved conversation %s with %d messages",
            conversation_id,
            len(messages),
        )
        return True

    async def get_conversation(self, conversation_id: str) -> Optional[List[Dict]]:
        """Get full conversation messages.

        Args:
            conversation_id: The conversation identifier.

        Returns:
            List of message dicts, or None if not found.
        """
        await self._ensure_loaded()
        if conversation_id not in self._data:
            return None

        conv_data = self._data[conversation_id]
        return conv_data.get("messages", [])

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation.

        Args:
            conversation_id: The conversation identifier.

        Returns:
            True if deleted, False if not found.
        """
        await self._ensure_loaded()
        if conversation_id not in self._data:
            return False

        del self._data[conversation_id]
        await self._save_data()

        _LOGGER.info("Deleted conversation %s", conversation_id)
        return True

    async def rename_conversation(self, conversation_id: str, name: str) -> bool:
        """Rename a conversation.

        Args:
            conversation_id: The conversation identifier.
            name: New name for the conversation.

        Returns:
            True if renamed, False if not found.
        """
        await self._ensure_loaded()
        if conversation_id not in self._data:
            return False

        metadata = ConversationMetadata.from_dict(
            self._data[conversation_id].get("metadata", {})
        )
        metadata.name = name
        metadata.updated_at = datetime.utcnow().isoformat()

        self._data[conversation_id]["metadata"] = metadata.to_dict()
        await self._save_data()

        _LOGGER.info("Renamed conversation %s to %s", conversation_id, name)
        return True

    async def export_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Export a conversation as a dict (for JSON download).

        Args:
            conversation_id: The conversation identifier.

        Returns:
            Dict with metadata and messages, or None if not found.
        """
        await self._ensure_loaded()
        if conversation_id not in self._data:
            return None

        return self._data[conversation_id].copy()

    async def search_conversations(self, query: str) -> List[ConversationMetadata]:
        """Search conversations by content (case-insensitive).

        Searches name, preview, and message content for the query string.

        Args:
            query: Search query string.

        Returns:
            List of matching ConversationMetadata.
        """
        await self._ensure_loaded()
        query_lower = query.lower()
        results = []

        for conv_id, conv_data in self._data.items():
            metadata = ConversationMetadata.from_dict(
                conv_data.get("metadata", {})
            )

            # Check name and preview first (fast path)
            if (
                query_lower in metadata.name.lower()
                or query_lower in metadata.preview.lower()
            ):
                results.append(metadata)
                continue

            # Check full message content (slow path)
            for msg in conv_data.get("messages", []):
                content = str(msg.get("text", "")).lower()
                if query_lower in content:
                    results.append(metadata)
                    break

            # Check tags
            for tag in metadata.tags:
                if query_lower in tag.lower():
                    results.append(metadata)
                    break

        # Sort by updated_at descending
        results.sort(
            key=lambda c: c.updated_at or c.created_at or "",
            reverse=True,
        )
        return results

    async def clear_old_conversations(self, days_threshold: int = 30) -> int:
        """Delete conversations older than threshold.

        Args:
            days_threshold: Delete conversations older than this many days.

        Returns:
            Number of conversations deleted.
        """
        await self._ensure_loaded()
        cutoff = datetime.utcnow() - timedelta(days=days_threshold)
        cutoff_iso = cutoff.isoformat()
        to_delete = []

        for conv_id, conv_data in self._data.items():
            metadata = ConversationMetadata.from_dict(
                conv_data.get("metadata", {})
            )
            updated_at = metadata.updated_at or metadata.created_at or ""
            if updated_at < cutoff_iso:
                to_delete.append(conv_id)

        for conv_id in to_delete:
            del self._data[conv_id]

        await self._save_data()
        _LOGGER.info(
            "Cleared %d conversations older than %d days",
            len(to_delete),
            days_threshold,
        )
        return len(to_delete)

    async def pin_conversation(self, conversation_id: str) -> bool:
        """Pin a conversation to keep it at the top.

        Args:
            conversation_id: The conversation identifier.

        Returns:
            True if pinned, False if not found.
        """
        await self._ensure_loaded()
        if conversation_id not in self._data:
            return False

        metadata = ConversationMetadata.from_dict(
            self._data[conversation_id].get("metadata", {})
        )
        metadata.is_pinned = True
        metadata.updated_at = datetime.utcnow().isoformat()

        self._data[conversation_id]["metadata"] = metadata.to_dict()
        await self._save_data()

        _LOGGER.info("Pinned conversation %s", conversation_id)
        return True

    async def add_tag(self, conversation_id: str, tag: str) -> bool:
        """Add a tag to a conversation.

        Args:
            conversation_id: The conversation identifier.
            tag: Tag to add.

        Returns:
            True if tag added, False if not found.
        """
        await self._ensure_loaded()
        if conversation_id not in self._data:
            return False

        metadata = ConversationMetadata.from_dict(
            self._data[conversation_id].get("metadata", {})
        )

        if tag not in metadata.tags:
            metadata.tags.append(tag)
            metadata.updated_at = datetime.utcnow().isoformat()

            self._data[conversation_id]["metadata"] = metadata.to_dict()
            await self._save_data()

        _LOGGER.debug("Added tag '%s' to conversation %s", tag, conversation_id)
        return True

    async def import_conversation(
        self,
        data: Dict[str, Any],
        conflict_resolution: str = "rename",
    ) -> Optional[str]:
        """Import a conversation from exported data.

        Args:
            data: Conversation data with 'metadata' and 'messages' keys.
            conflict_resolution: How to handle conflicts - 'rename', 'overwrite', or 'skip'.

        Returns:
            Conversation ID if imported, None if skipped or failed.
        """
        await self._ensure_loaded()

        # Validate data structure
        if "metadata" not in data and "messages" not in data:
            _LOGGER.error("Invalid conversation data structure")
            return None

        metadata_dict = data.get("metadata", {})
        messages = data.get("messages", [])

        # Create metadata if not provided
        if not metadata_dict:
            metadata_dict = ConversationMetadata.from_messages(messages).to_dict()

        metadata = ConversationMetadata.from_dict(metadata_dict)

        # Check for conflicts
        existing_id = None
        for conv_id, conv_data in self._data.items():
            existing_meta = ConversationMetadata.from_dict(conv_data.get("metadata", {}))
            if existing_meta.created_at == metadata.created_at and existing_meta.name == metadata.name:
                existing_id = conv_id
                break

        if existing_id:
            if conflict_resolution == "skip":
                _LOGGER.info("Skipping import - conversation already exists: %s", metadata.name)
                return None
            elif conflict_resolution == "overwrite":
                _LOGGER.info("Overwriting existing conversation: %s", metadata.name)
                del self._data[existing_id]
            else:  # rename
                # Generate new ID
                metadata.conversation_id = str(uuid4())
                metadata.created_at = datetime.utcnow().isoformat()
                metadata.updated_at = datetime.utcnow().isoformat()

        # Ensure conversation has an ID
        if not metadata.conversation_id:
            metadata.conversation_id = str(uuid4())

        # Store the conversation
        self._data[metadata.conversation_id] = {
            "metadata": metadata.to_dict(),
            "messages": messages,
        }

        await self._save_data()
        _LOGGER.info("Imported conversation: %s (%d messages)", metadata.name, len(messages))
        return metadata.conversation_id

    async def export_conversation_as_markdown(self, conversation_id: str) -> Optional[str]:
        """Export a conversation as formatted Markdown.

        Args:
            conversation_id: The conversation identifier.

        Returns:
            Markdown string or None if not found.
        """
        await self._ensure_loaded()
        if conversation_id not in self._data:
            return None

        conv_data = self._data[conversation_id]
        metadata = ConversationMetadata.from_dict(conv_data.get("metadata", {}))
        messages = conv_data.get("messages", [])

        lines = [
            f"# {metadata.name}",
            "",
            f"**Conversation ID:** {conversation_id}",
            f"**Created:** {metadata.created_at}",
            f"**Updated:** {metadata.updated_at}",
            f"**Messages:** {metadata.message_count}",
        ]

        if metadata.tags:
            lines.append(f"**Tags:** {', '.join(metadata.tags)}")

        lines.extend(["", "---", ""])

        for msg in messages:
            role = msg.get("type", "unknown")
            text = msg.get("text", "")
            timestamp = msg.get("timestamp", "")

            if role == "user":
                lines.append(f"### 👤 User")
            elif role == "assistant":
                lines.append(f"### 🤖 Assistant")
            elif role == "system":
                lines.append(f"### ⚙️ System")
            else:
                lines.append(f"### ❓ {role.capitalize()}")

            if timestamp:
                lines.append(f"**Time:** {timestamp}")

            lines.append("")
            lines.append(text)
            lines.append("")

        return "\n".join(lines)

    async def export_conversation_as_html(self, conversation_id: str) -> Optional[str]:
        """Export a conversation as formatted HTML.

        Args:
            conversation_id: The conversation identifier.

        Returns:
            HTML string or None if not found.
        """
        await self._ensure_loaded()
        if conversation_id not in self._data:
            return None

        conv_data = self._data[conversation_id]
        metadata = ConversationMetadata.from_dict(conv_data.get("metadata", {}))
        messages = conv_data.get("messages", [])

        html_parts = [
            "<!DOCTYPE html>",
            "<html lang=\"en\">",
            "<head>",
            f"  <meta charset=\"UTF-8\">",
            f"  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
            f"  <title>{metadata.name}</title>",
            "  <style>",
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }",
            "    .container { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            "    h1 { color: #333; border-bottom: 2px solid #007ba7; padding-bottom: 10px; }",
            "    .meta { color: #666; font-size: 0.9em; margin-bottom: 20px; }",
            "    .message { margin-bottom: 20px; padding: 15px; border-radius: 8px; }",
            "    .user { background: #e3f2fd; }",
            "    .assistant { background: #f3e5f5; }",
            "    .system { background: #fff3e0; }",
            "    .role { font-weight: bold; margin-bottom: 5px; }",
            "    .timestamp { color: #999; font-size: 0.8em; }",
            "    .content { white-space: pre-wrap; }",
            "    .tags { margin-top: 20px; }",
            "    .tag { background: #007ba7; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-right: 5px; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <div class=\"container\">",
            f"    <h1>{metadata.name}</h1>",
            f"    <div class=\"meta\">",
            f"      <p>Conversation ID: {conversation_id}</p>",
            f"      <p>Created: {metadata.created_at}</p>",
            f"      <p>Updated: {metadata.updated_at}</p>",
            f"      <p>Messages: {metadata.message_count}</p>",
            "    </div>",
            "    <hr>",
        ]

        for msg in messages:
            role = msg.get("type", "unknown")
            text = msg.get("text", "")
            timestamp = msg.get("timestamp", "")

            html_parts.extend([
                f'    <div class="message {role}">',
                f'      <div class="role">{role.capitalize()}</div>',
            ])

            if timestamp:
                html_parts.append(f'      <div class="timestamp">{timestamp}</div>')

            html_parts.extend([
                '      <div class="content">',
                f"        {text}",
                "      </div>",
                "    </div>",
            ])

        if metadata.tags:
            html_parts.append('    <div class="tags">')
            for tag in metadata.tags:
                html_parts.append(f'      <span class="tag">{tag}</span>')
            html_parts.append("    </div>")

        html_parts.extend([
            "  </div>",
            "</body>",
            "</html>",
        ])

        return "\n".join(html_parts)

    async def share_conversation(
        self,
        conversation_id: str,
        format_type: str = "markdown",
    ) -> Optional[str]:
        """Share a conversation in the specified format.

        Args:
            conversation_id: The conversation identifier.
            format_type: Export format - 'markdown', 'html', or 'json'.

        Returns:
            Formatted string or None if not found.
        """
        if format_type == "markdown":
            return await self.export_conversation_as_markdown(conversation_id)
        elif format_type == "html":
            return await self.export_conversation_as_html(conversation_id)
        elif format_type == "json":
            return await self.export_conversation(conversation_id)
        else:
            _LOGGER.error("Unknown share format: %s", format_type)
            return None
