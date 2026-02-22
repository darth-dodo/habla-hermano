# ADR-008: Switch LLM Model from Claude Sonnet 4 to Claude Haiku 4.5

**Date**: 2026-02-22
**Status**: Proposed
**Context**: Cost optimization and latency improvement for production deployment
**Decider(s)**: Project Owner

---

## Summary

Switch the default LLM model from `claude-sonnet-4-20250514` (Claude Sonnet 4) to `claude-haiku-4-5-20251001` (Claude Haiku 4.5) across all agent nodes. Haiku 4.5 offers significantly lower cost and faster response times while providing sufficient capability for the structured language tutoring interactions in Habla Hermano.

---

## Problem Statement

### The Challenge

Habla Hermano currently uses Claude Sonnet 4 as the default model for all LLM interactions — conversational responses, grammar analysis, scaffolding, review word generation, and lesson enhancement. While Sonnet 4 provides excellent quality, it comes at a cost and latency premium that may not be justified for the relatively constrained tasks the agent performs.

Each chat turn invokes the LLM at least twice (respond + analyze nodes), and lesson flows add further calls. As the user base grows, this becomes the dominant operating cost.

### Why This Matters

- **Cost**: Sonnet 4 input/output token pricing is ~10x more expensive than Haiku 4.5
- **Latency**: Sonnet 4 has higher time-to-first-token and overall response time
- **User experience**: Language learners expect near-instant conversational feedback — latency directly impacts engagement
- **Scalability**: Lower per-request cost enables serving more concurrent users within the same budget

### Success Criteria

- [ ] All 6 LLM profiles work correctly with Haiku 4.5
- [ ] Conversation quality remains natural and pedagogically sound
- [ ] Grammar feedback accuracy does not regress
- [ ] Response latency improves (target: <2s p95 for chat responses)
- [ ] All 1820+ existing tests continue to pass
- [ ] Monthly LLM cost projection decreases by ≥60%

---

## Context

### Current State

**Model Configuration** (`src/api/config.py`):
```python
LLM_MODEL: str = "claude-sonnet-4-20250514"
LLM_TEMPERATURE: float = 0.7
```

**LLM Factory** (`src/agent/llm.py`):
The centralized `get_llm()` factory creates `ChatAnthropic` instances using `settings.LLM_MODEL` across 6 profiles:

| Profile | Temperature | Max Tokens | Used By |
|---------|-------------|------------|---------|
| conversational | 0.7 (default) | 1024 | `respond` node — main chat |
| analysis | 0.3 | 1024 | `analyze` node — grammar feedback |
| structured | 0.3 | 512 | `scaffold` node — word banks, hints |
| creative | 0.7 | 512 | Lesson enhancement |
| enhancement | 0.7 | 1024 | Review word integration |
| default | 0.7 | 1024 | Fallback |

**Key Observation**: All profiles use the same underlying model. The factory already supports switching the model via a single config change — no code changes required.

### Task Complexity Analysis

The LLM tasks in Habla Hermano are well-scoped and structured:

1. **Conversational responses**: Follow a detailed system prompt with personality guidelines, level-appropriate vocabulary, and language mixing rules. The prompt provides strong constraints that guide output.
2. **Grammar analysis**: Detect errors in learner input and generate gentle corrections. The output follows a defined schema (error type, correction, explanation).
3. **Scaffolding**: Generate word banks, sentence starters, and hints for A0-A1 learners. Highly templated output.
4. **Lesson enhancement**: Personalize static lesson content with Hermano's voice. Bounded creative task.
5. **Review word integration**: Weave spaced-repetition vocabulary into conversation naturally. Follows explicit rules.

None of these tasks require the advanced reasoning, complex code generation, or multi-step logical analysis where Sonnet significantly outperforms Haiku.

### Requirements

**Functional Requirements**:
- Conversational quality remains natural and engaging
- Grammar detection accuracy is maintained
- Scaffolding output remains pedagogically appropriate
- Level-appropriate language complexity is preserved (A0-B1)

**Non-Functional Requirements**:
- **Latency**: p95 response time ≤2s (improvement from current ~3-5s)
- **Cost**: ≥60% reduction in per-request LLM cost
- **Reliability**: No increase in error rates or malformed responses

---

## Options Considered

### Option A: Switch to Claude Haiku 4.5 (Recommended)

**Description**: Change the default model to `claude-haiku-4-5-20251001` for all profiles.

**Implementation**: Single-line change in `src/api/config.py`:
```python
LLM_MODEL: str = "claude-haiku-4-5-20251001"
```

**Pros**:
- ~10x cheaper per token than Sonnet 4
- Significantly faster response times (lower TTFT and generation speed)
- Haiku 4.5 is the latest Haiku release with improved instruction following
- Zero code changes — the LLM factory and all profiles work as-is
- Easy to revert (single config line or env var override)
- Sufficient capability for constrained, prompt-guided language tutoring tasks

**Cons**:
- Lower ceiling for complex reasoning and nuanced responses
- May produce slightly less creative or varied conversational output
- Grammar analysis may miss subtle errors that Sonnet catches

**Risks**:
- **Quality regression in grammar feedback**: Medium probability; mitigate with manual testing across all 3 languages and 4 levels
- **Less natural conversation flow**: Low-medium probability; the detailed system prompt constrains output heavily

**Estimated Effort**: <1 hour (config change + smoke testing)

---

### Option B: Hybrid Model — Haiku for Chat, Sonnet for Analysis

**Description**: Use Haiku 4.5 for conversational and creative profiles, keep Sonnet 4 for analysis and structured profiles where precision matters more.

**Implementation**: Modify `get_llm()` to accept per-profile model overrides, or introduce a model mapping in the profile configuration.

**Pros**:
- Best quality where it matters most (grammar analysis accuracy)
- Cost savings on the highest-volume path (conversation)
- Preserves Sonnet quality for structured outputs

**Cons**:
- Adds complexity to the LLM factory
- Two model dependencies to manage and monitor
- Partial cost savings (~40-50% vs ~90%)
- Inconsistent "personality" if models respond differently

**Risks**:
- **Personality drift**: Different models may interpret Hermano's voice differently
- **Maintenance burden**: Tracking two model versions, deprecation schedules

**Estimated Effort**: 2-3 hours (factory changes + profile mapping + testing)

---

### Option C: Stay on Claude Sonnet 4

**Description**: Keep the current model and optimize costs through other means (caching, prompt compression, reduced max_tokens).

**Pros**:
- No quality risk whatsoever
- No testing or validation needed

**Cons**:
- Highest operating cost (no improvement)
- Higher latency persists
- Missed opportunity — Haiku 4.5 is well-suited for this use case

**Estimated Effort**: 0 (no change)

---

## Comparison Matrix

| Criteria | Weight | Option A (Haiku) | Option B (Hybrid) | Option C (Stay) |
|----------|--------|------------------|-------------------|-----------------|
| **Cost Reduction** | High | 5 | 3 | 1 |
| **Latency Improvement** | High | 5 | 3 | 1 |
| **Conversation Quality** | High | 4 | 4 | 5 |
| **Grammar Accuracy** | High | 3 | 5 | 5 |
| **Implementation Simplicity** | Medium | 5 | 3 | 5 |
| **Maintainability** | Medium | 5 | 3 | 5 |
| **Reversibility** | Medium | 5 | 4 | 5 |
| **Scalability** | Medium | 5 | 4 | 2 |
| **Total Score** | - | **37** | 29 | 29 |

**Scoring**: 1 = Poor, 2 = Below Average, 3 = Acceptable, 4 = Good, 5 = Excellent

---

## Decision

### Chosen Option

**Selected**: Option A — Switch to Claude Haiku 4.5

**Rationale**:
Habla Hermano's LLM tasks are well-constrained by detailed system prompts, structured output schemas, and level-specific language rules. These guardrails mean the model is operating within a narrow band where Haiku 4.5's capabilities are more than sufficient. The ~10x cost reduction and improved latency directly benefit user experience and operational sustainability.

**Key Factors**:
- Single-line config change with zero code modifications
- LLM factory already abstracts model selection via `settings.LLM_MODEL`
- `LLM_MODEL` is overridable via environment variable — can use Sonnet in specific deployments without code changes
- Conversational prompts are heavily constrained (personality, level, language rules)
- Grammar analysis follows defined schemas that guide the model's output

**Trade-offs Accepted**:
- Possible slight reduction in grammar detection for edge cases (acceptable — monitor and revisit)
- Slightly less varied creative output (acceptable — consistency is valued in tutoring)

---

## Consequences

### Positive Outcomes

**Immediate Benefits**:
- ~10x reduction in per-token LLM cost
- Faster response times improve conversational flow
- Lower latency → better mobile experience (especially on slower connections)
- No deployment or infrastructure changes needed

**Long-term Benefits**:
- Sustainable cost model for growing user base
- Headroom to add more LLM-powered features without cost anxiety
- Environment variable override preserves ability to use Sonnet for specific use cases

### Negative Outcomes

**Immediate Costs**:
- Manual quality validation across languages and levels
- Potential prompt tuning if Haiku responds differently to existing prompts

**Trade-offs**:
- Subtle grammar errors may be missed more often
- Creative responses may be less varied over time

### Risks and Mitigation

**Risk 1**: Grammar feedback quality regression
- **Probability**: Medium
- **Impact**: Medium — incorrect grammar feedback reduces trust
- **Mitigation**: Test all 3 languages × 4 levels with known error patterns. If accuracy drops below acceptable threshold, fall back to Option B (hybrid) for the analysis profile only.

**Risk 2**: Prompt compliance degradation
- **Probability**: Low
- **Impact**: Medium — Hermano personality or language mixing rules not followed
- **Mitigation**: Run existing test suite (1820 tests). Manual smoke testing of edge cases. Existing prompt structure is explicit enough to guide smaller models.

**Risk 3**: Model deprecation
- **Probability**: Low (Haiku 4.5 is current-generation)
- **Impact**: Low — model switch is a single config change
- **Mitigation**: Monitor Anthropic announcements. Migration to successor model is trivial.

---

## Implementation Plan

### Phase 1: Config Change

- [ ] Update `LLM_MODEL` default in `src/api/config.py`
- [ ] Update `.env.example` if it exists
- [ ] Run full test suite (`make test`) — expect 1820+ tests passing

### Phase 2: Quality Validation

- [ ] Manual conversation testing across all levels (A0, A1, A2, B1)
- [ ] Manual conversation testing across all languages (Spanish, German, French)
- [ ] Grammar feedback spot-check with known error patterns
- [ ] Scaffold output validation for A0/A1 learners
- [ ] Review mode testing with spaced repetition words

### Phase 3: Monitoring (Post-Deploy)

- [ ] Track response latency (expect improvement)
- [ ] Monitor error rates from Anthropic API
- [ ] Collect user feedback on conversation quality
- [ ] Review LLM cost dashboard after 1 week

### Rollback Plan

**Trigger Conditions**:
- Grammar feedback accuracy drops noticeably
- User complaints about conversation quality increase
- Prompt compliance issues detected

**Rollback Steps**:
1. Set `LLM_MODEL=claude-sonnet-4-20250514` in environment variables (instant, no deploy needed)
2. Or revert the config.py change and redeploy

**Fallback Option**:
If full Haiku switch isn't acceptable, fall back to Option B (hybrid) — use Haiku for conversational profiles and Sonnet for analysis profiles.

---

## Validation

### Pre-Implementation Checklist

- [x] Decision addresses the original problem (cost + latency)
- [x] Success criteria are measurable
- [x] Risks are identified and mitigated
- [x] Implementation plan is trivial (single config change)
- [x] Rollback plan is instant (env var override)

### Post-Implementation Validation

**Success Metrics**:
- LLM cost: ≥60% reduction (measure after 1 week)
- Response latency p95: ≤2s (measure after deployment)
- Test suite: 1820+ tests passing
- User quality complaints: No increase

**Review Date**: 2 weeks post-implementation

---

## Related Decisions

**Related To**:
- [ADR-002](ADR-002-langgraph-conversation-engine.md) — LangGraph conversation engine (LLM is core of the graph)
- Codebase improvement task #3 — Centralized LLM factory (enables this change)
- Codebase improvement task #15 — LLM instance caching (compatible with model switch)

**Depends On**:
- Centralized LLM factory in `src/agent/llm.py` (already implemented)

**Informs**:
- Future per-profile model selection if quality issues arise (Option B fallback)
- Cost projections for production scaling

---

## References

### Code References
- `src/api/config.py:48` — `LLM_MODEL` default value (change target)
- `src/agent/llm.py` — LLM factory with profile-based configuration
- `src/agent/prompts.py` — System prompts that constrain model output

### External Resources
- [Claude Model Overview](https://docs.anthropic.com/en/docs/about-claude/models) — Model capabilities and pricing
- [Claude Haiku 4.5](https://docs.anthropic.com/en/docs/about-claude/models#claude-haiku-4.5) — Haiku 4.5 specifications

---

## Metadata

**ADR Number**: 008
**Created**: 2026-02-22
**Last Updated**: 2026-02-22
**Version**: 1.0

**Authors**: Claude (AI Assistant)
**Reviewers**: Project Owner

**Tags**: llm, cost-optimization, latency, claude-haiku, model-selection

---

**Status**: PROPOSED
**Next Review**: 2 weeks post-implementation
