## Enhancement #2: Output Formatting (Markdown Rendering)

### Problem Statement
AI responses are rendered as plain text in the chat UI. Users see raw markdown syntax (`**bold**`, `### headings`, code fences, etc.) without any formatting.

### Solution Architecture

```
┌──────────────────────────────────────────────────┐
│           ai_agent_ha-panel.js                   │
│                                                  │
│  AI Response (raw text with markdown)            │
│         │                                        │
│         ▼                                        │
│  ┌──────────────────┐                            │
│  │ _formatMessage() │                            │
│  │                  │                            │
│  │ 1. marked.parse()│  ← marked.js CDN          │
│  │    (md → html)   │                            │
│  │                  │                            │
│  │ 2. hljs.         │  ← highlight.js CDN       │
│  │    highlightAll() │                            │
│  │    (code blocks) │                            │
│  │                  │                            │
│  │ 3. _sanitize()   │  ← DOMPurify or custom    │
│  │    (XSS prevent) │                            │
│  └────────┬─────────┘                            │
│           │                                      │
│           ▼                                      │
│  ┌─────────────────────────┐                    │
│  │ lit-html unsafeHTML    │                    │
│  │ directive for rendering │                    │
│  └─────────────────────────┘                    │
│           │                                      │
│           ▼                                      │
│  Formatted message in chat bubble               │
│  - Headings rendered                             │
│  - Bold/Italic applied                           │
│  - Code blocks with syntax highlight             │
│  - Copy button on code blocks                    │
│  - Links open in new tab                         │
└──────────────────────────────────────────────────┘
```

### Changes to [`manifest.json`](custom_components/ai_agent_ha/manifest.json)

No changes needed - `marked` and `highlight.js` are loaded from CDN in the frontend JS, not as Python dependencies. The `manifest.json` `requirements` field is for Python packages only.

### Changes to [`ai_agent_ha-panel.js`](custom_components/ai_agent_ha/frontend/ai_agent_ha-panel.js)

**Step 1: Add CDN imports at the top of the file (after existing imports):**

```javascript
// Markdown and syntax highlighting support
import { unsafeHTML } from "https://unpkg.com/lit-html@2.8.0/directives/unsafe-html.js?module";

// marked.js - loaded dynamically to avoid blocking
let marked = null;
async function loadMarked() {
  if (marked) return marked;
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js';
  document.head.appendChild(script);
  await new Promise((resolve) => { script.onload = resolve; });
  marked = window.marked;
  // Configure marked
  marked.setOptions({
    breaks: true,
    gfm: true,
  });
  return marked;
}

// highlight.js - loaded dynamically
let hljs = null;
async function loadHljs() {
  if (hljs) return hljs;
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/highlight.min.js';
  document.head.appendChild(script);
  await new Promise((resolve) => { script.onload = resolve; });
  
  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = 'https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/styles/github-dark.min.css';
  document.head.appendChild(css);
  
  hljs = window.hljs;
  return hljs;
}

// Lazy-load libraries when first needed
let librariesLoaded = false;
async function ensureLibraries() {
  if (librariesLoaded) return;
  await Promise.all([loadMarked(), loadHljs()]);
  librariesLoaded = true;
}
```

**Step 2: Add these methods to the `AiAgentHaPanel` class:**

```javascript
// Inside the AiAgentHaPanel class

_formatMessage(text) {
  if (!text) return '';
  
  // Check if text contains markdown syntax
  if (!this._hasMarkdown(text)) {
    // Simple text - just escape HTML and convert newlines
    return this._escapeHtml(text).replace(/\n/g, '<br>');
  }
  
  try {
    // Parse markdown to HTML
    let html = marked.parse(text);
    
    // Apply syntax highlighting to code blocks
    // highlight.js works on DOM elements, so we do it post-render
    // via the updated() lifecycle method
    
    // Sanitize HTML to prevent XSS
    html = this._sanitize(html);
    
    return html;
  } catch (e) {
    console.warn('Markdown parsing failed, falling back to plain text:', e);
    return this._escapeHtml(text).replace(/\n/g, '<br>');
  }
}

_hasMarkdown(text) {
  // Check for common markdown patterns
  const mdPatterns = [
    /^#{1,6}\s/m,           // headings
    /\*\*.*?\*\*/,          // bold
    /\*.*?\*/,              // italic
    /```[\s\S]*?```/,       // code blocks
    /`[^`]+`/,              // inline code
    /^\s*[-*+]\s/m,         // unordered lists
    /^\s*\d+\.\s/m,         // ordered lists
    /\[.*?\]\(.*?\)/,       // links
    /^\s*>\s/m,             // blockquotes
    /~~.*?~~/,              // strikethrough
  ];
  return mdPatterns.some(pattern => pattern.test(text));
}

_sanitize(html) {
  // Custom HTML sanitizer to prevent XSS
  // In production, use DOMPurify: https://github.com/cure53/DOMPurify
  
  // Create a temporary DOM element
  const temp = document.createElement('div');
  temp.innerHTML = html;
  
  // Remove dangerous elements and attributes
  const dangerousTags = ['script', 'iframe', 'object', 'embed', 'form', 'input', 'link', 'style', 'meta'];
  const dangerousAttrs = ['onerror', 'onclick', 'onload', 'onmouseover', 'onfocus', 'onblur', 
                          'href="javascript:', 'src="javascript:', 'action="javascript:'];
  
  // Walk the DOM tree
  const walk = (node) => {
    if (node.nodeType === Node.ELEMENT_NODE) {
      // Remove dangerous elements
      if (dangerousTags.includes(node.tagName.toLowerCase())) {
        node.remove();
        return;
      }
      
      // Remove dangerous attributes
      for (const attr of [...node.attributes]) {
        const attrStr = `${attr.name}="${attr.value}"`.toLowerCase();
        if (dangerousAttrs.some(d => attrStr.includes(d)) || attr.name.startsWith('on')) {
          node.removeAttribute(attr.name);
        }
      }
      
      // Add target="_blank" and rel="noopener" to links
      if (node.tagName.toLowerCase() === 'a') {
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
      }
      
      // Add copy button to code blocks
      if (node.tagName.toLowerCase() === 'pre') {
        this._addCopyButtonToCodeBlock(node);
      }
    }
    
    // Recurse (use Array.from since childNodes is a live list)
    for (const child of Array.from(node.childNodes)) {
      walk(child);
    }
  };
  
  walk(temp);
  return temp.innerHTML;
}

_addCopyButtonToCodeBlock(preElement) {
  // Check if button already exists
  if (preElement.querySelector('.code-copy-btn')) return;
  
  const button = document.createElement('button');
  button.className = 'code-copy-btn';
  button.textContent = 'Copy';
  button.addEventListener('click', (e) => {
    e.stopPropagation();
    const code = preElement.querySelector('code');
    const text = code ? code.textContent : preElement.textContent;
    navigator.clipboard.writeText(text).then(() => {
      button.textContent = 'Copied!';
      setTimeout(() => { button.textContent = 'Copy'; }, 2000);
    }).catch(() => {
      button.textContent = 'Failed';
      setTimeout(() => { button.textContent = 'Copy'; }, 2000);
    });
  });
  
  // Wrap pre in a container for positioning
  const wrapper = document.createElement('div');
  wrapper.className = 'code-block-wrapper';
  preElement.parentNode.insertBefore(wrapper, preElement);
  wrapper.appendChild(preElement);
  wrapper.appendChild(button);
}

_escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Override updated() to apply highlight.js to code blocks
async updated(changedProps) {
  // ... existing updated logic ...
  
  // Apply syntax highlighting to newly rendered code blocks
  if (changedProps.has('_messages') && librariesLoaded && hljs) {
    await this.updateComplete;  // Wait for Lit render
    const shadow = this.shadowRoot;
    if (shadow) {
      shadow.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
      });
    }
  }
}
```

**Step 3: Modify the `render()` method to use `_formatMessage()`:**

In the message rendering section of `render()`, change:

```javascript
// OLD:
${message.text}

// NEW:
${message.type === 'assistant' 
  ? unsafeHTML(this._formatMessage(message.text))
  : this._escapeHtml(message.text).replace(/\n/g, '<br>')}
```

**Step 4: Add markdown CSS styles to the static `styles` getter:**

```css
/* Markdown formatting styles */
.message-content h1 { font-size: 1.6em; margin: 8px 0; border-bottom: 1px solid var(--divider-color); }
.message-content h2 { font-size: 1.4em; margin: 8px 0; }
.message-content h3 { font-size: 1.2em; margin: 6px 0; }
.message-content h4, .message-content h5, .message-content h6 { font-size: 1.05em; margin: 4px 0; }

.message-content strong { font-weight: 600; }
.message-content em { font-style: italic; }

.message-content ul, .message-content ol {
  margin: 6px 0 6px 20px;
  padding: 0;
}
.message-content li { margin: 2px 0; }

.message-content blockquote {
  border-left: 3px solid var(--primary-color);
  margin: 8px 0;
  padding: 4px 12px;
  background: var(--secondary-background-color);
  border-radius: 0 4px 4px 0;
  opacity: 0.9;
}

.message-content a {
  color: var(--primary-color);
  text-decoration: underline;
}
.message-content a:hover {
  opacity: 0.8;
}

.message-content p { margin: 4px 0; line-height: 1.5; }

.message-content hr {
  border: none;
  border-top: 1px solid var(--divider-color);
  margin: 12px 0;
}

/* Inline code */
.message-content code:not(pre code) {
  background: var(--secondary-background-color);
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
  border: 1px solid var(--divider-color);
}

/* Code blocks */
.code-block-wrapper {
  position: relative;
  margin: 8px 0;
}
.message-content pre {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 14px;
  border-radius: 6px;
  overflow-x: auto;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.5;
  border: 1px solid var(--divider-color);
  margin: 0;
}
.message-content pre code {
  background: none;
  padding: 0;
  border: none;
}

.code-copy-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(255,255,255,0.1);
  color: #cdd6f4;
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 4px;
  padding: 3px 8px;
  cursor: pointer;
  font-size: 11px;
  transition: all 0.2s;
}
.code-copy-btn:hover {
  background: rgba(255,255,255,0.2);
}

/* Tables */
.message-content table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.message-content th, .message-content td {
  border: 1px solid var(--divider-color);
  padding: 6px 10px;
  text-align: left;
}
.message-content th {
  background: var(--secondary-background-color);
  font-weight: 600;
}

/* Images */
.message-content img {
  max-width: 100%;
  border-radius: 6px;
  margin: 8px 0;
}
```

---
