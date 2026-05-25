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

# Input Validation settings
CONF_MAX_QUERY_LENGTH = "max_query_length"
CONF_ENABLE_INJECTION_DETECTION = "enable_injection_detection"

DEFAULT_MAX_QUERY_LENGTH = 4096
DEFAULT_ENABLE_INJECTION_DETECTION = True

# Response Validation settings
CONF_RESPONSE_VALIDATION_ENABLED = "response_validation_enabled"
CONF_RESPONSE_VALIDATION_STRICT_MODE = "response_validation_strict_mode"

DEFAULT_RESPONSE_VALIDATION_ENABLED = True
DEFAULT_RESPONSE_VALIDATION_STRICT_MODE = False

# Error Recovery settings
CONF_MAX_RETRIES = "max_retries"
CONF_RETRY_DELAY = "retry_delay"
CONF_CIRCUIT_FAILURE_THRESHOLD = "circuit_failure_threshold"
CONF_CIRCUIT_TIMEOUT = "circuit_timeout"
CONF_FAILOVER_ENABLED = "failover_enabled"
CONF_FAILOVER_PROVIDERS = "failover_providers"
CONF_FALLBACK_RESPONSE = "fallback_response"

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_CIRCUIT_FAILURE_THRESHOLD = 5
DEFAULT_CIRCUIT_TIMEOUT = 60.0
DEFAULT_FAILOVER_ENABLED = True

# Action Execution settings
CONF_ACTION_REQUIRE_CONFIRMATION = "action_require_confirmation"
CONF_ACTION_ENABLE_SIMULATION = "action_enable_simulation"
CONF_ACTION_ENABLE_ROLLBACK = "action_enable_rollback"

DEFAULT_ACTION_REQUIRE_CONFIRMATION = True
DEFAULT_ACTION_ENABLE_SIMULATION = True
DEFAULT_ACTION_ENABLE_ROLLBACK = True

# Audit Log settings
CONF_AUDIT_LOG_ENABLED = "audit_log_enabled"
CONF_AUDIT_LOG_RETENTION_DAYS = "audit_log_retention_days"
CONF_AUDIT_LOG_MAX_ENTRIES = "audit_log_max_entries"
CONF_AUDIT_LOG_PERSISTENCE_ENABLED = "audit_log_persistence_enabled"

# Default audit log settings
DEFAULT_AUDIT_LOG_ENABLED = True
DEFAULT_AUDIT_LOG_RETENTION_DAYS = 90
DEFAULT_AUDIT_LOG_MAX_ENTRIES = 10000
DEFAULT_AUDIT_LOG_PERSISTENCE_ENABLED = True

# Voice interaction configuration
CONF_VOICE_ENABLED = "voice_enabled"
CONF_VOICE_TTS_ENABLED = "voice_tts_enabled"
CONF_VOICE_TTS_ENGINE = "voice_tts_engine"
CONF_VOICE_TTS_VOICE = "voice_tts_voice"

# Automation Testing/Simulation Mode (A3) configuration
CONF_SIMULATION_MODE_ENABLED = "simulation_mode_enabled"
CONF_SIMULATION_DANGEROUS_ACTION_BLOCKING = "simulation_dangerous_action_blocking"
CONF_SIMULATION_REQUIRE_APPROVAL = "simulation_require_approval"
CONF_SIMULATION_LOG_LEVEL = "simulation_log_level"

# Default values for simulation mode
DEFAULT_SIMULATION_MODE_ENABLED = True
DEFAULT_SIMULATION_DANGEROUS_ACTION_BLOCKING = True
DEFAULT_SIMULATION_REQUIRE_APPROVAL = True
DEFAULT_SIMULATION_LOG_LEVEL = "info"

# Default voice settings
DEFAULT_VOICE_ENABLED = True
DEFAULT_VOICE_TTS_ENABLED = True

# Data Size Management and Context Overflow Prevention
CONF_MAX_CONTEXT_TOKENS = "max_context_tokens"
CONF_ENABLE_DATA_SIZE_CHECKING = "enable_data_size_checking"
CONF_DATA_SUMMARIZATION_ENABLED = "data_summarization_enabled"
CONF_CONTEXT_SAFE_USAGE_THRESHOLD = "context_safe_usage_threshold"

# Default values for data size management
DEFAULT_MAX_CONTEXT_TOKENS = 262144  # 256K - conservative default for llama.cpp
DEFAULT_ENABLE_DATA_SIZE_CHECKING = True
DEFAULT_DATA_SUMMARIZATION_ENABLED = True
DEFAULT_CONTEXT_SAFE_USAGE_THRESHOLD = 0.7  # 70% of context window
