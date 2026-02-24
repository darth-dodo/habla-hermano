# ADR-010: Deepgram for Voice STT and TTS

**Date**: 2026-02-23
**Status**: Proposed
**Context**: Phase 17 (Voice Conversation)
**Decider(s)**: Project Owner

---

## Summary

Adopt Deepgram as the unified provider for Speech-to-Text (Nova-3) and Text-to-Speech (Aura-2) in Habla Hermano. Voice adds the missing sensory channel to conversational language learning — users speak to Hermano and hear him reply — while the existing text chat, SSE streaming, and LangGraph pipeline remain unchanged. Deepgram was chosen over alternatives (Google Cloud Speech, OpenAI Whisper, ElevenLabs, Azure) primarily for its native multilingual codeswitching support, which handles the mixed-language speech that language learners naturally produce.

---

## Problem Statement

### The Challenge

Habla Hermano teaches languages through conversation, but all interaction is currently text-based. This creates three problems:

1. **No listening practice**: Pronunciation tips (Phase 11) explain *how* to say something in text, but learners can't hear native-quality pronunciation. Reading "/OH-lah/" is no substitute for hearing "Hola" spoken by a native voice.

2. **No speaking practice**: Learners never practice producing sounds themselves. Text-based conversation develops reading and writing skills but not the speaking confidence that is the app's core promise ("take someone from zero to conversational").

3. **Mobile input friction**: Typing in a foreign language on a phone keyboard — especially with special characters like ñ, ü, é, ç — is slow and error-prone. Voice input removes this friction entirely.

### Why This Matters

The product vision states: "Conversation confidence comes from conversation practice." But text-only conversation is half a conversation. Adding voice transforms a chat interface into something closer to actually talking with Hermano — which is the experience the product promises.

### Success Criteria

- [ ] Users can speak into a microphone and see their words transcribed in the chat input
- [ ] Users can tap a speaker icon on Hermano's responses to hear them spoken aloud
- [ ] STT handles mixed-language speech (e.g., English + Spanish in one utterance)
- [ ] TTS speaks with natural pronunciation in all three target languages (es, de, fr)
- [ ] Voice is optional — text chat continues working unchanged
- [ ] Voice features degrade gracefully when the API key is not configured
- [ ] Cost per voice session stays under $0.15

---

## Context

### Current State

**Before this decision**, all user-Hermano interaction is text-based:

```
User types message → POST /chat/stream → SSE tokens → Text response
```

Phase 15 added real-time token streaming via SSE, which improved perceived latency. But the fundamental interaction is still keyboard → screen. There is no audio channel in either direction.

**Technical constraints**:

- Must integrate with the existing FastAPI + HTMX + LangGraph stack
- Must not modify the LangGraph graph, nodes, prompts, or state schema
- Must work on mobile (iOS Safari, Android Chrome) without native app distribution
- Must support all three target languages: Spanish, German, French
- Must handle mixed-language speech (learners mix native and target language)
- Must work behind Render's deployment infrastructure (HTTPS, reverse proxy)
- API key cost must be manageable for a learning project

### Requirements

**Functional Requirements**:

- Real-time speech-to-text with live interim transcripts
- Text-to-speech for Hermano's responses in all three languages
- STT must handle codeswitching (mixed English + target language)
- TTS must provide natural-sounding voices with correct pronunciation
- Voice features must be optional (text-only mode always available)

**Non-Functional Requirements**:

- **Latency**: First interim transcript within 500ms; TTS playback within 1s
- **Accuracy**: STT word error rate below 10% for target languages
- **Browser support**: Chrome, Firefox, Safari (including mobile)
- **Security**: API key never exposed to the browser
- **Cost**: Under $0.15 per 10-minute voice session

---

## Options Considered

### Option A: Deepgram Nova-3 STT + Aura-2 TTS (Chosen)

**Description**:
Unified voice platform using Deepgram's Nova-3 model for real-time speech-to-text (via WebSocket streaming) and Aura-2 model for text-to-speech (via REST API with MP3 streaming). All API calls proxied through the FastAPI server.

**Implementation**:
- WebSocket endpoint `/ws/transcribe` proxies browser audio to Deepgram STT
- REST endpoint `POST /api/speak` proxies text to Deepgram TTS, streams MP3 back
- Nova-3 with `language=multi` handles codeswitching natively
- Aura-2 voices per language: Celeste (es), Elara (de), Agathe (fr)
- New `deepgram-sdk` dependency (~lightweight, async-native)
- Client-side `voice.js` module for mic capture and audio playback

**Pros**:

- **Native codeswitching**: Nova-3 is the only STT model that handles mixed-language speech as a first-class feature. A student saying "I want to go to the mercado" gets transcribed correctly without pre-selecting a single language.
- **Unified provider**: One SDK, one API key, one billing relationship for both STT and TTS. Halves integration surface area vs. mixing providers.
- **Real-time streaming STT**: WebSocket-based with ~250ms transcript latency and interim results for live display.
- **Natural TTS voices**: Aura-2 voices sound conversational, not robotic. 17 Spanish voices with regional accents (Mexican, Colombian, Peninsular), 7 German, 2 French.
- **Async-native SDK**: `AsyncDeepgramClient` integrates cleanly with FastAPI's async architecture.
- **Simple audio format handling**: STT auto-detects container formats from `MediaRecorder` (webm/opus, mp4). TTS outputs MP3 via REST (universal browser support).
- **Cost-effective**: ~$0.11 per 10-min session. $200 free credit covers ~1,800 sessions.
- **Billed by the second**: No rounding to minutes.

**Cons**:

- **External dependency**: Adds a third-party API dependency (Deepgram) to a stack that currently only depends on Anthropic and Supabase.
- **Limited French TTS**: Only 2 French voices (Agathe, Hector) vs. 17 Spanish. Acceptable for now but constraining if voice selection becomes a feature.
- **No SSML or speed control**: Aura-2 doesn't support SSML, explicit speed parameters, or pitch adjustment. Can't slow down speech for beginners via API — would need client-side `playbackRate`.
- **Service availability risk**: If Deepgram has an outage, voice features are unavailable (text chat unaffected).
- **Python SDK maturity**: The `deepgram-sdk` v3.x API has gone through significant changes. Pinning to a specific version is important.

**Risks**:

- **Deepgram SDK breaking changes**: Mitigate by pinning version, wrapping SDK calls in a thin adapter layer
- **Service outage**: Mitigate with graceful degradation (voice buttons hidden, text chat unaffected)
- **Cost at scale**: Monitor usage; at 10,000 sessions/month, cost is ~$1,100/month

**Estimated Effort**: 3-5 days (server endpoints + client JS + testing)

---

### Option B: OpenAI Whisper (Self-Hosted) + Deepgram Aura-2 TTS

**Description**:
Self-host OpenAI's Whisper model for STT (free, no per-minute cost), use Deepgram only for TTS. Whisper runs on the server via `faster-whisper` or `whisper.cpp`.

**Pros**:

- Zero STT cost (self-hosted, open-source)
- Whisper has the highest batch transcription accuracy across languages
- No external STT dependency — runs entirely on your infrastructure

**Cons**:

- **No real-time streaming**: Whisper is batch-only. Users must record their full utterance, upload the audio file, then wait for transcription. No live interim transcripts. This fundamentally changes the UX from "speak and see words appear" to "record, wait, see result."
- **Requires GPU infrastructure**: Whisper large-v3 needs a GPU for acceptable latency. Render's free/starter tiers don't include GPU instances. A GPU instance costs $50-200/month — far exceeding Deepgram's pay-per-use pricing for this usage volume.
- **No codeswitching**: Whisper requires pre-selecting a single language. Mixed-language speech (the norm for language learners) produces poor results.
- **Two providers**: Still need Deepgram for TTS, so you have mixed infrastructure (self-hosted + API) to maintain.
- **DevOps overhead**: Model deployment, version management, GPU monitoring, scaling.

**Why rejected**: The batch-only limitation eliminates the real-time transcription UX. The GPU infrastructure cost exceeds Deepgram's API cost at this scale. The lack of codeswitching is a deal-breaker for language learning.

---

### Option C: Google Cloud Speech-to-Text + Google Cloud TTS

**Description**:
Use Google Cloud's Speech-to-Text v2 API for STT and Cloud TTS (WaveNet/Neural2 voices) for TTS. Both are mature, production-grade services.

**Pros**:

- Mature, battle-tested services with enterprise SLAs
- Streaming STT available via gRPC
- Extensive language support (125+ languages for STT)
- WaveNet voices are high quality for TTS
- Strong documentation and community support

**Cons**:

- **No native codeswitching**: Google STT requires pre-selecting a single language per recognition request. There is a multi-language recognition feature, but it selects the dominant language — it doesn't handle mid-sentence switching. A student mixing English and Spanish gets either an English or Spanish transcript, not both.
- **Complex GCP setup**: Requires a GCP project, service account credentials, IAM roles, and billing configuration. Significantly more operational overhead than a single API key.
- **Separate SDKs for STT and TTS**: `google-cloud-speech` and `google-cloud-texttospeech` are separate packages with different APIs, authentication patterns, and error models.
- **gRPC for streaming**: Google's streaming STT uses gRPC, which adds `grpcio` as a heavy dependency (~20MB compiled) and doesn't integrate as naturally with FastAPI's async WebSocket model as a simple WebSocket client.
- **TTS voices**: WaveNet voices are good but noticeably less natural than Deepgram Aura-2 for conversational speech. More "announcer" than "friend."
- **Higher cost**: Google STT is ~$0.016/min (enhanced) vs. Deepgram's ~$0.009/min. Google TTS is $0.016/1M characters (WaveNet) — cheaper per character but the base pricing model is more complex with tiered pricing.

**Why rejected**: The codeswitching limitation is critical. Language learners routinely mix their native language with the target language — this is normal and expected, especially at A0-A1 levels. An STT service that forces a single language produces unusable transcripts for the primary use case. The GCP operational overhead and gRPC dependency add complexity without proportional benefit.

---

### Option D: Deepgram STT + ElevenLabs TTS

**Description**:
Use Deepgram Nova-3 for STT (same as Option A) but ElevenLabs for TTS, leveraging ElevenLabs' arguably best-in-class voice synthesis quality.

**Pros**:

- ElevenLabs voices are widely considered the most natural-sounding
- Voice cloning and customization options
- Deepgram STT provides the codeswitching needed for language learning

**Cons**:

- **Two providers**: Two SDKs, two API keys, two billing accounts, two sets of docs, two potential points of failure. This doubles the integration and operational surface area.
- **Cost**: ElevenLabs TTS costs $0.15-0.30/1K characters (Starter-Pro plans) vs. Deepgram's $0.030/1K characters — 5-10x more expensive for TTS.
- **Limited multilingual voices**: ElevenLabs' strongest voices are English. Multilingual voices exist but the Spanish/German/French selection is smaller and less accent-diverse than Deepgram's dedicated per-language voices.
- **Rate limits**: ElevenLabs Starter plan limits concurrent requests and monthly character quotas.

**Why rejected**: The voice quality difference between ElevenLabs and Deepgram Aura-2 doesn't justify 5-10x TTS cost and doubled integration complexity. For a language tutoring context (not audiobook narration or voice acting), Aura-2's quality is more than sufficient. The unified Deepgram experience (one SDK, one key) is a significant simplicity win.

---

### Option E: Web Speech API (Browser-Native)

**Description**:
Use the browser's built-in `SpeechRecognition` API for STT and `SpeechSynthesis` API for TTS. Zero external dependencies, zero cost.

**Pros**:

- Zero cost (runs entirely in the browser)
- No server-side changes needed
- No API keys or external dependencies
- Built into all modern browsers

**Cons**:

- **Inconsistent quality**: STT accuracy varies wildly across browsers and OSes. Chrome uses Google's cloud service under the hood (decent), but Firefox and Safari use local engines (poor accuracy, especially for non-English).
- **No codeswitching**: `SpeechRecognition` requires a single `lang` property. Mixed-language speech is not supported.
- **Robotic TTS voices**: `SpeechSynthesis` voices are system-dependent and generally sound robotic. No control over which voices are available — it depends on the user's OS and installed language packs.
- **No streaming for STT**: Results arrive after silence detection, not as progressive interim transcripts.
- **Safari limitations**: Safari requires explicit user activation for both APIs and has inconsistent behavior.
- **No server-side control**: Can't log, monitor, rate-limit, or control the voice experience.

**Why rejected**: Quality is unacceptable for a language learning application. STT accuracy for non-English speech is poor on non-Chrome browsers. TTS voices sound robotic compared to modern neural TTS. The lack of codeswitching and inconsistent browser behavior make this unsuitable.

---

## Comparison Matrix

| Criteria | Weight | A: Deepgram | B: Whisper+DG | C: Google Cloud | D: DG+ElevenLabs | E: Web Speech |
|----------|--------|-------------|---------------|-----------------|-------------------|---------------|
| **Codeswitching** | High | 5 | 1 | 2 | 5 | 1 |
| **Real-time STT** | High | 5 | 1 | 4 | 5 | 3 |
| **TTS Voice Quality** | High | 4 | 4 | 3 | 5 | 1 |
| **Multilingual TTS Voices** | High | 4 | 4 | 4 | 3 | 2 |
| **Integration Simplicity** | High | 5 | 2 | 2 | 3 | 5 |
| **Cost at Scale** | Medium | 4 | 3 | 3 | 2 | 5 |
| **Operational Overhead** | Medium | 5 | 1 | 2 | 3 | 5 |
| **Browser Compatibility** | Medium | 5 | 5 | 5 | 5 | 3 |
| **Vendor Lock-in** | Low | 3 | 4 | 3 | 3 | 5 |
| **Total Score** | - | **40** | 25 | 28 | 34 | 30 |

**Scoring**: 1 = Poor, 2 = Below Average, 3 = Acceptable, 4 = Good, 5 = Excellent

---

## Decision

### Chosen Option

**Selected**: Option A: Deepgram Nova-3 STT + Aura-2 TTS

**Rationale**:
Deepgram is the only provider that offers native multilingual codeswitching in real-time streaming STT — the single most critical requirement for a language learning application. Learners mix languages naturally, and the STT service must handle this without requiring language pre-selection. The unified provider approach (one SDK for both STT and TTS) halves integration complexity compared to mixing providers. Aura-2 TTS provides natural-sounding voices in all three target languages with regional accent selection for Spanish. The cost model ($0.11/session) is sustainable for a learning project with Deepgram's $200 free credit covering the development and early usage phase.

**Key Factors**:

- Multilingual codeswitching is non-negotiable for language learning STT
- Unified STT + TTS provider eliminates dual-SDK complexity
- Async-native Python SDK integrates cleanly with FastAPI
- ~$0.11 per 10-minute session is cost-sustainable
- $200 free credit covers development and early users (~1,800 sessions)
- Server-side proxy pattern keeps API key secure and enables rate limiting

**Trade-offs Accepted**:

- External API dependency (mitigated by graceful degradation to text-only)
- Limited French TTS voices — 2 voices (acceptable for initial release)
- No SSML/speed control (can use client-side `playbackRate` as workaround for beginners)
- Python SDK is still maturing (mitigated by version pinning and thin adapter)

---

## Architecture

### Integration Pattern

```
Browser                    FastAPI                     Deepgram
───────                    ───────                     ────────

STT Flow:
  getUserMedia() ─audio─►  /ws/transcribe ──audio──►  Nova-3 STT
                 ◄─JSON──  (WebSocket proxy) ◄─JSON──  (WebSocket)

TTS Flow:
  tap 🔊 ──POST─────────►  /api/speak ──POST────────►  Aura-2 TTS
         ◄─audio/mpeg────  (REST proxy) ◄─mp3 stream─  (REST)

Chat Flow (unchanged):
  send message ──POST────►  /chat/stream ──ainvoke───►  Claude (LLM)
              ◄─SSE──────  (existing)   ◄─tokens─────  (existing)
```

### Key Components

| Component | Purpose |
|-----------|---------|
| `src/api/routes/voice.py` | WebSocket STT proxy + REST TTS proxy |
| `src/static/js/voice.js` | Mic capture, WebSocket streaming, audio playback |
| `src/api/dependencies.py` | `get_deepgram_client()` singleton |
| `src/api/config.py` | `DEEPGRAM_API_KEY` setting |

### What Does NOT Change

- `src/agent/` — LangGraph graph, nodes, prompts, state schema
- `src/api/routes/chat.py` — Chat endpoints (`/chat`, `/chat/stream`)
- `src/api/streaming.py` — SSE streaming logic
- `src/services/` — Progress, review, paths, adaptive services
- `src/db/` — No new tables or schema changes

Voice is a UI-layer feature with a server-side API proxy. It does not touch the AI pipeline.

---

## Consequences

### Positive Outcomes

**Immediate Benefits**:

- Learners can practice speaking and listening — completing the conversation loop
- Mobile input friction eliminated (no more typing ñ, ü, é on phone keyboards)
- Pronunciation tips (Phase 11) become actionable — "try saying it" is now possible
- Codeswitching support means STT works naturally for mixed-language learner speech

**Long-term Benefits**:

- Foundation for voice-first features: "repeat after me" exercises, voice-only mode, pronunciation scoring
- TTS voice selection can become a user preference (17 Spanish accents to choose from)
- Review sessions (Phase 12) can use voice for more natural quiz-like interactions

### Negative Outcomes

**Immediate Costs**:

- New external dependency (Deepgram API) adds a potential failure point
- Per-session cost (~$0.11) where text chat is effectively free after LLM costs
- Additional JavaScript complexity (`voice.js`) alongside existing `stream.js`
- `deepgram-sdk` added to Python dependencies

**Technical Debt Created**:

- Minimal; voice module is self-contained in `routes/voice.py` + `voice.js`
- No changes to existing modules means no debt introduced in the core pipeline

### Risks and Mitigation

**Risk 1**: Deepgram service outage

- **Probability**: Low (99.9% SLA for paid plans)
- **Impact**: Voice features unavailable; text chat unaffected
- **Mitigation**: Graceful degradation — mic button and speaker icons hidden when API is unreachable. Zero impact on core text chat functionality.

**Risk 2**: Cost growth with user adoption

- **Probability**: Medium (if the app gains users)
- **Impact**: Monthly API costs increase linearly with voice session count
- **Mitigation**: Server-side rate limiting, optional user-level quotas, Deepgram Growth plan at ~20% discount for higher volumes. At $0.11/session, 1,000 sessions/month = ~$110/month.

**Risk 3**: Deepgram Python SDK breaking changes

- **Probability**: Medium (SDK is actively evolving, v3 had significant API changes)
- **Impact**: Voice endpoints break after dependency update
- **Mitigation**: Pin `deepgram-sdk` to specific version. Wrap SDK calls in a thin adapter in `dependencies.py` so only one file changes if the SDK API shifts.

**Risk 4**: Poor STT accuracy for beginner-level speech

- **Probability**: Low-Medium (beginners speak hesitantly with mispronunciations)
- **Impact**: Frustrating transcription errors for the users who need voice most
- **Mitigation**: Use `language=multi` with high endpointing tolerance (300ms) for A0-A1. Transcription populates input field for review/editing before submission — users can correct errors. As pronunciation improves, accuracy naturally improves.

---

## Related Decisions

**Supersedes**:

- None

**Related To**:

- ADR-002: LangGraph conversation engine — voice does not modify the graph; STT feeds text into the existing pipeline
- ADR-003: HTMX frontend — voice.js follows the same progressive enhancement pattern as stream.js (Phase 15)
- ADR-009: ES module refactor — voice.js will be an ES module following the same pattern

**Depends On**:

- Phase 15 (SSE Streaming) — TTS triggers after the SSE stream completes
- Phase 11 (Pronunciation Tips) — voice makes pronunciation tips actionable

**Informs**:

- Future ADR for pronunciation scoring (if phoneme-level analysis is added)
- Future ADR for voice-only conversation mode
- Future ADR for "repeat after me" lesson exercises

---

## References

### External Resources

- [Deepgram Nova-3 Documentation](https://developers.deepgram.com/docs/models-languages-overview) — Model capabilities and language support
- [Deepgram Multilingual Codeswitching](https://developers.deepgram.com/docs/multilingual-code-switching) — Mixed-language transcription
- [Deepgram Aura-2 TTS](https://developers.deepgram.com/docs/tts-models) — Voice catalog and language support
- [Deepgram Python SDK](https://github.com/deepgram/deepgram-python-sdk) — AsyncDeepgramClient reference
- [Deepgram Pricing](https://deepgram.com/pricing) — STT and TTS per-unit costs
- [MediaRecorder API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder) — Browser audio capture
- [getUserMedia API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) — Microphone access

### Code References

- `docs/design/phase17-voice-conversation.md` — Full implementation design document
- `docs/design/phase15-sse-streaming.md` — SSE streaming architecture (voice TTS triggers post-stream)
- `src/api/streaming.py` — Existing SSE streaming module (unchanged by voice)

---

## Metadata

**ADR Number**: 010
**Created**: 2026-02-23
**Last Updated**: 2026-02-23
**Version**: 1.0

**Authors**: Claude (AI Assistant)
**Reviewers**: Project Owner

**Tags**: deepgram, voice, stt, tts, speech-to-text, text-to-speech, nova-3, aura-2, codeswitching, multilingual

**Project Phase**: Design

---

## Notes

The decisive factor in this ADR is **multilingual codeswitching**. Language learners don't speak in one language — they mix their native language with the target language, especially at beginner levels. An A0 student might say "I want to say... uh... gracias" and the STT must transcribe both the English and Spanish correctly. Deepgram Nova-3 is the only service that handles this as a first-class feature via `language=multi`, making it the clear choice despite alternatives being mature and well-known.

The architecture is deliberately minimal: voice is a UI-layer feature with a server-side proxy. It does not touch the LangGraph pipeline, state schema, prompts, or any service layer. STT produces text that goes into the existing chat input. TTS consumes text from the existing chat output. This clean separation means voice can be added (or removed) without affecting any other system component.

---

**Status**: PROPOSED
**Next Review**: After Phase 17 implementation
