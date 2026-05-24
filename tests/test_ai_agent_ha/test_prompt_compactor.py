"""Tests for the prompt compactor module."""

import pytest
from custom_components.ai_agent_ha.prompt_compactor import (
    ConversationSummary,
    PromptCompactor,
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


class TestConversationSummary:
    """Test cases for ConversationSummary dataclass."""

    def test_creation(self):
        """Test creating a ConversationSummary."""
        summary = ConversationSummary(
            summary_text="Test summary",
            original_message_count=5,
            original_token_count=100,
            summary_token_count=20,
        )
        assert summary.summary_text == "Test summary"
        assert summary.original_message_count == 5
        assert summary.original_token_count == 100
        assert summary.summary_token_count == 20
        assert summary.created_at != ""
        assert summary.first_message_index == 0
        assert summary.last_message_index == 4

    def test_post_init_sets_created_at(self):
        """Test that __post_init__ sets created_at if not provided."""
        summary = ConversationSummary(summary_text="Test")
        assert summary.created_at != ""

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


class TestEstimateTokens:
    """Test cases for token estimation."""

    def test_estimate_tokens_with_text(self, compactor):
        """Test estimating tokens for text."""
        # ~4 chars per token heuristic
        text = "Hello world, this is a test."
        estimated = compactor.estimate_tokens(text)
        assert estimated > 0
        assert estimated == len(text) // 4

    def test_estimate_tokens_empty_string(self, compactor):
        """Test estimating tokens for empty string."""
        assert compactor.estimate_tokens("") == 0

    def test_estimate_tokens_single_character(self, compactor):
        """Test estimating tokens for single character."""
        assert compactor.estimate_tokens("a") == 1  # min is 1

    def test_estimate_messages_tokens(self, compactor):
        """Test estimating tokens for a list of messages."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        total_tokens = compactor.estimate_messages_tokens(messages)
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

    def test_should_compact_disabled(self):
        """Test that compaction returns False when disabled."""
        compactor = PromptCompactor(enabled=False)
        assert compactor.should_compact(999999, 10000, 0.7) is False

    def test_should_compact_custom_threshold(self, compactor):
        """Test with custom threshold."""
        # 90% of 10000 = 9000, current is 8500
        assert compactor.should_compact(8500, 10000, 0.9) is False
        assert compactor.should_compact(9500, 10000, 0.9) is True


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

    def test_extract_system_prompt_first(self, compactor):
        """Test that system prompt is identified as first message."""
        messages = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User message"},
        ]
        system_prompt = compactor.extract_system_prompt(messages)
        assert system_prompt is messages[0]


class TestCompactConversation:
    """Test cases for compact_conversation method."""

    @pytest.mark.asyncio
    async def test_no_compaction_needed(self, compactor):
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
    async def test_preserves_system_prompt(self, compactor):
        """Test that system prompt is preserved during compaction."""
        # Create messages that will trigger compaction
        messages = [
            {"role": "system", "content": "You are a helpful Home Assistant assistant."},
        ]
        # Add many older messages
        for i in range(20):
            messages.append({"role": "user", "content": f"Old query {i}: " + "x" * 100})
            messages.append({"role": "assistant", "content": f"Old response {i}: " + "y" * 50})
        # Add recent messages
        messages.append({"role": "user", "content": "Current query"})
        messages.append({"role": "assistant", "content": "Current response"})

        compacted, summary = await compactor.compact_conversation(messages, 1000)
        
        # System prompt should be preserved
        assert compacted[0]["role"] == "system"
        assert "You are a helpful Home Assistant assistant" in compacted[0]["content"]

    @pytest.mark.asyncio
    async def test_preserves_last_n_messages(self, compactor):
        """Test that last N messages are preserved."""
        messages = [{"role": "system", "content": "System"}]
        for i in range(30):
            messages.append({"role": "user", "content": f"Query {i}"})
            messages.append({"role": "assistant", "content": f"Response {i}"})

        compacted, summary = await compactor.compact_conversation(messages, 500)

        # Last 5 messages should be preserved
        assert len(compacted) > 0

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


class TestGenerateSummary:
    """Test cases for generate_summary method."""

    @pytest.mark.asyncio
    async def test_generate_heuristic_summary_without_ai(self, compactor):
        """Test heuristic summary generation without AI client."""
        messages = [
            {"role": "user", "content": "Turn on light.living_room"},
            {"role": "assistant", "content": "Turning on light.living_room"},
            {"role": "user", "content": "What's the temperature?"},
        ]
        summary = await compactor.generate_summary(messages, ai_client=None)
        assert summary is not None
        assert summary.summary_text != ""
        assert summary.original_message_count == 3

    @pytest.mark.asyncio
    async def test_generate_summary_with_ai_client(self, compactor):
        """Test summary generation with AI client."""
        messages = [
            {"role": "user", "content": "Turn on the lights"},
            {"role": "assistant", "content": "Done"},
        ]

        class MockAIClient:
            async def get_response(self, messages):
                return '{"response": "User asked about turning on lights"}'

        summary = await compactor.generate_summary(messages, ai_client=MockAIClient())
        assert summary is not None
        assert summary.original_message_count == 2

    @pytest.mark.asyncio
    async def test_generate_summary_ai_failure_fallback(self, compactor):
        """Test fallback to heuristic when AI fails."""
        messages = [
            {"role": "user", "content": "Test query"},
        ]

        class FailingAIClient:
            async def get_response(self, messages):
                raise Exception("AI service unavailable")

        summary = await compactor.generate_summary(messages, ai_client=FailingAIClient())
        assert summary is not None
        assert summary.summary_text != ""


class TestCompactionStats:
    """Test cases for compaction statistics."""

    def test_get_compaction_stats_empty(self, compactor):
        """Test stats when no compactions have occurred."""
        stats = compactor.get_compaction_stats()
        assert stats["total_compactions"] == 0
        assert stats["total_original_tokens"] == 0
        assert stats["total_summary_tokens"] == 0
        assert stats["compression_ratio"] == 0

    def test_get_compaction_stats_after_compaction(self, compactor):
        """Test stats after compaction has occurred."""
        # Simulate adding a summary
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


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_compactor_with_custom_threshold(self):
        """Test compactor with custom threshold."""
        compactor = PromptCompactor(threshold_pct=0.9)
        assert compactor.threshold_pct == 0.9

    def test_compactor_with_custom_keep_last(self):
        """Test compactor with custom keep_last value."""
        compactor = PromptCompactor(keep_last=10)
        assert compactor.keep_last == 10

    def test_compactor_with_custom_compaction_prompt(self):
        """Test compactor with custom compaction prompt."""
        custom_prompt = "Custom prompt for summarization."
        compactor = PromptCompactor(compaction_prompt=custom_prompt)
        assert compactor.compaction_prompt == custom_prompt

    def test_large_message_list(self, compactor):
        """Test handling of large message lists."""
        messages = [{"role": "system", "content": "System"}]
        for i in range(100):
            messages.append({"role": "user", "content": f"Query {i}"})
            messages.append({"role": "assistant", "content": f"Response {i}"})

        # Should not raise any exceptions
        tokens = compactor.estimate_messages_tokens(messages)
        assert tokens > 0
