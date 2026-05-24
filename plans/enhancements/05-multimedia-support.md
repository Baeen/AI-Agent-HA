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