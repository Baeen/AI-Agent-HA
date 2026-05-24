// Local vendor libraries (no internet required)
import {
  LitElement,
  html,
  css,
} from "./vendor/lit-element.js";

// Markdown rendering libraries (local, no CDN required)
import { marked } from './vendor/marked.esm.js';
import DOMPurify from './vendor/dompurify.es.mjs';

console.log("AI Agent HA Panel loading..."); // Debug log

const PROVIDERS = {
  openai: "OpenAI",
  llama: "Llama",
  gemini: "Google Gemini",
  openrouter: "OpenRouter",
  anthropic: "Anthropic",
  alter: "Alter",
  zai: "z.ai",
  local: "Local Model",
  local_ollama: "Local Ollama",
  openai_compatible: "OpenAI-Compatible",
};

class AiAgentHaPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object, reflect: false, attribute: false },
      narrow: { type: Boolean, reflect: false, attribute: false },
      panel: { type: Object, reflect: false, attribute: false },
      _messages: { type: Array, reflect: false, attribute: false },
      _isLoading: { type: Boolean, reflect: false, attribute: false },
      _error: { type: String, reflect: false, attribute: false },
      _pendingAutomation: { type: Object, reflect: false, attribute: false },
      _promptHistory: { type: Array, reflect: false, attribute: false },
      _showPredefinedPrompts: { type: Boolean, reflect: false, attribute: false },
      _showPromptHistory: { type: Boolean, reflect: false, attribute: false },
      _selectedPrompts: { type: Array, reflect: false, attribute: false },
      _selectedProvider: { type: String, reflect: false, attribute: false },
      _availableProviders: { type: Array, reflect: false, attribute: false },
      _showProviderDropdown: { type: Boolean, reflect: false, attribute: false },
      _showThinking: { type: Boolean, reflect: false, attribute: false },
      _thinkingExpanded: { type: Boolean, reflect: false, attribute: false },
      _debugInfo: { type: Object, reflect: false, attribute: false },
      _attachedImages: { type: Array, reflect: false, attribute: false },
      _imageUploadEnabled: { type: Boolean, reflect: false, attribute: false },
      _maxImagesPerMessage: { type: Number, reflect: false, attribute: false },
      // Chat history state
      _conversations: { type: Array, reflect: false, attribute: false },
      _currentConversationId: { type: String, reflect: false, attribute: false },
      _showHistorySidebar: { type: Boolean, reflect: false, attribute: false },
      _conversationSearchQuery: { type: String, reflect: false, attribute: false },
      _contextMenu: { type: Object, reflect: false, attribute: false },
      // UX Enhancement: Typing indicator
      _showTypingIndicator: { type: Boolean },
      // UX Enhancement: Error display
      _errorMessage: { type: String },
      _errorDetails: { type: String },
      // UX Enhancement: Conversation status indicators
      _saveStatus: { type: String },  // 'saving', 'saved', 'error', null
      _loadStatus: { type: String },  // 'loading', 'loaded', 'error', null
    };
  }

  static get styles() {
    return css`
      :host {
        background: var(--primary-background-color);
        -webkit-font-smoothing: antialiased;
        display: flex;
        flex-direction: column;
        height: 100vh;
      }
      .header {
        background: var(--app-header-background-color);
        color: var(--app-header-text-color);
        padding: 16px 24px;
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 20px;
        font-weight: 500;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        position: relative;
        z-index: 100;
      }
      .clear-button {
        margin-left: auto;
        border: none;
        border-radius: 16px;
        background: var(--error-color);
        color: #fff;
        cursor: pointer;
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 16px;
        font-weight: 500;
        font-size: 13px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.08);
        min-width: unset;
        width: auto;
        height: 36px;
        flex-shrink: 0;
        position: relative;
        z-index: 101;
        font-family: inherit;
      }
      .clear-button:hover {
        background: var(--error-color);
        opacity: 0.92;
        transform: translateY(-1px);
        box-shadow: 0 2px 6px rgba(0,0,0,0.13);
      }
      .clear-button:active {
        transform: translateY(0);
        box-shadow: 0 1px 2px rgba(0,0,0,0.08);
      }
      .clear-button ha-icon {
        --mdc-icon-size: 16px;
        margin-right: 2px;
        color: #fff;
      }
      .clear-button span {
        color: #fff;
        font-weight: 500;
      }
      .content {
        flex-grow: 1;
        padding: 24px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
      }
      .chat-container {
        width: 100%;
        padding: 0;
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        height: 100%;
      }
      .messages {
        overflow-y: auto;
        border: 1px solid var(--divider-color);
        border-radius: 12px;
        margin-bottom: 24px;
        padding: 0;
        background: var(--primary-background-color);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        flex-grow: 1;
        width: 100%;
      }
      .prompts-section {
        margin-bottom: 12px;
        padding: 12px 16px;
        background: var(--secondary-background-color);
        border-radius: 16px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
        border: 1px solid var(--divider-color);
      }
      .prompts-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
        font-size: 14px;
        font-weight: 500;
        color: var(--secondary-text-color);
      }
      .prompts-toggle {
        display: flex;
        align-items: center;
        gap: 4px;
        cursor: pointer;
        color: var(--primary-color);
        font-size: 12px;
        font-weight: 500;
        padding: 2px 6px;
        border-radius: 4px;
        transition: background-color 0.2s ease;
      }
      .prompts-toggle:hover {
        background: var(--primary-color);
        color: var(--text-primary-color);
      }
      .prompts-toggle ha-icon {
        --mdc-icon-size: 14px;
      }
      .prompt-bubbles {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 8px;
      }
      .prompt-bubble {
        background: var(--primary-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 20px;
        padding: 6px 12px;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 12px;
        line-height: 1.3;
        color: var(--primary-text-color);
        white-space: nowrap;
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .prompt-bubble:hover {
        border-color: var(--primary-color);
        background: var(--primary-color);
        color: var(--text-primary-color);
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      }
      .prompt-bubble:active {
        transform: translateY(0);
      }
      .history-bubble {
        background: var(--primary-background-color);
        border: 1px solid var(--accent-color);
        border-radius: 20px;
        padding: 6px 12px;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 12px;
        line-height: 1.3;
        color: var(--accent-color);
        white-space: nowrap;
        max-width: 180px;
        overflow: hidden;
        text-overflow: ellipsis;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .history-bubble:hover {
        background: var(--accent-color);
        color: var(--text-primary-color);
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      }
      .history-delete {
        opacity: 0;
        transition: opacity 0.2s ease;
        color: var(--error-color);
        cursor: pointer;
        --mdc-icon-size: 14px;
      }
      .history-bubble:hover .history-delete {
        opacity: 1;
        color: var(--text-primary-color);
      }
      .message {
        margin-bottom: 16px;
        padding: 12px 16px;
        border-radius: 12px;
        max-width: 80%;
        line-height: 1.5;
        animation: fadeIn 0.3s ease-out;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
        word-wrap: break-word;
      }
      .message-container {
        max-width: 100%;
      }
      .code-block-container {
        position: relative;
        margin: 12px 0;
      }
      /* Markdown content styling */
      .message-content {
        line-height: 1.6;
        word-wrap: break-word;
      }
      .message-content h1, .message-content h2, .message-content h3 {
        margin-top: 16px;
        margin-bottom: 8px;
        font-weight: 600;
      }
      .message-content h1 { font-size: 1.5em; }
      .message-content h2 { font-size: 1.3em; }
      .message-content h3 { font-size: 1.1em; }
      .message-content p {
        margin: 8px 0;
      }
      .message-content ul, .message-content ol {
        margin: 8px 0;
        padding-left: 24px;
      }
      .message-content li {
        margin: 4px 0;
      }
      .message-content code {
        background-color: #1e1e1e;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.9em;
        color: #e6e6e6;
      }
      .message-content pre {
        background-color: #1e1e1e;
        padding: 16px;
        border-radius: 8px;
        overflow-x: auto;
        margin: 12px 0;
        position: relative;
      }
      .message-content pre code {
        background-color: transparent;
        padding: 0;
        color: #d4d4d4;
      }
      .message-content blockquote {
        border-left: 4px solid #007acc;
        margin: 12px 0;
        padding: 8px 16px;
        background-color: rgba(0, 122, 204, 0.1);
        border-radius: 0 4px 4px 0;
      }
      .message-content a {
        color: #4db6ac;
        text-decoration: none;
      }
      .message-content a:hover {
        text-decoration: underline;
      }
      .message-content table {
        border-collapse: collapse;
        width: 100%;
        margin: 12px 0;
      }
      .message-content th, .message-content td {
        border: 1px solid #444;
        padding: 8px 12px;
        text-align: left;
      }
      .message-content th {
        background-color: #333;
        font-weight: 600;
      }
      /* Action report styling */
      .action-report {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        border-left: 4px solid #4caf50;
        padding: 12px 16px;
        border-radius: 4px;
        margin: 8px 0;
        font-size: 0.95em;
      }
      .action-report br:last-child {
        display: none;
      }
      /* Copy button for code blocks */
      .copy-code-btn {
        position: absolute;
        top: 8px;
        right: 8px;
        background-color: #333;
        color: #ccc;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 0.8em;
        cursor: pointer;
        opacity: 0.7;
        transition: opacity 0.2s;
      }
      .copy-code-btn:hover {
        opacity: 1;
      }
      .copy-code-btn.copied {
        background-color: #2e7d32;
        color: white;
      }
      .user-message {
        background: var(--primary-color);
        color: var(--text-primary-color);
        margin-left: auto;
        border-bottom-right-radius: 4px;
      }
      .assistant-message {
        background: var(--secondary-background-color);
        margin-right: auto;
        border-bottom-left-radius: 4px;
      }
      .input-container {
        position: relative;
        width: 100%;
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        margin-bottom: 24px;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
      }
      .input-container:focus-within {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 2px rgba(var(--primary-color-rgb), 0.1);
      }
      .input-main {
        display: flex;
        align-items: flex-end;
        padding: 12px;
        gap: 12px;
      }
      .input-wrapper {
        flex-grow: 1;
        position: relative;
        border: 1px solid var(--divider-color);
      }
      textarea {
        width: 100%;
        min-height: 24px;
        max-height: 200px;
        padding: 12px 16px 12px 16px;
        border: none;
        outline: none;
        resize: none;
        font-size: 16px;
        line-height: 1.5;
        background: transparent;
        color: var(--primary-text-color);
        font-family: inherit;
      }
      textarea::placeholder {
        color: var(--secondary-text-color);
      }
      .input-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 16px 12px 16px;
        border-top: 1px solid var(--divider-color);
        background: var(--card-background-color);
        border-radius: 0 0 12px 12px;
      }
      .provider-selector {
        position: relative;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .provider-button {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        background: var(--secondary-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        color: var(--primary-text-color);
        transition: all 0.2s ease;
        min-width: 150px;
        -webkit-appearance: none;
        -moz-appearance: none;
        appearance: none;
        background-image: url('data:image/svg+xml;charset=US-ASCII,<svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7 10l5 5 5-5H7z" fill="currentColor"/></svg>');
        background-repeat: no-repeat;
        background-position: right 8px center;
        padding-right: 30px;
      }
      .provider-button:hover {
        background-color: var(--primary-background-color);
        border-color: var(--primary-color);
      }
      .provider-button:focus {
        outline: none;
        border-color: var(--primary-color);
        box-shadow: 0 0 0 2px rgba(var(--primary-color-rgb), 0.2);
      }
      .provider-label {
        font-size: 12px;
        color: var(--secondary-text-color);
        margin-right: 8px;
      }
      .thinking-toggle {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: var(--secondary-text-color);
        cursor: pointer;
        user-select: none;
      }
      .thinking-toggle input {
        margin: 0;
      }
      .thinking-panel {
        border: 1px dashed var(--divider-color);
        border-radius: 10px;
        padding: 10px 12px;
        margin: 12px 0;
        background: var(--secondary-background-color);
      }
      .thinking-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        cursor: pointer;
        gap: 10px;
      }
      .thinking-title {
        font-weight: 600;
        color: var(--primary-text-color);
        font-size: 14px;
      }
      .thinking-subtitle {
        display: block;
        font-size: 12px;
        color: var(--secondary-text-color);
        margin-top: 2px;
      }
      .thinking-body {
        margin-top: 10px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-height: 240px;
        overflow-y: auto;
      }
      .thinking-entry {
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        padding: 8px;
        background: var(--primary-background-color);
      }
      .thinking-entry .badge {
        display: inline-block;
        background: var(--secondary-background-color);
        color: var(--secondary-text-color);
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 6px;
        margin-bottom: 6px;
      }
      .thinking-entry pre {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        font-size: 12px;
      }
      .thinking-empty {
        color: var(--secondary-text-color);
        font-size: 12px;
      }
      .send-button {
        --mdc-theme-primary: var(--primary-color);
        --mdc-theme-on-primary: var(--text-primary-color);
        --mdc-typography-button-font-size: 14px;
        --mdc-typography-button-text-transform: none;
        --mdc-typography-button-letter-spacing: 0;
        --mdc-typography-button-font-weight: 500;
        --mdc-button-height: 36px;
        --mdc-button-padding: 0 16px;
        border-radius: 8px;
        transition: all 0.2s ease;
        min-width: 80px;
      }
      .send-button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }
      .send-button:active {
        transform: translateY(0);
      }
      .send-button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .loading {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
        padding: 12px 16px;
        border-radius: 12px;
        background: var(--secondary-background-color);
        margin-right: auto;
        max-width: 80%;
        animation: fadeIn 0.3s ease-out;
      }
      .loading-dots {
        display: flex;
        gap: 4px;
      }
      .dot {
        width: 8px;
        height: 8px;
        background: var(--primary-color);
        border-radius: 50%;
        animation: bounce 1.4s infinite ease-in-out;
      }
      .dot:nth-child(1) { animation-delay: -0.32s; }
      .dot:nth-child(2) { animation-delay: -0.16s; }
      @keyframes bounce {
        0%, 80%, 100% {
          transform: scale(0);
        }
        40% {
          transform: scale(1.0);
        }
      }
      @keyframes fadeIn {
        from {
          opacity: 0;
          transform: translateY(10px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }
      .error {
        color: var(--error-color);
        padding: 16px;
        margin: 8px 0;
        border-radius: 12px;
        background: var(--error-background-color);
        border: 1px solid var(--error-color);
        animation: fadeIn 0.3s ease-out;
      }
      .automation-suggestion {
        background: var(--secondary-background-color);
        border: 1px solid var(--primary-color);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        position: relative;
        z-index: 10;
      }
      .automation-title {
        font-weight: 500;
        margin-bottom: 8px;
        color: var(--primary-color);
        font-size: 16px;
      }
      .automation-description {
        margin-bottom: 16px;
        color: var(--secondary-text-color);
        line-height: 1.4;
      }
      .automation-actions {
        display: flex;
        gap: 8px;
        margin-top: 16px;
        justify-content: flex-end;
      }
      .automation-actions ha-button {
        --mdc-button-height: 40px;
        --mdc-button-padding: 0 20px;
        --mdc-typography-button-font-size: 14px;
        --mdc-typography-button-font-weight: 600;
        border-radius: 20px;
      }
      .automation-actions ha-button:first-child {
        --mdc-theme-primary: var(--success-color, #4caf50);
        --mdc-theme-on-primary: #fff;
      }
      .automation-actions ha-button:last-child {
        --mdc-theme-primary: var(--error-color);
        --mdc-theme-on-primary: #fff;
      }
      .automation-details {
        margin-top: 8px;
        padding: 8px;
        background: var(--primary-background-color);
        border-radius: 8px;
        font-family: monospace;
        font-size: 12px;
        white-space: pre-wrap;
        overflow-x: auto;
        max-height: 200px;
        overflow-y: auto;
        border: 1px solid var(--divider-color);
      }
      .dashboard-suggestion {
        background: var(--secondary-background-color);
        border: 1px solid var(--info-color, #2196f3);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        position: relative;
        z-index: 10;
      }
      .dashboard-title {
        font-weight: 500;
        margin-bottom: 8px;
        color: var(--info-color, #2196f3);
        font-size: 16px;
      }
      .dashboard-description {
        margin-bottom: 16px;
        color: var(--secondary-text-color);
        line-height: 1.4;
      }
      .dashboard-actions {
        display: flex;
        gap: 8px;
        margin-top: 16px;
        justify-content: flex-end;
      }
      .dashboard-actions ha-button {
        --mdc-button-height: 40px;
        --mdc-button-padding: 0 20px;
        --mdc-typography-button-font-size: 14px;
        --mdc-typography-button-font-weight: 600;
        border-radius: 20px;
      }
      .dashboard-actions ha-button:first-child {
        --mdc-theme-primary: var(--info-color, #2196f3);
        --mdc-theme-on-primary: #fff;
      }
      .dashboard-actions ha-button:last-child {
        --mdc-theme-primary: var(--error-color);
        --mdc-theme-on-primary: #fff;
      }
      .dashboard-details {
        margin-top: 8px;
        padding: 8px;
        background: var(--primary-background-color);
        border-radius: 8px;
        font-family: monospace;
        font-size: 12px;
        white-space: pre-wrap;
        overflow-x: auto;
        max-height: 200px;
        overflow-y: auto;
        border: 1px solid var(--divider-color);
      }
      .no-providers {
        color: var(--error-color);
        font-size: 14px;
        padding: 8px;
      }
      
      /* Image attachment button */
      .image-btn {
        background: none;
        border: none;
        cursor: pointer;
        padding: 8px;
        color: var(--primary-color);
        border-radius: 4px;
        transition: background-color 0.2s;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .image-btn:hover {
        background-color: rgba(0, 122, 204, 0.1);
      }
      .image-btn ha-icon {
        --mdc-icon-size: 24px;
      }
      
      /* Attached images preview */
      .attached-images {
        display: flex;
        gap: 8px;
        padding: 8px;
        overflow-x: auto;
        border-bottom: 1px solid var(--divider-color);
        margin-bottom: 4px;
      }
      .image-preview {
        position: relative;
        width: 80px;
        height: 80px;
        border-radius: 8px;
        overflow: hidden;
        border: 2px solid var(--primary-color);
        flex-shrink: 0;
      }
      .image-preview img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      .remove-image {
        position: absolute;
        top: 2px;
        right: 2px;
        background: rgba(0, 0, 0, 0.7);
        color: white;
        border: none;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        font-size: 14px;
        line-height: 1;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
      }
      .remove-image:hover {
        background: rgba(255, 0, 0, 0.8);
      }
      
      /* Chat History Sidebar */
      .sidebar-toggle {
        background: none;
        border: none;
        cursor: pointer;
        padding: 4px;
        color: var(--primary-text-color);
        display: flex;
        align-items: center;
        justify-content: center;
        transition: opacity 0.2s ease;
      }
      .sidebar-toggle:hover {
        opacity: 0.8;
      }
      .sidebar-toggle ha-icon {
        --mdc-icon-size: 24px;
      }
      .main-layout {
        display: flex;
        flex-grow: 1;
        overflow: hidden;
        position: relative;
      }
      .sidebar {
        width: 320px;
        min-width: 280px;
        max-width: 320px;
        background: var(--secondary-background-color);
        border-right: 1px solid var(--divider-color);
        display: flex;
        flex-direction: column;
        height: 100%;
        animation: slideIn 0.2s ease-out;
        overflow: hidden;
      }
      @keyframes slideIn {
        from { transform: translateX(-100%); }
        to { transform: translateX(0); }
      }
      .sidebar-header {
        padding: 16px;
        border-bottom: 1px solid var(--divider-color);
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .sidebar-header h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: var(--primary-text-color);
      }
      .new-conversation-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        width: 100%;
        padding: 12px;
        background: var(--primary-color);
        color: var(--text-primary-color);
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s ease;
        margin: 12px 16px;
      }
      .new-conversation-btn:hover {
        opacity: 0.9;
        transform: translateY(-1px);
      }
      .sidebar-search {
        padding: 12px 16px;
        border-bottom: 1px solid var(--divider-color);
      }
      .sidebar-search input {
        width: 100%;
        padding: 8px 12px;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        font-size: 14px;
        background: var(--primary-background-color);
        color: var(--primary-text-color);
        font-family: inherit;
        box-sizing: border-box;
      }
      .sidebar-search input:focus {
        outline: none;
        border-color: var(--primary-color);
        box-shadow: 0 0 0 2px rgba(var(--primary-color-rgb), 0.1);
      }
      .sidebar-search input::placeholder {
        color: var(--secondary-text-color);
      }
      .conversation-list {
        flex-grow: 1;
        overflow-y: auto;
        padding: 8px;
      }
      .conversation-item {
        padding: 12px;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
        margin-bottom: 4px;
        border: 1px solid transparent;
      }
      .conversation-item:hover {
        background: var(--primary-background-color);
        border-color: var(--divider-color);
      }
      .conversation-item.active {
        background: var(--primary-color);
        color: var(--text-primary-color);
        border-color: var(--primary-color);
      }
      .conversation-item.pinned {
        border-left: 3px solid var(--warning-color, #ff9800);
      }
      .conversation-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 4px;
      }
      .conversation-name {
        font-weight: 500;
        font-size: 14px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .conversation-item.active .conversation-name {
        color: var(--text-primary-color);
      }
      .pinned-icon {
        --mdc-icon-size: 14px;
        color: var(--warning-color, #ff9800);
        flex-shrink: 0;
        margin-left: 4px;
      }
      .conversation-item.active .pinned-icon {
        color: var(--text-primary-color);
      }
      .conversation-preview {
        font-size: 12px;
        color: var(--secondary-text-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 4px;
      }
      .conversation-item.active .conversation-preview {
        color: rgba(var(--text-primary-color-rgb), 0.8);
      }
      .conversation-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 11px;
        color: var(--secondary-text-color);
      }
      .conversation-item.active .conversation-meta {
        color: rgba(var(--text-primary-color-rgb), 0.7);
      }
      .conversation-tags {
        display: flex;
        gap: 4px;
      }
      .tag-badge {
        background: var(--primary-background-color);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 10px;
      }
      .conversation-item.active .tag-badge {
        background: rgba(var(--text-primary-color-rgb), 0.2);
      }
      .context-menu {
        position: fixed;
        background: var(--card-background-color);
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        z-index: 1000;
        min-width: 160px;
        padding: 4px 0;
      }
      .context-menu-item {
        padding: 10px 16px;
        cursor: pointer;
        font-size: 14px;
        display: flex;
        align-items: center;
        gap: 10px;
        transition: background-color 0.2s ease;
      }
      .context-menu-item:hover {
        background: var(--primary-background-color);
      }
      .context-menu-item.delete {
        color: var(--error-color);
      }
      .context-menu-item.delete:hover {
        background: rgba(var(--error-color-rgb), 0.1);
      }
      .context-menu-divider {
        height: 1px;
        background: var(--divider-color);
        margin: 4px 0;
      }
      .empty-conversations {
        padding: 32px 16px;
        text-align: center;
        color: var(--secondary-text-color);
        font-size: 14px;
      }
      .content-area {
        flex-grow: 1;
        overflow: hidden;
        display: flex;
        flex-direction: column;
      }
      @media (max-width: 768px) {
        .sidebar {
          position: absolute;
          top: 0;
          left: 0;
          height: 100%;
          z-index: 200;
          box-shadow: 4px 0 16px rgba(0, 0, 0, 0.2);
        }
      }
      
      /* ========== UX Enhancement: Typing Indicator ========== */
      .typing-indicator {
        display: flex;
        align-items: center;
        padding: 8px 0;
        gap: 4px;
      }

      .typing-indicator span {
        animation: blink 1.4s infinite both;
        font-size: 18px;
        color: #666;
      }

      .typing-indicator span:nth-child(2) {
        animation-delay: 0.2s;
      }

      .typing-indicator span:nth-child(3) {
        animation-delay: 0.4s;
      }

      @keyframes blink {
        0% { opacity: 0.2; }
        20% { opacity: 1; }
        100% { opacity: 0.2; }
      }
      
      /* ========== UX Enhancement: Error Banner ========== */
      .error-banner {
        background: #ffebee;
        border-left: 4px solid #f44336;
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 4px;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: fadeIn 0.3s ease-out;
      }

      .error-banner .error-content {
        flex-grow: 1;
      }

      .error-banner .error-message {
        color: #c62828;
        font-weight: 500;
        margin-bottom: 4px;
      }

      .error-banner .error-details {
        color: #e57373;
        font-size: 13px;
      }

      .error-banner .retry-button {
        margin-left: auto;
        background: #f44336;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
        font-weight: 500;
        white-space: nowrap;
      }

      .error-banner .retry-button:hover {
        background: #d32f2f;
      }
      
      /* ========== UX Enhancement: Skeleton Loading ========== */
      .skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: skeleton-loading 1.5s infinite;
        border-radius: 4px;
      }

      @keyframes skeleton-loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }

      .skeleton-message {
        height: 40px;
        margin-bottom: 12px;
        border-radius: 12px;
      }

      .skeleton-message:last-child {
        margin-bottom: 0;
      }
      
      /* ========== UX Enhancement: Action Cards ========== */
      .action-card {
        background: var(--primary-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        transition: all 0.2s ease;
      }

      .action-card.success {
        border-left: 4px solid #4caf50;
      }

      .action-card.error {
        border-left: 4px solid #f44336;
      }

      .action-card.in-progress {
        border-left: 4px solid #ff9800;
      }

      .action-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
      }

      .action-badge {
        background: var(--secondary-background-color);
        padding: 4px 8px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 12px;
        color: var(--primary-text-color);
        font-weight: 500;
      }

      .action-status {
        font-size: 16px;
      }

      .action-target {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: var(--secondary-text-color);
        margin-top: 4px;
      }

      .action-target ha-icon {
        --mdc-icon-size: 16px;
        color: var(--primary-color);
      }

      .action-error {
        color: #f44336;
        font-size: 12px;
        margin-top: 8px;
        padding: 6px;
        background: rgba(244, 67, 54, 0.1);
        border-radius: 4px;
      }
      
      /* ========== UX Enhancement: Action Progress ========== */
      .action-progress {
        background: var(--secondary-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
      }

      .action-progress-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
        font-size: 14px;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .action-progress-spinner {
        width: 16px;
        height: 16px;
        border: 2px solid var(--primary-color);
        border-top: 2px solid transparent;
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }

      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }

      .action-progress-bar {
        height: 4px;
        background: var(--primary-background-color);
        border-radius: 2px;
        overflow: hidden;
        margin: 8px 0;
      }

      .action-progress-fill {
        height: 100%;
        background: var(--primary-color);
        transition: width 0.3s ease;
        border-radius: 2px;
      }
      
      /* ========== UX Enhancement: Response Time ========== */
      .response-meta {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 11px;
        color: var(--secondary-text-color);
        margin-top: 6px;
        padding-top: 6px;
        border-top: 1px solid var(--divider-color);
      }

      .response-meta ha-icon {
        --mdc-icon-size: 12px;
      }
      
      /* ========== UX Enhancement: Message Status ========== */
      .message-status {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 11px;
        margin-top: 4px;
      }

      .message-status.pending {
        color: #ff9800;
      }

      .message-status.success {
        color: #4caf50;
      }

      .message-status.error {
        color: #f44336;
      }

      .status-spinner {
        width: 12px;
        height: 12px;
        border: 2px solid #ff9800;
        border-top: 2px solid transparent;
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }
      
      /* ========== UX Enhancement: Save/Load Status ========== */
      .status-indicator {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        color: var(--secondary-text-color);
      }

      .status-indicator ha-icon {
        --mdc-icon-size: 14px;
      }

      .status-indicator.saving {
        color: #ff9800;
      }

      .status-indicator.saved {
        color: #4caf50;
      }

      .status-indicator.loading {
        color: #2196f3;
      }
    `;
  }

  constructor() {
    super();
    this._messages = [];
    this._isLoading = false;
    this._error = null;
    this._pendingAutomation = null;
    this._promptHistory = [];
    this._promptHistoryLoaded = false;
    this._showPredefinedPrompts = true;
    this._showPromptHistory = true;
    this._attachedImages = [];
    this._imageUploadEnabled = true;
    this._maxImagesPerMessage = 3;
    this._predefinedPrompts = [
      "Build a new automation to turn off all lights at 10:00 PM every day",
      "What's the current temperature inside and outside?",
      "Turn on all the lights in the living room",
      "Show me today's weather forecast",
      "What devices are currently on?",
      "Show me the energy usage for today",
      "Are all the doors and windows locked?",
      "Turn on movie mode in the living room",
      "What's the status of my security system?",
      "Show me who's currently home",
      "Turn off all devices when I leave home"
    ];
    this._selectedPrompts = this._getRandomPrompts();
    this._selectedProvider = null;
    this._availableProviders = [];
    this._showProviderDropdown = false;
    this.providersLoaded = false;
    this._eventSubscriptionSetup = false;
    this._serviceCallTimeout = null;
    this._showThinking = false;
    this._thinkingExpanded = false;
    this._debugInfo = null;
    // Chat history state
    this._conversations = [];
    this._currentConversationId = null;
    this._showHistorySidebar = false;
    this._conversationSearchQuery = '';
    this._contextMenu = null;
    
    // UX Enhancement: Typing indicator
    this._showTypingIndicator = false;
    // UX Enhancement: Error display
    this._errorMessage = null;
    this._errorDetails = null;
    // UX Enhancement: Conversation status indicators
    this._saveStatus = null;
    this._loadStatus = null;
    
    console.debug("AI Agent HA Panel constructor called");
  }

  _getRandomPrompts() {
    // Shuffle array and take first 3 items
    const shuffled = [...this._predefinedPrompts].sort(() => 0.5 - Math.random());
    return shuffled.slice(0, 3);
  }

  async connectedCallback() {
    super.connectedCallback();
    console.debug("AI Agent HA Panel connected");
    if (this.hass && !this._eventSubscriptionSetup) {
      this._eventSubscriptionSetup = true;
      this.hass.connection.subscribeEvents(
        (event) => this._handleLlamaResponse(event),
        'ai_agent_ha_response'
      );
      console.debug("Event subscription set up in connectedCallback()");
      // Load prompt history from Home Assistant storage
      await this._loadPromptHistory();
      // Load conversations list
      await this._loadConversations();
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!this.shadowRoot.querySelector('.provider-selector')?.contains(e.target)) {
        this._showProviderDropdown = false;
      }
      // Close context menu when clicking outside
      if (this._contextMenu && !e.target.closest('.context-menu')) {
        this._contextMenu = null;
        this.requestUpdate();
      }
    });
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    // Auto-save current conversation when panel is closed
    if (this.hass && this._messages.length > 0) {
      this._saveCurrentConversation();
    }
  }

  async updated(changedProps) {
    console.debug("Updated called with:", changedProps);

    // Set up event subscription when hass becomes available
    if (changedProps.has('hass') && this.hass && !this._eventSubscriptionSetup) {
      this._eventSubscriptionSetup = true;
      this.hass.connection.subscribeEvents(
        (event) => this._handleLlamaResponse(event),
        'ai_agent_ha_response'
      );
      console.debug("Event subscription set up in updated()");
    }

    // Load providers when hass becomes available
    if (changedProps.has('hass') && this.hass && !this.providersLoaded) {
      this.providersLoaded = true;

      try {
        // Uses the WebSocket API to get all entries with their complete data
        const allEntries = await this.hass.callWS({ type: 'config_entries/get' });

        const aiAgentEntries = allEntries.filter(
          entry => entry.domain === 'ai_agent_ha'
        );

        if (aiAgentEntries.length > 0) {
          const providers = aiAgentEntries
            .map(entry => {
              const provider = this._resolveProviderFromEntry(entry);
              if (!provider) return null;

              return {
                value: provider,
                label: PROVIDERS[provider] || provider
              };
            })
            .filter(Boolean);

          this._availableProviders = providers;

          if (
            (!this._selectedProvider || !providers.find(p => p.value === this._selectedProvider)) &&
            providers.length > 0
          ) {
            this._selectedProvider = providers[0].value;
          }
        } else {
          console.debug("No 'ai_agent_ha' config entries found via WebSocket.");
          this._availableProviders = [];
        }
      } catch (error) {
        console.error("Error fetching config entries via WebSocket:", error);
        this._error = error.message || 'Failed to load AI provider configurations.';
        this._availableProviders = [];
      }
      this.requestUpdate();
    }

    // Load prompt history when hass becomes available and we haven't loaded it yet
    if (changedProps.has('hass') && this.hass && !this._promptHistoryLoaded) {
      this._promptHistoryLoaded = true;
      await this._loadPromptHistory();
    }

    // Load prompt history when provider changes
    if (changedProps.has('_selectedProvider') && this._selectedProvider && this.hass) {
      await this._loadPromptHistory();
    }

    if (changedProps.has('_messages') || changedProps.has('_isLoading')) {
      this._scrollToBottom();
      // Set innerHTML for markdown content after render (use requestAnimationFrame to ensure DOM is ready)
      requestAnimationFrame(() => this._setMarkdownContent());
    }
  }
  
  firstUpdated() {
    // Set innerHTML for all markdown content elements on first render
    this._setMarkdownContent();
  }
  
  _setMarkdownContent() {
    // Use requestAnimationFrame to ensure DOM is ready
    requestAnimationFrame(() => {
      const markdownElements = this.shadowRoot?.querySelectorAll('.markdown-content');
      if (markdownElements) {
        markdownElements.forEach(el => {
          const htmlContent = el.getAttribute('data-html');
          if (htmlContent && el.innerHTML !== htmlContent) {
            el.innerHTML = htmlContent;
          }
        });
      }
    });
  }

  _renderPromptsSection() {
    return html`
      <div class="prompts-section">
        <div class="prompts-header">
          <span>Quick Actions</span>
          <div style="display: flex; gap: 12px;">
            <div class="prompts-toggle" @click=${() => this._togglePredefinedPrompts()}>
              <ha-icon icon="${this._showPredefinedPrompts ? 'mdi:chevron-up' : 'mdi:chevron-down'}"></ha-icon>
              <span>Suggestions</span>
            </div>
            ${this._promptHistory.length > 0 ? html`
              <div class="prompts-toggle" @click=${() => this._togglePromptHistory()}>
                <ha-icon icon="${this._showPromptHistory ? 'mdi:chevron-up' : 'mdi:chevron-down'}"></ha-icon>
                <span>Recent</span>
              </div>
            ` : ''}
          </div>
        </div>

        ${this._showPredefinedPrompts ? html`
          <div class="prompt-bubbles">
            ${this._selectedPrompts.map(prompt => html`
              <div class="prompt-bubble" @click=${() => this._usePrompt(prompt)}>
                ${prompt}
              </div>
            `)}
          </div>
        ` : ''}

        ${this._showPromptHistory && this._promptHistory.length > 0 ? html`
          <div class="prompt-bubbles">
            ${this._promptHistory.slice(-3).reverse().map((prompt, index) => html`
              <div class="history-bubble" @click=${(e) => this._useHistoryPrompt(e, prompt)}>
                <span style="flex-grow: 1; overflow: hidden; text-overflow: ellipsis;">${prompt}</span>
                <ha-icon
                  class="history-delete"
                  icon="mdi:close"
                  @click=${(e) => this._deleteHistoryItem(e, prompt)}
                ></ha-icon>
              </div>
            `)}
          </div>
        ` : ''}
      </div>
    `;
  }

  _togglePredefinedPrompts() {
    this._showPredefinedPrompts = !this._showPredefinedPrompts;
    // Refresh random selection when toggling on
    if (this._showPredefinedPrompts) {
      this._selectedPrompts = this._getRandomPrompts();
    }
  }

  _togglePromptHistory() {
    this._showPromptHistory = !this._showPromptHistory;
  }

  _usePrompt(prompt) {
    if (this._isLoading) return;
    const promptEl = this.shadowRoot.querySelector('#prompt');
    if (promptEl) {
      promptEl.value = prompt;
      promptEl.focus();
    }
  }

  _useHistoryPrompt(event, prompt) {
    event.stopPropagation();
    if (this._isLoading) return;
    const promptEl = this.shadowRoot.querySelector('#prompt');
    if (promptEl) {
      promptEl.value = prompt;
      promptEl.focus();
    }
  }

  async _deleteHistoryItem(event, prompt) {
    event.stopPropagation();
    this._promptHistory = this._promptHistory.filter(p => p !== prompt);
    await this._savePromptHistory();
    this.requestUpdate();
  }

  async _addToHistory(prompt) {
    if (!prompt || prompt.trim().length === 0) return;

    // Remove duplicates and add to front
    this._promptHistory = this._promptHistory.filter(p => p !== prompt);
    this._promptHistory.push(prompt);

    // Keep only last 20 prompts
    if (this._promptHistory.length > 20) {
      this._promptHistory = this._promptHistory.slice(-20);
    }

    await this._savePromptHistory();
    this.requestUpdate();
  }

  async _loadPromptHistory() {
    if (!this.hass) {
      console.debug('Hass not available, skipping prompt history load');
      return;
    }

    console.debug('Loading prompt history...');
    try {
      const result = await this.hass.callService('ai_agent_ha', 'load_prompt_history', {
        provider: this._selectedProvider
      });
      console.debug('Prompt history service result:', result);

      if (result && result.response && result.response.history) {
        this._promptHistory = result.response.history;
        console.debug('Loaded prompt history from service:', this._promptHistory);
        this.requestUpdate();
      } else if (result && result.history) {
        this._promptHistory = result.history;
        console.debug('Loaded prompt history from service (direct):', this._promptHistory);
        this.requestUpdate();
      } else {
        console.debug('No prompt history returned from service, checking localStorage');
        // Fallback to localStorage if service returns no data
        this._loadFromLocalStorage();
      }
    } catch (error) {
      console.error('Error loading prompt history from service:', error);
      // Fallback to localStorage if service fails
      this._loadFromLocalStorage();
    }
  }

  _loadFromLocalStorage() {
    try {
      const savedList = localStorage.getItem('ai_agent_ha_prompt_history');
      if (savedList) {
        const parsedList = JSON.parse(savedList);
        const saved = parsedList.history && parsedList.provider === this._selectedProvider ? parsedList.history : null;
        if (saved) {
          this._promptHistory = JSON.parse(saved);
          console.debug('Loaded prompt history from localStorage:', this._promptHistory);
          this.requestUpdate();
        } else {
          console.debug('No prompt history in localStorage');
          this._promptHistory = [];
        }
      }
    } catch (e) {
      console.error('Error loading from localStorage:', e);
      this._promptHistory = [];
    }
  }

  async _savePromptHistory() {
    if (!this.hass) {
      console.debug('Hass not available, saving to localStorage only');
      this._saveToLocalStorage();
      return;
    }

    console.debug('Saving prompt history:', this._promptHistory);
    try {
      const result = await this.hass.callService('ai_agent_ha', 'save_prompt_history', {
        history: this._promptHistory,
        provider: this._selectedProvider
      });
      console.debug('Save prompt history result:', result);

      // Also save to localStorage as backup
      this._saveToLocalStorage();
    } catch (error) {
      console.error('Error saving prompt history to service:', error);
      // Fallback to localStorage if service fails
      this._saveToLocalStorage();
    }
  }

  _saveToLocalStorage() {
    try {
      const data = {
        provider: this._selectedProvider,
        history: JSON.stringify(this._promptHistory)
      }
      localStorage.setItem('ai_agent_ha_prompt_history', JSON.stringify(data));
      console.debug('Saved prompt history to localStorage');
    } catch (e) {
      console.error('Error saving to localStorage:', e);
    }
  }

  render() {
    console.debug("Rendering with state:", {
      messages: this._messages,
      isLoading: this._isLoading,
      error: this._error
    });
    console.debug("Messages array:", this._messages);

    return html`
      <div class="header">
        <button class="sidebar-toggle" @click=${() => this._toggleHistorySidebar()} title="Toggle conversation history">
          <ha-icon icon="${this._showHistorySidebar ? 'mdi:close-box' : 'mdi:history'}"></ha-icon>
        </button>
        <ha-icon icon="mdi:robot"></ha-icon>
        AI Agent HA
        <button
          class="clear-button"
          @click=${this._clearChat}
          ?disabled=${this._isLoading}
        >
          <ha-icon icon="mdi:delete-sweep"></ha-icon>
          <span>Clear Chat</span>
        </button>
      </div>
      <div class="content">
        <div class="main-layout">
          ${this._showHistorySidebar ? html`
            <div class="sidebar">
              <div class="sidebar-header">
                <h3>Conversation History</h3>
                <span style="font-size: 12px; color: var(--secondary-text-color);">
                  ${this._conversations.length} conversation${this._conversations.length !== 1 ? 's' : ''}
                </span>
              </div>
              <button class="new-conversation-btn" @click=${() => this._createNewConversation()}>
                <ha-icon icon="mdi:plus"></ha-icon>
                <span>New Conversation</span>
              </button>
              <div class="sidebar-search">
                <input
                  type="text"
                  placeholder="Search conversations..."
                  .value=${this._conversationSearchQuery}
                  @input=${(e) => this._handleConversationSearch(e.target.value)}
                />
              </div>
              <div class="conversation-list">
                ${this._filteredConversations.length === 0 ? html`
                  <div class="empty-conversations">
                    ${this._conversations.length === 0 ? 'No conversations yet' : 'No matching conversations'}
                  </div>
                ` : this._filteredConversations.map(conv => html`
                  <div class="conversation-item ${conv.conversation_id === this._currentConversationId ? 'active' : ''} ${conv.is_pinned ? 'pinned' : ''}"
                       @click=${() => this._loadConversation(conv.conversation_id)}
                       @contextmenu=${(e) => this._showContextMenu(e, conv.conversation_id)}>
                    <div class="conversation-header">
                      <span class="conversation-name">${conv.name || 'New Conversation'}</span>
                      ${conv.is_pinned ? html`<ha-icon icon="mdi:pin" class="pinned-icon"></ha-icon>` : ''}
                    </div>
                    <div class="conversation-preview">${conv.preview || 'No preview'}</div>
                    <div class="conversation-meta">
                      <span>${this._formatConversationDate(conv.updated_at || conv.created_at)}</span>
                      <div class="conversation-tags">
                        ${conv.tags?.slice(0, 2).map(tag => html`<span class="tag-badge">${tag}</span>`)}
                      </div>
                    </div>
                  </div>
                `)}
              </div>
            </div>
          ` : ''}
          <div class="content-area">
            <div class="chat-container">
              <div class="messages" id="messages">
                <!-- UX Enhancement: Error Banner -->
                ${this._errorMessage ? this._renderErrorBanner() : ''}
                
                <!-- UX Enhancement: Skeleton Loading -->
                ${this._loadStatus === 'loading' ? this._renderSkeletonLoading() : ''}
                
                ${this._messages.map(msg => html`
                  <div class="message-container">
                    <div class="message ${msg.type}-message">
                      ${this._renderMessageContent(msg)}
                      <!-- UX Enhancement: Message Status Indicator -->
                      ${msg.status ? html`
                        <div class="message-status ${msg.status}">
                          ${msg.status === 'pending' ? html`
                            <div class="status-spinner"></div>
                            <span>Sending...</span>
                          ` : msg.status === 'error' ? html`
                            <ha-icon icon="mdi:alert-circle"></ha-icon>
                            <span>Failed</span>
                          ` : html`
                            <ha-icon icon="mdi:check-circle"></ha-icon>
                            <span>Sent</span>
                          `}
                        </div>
                      ` : ''}
                      ${msg.automation ? html`
                      <div class="automation-suggestion">
                        <div class="automation-title">${msg.automation.alias}</div>
                        <div class="automation-description">${msg.automation.description}</div>
                        <div class="automation-details">
                          ${JSON.stringify(msg.automation, null, 2)}
                        </div>
                        <div class="automation-actions">
                          <ha-button
                            @click=${() => this._approveAutomation(msg.automation)}
                            .disabled=${this._isLoading}
                          >Approve</ha-button>
                          <ha-button
                            @click=${() => this._rejectAutomation()}
                            .disabled=${this._isLoading}
                          >Reject</ha-button>
                        </div>
                      </div>
                    ` : ''}
                    ${msg.dashboard ? html`
                      <div class="dashboard-suggestion">
                        <div class="dashboard-title">${msg.dashboard.title}</div>
                        <div class="dashboard-description">Dashboard with ${msg.dashboard.views ? msg.dashboard.views.length : 0} view(s)</div>
                        <div class="dashboard-details">
                          ${JSON.stringify(msg.dashboard, null, 2)}
                        </div>
                        <div class="dashboard-actions">
                          <ha-button
                            @click=${() => this._approveDashboard(msg.dashboard)}
                            .disabled=${this._isLoading}
                          >Create Dashboard</ha-button>
                          <ha-button
                            @click=${() => this._rejectDashboard()}
                            .disabled=${this._isLoading}
                          >Cancel</ha-button>
                        </div>
                      </div>
                    ` : ''}
                    </div>
                  </div>
                `)}
                ${this._isLoading ? html`
                  <div class="loading">
                    <span>AI Agent is thinking</span>
                    <div class="loading-dots">
                      <div class="dot"></div>
                      <div class="dot"></div>
                      <div class="dot"></div>
                    </div>
                  </div>
                  <!-- UX Enhancement: Typing Indicator -->
                  ${this._renderTypingIndicator()}
                ` : ''}
                ${this._error ? html`
                  <div class="error">${this._error}</div>
                ` : ''}
                ${this._showThinking ? this._renderThinkingPanel() : ''}
              </div>
              ${this._renderPromptsSection()}
              <div class="input-container">
                <!-- Hidden file input for image upload -->
                <input
                  type="file"
                  id="imageUpload"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  multiple
                  style="display: none;"
                  @change=${this._handleImageSelect}
                ></input>
                
                <div class="input-main">
                  <!-- Attached images preview -->
                  ${this._attachedImages.length > 0 ? html`
                    <div class="attached-images">
                      ${this._attachedImages.map((img, index) => html`
                        <div class="image-preview">
                          <img src="data:image/jpeg;base64,${img.data}" alt="${img.original_name}" />
                          <button class="remove-image" @click="${() => this._removeImage(index)}">
                            ×
                          </button>
                        </div>
                      `)}
                    </div>
                  ` : ''}
                  <div class="input-wrapper">
                    <textarea
                      id="prompt"
                      placeholder="Ask me anything about your Home Assistant... (Images: ${this._attachedImages.length}/${this._maxImagesPerMessage})"
                      ?disabled=${this._isLoading}
                      @keydown=${this._handleKeyDown}
                      @input=${this._autoResize}
                    ></textarea>
                  </div>
                </div>

                <div class="input-footer">
                  <div class="provider-selector">
                    <span class="provider-label">Model:</span>
                    <select
                      class="provider-button"
                      @change=${(e) => this._selectProvider(e.target.value)}
                      .value=${this._selectedProvider || ''}
                    >
                      ${this._availableProviders.map(provider => html`
                        <option
                          value=${provider.value}
                          ?selected=${provider.value === this._selectedProvider}
                        >
                          ${provider.label}
                        </option>
                      `)}
                    </select>
                  </div>
                  ${this._imageUploadEnabled ? html`
                    <button class="image-btn" @click="${this._triggerImageUpload}" title="Attach image">
                      <ha-icon icon="mdi:image"></ha-icon>
                    </button>
                  ` : ''}
                  <label class="thinking-toggle">
                    <input
                      type="checkbox"
                      .checked=${this._showThinking}
                      @change=${(e) => this._toggleShowThinking(e)}
                    />
                    Show thinking
                  </label>

                  <ha-button
                    class="send-button"
                    @click=${this._sendMessage}
                    .disabled=${this._isLoading || !this._hasProviders()}
                  >
                    <ha-icon icon="mdi:send"></ha-icon>
                  </ha-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      ${this._contextMenu ? this._renderContextMenu() : ''}
    `;
  }
  
  /**
   * Render the context menu for conversations
   */
  _renderContextMenu() {
    if (!this._contextMenu) return '';
    
    return html`
      <div class="context-menu" style="left: ${this._contextMenu.x}px; top: ${this._contextMenu.y}px;">
        <div class="context-menu-item" @click=${() => this._renameConversation(this._contextMenu.conversationId, prompt('Enter new name:'))}>
          <ha-icon icon="mdi:pencil"></ha-icon>
          <span>Rename</span>
        </div>
        <div class="context-menu-item" @click=${() => this._pinConversation(this._contextMenu.conversationId)}>
          <ha-icon icon="mdi:pin"></ha-icon>
          <span>Pin</span>
        </div>
        <div class="context-menu-item" @click=${() => this._exportConversation(this._contextMenu.conversationId)}>
          <ha-icon icon="mdi:download"></ha-icon>
          <span>Export</span>
        </div>
        <div class="context-menu-divider"></div>
        <div class="context-menu-item delete" @click=${() => this._deleteConversation(this._contextMenu.conversationId)}>
          <ha-icon icon="mdi:delete"></ha-icon>
          <span>Delete</span>
        </div>
      </div>
    `;
  }
  
  /**
   * Toggle the history sidebar visibility
   */
  _toggleHistorySidebar() {
    this._showHistorySidebar = !this._showHistorySidebar;
    if (this._showHistorySidebar) {
      this._loadConversations();
    }
  }

  _scrollToBottom() {
    const messages = this.shadowRoot.querySelector('#messages');
    if (messages) {
      messages.scrollTop = messages.scrollHeight;
    }
  }

  /**
   * Check if text contains markdown that needs rendering
   */
  _hasMarkdown(text) {
    if (!text || typeof text !== 'string') return false;
    // Check for common markdown patterns
    const markdownPatterns = [
      /^#{1,6}\s/m,           // Headers
      /^\s*[-*+]\s/m,         // Unordered lists
      /^\s*\d+\.\s/m,         // Ordered lists
      /^```/m,                // Code blocks
      /^`[^`]+`/m,            // Inline code
      /^> /m,                 // Blockquotes
      /^\*\*.*\*\*/m,         // Bold
      /^\*.*\*/m,             // Italic
      /^---/m,                // Horizontal rules
      /^\|.*\|/m              // Tables
    ];
    return markdownPatterns.some(pattern => pattern.test(text));
  }

  /**
   * Format markdown text to HTML with sanitization
   */
  _formatMarkdown(text) {
    if (!text || typeof text !== 'string') return '';
    
    try {
      // Configure marked
      marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false
      });
      
      // Parse markdown to HTML
      let html = marked.parse(text);
      
      // Sanitize HTML to prevent XSS
      html = DOMPurify.sanitize(html, {
        ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 's', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                       'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a', 'hr', 'img'],
        ALLOWED_ATTR: ['href', 'src', 'alt', 'class', 'type', 'border', 'cellpadding', 'cellspacing']
      });
      
      // Add copy buttons to code blocks
      html = this._addCopyButtonsToCodeBlocks(html);
      
      return html;
    } catch (error) {
      console.error('Error formatting markdown:', error);
      // Fallback to plain text
      return text.replace(/\n/g, '<br>');
    }
  }

  /**
   * Add copy buttons to code blocks
   */
  _addCopyButtonsToCodeBlocks(html) {
    // Find all pre>code blocks and wrap with copy button
    return html.replace(/<pre><code([^>]*)>([\s\S]*?)<\/code><\/pre>/g, (match, attrs, code) => {
      const uniqueId = 'code-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
      return `
        <div class="code-block-container">
          <pre>${code}</pre>
          <button class="copy-code-btn" onclick="event.stopPropagation(); this.textContent='Copied!'; this.classList.add('copied'); setTimeout(() => { this.textContent='Copy'; this.classList.remove('copied'); }, 2000); navigator.clipboard.writeText(document.getElementById('${uniqueId}').textContent);">Copy</button>
          <code id="${uniqueId}" style="display:none;">${code}</code>
        </div>
      `;
    });
  }

  /**
   * Render a message with appropriate formatting and UX enhancements
   */
  _renderMessageContent(message) {
    // Render action cards (UX Enhancement)
    if (message.type === 'actionCard') {
      return this._renderActionCard(message.action, message.index, message.total);
    }
    
    if (message.type === 'user') {
      return html`
        <div class="message-content">${message.text}</div>
        ${message.timestamp ? html`
          <div class="response-meta">
            <span>${this._formatRelativeTime(message.timestamp)}</span>
          </div>
        ` : ''}
      `;
    }
    
    // For action report messages, use special styling
    if (message.isActionReport) {
      return html`
        <div class="message-content action-report">${message.text.replace(/\n/g, html`<br>`)}</div>
        ${message.timestamp ? html`
          <div class="response-meta">
            <span>${this._formatRelativeTime(message.timestamp)}</span>
          </div>
        ` : ''}
      `;
    }
    
    // For assistant messages, check if markdown formatting is needed
    if (this._hasMarkdown(message.text)) {
      const htmlContent = this._formatMarkdown(message.text);
      return html`
        <div class="message-content markdown-content" data-html=${htmlContent}></div>
        ${message.timestamp ? html`
          <div class="response-meta">
            <span>${this._formatRelativeTime(message.timestamp)}</span>
          </div>
        ` : ''}
      `;
    }
    
    // Plain text with line breaks and response time
    return html`
      <div class="message-content">${message.text.replace(/\n/g, html`<br>`)}</div>
      ${message.timestamp ? html`
        <div class="response-meta">
          <span>${this._formatRelativeTime(message.timestamp)}</span>
        </div>
      ` : ''}
    `;
  }

  _autoResize(e) {
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
  }

  /**
   * Handle key down events with keyboard shortcuts
   * Ctrl/Cmd + Enter: Send message
   * Escape: Close dropdowns/modals
   * Enter: Send message (without modifier)
   */
  _handleKeyDown(e) {
    // Send message on Ctrl/Cmd + Enter
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      this._sendMessage();
      return;
    }
    
    // Close dropdowns on Escape
    if (e.key === 'Escape') {
      this._showProviderDropdown = false;
      this._showContextMenu = false;
      this.requestUpdate();
      return;
    }
    
    // Send message on Enter (without modifier)
    if (e.key === 'Enter' && !e.shiftKey && !this._isLoading) {
      e.preventDefault();
      this._sendMessage();
    }
  }

  _toggleProviderDropdown() {
    this._showProviderDropdown = !this._showProviderDropdown;
    console.log("Toggling provider dropdown:", this._showProviderDropdown);
    this.requestUpdate(); // Añade esta línea para forzar la actualización
  }

  async _selectProvider(provider) {
    this._selectedProvider = provider;
    console.debug("Provider changed to:", provider);
    await this._loadPromptHistory();
    this.requestUpdate();
  }

  _getSelectedProviderLabel() {
    const provider = this._availableProviders.find(p => p.value === this._selectedProvider);
    return provider ? provider.label : 'Select Model';
  }

  /**
   * Send message to AI with UX enhancements
   */
  async _sendMessage() {
    const promptEl = this.shadowRoot.querySelector('#prompt');
    const prompt = promptEl.value.trim();
    
    // Check if we have images but no text
    if (!prompt && this._attachedImages.length === 0) return;
    if (this._isLoading) return;

    console.debug("Sending message:", prompt);
    console.debug("Sending message with provider:", this._selectedProvider);
    console.debug("Attached images:", this._attachedImages.length);

    // Track send start time for response time measurement
    const sendStartTime = Date.now();

    // Add to history
    await this._addToHistory(prompt || '[Image only]');

    // Add user message with status tracking (UX Enhancement)
    const userDisplayText = prompt || '📷 Image attached';
    this._messages = [...this._messages, {
      type: 'user',
      text: userDisplayText,
      images: this._attachedImages.map(img => img.data),
      status: 'pending',  // UX Enhancement: Message status
      timestamp: sendStartTime
    }];
    
    promptEl.value = '';
    promptEl.style.height = 'auto';
    this._isLoading = true;
    this._error = null;
    this._debugInfo = null;
    this._thinkingExpanded = false; // keep collapsed until a trace arrives
    
    // Show typing indicator (UX Enhancement)
    this._showTyping();

    // Clear any existing timeout
    if (this._serviceCallTimeout) {
      clearTimeout(this._serviceCallTimeout);
    }

    // Set timeout to clear loading state after 10 minutes (for slower/local models)
    this._serviceCallTimeout = setTimeout(() => {
      if (this._isLoading) {
        console.warn("Service call timeout - clearing loading state");
        this._isLoading = false;
        this._showTypingIndicator = false;
        this._error = 'Request timed out. Please try again.';
        this._messages = this._messages.map((msg, i) =>
          i === this._messages.length - 1
            ? { ...msg, status: 'error' }
            : msg
        );
        this._messages = [...this._messages, {
          type: 'assistant',
          text: 'Sorry, the request timed out. Please try again.',
          timestamp: Date.now()
        }];
        this.requestUpdate();
      }
    }, 600000); // 10 minute timeout

    try {
      console.debug("Calling ai_agent_ha service");
      // Send images with prompt
      const serviceData = {
        prompt: prompt || 'Analyze this image',
        provider: this._selectedProvider,
        debug: this._showThinking
      };
      
      if (this._attachedImages.length > 0) {
        serviceData.images = this._attachedImages.map(img => img.data);
        serviceData.mime_types = this._attachedImages.map(img => img.mime_type || 'image/jpeg');
      }
      
      await this.hass.callService('ai_agent_ha', 'query', serviceData);
    } catch (error) {
      console.error("Error calling service:", error);
      this._clearLoadingState();
      this._showTypingIndicator = false;
      this._error = error.message || 'An error occurred while processing your request';
      
      // Update message status to error
      this._messages = this._messages.map((msg, i) =>
        i === this._messages.length - 1
          ? { ...msg, status: 'error' }
          : msg
      );
      this._messages = [...this._messages, {
        type: 'assistant',
        text: `Error: ${this._error}`,
        timestamp: Date.now()
      }];
    }
    
    // Clear attached images after sending
    this._attachedImages = [];
    this.requestUpdate();
  }

  /**
   * Trigger file input click
   */
  _triggerImageUpload() {
    const input = this.shadowRoot.querySelector('#imageUpload');
    if (input) {
      input.click();
    }
  }

  /**
   * Handle image file selection
   */
  async _handleImageSelect(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    // Check limit
    if (this._attachedImages.length + files.length > this._maxImagesPerMessage) {
      alert(`Maximum ${this._maxImagesPerMessage} images per message`);
      return;
    }
    
    // Process each file
    for (const file of files) {
      try {
        const compressed = await this._compressImage(file);
        this._attachedImages = [...this._attachedImages, compressed];
      } catch (error) {
        console.error('Error processing image:', error);
        alert(`Error processing ${file.name}: ${error.message}`);
      }
    }
    
    // Clear input
    event.target.value = '';
    this.requestUpdate();
  }

  /**
   * Compress image client-side
   */
  async _compressImage(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          
          // Resize if too large
          const maxDim = 2048;
          let width = img.width;
          let height = img.height;
          
          if (width > maxDim || height > maxDim) {
            const ratio = Math.min(maxDim / width, maxDim / height);
            width = Math.floor(width * ratio);
            height = Math.floor(height * ratio);
          }
          
          canvas.width = width;
          canvas.height = height;
          ctx.drawImage(img, 0, 0, width, height);
          
          // Compress to JPEG
          canvas.toBlob(
            (blob) => {
              if (!blob) {
                reject(new Error('Failed to compress image'));
                return;
              }
              const reader2 = new FileReader();
              reader2.onload = () => {
                const result = reader2.result;
                const base64Data = result.split(',')[1]; // Base64 only
                resolve({
                  data: base64Data,
                  mime_type: 'image/jpeg',
                  original_name: file.name,
                  width: width,
                  height: height
                });
              };
              reader2.readAsDataURL(blob);
            },
            'image/jpeg',
            0.8 // Quality
          );
        };
        img.src = e.target.result;
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  /**
   * Remove attached image
   */
  _removeImage(index) {
    this._attachedImages = this._attachedImages.filter((_, i) => i !== index);
    this.requestUpdate();
  }

  _clearLoadingState() {
    this._isLoading = false;
    if (this._serviceCallTimeout) {
      clearTimeout(this._serviceCallTimeout);
      this._serviceCallTimeout = null;
    }
  }

  /**
   * Handle AI response from backend event
   */
  _handleLlamaResponse(event) {
    console.debug("Received llama response:", event);
    
    try {
      this._clearLoadingState();
      this._debugInfo = this._showThinking ? (event.data.debug || null) : null;
      if (this._showThinking && this._debugInfo) {
        this._thinkingExpanded = true;
      }
      
      // Hide typing indicator (UX Enhancement)
      this._hideTyping();
      
      // Calculate response time (UX Enhancement)
      const responseStartTime = event.data.response_time || Date.now();
      const responseTimeMs = Date.now() - responseStartTime;

    if (event.data.success) {
      // DEBUG: Log the full response data for debugging empty responses
      console.debug("=== FRONTEND RESPONSE DEBUG === success=%s, answer=%s, answer_length=%d, answer_preview=%s, response_time=%dms, full_event_data=%s",
        event.data.success,
        typeof event.data.answer,
        event.data.answer ? event.data.answer.length : 0,
        event.data.answer ? JSON.stringify(event.data.answer.toString().slice(0, 200)) : "None",
        responseTimeMs,
        JSON.stringify(event.data, (key, value) => key === 'debug' ? '[debug omitted]' : value, 2)
      );
      // Check if the answer is empty
      if (!event.data.answer || event.data.answer.trim() === '') {
        console.error("=== EMPTY RESPONSE DEBUG === event.data=%s, answer_type=%s, answer_value=%s",
          JSON.stringify(event.data, (key, value) => key === 'debug' ? '[debug omitted]' : value, 2),
          typeof event.data.answer,
          event.data.answer);
        console.warn("AI agent returned empty response");
        this._messages = [
          ...this._messages,
          {
            type: 'assistant',
            text: 'I received your message but I\'m not sure how to respond. Could you please try rephrasing your question?',
            timestamp: Date.now()
          }
        ];
        // Update previous user message status to success
        this._messages = this._messages.map((msg, i) =>
          i === this._messages.length - 2 && msg.type === 'user'
            ? { ...msg, status: 'success' }
            : msg
        );
        return;
      }

      let message = { type: 'assistant', text: event.data.answer, timestamp: Date.now() };

      // Check if the response contains an automation or dashboard suggestion
      try {
        console.debug("Attempting to parse response as JSON:", event.data.answer);
        let jsonText = event.data.answer;
        
        // Try to extract JSON from mixed text+JSON responses
        const jsonMatch = jsonText.match(/\{[\s\S]*\}/);
        if (jsonMatch && jsonMatch[0] !== jsonText.trim()) {
          console.debug("Found JSON within mixed response, extracting:", jsonMatch[0]);
          jsonText = jsonMatch[0];
        }
        
        const response = JSON.parse(jsonText);
        console.debug("Parsed JSON response:", response);
        
        if (response.request_type === 'automation_suggestion') {
          console.debug("Found automation suggestion");
          message.automation = response.automation;
          message.text = response.message || 'I found an automation that might help you. Would you like me to create it?';
        } else if (response.request_type === 'dashboard_suggestion') {
          console.debug("Found dashboard suggestion:", response.dashboard);
          message.dashboard = response.dashboard;
          message.text = response.message || 'I created a dashboard configuration for you. Would you like me to create it?';
        } else if (response.request_type === 'final_response') {
          // If it's a final response, use the response field
          message.text = response.response || response.message || event.data.answer;
        } else if (response.message) {
          // If there's a message field, use it
          message.text = response.message;
        } else if (response.response) {
          // If there's a response field, use it
          message.text = response.response;
        }
        // If none of the above, keep the original event.data.answer as message.text
      } catch (e) {
        // Not a JSON response, treat as normal message
        console.debug("Response is not JSON, using as-is:", event.data.answer);
        console.debug("JSON parse error:", e);
        // message.text is already set to event.data.answer
      }

      console.debug("Adding message to UI:", message);
      
      // Add action details to message if present
      if (event.data.action_details && Array.isArray(event.data.action_details) && event.data.action_details.length > 0) {
        message.action_details = event.data.action_details;
        console.debug("Found action details:", event.data.action_details);
      }
      
      this._messages = [...this._messages, message];
      
      // Update the last user message status to success (UX Enhancement)
      this._messages = this._messages.map((msg, i) =>
        i === this._messages.length - 2 && msg.type === 'user'
          ? { ...msg, status: 'success' }
          : msg
      );
      
      // If there are action details, add a separate message showing the actions performed
      if (event.data.action_details && Array.isArray(event.data.action_details) && event.data.action_details.length > 0) {
        const actionMessages = this._formatActionDetails(event.data.action_details);
        this._messages = [...this._messages, ...actionMessages];
      }
      
      // Auto-save the current conversation after receiving a response
      this._saveCurrentConversation();
    } else {
      this._showTypingIndicator = false;
      this._error = event.data.error || 'An error occurred';
      
      // Update previous user message status to error
      this._messages = this._messages.map((msg, i) =>
        i === this._messages.length - 1 && msg.type === 'user'
          ? { ...msg, status: 'error' }
          : msg
      );
      
      this._messages = [
        ...this._messages,
        {
          type: 'assistant',
          text: `Error: ${this._error}`,
          timestamp: Date.now()
        }
      ];
    }
    } catch (error) {
      console.error("Error in _handleLlamaResponse:", error);
      this._clearLoadingState();
      this._error = 'An error occurred while processing the response';
      this._messages = [...this._messages, {
        type: 'assistant',
        text: 'Sorry, an error occurred while processing the response. Please try again.'
      }];
      this.requestUpdate();
    }
  }
  
  /**
   * Format action details for display in chat with action cards
   * @param {Array} actionDetails - Array of action detail objects
   * @returns {Array} Array of message objects for display
   */
  _formatActionDetails(actionDetails) {
    const messages = [];
    
    // Add a header message with action count
    const actionTypes = new Set(actionDetails.map(a => `${a.domain}.${a.service}`));
    let actionSummary = '';
    
    if (actionDetails.length === 1) {
      const action = actionDetails[0];
      const targetEntities = Array.isArray(action.target?.entity_id)
        ? action.target.entity_id.join(', ')
        : action.target?.entity_id || 'N/A';
      
      actionSummary = `I performed the following action:\n\n`;
      actionSummary += `**${action.domain}.${action.service}** → ${targetEntities}`;
    } else {
      actionSummary = `I performed ${actionDetails.length} actions:\n\n`;
      actionDetails.forEach((action, index) => {
        const targetEntities = Array.isArray(action.target?.entity_id)
          ? action.target.entity_id.join(', ')
          : action.target?.entity_id || 'N/A';
        
        actionSummary += `${index + 1}. **${action.domain}.${action.service}** → ${targetEntities}\n`;
      });
    }
    
    // Add action summary message
    messages.push({
      type: 'assistant',
      text: actionSummary,
      isActionReport: true
    });
    
    // Add individual action cards (UX Enhancement)
    actionDetails.forEach((action, index) => {
      messages.push({
        type: 'actionCard',
        action: action,
        index: index,
        total: actionDetails.length
      });
    });
    
    return messages;
  }

  async _approveAutomation(automation) {
    if (this._isLoading) return;
    this._isLoading = true;
    try {
      const result = await this.hass.callService('ai_agent_ha', 'create_automation', {
        automation: automation
      });

      console.debug("Automation creation result:", result);

      // The result should be an object with a message property
      if (result && result.message) {
        this._messages = [...this._messages, {
          type: 'assistant',
          text: result.message
        }];
      } else {
        // Fallback success message if no message is provided
        this._messages = [...this._messages, {
          type: 'assistant',
          text: `Automation "${automation.alias}" has been created successfully!`
        }];
      }
    } catch (error) {
      console.error("Error creating automation:", error);
      this._error = error.message || 'An error occurred while creating the automation';
      this._messages = [...this._messages, {
        type: 'assistant',
        text: `Error: ${this._error}`
      }];
    } finally {
      this._clearLoadingState();
    }
  }

  _rejectAutomation() {
    this._messages = [...this._messages, {
      type: 'assistant',
      text: 'Automation creation cancelled. Would you like to try something else?'
    }];
  }

  async _approveDashboard(dashboard) {
    if (this._isLoading) return;
    this._isLoading = true;
    try {
      const result = await this.hass.callService('ai_agent_ha', 'create_dashboard', {
        dashboard_config: dashboard
      });

      console.debug("Dashboard creation result:", result);

      // The result should be an object with a message property
      if (result && result.message) {
        this._messages = [...this._messages, {
          type: 'assistant',
          text: result.message
        }];
      } else {
        // Fallback success message if no message is provided
        this._messages = [...this._messages, {
          type: 'assistant',
          text: `Dashboard "${dashboard.title}" has been created successfully!`
        }];
      }
    } catch (error) {
      console.error("Error creating dashboard:", error);
      this._error = error.message || 'An error occurred while creating the dashboard';
      this._messages = [...this._messages, {
        type: 'assistant',
        text: `Error: ${this._error}`
      }];
    } finally {
      this._clearLoadingState();
    }
  }

  _rejectDashboard() {
    this._messages = [...this._messages, {
      type: 'assistant',
      text: 'Dashboard creation cancelled. Would you like me to create a different dashboard?'
    }];
  }

  shouldUpdate(changedProps) {
    // Only update if internal state changes, not on every hass update
    return changedProps.has('_messages') ||
           changedProps.has('_isLoading') ||
           changedProps.has('_error') ||
           changedProps.has('_promptHistory') ||
           changedProps.has('_showPredefinedPrompts') ||
           changedProps.has('_showPromptHistory') ||
           changedProps.has('_availableProviders') ||
           changedProps.has('_selectedProvider') ||
           changedProps.has('_showProviderDropdown');
  }

  // ========== Chat History Methods ==========
  
  /**
   * Load the list of conversations from the backend
   */
  async _loadConversations() {
    if (!this.hass) return;
    
    try {
      // Use WebSocket command to get conversations directly
      const result = await this.hass.callWS({
        type: 'ai_agent_ha/get_conversations'
      });
      if (result && result.conversations) {
        this._conversations = result.conversations;
      } else if (result && Array.isArray(result)) {
        this._conversations = result;
      } else if (result && result.success) {
        // Service call format
        this._conversations = result.conversations || [];
      }
      console.debug('Loaded conversations:', this._conversations);
    } catch (error) {
      console.error('Error loading conversations:', error);
      this._conversations = [];
    }
  }
  
  /**
   * Save the current conversation to the backend with UX status
   */
  async _saveCurrentConversation() {
    if (!this.hass || this._messages.length === 0) return;
    
    // Set saving status (UX Enhancement)
    this._saveStatus = 'saving';
    this.requestUpdate();
    
    try {
      const conversationId = this._currentConversationId || crypto.randomUUID();
      const messages = this._messages.map(msg => ({
        type: msg.type,
        text: msg.text,
        ...(msg.images ? { images: msg.images } : {}),
        ...(msg.automation ? { automation: msg.automation } : {}),
        ...(msg.dashboard ? { dashboard: msg.dashboard } : {})
      }));
      
      // Generate name from first user message
      let name = '';
      for (const msg of this._messages) {
        if (msg.type === 'user') {
          name = msg.text.slice(0, 50);
          if (msg.text.length > 50) name += '...';
          break;
        }
      }
      if (!name) name = 'New Conversation';
      
      const result = await this.hass.callWS({
        type: 'ai_agent_ha/save_conversation',
        conversation_id: conversationId,
        name: name,
        messages: messages
      });
      
      if (result && result.success) {
        if (!this._currentConversationId) {
          this._currentConversationId = conversationId;
        }
        this._saveStatus = 'saved';
        await this._loadConversations();
        this.requestUpdate();
        
        // Clear saved status after 2 seconds
        setTimeout(() => {
          this._saveStatus = null;
          this.requestUpdate();
        }, 2000);
      }
    } catch (error) {
      console.error('Error saving conversation:', error);
      this._saveStatus = 'error';
      this.requestUpdate();
      
      // Clear error status after 3 seconds
      setTimeout(() => {
        this._saveStatus = null;
        this.requestUpdate();
      }, 3000);
    }
  }
  
  /**
   * Load a specific conversation with UX status indicators
   */
  async _loadConversation(conversationId) {
    if (!this.hass) return;
    
    // Set loading status (UX Enhancement)
    this._loadStatus = 'loading';
    this.requestUpdate();
    
    try {
      const result = await this.hass.callWS({
        type: 'ai_agent_ha/get_conversation',
        conversation_id: conversationId
      });
      
      if (result && result.messages) {
        this._messages = result.messages;
        this._currentConversationId = conversationId;
        this._loadStatus = 'loaded';
        await this._loadConversations();
        this.requestUpdate();
        
        // Clear loaded status after 2 seconds
        setTimeout(() => {
          this._loadStatus = null;
          this.requestUpdate();
        }, 2000);
      }
    } catch (error) {
      console.error('Error loading conversation:', error);
      this._loadStatus = 'error';
      this.requestUpdate();
    }
  }
  
  /**
   * Create a new conversation and reset the chat
   */
  _createNewConversation() {
    this._messages = [];
    this._currentConversationId = null;
    this._error = null;
    this._debugInfo = null;
    this._pendingAutomation = null;
    this.requestUpdate();
  }
  
  /**
   * Delete a conversation
   */
  async _deleteConversation(conversationId) {
    if (!this.hass) return;
    
    if (!confirm('Are you sure you want to delete this conversation?')) return;
    
    try {
      const result = await this.hass.callWS({
        type: 'ai_agent_ha/delete_conversation',
        conversation_id: conversationId
      });
      
      if (result && result.success) {
        if (this._currentConversationId === conversationId) {
          this._createNewConversation();
        }
        await this._loadConversations();
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
    }
  }
  
  /**
   * Rename a conversation
   */
  async _renameConversation(conversationId, newName) {
    if (!this.hass || !newName || !newName.trim()) return;
    
    try {
      const result = await this.hass.callWS({
        type: 'ai_agent_ha/rename_conversation',
        conversation_id: conversationId,
        name: newName.trim()
      });
      
      if (result && result.success) {
        await this._loadConversations();
      }
    } catch (error) {
      console.error('Error renaming conversation:', error);
    }
  }
  
  /**
   * Export a conversation as JSON
   */
  async _exportConversation(conversationId) {
    if (!this.hass) return;
    
    try {
      const result = await this.hass.callWS({
        type: 'ai_agent_ha/export_conversation',
        conversation_id: conversationId
      });
      
      if (result && result.success && result.data) {
        const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `conversation-${conversationId}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Error exporting conversation:', error);
    }
  }
  
  /**
   * Toggle pin status of a conversation
   */
  async _pinConversation(conversationId) {
    if (!this.hass) return;
    
    try {
      const result = await this.hass.callWS({
        type: 'ai_agent_ha/pin_conversation',
        conversation_id: conversationId
      });
      
      if (result && result.success) {
        await this._loadConversations();
      }
    } catch (error) {
      console.error('Error pinning conversation:', error);
    }
  }
  
  /**
   * Add a tag to a conversation
   */
  async _addTagToConversation(conversationId, tag) {
    if (!this.hass || !tag) return;
    
    try {
      const result = await this.hass.callWS({
        type: 'ai_agent_ha/add_tag',
        conversation_id: conversationId,
        tag: tag.trim()
      });
      
      if (result && result.success) {
        await this._loadConversations();
      }
    } catch (error) {
      console.error('Error adding tag:', error);
    }
  }
  
  /**
   * Handle conversation search/filter
   */
  _handleConversationSearch(query) {
    this._conversationSearchQuery = query;
  }
  
  /**
   * Get filtered conversations based on search query
   */
  get _filteredConversations() {
    if (!this._conversationSearchQuery || !this._conversationSearchQuery.trim()) {
      return this._conversations;
    }
    
    const query = this._conversationSearchQuery.toLowerCase();
    return this._conversations.filter(conv => {
      return (
        (conv.name && conv.name.toLowerCase().includes(query)) ||
        (conv.preview && conv.preview.toLowerCase().includes(query)) ||
        (conv.tags && conv.tags.some(tag => tag.toLowerCase().includes(query))) ||
        (conv.conversation_id && conv.conversation_id.includes(query))
      );
    });
  }
  
  /**
   * Format date for display
   */
  _formatConversationDate(dateString) {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  }
  
  /**
   * Show context menu for a conversation
   */
  _showContextMenu(event, conversationId) {
    event.preventDefault();
    event.stopPropagation();
    
    this._contextMenu = {
      x: event.clientX,
      y: event.clientY,
      conversationId: conversationId
    };
    
    this.requestUpdate();
  }
  
  /**
   * Hide context menu
   */
  _hideContextMenu() {
    this._contextMenu = null;
    this.requestUpdate();
  }
  
  // ========== UX Enhancement Methods ==========
  
  /**
   * Format response time in a human-readable format
   * @param {number} milliseconds - Response time in milliseconds
   * @returns {string} Formatted response time string
   */
  _formatResponseTime(milliseconds) {
    if (!milliseconds || milliseconds < 0) return '';
    if (milliseconds < 1000) return `${milliseconds}ms`;
    return `${(milliseconds / 1000).toFixed(1)}s`;
  }
  
  /**
   * Format relative time (e.g., "2 minutes ago")
   * @param {number} timestamp - Unix timestamp in milliseconds
   * @returns {string} Relative time string
   */
  _formatRelativeTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) return 'just now';
    if (diffMin < 60) return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`;
    if (diffHour < 24) return `${diffHour} hour${diffHour !== 1 ? 's' : ''} ago`;
    if (diffDay < 7) return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`;
    return date.toLocaleDateString();
  }
  
  /**
   * Show typing indicator when AI is processing
   */
  _showTyping() {
    this._showTypingIndicator = true;
    this.requestUpdate();
  }
  
  /**
   * Hide typing indicator when AI response is received
   */
  _hideTyping() {
    this._showTypingIndicator = false;
    this.requestUpdate();
  }
  
  /**
   * Show user-friendly error message with auto-dismiss
   * @param {string} message - Main error message
   * @param {string} details - Optional error details
   */
  _showError(message, details = '') {
    this._errorMessage = message;
    this._errorDetails = details;
    this.requestUpdate();
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      this._errorMessage = null;
      this._errorDetails = null;
      this.requestUpdate();
    }, 5000);
  }
  
  /**
   * Hide error message
   */
  _hideError() {
    this._errorMessage = null;
    this._errorDetails = null;
    this.requestUpdate();
  }
  
  /**
   * Render error banner with retry option
   */
  _renderErrorBanner() {
    if (!this._errorMessage) return '';
    
    return html`
      <div class="error-banner">
        <ha-icon icon="mdi:alert-circle" style="color: #f44336; --mdc-icon-size: 20px;"></ha-icon>
        <div class="error-content">
          <div class="error-message">${this._errorMessage}</div>
          ${this._errorDetails ? html`<div class="error-details">${this._errorDetails}</div>` : ''}
        </div>
        <button class="retry-button" @click=${this._retryLastAction}>Retry</button>
      </div>
    `;
  }
  
  /**
   * Render typing indicator with animated dots
   */
  _renderTypingIndicator() {
    if (!this._showTypingIndicator) return '';
    
    return html`
      <div class="typing-indicator">
        <span>.</span>
        <span>.</span>
        <span>.</span>
      </div>
    `;
  }
  
  /**
   * Render action card with status
   * @param {Object} action - Action object with domain, service, target, result
   * @returns {Template} Rendered action card
   */
  _renderActionCard(action, index, total) {
    const domain = action.domain || 'unknown';
    const service = action.service || 'unknown';
    const target = action.target || {};
    const result = action.result || {};
    
    const isSuccess = result?.success !== false;
    const hasError = result?.error !== undefined;
    const statusIcon = hasError ? '❌' : (isSuccess ? '✅' : '⏳');
    const cardClass = hasError ? 'error' : (isSuccess ? 'success' : 'in-progress');
    
    return html`
      <div class="action-card ${cardClass}">
        <div class="action-header">
          <span class="action-badge">${domain}/${service}</span>
          <span class="action-status">${statusIcon}</span>
        </div>
        ${target?.entity_id ? html`
          <div class="action-target">
            <ha-icon icon="mdi:cursor-pointer"></ha-icon>
            ${Array.isArray(target.entity_id) ? target.entity_id.join(', ') : target.entity_id}
          </div>
        ` : ''}
        ${target?.area_id ? html`
          <div class="action-target">
            <ha-icon icon="mdi:map-marker"></ha-icon>
            Area: ${target.area_id}
          </div>
        ` : ''}
        ${hasError ? html`
          <div class="action-error">${result.error || 'Unknown error'}</div>
        ` : ''}
      </div>
    `;
  }
  
  /**
   * Render action progress during execution
   * @param {Array} actions - Array of actions being executed
   * @param {number} currentIndex - Current action index
   */
  _renderActionProgress(actions, currentIndex = -1) {
    if (!actions || actions.length === 0) return '';
    
    const currentAction = currentIndex >= 0 ? actions[currentIndex] : null;
    const progress = ((currentIndex) / actions.length) * 100;
    
    return html`
      <div class="action-progress">
        <div class="action-progress-header">
          <div class="action-progress-spinner"></div>
          <span>${currentAction ?
            `Executing action ${currentIndex + 1} of ${actions.length}: ${currentAction.domain}/${currentAction.service}` :
            `Executing ${actions.length} actions...`
          }</span>
        </div>
        <div class="action-progress-bar">
          <div class="action-progress-fill" style="width: ${progress}%"></div>
        </div>
      </div>
    `;
  }
  
  /**
   * Render message status indicator
   * @param {string} status - Message status: 'pending', 'success', 'error'
   */
  _renderMessageStatus(status) {
    if (!status || status === 'success') return '';
    
    if (status === 'pending') {
      return html`
        <div class="message-status pending">
          <div class="status-spinner"></div>
          <span>Sending...</span>
        </div>
      `;
    }
    
    if (status === 'error') {
      return html`
        <div class="message-status error">
          <ha-icon icon="mdi:alert-circle"></ha-icon>
          <span>Failed to send</span>
        </div>
      `;
    }
    
    return '';
  }
  
  /**
   * Render save/load status indicator
   */
  _renderConversationStatus() {
    if (this._saveStatus === 'saving') {
      return html`
        <div class="status-indicator saving">
          <div class="status-spinner"></div>
          <span>Saving...</span>
        </div>
      `;
    }
    
    if (this._saveStatus === 'saved') {
      return html`
        <div class="status-indicator saved">
          <ha-icon icon="mdi:check-circle"></ha-icon>
          <span>Saved</span>
        </div>
      `;
    }
    
    if (this._loadStatus === 'loading') {
      return html`
        <div class="status-indicator loading">
          <div class="status-spinner"></div>
          <span>Loading...</span>
        </div>
      `;
    }
    
    return '';
  }
  
  /**
   * Render skeleton loading screens
   */
  _renderSkeletonLoading() {
    return html`
      <div class="skeleton skeleton-message"></div>
      <div class="skeleton skeleton-message"></div>
      <div class="skeleton skeleton-message"></div>
    `;
  }
  
  /**
   * Retry the last action (send message again)
   */
  async _retryLastAction() {
    this._hideError();
    
    // Find the last user message
    const lastUserMessage = [...this._messages].reverse().find(m => m.type === 'user');
    if (lastUserMessage) {
      // Clear error and retry
      this._error = null;
      await this._sendMessage();
    }
  }
  
  _clearChat() {
    this._messages = [];
    this._clearLoadingState();
    this._error = null;
    this._pendingAutomation = null;
    this._debugInfo = null;
    this._errorMessage = null;
    this._errorDetails = null;
    this._saveStatus = null;
    this._loadStatus = null;
    // Don't clear prompt history - users might want to keep it
  }

  _resolveProviderFromEntry(entry) {
    if (!entry) return null;

    const providerFromData = entry.data?.ai_provider || entry.options?.ai_provider;
    if (providerFromData && PROVIDERS[providerFromData]) {
      return providerFromData;
    }

    const uniqueId = entry.unique_id || entry.uniqueId;
    if (uniqueId && uniqueId.startsWith("ai_agent_ha_")) {
      const fromUniqueId = uniqueId.replace("ai_agent_ha_", "");
      if (PROVIDERS[fromUniqueId]) {
        return fromUniqueId;
      }
    }

    // Fallback: try to match from title (case-insensitive, partial match)
    if (entry.title) {
      const lowerTitle = entry.title.toLowerCase();

      // Direct keyword match for known providers
      const keywordMap = [
        { key: "openai_compatible", keywords: ["openai-compatible", "openai compatible"] },
        { key: "local_ollama", keywords: ["local ollama", "ollama"] },
        { key: "openrouter", keywords: ["openrouter"] },
        { key: "gemini", keywords: ["google gemini", "gemini"] },
        { key: "openai", keywords: ["openai"] },
        { key: "llama", keywords: ["llama"] },
        { key: "anthropic", keywords: ["anthropic", "claude"] },
        { key: "alter", keywords: ["alter"] },
        { key: "zai", keywords: ["z.ai"] },
        { key: "local", keywords: ["local model"] },
      ];

      for (const { key, keywords } of keywordMap) {
        if (PROVIDERS[key] && keywords.some(k => lowerTitle.includes(k))) {
          return key;
        }
      }
    }

    return null;
  }

  _getProviderInfo(providerId) {
    return this._availableProviders.find(p => p.value === providerId);
  }

  _hasProviders() {
    return this._availableProviders && this._availableProviders.length > 0;
  }

  _toggleThinkingPanel() {
    this._thinkingExpanded = !this._thinkingExpanded;
  }

  _toggleShowThinking(e) {
    this._showThinking = e.target.checked;
    if (!this._showThinking) {
      this._thinkingExpanded = false;
    }
  }

  _renderThinkingPanel() {
    if (!this._debugInfo) {
      return '';
    }

    const subtitleParts = [];
    if (this._debugInfo.provider) subtitleParts.push(this._debugInfo.provider);
    if (this._debugInfo.model) subtitleParts.push(this._debugInfo.model);
    if (this._debugInfo.endpoint_type) subtitleParts.push(this._debugInfo.endpoint_type);
    const subtitle = subtitleParts.join(" · ");
    const conversation = this._debugInfo.conversation || [];

    return html`
      <div class="thinking-panel">
        <div class="thinking-header" @click=${() => this._toggleThinkingPanel()}>
          <div>
            <span class="thinking-title">Thinking trace</span>
            ${subtitle ? html`<span class="thinking-subtitle">${subtitle}</span>` : ''}
          </div>
          <ha-icon icon=${this._thinkingExpanded ? 'mdi:chevron-up' : 'mdi:chevron-down'}></ha-icon>
        </div>
        ${this._thinkingExpanded ? html`
          <div class="thinking-body">
            ${conversation.length === 0 ? html`
              <div class="thinking-empty">No trace captured.</div>
            ` : conversation.map((entry, index) => html`
              <div class="thinking-entry">
                <div class="badge">${entry.role || 'unknown'}</div>
                <pre>${entry.content || ''}</pre>
              </div>
            `)}
          </div>
        ` : ''}
      </div>
    `;
  }
}

customElements.define("ai_agent_ha-panel", AiAgentHaPanel);

console.log("AI Agent HA Panel registered");
