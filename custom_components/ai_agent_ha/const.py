"""Constants for the AI Agent HA integration."""

DOMAIN = "ai_agent_ha"
CONF_API_KEY = "api_key"
CONF_WEATHER_ENTITY = "weather_entity"

# AI Provider configuration keys
CONF_LLAMA_TOKEN = "llama_token"  # nosec B105
CONF_OPENAI_TOKEN = "openai_token"  # nosec B105
CONF_OPENAI_BASE_URL = (
    "openai_base_url"  # nosec B105 - configuration key, not a credential
)
CONF_GEMINI_TOKEN = "gemini_token"  # nosec B105
CONF_OPENROUTER_TOKEN = "openrouter_token"  # nosec B105
CONF_ANTHROPIC_TOKEN = "anthropic_token"  # nosec B105
CONF_ALTER_TOKEN = "alter_token"  # nosec B105
CONF_ZAI_TOKEN = "zai_token"  # nosec B105
CONF_LOCAL_OLLAMA_URL = "local_ollama_url"
CONF_LOCAL_OLLAMA_MODEL = "local_ollama_model"
CONF_OPENAI_COMPATIBLE_URL = "openai_compatible_url"
CONF_LOCAL_URL = "local_url"  # legacy alias for local_ollama_url

# Available AI providers
AI_PROVIDERS = [
    "llama",
    "openai",
    "gemini",
    "openrouter",
    "anthropic",
    "alter",
    "zai",
    "local_ollama",
    "openai_compatible",
]

# AI Provider constants
CONF_MODELS = "models"

# Supported AI providers
DEFAULT_AI_PROVIDER = "openai"

# YAML Review settings
YAML_REVIEW_ENABLED = True
YAML_REVIEW_REQUIRE_APPROVAL = False
# HA Documentation settings
HA_DOCS_ENABLED = True
HA_DOCS_EMBEDDED = True

# Prompt Compaction settings
CONF_PROMPT_COMPACTION_ENABLED = "prompt_compaction_enabled"
CONF_PROMPT_COMPACTION_THRESHOLD = "compaction_threshold"
CONF_PROMPT_COMPACTION_MAX_TOKENS = "compaction_max_tokens"

DEFAULT_PROMPT_COMPACTION_ENABLED = True
DEFAULT_COMPACTION_THRESHOLD = 0.7

# Chat History settings
CONF_CHAT_HISTORY_ENABLED = "chat_history_enabled"
CONF_CHAT_HISTORY_MAX_CONVERSATIONS = "max_conversations"
CONF_CHAT_HISTORY_AUTO_CLEAR_DAYS = "auto_clear_days"
DEFAULT_CHAT_HISTORY_ENABLED = True
DEFAULT_MAX_CONVERSATIONS = 50
DEFAULT_AUTO_CLEAR_DAYS = 30

# Permission System settings
CONF_PERMISSION_MODE = "permission_mode"
CONF_PERMISSION_WHITELIST = "permission_whitelist"
CONF_PERMISSION_BLACKLIST = "permission_blacklist"
CONF_PERMISSION_TIMEOUT = "permission_timeout"
CONF_PERMISSION_AUTO_ALLOW = "permission_auto_allow"
CONF_PERMISSION_AUTO_DENY = "permission_auto_deny"

# Default permission mode
DEFAULT_PERMISSION_MODE = "prompt"
DEFAULT_PERMISSION_TIMEOUT = 60

# Multimedia settings
CONF_MULTIMODAL_ENABLED = "multimodal_enabled"
CONF_IMAGE_UPLOAD_ENABLED = "image_upload_enabled"
CONF_MAX_IMAGE_SIZE = "max_image_size"  # in bytes (5MB default)
CONF_MAX_IMAGES_PER_MESSAGE = "max_images_per_message"
CONF_IMAGE_COMPRESSION_QUALITY = "image_compression_quality"  # 1-100

# Default values
DEFAULT_MULTIMODAL_ENABLED = True
DEFAULT_IMAGE_UPLOAD_ENABLED = True
DEFAULT_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
DEFAULT_MAX_IMAGES_PER_MESSAGE = 3
DEFAULT_IMAGE_COMPRESSION_QUALITY = 80

# Supported image types
SUPPORTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]
SUPPORTED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".gif"]
