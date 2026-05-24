# Changelog

All notable changes to AI Agent HA will be documented in this file.

## [Unreleased] - Enhancement Release

### Added

#### Enhancement #1: Prompt Compacting/Summarizing (#1)

- **New module: `prompt_compactor.py`**
  - `ConversationSummary` dataclass for storing conversation summaries
  - `PromptCompactor` class with token estimation and conversation compaction
  - AI-assisted summarization with configurable prompt template
  - Heuristic fallback when AI summarization fails

- **Updated `const.py`**
  - Added `CONF_PROMPT_COMPACTION_ENABLED`, `CONF_PROMPT_COMPACTION_THRESHOLD`
  - Added `DEFAULT_PROMPT_COMPACTION_ENABLED = True`
  - Added `DEFAULT_COMPACTION_THRESHOLD = 0.7`

- **Updated `config_flow.py`**
  - Added `async_step_prompt_compaction()` for UI configuration
  - Threshold slider: 50%-95% with 0.05 steps

- **Updated `agent.py`**
  - Added `_get_max_tokens_for_provider()` with provider-specific limits
  - Integrated compaction check in `_get_ai_response()`
  - Automatic triggering when tokens exceed threshold

- **Updated `__init__.py`**
  - Added `get_compaction_status` service for debugging

- **Updated `services.yaml`**
  - Added `get_compaction_status` service definition

- **Benefits**
  - Fixes context overflow errors (583846 tokens vs 262144 limit)
  - Automatic context window management
  - Configurable compaction threshold

#### Enhancement #2: Output Formatting (Markdown Rendering)

- **Updated `ai_agent_ha-panel.js`**
  - Added `marked.js` and `DOMPurify` CDN imports
  - `_hasMarkdown()` method for markdown detection
  - `_formatMarkdown()` method with GFM support
  - `_addCopyButtonsToCodeBlocks()` with copy-to-clipboard
  - `_renderMessageContent()` for formatted message rendering
  - CSS styles for headers, code blocks, lists, blockquotes, tables
  - Copy buttons for code blocks with "Copied!" feedback
  - XSS prevention via DOMPurify sanitization
  - Graceful degradation for plain text

- **Features**
  - Headers (h1-h3) with proper spacing
  - Code blocks with syntax highlighting
  - Inline code styling
  - Bold, italic, strikethrough
  - Ordered and unordered lists
  - Blockquotes with blue border
  - Tables with borders
  - Links styled and opening in new tab

#### Enhancement #3: Chat History Management

- **New module: `chat_history.py`**
  - `ConversationMetadata` dataclass with tags and pin support
  - `ChatHistoryManager` using HA storage
  - `save_conversation()`, `get_conversation()`, `delete_conversation()`
  - `rename_conversation()`, `export_conversation()`, `search_conversations()`
  - `clear_old_conversations()`, `pin_conversation()`, `add_tag()`

- **Updated `const.py`**
  - Added `CONF_CHAT_HISTORY_ENABLED`, `CONF_CHAT_HISTORY_MAX_CONVERSATIONS`
  - Added `CONF_CHAT_HISTORY_AUTO_CLEAR_DAYS`
  - Defaults: 50 max conversations, 30 day auto-clear

- **Updated `config_flow.py`**
  - Added `async_step_chat_history()` with configuration options
  - Auto-save toggle, max conversations (5-500), auto-clear days (1-365)

- **Updated `agent.py`**
  - Auto-save conversations after each successful query
  - Auto-generate conversation names from first user message

- **Updated `__init__.py`**
  - Added 8 new services:
    - `get_conversations`
    - `delete_conversation`
    - `rename_conversation`
    - `export_conversation`
    - `search_conversations`
    - `clear_old_conversations`
    - `pin_conversation`
    - `add_tag`

- **Updated `services.yaml`**
  - Added service definitions for all 8 new services

- **Features**
  - Full conversation storage with metadata
  - Search by content, tags, names
  - Export to JSON for backup
  - Pin important conversations
  - Tag conversations for organization
  - Auto-clear old conversations

#### Enhancement #4: Permission System

- **New module: `permissions.py`**
  - `PermissionRule` dataclass for allow/deny rules
  - `PermissionRequest` dataclass for user approval requests
  - `PermissionChecker` class with pattern matching
  - `check_action()` returns PERMIT, DENY, or PROMPT
  - `match_pattern()` supports wildcards (`light.*`, `*.lock`)
  - `_calculate_risk_level()` for automatic risk assessment
  - `approve_request()`, `deny_request()`, `get_pending_requests()`
  - Dangerous and high-risk service lists

- **Updated `const.py`**
  - Added `CONF_PERMISSION_MODE`, `CONF_PERMISSION_WHITELIST`
  - Added `CONF_PERMISSION_BLACKLIST`, `CONF_PERMISSION_TIMEOUT`
  - Defaults: mode="prompt", timeout=60 seconds

- **Updated `config_flow.py`**
  - Added `async_step_permission_options()` with configuration
  - Mode selector (prompt/auto_allow/auto_deny)
  - Timeout slider (10-300 seconds)

- **Updated `agent.py`**
  - Permission checking before all service calls
  - Returns `permission_request` response type for user approval
  - DENY actions are skipped with warning log
  - PROMPT actions return request with risk details

- **Updated `__init__.py`**
  - Added 3 new services:
    - `approve_permission`
    - `deny_permission`
    - `get_pending_permissions`

- **Updated `services.yaml`**
  - Added service definitions for permission management

- **Features**
  - Three permission modes (prompt/auto_allow/auto_deny)
  - Wildcard pattern matching
  - Automatic risk level calculation
  - Request expiration (configurable timeout)
  - Decision caching for similar actions
  - Audit logging of all permission checks

#### Enhancement #5: Multimedia Support

- **New module: `multimedia.py`**
  - `ImageAttachment` dataclass for image metadata
  - `MultimediaProcessor` class for image handling
  - `validate_image()` for MIME type and size checking
  - `compress_image()` using Pillow library
  - `encode_to_base64()` for transmission
  - `process_image_upload()` full pipeline
  - `format_multimodal_message()` for AI model compatibility
  - `get_supported_models()` returns vision model list

- **Updated `const.py`**
  - Added `CONF_MULTIMODAL_ENABLED`, `CONF_IMAGE_UPLOAD_ENABLED`
  - Added `CONF_MAX_IMAGE_SIZE`, `CONF_MAX_IMAGES_PER_MESSAGE`
  - Added `CONF_IMAGE_COMPRESSION_QUALITY`
  - Defaults: 5MB max, 3 images max, 80% quality

- **Updated `config_flow.py`**
  - Added `async_step_multimedia_options()` with configuration
  - Enable/disable toggles, size selector, quality slider

- **Updated `agent.py`**
  - Added `_build_messages_with_images()` for multimodal content
  - Added `_get_ai_response_with_images()` for vision model calls
  - `process_query()` accepts optional `images` parameter

- **Updated `__init__.py`**
  - Added `multimodal_query` service with image support

- **Updated `ai_agent_ha-panel.js`**
  - File input for image selection
  - Image attachment button in input footer
  - `_handleImageSelect()` for file processing
  - `_compressImage()` for client-side compression
  - `_renderAttachedImages()` for preview display
  - CSS styles for image previews and remove buttons
  - Remove image button for each attachment

- **Updated `services.yaml`**
  - Added `multimodal_query` service definition

- **Features**
  - Client-side image compression (2048px max)
  - Support for JPEG, PNG, WebP, GIF
  - Up to 3 images per message (configurable)
  - Base64 encoding for transmission
  - Integration with multimodal AI models

### Testing

- Created `tests/test_enhancements.py` with 179 tests
- All tests passing with 65 warnings (datetime deprecations)
- Test coverage:
  - Prompt Compacting: ~45 tests
  - Output Formatting: ~25 tests
  - Chat History: ~30 tests
  - Permission System: ~30 tests
  - Multimedia Support: ~40 tests
  - Integration Tests: ~9 tests

### Configuration UI

All enhancements are configurable via Home Assistant UI:
- Settings > Integrations > AI Agent HA > Configure
- New configuration steps added:
  - Chat History settings
  - Permission System settings
  - Multimedia settings
  - Prompt Compacting settings

### Files Modified

- `custom_components/ai_agent_ha/__init__.py` - Added new services and integration updates
- `custom_components/ai_agent_ha/agent.py` - Core agent enhancements
- `custom_components/ai_agent_ha/config_flow.py` - Configuration UI for all enhancements
- `custom_components/ai_agent_ha/const.py` - New configuration constants
- `custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js` - Frontend enhancements
- `custom_components/ai_agent_ha/manifest.json` - Updated dependencies
- `custom_components/ai_agent_ha/services.yaml` - New service definitions

### Files Added

- `custom_components/ai_agent_ha/prompt_compactor.py` - Prompt compaction module
- `custom_components/ai_agent_ha/chat_history.py` - Chat history management module
- `custom_components/ai_agent_ha/permissions.py` - Permission system module
- `custom_components/ai_agent_ha/multimedia.py` - Multimedia processing module
- `tests/test_ai_agent_ha/test_enhancements.py` - Integration tests
- `tests/test_ai_agent_ha/test_prompt_compactor.py` - Prompt compactor tests
- `tests/test_prompt_compactor_standalone.py` - Standalone prompt compactor tests
