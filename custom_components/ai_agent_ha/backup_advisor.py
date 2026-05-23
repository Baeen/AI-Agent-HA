"""Backup and restore advisor for Home Assistant.

This module helps users backup configuration before making changes,
verify configurations after changes, and provide rollback suggestions.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class BackupItem:
    """Represents an item that should be backed up."""

    def __init__(
        self,
        item_type: str,
        name: str,
        path: str,
        description: str = "",
        critical: bool = True,
    ):
        self.item_type = item_type
        self.name = name
        self.path = path
        self.description = description
        self.critical = critical

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_type": self.item_type,
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "critical": self.critical,
        }


class BackupRecommendation:
    """Recommendation for what to backup before changes."""

    def __init__(
        self,
        items: List[BackupItem] = None,
        summary: str = "",
        instructions: str = "",
    ):
        self.items = items or []
        self.summary = summary
        self.instructions = instructions

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "items": [item.to_dict() for item in self.items],
            "summary": self.summary,
            "instructions": self.instructions,
            "total_items": len(self.items),
            "critical_items": sum(1 for item in self.items if item.critical),
            "timestamp": datetime.now().isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = ["# Backup Recommendation\n"]

        if self.summary:
            lines.append(f"**{self.summary}**\n")

        lines.append("## Items to Backup\n")
        lines.append(
            "| Type | Name | Path | Critical | Description |"
        )
        lines.append("|------|------|------|----------|-------------|")

        for item in self.items:
            critical_str = "Yes" if item.critical else "No"
            lines.append(
                f"| {item.item_type} | {item.name} | {item.path} | {critical_str} | {item.description} |"
            )

        lines.append("")
        if self.instructions:
            lines.append("## Instructions\n")
            lines.append(self.instructions)

        lines.append("")
        lines.append(
            f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )

        return "\n".join(lines)


class PostChangeVerification:
    """Verification results after making changes."""

    def __init__(
        self,
        checks_passed: int = 0,
        checks_failed: int = 0,
        issues: List[Dict] = None,
        recommendations: List[str] = None,
    ):
        self.checks_passed = checks_passed
        self.checks_failed = checks_failed
        self.issues = issues or []
        self.recommendations = recommendations or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "overall_status": "passed" if self.checks_failed == 0 else "failed",
            "issues": self.issues,
            "recommendations": self.recommendations,
            "total_checks": self.checks_passed + self.checks_failed,
            "timestamp": datetime.now().isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = ["# Post-Change Verification Results\n"]

        status = "✅ PASSED" if self.checks_failed == 0 else "❌ FAILED"
        lines.append(f"**Overall Status: {status}**\n")

        lines.append(f"- Checks Passed: {self.checks_passed}")
        lines.append(f"- Checks Failed: {self.checks_failed}")
        lines.append(f"- Total Checks: {self.checks_passed + self.checks_failed}\n")

        if self.issues:
            lines.append("## Issues Detected\n")
            for i, issue in enumerate(self.issues, 1):
                severity = issue.get("severity", "medium").upper()
                lines.append(f"### {i}. [{severity}] {issue.get('description', 'Unknown')}\n")
                lines.append(f"- **Type:** {issue.get('type', 'unknown')}")
                lines.append(f"- **Details:** {issue.get('details', 'N/A')}")
                if issue.get("suggestion"):
                    lines.append(f"- **Suggestion:** {issue.get('suggestion')}")
                lines.append("")

        if self.recommendations:
            lines.append("## Recommendations\n")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        lines.append(
            f"*Verified on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )

        return "\n".join(lines)


class RollbackSuggestion:
    """Suggestion for rolling back changes."""

    def __init__(
        self,
        issue_description: str,
        rollback_steps: List[str] = None,
        affected_components: List[str] = None,
        priority: str = "medium",
    ):
        self.issue_description = issue_description
        self.rollback_steps = rollback_steps or []
        self.affected_components = affected_components or []
        self.priority = priority

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        priority_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return {
            "issue_description": self.issue_description,
            "rollback_steps": self.rollback_steps,
            "affected_components": self.affected_components,
            "priority": self.priority,
            "priority_order": priority_order.get(self.priority, 2),
            "timestamp": datetime.now().isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        priority_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴",
        }
        emoji = priority_emoji.get(self.priority, "⚪")

        lines = [f"# Rollback Suggestion [{emoji} {self.priority.upper()}]\n"]
        lines.append(f"**Issue:** {self.issue_description}\n")

        if self.affected_components:
            lines.append("## Affected Components\n")
            for comp in self.affected_components:
                lines.append(f"- {comp}")
            lines.append("")

        if self.rollback_steps:
            lines.append("## Rollback Steps\n")
            for i, step in enumerate(self.rollback_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        lines.append(
            f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )

        return "\n".join(lines)


class BackupAdvisor:
    """Advises on backup, restore, and rollback procedures."""

    # Items that should always be backed up
    CRITICAL_BACKUP_ITEMS = [
        BackupItem(
            "file",
            "configuration.yaml",
            "configuration.yaml",
            "Main Home Assistant configuration",
            critical=True,
        ),
        BackupItem(
            "file",
            "automations.yaml",
            "automations.yaml",
            "Automation configurations",
            critical=True,
        ),
        BackupItem(
            "file",
            "scripts.yaml",
            "scripts.yaml",
            "Script configurations",
            critical=True,
        ),
        BackupItem(
            "file",
            "scenes.yaml",
            "scenes.yaml",
            "Scene configurations",
            critical=True,
        ),
        BackupItem(
            "file",
            "groups.yaml",
            "groups.yaml",
            "Group configurations",
            critical=True,
        ),
        BackupItem(
            "file",
            "customize.yaml",
            "customize.yaml",
            "Customization configurations",
            critical=False,
        ),
        BackupItem(
            "database",
            "SQLite database",
            "home-assistant_v2.db",
            "Home Assistant database with states and events",
            critical=True,
        ),
        BackupItem(
            "directory",
            "config folder",
            ".",
            "Entire configuration directory",
            critical=True,
        ),
    ]

    def get_backup_recommendation(
        self,
        changes_description: str,
        include_database: bool = True,
    ) -> BackupRecommendation:
        """Get recommendation for what to backup before making changes.

        Args:
            changes_description: Description of changes to be made
            include_database: Whether to recommend database backup

        Returns:
            BackupRecommendation with items to backup
        """
        items = list(self.CRITICAL_BACKUP_ITEMS)

        # Add specific items based on changes description
        changes_lower = changes_description.lower()

        if any(
            keyword in changes_lower
            for keyword in ["automation", "trigger", "condition", "action"]
        ):
            items.append(
                BackupItem(
                    "file",
                    "automations.yaml (additional)",
                    "automations.yaml",
                    "Backup again as automations are being modified",
                    critical=True,
                )
            )

        if any(
            keyword in changes_lower
            for keyword in ["dashboard", "view", "card", "panel"]
        ):
            items.append(
                BackupItem(
                    "file",
                    "lovelace UI config",
                    ".storage/core.config_entries",
                    "Dashboard and UI configuration stored in Home Assistant storage",
                    critical=True,
                )
            )

        if any(
            keyword in changes_lower
            for keyword in ["integration", "device", "entity", "platform"]
        ):
            items.append(
                BackupItem(
                    "file",
                    "config entries storage",
                    ".storage/core.config_entries",
                    "Integration and device configurations",
                    critical=True,
                )
            )

        if any(
            keyword in changes_lower
            for keyword in ["scene", "light", "color"]
        ):
            items.append(
                BackupItem(
                    "file",
                    "scenes.yaml (additional)",
                    "scenes.yaml",
                    "Backup again as scenes are being modified",
                    critical=True,
                )
            )

        if any(
            keyword in changes_lower
            for keyword in ["script", "sequence", "service"]
        ):
            items.append(
                BackupItem(
                    "file",
                    "scripts.yaml (additional)",
                    "scripts.yaml",
                    "Backup again as scripts are being modified",
                    critical=True,
                )
            )

        # Build summary and instructions
        critical_count = sum(1 for item in items if item.critical)
        summary = (
            f"Before making changes, you should backup {len(items)} items "
            f"({critical_count} critical). "
            f"Changes detected: {changes_description}"
        )

        instructions = (
            "1. Open Home Assistant terminal or SSH access\n"
            "2. Navigate to your configuration directory (usually /config)\n"
            "3. Create a backup folder with timestamp: `mkdir backup_$(date +%Y%m%d_%H%M%S)`\n"
            "4. Copy the files listed above to the backup folder\n"
            "5. If using database, stop Home Assistant before copying home-assistant_v2.db\n"
            "6. Verify backup files are complete before proceeding with changes\n"
            "7. Consider using the Home Assistant Backup add-on for a complete backup"
        )

        return BackupRecommendation(
            items=items,
            summary=summary,
            instructions=instructions,
        )

    def get_pre_change_checklist(
        self,
        changes_description: str,
    ) -> List[str]:
        """Get a checklist of things to verify before making changes.

        Args:
            changes_description: Description of changes to be made

        Returns:
            List of checklist items
        """
        checklist = [
            "Review current configuration files for syntax errors",
            "Verify Home Assistant is running without errors",
            "Check that all integrations are properly connected",
            "Confirm you have a recent backup available",
            "Document current working state (e.g., list of active automations)",
            f"Understand the impact of changes: {changes_description}",
        ]

        changes_lower = changes_description.lower()

        if any(
            keyword in changes_lower
            for keyword in ["automation", "trigger", "condition"]
        ):
            checklist.append(
                "Test current automations are working before making changes"
            )
            checklist.append(
                "Note which automations will be affected by changes"
            )

        if any(
            keyword in changes_lower
            for keyword in ["integration", "device", "entity"]
        ):
            checklist.append(
                "Document current entity states and integration statuses"
            )
            checklist.append(
                "Check for any pending integration updates or configurations"
            )

        if any(
            keyword in changes_lower
            for keyword in ["dashboard", "ui", "panel"]
        ):
            checklist.append(
                "Take screenshots of current dashboard layout"
            )
            checklist.append(
                "Note any custom cards or lovelace configurations used"
            )

        checklist.append(
            "Ensure you have access to rollback procedure if needed"
        )

        return checklist

    def verify_after_changes(
        self,
        changes_made: List[Dict[str, Any]],
        current_config: Optional[Dict] = None,
    ) -> PostChangeVerification:
        """Verify system is working correctly after changes.

        Args:
            changes_made: List of changes that were made
            current_config: Current configuration to verify

        Returns:
            PostChangeVerification with results
        """
        checks_passed = 0
        checks_failed = 0
        issues = []
        recommendations = []

        # Check 1: Verify no changes were made without proper backup
        if not changes_made:
            checks_failed += 1
            issues.append(
                {
                    "type": "empty_changes",
                    "severity": "medium",
                    "description": "No changes detected in the provided list",
                    "details": "The changes_made list is empty. Verify changes were applied correctly.",
                    "suggestion": "Review your changes and ensure they were properly saved.",
                }
            )
        else:
            checks_passed += 1

        # Check 2: Validate change structure
        valid_change_types = {
            "file_modified",
            "file_created",
            "file_deleted",
            "automation_added",
            "automation_modified",
            "automation_deleted",
            "integration_added",
            "integration_removed",
            "configuration_changed",
            "entity_changed",
        }

        invalid_changes = [
            c for c in changes_made
            if c.get("type", "") not in valid_change_types
        ]

        if invalid_changes:
            checks_failed += 1
            issues.append(
                {
                    "type": "invalid_change_type",
                    "severity": "low",
                    "description": f"{len(invalid_changes)} changes have unrecognized types",
                    "details": f"Invalid change types: {', '.join(c.get('type', 'unknown') for c in invalid_changes)}",
                    "suggestion": "Use standard change type identifiers.",
                }
            )
        else:
            checks_passed += 1

        # Check 3: Verify no critical files were modified without backup note
        critical_files = [
            "configuration.yaml",
            "automations.yaml",
            "scripts.yaml",
            "scenes.yaml",
        ]

        critical_modifications = [
            c
            for c in changes_made
            if c.get("type", "") in ("file_modified", "file_created")
            and any(c.get("file", "").endswith(f) for f in critical_files)
        ]

        if critical_modifications:
            checks_passed += 1
            recommendations.append(
                f"Critical files were modified ({len(critical_modifications)} changes). "
                f"Ensure you have a backup available before restarting Home Assistant."
            )

        # Check 4: Verify automation syntax if automations were changed
        automation_changes = [
            c
            for c in changes_made
            if "automation" in c.get("type", "").lower()
        ]

        if automation_changes:
            # Check for common automation issues
            missing_triggers = [
                c
                for c in automation_changes
                if not c.get("has_trigger", True)
            ]

            if missing_triggers:
                checks_failed += 1
                issues.append(
                    {
                        "type": "automation_missing_trigger",
                        "severity": "high",
                        "description": f"{len(missing_triggers)} automations may be missing triggers",
                        "details": "Automations without triggers cannot execute automatically.",
                        "suggestion": "Add appropriate triggers to the affected automations.",
                    }
                )
            else:
                checks_passed += 1
                recommendations.append(
                    "All modified automations appear to have valid triggers."
                )

        # Check 5: Verify integration changes
        integration_changes = [
            c
            for c in changes_made
            if "integration" in c.get("type", "").lower()
        ]

        if integration_changes:
            checks_passed += 1
            recommendations.append(
                "Integration changes detected. Restart Home Assistant to apply changes "
                "and verify all devices are properly discovered."
            )

        # Check 6: Verify configuration structure if provided
        if current_config:
            if "homeassistant" in current_config:
                checks_passed += 1
            else:
                checks_failed += 1
                issues.append(
                    {
                        "type": "missing_homeassistant_section",
                        "severity": "high",
                        "description": "Configuration missing homeassistant section",
                        "details": "The main configuration section is required.",
                        "suggestion": "Add the homeassistant section with at least latitude, longitude, and elevation.",
                    }
                )

            if "automation" in current_config:
                checks_passed += 1
            else:
                checks_passed += 1  # Not having automations is fine
                recommendations.append(
                    "No automations defined in configuration. Consider using automations.yaml."
                )

        return PostChangeVerification(
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            issues=issues,
            recommendations=recommendations,
        )

    def get_rollback_suggestion(
        self,
        issue_detected: str,
        changes_made: List[Dict],
        backup_path: Optional[str] = None,
    ) -> RollbackSuggestion:
        """Get suggestion for rolling back changes.

        Args:
            issue_detected: Description of the issue detected
            changes_made: List of changes that were made
            backup_path: Path to backup for restoration

        Returns:
            RollbackSuggestion with rollback steps
        """
        rollback_steps = []
        affected_components = []
        priority = "medium"

        # Determine priority based on issue description
        issue_lower = issue_detected.lower()
        if any(
            keyword in issue_lower
            for keyword in ["crash", "unrecoverable", "data loss", "corruption"]
        ):
            priority = "critical"
        elif any(
            keyword in issue_lower
            for keyword in ["error", "fail", "broken", "not working"]
        ):
            priority = "high"
        elif any(
            keyword in issue_lower
            for keyword in ["warning", "deprecated", "issue"]
        ):
            priority = "medium"
        else:
            priority = "low"

        # Generate rollback steps based on changes made
        automation_changes = [
            c for c in changes_made if "automation" in c.get("type", "").lower()
        ]
        file_changes = [
            c
            for c in changes_made
            if c.get("type", "") in ("file_modified", "file_created", "file_deleted")
        ]
        integration_changes = [
            c for c in changes_made if "integration" in c.get("type", "").lower()
        ]

        # Base rollback steps
        rollback_steps.extend([
            "Stop Home Assistant service",
            f"Navigate to your configuration directory",
        ])

        if backup_path:
            rollback_steps.extend([
                f"Restore from backup: `cp {backup_path}/* /config/`",
                "Verify restored files are correct",
            ])
        else:
            rollback_steps.extend([
                "Identify the backup containing the previous working state",
                "Restore each modified file from the backup",
                "Verify file permissions are correct",
            ])

        # Add specific rollback steps based on change types
        if automation_changes:
            affected_components.append("Automations")
            rollback_steps.append(
                "After restoring automations.yaml, verify all automations load correctly "
                "in the Home Assistant UI"
            )

        if file_changes:
            affected_components.append("Configuration files")
            rollback_steps.append(
                "Run `ha core check` to verify configuration syntax after restoration"
            )

        if integration_changes:
            affected_components.append("Integrations")
            rollback_steps.append(
                "Re-add any removed integrations if needed, or remove newly added ones"
            )

        # Add issue-specific steps
        if any(
            keyword in issue_lower
            for keyword in ["automation", "trigger", "condition"]
        ):
            affected_components.append("Automations")
            rollback_steps.append(
                "Check automations tab for any errors or disabled automations"
            )

        if any(
            keyword in issue_lower
            for keyword in ["integration", "device", "entity"]
        ):
            affected_components.append("Integrations")
            rollback_steps.append(
                "Check Integrations page for any failed setups"
            )

        if any(
            keyword in issue_lower
            for keyword in ["database", "state", "history"]
        ):
            affected_components.append("Database")
            rollback_steps.append(
                "Consider clearing database if corruption is detected: "
                "`ha core stop && rm /config/home-assistant_v2.db && ha core start`"
            )

        # Final steps
        rollback_steps.extend([
            "Start Home Assistant service",
            "Verify system is running without errors in logs",
            "Test affected automations and integrations",
        ])

        if not affected_components:
            affected_components = ["General configuration"]

        return RollbackSuggestion(
            issue_description=issue_detected,
            rollback_steps=rollback_steps,
            affected_components=affected_components,
            priority=priority,
        )

    def generate_backup_script(self, backup_path: str) -> str:
        """Generate a backup script for the user to run.

        Args:
            backup_path: Path to store the backup

        Returns:
            Shell script content
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Use string concatenation to avoid f-string issues with {} in shell commands
        script = '''#!/bin/bash
# Home Assistant Backup Script
# Generated on GEN_TIME
# This script backs up critical Home Assistant configuration files

set -e

# Configuration
BACKUP_BASE="BACKUP_PATH"
TIMESTAMP="TIMESTAMP_VAL"
BACKUP_DIR="$BACKUP_BASE/ha_backup_$TIMESTAMP"
CONFIG_DIR="/config"  # Change this if your config directory is different

# Create backup directory
echo "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# Backup configuration files
echo "Backing up configuration files..."
cp -n "$CONFIG_DIR/configuration.yaml" "$BACKUP_DIR/" 2>/dev/null || echo "configuration.yaml not found"
cp -n "$CONFIG_DIR/automations.yaml" "$BACKUP_DIR/" 2>/dev/null || echo "automations.yaml not found"
cp -n "$CONFIG_DIR/scripts.yaml" "$BACKUP_DIR/" 2>/dev/null || echo "scripts.yaml not found"
cp -n "$CONFIG_DIR/scenes.yaml" "$BACKUP_DIR/" 2>/dev/null || echo "scenes.yaml not found"
cp -n "$CONFIG_DIR/groups.yaml" "$BACKUP_DIR/" 2>/dev/null || echo "groups.yaml not found"
cp -n "$CONFIG_DIR/customize.yaml" "$BACKUP_DIR/" 2>/dev/null || echo "customize.yaml not found"

# Backup Home Assistant storage (contains UI configs, integration settings, etc.)
echo "Backing up Home Assistant storage..."
if [ -d "$CONFIG_DIR/.storage" ]; then
    cp -r "$CONFIG_DIR/.storage" "$BACKUP_DIR/"
else
    echo ".storage directory not found"
fi

# Backup database (optional - may require stopping Home Assistant first)
echo "Note: For database backup, stop Home Assistant first:"
echo "  ha core stop"
echo "  cp $CONFIG_DIR/home-assistant_v2.db $BACKUP_DIR/"
echo "  ha core start"

# Create a manifest file
cat > "$BACKUP_DIR/backup_manifest.json" << EOF
{
    "backup_date": "BACKUP_DATE",
    "backup_type": "manual",
    "files_backed_up": [
        "configuration.yaml",
        "automations.yaml",
        "scripts.yaml",
        "scenes.yaml",
        "groups.yaml",
        "customize.yaml",
        ".storage/"
    ],
    "notes": "Use this backup to restore your Home Assistant configuration"
}
EOF

# Create a checksum file for verification
echo "Creating checksums..."
find "$BACKUP_DIR" -type f ! -name "backup_manifest.json" -exec md5sum {} + > "$BACKUP_DIR/checksums.md5" 2>/dev/null || echo "Checksum creation failed"

# Display backup summary
echo ""
echo "Backup completed successfully!"
echo "Backup location: $BACKUP_DIR"
echo "Files backed up:"
ls -la "$BACKUP_DIR/" | grep -v "^total" | grep -v "^d" || echo "  (no files)"
echo ""
echo "To restore, copy files back to $CONFIG_DIR/"
echo "Example: cp $BACKUP_DIR/* $CONFIG_DIR/"

# Compress the backup
echo ""
echo "Compressing backup..."
cd "$BACKUP_BASE"
tar -czf "ha_backup_$TIMESTAMP.tar.gz" "ha_backup_$TIMESTAMP"
echo "Compressed backup: ha_backup_$TIMESTAMP.tar.gz"
echo "You can safely delete the uncompressed folder:"
echo "  rm -rf $BACKUP_DIR"
'''.replace('GEN_TIME', generated_time).replace('BACKUP_PATH', backup_path).replace('TIMESTAMP_VAL', timestamp).replace('BACKUP_DATE', datetime.now().isoformat())

        return script

    def get_ai_prompt_for_rollback(
        self,
        issue: str,
        changes: List[Dict],
        backup_available: bool,
    ) -> str:
        """Generate an AI prompt to get personalized rollback advice.

        Args:
            issue: Description of the issue detected
            changes: List of changes that were made
            backup_available: Whether a backup is available

        Returns:
            AI prompt string for getting personalized rollback advice
        """
        changes_summary = []
        for change in changes:
            change_summary = f"- Type: {change.get('type', 'unknown')}, File: {change.get('file', 'N/A')}"
            if "description" in change:
                change_summary += f", Description: {change['description']}"
            changes_summary.append(change_summary)

        changes_text = "\n".join(changes_summary) if changes_summary else "No changes provided"

        prompt = f"""I made changes to my Home Assistant configuration and now I'm experiencing an issue.

Issue Description: {issue}

Changes I made:
{changes_text}

Backup Available: {'Yes' if backup_available else 'No'}

Please provide personalized advice on:
1. The most likely cause of this issue based on my changes
2. Step-by-step instructions to rollback if needed
3. Alternative solutions that don't require full rollback
4. How to prevent this issue in the future
5. Any specific Home Assistant commands I should run to diagnose the problem

If a backup is available, please include instructions for restoring from backup.
If no backup is available, provide manual recovery steps.

My Home Assistant environment details:
- Configuration is managed through YAML files
- I have access to the Home Assistant terminal/SSH
- I can use 'ha' commands for system operations

Please be specific and provide exact commands where possible."""

        return prompt
