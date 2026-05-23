"""Log file analyzer for Home Assistant.

This module provides functionality to analyze Home Assistant logs,
identify errors, warnings, patterns, and generate AI-friendly summaries.
"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import yaml

_LOGGER = logging.getLogger(__name__)


class LogEntry:
    """Represents a single log entry."""

    def __init__(
        self,
        timestamp: datetime,
        level: str,
        logger_name: str,
        message: str,
        exc_info: Optional[str] = None,
    ):
        self.timestamp = timestamp
        self.level = level.upper()
        self.logger_name = logger_name
        self.message = message
        self.exc_info = exc_info

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "logger": self.logger_name,
            "message": self.message,
            "exc_info": self.exc_info,
        }

    def __str__(self) -> str:
        return f"[{self.timestamp}] {self.level}: {self.logger_name} - {self.message}"


class LogPattern:
    """Represents a detected pattern in logs."""

    def __init__(
        self, pattern: str, count: int, examples: List[str], severity: str = "info"
    ):
        self.pattern = pattern
        self.count = count
        self.examples = examples[:5]  # Limit examples
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern": self.pattern,
            "count": self.count,
            "examples": self.examples,
            "severity": self.severity,
        }


class LogAnalyzerResult:
    """Result of log analysis."""

    def __init__(
        self,
        summary: Optional[Dict[str, Any]] = None,
        errors: Optional[List[LogEntry]] = None,
        warnings: Optional[List[LogEntry]] = None,
        patterns: Optional[List[LogPattern]] = None,
        recommendations: Optional[List[str]] = None,
        ai_summary: Optional[str] = None,
    ):
        self.summary = summary or {}
        self.errors = errors or []
        self.warnings = warnings or []
        self.patterns = patterns or []
        self.recommendations = recommendations or []
        self.ai_summary = ai_summary or ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary": self.summary,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "pattern_count": len(self.patterns),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "patterns": [p.to_dict() for p in self.patterns],
            "recommendations": self.recommendations,
            "ai_summary": self.ai_summary,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format for display."""
        lines = ["## Home Assistant Log Analysis"]
        lines.append("")

        # Summary
        summary = self.summary
        if summary:
            lines.append("### Summary")
            lines.append(f"- **Total Entries Analyzed:** {summary.get('total_entries', 0)}")
            lines.append(f"- **Time Range:** {summary.get('start_time', 'N/A')} to {summary.get('end_time', 'N/A')}")
            lines.append(f"- **Errors:** {len(self.errors)}")
            lines.append(f"- **Warnings:** {len(self.warnings)}")
            lines.append(f"- **Patterns Detected:** {len(self.patterns)}")
            lines.append("")

        # AI Summary
        if self.ai_summary:
            lines.append("### AI Analysis")
            lines.append(self.ai_summary)
            lines.append("")

        # Errors
        if self.errors:
            lines.append("### Errors")
            for error in self.errors[:20]:  # Limit display
                lines.append(f"- **[{error.timestamp}]** {error.logger_name}: {error.message}")
            if len(self.errors) > 20:
                lines.append(f"- ... and {len(self.errors) - 20} more errors")
            lines.append("")

        # Warnings
        if self.warnings:
            lines.append("### Warnings")
            for warning in self.warnings[:20]:  # Limit display
                lines.append(f"- **[{warning.timestamp}]** {warning.logger_name}: {warning.message}")
            if len(self.warnings) > 20:
                lines.append(f"- ... and {len(self.warnings) - 20} more warnings")
            lines.append("")

        # Patterns
        if self.patterns:
            lines.append("### Detected Patterns")
            for pattern in self.patterns:
                severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                    pattern.severity, "⚪"
                )
                lines.append(f"- {severity_emoji} **{pattern.pattern}** (occurred {pattern.count} times)")
                for example in pattern.examples[:2]:
                    lines.append(f"  - `{example[:100]}...`" if len(example) > 100 else f"  - `{example}`")
            lines.append("")

        # Recommendations
        if self.recommendations:
            lines.append("### Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)


class LogAnalyzer:
    """Analyzes Home Assistant logs."""

    # Common error patterns and their likely causes
    ERROR_PATTERNS = {
        r"Entity .* is not valid": {
            "severity": "high",
            "message": "Invalid entity reference",
            "suggestion": "Check entity IDs in your automation or configuration",
        },
        r"Service .* does not exist": {
            "severity": "high",
            "message": "Non-existent service called",
            "suggestion": "Verify the service domain and name are correct",
        },
        r"Timeout": {
            "severity": "medium",
            "message": "Operation timed out",
            "suggestion": "Check network connectivity or increase timeout value",
        },
        r"Connection refused": {
            "severity": "high",
            "message": "Connection refused",
            "suggestion": "Ensure the target service is running and accessible",
        },
        r"Unauthorized|401|403": {
            "severity": "high",
            "message": "Authentication/Authorization failed",
            "suggestion": "Check API keys, tokens, or credentials",
        },
        r"Entity not found|no entity": {
            "severity": "medium",
            "message": "Entity not found",
            "suggestion": "Verify the entity exists and is not disabled",
        },
        r"ValueError|invalid value": {
            "severity": "medium",
            "message": "Invalid value",
            "suggestion": "Check the value being passed matches expected format",
        },
        r"KeyError|AttributeError": {
            "severity": "medium",
            "message": "Code error",
            "suggestion": "This may be a bug in a custom integration",
        },
        r"OOMKilled|Out of memory": {
            "severity": "critical",
            "message": "Out of memory",
            "suggestion": "Increase system memory or reduce load",
        },
        r"Disk space|No space left": {
            "severity": "critical",
            "message": "Disk space full",
            "suggestion": "Free up disk space or expand storage",
        },
    }

    def __init__(self, hass):
        """Initialize the log analyzer."""
        self.hass = hass

    def get_log_entries(
        self,
        hours: int = 24,
        levels: Optional[List[str]] = None,
        search_terms: Optional[List[str]] = None,
        limit: int = 1000,
    ) -> List[LogEntry]:
        """Get log entries from Home Assistant.
        
        Args:
            hours: Number of hours to look back
            levels: Log levels to include (ERROR, WARNING, etc.)
            search_terms: Terms to search for in messages
            limit: Maximum number of entries to return
            
        Returns:
            List of LogEntry objects
        """
        if levels is None:
            levels = ["ERROR", "WARNING", "INFO"]

        try:
            # Try to get logs via WebSocket API or recorder
            entries = self._get_logs_from_api(hours, levels, limit)
            
            # Filter by search terms if specified
            if search_terms and entries:
                entries = [
                    entry
                    for entry in entries
                    if any(
                        term.lower() in entry.message.lower()
                        for term in search_terms
                    )
                ]
            
            return entries[:limit]
        except Exception as e:
            _LOGGER.error(f"Failed to get log entries: {e}")
            return []

    def _get_logs_from_api(
        self, hours: int, levels: List[str], limit: int
    ) -> List[LogEntry]:
        """Get logs from Home Assistant API."""
        entries = []
        
        try:
            # Try using the WebSocket API
            ws_api = self.hass.data.get("websocket_api")
            if ws_api:
                # Use the recorder/history if available
                entries = self._get_from_recorder(hours, levels, limit)
            
            # Fallback: try to read log file directly
            if not entries:
                entries = self._read_log_file(hours, levels, limit)
                
        except Exception as e:
            _LOGGER.warning(f"Failed to get logs from API: {e}")
            # Final fallback
            entries = self._read_log_file(hours, levels, limit)
        
        return entries

    def _get_from_recorder(
        self, hours: int, levels: List[str], limit: int
    ) -> List[LogEntry]:
        """Try to get logs from the recorder."""
        entries = []
        
        try:
            # Access the event bus to get recent events
            from homeassistant.components.recorder import get_instance
            
            # This is a simplified approach - in production you'd use the proper
            # recorder API to query the events table
            _LOGGER.debug("Attempting to get logs from recorder")
            
        except ImportError:
            _LOGGER.debug("Recorder component not available")
        
        return entries

    def _read_log_file(
        self, hours: int, levels: List[str], limit: int
    ) -> List[LogEntry]:
        """Read logs from the Home Assistant log file."""
        entries = []
        
        try:
            # Get the log file path
            log_path = self.hass.config.path("home-assistant.log")
            
            if not os.path.exists(log_path):
                _LOGGER.warning(f"Log file not found: {log_path}")
                return entries
            
            # Calculate time threshold
            threshold = datetime.now() - timedelta(hours=hours)
            
            # Common log format: 2024-01-15 10:30:45.123 ERROR [logger] Message
            log_pattern = re.compile(
                r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d+)\s"
                r"(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s"
                r"\[([^\]]+)\]\s"
                r"(.*)"
            )
            
            with open(log_path, "r", encoding="utf-8") as f:
                # Read last 10000 lines to handle large files
                lines = f.readlines()[-10000:]
                
                for line in lines:
                    match = log_pattern.match(line.strip())
                    if match:
                        timestamp_str, level, logger, message = match.groups()
                        
                        try:
                            timestamp = datetime.strptime(
                                timestamp_str, "%Y-%m-%d %H:%M:%S.%f"
                            )
                        except ValueError:
                            continue
                        
                        # Filter by time
                        if timestamp < threshold:
                            continue
                        
                        # Filter by level
                        if level not in levels:
                            continue
                        
                        entry = LogEntry(
                            timestamp=timestamp,
                            level=level,
                            logger_name=logger,
                            message=message,
                        )
                        entries.append(entry)
                        
                        if len(entries) >= limit:
                            break
            
        except Exception as e:
            _LOGGER.error(f"Failed to read log file: {e}")
        
        return entries

    def analyze_logs(
        self,
        hours: int = 24,
        search_terms: Optional[List[str]] = None,
        generate_ai_summary: bool = True,
    ) -> LogAnalyzerResult:
        """Analyze logs and generate report.
        
        Args:
            hours: Number of hours to analyze
            search_terms: Optional terms to filter by
            generate_ai_summary: Whether to generate AI summary
            
        Returns:
            LogAnalyzerResult with analysis
        """
        # Get log entries
        entries = self.get_log_entries(
            hours=hours,
            levels=["ERROR", "WARNING", "CRITICAL"],
            search_terms=search_terms,
            limit=5000,
        )
        
        if not entries:
            return LogAnalyzerResult(
                summary={
                    "total_entries": 0,
                    "start_time": "N/A",
                    "end_time": "N/A",
                },
                ai_summary="No errors or warnings found in the specified time range.",
            )
        
        # Separate errors and warnings
        errors = [e for e in entries if e.level in ("ERROR", "CRITICAL")]
        warnings = [e for e in entries if e.level == "WARNING"]
        
        # Calculate summary
        summary = {
            "total_entries": len(entries),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "start_time": entries[-1].timestamp.isoformat() if entries else "N/A",
            "end_time": entries[0].timestamp.isoformat() if entries else "N/A",
        }
        
        # Detect patterns
        patterns = self._detect_patterns(entries)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(errors, warnings, patterns)
        
        # Build result
        result = LogAnalyzerResult(
            summary=summary,
            errors=errors,
            warnings=warnings,
            patterns=patterns,
            recommendations=recommendations,
        )
        
        # Generate AI summary if requested
        if generate_ai_summary:
            result.ai_summary = self._generate_summary_text(result)
        
        return result

    def _detect_patterns(self, entries: List[LogEntry]) -> List[LogPattern]:
        """Detect patterns in log entries."""
        pattern_counts: Dict[str, LogPattern] = {}
        
        for entry in entries:
            # Check against known error patterns
            for pattern_regex, pattern_info in self.ERROR_PATTERNS.items():
                if re.search(pattern_regex, entry.message, re.IGNORECASE):
                    pattern_key = pattern_info["message"]
                    
                    if pattern_key in pattern_counts:
                        pattern_counts[pattern_key].count += 1
                        if len(pattern_counts[pattern_key].examples) < 3:
                            pattern_counts[pattern_key].examples.append(
                                f"[{entry.level}] {entry.message[:100]}"
                            )
                    else:
                        pattern_counts[pattern_key] = LogPattern(
                            pattern=pattern_info["message"],
                            count=1,
                            examples=[f"[{entry.level}] {entry.message[:100]}"],
                            severity=pattern_info["severity"],
                        )
            
            # Detect repeated messages (generic pattern)
            if entry.message not in pattern_counts:
                short_msg = re.sub(r"\d+", "N", entry.message[:100])
                if short_msg in pattern_counts:
                    pattern_counts[short_msg].count += 1
                else:
                    pattern_counts[short_msg] = LogPattern(
                        pattern=entry.message[:80],
                        count=1,
                        examples=[f"[{entry.level}] {entry.message[:100]}"],
                        severity="low",
                    )
        
        # Sort by count
        return sorted(
            pattern_counts.values(), key=lambda p: p.count, reverse=True
        )[:20]  # Top 20 patterns

    def _generate_recommendations(
        self,
        errors: List[LogEntry],
        warnings: List[LogEntry],
        patterns: List[LogPattern],
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Check for critical patterns
        critical_patterns = [p for p in patterns if p.severity == "critical"]
        if critical_patterns:
            recommendations.append(
                "🔴 CRITICAL: Immediate attention required for the following patterns:"
            )
            for p in critical_patterns:
                recommendations.append(f"   - {p.pattern} ({p.count} occurrences)")
        
        # Check for frequent errors
        frequent_errors = [p for p in patterns if p.count > 10]
        if frequent_errors:
            recommendations.append(
                "⚠️ High-frequency errors detected. Consider investigating:"
            )
            for p in frequent_errors[:5]:
                recommendations.append(f"   - {p.pattern} ({p.count} times)")
        
        # Check for specific error types
        error_messages = [e.message for e in errors]
        if any("Entity not found" in msg for msg in error_messages):
            recommendations.append(
                "💡 Several 'entity not found' errors. Check your automation entity IDs."
            )
        
        if any("Timeout" in msg for msg in error_messages):
            recommendations.append(
                "💡 Timeout errors detected. Check network connectivity or increase timeouts."
            )
        
        if any("Connection refused" in msg for msg in error_messages):
            recommendations.append(
                "💡 Connection refused errors. Ensure target services are running."
            )
        
        # General recommendations
        if len(errors) > 50:
            recommendations.append(
                "📊 High number of errors detected. Consider reviewing recent changes."
            )
        
        if not recommendations:
            recommendations.append("✅ No critical issues detected. System appears healthy.")
        
        return recommendations

    def _generate_summary_text(self, result: LogAnalyzerResult) -> str:
        """Generate a natural language summary of the log analysis."""
        summary = result.summary
        lines = []
        
        total = summary.get("total_entries", 0)
        error_count = result.errors.__len__()
        warning_count = result.warnings.__len__()
        
        if total == 0:
            return "No errors or warnings were found in the analyzed time period. Your system appears to be running cleanly."
        
        lines.append(
            f"Over the analyzed period, I found {error_count} errors and {warning_count} warnings."
        )
        
        if error_count > 0:
            # Group errors by type
            error_types: Dict[str, int] = {}
            for error in result.errors:
                # Simplify error message to group similar ones
                simplified = re.sub(r"\d+", "N", error.message[:80])
                error_types[simplified] = error_types.get(simplified, 0) + 1
            
            if error_types:
                lines.append("\nMost common errors:")
                for error_type, count in sorted(
                    error_types.items(), key=lambda x: x[1], reverse=True
                )[:5]:
                    lines.append(f"- {count}x: {error_type}")
        
        if result.recommendations:
            lines.append("\nRecommendations:")
            for rec in result.recommendations:
                lines.append(f"- {rec}")
        
        return "\n".join(lines)

    def search_logs(
        self,
        search_term: str,
        hours: int = 24,
        levels: Optional[List[str]] = None,
    ) -> List[LogEntry]:
        """Search logs for a specific term.
        
        Args:
            search_term: Term to search for
            hours: Number of hours to look back
            levels: Log levels to include
            
        Returns:
            List of matching LogEntry objects
        """
        return self.get_log_entries(
            hours=hours,
            levels=levels or ["ERROR", "WARNING", "INFO"],
            search_terms=[search_term],
            limit=100,
        )

    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get a quick summary of recent errors.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dictionary with error summary
        """
        result = self.analyze_logs(hours=hours, generate_ai_summary=False)
        
        return {
            "total_errors": len(result.errors),
            "total_warnings": len(result.warnings),
            "top_errors": [
                {"message": e.message[:100], "count": 1}
                for e in result.errors[:10]
            ],
            "patterns": [p.to_dict() for p in result.patterns[:10]],
        }
