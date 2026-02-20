# ADR-005: SM-2 Algorithm for Spaced Repetition with Dual-Channel Review

**Date**: 2025-01-16
**Status**: Accepted
**Context**: Phase 12 — Spaced Repetition
**Decider(s)**: Project Owner

---

## Summary

Implement the SM-2 (SuperMemo 2) spaced repetition algorithm for vocabulary review scheduling, delivered through two channels: a dedicated review mode and silent chat weaving. Quality scores are AI-inferred from answer correctness rather than user self-rated. This enables optimal vocabulary retention without adding friction to the conversation experience.

---

## Problem Statement

### The Challenge

Habla Hermano captures vocabulary from lessons and conversations, but without a review system, words fade from memory. The app needs:

1. **Optimal review scheduling**: Not too soon (wastes time), not too late (forgotten)
2. **Chat-first integration**: Reviews should fit naturally into the conversation experience
3. **Dedicated practice mode**: Users who want focused review should have that option
4. **Per-word adaptation**: Easy words get longer intervals; hard words get shorter
5. **Minimal user friction**: No manual difficulty ratings or complex UI

### Why This Matters

Research shows spaced repetition is the most effective technique for long-term vocabulary retention. Without it, users learn words in lessons but forget them within weeks. The dual-channel approach ensures retention happens both passively (chat) and actively (review mode).

### Success Criteria

- [x] SM-2 algorithm correctly schedules reviews based on quality scores
- [x] Dedicated review mode with 3 question types
- [x] Silent chat weaving detects and reinforces due words in conversation
- [x] AI infers quality score without user self-rating
- [x] Review statistics visible on progress page

---

## Options Considered

### Option A: SM-2 with Dual Channels (Selected)

**Description**: Standard SM-2 algorithm tracking easiness factor, interval, and repetition count per word. Two delivery channels: dedicated `/review` mode with LangGraph subgraphs, and silent chat weaving through respond/analyze nodes.

**Implementation**:
- **SM-2 formula**: EF = max(1.3, EF + 0.1 - (5 - q) x (0.08 + (5 - q) x 0.02))
- **Intervals**: 1 day, then 6 days, then previous_interval x EF
- **Reset**: Quality < 3 resets interval to 1 day
- **Quality inference**: AI evaluates answer quality (0-5) without user input

**Pros**:

- Research-backed optimal retention scheduling
- Invisible reinforcement via chat (no extra effort from user)
- Per-word adaptation (easy words reviewed less, hard words more)
- Dedicated mode for focused practice when desired

**Cons**:

- Database schema changes (5 new columns)
- Two delivery channels add complexity
- Quality inference adds LLM call in review mode

**Estimated Effort**: 4-5 days

---

### Option B: Leitner Box System

**Description**: Fixed interval boxes where words advance on correct answer, retreat on incorrect.

**Pros**:

- Simple to implement (5 fixed intervals)
- Easy to visualize (boxes)

**Cons**:

- Rigid intervals don't adapt to word difficulty
- Less research backing for language learning specifically
- No per-word easiness adaptation

**Estimated Effort**: 2-3 days

---

### Option C: Simple Fixed Intervals

**Description**: Review all due words every N days with no adaptation.

**Pros**:

- Trivially simple implementation

**Cons**:

- Wastes time on easy words
- Insufficient repetition for hard words
- No research backing

**Estimated Effort**: 1 day

---

## Decision

### Chosen Option

**Selected**: Option A: SM-2 with Dual Channels

**Rationale**: SM-2 is the most researched and validated algorithm for spaced repetition. The dual-channel approach aligns with the chat-first architecture — users get passive reinforcement in every conversation, plus focused practice when they want it.

**Key Factors**:

- SM-2 has decades of research validation
- Chat weaving makes review invisible and frictionless
- AI-inferred quality scores eliminate manual rating UI
- Per-word adaptation optimizes study time

**Trade-offs Accepted**:

- Schema changes for SM-2 state (5 columns — acceptable)
- Dual channel complexity (acceptable given UX benefits)

---

## Consequences

### SM-2 Algorithm

**Per-Word State** (5 new columns on vocabulary table):
- `easiness_factor` (float, default 2.5): How easy this word is for the user
- `interval_days` (int, default 0): Days until next review
- `repetition_count` (int, default 0): Successful consecutive reviews
- `next_review_at` (timestamp, nullable): When this word is next due
- `last_reviewed_at` (timestamp, nullable): Last review timestamp

**Quality Score Scale** (AI-inferred, not user-rated):
- 5: Perfect, immediate correct answer
- 4: Correct with minor issue (typo, missing accent)
- 3: Correct after hint shown
- 2: Incorrect, but recognizes correct answer
- 1: Incorrect, seems unfamiliar
- 0: Complete blank or skip

**Scheduling Logic**:
- First review: 1 day
- Second review: 6 days
- Subsequent: previous_interval x easiness_factor
- Quality < 3: Reset interval to 1 day (relearning)

### Dual-Channel Architecture

**Channel 1: Dedicated Review Mode**
- User navigates to `/chat?mode=review`
- Selects session size: Quick (5), Regular (10), All
- Three question types:
  - **Translate**: "How do you say 'thank you'?" — user responds in target language
  - **Fill blank**: "At a restaurant, you'd say '_____ la cuenta'" — fill in blank
  - **Recognize**: "What does 'cansado' mean?" — translate from target language
- LangGraph review subgraphs: `generate_question_subgraph`, `evaluate_answer_subgraph`
- AI evaluates answer, infers quality score, updates SM-2 state

**Channel 2: Silent Chat Weaving**
1. `respond_node`: `_get_topical_review_words()` queries due words matching topic
2. Hermano naturally uses due words in response (or skips if they don't fit)
3. User responds in conversation
4. `analyze_node`: `_check_review_word_usage()` detects if user used due words
5. Correct usage updates SM-2 with quality 4-5
6. **Constraint**: Conversation flow always wins — never force awkward word insertions

---

## Key Files

- `src/services/review.py` — ReviewService with SM-2 scheduling, due word queries
- `src/agent/review_graph.py` — LangGraph subgraphs (generate question, evaluate answer)
- `src/agent/review_state.py` — ReviewState TypedDict
- `src/agent/nodes/review.py` — Review nodes (question generation, answer evaluation)
- `src/agent/nodes/respond.py` — `_get_topical_review_words()` for chat weaving
- `src/agent/nodes/analyze.py` — `_check_review_word_usage()` for silent tracking
- `src/api/routes/review.py` — Review API endpoints

---

## Related Decisions

**Depends On**:
- ADR-001 (Supabase stores SM-2 state in vocabulary table)
- ADR-002 (LangGraph subgraphs for review workflow)

**Related To**:
- ADR-006 (ReviewService follows repository + service pattern)
- ADR-007 (AdaptiveService uses review_due_count for recommendations)

---

## Metadata

**ADR Number**: 005
**Created**: 2025-01-16
**Last Updated**: 2025-01-18
**Version**: 1.0
**Tags**: spaced-repetition, sm2, vocabulary, review, chat-weaving, algorithm

---

**Status**: ACCEPTED
