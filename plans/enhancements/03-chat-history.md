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
