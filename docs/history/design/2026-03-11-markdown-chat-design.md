# Markdown Chat Responses Design

**Date**: 2026-03-11
**Branch**: `feature/markdown-chat-responses`
**Status**: Approved

## Problem

AI chat responses stream as plain text. Claude naturally outputs markdown (bold, lists, code blocks, headers), but the app renders these as literal characters. Users see `**word**` instead of **word**.

## Decision

Server-side markdown rendering using Python `markdown` library, piped through existing `nh3` sanitization. Render on stream completion (not during streaming).

## Architecture

```
Claude LLM -> markdown text (streamed as plain text tokens)
                | (on completion)
         markdown.markdown() -> raw HTML
                |
         nh3.clean() -> sanitized HTML
                |
         SSE "response_complete" event carries rendered HTML
                |
         Client replaces plain-text bubble with rendered HTML
```

## Changes

### 1. Python dependency
- Add `markdown>=3.7` to `pyproject.toml`

### 2. `src/api/sanitize.py`
- Add `render_markdown(text) -> str`: calls `markdown.markdown()` with `fenced_code` and `tables` extensions, then pipes through `sanitize_html()`

### 3. `src/api/streaming.py`
- In `response_complete` SSE event, pass accumulated response through `render_markdown()`
- Add `rendered_html` field to event data

### 4. `src/static/js/modules/stream.js`
- On `response_complete`, replace streaming bubble text with `rendered_html` via `innerHTML`

### 5. CSS in `src/templates/base.html`
- Styles for markdown elements inside `.text-ai-text`: headings, lists, code blocks, blockquotes, tables, paragraphs

### 6. Template partials
- `message.html`, `message_pair.html`: use `render_markdown` filter for history messages

## What stays the same
- Streaming UX: plain text tokens via `insertAdjacentText()`
- User messages: escaped, no markdown
- Security: nh3 sanitization, CSP nonces
- TTS: raw text from `data-text` attribute

## Rejected alternatives
- **Client-side marked.js**: Adds JS dependency + DOMPurify, duplicates sanitization
- **Prompt-only HTML**: Fragile, depends on Claude consistently outputting HTML
