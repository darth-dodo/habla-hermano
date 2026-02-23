# Phase 15: SSE Streaming for Chat Responses

> Real-time token streaming via Server-Sent Events, replacing the blocking ainvoke() pattern with progressive response delivery

---

## Overview

Phase 15 replaces the blocking `graph.ainvoke()` call in the chat endpoint with Server-Sent Events (SSE) streaming using `graph.astream()`. Previously, the chat endpoint waited 5-15 seconds for the full LangGraph pipeline to complete before returning any response. During this time, users saw only a loading indicator with no feedback about what was happening. This phase introduces real-time token-by-token streaming — the same interaction pattern used by ChatGPT, Claude, and other modern AI chat interfaces.

**Business Value**: Perceived latency drops from 5-15 seconds to near-instant. Users see the first token within ~200ms of submitting their message, transforming the experience from "waiting for a wall of text" to "watching the tutor think and respond in real time."

---

## Design Decisions

### SSE via fetch() + ReadableStream

The core decision is to use the browser's native `fetch()` API with `ReadableStream` to consume a `text/event-stream` response from a new streaming endpoint. This was chosen over three alternatives:

#### Rejected: HTMX SSE Extension

HTMX has a built-in SSE extension (`hx-ext="sse"`), but it **replaces** the target element's content on each event rather than appending tokens. For chat streaming, we need to append each token to a growing response bubble. The HTMX SSE model is designed for discrete updates (e.g., notifications, status changes), not for progressive text accumulation. Workarounds involving `innerHTML +=` on each event would fight against HTMX's declarative model and introduce brittleness.

#### Rejected: WebSockets

WebSockets provide full-duplex communication, but chat streaming is fundamentally unidirectional — the server streams tokens to the client. WebSockets add connection management complexity (heartbeats, reconnection, multiplexing), require a different server infrastructure path (upgrade handshake, persistent connections), and are overkill for a request-response pattern where the client sends a message and receives a streamed reply.

#### Rejected: Browser EventSource API

The native `EventSource` API is purpose-built for SSE, but it **only supports GET requests**. Chat messages must be sent via POST with form data (message text, language, level, conversation context). There is no clean way to encode this as query parameters, especially as conversation history grows. Using `EventSource` would require either a two-step flow (POST the message first, then GET the stream) or encoding large payloads in URLs, both of which add unnecessary complexity.

### LangGraph astream() with Dual Stream Modes

The key technical insight enabling this feature: LangGraph's `astream(stream_mode=["messages", "updates"])` intercepts LLM callbacks automatically, even when graph nodes use `ainvoke()` internally. This means **no changes were needed to the LLM configuration, node code, or prompt setup**. The existing `respond_node` calls `llm.ainvoke(messages)` as before — LangGraph's streaming infrastructure hooks into the underlying LLM client to emit tokens as they arrive.

Two stream modes are used simultaneously:

- **`messages`**: Emits individual LLM tokens as `AIMessageChunk` objects during node execution. These are the tokens streamed to the client in real time.
- **`updates`**: Emits the final state update when each node completes. These are used to detect when post-LLM nodes (scaffold, grammar, pronunciation) finish and to extract their results from the graph state.

### SSE Event Protocol

The server emits a structured sequence of SSE event types:

```
event: token
data: {"content": "Hola"}

event: token
data: {"content": " amigo"}

event: token
data: {"content": "!"}

event: response_complete
data: {"message_id": "msg_123"}

event: scaffolding
data: {"html": "<div class=\"scaffold\">...</div>"}

event: grammar
data: {"html": "<div class=\"grammar-feedback\">...</div>"}

event: pronunciation
data: {"html": "<div class=\"pronunciation-tips\">...</div>"}

event: done
data: {}
```

**Protocol design rationale**:

- **`token`** events carry individual text chunks for progressive display
- **`response_complete`** signals the LLM has finished generating, allowing the client to finalize the response bubble
- **`scaffolding`**, **`grammar`**, and **`pronunciation`** events carry server-rendered HTML fragments produced by the existing Jinja2 partials. This reuses the same templates from the non-streaming path, avoiding template duplication.
- **`done`** is the terminal event, signaling the client to clean up (re-enable input, hide loading state)
- Events after `response_complete` are optional — they only fire if the corresponding graph nodes produce output (e.g., scaffolding only appears for A0-A1 levels)

### Server-Rendered HTML in SSE Events

Post-response enrichments (scaffolding, grammar feedback, pronunciation tips) are sent as pre-rendered HTML fragments rather than raw JSON data. This reuses the existing Jinja2 partials (`scaffold.html`, `grammar_feedback.html`, `pronunciation_tips.html`) and keeps the client-side JavaScript simple — it just inserts HTML into the DOM. This follows the HTMX philosophy of server-rendered HTML, even though the streaming transport itself is JavaScript-driven.

### Two Chat Endpoints

The original `POST /chat` endpoint is preserved alongside the new `POST /chat/stream` endpoint:

- **`POST /chat`**: Original blocking endpoint using `graph.ainvoke()`. Returns a complete HTML fragment via HTMX. Serves as a fallback for clients without JavaScript or for testing.
- **`POST /chat/stream`**: New streaming endpoint using `graph.astream()`. Returns `text/event-stream` consumed by `stream.js`.

Both endpoints accept the same form data and produce the same final result. The streaming endpoint yields tokens progressively, while the original returns everything at once.

---

## Client Architecture

### stream.js

A new JavaScript module handles the client-side streaming logic:

```javascript
async function streamChat(formData) {
    const response = await fetch("/chat/stream", {
        method: "POST",
        body: formData,
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    // Create empty response bubble in chat container
    const bubble = createResponseBubble();

    // Read SSE stream
    let buffer = "";
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // Parse SSE events from buffer
        // Dispatch to handlers: appendToken, insertHTML, finalize
    }
}
```

**Responsibilities**:
- Intercept the chat form submission (prevent default HTMX behavior for the streaming path)
- Create an empty AI response bubble in the chat container
- Open a `fetch()` stream to `/chat/stream`
- Parse the SSE text protocol from the `ReadableStream`
- Append tokens to the response bubble as they arrive
- Insert server-rendered HTML fragments for scaffolding, grammar, and pronunciation
- Re-enable the input form and hide loading state on `done`
- Handle errors and connection failures gracefully

### Form Submission Flow (Streaming)

```
1. User submits message
2. JavaScript shows user message optimistically (existing behavior)
3. JavaScript creates empty AI response bubble with cursor animation
4. fetch() POST to /chat/stream with form data
5. Server begins LangGraph astream()
6. Tokens arrive → append to bubble text
7. response_complete → finalize bubble, stop cursor animation
8. scaffolding/grammar/pronunciation → insert HTML below bubble
9. done → re-enable input, scroll to bottom
```

---

## Server Architecture

### Streaming Endpoint

```python
@router.post("/chat/stream")
async def stream_chat(
    request: Request,
    message: str = Form(...),
    level: str = Form("A1"),
    language: str = Form("es"),
) -> StreamingResponse:
    """Stream chat response as Server-Sent Events."""

    async def event_generator():
        async for stream_mode, chunk in graph.astream(
            input_state,
            stream_mode=["messages", "updates"],
        ):
            if stream_mode == "messages":
                # LLM token — emit as SSE token event
                if hasattr(chunk, "content") and chunk.content:
                    yield f"event: token\ndata: {json.dumps({'content': chunk.content})}\n\n"

            elif stream_mode == "updates":
                # Node completed — check for post-response data
                # Render HTML partials and emit as typed events
                ...

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

**Key headers**:
- `Cache-Control: no-cache` prevents proxies from buffering the stream
- `X-Accel-Buffering: no` disables Nginx buffering if deployed behind a reverse proxy

---

## Dependencies

### External Libraries

No new dependencies. The implementation uses:
- `langgraph` (existing): `astream()` with `stream_mode` parameter
- `fastapi` (existing): `StreamingResponse` for SSE
- Browser `fetch()` + `ReadableStream` APIs (native, no polyfill needed for modern browsers)

### Internal Modules

- `src/api/routes/chat.py`: New `/chat/stream` endpoint alongside existing `/chat`
- `src/static/js/stream.js`: New client-side streaming module
- `src/templates/chat.html`: Updated to load `stream.js` and wire up form submission
- Existing Jinja2 partials: Reused for server-rendering HTML fragments in SSE events

---

## Consequences

### Positive

- **Real-time UX**: First token visible within ~200ms, matching user expectations set by ChatGPT and Claude
- **No LLM changes needed**: `astream(stream_mode=["messages", "updates"])` intercepts callbacks automatically — existing node code using `ainvoke()` works without modification
- **Server-rendered HTML reuse**: Post-response enrichments (scaffolding, grammar, pronunciation) use the same Jinja2 partials as the non-streaming path
- **Graceful degradation**: The original `/chat` endpoint remains functional as a fallback
- **Progressive enhancement**: The streaming experience layers on top of the existing HTMX architecture without replacing it

### Negative

- **Additional JavaScript complexity**: `stream.js` introduces imperative DOM manipulation alongside the declarative HTMX patterns used elsewhere in the app. This is a necessary trade-off — HTMX's SSE extension cannot handle token-by-token appending.
- **Two chat endpoints to maintain**: `/chat` and `/chat/stream` accept the same inputs but have different response mechanisms. Changes to chat logic (e.g., new form fields, authentication) must be applied to both endpoints.
- **SSE parsing complexity**: The client must parse the SSE text protocol manually from the `ReadableStream`, handling buffering, multi-line data fields, and partial reads. This is straightforward but adds code that would be unnecessary with `EventSource` (if it supported POST).

---

## Testing Strategy

### Unit Tests

- `test_chat_stream.py`: Test the streaming endpoint
  - Verify SSE event format (correct `event:` and `data:` lines)
  - Verify token events contain content
  - Verify `response_complete` fires after last token
  - Verify `done` is always the final event
  - Verify post-response events (scaffolding, grammar, pronunciation) contain valid HTML
  - Verify A2-B1 levels skip scaffolding event

### Integration Tests

- Full stream consumption: submit message, collect all events, verify final state matches non-streaming endpoint output
- Error handling: verify stream closes cleanly on graph errors

### Manual Testing

- Verify token-by-token rendering in browser at all CEFR levels
- Verify scaffolding/grammar/pronunciation appear after response completes
- Verify input re-enables after `done` event
- Verify cursor animation during streaming
- Test on mobile (iOS Safari, Android Chrome) for streaming support

---

## Success Criteria

### Functional

- [ ] Tokens stream to the browser as the LLM generates them
- [ ] Post-response enrichments appear after the response completes
- [ ] The existing `/chat` endpoint continues to work unchanged
- [ ] All CEFR levels and languages work with streaming

### Performance

- [ ] First token visible within 500ms of form submission
- [ ] No perceptible delay between consecutive tokens
- [ ] Total response time equal to or better than blocking endpoint

### Technical

- [ ] SSE event protocol followed correctly (token → response_complete → enrichments → done)
- [ ] Stream closes cleanly on completion and on error
- [ ] No memory leaks from unclosed streams or readers
- [ ] All existing tests pass unchanged
