# AI Agent HA - Enhancement Architecture Documents

This directory contains the detailed architecture specifications for five enhancements to the `ai_agent_ha` Home Assistant integration.

## Quick Links

| # | Enhancement | File | Priority |
|---|-------------|------|----------|
| 1 | **Prompt Compacting** | [`01-prompt-compacting.md`](01-prompt-compacting.md) | 🔴 Critical (fixes context overflow) |
| 2 | **Output Formatting** | [`02-output-formatting.md`](02-output-formatting.md) | 🟡 High (improves UX) |
| 3 | **Chat History Management** | [`03-chat-history.md`](03-chat-history.md) | 🟡 High (improves UX) |
| 4 | **Permission System** | [`04-permission-system.md`](04-permission-system.md) | 🟢 Medium (security) |
| 5 | **Multimedia Support** | [`05-multimedia-support.md`](05-multimedia-support.md) | 🔵 Low (nice-to-have) |

## Master Document

A single comprehensive document containing all enhancements plus cross-cutting concerns is available at:
- [`../enhancements-architecture.md`](../enhancements-architecture.md)

## Current Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    ai_agent_ha-panel.js                  │
│               (LitElement Web Component)                 │
│  ┌─────────┐ ┌──────────────┐ ┌──────────────────────┐  │
│  │ Messages│ │Prompt History│ │Provider/Automation UI│  │
│  └────┬────┘ └──────┬───────┘ └──────────┬───────────┘  │
│       │             │                    │               │
└───────┼─────────────┼────────────────────┼───────────────┘
        │             │                    │
   WebSocket      hass.callService    hass.callService
        │             │                    │
┌───────┼─────────────┼────────────────────┼───────────────┐
│       ▼             ▼                    ▼               │
│                  __init__.py                             │
│         (Service Handlers & Integration Setup)           │
│       │                                                  │
│       ▼                                                  │
│                  agent.py                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │           AiAgentHaAgent                         │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │   │
│  │  │BaseAI-   │ │Sub-modules│ │History           │ │   │
│  │  │Client    │ │(yaml, log,│ │save/load         │ │   │
│  │  │hierarchy │ │energy...) │ │                  │ │   │
│  │  └──────────┘ └──────────┘ └──────────────────┘ │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  const.py          config_flow.py        services.yaml   │
│  (Constants)       (Config UI)         (Service defs)    │
└──────────────────────────────────────────────────────────┘
```

### Key Integration Points

| Component | File | Role |
|-----------|------|------|
| Frontend | [`ai_agent_ha-panel.js`](../../custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js) | LitElement chat UI, WebSocket event listener |
| Agent Core | [`agent.py`](../../custom_components/ai_agent_ha/agent.py) | AI client management, `process_query()`, sub-modules |
| Integration | [`__init__.py`](../../custom_components/ai_agent_ha/__init__.py) | Service registration, `async_setup_entry` |
| Config | [`config_flow.py`](../../custom_components/ai_agent_ha/config_flow.py) | Config & Options flow handlers |
| Constants | [`const.py`](../../custom_components/ai_agent_ha/const.py) | Domain, provider configs, feature flags |

## Implementation Order & Dependencies

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

## File Manifest

| File | Action | Enhancement(s) |
|------|--------|----------------|
| [`const.py`](../../custom_components/ai_agent_ha/const.py) | **Modify** | #1, #3, #4, #5 |
| [`config_flow.py`](../../custom_components/ai_agent_ha/config_flow.py) | **Modify** | #1, #4, #5 |
| [`agent.py`](../../custom_components/ai_agent_ha/agent.py) | **Modify** | #1, #4, #5 |
| [`__init__.py`](../../custom_components/ai_agent_ha/__init__.py) | **Modify** | #3, #4 |
| [`services.yaml`](../../custom_components/ai_agent_ha/services.yaml) | **Modify** | #3, #5 |
| [`manifest.json`](../../custom_components/ai_agent_ha/manifest.json) | **Modify** | #2 (minimal - CDN loaded) |
| [`ai_agent_ha-panel.js`](../../custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js) | **Modify** | #2, #3, #4, #5 |
| [`prompt_compactor.py`](../../custom_components/ai_agent_ha/prompt_compactor.py) | **Create** | #1 |
| [`chat_history.py`](../../custom_components/ai_agent_ha/chat_history.py) | **Create** | #3 |
| [`permissions.py`](../../custom_components/ai_agent_ha/permissions.py) | **Create** | #4 |

## Backward Compatibility Notes

1. **Prompt Compacting**: Feature is opt-out via config. Default threshold (70%) prevents unexpected behavior.
2. **Output Formatting**: `_hasMarkdown()` check ensures plain text still renders correctly. No config migration needed.
3. **Chat History**: New `ChatHistoryManager` coexists with existing `save_user_prompt_history`/`load_user_prompt_history`. Existing storage keys are not modified. Migration path: old `ai_agent_ha_history_{user_id}` stores continue to work; new conversations use the manager.
4. **Permission System**: Default mode is `"prompt"` (most conservative). Existing behavior is preserved for whitelisted actions.
5. **Multimedia**: Image parameter is optional, default empty list. Text-only queries are unaffected.

## Testing Strategy

| Enhancement | Unit Tests | Integration Tests | Manual Tests |
|-------------|-----------|-------------------|-------------|
| #1 Compacting | `PromptCompactor.estimate_tokens()`, `compact_conversation()` | Large conversation → compaction triggered | Real long conversation |
| #2 Formatting | `_hasMarkdown()`, `_sanitize()` | Full render with markdown response | Various markdown inputs |
| #3 History | `ChatHistoryManager` CRUD | Service call round-trip | History browser UI |
| #4 Permissions | `PermissionChecker.check_action()` | Full query → permission → approve flow | Dialog interactions |
| #5 Multimedia | `_validate_image()` | Image upload → query → response | Real camera image upload |

## Implementation Status

| Phase | Feature | Status | Files |
|-------|---------|--------|-------|
| 2 | Response Validation | ✅ Complete | `response_validator.py` |
| 3 | Error Recovery | ✅ Complete | `error_recovery.py` |
| 4 | Action Execution Framework | ✅ Complete | `action_executor.py` |
| 5 | Performance Optimizations | ✅ Complete | `performance.py` |
| 6 | UX Enhancements | ✅ Complete | `ai_agent_ha-panel.js` |
