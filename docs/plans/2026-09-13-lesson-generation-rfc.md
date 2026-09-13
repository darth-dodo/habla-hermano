# RFC: Runtime Lesson Generation

**Date**: 2026-09-13
**Status**: Draft — request for comment
**Goal**: Raise the structured-content ceiling from 105 minutes per language to an arbitrary amount, and close the Hinglish content gap, by generating lessons at runtime behind an adversarial quality gate.

---

## Summary

Habla Hermano ships **105 minutes of structured content per language**. A motivated learner exhausts the entire A0→B1 curriculum in under two evenings, after which the app falls back to freeform chat and SM-2 review of a fixed vocabulary set. Hinglish, added in f951d8f, has **zero** lessons at all.

This RFC proposes generating lessons at runtime with Claude Haiku 4.5, constrained by the existing Pydantic schema and gated by four adversarial critics calibrated against the hand-written corpus.

It also documents a **latent data-loss bug** (§3) that must be fixed before any Hinglish content — generated or hand-written — can be added.

---

## 1. Problem

### 1.1 The content ceiling

`data/lessons/` holds 20 YAML files, each carrying an `es`, `de`, and `fr` block — 60 language-lessons total, but only **20 per learner**, since a learner studies one language.

| Level | Lessons | Minutes |
|-------|---------|---------|
| A0 | 5 | 15 |
| A1 | 5 | 20 |
| A2 | 5 | 30 |
| B1 | 5 | 40 |
| **Total** | **20** | **105 min** |

Measured by summing `estimated_minutes` across `data/lessons/**/*.yaml`.

This is the binding constraint on retention. Every other improvement — onboarding, placement, engagement — routes learners to this cliff faster. It interacts badly with the product's stated philosophy (`docs/product.md:149`: *"No XP, streaks, leaderboards, or guilt"*): having rejected habit-loop mechanics, retention rests entirely on content depth and conversation quality.

### 1.2 Hinglish ships hollow

Zero of the 20 lesson files contain a `hi:` block. Hinglish is selectable in every language picker, and the surrounding system degrades gracefully — `lessons.html:55` shows an empty-state message, `review.py:261` shows "no words due", `learn.py:97` redirects to `/lessons` — but a learner who picks 🇮🇳 gets freeform chat, an empty lessons page, and a zeroed progress dashboard.

This is purely a content gap; prompts (`prompts.py:63-77`), validation (`validation.py:10`), STT (`voice-stt.js:71` sends `multi`, correct for code-mixing), and TTS (fixed in #99) are all complete.

---

## 2. Non-goals

- Replacing the 20 hand-written lessons. They stay, and become the calibration corpus (§5.2).
- Onboarding / CEFR placement. A real gap (learners self-select level cold in `chat.py`), but orthogonal and separately scoped.
- Fixing the silent persistence failures at `chat_stream.py:293,345,353,375`. Real, worth doing, out of scope here.

---

## 3. Blocker: adding a `hi:` block currently deletes a lesson file

**This must be fixed first, and is independently worth merging.**

`models.py:105-112` hardcodes the supported-language set:

```python
supported = {"es", "de", "fr"}
if v not in supported:
    raise ValueError(f"Language must be one of {supported}, got {v}")
```

This has already drifted from `validation.py:10` (`VALID_LANGUAGES`), which includes `"hi"` — two copies of the same truth, exactly the duplication the canonical-module layering was meant to prevent.

The failure mode is worse than a rejected block. `service.py:79-95` catches `ValidationError` at **file** granularity, but the validation unit is a **language block**. So one bad block discards the whole file — including its working Spanish, German, and French lessons. Verified empirically:

```
lessons loaded from file WITH hi block: 0
languages: NONE — entire file dropped
```

The app boots normally; the lessons just vanish with a warning to the log.

**Fix**: point the validator at `VALID_LANGUAGES`, and narrow the `try/except` into the per-language loop in `_parse_multi_language_file` so a bad block skips only that language.

---

## 4. Constraints discovered

| Constraint | Evidence | Consequence |
|---|---|---|
| `max_tokens` caps at 1024 on every profile | `llm.py:23-32` | A B1 lesson block measures ~1376 tokens — single-shot generation truncates. Forces staged generation. |
| Structured outputs supported on Haiku 4.5 | Claude API | Generate directly into existing Pydantic models; schema errors become impossible by construction. |
| Prompt-cache minimum prefix: 4096 tokens on Haiku 4.5 | Claude API | The schema + exemplar prefix must clear 4096 or caching silently no-ops (Sonnet 4.6's floor is 2048). |
| Haiku 4.5 pricing: $1 / $5 per MTok | Claude API | ~$0.01 per lesson. Cost is not a design constraint; latency and quality are. |

---

## 5. Proposed design

### 5.1 Pipeline

Generation hangs off the point where the app currently gives up — `paths.get_next_path_lesson()` returning `None`.

```
learner approaches end of curriculum
        ↓
LessonGenerator  (src/services/lesson_generation.py)
  stage 1  topic selection ← learner's weak vocabulary (SM-2 data)
  stage 2  instruction + vocabulary   ─┐
  stage 3  examples + tips             ├─ structured output → existing Pydantic models
  stage 4  exercises                  ─┘
        ↓
QualityGate — 4 critics in parallel, each prompted to REFUTE
        ↓  ≥2 refute → regenerate (max 3 attempts)
GeneratedLessonRepository → Supabase `generated_lessons` (RLS, per-user)
        ↓
served through the existing LessonService interface
```

Staging is forced by the 1024-token cap, but earns its keep twice over: each stage gets its own validation point, and each stage's output is small enough to verify cheaply.

Because the output is the existing `Lesson` type, generated lessons flow through `LessonService`, the progress dashboard, and SM-2 vocabulary seeding **with no downstream changes**.

### 5.2 Quality gate

Four critics, each with a distinct lens. Redundant critics share blind spots; diverse ones do not.

| Critic | Refutes on |
|---|---|
| Grammar | agreement, conjugation, case, word order |
| Naturalness | would a native say this, or is it textbook-ese? |
| CEFR fit | is this really A2, or smuggled-in B1 grammar? |
| Answerability | is every exercise solvable from material taught *above it* in the same lesson? |

**Why this matters more here than in most LLM applications:** a learner cannot detect a wrong translation or a broken gender agreement — that is precisely why they are learning. A bad lesson is memorized, and SM-2 will then faithfully drill the error every few days. Unlike a code assistant, there is no compiler to catch it.

**Calibration against the hand-written corpus.** The 20 existing lessons are human-authored, shipped, and trusted — a golden set in exactly the schema the generator targets:

1. Run all 60 existing language blocks through the critics. **They should pass.** If critics reject hand-written content, they are miscalibrated and would reject good generated content too. This measures the false-positive rate.
2. Mutate known-good lessons — swap a translation, break an agreement, make an exercise reference untaught vocabulary — and confirm critics catch them. This measures the false-negative rate.

This yields measured error rates *before* any learner sees generated content. Without it, "we have critics" is an assertion, not a control.

### 5.3 Latency, not cost, is the runtime problem

Four stages plus four critics is roughly 10–20s. At ~$0.01/lesson the money is irrelevant; making a learner watch a spinner is not.

**Generate ahead.** When a learner *starts* their second-to-last available lesson, kick off background generation for the next. By the time they finish, it is cached. Runtime generation becomes invisible.

**Failure is always soft.** Generation error, or three rejected attempts → fall back to today's behavior (review mode / "keep exploring"). A learner never sees a critic-rejected lesson, and never sees an error.

---

## 6. Decisions and rationale

| Decision | Alternative considered | Why |
|---|---|---|
| Runtime generation, cached per user | Offline authoring tool committing YAML to the repo | Personalization (topics targeting the learner's actual weak vocabulary) and no human bottleneck. Trade-off accepted: content is not reviewable, diffable, or reproducible. |
| Adversarial critics, ≥2-of-4 to reject | Single reviewer pass | A single reviewer shares the generator's blind spots and tends to rubber-stamp plausible-looking errors. |
| Haiku 4.5 throughout | Sonnet 4.6 for critics (~$0.05/lesson) | Consistency with the app default (`config.py:65`). The pilot measures whether Haiku critics can separate good from corrupted content; if calibration is poor, revisit with evidence rather than assumption. |
| Pilot before building | Build the full pipeline | Cheapest path to the only question that matters: is generated quality acceptable? |

---

## 7. Pilot (immediate next step)

**Question:** Can Haiku 4.5 generate lesson content that passes critics calibrated against the hand-written corpus?

**Target: Spanish A2** — deliberately *not* Hinglish. Spanish has a golden set (5 human-authored A2 lessons), so generated output is measurable against a known-good baseline. Hinglish is the real product gap but has nothing to calibrate against, so it cannot answer the question. It follows once the method is proven.

Throwaway script, no changes to `src/`:

1. **Calibrate** — 60 existing blocks through the critics. Measure false positives. *If this fails, stop here.*
2. **Mutation check** — corrupt known-good lessons, confirm critics catch them. Measure false negatives.
3. **Generate** ~5 Spanish A2 lessons via staged structured output.
4. **Judge** — run through calibrated critics; a human reads 2–3. Model verdicts are evidence; the human read is ground truth.

**Cost:** ~$1–2. **Output:** false-positive/false-negative rates, sample lessons, and a go/no-go.

---

## 8. Risks and open questions

- **Hinglish has no golden set.** "Correct Hinglish" is genuinely fuzzier than correct Spanish — code-mixing ratio is a style choice, not a rule. Critics need Hinglish-specific prompting and separate calibration. Parity with Spanish should not be assumed.
- **Critic calibration may fail on Haiku.** The pilot is designed to surface this as a number rather than a debate.
- **Per-user caching duplicates work.** A generated Spanish A2 lesson on "ordering coffee" is equally good for any learner. A shared pool keyed by `(language, level, topic)` would reuse it, trading personalization for efficiency. Deferred — at $0.01/lesson, not yet worth the complexity.
- **Relationship to ADR-004 and ADR-007.** ADR-004 (YAML lesson content) and ADR-007 (static learning paths) both assume a fixed, hand-authored curriculum. This RFC does not replace them — hand-written lessons remain the spine — but it does introduce a second content source. If adopted, both ADRs need an amendment noting the hybrid model.
- **Generated content is not reviewable or diffable.** Accepted consequence of the runtime choice. A human review queue would restore it at the cost of reintroducing the bottleneck.

---

## 9. Requested feedback

1. Is the adversarial-critic gate sufficient protection for teaching content, or is a human review queue warranted before learners see generated lessons?
2. Should the §3 blocker fix ship independently and immediately, ahead of this RFC's outcome? (Recommendation: yes.)
3. Is per-user caching the right default, or should generated lessons enter a shared pool from the start?
