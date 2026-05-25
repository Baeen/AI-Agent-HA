"""Data size estimation and summarization for preventing context overflow.

This module provides utilities to:
1. Estimate the token size of data structures
2. Check if data exceeds context window limits
3. Generate summaries of large datasets
4. Provide filtering recommendations
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)


# --- Enums and Constants ---

class DataType(Enum):
    """Types of data that can be retrieved."""
    ENTITIES = "entities"
    AUTOMATIONS = "automations"
    SCRIPTS = "scripts"
    DASHBOARDS = "dashboards"
    SCENES = "scenes"
    ENTITY_REGISTRY = "entity_registry"
    DEVICE_REGISTRY = "device_registry"
    AREA_REGISTRY = "area_registry"
    HISTORY = "history"
    STATISTICS = "statistics"
    CALENDAR_EVENTS = "calendar_events"
    PERSON_DATA = "person_data"
    WEATHER_DATA = "weather_data"
    CONFIG_FILES = "config_files"
    GENERAL = "general"


class FilterCategory(Enum):
    """Categories for filtering data."""
    DOMAIN = "domain"  # e.g., light, switch, sensor
    AREA = "area"  # e.g., living room, kitchen
    AREA_ID = "area_id"  # e.g., area_123
    DEVICE_CLASS = "device_class"  # e.g., temperature, humidity
    INTEGRATION = "integration"  # e.g., mqtt, zigbee
    STATE = "state"  # e.g., on, off, active
    ENTITY_ID_PATTERN = "entity_id_pattern"  # e.g., light.*
    ENTITY_ID_LIST = "entity_id_list"  # e.g., ["light.1", "light.2"]
    CUSTOM = "custom"  # Custom filter function


@dataclass
class ContextLimits:
    """Context window limits for different AI providers."""
    # Conservative estimates (in tokens)
    llama_cpp_small: int = 262144  # 256K - for small models like llama.cpp
    llama_cpp_medium: int = 524288  # 512K - for medium models
    llama_cpp_large: int = 1310720  # 1.3M - for large models
    openai_gpt4: int = 128000  # 128K
    gemini_flash: int = 1048576  # 1M
    anthropic_claude: int = 200000  # 200K
    openrouter_variable: int = 524288  # 512K - conservative default
    
    # Safe usage threshold (percentage of context to use)
    safe_usage_threshold: float = 0.7  # 70% of context window


@dataclass
class DataSizeInfo:
    """Information about the size of retrieved data."""
    raw_text_size: int = 0  # Raw text size in bytes
    estimated_tokens: int = 0  # Estimated token count
    item_count: int = 0  # Number of items/records
    data_type: DataType = DataType.GENERAL
    exceeds_limit: bool = False
    limit_threshold: int = 0
    overflow_amount: int = 0
    is_safe: bool = True
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary."""
        return {
            "raw_text_size_bytes": self.raw_text_size,
            "estimated_tokens": self.estimated_tokens,
            "item_count": self.item_count,
            "data_type": self.data_type.value,
            "exceeds_limit": self.exceeds_limit,
            "limit_threshold": self.limit_threshold,
            "overflow_tokens": self.overflow_amount,
            "is_safe": self.is_safe,
            "usage_percentage": (self.estimated_tokens / self.limit_threshold * 100) if self.limit_threshold > 0 else 0,
        }


@dataclass
class DataSummary:
    """A summary of large dataset."""
    data_type: DataType
    total_count: int
    summary_text: str
    top_items: List[Dict[str, Any]] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    filtering_suggestions: List[Dict[str, str]] = field(default_factory=list)
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary."""
        return {
            "data_type": self.data_type.value,
            "total_count": self.total_count,
            "summary_text": self.summary_text,
            "top_items": self.top_items[:10],  # Limit to first 10 items
            "statistics": self.statistics,
            "filtering_suggestions": self.filtering_suggestions,
        }


# --- Token Estimation ---

def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string.
    
    This is a rough estimation based on:
    - Average English word length: 4.7 characters
    - Average tokens per word: ~1.3 tokens per word (including whitespace, punctuation)
    - For JSON: each key-value pair adds overhead
    
    Returns approximate token count.
    """
    if not text:
        return 0
    
    # Remove excess whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Count words (rough approximation)
    words = len(text.split())
    
    # Rough estimation: 1.3 tokens per word
    estimated_tokens = int(words * 1.3)
    
    # Add overhead for JSON structure
    if text.startswith('{') or text.startswith('['):
        estimated_tokens += text.count(',') + text.count(':') * 2
    
    return max(estimated_tokens, len(text) // 4)  # At least 1 token per 4 chars


def estimate_data_size(data: Any) -> Tuple[int, int]:
    """Estimate the size of data in bytes and tokens.
    
    Returns:
        Tuple of (byte_size, estimated_tokens)
    """
    if data is None:
        return 0, 0
    
    # Convert to JSON string
    try:
        json_str = json.dumps(data, default=str, ensure_ascii=False)
        byte_size = len(json_str.encode('utf-8'))
        token_estimate = estimate_tokens(json_str)
        return byte_size, token_estimate
    except (TypeError, ValueError) as e:
        _LOGGER.warning("Failed to estimate data size: %s", str(e))
        # Fallback estimation
        str_repr = str(data)
        return len(str_repr.encode('utf-8')), len(str_repr.split())


# --- Data Size Info Calculation ---

def calculate_data_size_info(
    data: Any,
    data_type: DataType,
    context_limits: Optional[ContextLimits] = None,
    custom_limit: Optional[int] = None
) -> DataSizeInfo:
    """Calculate comprehensive size information for retrieved data.
    
    Args:
        data: The data to analyze
        data_type: Type of data being analyzed
        context_limits: Context limits configuration
        custom_limit: Custom token limit (overrides context_limits)
    
    Returns:
        DataSizeInfo object with size information
    """
    if context_limits is None:
        context_limits = ContextLimits()
    
    byte_size, token_estimate = estimate_data_size(data)
    
    # Determine the limit to use
    if custom_limit is not None:
        limit = custom_limit
    else:
        # Use the smallest reasonable limit as conservative estimate
        limit = min(
            context_limits.llama_cpp_small,
            context_limits.openai_gpt4,
            context_limits.anthropic_claude,
        )
    
    # Calculate safe threshold (70% of limit)
    safe_threshold = int(limit * context_limits.safe_usage_threshold)
    
    # Determine if data exceeds limits
    exceeds_limit = token_estimate > safe_threshold
    is_safe = token_estimate <= safe_threshold
    
    info = DataSizeInfo(
        raw_text_size=byte_size,
        estimated_tokens=token_estimate,
        item_count=_count_items(data),
        data_type=data_type,
        exceeds_limit=exceeds_limit,
        limit_threshold=safe_threshold,
        overflow_amount=max(0, token_estimate - safe_threshold),
        is_safe=is_safe,
    )
    
    return info


def _count_items(data: Any) -> int:
    """Count the number of items in data structure."""
    if isinstance(data, list):
        return len(data)
    elif isinstance(data, dict):
        # Count leaf items
        count = 0
        for value in data.values():
            if isinstance(value, (list, dict)):
                count += _count_items(value)
            else:
                count += 1
        return count
    return 1


# --- Data Summarization ---

def generate_data_summary(
    data: Any,
    data_type: DataType,
    max_items_for_summary: int = 5,
    include_statistics: bool = True
) -> DataSummary:
    """Generate a summary of large dataset.
    
    Args:
        data: The data to summarize
        data_type: Type of data
        max_items_for_summary: Maximum items to include in summary preview
        include_statistics: Whether to include statistical information
    
    Returns:
        DataSummary object with summary information
    """
    if isinstance(data, list):
        return _summarize_list(data, data_type, max_items_for_summary, include_statistics)
    elif isinstance(data, dict):
        return _summarize_dict(data, data_type, max_items_for_summary, include_statistics)
    else:
        return DataSummary(
            data_type=data_type,
            total_count=1,
            summary_text=f"Single item of type {type(data).__name__}",
        )


def _summarize_list(
    data: List,
    data_type: DataType,
    max_items: int,
    include_stats: bool
) -> DataSummary:
    """Summarize a list of items."""
    total_count = len(data)
    
    # Build summary text
    summary_parts = [
        f"Data contains {total_count} items of type '{data_type.value}'.",
    ]
    
    # Generate statistics if requested
    statistics = {}
    if include_stats and data:
        statistics = _calculate_statistics(data, data_type)
        if statistics:
            summary_parts.append(f"Statistics: {json.dumps(statistics, default=str)}")
    
    # Get top items for preview
    top_items = data[:max_items]
    if total_count > max_items:
        summary_parts.append(f"Showing first {max_items} of {total_count} items.")
    
    # Generate filtering suggestions
    suggestions = _generate_filtering_suggestions(data, data_type)
    if suggestions:
        summary_parts.append(f"Filtering options: {'; '.join(s['description'] for s in suggestions[:5])}")
    
    summary_text = " ".join(summary_parts)
    
    return DataSummary(
        data_type=data_type,
        total_count=total_count,
        summary_text=summary_text,
        top_items=top_items,
        statistics=statistics,
        filtering_suggestions=suggestions,
    )


def _summarize_dict(
    data: Dict,
    data_type: DataType,
    max_items: int,
    include_stats: bool
) -> DataSummary:
    """Summarize a dictionary of items."""
    total_count = len(data)
    
    summary_parts = [
        f"Data contains {total_count} keys/entries.",
    ]
    
    # Get top keys for preview
    top_keys = list(data.keys())[:max_items]
    if total_count > max_items:
        summary_parts.append(f"Showing first {max_items} keys: {', '.join(str(k) for k in top_keys)}...")
    else:
        summary_parts.append(f"Keys: {', '.join(str(k) for k in top_keys)}")
    
    suggestions = _generate_filtering_suggestions_for_dict(data)
    if suggestions:
        summary_parts.append(f"Filtering options: {'; '.join(s['description'] for s in suggestions[:3])}")
    
    summary_text = " ".join(summary_parts)
    
    return DataSummary(
        data_type=data_type,
        total_count=total_count,
        summary_text=summary_text,
        top_items=[{k: data[k] for k in top_keys if k in data}],
        filtering_suggestions=suggestions,
    )


def _calculate_statistics(data: List, data_type: DataType) -> Dict[str, Any]:
    """Calculate basic statistics for a list of items."""
    if not data:
        return {}
    
    stats = {"count": len(data)}
    
    # Try to analyze first item for common fields
    first_item = data[0]
    if isinstance(first_item, dict):
        # Count items with specific attributes
        domain_counts = {}
        area_counts = {}
        state_counts = {}
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            # Count by domain
            domain = item.get("domain") or item.get("entity_id", "").split(".")[0] if isinstance(item.get("entity_id"), str) else None
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
            
            # Count by area
            area = item.get("area_name") or item.get("area_id")
            if area:
                area_counts[area] = area_counts.get(area, 0) + 1
            
            # Count by state
            state = item.get("state")
            if state:
                state_counts[state] = state_counts.get(state, 0) + 1
        
        if domain_counts:
            stats["by_domain"] = dict(sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        if area_counts:
            stats["by_area"] = dict(sorted(area_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        if state_counts:
            stats["by_state"] = dict(sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    
    elif isinstance(data[0], str):
        stats["sample"] = data[:5]
    
    return stats


def _generate_filtering_suggestions(
    data: List,
    data_type: DataType
) -> List[Dict[str, str]]:
    """Generate filtering suggestions based on data structure."""
    suggestions = []
    
    if not data or not isinstance(data[0], dict):
        return suggestions
    
    first_item = data[0]
    
    # Suggest domain filtering if entities are present
    if "domain" in first_item or "entity_id" in first_item:
        domains = set()
        for item in data:
            if isinstance(item, dict):
                domain = item.get("domain")
                if domain:
                    domains.add(domain)
                entity_id = item.get("entity_id")
                if entity_id and "." in entity_id:
                    domains.add(entity_id.split(".")[0])
        
        if domains:
            suggestions.append({
                "type": FilterCategory.DOMAIN.value,
                "description": f"Filter by domain (available: {', '.join(sorted(domains)[:10])})",
            })
    
    # Suggest area filtering if area info is present
    if "area_name" in first_item or "area_id" in first_item:
        suggestions.append({
            "type": FilterCategory.AREA.value,
            "description": "Filter by area/room",
        })
    
    # Suggest device_class filtering if present
    if "device_class" in first_item:
        suggestions.append({
            "type": FilterCategory.DEVICE_CLASS.value,
            "description": "Filter by device class",
        })
    
    # Suggest entity_id pattern filtering
    suggestions.append({
        "type": FilterCategory.ENTITY_ID_PATTERN.value,
        "description": "Filter by entity ID pattern (e.g., 'light.*')",
    })
    
    return suggestions


def _generate_filtering_suggestions_for_dict(data: Dict) -> List[Dict[str, str]]:
    """Generate filtering suggestions for dictionary data."""
    suggestions = []
    top_keys = list(data.keys())[:10]
    
    # Suggest specific key access
    for key in top_keys[:5]:
        suggestions.append({
            "type": FilterCategory.ENTITY_ID_LIST.value,
            "description": f"Access specific key: '{key}'",
        })
    
    return suggestions


# --- Context Overflow Prevention ---

def check_and_handle_large_data(
    data: Any,
    data_type: DataType,
    context_limits: Optional[ContextLimits] = None,
    custom_limit: Optional[int] = None
) -> Dict[str, Any]:
    """Check if data exceeds context limits and generate appropriate response.
    
    This is the main entry point for preventing context overflow.
    
    Args:
        data: The data to check
        data_type: Type of data
        context_limits: Context limits configuration
        custom_limit: Custom token limit
    
    Returns:
        Dictionary with:
        - "is_safe": bool
        - "size_info": DataSizeInfo dict
        - "summary": DataSummary dict (if data is large)
        - "message": User-facing message
        - "filtering_suggestions": List of filtering options
    """
    size_info = calculate_data_size_info(data, data_type, context_limits, custom_limit)
    
    result = {
        "is_safe": size_info.is_safe,
        "size_info": size_info.to_summary_dict(),
    }
    
    if size_info.is_safe:
        result["message"] = "Data size is within safe limits."
        return result
    
    # Data exceeds limits - generate summary
    summary = generate_data_summary(data, data_type)
    result["summary"] = summary.to_summary_dict()
    result["message"] = _generate_overflow_message(size_info, summary)
    result["filtering_suggestions"] = summary.filtering_suggestions
    
    return result


def _generate_overflow_message(size_info: DataSizeInfo, summary: DataSummary) -> str:
    """Generate a user-friendly message for oversized data."""
    message_parts = [
        f"The requested data is too large to process ({size_info.estimated_tokens} tokens estimated, "
        f"safe limit is {size_info.limit_threshold} tokens).",
        f"\n\nHere's a summary of the data:",
        f"\n{summary.summary_text}",
    ]
    
    if summary.filtering_suggestions:
        message_parts.append("\n\nTo get specific data, you can filter by:")
        for suggestion in summary.filtering_suggestions[:5]:
            message_parts.append(f"  - {suggestion['description']}")
    
    return "".join(message_parts)


# --- Filtering Helpers ---

def apply_filter_to_data(
    data: Any,
    filter_category: FilterCategory,
    filter_value: Any
) -> Any:
    """Apply a filter to a dataset.
    
    Args:
        data: The data to filter (list or dict)
        filter_category: Type of filter to apply
        filter_value: Value to filter by
    
    Returns:
        Filtered data
    """
    if isinstance(data, list):
        return _filter_list(data, filter_category, filter_value)
    elif isinstance(data, dict):
        return _filter_dict(data, filter_category, filter_value)
    return data


def _filter_list(data: List, filter_category: FilterCategory, filter_value: Any) -> List:
    """Filter a list based on category and value."""
    filtered = []
    
    for item in data:
        if not isinstance(item, dict):
            continue
        
        match = False
        
        if filter_category == FilterCategory.DOMAIN:
            domain = item.get("domain") or item.get("entity_id", "").split(".")[0] if isinstance(item.get("entity_id"), str) else None
            match = domain == filter_value
            
        elif filter_category == FilterCategory.AREA:
            match = item.get("area_name") == filter_value
            
        elif filter_category == FilterCategory.AREA_ID:
            match = item.get("area_id") == filter_value
            
        elif filter_category == FilterCategory.DEVICE_CLASS:
            match = item.get("device_class") == filter_value
            
        elif filter_category == FilterCategory.INTEGRATION:
            match = item.get("integration") == filter_value
            
        elif filter_category == FilterCategory.STATE:
            match = item.get("state") == filter_value
            
        elif filter_category == FilterCategory.ENTITY_ID_PATTERN:
            entity_id = item.get("entity_id", "")
            match = _match_pattern(entity_id, filter_value)
            
        elif filter_category == FilterCategory.ENTITY_ID_LIST:
            entity_id = item.get("entity_id", "")
            match = entity_id in filter_value
        
        if match:
            filtered.append(item)
    
    return filtered


def _filter_dict(data: Dict, filter_category: FilterCategory, filter_value: Any) -> Dict:
    """Filter a dictionary based on category and value."""
    if filter_category == FilterCategory.ENTITY_ID_LIST:
        # Return only specified keys
        return {k: data[k] for k in filter_value if k in data}
    
    # For other filters, return subset based on keys
    filtered = {}
    for key, value in data.items():
        if filter_category == FilterCategory.DOMAIN and "." in key:
            domain = key.split(".")[0]
            if domain == filter_value:
                filtered[key] = value
        elif filter_category == FilterCategory.ENTITY_ID_PATTERN:
            if _match_pattern(key, filter_value):
                filtered[key] = value
    
    return filtered


def _match_pattern(entity_id: str, pattern: str) -> bool:
    """Match an entity ID against a pattern with wildcard support.
    
    Examples:
        light.* matches light.living_room
        *.lock matches front_door.lock
        sensor.* matches sensor.temperature
    """
    if not pattern or not entity_id:
        return False
    
    # Convert wildcard pattern to regex
    regex_pattern = pattern.replace(".", r"\.").replace("*", ".")
    regex_pattern = f"^{regex_pattern}$"
    
    try:
        return bool(re.match(regex_pattern, entity_id))
    except re.error:
        return entity_id == pattern


# --- Agent Integration Helpers ---

def get_filtering_command_suggestions(data_type: DataType) -> List[str]:
    """Get suggested commands for filtering data."""
    suggestions = []
    
    if data_type in (DataType.AUTOMATIONS, DataType.ENTITIES, DataType.SCENES):
        suggestions.extend([
            "get_entities_by_domain(domain='light')",
            "get_entities_by_area(area_id='area_123')",
            "get_entities_by_device_class(device_class='temperature')",
        ])
    
    if data_type == DataType.DASHBOARDS:
        suggestions.append("get_dashboard_config(dashboard_url='path/to/dashboard')")
    
    if data_type == DataType.HISTORY:
        suggestions.extend([
            "get_history(entity_id='sensor.temperature', hours=1)",
        ])
    
    return suggestions


def build_context_aware_response(
    original_query: str,
    data_result: Dict[str, Any],
    data_type: DataType
) -> str:
    """Build a context-aware response for the AI agent.
    
    This helps the agent understand how to proceed when data is too large.
    
    Args:
        original_query: The user's original query
        data_result: Result from check_and_handle_large_data()
        data_type: Type of data that was retrieved
    
    Returns:
        Formatted response string for the AI agent
    """
    if data_result.get("is_safe", True):
        return f"Data is within safe limits for processing."
    
    size_info = data_result.get("size_info", {})
    summary = data_result.get("summary", {})
    
    response_parts = [
        f"Data size warning: The requested data exceeds safe context limits.",
        f"Estimated tokens: {size_info.get('estimated_tokens', 'unknown')}, "
        f"Safe threshold: {size_info.get('limit_threshold', 'unknown')}.",
        f"\n\nData summary: {summary.get('summary_text', 'No summary available')}.",
    ]
    
    # Add filtering suggestions
    suggestions = data_result.get("filtering_suggestions", [])
    if suggestions:
        response_parts.append("\n\nRecommended filtering options:")
        for suggestion in suggestions[:5]:
            response_parts.append(f"- {suggestion.get('description', 'N/A')}")
    
    # Add command suggestions
    command_suggestions = get_filtering_command_suggestions(data_type)
    if command_suggestions:
        response_parts.append("\n\nYou can request filtered data using:")
        for cmd in command_suggestions[:3]:
            response_parts.append(f"- {cmd}")
    
    return "\n".join(response_parts)


# --- Data Size Context Manager ---

@dataclass
class DataSizeContextManager:
    """Manages data size checking and context overflow prevention.
    
    This class provides a high-level interface for checking data sizes,
    generating summaries, and applying filters to prevent context overflow.
    """
    
    max_context_tokens: int = 262144  # 256K default
    enable_data_size_checking: bool = True
    enable_summarization: bool = True
    safe_usage_threshold: float = 0.7  # 70%
    
    def __post_init__(self):
        """Initialize after dataclass creation."""
        self.context_limits = ContextLimits(
            safe_usage_threshold=self.safe_usage_threshold
        )
        self._data_size_history: List[Dict[str, Any]] = []
    
    def check_data_size(
        self,
        data: Any,
        data_type: DataType,
        custom_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Check if data size is within safe limits.
        
        Args:
            data: The data to check
            data_type: Type of data
            custom_limit: Optional custom token limit
            
        Returns:
            Dictionary with size information and recommendations
        """
        if not self.enable_data_size_checking:
            return {
                "is_safe": True,
                "size_info": {},
                "message": "Data size checking is disabled.",
            }
        
        result = check_and_handle_large_data(
            data,
            data_type,
            self.context_limits,
            custom_limit
        )
        
        # Log the size check
        self._log_size_check(data_type, result)
        
        return result
    
    def apply_filter(
        self,
        data: Any,
        filter_category: FilterCategory,
        filter_value: Any
    ) -> Any:
        """Apply a filter to data.
        
        Args:
            data: The data to filter
            filter_category: Type of filter
            filter_value: Value to filter by
            
        Returns:
            Filtered data
        """
        return apply_filter_to_data(data, filter_category, filter_value)
    
    def get_summary(
        self,
        data: Any,
        data_type: DataType
    ) -> Optional[Dict[str, Any]]:
        """Get a summary of data if it's too large.
        
        Args:
            data: The data to summarize
            data_type: Type of data
            
        Returns:
            Summary dictionary if data is large, None if safe
        """
        result = self.check_data_size(data, data_type)
        
        if result.get("is_safe", True):
            return None
        
        return result.get("summary")
    
    def build_agent_response(
        self,
        data: Any,
        data_type: DataType,
        original_query: str
    ) -> str:
        """Build a context-aware response for the AI agent.
        
        This helps the agent understand how to proceed when data is too large.
        
        Args:
            data: The retrieved data
            data_type: Type of data
            original_query: User's original query
            
        Returns:
            Formatted response string for the AI agent
        """
        result = self.check_data_size(data, data_type)
        
        if result.get("is_safe", True):
            return build_context_aware_response(
                original_query,
                result,
                data_type
            )
        
        # Data is too large - include summary in response
        summary = result.get("summary", {})
        size_info = result.get("size_info", {})
        
        response_parts = [
            build_context_aware_response(original_query, result, data_type),
            f"\n\nDATA SUMMARY:",
            f"Total items: {summary.get('total_count', 'unknown')}",
            f"Estimated tokens: {size_info.get('estimated_tokens', 'unknown')}",
        ]
        
        if summary.get("filtering_suggestions"):
            response_parts.append("\nRECOMMENDED FILTERS:")
            for suggestion in summary["filtering_suggestions"][:5]:
                response_parts.append(f"- {suggestion.get('description', 'N/A')}")
        
        return "\n".join(response_parts)
    
    def _log_size_check(
        self,
        data_type: DataType,
        result: Dict[str, Any]
    ):
        """Log a data size check for monitoring."""
        size_info = result.get("size_info", {})
        _LOGGER.debug(
            "Data size check: type=%s, tokens=%s, safe=%s, item_count=%s",
            data_type.value,
            size_info.get("estimated_tokens", "unknown"),
            result.get("is_safe", False),
            size_info.get("item_count", 0),
        )
        
        # Maintain history (last 100 entries)
        self._data_size_history.append({
            "data_type": data_type.value,
            "is_safe": result.get("is_safe", False),
            "tokens": size_info.get("estimated_tokens", 0),
            "timestamp": time.time() if 'time' in dir() else 0,
        })
        
        if len(self._data_size_history) > 100:
            self._data_size_history = self._data_size_history[-100:]
    
    def get_size_statistics(self) -> Dict[str, Any]:
        """Get statistics about recent data size checks."""
        if not self._data_size_history:
            return {
                "total_checks": 0,
                "overflows_detected": 0,
                "safe_requests": 0,
            }
        
        total = len(self._data_size_history)
        overflows = sum(1 for x in self._data_size_history if not x.get("is_safe", True))
        
        return {
            "total_checks": total,
            "overflows_detected": overflows,
            "safe_requests": total - overflows,
            "overflow_rate": round(overflows / total * 100, 2) if total > 0 else 0,
        }
