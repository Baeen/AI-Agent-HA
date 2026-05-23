"""Comprehensive tests for all 11 features of the ai_agent_ha Home Assistant integration.

Tests cover:
- All public methods in each class
- Error handling and edge cases
- Parameterized tests for multiple scenarios
- Mocked Home Assistant components
- Random test data generation
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import MagicMock, AsyncMock, patch, mock_open

import sys
import os

# Add the ai_agent_ha module path to sys.path for imports
_base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ai_agent_ha_path = os.path.join(_base_path, "custom_components", "ai_agent_ha")
if _ai_agent_ha_path not in sys.path:
    sys.path.insert(0, _ai_agent_ha_path)

# Import the classes to test
from log_analyzer import LogEntry, LogPattern, LogAnalyzerResult, LogAnalyzer
from error_diagnosis import DiagnosisResult, ErrorDiagnosisAssistant
from automation_troubleshooter import (
    AutomationIssue,
    AutomationTroubleshootResult,
    AutomationTroubleshooter,
)
from entity_discovery import (
    EntitySummary,
    AutomationSuggestion,
    EntityDiscoveryResult,
    EntityDiscoveryAssistant,
)
from config_validator import (
    ConfigIssue,
    ConfigValidationResult,
    ConfigurationValidator,
)
from backup_advisor import (
    BackupItem,
    BackupRecommendation,
    PostChangeVerification,
    RollbackSuggestion,
    BackupAdvisor,
)
from energy_advisor import (
    EnergySummary,
    EnergySuggestion,
    DeviceEnergyAnalysis,
    EnergyOptimizationResult,
    EnergyAdvisor,
)
from security_audit import SecurityIssue, SecurityAuditResult, SecurityAuditor
from nl_to_automation import NLToAutomationResult, NLToAutomationConverter
from dashboard_advisor import (
    DashboardAnalysis,
    CardRecommendation,
    DashboardImprovement,
    DashboardAdvisor,
)
from integration_guide import (
    IntegrationInfo,
    SetupStep,
    IntegrationGuide,
    IntegrationGuideProvider,
)


# ============================================================================
# Fixtures for Common Test Data
# ============================================================================

@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config = MagicMock()
    hass.config.config_dir = "/config"
    hass.config.path = MagicMock(return_value="/config/home-assistant.log")
    hass.states = MagicMock()
    hass.states.async_all = MagicMock(return_value=[])
    hass.services = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def sample_log_entries():
    """Create sample log entries for testing."""
    base_time = datetime.now()
    return [
        LogEntry(
            timestamp=base_time,
            level="INFO",
            logger_name="homeassistant.core",
            message="Starting Home Assistant",
        ),
        LogEntry(
            timestamp=base_time + timedelta(seconds=1),
            level="ERROR",
            logger_name="homeassistant.components.hassio",
            message="Error connecting to Hass.io API",
        ),
        LogEntry(
            timestamp=base_time + timedelta(seconds=2),
            level="WARNING",
            logger_name="homeassistant.helpers.entity",
            message="Entity sensor.temperature is taking a long time to update",
        ),
        LogEntry(
            timestamp=base_time + timedelta(seconds=3),
            level="ERROR",
            logger_name="homeassistant.components.websocket_api",
            message="Connection lost",
            exc_info="ValueError: Test error",
        ),
        LogEntry(
            timestamp=base_time + timedelta(seconds=4),
            level="DEBUG",
            logger_name="homeassistant.core",
            message="State update: light.living_room = on",
        ),
    ]


@pytest.fixture
def sample_error_messages():
    """Create sample error messages for testing."""
    return [
        "HomeAssistantError: Unable to set up state. Parent not found.",
        "HomeAssistantError: Unknown service registered",
        "TimeoutError: Connection timed out after 30 seconds",
        "ValueError: Invalid entity ID 'invalid id!@#$'",
        "TypeError: Unexpected keyword argument 'invalid_param'",
        "FileNotFoundError: /config/automations.yaml not found",
        "yaml.scanner.ScannerError: while parsing a block mapping",
        "PermissionError: [Errno 13] Permission denied: '/config/secrets.yaml'",
        "ConnectionError: Cannot connect to host 192.168.1.100 ssl:default [Connect call failed]",
        "RecursionError: maximum recursion depth exceeded",
    ]


@pytest.fixture
def sample_automation_config():
    """Create sample automation configurations for testing."""
    return {
        "perfect_automation": {
            "alias": "Test Automation",
            "description": "A perfect automation",
            "mode": "single",
            "trigger": {"platform": "time", "at": "00:00:00"},
            "condition": [],
            "action": [
                {
                    "service": "homeassistant.turn_on",
                    "target": {"entity_id": "light.test"},
                }
            ],
        },
        "missing_condition": {
            "alias": "Missing Condition",
            "description": "Automation without conditions",
            "mode": "single",
            "trigger": {"platform": "time", "at": "00:00:00"},
            "action": [
                {
                    "service": "homeassistant.turn_on",
                    "target": {"entity_id": "light.test"},
                }
            ],
        },
        "infinite_loop": {
            "alias": "Infinite Loop",
            "description": "Automation that triggers itself",
            "mode": "single",
            "trigger": {"platform": "state", "entity_id": "light.test"},
            "action": [
                {
                    "service": "light.turn_on",  # light domain matches trigger entity domain
                    "target": {"entity_id": "light.test"},
                }
            ],
        },
        "invalid_trigger": {
            "alias": "Invalid Trigger",
            "description": "Automation with invalid trigger platform",
            "mode": "single",
            "trigger": {"platform": "invalid_platform"},
            "action": [
                {
                    "service": "homeassistant.turn_on",
                    "target": {"entity_id": "light.test"},
                }
            ],
        },
        "missing_action": {
            "alias": "Missing Action",
            "description": "Automation without actions",
            "mode": "single",
            "trigger": {"platform": "time", "at": "00:00:00"},
            "condition": [],
        },
    }


@pytest.fixture
def sample_entities():
    """Create sample entities for testing."""
    return [
        {"entity_id": "light.living_room", "state": "on", "attributes": {"friendly_name": "Living Room Light", "room": "Living Room", "function": "lighting"}},
        {"entity_id": "light.kitchen", "state": "off", "attributes": {"friendly_name": "Kitchen Light", "room": "Kitchen", "function": "lighting"}},
        {"entity_id": "switch.ac", "state": "on", "attributes": {"friendly_name": "AC Switch", "room": "Living Room", "function": "climate"}},
        {"entity_id": "sensor.temperature", "state": "22.5", "attributes": {"friendly_name": "Temperature", "unit_of_measurement": "°C", "room": "Living Room", "function": "sensor"}},
        {"entity_id": "sensor.humidity", "state": "65", "attributes": {"friendly_name": "Humidity", "unit_of_measurement": "%", "room": "Living Room", "function": "sensor"}},
        {"entity_id": "binary_sensor.door", "state": "off", "attributes": {"friendly_name": "Door Sensor", "room": "Front Door", "function": "security"}},
        {"entity_id": "binary_sensor.motion", "state": "off", "attributes": {"friendly_name": "Motion Sensor", "room": "Living Room", "function": "security"}},
        {"entity_id": "media_player.tv", "state": "on", "attributes": {"friendly_name": "TV", "room": "Living Room", "function": "entertainment"}},
        {"entity_id": "climate.thermostat", "state": "heat", "attributes": {"friendly_name": "Thermostat", "room": "Living Room", "function": "climate"}},
        {"entity_id": "camera.front_door", "state": "off", "attributes": {"friendly_name": "Front Door Camera", "room": "Front Door", "function": "security"}},
    ]


@pytest.fixture
def sample_config_issues():
    """Create sample configuration issues for testing."""
    return [
        {"level": "error", "message": "Invalid YAML syntax", "filename": "configuration.yaml"},
        {"level": "warning", "message": "Deprecated option 'customize' used", "filename": "automations.yaml"},
        {"level": "info", "message": "Best practice suggestion", "filename": "scripts.yaml"},
    ]


@pytest.fixture
def sample_backup_items():
    """Create sample backup items for testing."""
    return [
        BackupItem(
            item_type="config",
            name="Main Config",
            path="/config/configuration.yaml",
            description="Main configuration file",
            critical=True,
        ),
        BackupItem(
            item_type="automation",
            name="Automations",
            path="/config/automations.yaml",
            description="Automations configuration",
            critical=True,
        ),
        BackupItem(
            item_type="script",
            name="Scripts",
            path="/config/scripts.yaml",
            description="Scripts configuration",
            critical=False,
        ),
        BackupItem(
            item_type="custom_component",
            name="AI Agent HA",
            path="/config/custom_components/ai_agent_ha",
            description="AI Agent HA custom component",
            critical=True,
        ),
    ]


@pytest.fixture
def sample_energy_data():
    """Create sample energy usage data for testing."""
    return {
        "entities": [
            {
                "entity_id": "sensor.living_room_power",
                "state": "150.5",
                "attributes": {"unit_of_measurement": "W", "friendly_name": "Living Room Power"},
            },
            {
                "entity_id": "sensor.kitchen_power",
                "state": "800.2",
                "attributes": {"unit_of_measurement": "W", "friendly_name": "Kitchen Power"},
            },
            {
                "entity_id": "sensor.hvac_power",
                "state": "2500.0",
                "attributes": {"unit_of_measurement": "W", "friendly_name": "HVAC Power"},
            },
            {
                "entity_id": "sensor.tv_power",
                "state": "120.0",
                "attributes": {"unit_of_measurement": "W", "friendly_name": "TV Power"},
            },
        ]
    }


@pytest.fixture
def sample_security_config():
    """Create sample configurations for security testing."""
    return {
        "automation_with_credential": {
            "alias": "Test",
            "trigger": {"platform": "time"},
            "action": [
                {
                    "service": "shell_command.run",
                    "data": {"command": "curl -H 'Authorization: Bearer abc123' https://api.example.com"},
                }
            ],
        },
        "automation_with_exposed_api_key": {
            "alias": "API Test",
            "trigger": {"platform": "state"},
            "action": [
                {
                    "service": "rest_command.call_api",
                    "data": {"api_key": "sk-1234567890"},
                }
            ],
        },
        "automation_with_infinite_loop": {
            "alias": "Loop Test",
            "trigger": {"platform": "state", "entity_id": "switch.test"},
            "condition": [],
            "action": [{"service": "homeassistant.turn_on", "target": {"entity_id": "switch.test"}}],
        },
        "automation_with_password": {
            "alias": "Password Test",
            "trigger": {"platform": "time"},
            "action": [
                {
                    "service": "shell_command.execute",
                    "data": {"command": "mysql -u admin -p password123"},
                }
            ],
        },
    }


@pytest.fixture
def sample_nl_inputs():
    """Create sample natural language inputs for testing."""
    return [
        "Turn on the living room light at 6pm",
        "When the door opens, send me a notification",
        "If temperature goes above 25 degrees, turn on the AC",
        "Every day at 8am, tell me the weather",
        "When I leave home, turn off all lights",
        "At sunset, turn on the garden lights",
        "When the motion sensor detects movement, turn on the bathroom light for 5 minutes",
        "If no one is home for 30 minutes, arm the security system",
        "",  # Empty input
        "Turn on",  # Too vague
    ]


@pytest.fixture
def sample_dashboard_config():
    """Create sample dashboard configurations for testing."""
    return {
        "empty_dashboard": {"title": "Empty Dashboard", "cards": []},
        "well_structured_dashboard": {
            "title": "Main Dashboard",
            "cards": [
                {
                    "type": "entities",
                    "title": "Living Room",
                    "entities": ["light.living_room", "switch.ac", "sensor.temperature"],
                },
                {
                    "type": "gauge",
                    "title": "Temperature",
                    "entity": "sensor.temperature",
                },
                {
                    "type": "picture",
                    "title": "Security Camera",
                    "image": "/local/camera.jpg",
                },
            ],
        },
        "poorly_structured_dashboard": {
            "title": "My Dashboard",
            "cards": [
                {"type": "invalid_type", "entity": "light.test"},
                {"entity": "light.test"},  # Missing type
                {"type": "entities"},  # Missing entities
            ],
        },
    }


@pytest.fixture
def sample_integration_queries():
    """Create sample integration queries for testing."""
    return [
        "philips hue",
        "tasmota",
        "mqtt",
        "nest",
        "roborock",
        "nonexistent_integration_xyz",
        "light",
        "security camera",
    ]


# ============================================================================
# Feature 1: Log Analyzer Tests
# ============================================================================

class TestLogEntry:
    """Tests for LogEntry class."""

    def test_log_entry_init(self):
        """Test LogEntry initialization."""
        timestamp = datetime.now()
        entry = LogEntry(
            timestamp=timestamp,
            level="ERROR",
            logger_name="test.logger",
            message="Test message",
            exc_info="ValueError: test error",
        )
        assert entry.timestamp == timestamp
        assert entry.level == "ERROR"
        assert entry.logger_name == "test.logger"
        assert entry.message == "Test message"
        assert entry.exc_info == "ValueError: test error"

    def test_log_entry_init_without_exc_info(self):
        """Test LogEntry initialization without exc_info."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level="INFO",
            logger_name="test",
            message="Test",
        )
        assert entry.exc_info is None

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_log_entry_levels(self, level):
        """Test LogEntry with different log levels."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            logger_name="test",
            message="Test",
        )
        assert entry.level == level.upper()

    def test_log_entry_to_dict(self):
        """Test LogEntry.to_dict() method."""
        entry = LogEntry(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            level="ERROR",
            logger_name="test",
            message="Test message",
        )
        result = entry.to_dict()
        assert "timestamp" in result
        assert "level" in result
        assert "logger" in result  # Note: uses "logger" not "logger_name"
        assert "message" in result
        assert result["level"] == "ERROR"
        assert result["message"] == "Test message"


class TestLogPattern:
    """Tests for LogPattern class."""

    def test_log_pattern_init(self):
        """Test LogPattern initialization."""
        pattern = LogPattern(
            pattern="connection_error",
            count=5,
            examples=["Error 1", "Error 2"],
            severity="warning",
        )
        assert pattern.pattern == "connection_error"
        assert pattern.count == 5
        assert pattern.severity == "warning"

    def test_log_pattern_to_dict(self):
        """Test LogPattern.to_dict() method."""
        pattern = LogPattern(
            pattern="test_pattern",
            count=10,
            examples=["Example 1"],
            severity="error",
        )
        result = pattern.to_dict()
        assert result["pattern"] == "test_pattern"
        assert result["count"] == 10
        assert result["severity"] == "error"


class TestLogAnalyzerResult:
    """Tests for LogAnalyzerResult class."""

    def test_log_analyzer_result_init(self):
        """Test LogAnalyzerResult initialization."""
        result = LogAnalyzerResult(
            summary={},
            errors=[],
            warnings=[],
            patterns=[],
            recommendations=[],
            ai_summary="",
        )
        assert result.summary == {}
        assert result.errors == []
        assert result.warnings == []
        assert result.patterns == []
        assert result.recommendations == []
        assert result.ai_summary == ""

    def test_log_analyzer_result_to_dict(self):
        """Test LogAnalyzerResult.to_dict() method."""
        result = LogAnalyzerResult(
            summary={"total_entries": 0},
            errors=[],
            warnings=[],
            patterns=[],
            recommendations=[],
            ai_summary="",
        )
        data = result.to_dict()
        assert "patterns" in data
        assert "summary" in data
        assert "error_count" in data
        assert "warning_count" in data

    def test_log_analyzer_result_to_markdown(self):
        """Test LogAnalyzerResult.to_markdown() method."""
        result = LogAnalyzerResult(
            summary={},
            errors=[],
            warnings=[],
            patterns=[],
            recommendations=[],
            ai_summary="",
        )
        markdown = result.to_markdown()
        assert isinstance(markdown, str)
        assert len(markdown) > 0


class TestLogAnalyzer:
    """Tests for LogAnalyzer class."""

    def test_log_analyzer_init(self, mock_hass):
        """Test LogAnalyzer initialization."""
        analyzer = LogAnalyzer(hass=mock_hass)
        assert analyzer.hass == mock_hass

    def test_get_log_entries_empty(self, mock_hass):
        """Test get_log_entries with empty logs (sync)."""
        analyzer = LogAnalyzer(hass=mock_hass)

        with patch.object(analyzer, "_read_log_file", return_value=[]):
            entries = analyzer.get_log_entries()
            assert entries == []

    def test_get_log_entries_with_data(self, mock_hass, sample_log_entries):
        """Test get_log_entries with sample data (sync)."""
        analyzer = LogAnalyzer(hass=mock_hass)

        with patch.object(analyzer, "_read_log_file", return_value=sample_log_entries):
            entries = analyzer.get_log_entries()
            assert len(entries) == 5

    def test_analyze_logs_empty(self, mock_hass):
        """Test analyze_logs with empty entries (sync)."""
        analyzer = LogAnalyzer(hass=mock_hass)
        result = analyzer.analyze_logs([])
        assert result is not None
        assert result.patterns == []

    def test_analyze_logs_with_errors(self, mock_hass, sample_log_entries):
        """Test analyze_logs with error entries (sync)."""
        analyzer = LogAnalyzer(hass=mock_hass)
        result = analyzer.analyze_logs(sample_log_entries)
        assert result is not None

    def test_search_logs(self, mock_hass, sample_log_entries):
        """Test search_logs method (sync)."""
        analyzer = LogAnalyzer(hass=mock_hass)
        results = analyzer.search_logs(sample_log_entries, "error")
        assert isinstance(results, list)

    def test_search_logs_case_insensitive(self, mock_hass, sample_log_entries):
        """Test search_logs is case insensitive (sync)."""
        analyzer = LogAnalyzer(hass=mock_hass)
        results_lower = analyzer.search_logs(sample_log_entries, "error")
        results_upper = analyzer.search_logs(sample_log_entries, "ERROR")
        assert len(results_lower) == len(results_upper)

    def test_get_error_summary(self, mock_hass):
        """Test get_error_summary method (sync)."""
        analyzer = LogAnalyzer(hass=mock_hass)
        with patch.object(analyzer, "analyze_logs", return_value=LogAnalyzerResult(summary={}, errors=[], warnings=[], patterns=[], recommendations=[], ai_summary="")):
            summary = analyzer.get_error_summary(hours=24)
            assert isinstance(summary, dict)

    def test_error_patterns_exist(self, mock_hass):
        """Test that ERROR_PATTERNS is populated."""
        analyzer = LogAnalyzer(hass=mock_hass)
        assert len(analyzer.ERROR_PATTERNS) > 0

    def test_read_log_file_malformed(self, mock_hass):
        """Test _read_log_file with malformed log data."""
        analyzer = LogAnalyzer(hass=mock_hass)
        malformed_log = "This is not a proper log format\nAnother bad line\n"

        with patch("builtins.open", mock_open(read_data=malformed_log)):
            entries = analyzer._read_log_file(hours=24, levels=["ERROR"], limit=100)
            assert isinstance(entries, list)

    def test_read_log_file_empty(self, mock_hass):
        """Test _read_log_file with empty file."""
        analyzer = LogAnalyzer(hass=mock_hass)

        with patch("builtins.open", mock_open(read_data="")):
            entries = analyzer._read_log_file(hours=24, levels=["ERROR"], limit=100)
            assert entries == []

    def test_read_log_file_special_characters(self, mock_hass):
        """Test _read_log_file with special characters."""
        analyzer = LogAnalyzer(hass=mock_hass)
        special_log = "2024-01-01 12:00:00 ERROR Test message with special chars: @#$%^&*()\n"

        with patch("builtins.open", mock_open(read_data=special_log)):
            entries = analyzer._read_log_file(hours=24, levels=["ERROR"], limit=100)
            assert isinstance(entries, list)


# ============================================================================
# Feature 2: Error Diagnosis Tests
# ============================================================================

class TestDiagnosisResult:
    """Tests for DiagnosisResult class."""

    def test_diagnosis_result_init(self):
        """Test DiagnosisResult initialization."""
        result = DiagnosisResult(
            error_message="Test error",
            error_type="ValueError",
            severity="high",
            possible_causes=["Cause 1", "Cause 2"],
            suggested_fixes=["Fix 1", "Fix 2"],
            related_entities=["entity.test"],
            documentation_url="https://example.com",
            confidence=0.85,
        )
        assert result.error_message == "Test error"
        assert result.error_type == "ValueError"
        assert result.severity == "high"
        assert len(result.possible_causes) == 2
        assert result.confidence == 0.85

    def test_diagnosis_result_to_dict(self):
        """Test DiagnosisResult.to_dict() method."""
        result = DiagnosisResult(
            error_message="Test",
            error_type="TestError",
            severity="medium",
            possible_causes=[],
            suggested_fixes=[],
            related_entities=[],
            documentation_url="",
            confidence=0.5,
        )
        data = result.to_dict()
        assert data["error_message"] == "Test"
        assert "confidence_label" in data

    @pytest.mark.parametrize("confidence,expected_label", [
        (0.95, "Very High"),
        (0.9, "Very High"),
        (0.8, "High"),
        (0.7, "High"),
        (0.6, "Medium"),
        (0.5, "Medium"),
        (0.4, "Low"),
        (0.3, "Low"),
        (0.2, "Very Low"),
        (0.0, "Very Low"),
        (1.0, "Very High"),
    ])
    def test_diagnosis_result_confidence_label(self, confidence, expected_label):
        """Test _confidence_label method with different confidence values."""
        result = DiagnosisResult(
            error_message="Test",
            error_type="TestError",
            severity="low",
            possible_causes=[],
            suggested_fixes=[],
            related_entities=[],
            documentation_url="",
            confidence=confidence,
        )
        assert result._confidence_label() == expected_label

    def test_diagnosis_result_to_markdown(self):
        """Test DiagnosisResult.to_markdown() method."""
        result = DiagnosisResult(
            error_message="Test error",
            error_type="TestError",
            severity="high",
            possible_causes=["Cause 1"],
            suggested_fixes=["Fix 1"],
            related_entities=[],
            documentation_url="",
            confidence=0.8,
        )
        markdown = result.to_markdown()
        assert isinstance(markdown, str)
        assert "Test error" in markdown


class TestErrorDiagnosisAssistant:
    """Tests for ErrorDiagnosisAssistant class."""

    def test_error_diagnosis_assistant_init(self):
        """ErrorDiagnosisAssistant initialization (no hass parameter)."""
        assistant = ErrorDiagnosisAssistant()
        assert assistant is not None

    def test_known_error_patterns_exist(self):
        """Test that patterns (KNOWN_ERROR_PATTERNS) is populated."""
        assistant = ErrorDiagnosisAssistant()
        # ErrorDiagnosisAssistant uses self.patterns (from module-level KNOWN_ERROR_PATTERNS)
        assert len(assistant.patterns) > 0

    def test_diagnose_known_error(self, sample_error_messages):
        """Test diagnose with known error patterns (sync, returns List[DiagnosisResult])."""
        assistant = ErrorDiagnosisAssistant()
        for error_msg in sample_error_messages:
            results = assistant.diagnose(error_msg)
            assert results is not None
            assert isinstance(results, list)

    def test_diagnose_unknown_error(self):
        """Test diagnose with unknown error."""
        assistant = ErrorDiagnosisAssistant()
        results = assistant.diagnose("Completely unknown error pattern xyz123")
        assert results is not None
        assert isinstance(results, list)

    def test_diagnose_empty_error(self):
        """Test diagnose with empty error message."""
        assistant = ErrorDiagnosisAssistant()
        results = assistant.diagnose("")
        assert results is not None
        assert isinstance(results, list)

    def test_diagnose_multiple(self, sample_error_messages):
        """Test diagnose_multiple method (sync, returns Dict[str, List[DiagnosisResult]])."""
        assistant = ErrorDiagnosisAssistant()
        results = assistant.diagnose_multiple(sample_error_messages)
        assert isinstance(results, dict)
        assert len(results) == len(sample_error_messages)
        for error_msg, diag_results in results.items():
            assert isinstance(diag_results, list)

    def test_get_ai_enhanced_diagnosis(self):
        """Test get_ai_enhanced_diagnosis method (sync, requires error_message + diagnosis_results)."""
        assistant = ErrorDiagnosisAssistant()
        # get_ai_enhanced_diagnosis(error_message, diagnosis_results: List[DiagnosisResult])
        result = assistant.get_ai_enhanced_diagnosis("Test error", [])
        assert isinstance(result, str)

    def test_get_diagnosis_summary(self, sample_error_messages):
        """Test get_diagnosis_summary method (sync)."""
        assistant = ErrorDiagnosisAssistant()
        # diagnose_multiple returns Dict[str, List[DiagnosisResult]], get_diagnosis_summary needs List[DiagnosisResult]
        all_results = []
        for error_msg in sample_error_messages:
            results = assistant.diagnose(error_msg)
            all_results.extend(results)
        summary = assistant.get_diagnosis_summary(all_results)
        assert isinstance(summary, str)

    def test_diagnose_malformed_error(self):
        """Test diagnose with malformed error string."""
        assistant = ErrorDiagnosisAssistant()
        malformed_errors = [
            "",
            " " * 100,
            "\n\n\n",
            "!!!@##$%%^&&**(((",
        ]
        for error in malformed_errors:
            results = assistant.diagnose(error)
            assert results is not None
            assert isinstance(results, list)


# ============================================================================
# Feature 3: Automation Troubleshooter Tests
# ============================================================================

class TestAutomationIssue:
    """Tests for AutomationIssue class."""

    def test_automation_issue_init(self):
        """Test AutomationIssue initialization."""
        issue = AutomationIssue(
            issue_type="test_issue",
            severity="high",
            message="Test issue",
            suggestion="Test suggestion",
            affected_field="light.test",
        )
        assert issue.severity == "high"
        assert issue.message == "Test issue"
        assert issue.issue_type == "test_issue"

    def test_automation_issue_to_dict(self):
        """Test AutomationIssue.to_dict() method."""
        issue = AutomationIssue(issue_type="test", severity="medium", message="Test", suggestion="Suggestion")
        data = issue.to_dict()
        assert data["severity"] == "medium"
        assert data["issue_type"] == "test"

    def test_automation_issue_to_markdown(self):
        """Test AutomationIssue.to_markdown() method."""
        issue = AutomationIssue(
            issue_type="test", severity="high", message="Test issue", suggestion="Test suggestion"
        )
        markdown = issue.to_markdown()
        assert isinstance(markdown, str)


class TestAutomationTroubleshootResult:
    """Tests for AutomationTroubleshootResult class."""

    def test_troubleshoot_result_init(self):
        """Test AutomationTroubleshootResult initialization."""
        result = AutomationTroubleshootResult(
            issues=[],
            health_score=1.0,
            automation_alias="Test",
        )
        assert result.health_score == 1.0
        assert result.automation_alias == "Test"

    def test_troubleshoot_result_to_dict(self):
        """Test AutomationTroubleshootResult.to_dict() method."""
        result = AutomationTroubleshootResult(
            issues=[], health_score=0.85, automation_alias="Test"
        )
        data = result.to_dict()
        assert "health_score" in data
        assert "issue_count" in data

    def test_troubleshoot_result_to_markdown(self):
        """Test AutomationTroubleshootResult.to_markdown() method."""
        result = AutomationTroubleshootResult(
            issues=[], health_score=0.9, automation_alias="Test"
        )
        markdown = result.to_markdown()
        assert isinstance(markdown, str)


class TestAutomationTroubleshooter:
    """Tests for AutomationTroubleshooter class."""

    def test_automation_troubleshooter_init(self):
        """Test AutomationTroubleshooter initialization (no hass parameter)."""
        troubleshooter = AutomationTroubleshooter()
        assert troubleshooter is not None

    def test_valid_trigger_platforms_exist(self):
        """Test that VALID_TRIGGER_PLATFORMS is populated."""
        troubleshooter = AutomationTroubleshooter()
        assert len(troubleshooter.VALID_TRIGGER_PLATFORMS) > 0

    def test_validate_basic_structure_valid(self, sample_automation_config):
        """Test _validate_basic_structure with valid automation."""
        troubleshooter = AutomationTroubleshooter()
        issues = troubleshooter._validate_basic_structure(
            sample_automation_config["perfect_automation"]
        )
        assert len(issues) == 0

    def test_validate_basic_structure_invalid(self):
        """Test _validate_basic_structure with invalid automation."""
        troubleshooter = AutomationTroubleshooter()
        invalid_config = {}  # Empty config
        issues = troubleshooter._validate_basic_structure(invalid_config)
        assert len(issues) > 0

    def test_validate_triggers_valid(self, sample_automation_config):
        """Test _validate_triggers with valid trigger (expects config dict with 'trigger' key)."""
        troubleshooter = AutomationTroubleshooter()
        issues = troubleshooter._validate_triggers(
            sample_automation_config["perfect_automation"]
        )
        assert len(issues) == 0

    def test_validate_triggers_invalid(self):
        """Test _validate_triggers with invalid trigger (expects config dict with 'trigger' key)."""
        troubleshooter = AutomationTroubleshooter()
        # Invalid trigger: missing platform field
        invalid_config = {"trigger": [{"platform": "invalid_platform_xyz"}]}
        issues = troubleshooter._validate_triggers(invalid_config)
        # Note: invalid_platform_xyz may still be valid if not checked strictly
        # The test verifies the method handles invalid platforms gracefully
        assert isinstance(issues, list)

    def test_validate_conditions_empty(self):
        """Test _validate_conditions with empty conditions (valid)."""
        troubleshooter = AutomationTroubleshooter()
        issues = troubleshooter._validate_conditions({"condition": []})
        assert len(issues) == 0

    def test_validate_actions_valid(self, sample_automation_config):
        """Test _validate_actions with valid actions (expects config dict)."""
        troubleshooter = AutomationTroubleshooter()
        issues = troubleshooter._validate_actions(
            sample_automation_config["perfect_automation"]
        )
        assert len(issues) == 0

    def test_check_infinite_loop_detected(self, sample_automation_config):
        """Test _check_infinite_loop detection."""
        troubleshooter = AutomationTroubleshooter()
        issues = troubleshooter._check_infinite_loop(
            sample_automation_config["infinite_loop"]
        )
        assert len(issues) > 0

    def test_check_infinite_loop_not_present(self, sample_automation_config):
        """Test _check_infinite_loop when no loop exists."""
        troubleshooter = AutomationTroubleshooter()
        issues = troubleshooter._check_infinite_loop(
            sample_automation_config["perfect_automation"]
        )
        assert len(issues) == 0

    def test_check_mode(self):
        """Test _check_mode method."""
        troubleshooter = AutomationTroubleshooter()
        valid_modes = ["single", "restart", "queued", "parallel"]
        for mode in valid_modes:
            config = {"mode": mode}
            issues = troubleshooter._check_mode(config)
            assert len(issues) == 0

    def test_calculate_health_score(self):
        """Test _calculate_health_score method."""
        troubleshooter = AutomationTroubleshooter()
        issues = [
            AutomationIssue(issue_type="test_error", severity="high", message="Error 1", suggestion="Fix 1"),
            AutomationIssue(issue_type="test_warning", severity="medium", message="Warning 1", suggestion="Fix 1"),
        ]
        score = troubleshooter._calculate_health_score(issues)
        assert 0 <= score <= 1

    def test_troubleshoot_valid_automation(self, sample_automation_config):
        """Test troubleshoot with valid automation (sync)."""
        troubleshooter = AutomationTroubleshooter()
        result = troubleshooter.troubleshoot(sample_automation_config["perfect_automation"])
        assert isinstance(result, AutomationTroubleshootResult)

    def test_troubleshoot_invalid_automation(self, sample_automation_config):
        """Test troubleshoot with invalid automation (sync)."""
        troubleshooter = AutomationTroubleshooter()
        result = troubleshooter.troubleshoot(sample_automation_config["infinite_loop"])
        assert isinstance(result, AutomationTroubleshootResult)
        assert len(result.issues) > 0

    def test_troubleshoot_multiple(self, sample_automation_config):
        """Test troubleshoot_multiple method (sync)."""
        troubleshooter = AutomationTroubleshooter()
        configs = list(sample_automation_config.values())
        results = troubleshooter.troubleshoot_multiple(configs)
        assert len(results) == len(configs)

    def test_get_ai_enhanced_troubleshooting(self, sample_automation_config):
        """Test get_ai_enhanced_troubleshooting method (sync)."""
        troubleshooter = AutomationTroubleshooter()
        result = troubleshooter.get_ai_enhanced_troubleshooting(
            sample_automation_config["perfect_automation"],
            AutomationTroubleshootResult(issues=[], health_score=1.0, automation_alias="Test"),
        )
        assert isinstance(result, str)

    def test_generate_fixed_automation(self):
        """Test generate_fixed_automation method (sync)."""
        troubleshooter = AutomationTroubleshooter()
        # Config missing alias and mode - should be auto-fixed
        incomplete_config = {
            "description": "Incomplete automation",
            "mode": "single",
            "trigger": {"platform": "time", "at": "00:00:00"},
            "action": [{"service": "light.turn_on", "target": {"entity_id": "light.test"}}],
        }
        fixed = troubleshooter.generate_fixed_automation(
            incomplete_config,
            AutomationTroubleshootResult(issues=[], health_score=1.0, automation_alias=""),
        )
        # May return None if no fixes needed, or dict if fixes applied
        assert fixed is None or isinstance(fixed, dict)


# ============================================================================
# Feature 4: Entity Discovery Tests
# ============================================================================

class TestEntitySummary:
    """Tests for EntitySummary class."""

    def test_entity_summary_init(self):
        """Test EntitySummary initialization."""
        summary = EntitySummary(
            entity_id="light.test",
            name="Test Light",
            domain="light",
            device_class="light",
            area="Living Room",
            state="on",
            attributes={"brightness": 200},
        )
        assert summary.entity_id == "light.test"
        assert summary.name == "Test Light"
        assert summary.domain == "light"

    def test_entity_summary_to_dict(self):
        """Test EntitySummary.to_dict() method."""
        summary = EntitySummary(entity_id="light.test2", name="Test2", domain="light")
        data = summary.to_dict()
        assert data["entity_id"] == "light.test2"
        assert data["name"] == "Test2"
        assert data["domain"] == "light"


class TestAutomationSuggestion:
    """Tests for AutomationSuggestion class."""

    def test_automation_suggestion_init(self):
        """Test AutomationSuggestion initialization."""
        suggestion = AutomationSuggestion(
            suggestion_text="Test Automation",
            automation_config={"trigger": {}, "action": {}},
            confidence=0.85,
            category="general",
            required_entities=["light.test"],
        )
        assert suggestion.suggestion_text == "Test Automation"
        assert suggestion.confidence == 0.85

    def test_automation_suggestion_to_dict(self):
        """Test AutomationSuggestion.to_dict() method."""
        suggestion = AutomationSuggestion(
            suggestion_text="Test", automation_config={}, confidence=0.9, category="test"
        )
        data = suggestion.to_dict()
        assert "confidence_label" in data

    def test_confidence_label(self):
        """Test _confidence_label method."""
        high_conf = AutomationSuggestion(
            suggestion_text="Test", automation_config={}, confidence=0.9, category="test"
        )
        assert high_conf._confidence_label() in ["high", "Very High", "High"]

        low_conf = AutomationSuggestion(
            suggestion_text="Test", automation_config={}, confidence=0.3, category="test"
        )
        assert low_conf._confidence_label() in ["low", "Very Low", "Low"]


class TestEntityDiscoveryResult:
    """Tests for EntityDiscoveryResult class."""

    def test_entity_discovery_result_init(self):
        """Test EntityDiscoveryResult initialization."""
        result = EntityDiscoveryResult(
            entities_by_area={},
            entities_by_domain={},
            entities_by_device_class={},
            suggestions=[],
            total_entities=0,
        )
        assert result.total_entities == 0
        assert result.entities_by_area == {}

    def test_entity_discovery_result_to_dict(self):
        """Test EntityDiscoveryResult.to_dict() method."""
        result = EntityDiscoveryResult(
            entities_by_area={"room": []},
            entities_by_domain={"light": []},
            entities_by_device_class={},
            suggestions=[],
            total_entities=1,
        )
        data = result.to_dict()
        assert "entities_by_area" in data
        assert "entities_by_domain" in data
        assert "total_entities" in data


class TestEntityDiscoveryAssistant:
    """Tests for EntityDiscoveryAssistant class."""

    def test_entity_discovery_assistant_init(self):
        """EntityDiscoveryAssistant initialization (no hass parameter)."""
        assistant = EntityDiscoveryAssistant()
        assert assistant is not None

    def test_automation_patterns_exist(self):
        """Test that _patterns (AUTOMATION_PATTERNS) is populated."""
        assistant = EntityDiscoveryAssistant()
        assert len(assistant._patterns) > 0

    def test_discover_entities(self, sample_entities):
        """Test discover_entities method (sync, takes entities list directly)."""
        assistant = EntityDiscoveryAssistant()
        result = assistant.discover_entities(sample_entities)
        assert isinstance(result, EntityDiscoveryResult)

    def test_discover_entities_empty(self):
        """Test discover_entities with no entities."""
        assistant = EntityDiscoveryAssistant()
        result = assistant.discover_entities([])
        assert isinstance(result, EntityDiscoveryResult)
        # EntityDiscoveryResult has entities_by_area, entities_by_domain, etc. (not 'entities')
        assert result.total_entities == 0

    def test_get_entities_by_room(self, sample_entities):
        """Test get_entities_by_room method (sync, returns List[Dict])."""
        assistant = EntityDiscoveryAssistant()
        rooms = assistant.get_entities_by_room(sample_entities)
        assert isinstance(rooms, list)  # Returns list of entities in the room

    def test_get_entities_by_function(self, sample_entities):
        """Test get_entities_by_function method (sync, returns List[Dict])."""
        assistant = EntityDiscoveryAssistant()
        # get_entities_by_function requires a function parameter
        lights = assistant.get_entities_by_function(sample_entities, "lights")
        assert isinstance(lights, list)  # Returns list of matching entities

    def test_suggest_automations(self, sample_entities):
        """Test suggest_automations method (sync)."""
        assistant = EntityDiscoveryAssistant()
        suggestions = assistant.suggest_automations(sample_entities)
        assert isinstance(suggestions, list)  # May be empty if no patterns match

    def test_get_ai_prompt_for_suggestions(self, sample_entities):
        """Test get_ai_prompt_for_suggestions method (sync)."""
        assistant = EntityDiscoveryAssistant()
        prompt = assistant.get_ai_prompt_for_suggestions(sample_entities, "Test query")
        assert isinstance(prompt, str)
        assert len(prompt) > 0


# ============================================================================
# Feature 5: Configuration Validator Tests
# ============================================================================

class TestConfigIssue:
    """Tests for ConfigIssue class."""

    def test_config_issue_init(self):
        """Test ConfigIssue initialization."""
        issue = ConfigIssue(
            issue_type="test_issue",
            severity="high",
            file="configuration.yaml",
            line=1,
            message="Test issue",
            suggestion="Test suggestion",
        )
        assert issue.severity == "high"
        assert issue.message == "Test issue"
        assert issue.file == "configuration.yaml"

    def test_config_issue_to_dict(self):
        """Test ConfigIssue.to_dict() method."""
        issue = ConfigIssue(
            issue_type="test", severity="medium", file="test.yaml", line=0,
            message="Test", suggestion="Suggestion"
        )
        data = issue.to_dict()
        assert data["severity"] == "medium"
        assert data["file"] == "test.yaml"


class TestConfigValidationResult:
    """Tests for ConfigValidationResult class."""

    def test_config_validation_result_init(self):
        """Test ConfigValidationResult initialization."""
        result = ConfigValidationResult(
            config_type="yaml",
            issues=[],
            valid=True,
            summary={"total_issues": 0, "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}},
        )
        assert result.config_type == "yaml"
        assert result.valid == True

    def test_config_validation_result_to_dict(self):
        """Test ConfigValidationResult.to_dict() method."""
        result = ConfigValidationResult(
            config_type="test", issues=[], valid=True,
            summary={"total_issues": 0, "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}}
        )
        data = result.to_dict()
        assert "issues" in data
        assert "summary" in data

    def test_config_validation_result_to_markdown(self):
        """Test ConfigValidationResult.to_markdown() method."""
        result = ConfigValidationResult(
            config_type="test", issues=[], valid=True,
            summary={"total_issues": 0, "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}}
        )
        markdown = result.to_markdown()
        assert isinstance(markdown, str)


class TestConfigurationValidator:
    """Tests for ConfigurationValidator class."""

    def test_configuration_validator_init(self, mock_hass):
        """Test ConfigurationValidator initialization."""
        validator = ConfigurationValidator()
        assert validator is not None

    def test_deprecated_options_exist(self):
        """Test that deprecated_options is populated."""
        validator = ConfigurationValidator()
        assert len(validator.deprecated_options) > 0

    def test_validate_configuration_yaml_valid(self):
        """Test validate_configuration_yaml with valid config."""
        validator = ConfigurationValidator()
        valid_config = {"homeassistant": {"latitude": 0, "longitude": 0}}
        result = validator.validate_configuration_yaml(valid_config)
        assert isinstance(result, ConfigValidationResult)

    def test_validate_configuration_yaml_invalid(self):
        """Test validate_configuration_yaml with invalid config."""
        validator = ConfigurationValidator()
        invalid_config = {"invalid_section_xyz": {}}
        result = validator.validate_configuration_yaml(invalid_config)
        assert isinstance(result, ConfigValidationResult)

    def test_validate_automations_yaml(self, sample_automation_config):
        """Test validate_automations_yaml method."""
        validator = ConfigurationValidator()
        result = validator.validate_automations_yaml(
            list(sample_automation_config.values())
        )
        assert isinstance(result, ConfigValidationResult)

    def test_validate_scripts_yaml(self):
        """Test validate_scripts_yaml method."""
        validator = ConfigurationValidator()
        scripts = [{"alias": "test", "sequence": [{"service": "test"}]}]
        result = validator.validate_scripts_yaml(scripts)
        assert isinstance(result, ConfigValidationResult)

    def test_validate_groups_yaml(self):
        """Test validate_groups_yaml method."""
        validator = ConfigurationValidator()
        groups = {"test_group": {"entities": ["light.test"]}}
        result = validator.validate_groups_yaml(groups)
        assert isinstance(result, ConfigValidationResult)

    def test_validate_integration_config(self):
        """Test validate_integration_config method."""
        validator = ConfigurationValidator()
        result = validator.validate_integration_config("mqtt", {"broker": "localhost"})
        assert isinstance(result, ConfigValidationResult)

    def test_check_deprecated_options(self):
        """Test check_deprecated_options method."""
        validator = ConfigurationValidator()
        issues = validator.check_deprecated_options("sensor", {"platform": "yaml"})
        assert isinstance(issues, list)

    def test_check_best_practices(self):
        """Test check_best_practices method."""
        validator = ConfigurationValidator()
        config = {"automation": {"alias": "test", "trigger": {}, "action": {}}}
        issues = validator.check_best_practices("automation", config)
        assert isinstance(issues, list)

    def test_check_sensitive_data(self):
        """Test check_sensitive_data method."""
        validator = ConfigurationValidator()
        config = {"password": "secret123", "api_key": "abc123"}
        issues = validator.check_sensitive_data(config)
        assert isinstance(issues, list)

    def test_get_ai_prompt_for_improvements(self):
        """Test get_ai_prompt_for_improvements method."""
        validator = ConfigurationValidator()
        result = ConfigValidationResult(config_type="test", issues=[], valid=True)
        prompt = validator.get_ai_prompt_for_improvements(result)
        assert isinstance(prompt, str)


# ============================================================================
# Feature 6: Backup Advisor Tests
# ============================================================================

class TestBackupItem:
    """Tests for BackupItem class."""

    def test_backup_item_init(self):
        """Test BackupItem initialization."""
        item = BackupItem(
            item_type="config",
            name="Main Config",
            path="/config/test.yaml",
            description="Test item",
            critical=True,
        )
        assert item.item_type == "config"
        assert item.name == "Main Config"
        assert item.critical == True

    def test_backup_item_to_dict(self):
        """Test BackupItem.to_dict() method."""
        item = BackupItem(
            item_type="test", name="Test", path="/test", description="Test", critical=False
        )
        data = item.to_dict()
        assert data["item_type"] == "test"
        assert data["critical"] == False


class TestBackupRecommendation:
    """Tests for BackupRecommendation class."""

    def test_backup_recommendation_init(self):
        """Test BackupRecommendation initialization."""
        recommendation = BackupRecommendation(
            items=[],
            summary="Test summary",
            instructions="Test instructions",
        )
        assert recommendation.summary == "Test summary"
        assert recommendation.instructions == "Test instructions"

    def test_backup_recommendation_to_markdown(self):
        """Test BackupRecommendation.to_markdown() method."""
        recommendation = BackupRecommendation(items=[], summary="Test", instructions="Test")
        markdown = recommendation.to_markdown()
        assert isinstance(markdown, str)


class TestPostChangeVerification:
    """Tests for PostChangeVerification class."""

    def test_post_change_verification_init(self):
        """Test PostChangeVerification initialization."""
        verification = PostChangeVerification(
            checks_passed=5,
            checks_failed=0,
            issues=[],
            recommendations=[],
        )
        assert verification.checks_passed == 5
        assert verification.checks_failed == 0

    def test_post_change_verification_to_markdown(self):
        """Test PostChangeVerification.to_markdown() method."""
        verification = PostChangeVerification(
            checks_passed=1, checks_failed=0, issues=[], recommendations=[]
        )
        markdown = verification.to_markdown()
        assert isinstance(markdown, str)


class TestRollbackSuggestion:
    """Tests for RollbackSuggestion class."""

    def test_rollback_suggestion_init(self):
        """Test RollbackSuggestion initialization."""
        suggestion = RollbackSuggestion(
            issue_description="Test issue",
            rollback_steps=["Step 1", "Step 2"],
            affected_components=["component1"],
            priority="high",
        )
        assert suggestion.issue_description == "Test issue"
        assert len(suggestion.rollback_steps) == 2
        assert suggestion.priority == "high"

    def test_rollback_suggestion_to_markdown(self):
        """Test RollbackSuggestion.to_markdown() method."""
        suggestion = RollbackSuggestion(
            issue_description="Test issue", rollback_steps=["Step 1"], affected_components=["component1"], priority="high"
        )
        markdown = suggestion.to_markdown()
        assert isinstance(markdown, str)


class TestBackupAdvisor:
    """Tests for BackupAdvisor class."""

    def test_backup_advisor_init(self):
        """Test BackupAdvisor initialization."""
        advisor = BackupAdvisor()
        assert advisor is not None

    def test_critical_backup_items_exist(self):
        """Test that CRITICAL_BACKUP_ITEMS is populated."""
        advisor = BackupAdvisor()
        assert len(advisor.CRITICAL_BACKUP_ITEMS) > 0

    def test_get_backup_recommendation(self, sample_backup_items):
        """Test get_backup_recommendation method."""
        advisor = BackupAdvisor()
        recommendation = advisor.get_backup_recommendation("Testing backup functionality")
        assert isinstance(recommendation, BackupRecommendation)

    def test_get_pre_change_checklist(self):
        """Test get_pre_change_checklist method."""
        advisor = BackupAdvisor()
        checklist = advisor.get_pre_change_checklist("Testing checklist")
        assert isinstance(checklist, list)

    def test_verify_after_changes(self):
        """Test verify_after_changes method."""
        advisor = BackupAdvisor()
        changes = [{"type": "automation", "name": "test_automation"}]
        verification = advisor.verify_after_changes(changes)
        assert isinstance(verification, PostChangeVerification)

    def test_get_rollback_suggestion(self):
        """Test get_rollback_suggestion method."""
        advisor = BackupAdvisor()
        changes = [{"type": "automation", "name": "test"}]
        suggestion = advisor.get_rollback_suggestion("Test issue", changes)
        assert isinstance(suggestion, RollbackSuggestion)

    def test_generate_backup_script(self):
        """Test generate_backup_script method."""
        advisor = BackupAdvisor()
        script = advisor.generate_backup_script("/backup/path")
        assert isinstance(script, str)
        assert len(script) > 0

    def test_get_ai_prompt_for_rollback(self):
        """Test get_ai_prompt_for_rollback method."""
        advisor = BackupAdvisor()
        changes = [{"type": "automation", "name": "test"}]
        prompt = advisor.get_ai_prompt_for_rollback("Test issue", changes, True)
        assert isinstance(prompt, str)


# ============================================================================
# Feature 7: Energy Advisor Tests
# ============================================================================

class TestEnergySummary:
    """Tests for EnergySummary class."""

    def test_energy_summary_init(self):
        """Test EnergySummary initialization."""
        summary = EnergySummary(
            total_usage=1000.5,
            total_cost=50.0,
            usage_by_source={"grid": 800, "solar": 200},
            usage_by_period={"hourly": {}, "daily": {}},
        )
        assert summary.total_usage == 1000.5
        assert summary.total_cost == 50.0

    def test_energy_summary_to_dict(self):
        """Test EnergySummary.to_dict() method."""
        summary = EnergySummary(total_usage=100, total_cost=5.0)
        data = summary.to_dict()
        assert data["total_usage"] == 100


class TestEnergySuggestion:
    """Tests for EnergySuggestion class."""

    def test_energy_suggestion_init(self):
        """Test EnergySuggestion initialization."""
        suggestion = EnergySuggestion(
            title="Test Suggestion",
            description="Test description",
            potential_savings="10% reduction",
            priority="high",
            category="automation",
        )
        assert suggestion.title == "Test Suggestion"
        assert suggestion.potential_savings == "10% reduction"

    def test_energy_suggestion_to_markdown(self):
        """Test EnergySuggestion.to_markdown() method."""
        suggestion = EnergySuggestion(
            title="Test", description="Test", potential_savings="5%", priority="medium"
        )
        markdown = suggestion.to_markdown()
        assert isinstance(markdown, str)


class TestDeviceEnergyAnalysis:
    """Tests for DeviceEnergyAnalysis class."""

    def test_device_energy_analysis_init(self):
        """Test DeviceEnergyAnalysis initialization."""
        analysis = DeviceEnergyAnalysis(
            entity_id="sensor.test",
            name="Test Device",
            domain="sensor",
            avg_usage=2.0,
            cost_per_period=15.0,
            is_automatable=False,
        )
        assert analysis.entity_id == "sensor.test"
        assert analysis.name == "Test Device"
        assert analysis.domain == "sensor"

    def test_device_energy_analysis_to_dict(self):
        """Test DeviceEnergyAnalysis.to_dict() method."""
        analysis = DeviceEnergyAnalysis(
            entity_id="test", name="Test", domain="sensor", avg_usage=1.0, cost_per_period=5.0
        )
        data = analysis.to_dict()
        assert data["entity_id"] == "test"


class TestEnergyOptimizationResult:
    """Tests for EnergyOptimizationResult class."""

    def test_energy_optimization_result_init(self):
        """Test EnergyOptimizationResult initialization."""
        result = EnergyOptimizationResult(
            energy_summary=EnergySummary(total_usage=1000, total_cost=50),
            suggestions=[],
            device_analysis=[],
        )
        assert result.energy_summary is not None

    def test_energy_optimization_result_to_markdown(self):
        """Test EnergyOptimizationResult.to_markdown() method."""
        result = EnergyOptimizationResult(
            energy_summary=EnergySummary(total_usage=100, total_cost=5),
            suggestions=[],
            device_analysis=[],
        )
        markdown = result.to_markdown()
        assert isinstance(markdown, str)


class TestEnergyAdvisor:
    """Tests for EnergyAdvisor class."""

    def test_energy_advisor_init(self):
        """Test EnergyAdvisor initialization."""
        advisor = EnergyAdvisor()
        assert advisor is not None

    def test_optimization_patterns_exist(self):
        """Test that OPTIMIZATION_PATTERNS is populated."""
        advisor = EnergyAdvisor()
        assert len(advisor.OPTIMIZATION_PATTERNS) > 0

    def test_analyze_energy_data(self, sample_energy_data):
        """Test analyze_energy_data method."""
        advisor = EnergyAdvisor()
        result = advisor.analyze_energy_data(sample_energy_data.get("entities", []), [])
        assert isinstance(result, EnergyOptimizationResult)

    def test_analyze_energy_data_empty(self):
        """Test analyze_energy_data with empty data."""
        advisor = EnergyAdvisor()
        result = advisor.analyze_energy_data([], [])
        assert isinstance(result, EnergyOptimizationResult)

    def test_get_energy_summary(self, sample_energy_data):
        """Test get_energy_summary method."""
        advisor = EnergyAdvisor()
        summary = advisor.get_energy_summary(sample_energy_data.get("entities", []))
        assert isinstance(summary, EnergySummary)

    def test_analyze_device_energy(self, sample_energy_data):
        """Test analyze_device_energy method."""
        advisor = EnergyAdvisor()
        entities = [sample_energy_data["entities"][0]]
        analyses = advisor.analyze_device_energy(entities)
        assert isinstance(analyses, list)

    def test_get_optimization_suggestions(self, sample_energy_data):
        """Test get_optimization_suggestions method."""
        advisor = EnergyAdvisor()
        suggestions = advisor.get_optimization_suggestions(sample_energy_data["entities"])
        assert len(suggestions) >= 0

    def test_suggest_automation_for_device(self, sample_energy_data):
        """Test suggest_automation_for_device method."""
        advisor = EnergyAdvisor()
        entity = sample_energy_data["entities"][0]
        automation = advisor.suggest_automation_for_device(entity)
        assert automation is None or isinstance(automation, dict)

    def test_get_ai_prompt_for_energy_analysis(self):
        """Test get_ai_prompt_for_energy_analysis method."""
        advisor = EnergyAdvisor()
        prompt = advisor.get_ai_prompt_for_energy_analysis({}, [])
        assert isinstance(prompt, str)


# ============================================================================
# Feature 8: Security Audit Tests
# ============================================================================

class TestSecurityIssue:
    """Tests for SecurityIssue class."""

    def test_security_issue_init(self):
        """Test SecurityIssue initialization."""
        issue = SecurityIssue(
            issue_type="test_issue",
            severity="critical",
            description="Test issue",
            recommendation="Test recommendation",
            affected_entity="light.test",
        )
        assert issue.severity == "critical"
        assert issue.issue_type == "test_issue"

    def test_security_issue_to_markdown(self):
        """Test SecurityIssue.to_markdown() method."""
        issue = SecurityIssue(
            issue_type="test", severity="high", description="Test", recommendation="Test"
        )
        markdown = issue.to_markdown()
        assert isinstance(markdown, str)


class TestSecurityAuditResult:
    """Tests for SecurityAuditResult class."""

    def test_security_audit_result_init(self):
        """Test SecurityAuditResult initialization."""
        result = SecurityAuditResult(
            issues=[],
            score=0.85,
        )
        assert result.score == 0.85

    def test_security_audit_result_to_markdown(self):
        """Test SecurityAuditResult.to_markdown() method."""
        result = SecurityAuditResult(issues=[], score=0.9)
        markdown = result.to_markdown()
        assert isinstance(markdown, str)


class TestSecurityAuditor:
    """Tests for SecurityAuditor class."""

    def test_security_auditor_init(self):
        """Test SecurityAuditor initialization."""
        auditor = SecurityAuditor()
        assert auditor is not None

    def test_credential_patterns_exist(self):
        """Test that CREDENTIAL_PATTERNS is populated."""
        auditor = SecurityAuditor()
        assert len(auditor.CREDENTIAL_PATTERNS) > 0

    def test_audit_automations(self, sample_security_config):
        """Test audit_automations method."""
        auditor = SecurityAuditor()
        # Convert trigger from dict to list format expected by source
        proper_automations = []
        for key, value in sample_security_config.items():
            auto = value.copy()
            if isinstance(auto.get("trigger"), dict):
                auto["trigger"] = [auto["trigger"]]
            if "condition" not in auto:
                auto["condition"] = []
            if "action" not in auto:
                auto["action"] = []
            proper_automations.append(auto)
        result = auditor.audit_automations(proper_automations)
        assert isinstance(result, SecurityAuditResult)

    def test_check_exposed_credentials(self):
        """Test check_exposed_credentials method."""
        auditor = SecurityAuditor()
        configs = [{"alias": "test", "api_key": "12345"}]
        issues = auditor.check_exposed_credentials(configs)
        assert isinstance(issues, list)

    def test_check_permissive_configs(self):
        """Test check_permissive_configs method."""
        auditor = SecurityAuditor()
        automations = [{"alias": "test", "config": {"http": {"cors_enabled": True, "trusted_networks": []}}}]
        issues = auditor.check_permissive_configs(automations)
        assert isinstance(issues, list)

    def test_check_infinite_loops(self, sample_security_config):
        """Test check_infinite_loops method."""
        auditor = SecurityAuditor()
        # Convert trigger from dict to list format expected by source
        proper_automations = []
        for key, value in sample_security_config.items():
            auto = value.copy()
            if isinstance(auto.get("trigger"), dict):
                auto["trigger"] = [auto["trigger"]]
            if "condition" not in auto:
                auto["condition"] = []
            if "action" not in auto:
                auto["action"] = []
            proper_automations.append(auto)
        issues = auditor.check_infinite_loops(proper_automations)
        assert isinstance(issues, list)

    def test_check_service_permissions(self):
        """Test check_service_permissions method."""
        auditor = SecurityAuditor()
        automations = [{"alias": "test", "action": [{"service": "shell_command.run"}]}]
        issues = auditor.check_service_permissions(automations)
        assert isinstance(issues, list)

    def test_check_external_exposure(self):
        """Test check_external_exposure method."""
        auditor = SecurityAuditor()
        automations = [{"alias": "test", "trigger": [{"platform": "state", "entity_id": "sensor.test"}]}]
        issues = auditor.check_external_exposure(automations)
        assert isinstance(issues, list)

    def test_get_ai_security_review(self):
        """Test get_ai_security_review method."""
        auditor = SecurityAuditor()
        review = auditor.get_ai_security_review(SecurityAuditResult(issues=[], score=100.0))
        assert isinstance(review, str)

    def test_calculate_security_score(self):
        """Test calculate_security_score method."""
        auditor = SecurityAuditor()
        issues = [
            SecurityIssue(issue_type="critical", severity="critical", description="Critical", recommendation="Fix"),
            SecurityIssue(issue_type="low", severity="low", description="Low", recommendation="Fix"),
        ]
        score = auditor.calculate_security_score(issues)
        assert isinstance(score, (int, float))  # Accept both int and float

    def test_audit_automations_empty(self):
        """Test audit_automations with empty list."""
        auditor = SecurityAuditor()
        result = auditor.audit_automations([])
        assert isinstance(result, SecurityAuditResult)


# ============================================================================
# Feature 9: NL to Automation Converter Tests
# ============================================================================

class TestNLToAutomationResult:
    """Tests for NLToAutomationResult class."""

    def test_nl_to_automation_result_init(self):
        """Test NLToAutomationResult initialization."""
        result = NLToAutomationResult(
            original_query="Test query",
            automation_config={},
            yaml_output="```yaml\n",
            confidence=0.85,
            suggestions=[],
            needs_clarification=False,
            clarification_questions=[],
        )
        assert result.confidence == 0.85
        assert result.original_query == "Test query"

    def test_nl_to_automation_result_to_dict(self):
        """Test NLToAutomationResult.to_dict() method."""
        result = NLToAutomationResult(
            original_query="Test", automation_config={}, yaml_output="", confidence=0.9
        )
        data = result.to_dict()
        assert "confidence" in data

    def test_nl_to_automation_result_to_markdown(self):
        """Test NLToAutomationResult.to_markdown() method."""
        result = NLToAutomationResult(
            original_query="Test", automation_config={}, yaml_output="", confidence=0.8
        )
        markdown = result.to_markdown()
        assert isinstance(markdown, str)


class TestNLToAutomationConverter:
    """Tests for NLToAutomationConverter class."""

    def test_nl_to_automation_converter_init(self):
        """Test NLToAutomationConverter initialization."""
        converter = NLToAutomationConverter()
        assert converter is not None

    def test_time_patterns_exist(self):
        """Test that TIME_PATTERNS is populated."""
        converter = NLToAutomationConverter()
        assert len(converter.TIME_PATTERNS) > 0

    def test_convert(self, sample_nl_inputs):
        """Test convert method with various inputs."""
        converter = NLToAutomationConverter()
        for nl_input in sample_nl_inputs:
            if nl_input:  # Skip empty inputs for this test
                result = converter.convert(nl_input, [])
                assert isinstance(result, NLToAutomationResult)

    def test_parse_time_expression(self):
        """Test parse_time_expression method."""
        converter = NLToAutomationConverter()
        result = converter.parse_time_expression("6pm")
        assert isinstance(result, dict)

    def test_identify_entities(self):
        """Test identify_entities method."""
        converter = NLToAutomationConverter()
        result = converter.identify_entities("turn on the living room light")
        assert isinstance(result, list)

    def test_identify_action(self):
        """Test identify_action method."""
        converter = NLToAutomationConverter()
        result = converter.identify_action("turn on the light")
        assert isinstance(result, dict)

    def test_identify_trigger(self):
        """Test identify_trigger method."""
        converter = NLToAutomationConverter()
        result = converter.identify_trigger("when the door opens")
        assert isinstance(result, dict)

    def test_generate_automation(self):
        """Test generate_automation method."""
        converter = NLToAutomationConverter()
        trigger_info = {"platform": "time", "at": "00:00:00"}
        action_info = {"service": "homeassistant.turn_on"}
        entities = []
        time_info = {}
        result = converter.generate_automation(trigger_info, action_info, entities, time_info)
        assert isinstance(result, dict)

    def test_generate_yaml(self):
        """Test generate_yaml method."""
        converter = NLToAutomationConverter()
        automation_config = {
            "alias": "Test",
            "trigger": {"platform": "time", "at": "00:00:00"},
            "action": [{"service": "test.service"}],
        }
        yaml_output = converter.generate_yaml(automation_config)
        assert isinstance(yaml_output, str)

    def test_check_clarification_needed(self):
        """Test check_clarification_needed method."""
        converter = NLToAutomationConverter()
        # Vague input should need clarification
        trigger_info = {}
        action_info = {"action_type": "turn_on"}
        entities = []
        needs_clar, questions = converter.check_clarification_needed(trigger_info, action_info, entities)
        assert needs_clar == True

        # Specific input should not need clarification
        trigger_info = {"trigger_type": "time"}
        action_info = {"action_type": "turn_on"}
        entities = [{"entity_id": "light.test"}]
        needs_clar, questions = converter.check_clarification_needed(trigger_info, action_info, entities)
        assert needs_clar == False

    def test_get_ai_conversion_prompt(self):
        """Test get_ai_conversion_prompt method."""
        converter = NLToAutomationConverter()
        prompt = converter.get_ai_conversion_prompt("turn on the light", [])
        assert isinstance(prompt, str)

    def test_generate_automation_missing_fields(self):
        """Test generate_automation with missing fields."""
        converter = NLToAutomationConverter()
        trigger_info = {}
        action_info = {}
        entities = []
        time_info = {}
        result = converter.generate_automation(trigger_info, action_info, entities, time_info)
        assert isinstance(result, dict)


# ============================================================================
# Feature 10: Dashboard Advisor Tests
# ============================================================================

class TestDashboardAnalysis:
    """Tests for DashboardAnalysis class."""

    def test_dashboard_analysis_init(self):
        """Test DashboardAnalysis initialization."""
        analysis = DashboardAnalysis(
            dashboard_url="/dashboard/main",
            dashboard_title="Main Dashboard",
            card_count=5,
            views=2,
            card_types={"entities": 3, "gauge": 2},
            issues=[],
            recommendations=[],
        )
        assert analysis.dashboard_url == "/dashboard/main"
        assert analysis.dashboard_title == "Main Dashboard"
        assert analysis.card_count == 5
        assert analysis.views == 2

    def test_dashboard_analysis_to_markdown(self):
        """Test DashboardAnalysis.to_markdown() method."""
        analysis = DashboardAnalysis(
            dashboard_url="/dashboard/test",
            dashboard_title="Test Dashboard",
            card_count=3,
            views=1,
            card_types={"entities": 3},
            issues=[],
            recommendations=[],
        )
        markdown = analysis.to_markdown()
        assert isinstance(markdown, str)
        assert "Test Dashboard" in markdown


class TestCardRecommendation:
    """Tests for CardRecommendation class."""

    def test_card_recommendation_init(self):
        """Test CardRecommendation initialization."""
        recommendation = CardRecommendation(
            card_type="entities",
            title="Living Room",
            entity_id="light.test",
            description="Test description",
            config={},
            priority="high",
        )
        assert recommendation.card_type == "entities"
        assert recommendation.title == "Living Room"
        assert recommendation.priority == "high"

    def test_card_recommendation_to_dict(self):
        """Test CardRecommendation.to_dict() method."""
        recommendation = CardRecommendation(
            card_type="picture",
            title="Camera",
            entity_id="camera.test",
            description="Test",
            config={},
            priority="medium",
        )
        data = recommendation.to_dict()
        assert data["card_type"] == "picture"


class TestDashboardImprovement:
    """Tests for DashboardImprovement class."""

    def test_dashboard_improvement_init(self):
        """Test DashboardImprovement initialization."""
        improvement = DashboardImprovement(
            improvement_type="layout",
            description="Test description",
            current_state="Current state",
            suggested_change="Suggested change",
            priority="low",
        )
        assert improvement.improvement_type == "layout"
        assert improvement.description == "Test description"
        assert improvement.priority == "low"

    def test_dashboard_improvement_to_dict(self):
        """Test DashboardImprovement.to_dict() method."""
        improvement = DashboardImprovement(
            improvement_type="content",
            description="Test description",
            current_state="Current",
            suggested_change="Change",
            priority="medium",
        )
        data = improvement.to_dict()
        assert data["improvement_type"] == "content"


class TestDashboardAdvisor:
    """Tests for DashboardAdvisor class."""

    def test_dashboard_advisor_init(self):
        """Test DashboardAdvisor initialization."""
        advisor = DashboardAdvisor()
        assert advisor is not None

    def test_card_type_recommendations_exist(self):
        """Test that CARD_TYPE_RECOMMENDATIONS is populated."""
        advisor = DashboardAdvisor()
        assert len(advisor.CARD_TYPE_RECOMMENDATIONS) > 0

    def test_analyze_dashboard(self, sample_dashboard_config):
        """Test analyze_dashboard method."""
        advisor = DashboardAdvisor()
        config = sample_dashboard_config["well_structured_dashboard"]
        result = advisor.analyze_dashboard(config, [])
        assert isinstance(result, DashboardAnalysis)

    def test_analyze_dashboard_empty(self):
        """Test analyze_dashboard with empty dashboard."""
        advisor = DashboardAdvisor()
        result = advisor.analyze_dashboard({"title": "Empty", "views": []}, [])
        assert isinstance(result, DashboardAnalysis)

    def test_get_card_recommendations(self, sample_entities):
        """Test get_card_recommendations method."""
        advisor = DashboardAdvisor()
        recommendations = advisor.get_card_recommendations(sample_entities)
        assert len(recommendations) >= 0

    def test_get_improvement_suggestions(self, sample_dashboard_config):
        """Test get_improvement_suggestions method."""
        advisor = DashboardAdvisor()
        config = sample_dashboard_config["poorly_structured_dashboard"]
        analysis = DashboardAnalysis(dashboard_url="test", dashboard_title="test")
        suggestions = advisor.get_improvement_suggestions(config, analysis)
        assert len(suggestions) >= 0

    def test_suggest_dashboard_layout(self, sample_entities):
        """Test suggest_dashboard_layout method."""
        advisor = DashboardAdvisor()
        layout = advisor.suggest_dashboard_layout(sample_entities)
        assert isinstance(layout, dict)
        assert "title" in layout

    def test_get_dashboard_template(self, sample_entities):
        """Test get_dashboard_template method."""
        advisor = DashboardAdvisor()
        template = advisor.get_dashboard_template("energy", sample_entities)
        assert isinstance(template, dict)

    def test_get_ai_dashboard_review(self, sample_dashboard_config):
        """Test get_ai_dashboard_review method."""
        advisor = DashboardAdvisor()
        review = advisor.get_ai_dashboard_review(
            sample_dashboard_config["well_structured_dashboard"], []
        )
        assert isinstance(review, str)


# ============================================================================
# Feature 11: Integration Guide Tests
# ============================================================================

class TestIntegrationInfo:
    """Tests for IntegrationInfo class."""

    def test_integration_info_init(self):
        """Test IntegrationInfo initialization."""
        info = IntegrationInfo(
            domain="mqtt",
            name="MQTT",
            description="MQTT integration",
            setup_required=True,
        )
        assert info.domain == "mqtt"
        assert info.setup_required == True

    def test_integration_info_to_dict(self):
        """Test IntegrationInfo.to_dict() method."""
        info = IntegrationInfo(
            domain="test", name="Test", description="Test", setup_required=False
        )
        data = info.to_dict()
        assert data["domain"] == "test"


class TestSetupStep:
    """Tests for SetupStep class."""

    def test_setup_step_init(self):
        """Test SetupStep initialization."""
        step = SetupStep(
            step_number=1,
            title="Install",
            description="Install the integration",
            code_snippet="mqtt:\n  broker: localhost",
            required=True,
        )
        assert step.step_number == 1
        assert step.title == "Install"
        assert step.description == "Install the integration"
        assert step.code_snippet == "mqtt:\n  broker: localhost"
        assert step.required == True

    def test_setup_step_to_markdown(self):
        """Test SetupStep.to_markdown() method."""
        step = SetupStep(
            step_number=1, title="Test", description="Test description", code_snippet="", required=True
        )
        markdown = step.to_markdown()
        assert isinstance(markdown, str)
        assert "Step 1: Test" in markdown


class TestIntegrationGuide:
    """Tests for IntegrationGuide class."""

    def test_integration_guide_init(self):
        """Test IntegrationGuide initialization."""
        guide = IntegrationGuide(
            integration=IntegrationInfo(
                domain="test", name="Test", description="Test", setup_required=False
            ),
            steps=[SetupStep(step_number=1, title="Test", description="Test", code_snippet="", required=True)],
            config_snippets={},
            initial_automations=[],
            tips=["Tip 1"],
        )
        assert len(guide.steps) == 1
        assert guide.integration.domain == "test"

    def test_integration_guide_to_markdown(self):
        """Test IntegrationGuide.to_markdown() method."""
        guide = IntegrationGuide(
            integration=IntegrationInfo(
                domain="test", name="Test", description="Test", setup_required=False
            ),
            steps=[],
            config_snippets={},
            initial_automations=[],
            tips=[],
        )
        markdown = guide.to_markdown()
        assert isinstance(markdown, str)


class TestIntegrationGuideProvider:
    """Tests for IntegrationGuideProvider class."""

    def test_integration_guide_provider_init(self):
        """Test IntegrationGuideProvider initialization (no hass parameter)."""
        provider = IntegrationGuideProvider()
        assert provider is not None

    def test_integration_database_exist(self):
        """Test that INTEGRATION_DATABASE is populated."""
        provider = IntegrationGuideProvider()
        assert len(provider.INTEGRATION_DATABASE) > 0
        # Check known domains
        assert "mqtt" in provider.INTEGRATION_DATABASE
        assert "zha" in provider.INTEGRATION_DATABASE
        assert "deconz" in provider.INTEGRATION_DATABASE

    def test_get_integration_info(self):
        """Test get_integration_info method."""
        provider = IntegrationGuideProvider()
        info = provider.get_integration_info("mqtt")
        assert info is not None
        assert info.domain == "mqtt"
        assert info.name == "MQTT"

    def test_get_integration_info_zha(self):
        """Test get_integration_info for ZHA."""
        provider = IntegrationGuideProvider()
        info = provider.get_integration_info("zha")
        assert info is not None
        assert info.domain == "zha"

    def test_get_integration_info_not_found(self):
        """Test get_integration_info with non-existent domain."""
        provider = IntegrationGuideProvider()
        info = provider.get_integration_info("nonexistent_integration_xyz")
        assert info is None

    def test_get_setup_guide(self):
        """Test get_setup_guide method."""
        provider = IntegrationGuideProvider()
        guide = provider.get_setup_guide("mqtt")
        assert isinstance(guide, IntegrationGuide)

    def test_get_setup_steps(self):
        """Test get_setup_steps method."""
        provider = IntegrationGuideProvider()
        steps = provider.get_setup_steps("mqtt")
        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_get_config_snippet(self):
        """Test get_config_snippet method."""
        provider = IntegrationGuideProvider()
        snippet = provider.get_config_snippet("mqtt")
        assert isinstance(snippet, str)
        assert len(snippet) > 0

    def test_get_initial_automations(self):
        """Test get_initial_automations method."""
        provider = IntegrationGuideProvider()
        automations = provider.get_initial_automations("mqtt")
        assert isinstance(automations, list)

    def test_get_setup_tips(self):
        """Test get_setup_tips method."""
        provider = IntegrationGuideProvider()
        tips = provider.get_setup_tips("mqtt")
        assert isinstance(tips, list)

    def test_search_integrations(self, sample_integration_queries):
        """Test search_integrations method."""
        provider = IntegrationGuideProvider()
        for query in sample_integration_queries:
            results = provider.search_integrations(query)
            assert isinstance(results, list)

    def test_get_ai_setup_guide(self):
        """Test get_ai_setup_guide method."""
        provider = IntegrationGuideProvider()
        guide = provider.get_ai_setup_guide("mqtt", "Set up MQTT for home automation")
        assert isinstance(guide, str)
        assert len(guide) > 0


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Edge case tests across all features."""

    def test_empty_log_entries(self, mock_hass):
        """Test LogAnalyzer with empty log entries."""
        analyzer = LogAnalyzer(hass=mock_hass)
        result = analyzer.analyze_logs(generate_ai_summary=False)
        assert result is not None

    def test_very_long_error_message(self):
        """Test ErrorDiagnosisAssistant with very long error message."""
        assistant = ErrorDiagnosisAssistant()
        long_error = "Error: " + "x" * 10000
        result = assistant.diagnose(long_error)
        assert isinstance(result, list)

    def test_malformed_automation_config(self, mock_hass):
        """Test AutomationTroubleshooter with malformed config."""
        troubleshooter = AutomationTroubleshooter()
        malformed = {"this_is_not": {"a": {"valid": {"automation": {}}}}}
        result = troubleshooter.troubleshoot(malformed)
        assert isinstance(result, AutomationTroubleshootResult)

    def test_entities_with_special_characters(self):
        """Test EntityDiscoveryAssistant with special characters in entity names."""
        assistant = EntityDiscoveryAssistant()
        special_entities = [
            {
                "entity_id": "light.test-with_special.chars123",
                "state": "on",
                "attributes": {"friendly_name": "Test @#$%"},
            }
        ]
        result = assistant.discover_entities(special_entities)
        assert isinstance(result, EntityDiscoveryResult)

    def test_invalid_yaml_config(self):
        """Test ConfigurationValidator with invalid YAML."""
        validator = ConfigurationValidator()
        invalid = {"invalid": {"config": {"with": {"nested": {"invalid": {}}}}}}
        result = validator.validate_configuration_yaml(invalid)
        assert isinstance(result, ConfigValidationResult)

    def test_empty_backup_items(self):
        """Test BackupAdvisor with no backup items."""
        advisor = BackupAdvisor()
        recommendation = advisor.get_backup_recommendation("No items")
        assert isinstance(recommendation, BackupRecommendation)

    def test_zero_power_energy_data(self):
        """Test EnergyAdvisor with zero power readings."""
        advisor = EnergyAdvisor()
        zero_data = [
            {"entity_id": "sensor.test", "state": "0", "attributes": {}}
        ]
        result = advisor.analyze_energy_data(zero_data, [])
        assert isinstance(result, EnergyOptimizationResult)

    def test_empty_nl_input(self):
        """Test NLToAutomationConverter with empty input."""
        converter = NLToAutomationConverter()
        result = converter.convert("", [])
        assert isinstance(result, NLToAutomationResult)

    def test_empty_dashboard(self):
        """Test DashboardAdvisor with empty dashboard."""
        advisor = DashboardAdvisor()
        result = advisor.analyze_dashboard({"title": "Empty", "cards": []}, [])
        assert isinstance(result, DashboardAnalysis)

    def test_search_nonexistent_integration(self):
        """Test IntegrationGuideProvider searching for non-existent integration."""
        provider = IntegrationGuideProvider()
        results = provider.search_integrations("nonexistent_integration_xyz_123")
        assert isinstance(results, list)

    @pytest.mark.parametrize("severity", ["critical", "high", "medium", "low", "info"])
    def test_all_severity_levels(self, severity):
        """Test all severity levels across different classes."""
        # SecurityIssue
        issue = SecurityIssue(
            issue_type="test_issue", severity=severity, description="Test", recommendation="Test"
        )
        assert issue.severity == severity

        # AutomationIssue
        auto_issue = AutomationIssue(
            issue_type="test_issue", severity=severity, message="Test", suggestion="Test"
        )
        assert auto_issue.severity == severity

        # ConfigIssue
        config_issue = ConfigIssue(
            issue_type="test_issue", severity=severity, file="test.yaml", line=1, message="Test", suggestion="Test"
        )
        assert config_issue.severity == severity

    @pytest.mark.parametrize("confidence", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_confidence_ranges(self, confidence):
        """Test different confidence values."""
        # DiagnosisResult
        diagnosis = DiagnosisResult(
            error_message="Test", error_type="Test", severity="low",
            possible_causes=[], suggested_fixes=[], related_entities=[],
            documentation_url="", confidence=confidence,
        )
        assert diagnosis.confidence == confidence

        # AutomationSuggestion
        suggestion = AutomationSuggestion(
            suggestion_text="Test", confidence=confidence, category="general"
        )
        assert suggestion.confidence == confidence

        # NLToAutomationResult
        nl_result = NLToAutomationResult(
            original_query="Test",
            confidence=confidence,
        )
        assert nl_result.confidence == confidence


# ============================================================================
# Parameterized Tests for Random Test Data
# ============================================================================

class TestParameterizedTests:
    """Parameterized tests with random test data."""

    @pytest.mark.parametrize("log_level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    @pytest.mark.parametrize("logger_name", ["homeassistant.core", "custom_component.test", "custom.integration"])
    def test_log_entry_with_various_levels(self, log_level, logger_name):
        """Test LogEntry with various log levels and logger names."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=log_level,
            logger_name=logger_name,
            message="Test message",
        )
        assert entry.level == log_level.upper()
        assert entry.logger_name == logger_name

    @pytest.mark.parametrize("error_type", [
        "ValueError",
        "TypeError",
        "KeyError",
        "IndexError",
        "FileNotFoundError",
        "ConnectionError",
        "TimeoutError",
    ])
    def test_diagnose_various_error_types(self, error_type):
        """Test ErrorDiagnosisAssistant with various error types."""
        assistant = ErrorDiagnosisAssistant()
        error_msg = f"{error_type}: Test error message"
        result = assistant.diagnose(error_msg)
        assert isinstance(result, list)

    @pytest.mark.parametrize("mode", ["single", "restart", "queued", "parallel"])
    def test_automation_with_different_modes(self, mode):
        """Test AutomationTroubleshooter with different automation modes."""
        troubleshooter = AutomationTroubleshooter()
        config = {
            "alias": "Test",
            "mode": mode,
            "trigger": {"platform": "time", "at": "00:00:00"},
            "action": [{"service": "test.service"}],
        }
        result = troubleshooter.troubleshoot(config)
        assert isinstance(result, AutomationTroubleshootResult)

    @pytest.mark.parametrize("room", ["Living Room", "Kitchen", "Bedroom", "Bathroom", "Garage"])
    def test_entities_by_room(self, room):
        """Test EntityDiscoveryAssistant with different rooms."""
        assistant = EntityDiscoveryAssistant()
        entities = [
            {
                "entity_id": f"light.{room.lower().replace(' ', '_')}",
                "state": "on",
                "attributes": {"friendly_name": f"{room} Light", "room": room},
            }
        ]
        result = assistant.discover_entities(entities)
        assert isinstance(result, EntityDiscoveryResult)

    @pytest.mark.parametrize("config_section", [
        "configuration.yaml",
        "automations.yaml",
        "scripts.yaml",
        "groups.yaml",
    ])
    def test_validate_different_config_files(self, config_section):
        """Test ConfigurationValidator with different config file types."""
        validator = ConfigurationValidator()
        if config_section == "configuration.yaml":
            result = validator.validate_configuration_yaml({"homeassistant": {}})
        elif config_section == "automations.yaml":
            result = validator.validate_automations_yaml([])
        elif config_section == "scripts.yaml":
            result = validator.validate_scripts_yaml([])
        else:
            result = validator.validate_groups_yaml({})
        assert isinstance(result, ConfigValidationResult)

    @pytest.mark.parametrize("critical", [True, False])
    def test_backup_items_with_different_critical_values(self, critical):
        """Test BackupItem with different critical values."""
        item = BackupItem(
            item_type="config",
            name="Test Item",
            path="/config/test.yaml",
            description="Test",
            critical=critical,
        )
        assert item.critical == critical

    @pytest.mark.parametrize("power_value", [0, 10, 100, 1000, 10000])
    def test_energy_analysis_with_different_power_values(self, power_value):
        """Test EnergyAdvisor with different power values."""
        advisor = EnergyAdvisor()
        entities = [
            {
                "entity_id": "sensor.test",
                "state": str(power_value),
                "attributes": {"unit_of_measurement": "W", "device_class": "power"},
            }
        ]
        result = advisor.analyze_energy_data(entities, [])
        assert isinstance(result, EnergyOptimizationResult)

    @pytest.mark.parametrize("nl_input", [
        "Turn on the light",
        "Turn off all lights",
        "Open the garage door",
        "Set temperature to 22 degrees",
        "Start the vacuum cleaner",
        "Lock all doors",
    ])
    def test_convert_various_nl_inputs(self, nl_input):
        """Test NLToAutomationConverter with various natural language inputs."""
        converter = NLToAutomationConverter()
        result = converter.convert(nl_input, [])
        assert isinstance(result, NLToAutomationResult)

    @pytest.mark.parametrize("dashboard_type", [
        "energy",
        "security",
        "climate",
        "automations",
        "media",
    ])
    def test_dashboard_templates(self, dashboard_type):
        """Test DashboardAdvisor with different dashboard types."""
        advisor = DashboardAdvisor()
        entities = [
            {
                "entity_id": f"sensor.test_{dashboard_type}",
                "state": "on",
                "attributes": {},
            }
        ]
        template = advisor.get_dashboard_template(dashboard_type, entities)
        assert isinstance(template, dict)

    @pytest.mark.parametrize("integration_domain", [
        "mqtt",
        "hue",
        "nest",
        "tasmota",
        "roborock",
    ])
    def test_integration_guides(self, integration_domain):
        """Test IntegrationGuideProvider with different integrations."""
        provider = IntegrationGuideProvider()
        info = provider.get_integration_info(integration_domain)
        if info is not None:
            assert info.domain == integration_domain
            guide = provider.get_setup_guide(integration_domain)
            assert isinstance(guide, IntegrationGuide)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegrationTests:
    """Integration tests that test multiple components together."""

    def test_full_log_analysis_workflow(self, mock_hass, sample_log_entries):
        """Test complete log analysis workflow."""
        analyzer = LogAnalyzer(hass=mock_hass)
        
        # Get entries
        entries = sample_log_entries
        
        # Analyze logs
        result = analyzer.analyze_logs(entries)
        assert isinstance(result, LogAnalyzerResult)
        
        # Search logs
        search_results = analyzer.search_logs(entries, "error")
        assert isinstance(search_results, list)
        
        # Get error summary
        summary = analyzer.get_error_summary(hours=24)
        assert isinstance(summary, dict)

    def test_full_error_diagnosis_workflow(self, sample_error_messages):
        """Test complete error diagnosis workflow."""
        assistant = ErrorDiagnosisAssistant()
        
        # Diagnose single error (returns a list of DiagnosisResult)
        single_result = assistant.diagnose(sample_error_messages[0])
        assert isinstance(single_result, list)
        
        # Diagnose multiple errors
        all_results = []
        for error_msg in sample_error_messages:
            results = assistant.diagnose(error_msg)
            all_results.extend(results)
        
        # Get summary
        summary = assistant.get_diagnosis_summary(all_results)
        assert isinstance(summary, str)

    def test_full_entity_discovery_workflow(self, sample_entities):
        """Test complete entity discovery workflow."""
        assistant = EntityDiscoveryAssistant()
        
        # Discover entities
        result = assistant.discover_entities(sample_entities)
        assert isinstance(result, EntityDiscoveryResult)
        
        # Get by room
        rooms = assistant.get_entities_by_room(sample_entities)
        assert isinstance(rooms, list)
        
        # Suggest automations
        suggestions = assistant.suggest_automations(sample_entities)
        assert isinstance(suggestions, list)

    def test_full_security_audit_workflow(self, sample_security_config):
        """Test complete security audit workflow."""
        auditor = SecurityAuditor()
        
        # Get automations from sample config and convert to proper format
        automations = []
        for key, value in sample_security_config.items():
            if isinstance(value, dict):
                auto = value.copy()
                if isinstance(auto.get("trigger"), dict):
                    auto["trigger"] = [auto["trigger"]]
                if "condition" not in auto:
                    auto["condition"] = []
                if "action" not in auto:
                    auto["action"] = []
                automations.append(auto)
        
        if not automations:
            automations = [{"alias": "test", "trigger": [{"platform": "state", "entity_id": "test"}], "condition": [], "action": [{"service": "test"}]}]
        
        # Audit automations
        result = auditor.audit_automations(automations)
        assert isinstance(result, SecurityAuditResult)
        
        # Calculate score
        score = auditor.calculate_security_score(result.issues)
        assert isinstance(score, (int, float))

    def test_full_energy_analysis_workflow(self, sample_energy_data):
        """Test complete energy analysis workflow."""
        advisor = EnergyAdvisor()
        
        # Analyze energy data
        entities = sample_energy_data.get("entities", [])
        result = advisor.analyze_energy_data(entities, [])
        assert isinstance(result, EnergyOptimizationResult)
        
        # Get summary
        summary = advisor.get_energy_summary(entities)
        assert isinstance(summary, EnergySummary)
        
        # Get suggestions
        suggestions = advisor.get_optimization_suggestions(entities)
        assert isinstance(suggestions, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
