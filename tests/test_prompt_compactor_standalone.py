"""Standalone tests for the prompt compactor module.

These tests are designed to run without Home Assistant dependencies.
"""

import sys
import os
import pytest
from datetime import datetime

# Add the project root to the path so we can import the module directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'ai_agent_ha'))

from prompt_compactor import (
    ConversationSummary,
    PromptCompactor,
    DEFAULT_COMPACTION_PROMPT,
)


@pytest.fixture
def compactor():
    """Create a PromptCompactor instance for testing."""
    return PromptCompactor(threshold_pct=0.7, keep_last=5)


@pytest.fixture
def sample_messages():
    """Create sample conversation messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful Home Assistant assistant."},
        {"role": "user", "content": "Turn on the living room lights."},
        {"role": "assistant", "content": "I'll turn on the living room lights now."},
        {"role": "user", "content": "What's the temperature outside?"},
        {"role": "assistant", "content": "The current temperature is 72°F."},
        {"role": "user", "content": "Set the thermostat to 72 degrees."},
        {"role": "assistant", "content": "Thermostat set to 72 degrees."},
        {"role": "user", "content": "Lock all the doors."},
        {"role": "assistant", "content": "All doors have been locked."},
        {"role": "user", "content": "Play music in the living room."},
        {"role": "assistant", "content": "Playing music in the living room."},
    ]


class TestConstants:
    """Test cases for module constants."""

    def test_default_compaction_prompt_exists(self):
        """Test that default compaction prompt is defined."""
        assert DEFAULT_COMPACTION_PROMPT is not None
        assert len(DEFAULT_COMPACTION_PROMPT) > 0
        assert "Key user requests" in DEFAULT_COMPACTION_PROMPT

    def test_default_compaction_prompt_focused_on_relevant_topics(self):
        """Test that default compaction prompt focuses on relevant topics."""
        assert "user requests" in DEFAULT_COMPACTION_PROMPT.lower()
        assert "smart home" in DEFAULT_COMPACTION_PROMPT.lower()
        assert "entities" in DEFAULT_COMPACTION_PROMPT.lower()


class TestConversationSummary:
    """Test cases for ConversationSummary dataclass."""

    def test_creation_with_all_fields(self):
        """Test creating a ConversationSummary with all fields."""
        summary = ConversationSummary(
            summary_text="Test summary",
            original_message_count=5,
            original_token_count=100,
            summary_token_count=20,
            created_at="2024-01-01T00:00:00",
            first_message_index=0,
            last_message_index=4,
        )
        assert summary.summary_text == "Test summary"
        assert summary.original_message_count == 5
        assert summary.original_token_count == 100
        assert summary.summary_token_count == 20
        assert summary.created_at == "2024-01-01T00:00:00"
        assert summary.first_message_index == 0
        assert summary.last_message_index == 4

    def test_creation_with_defaults(self):
        """Test creating a ConversationSummary with default values."""
        summary = ConversationSummary(summary_text="Test")
        assert summary.summary_text == "Test"
        assert summary.original_message_count == 0
        assert summary.original_token_count == 0
        assert summary.summary_token_count == 0
        assert summary.created_at != ""
        assert summary.first_message_index == 0
        assert summary.last_message_index == 0

    def test_post_init_sets_created_at(self):
        """Test that __post_init__ sets created_at if not provided."""
        summary = ConversationSummary(summary_text="Test")
        assert summary.created_at != ""
        # Verify it's a valid ISO format timestamp
        try:
            datetime.fromisoformat(summary.created_at)
        except ValueError:
            pytest.fail("created_at is not a valid ISO format timestamp")

    def test_to_dict(self):
        """Test serialization to dictionary."""
        summary = ConversationSummary(
            summary_text="Test summary",
            original_message_count=5,
            original_token_count=100,
            summary_token_count=20,
            created_at="2024-01-01T00:00:00",
            first_message_index=0,
            last_message_index=4,
        )
        data = summary.to_dict()
        assert data["summary_text"] == "Test summary"
        assert data["original_message_count"] == 5
        assert data["original_token_count"] == 100
        assert data["summary_token_count"] == 20
        assert data["created_at"] == "2024-01-01T00:00:00"
        assert data["first_message_index"] == 0
        assert data["last_message_index"] == 4

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "summary_text": "Test summary",
            "original_message_count": 5,
            "original_token_count": 100,
            "summary_token_count": 20,
            "created_at": "2024-01-01T00:00:00",
            "first_message_index": 0,
            "last_message_index": 4,
        }
        summary = ConversationSummary.from_dict(data)
        assert summary.summary_text == "Test summary"
        assert summary.original_message_count == 5
        assert summary.original_token_count == 100
        assert summary.summary_token_count == 20
        assert summary.created_at == "2024-01-01T00:00:00"
        assert summary.first_message_index == 0
        assert summary.last_message_index == 4

    def test_roundtrip_serialization(self):
        """Test that serialization and deserialization roundtrip works."""
        original = ConversationSummary(
            summary_text="Test summary",
            original_message_count=10,
            original_token_count=200,
            summary_token_count=50,
            created_at="2024-01-01T00:00:00",
            first_message_index=0,
            last_message_index=9,
        )
        data = original.to_dict()
        restored = ConversationSummary.from_dict(data)
        assert restored.summary_text == original.summary_text
        assert restored.original_message_count == original.original_message_count
        assert restored.original_token_count == original.original_token_count


class TestEstimateTokens:
    """Test cases for token estimation."""

    def test_estimate_tokens_with_english_text(self, compactor):
        """Test estimating tokens for English text."""
        # ~4 chars per token heuristic for English
        text = "The quick brown fox jumps over the lazy dog."
        estimated = compactor.estimate_tokens(text)
        expected = len(text) // 4
        assert estimated == expected

    def test_estimate_tokens_with_long_text(self, compactor):
        """Test estimating tokens for longer text."""
        text = "Hello world, this is a test of token estimation. " * 10
        estimated = compactor.estimate_tokens(text)
        assert estimated > 0
        assert estimated == len(text) // 4

    def test_estimate_tokens_empty_string(self, compactor):
        """Test estimating tokens for empty string."""
        assert compactor.estimate_tokens("") == 0

    def test_estimate_tokens_single_character(self, compactor):
        """Test estimating tokens for single character (minimum is 1)."""
        assert compactor.estimate_tokens("a") == 1

    def test_estimate_tokens_whitespace(self, compactor):
        """Test estimating tokens for whitespace."""
        assert compactor.estimate_tokens("    ") == 1  # 4 spaces = 1 token

    def test_estimate_messages_tokens(self, compactor):
        """Test estimating tokens for a list of messages."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        total_tokens = compactor.estimate_messages_tokens(messages)
        assert total_tokens > 0

    def test_estimate_messages_tokens_empty(self, compactor):
        """Test estimating tokens for empty message list."""
        assert compactor.estimate_messages_tokens([]) == 0

    def test_estimate_messages_tokens_with_multimodal_content(self, compactor):
        """Test estimating tokens with multimodal content arrays."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "image", "image": "data"},
                ],
            },
        ]
        total_tokens = compactor.estimate_messages_tokens(messages)
        # Should only count text content
        assert total_tokens > 0


class TestShouldCompact:
    """Test cases for should_compact method."""

    def test_should_compact_returns_true_when_over_threshold(self, compactor):
        """Test that compaction is triggered when over threshold."""
        # 70% of 10000 = 7000, current is 8000
        assert compactor.should_compact(8000, 10000, 0.7) is True

    def test_should_compact_returns_false_when_under_threshold(self, compactor):
        """Test that compaction is not triggered when under threshold."""
        # 70% of 10000 = 7000, current is 5000
        assert compactor.should_compact(5000, 10000, 0.7) is False

    def test_should_compact_at_exact_threshold(self, compactor):
        """Test behavior at exact threshold boundary."""
        # 70% of 10000 = 7000, current is exactly 7000
        assert compactor.should_compact(7000, 10000, 0.7) is False  # not > threshold

    def test_should_compact_disabled(self):
        """Test that compaction returns False when disabled."""
        compactor = PromptCompactor(enabled=False)
        assert compactor.should_compact(999999, 10000, 0.7) is False

    def test_should_compact_custom_threshold(self, compactor):
        """Test with custom threshold."""
        # 90% of 10000 = 9000
        assert compactor.should_compact(8500, 10000, 0.9) is False
        assert compactor.should_compact(9500, 10000, 0.9) is True

    def test_should_compact_strict_threshold(self, compactor):
        """Test with strict threshold (95%)."""
        assert compactor.should_compact(9400, 10000, 0.94) is False
        assert compactor.should_compact(9500, 10000, 0.95) is False
        assert compactor.should_compact(9600, 10000, 0.95) is True


class TestExtractSystemPrompt:
    """Test cases for extract_system_prompt method."""

    def test_extract_system_prompt_exists(self, compactor):
        """Test extracting existing system prompt."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        system_prompt = compactor.extract_system_prompt(messages)
        assert system_prompt is not None
        assert system_prompt["role"] == "system"

    def test_extract_system_prompt_not_exists(self, compactor):
        """Test when no system prompt exists."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        system_prompt = compactor.extract_system_prompt(messages)
        assert system_prompt is None

    def test_extract_system_prompt_is_first_message(self, compactor):
        """Test that system prompt is identified as first message."""
        messages = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User message"},
        ]
        system_prompt = compactor.extract_system_prompt(messages)
        assert system_prompt is messages[0]

    def test_extract_system_prompt_from_sample_messages(self, compactor, sample_messages):
        """Test extracting system prompt from sample messages."""
        system_prompt = compactor.extract_system_prompt(sample_messages)
        assert system_prompt is not None
        assert "Home Assistant" in system_prompt["content"]


class TestHeuristicSummary:
    """Test cases for heuristic summary generation."""

    def test_generate_heuristic_summary_extract_user_queries(self, compactor):
        """Test that user queries are extracted in heuristic summary."""
        messages = [
            {"role": "user", "content": "Turn on the lights"},
            {"role": "assistant", "content": "Done"},
            {"role": "user", "content": "What's the weather?"},
        ]
        summary = compactor._generate_heuristic_summary(messages)
        assert "User asked about" in summary.summary_text

    def test_generate_heuristic_summary_extract_entities(self, compactor):
        """Test that Home Assistant entities are extracted."""
        messages = [
            {"role": "user", "content": "Turn on light.living_room"},
            {"role": "assistant", "content": "Done"},
            {"role": "user", "content": "Check sensor.temperature_1"},
        ]
        summary = compactor._generate_heuristic_summary(messages)
        assert "Entities discussed" in summary.summary_text
        assert "light.living_room" in summary.summary_text

    def test_generate_heuristic_summary_extract_actions(self, compactor):
        """Test that action keywords are extracted."""
        messages = [
            {"role": "user", "content": "Turn on the light"},
            {"role": "user", "content": "Lock the door"},
        ]
        summary = compactor._generate_heuristic_summary(messages)
        assert "Actions discussed" in summary.summary_text
        # The regex matches "turn" and "on" separately, and "lock"
        assert "turn" in summary.summary_text.lower() or "lock" in summary.summary_text.lower()

    def test_generate_heuristic_summary_empty_messages(self, compactor):
        """Test heuristic summary with empty messages."""
        summary = compactor._generate_heuristic_summary([])
        assert summary.summary_text != ""
        assert summary.original_message_count == 0

    def test_generate_heuristic_summary_token_counts(self, compactor):
        """Test that token counts are properly set."""
        messages = [
            {"role": "user", "content": "Test query with some content"},
        ]
        summary = compactor._generate_heuristic_summary(messages)
        assert summary.original_message_count == 1
        assert summary.original_token_count > 0
        assert summary.summary_token_count > 0


class TestCompactConversation:
    """Test cases for compact_conversation method."""

    @pytest.mark.asyncio
    async def test_no_compaction_needed_for_small_messages(self, compactor):
        """Test that messages are returned unchanged when no compaction needed."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        # Small message list, large max_tokens - no compaction needed
        compacted, summary = await compactor.compact_conversation(messages, 100000)
        assert compacted == messages
        assert summary is None

    @pytest.mark.asyncio
    async def test_empty_messages(self, compactor):
        """Test handling empty message list."""
        compacted, summary = await compactor.compact_conversation([], 10000)
        assert compacted == []
        assert summary is None

    @pytest.mark.asyncio
    async def test_single_message(self, compactor):
        """Test handling single message."""
        messages = [{"role": "system", "content": "Single message"}]
        compacted, summary = await compactor.compact_conversation(messages, 10000)
        assert compacted == messages
        assert summary is None

    @pytest.mark.asyncio
    async def test_compaction_reduces_token_count(self, compactor):
        """Test that compaction actually reduces token count."""
        messages = [{"role": "system", "content": "System"}]
        # Add many messages with content
        for i in range(30):
            messages.append({"role": "user", "content": f"Query {i}: " + "x" * 100})
            messages.append({"role": "assistant", "content": f"Response {i}: " + "y" * 50})

        original_tokens = compactor.estimate_messages_tokens(messages)
        compacted, summary = await compactor.compact_conversation(messages, 500)

        compacted_tokens = compactor.estimate_messages_tokens(compacted)
        assert compacted_tokens < original_tokens


class TestCompactionStats:
    """Test cases for compaction statistics."""

    def test_get_compaction_stats_empty(self, compactor):
        """Test stats when no compactions have occurred."""
        stats = compactor.get_compaction_stats()
        assert stats["total_compactions"] == 0
        assert stats["total_original_tokens"] == 0
        assert stats["total_summary_tokens"] == 0
        assert stats["compression_ratio"] == 0
        assert stats["summaries"] == []

    def test_get_compaction_stats_after_adding_summary(self, compactor):
        """Test stats after manually adding a summary."""
        summary = ConversationSummary(
            summary_text="Test summary",
            original_message_count=10,
            original_token_count=1000,
            summary_token_count=100,
        )
        compactor._summaries.append(summary)

        stats = compactor.get_compaction_stats()
        assert stats["total_compactions"] == 1
        assert stats["total_original_tokens"] == 1000
        assert stats["total_summary_tokens"] == 100
        assert abs(stats["compression_ratio"] - 0.1) < 0.01

    def test_get_compaction_stats_multiple_summaries(self, compactor):
        """Test stats with multiple summaries."""
        for i in range(3):
            summary = ConversationSummary(
                summary_text=f"Summary {i}",
                original_message_count=5,
                original_token_count=500,
                summary_token_count=50,
            )
            compactor._summaries.append(summary)

        stats = compactor.get_compaction_stats()
        assert stats["total_compactions"] == 3
        assert stats["total_original_tokens"] == 1500
        assert stats["total_summary_tokens"] == 150


class TestPromptCompactorInitialization:
    """Test cases for PromptCompactor initialization."""

    def test_default_initialization(self):
        """Test default initialization values."""
        compactor = PromptCompactor()
        assert compactor.threshold_pct == 0.70
        assert compactor.keep_last == 5
        assert compactor.enabled is True
        assert compactor.compaction_prompt == DEFAULT_COMPACTION_PROMPT
        assert compactor._summaries == []

    def test_custom_initialization(self):
        """Test initialization with custom values."""
        custom_prompt = "Custom prompt for summarization."
        compactor = PromptCompactor(
            threshold_pct=0.85,
            keep_last=10,
            compaction_prompt=custom_prompt,
            enabled=False,
        )
        assert compactor.threshold_pct == 0.85
        assert compactor.keep_last == 10
        assert compactor.compaction_prompt == custom_prompt
        assert compactor.enabled is False

    def test_boundary_threshold_values(self):
        """Test boundary threshold values."""
        compactor_low = PromptCompactor(threshold_pct=0.0)
        assert compactor_low.threshold_pct == 0.0

        compactor_high = PromptCompactor(threshold_pct=1.0)
        assert compactor_high.threshold_pct == 1.0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_very_long_content(self, compactor):
        """Test handling of very long content."""
        long_content = "x" * 10000
        messages = [{"role": "user", "content": long_content}]
        tokens = compactor.estimate_messages_tokens(messages)
        assert tokens > 0

    def test_unicode_content(self, compactor):
        """Test handling of unicode content."""
        unicode_content = "Hello 世界 🌍 مرحبا"
        messages = [{"role": "user", "content": unicode_content}]
        tokens = compactor.estimate_messages_tokens(messages)
        assert tokens > 0

    def test_mixed_content_types(self, compactor):
        """Test handling of mixed content types."""
        messages = [
            {"role": "user", "content": "String content"},
            {"role": "assistant", "content": ["text", "with", "multiple", "parts"]},
        ]
        tokens = compactor.estimate_messages_tokens(messages)
        assert tokens > 0

    def test_null_content(self, compactor):
        """Test handling of null content."""
        messages = [{"role": "user", "content": None}]
        tokens = compactor.estimate_messages_tokens(messages)
        # Should handle gracefully
        assert tokens >= 0
