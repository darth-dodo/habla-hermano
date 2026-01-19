# ADR-001: Supabase Integration for Multi-User Production Deployment

**Date**: 2025-01-18
**Status**: Accepted
**Context**: Phase 5 - Production-ready authentication and persistence
**Decider(s)**: Project Owner

---

## Summary

Adopt Supabase as the unified backend platform for Habla Hermano, replacing the current anonymous single-user architecture with production-ready multi-user support. This decision integrates Supabase Auth (email/password), Supabase Postgres with Row Level Security (RLS), and PostgresSaver for LangGraph checkpointing, enabling secure, isolated user experiences suitable for production deployment.

---

## Problem Statement

### The Challenge

Habla Hermano currently operates in a single-user, anonymous mode with several production-blocking limitations:

1. **No user authentication**: Anyone can access conversations via cookie manipulation
2. **In-memory persistence**: MemorySaver loses all data on server restart
3. **No user isolation**: Thread IDs in cookies provide weak isolation
4. **No data ownership**: Users cannot access their learning history from other devices
5. **Security vulnerabilities**: Cookies lack secure flag, thread IDs are predictable UUIDs

### Why This Matters

For Habla Hermano to be deployed as a real language learning product:
- Users need accounts to track progress across sessions and devices
- Conversations must persist beyond server restarts
- User data must be securely isolated with proper access controls
- The system must scale beyond single-server deployment

### Success Criteria

- [x] Email/password authentication with secure session management
- [x] Persistent conversations that survive server restarts
- [x] Complete user isolation via Row Level Security
- [x] Single conversation per user (simplicity over complexity)
- [x] All existing functionality preserved (chat, scaffolding, grammar feedback)

---

## Context

### Current State

**Existing Architecture**:
```
Browser Cookie (thread_id: UUID)
         │
         ▼
    FastAPI ─────► LangGraph ─────► MemorySaver (in-process)
         │
         ▼
    No persistent storage
```

**Pain Points**:

- Server restart loses all conversation history
- No way for users to access their data from different devices
- Cookie hijacking possible without authentication
- No vocabulary/progress tracking persistence

**Technical Constraints**:

- Must maintain FastAPI + HTMX frontend architecture
- LangGraph checkpointing must continue working
- Cannot disrupt existing Hermano personality and chat flow
- Development environment must remain simple (no complex infrastructure)

### Requirements

**Functional Requirements**:

- Email/password signup and login
- Persistent single conversation per user
- Vocabulary and progress data persistence
- Logout functionality
- Conversation history survives indefinitely

**Non-Functional Requirements**:

- **Performance**: <200ms authentication, <100ms database operations
- **Scalability**: Support 1000+ concurrent users
- **Maintainability**: Minimal custom auth code (leverage Supabase)
- **Security**: JWT-based auth, RLS for data isolation, HTTPS only
- **Reliability**: 99.9% uptime via Supabase managed infrastructure

**Stakeholder Concerns**:

- Simple onboarding (email/password, no OAuth complexity yet)
- Data privacy (users own their data, can delete account)
- Cost efficiency (Supabase free tier supports initial launch)

---

## Options Considered

### Option A: Supabase (Auth + Postgres + PostgresSaver)

**Description**:
Full Supabase integration using their managed Auth service for email/password authentication, Postgres database with Row Level Security for all user data, and LangGraph's PostgresSaver for conversation checkpointing.

**Implementation**:
- Supabase Auth handles signup/login/logout with JWT tokens
- JWT stored in httponly cookies, validated by FastAPI middleware
- User ID becomes thread_id for LangGraph (one conversation per user)
- All tables use RLS policies: users only access their own data
- PostgresSaver connects to Supabase Postgres for checkpointing

**Pros**:

- Managed infrastructure (no server ops)
- Built-in auth best practices (password hashing, token refresh)
- Row Level Security for bulletproof data isolation
- Generous free tier (50K MAU, 500MB database)
- PostgresSaver is LangGraph's recommended production checkpointer
- Single platform for auth, database, and realtime (future features)

**Cons**:

- Vendor lock-in to Supabase platform
- Requires internet connectivity for all operations
- Learning curve for RLS policy writing
- Slightly more complex local development setup

**Risks**:

- **Supabase outage**: Low probability; mitigate with status monitoring
- **RLS misconfiguration**: High impact; mitigate with thorough testing

**Estimated Effort**: 3-4 days

---

### Option B: Self-Hosted Auth + SQLite/Postgres

**Description**:
Implement custom authentication using libraries like `passlib` for password hashing and `python-jose` for JWT, storing users in SQLite (local) or self-managed Postgres (production).

**Implementation**:
- Custom User model with password hashing
- JWT generation and validation middleware
- AsyncSqliteSaver or custom Postgres integration
- Manual session management

**Pros**:

- Full control over authentication flow
- No external dependencies or vendor lock-in
- Works offline for local development
- No recurring costs

**Cons**:

- Significant security burden (must implement correctly)
- More code to maintain and test
- AsyncSqliteSaver has known bugs (current Phase 4 issue)
- No built-in features (password reset, email verification)
- Scaling requires infrastructure expertise

**Risks**:

- **Security vulnerabilities**: High probability with custom auth
- **Maintenance burden**: Ongoing security updates required

**Estimated Effort**: 5-7 days + ongoing maintenance

---

### Option C: Firebase (Auth + Firestore)

**Description**:
Use Firebase Authentication with Firestore for data storage, requiring custom LangGraph checkpointer implementation.

**Implementation**:
- Firebase Auth SDK for email/password
- Firestore for user data and vocabulary
- Custom LangGraph checkpointer for Firestore
- Firebase security rules for data isolation

**Pros**:

- Mature auth system with extensive features
- Good free tier
- Well-documented SDKs

**Cons**:

- No native LangGraph checkpointer (must build custom)
- Different data model (NoSQL vs relational)
- Google ecosystem lock-in
- Firestore query limitations for complex relationships

**Risks**:

- **Custom checkpointer bugs**: High probability, high impact
- **Data modeling challenges**: Firestore not ideal for relational data

**Estimated Effort**: 5-6 days

---

## Comparison Matrix

| Criteria                  | Weight | Option A (Supabase) | Option B (Self-Hosted) | Option C (Firebase) |
| ------------------------- | ------ | ------------------- | ---------------------- | ------------------- |
| **Security**              | High   | 5                   | 2                      | 4                   |
| **Maintainability**       | High   | 5                   | 2                      | 3                   |
| **LangGraph Compatibility**| High   | 5                   | 3                      | 2                   |
| **Scalability**           | High   | 5                   | 3                      | 4                   |
| **Implementation Effort** | Medium | 4                   | 2                      | 3                   |
| **Complexity**            | Medium | 4                   | 2                      | 3                   |
| **Cost Efficiency**       | Medium | 5                   | 5                      | 4                   |
| **Offline Development**   | Low    | 3                   | 5                      | 3                   |
| **Total Score**           | -      | **36**              | 24                     | 26                  |

**Scoring**: 1 = Poor, 2 = Below Average, 3 = Acceptable, 4 = Good, 5 = Excellent
**Note**: For negative criteria (Complexity, Effort), higher score = lower complexity/effort

---

## Decision

### Chosen Option

**Selected**: Option A: Supabase (Auth + Postgres + PostgresSaver)

**Rationale**:
Supabase provides the best balance of security, developer experience, and LangGraph compatibility. The built-in PostgresSaver support eliminates the need for custom checkpointer code, while Row Level Security provides robust data isolation without application-level checks. The managed infrastructure reduces operational burden and allows focus on the learning experience.

**Key Factors**:

- Native LangGraph PostgresSaver support (no custom code)
- Row Level Security for foolproof data isolation
- Managed auth with security best practices built-in
- Free tier sufficient for initial production launch
- Single platform reduces integration complexity

**Trade-offs Accepted**:

- Vendor lock-in to Supabase (acceptable given benefits)
- Requires internet for local development (acceptable)
- Learning RLS syntax (one-time investment)

---

## Consequences

### Positive Outcomes

**Immediate Benefits**:

- Production-ready authentication out of the box
- Persistent conversations that survive server restarts
- Secure user isolation without custom security code
- User ID as thread_id simplifies session management

**Long-term Benefits**:

- Supabase Realtime for future collaborative features
- Built-in analytics and monitoring
- Easy scaling as user base grows
- Standard Postgres allows migration if needed

### Negative Outcomes

**Immediate Costs**:

- Supabase project setup and configuration
- Migration from MemorySaver to PostgresSaver
- Auth UI implementation (login/signup forms)

**Technical Debt Created**:

- None significant; Supabase is a clean foundation

**Trade-offs**:

- Cannot run fully offline (acceptable for production app)
- Monthly costs after free tier (acceptable trade for managed infra)

### Risks and Mitigation

**Risk 1**: Supabase service outage

- **Probability**: Low
- **Impact**: Application unavailable during outage
- **Mitigation**: Status monitoring, error pages, local caching for read-only

**Risk 2**: RLS policy misconfiguration exposing user data

- **Probability**: Medium (during initial implementation)
- **Impact**: Critical security breach
- **Mitigation**: Comprehensive RLS testing, security review before launch

**Risk 3**: PostgresSaver compatibility issues

- **Probability**: Low
- **Impact**: Conversation persistence broken
- **Mitigation**: Test with LangGraph version, have MemorySaver fallback

---

## Implementation Plan

### Phases

**Phase 1**: Configuration + Dependencies

- **Tasks**:
  - [ ] Create Supabase project
  - [ ] Add dependencies (supabase, PyJWT, langgraph-checkpoint-postgres, psycopg)
  - [ ] Configure environment variables
  - [ ] Create Supabase client singleton
- **Deliverable**: Working Supabase connection

**Phase 2**: Database Schema

- **Tasks**:
  - [ ] Create user_profiles table with trigger
  - [ ] Create vocabulary table
  - [ ] Create learning_sessions table
  - [ ] Create lesson_progress table
  - [ ] Enable and test RLS policies
- **Deliverable**: Complete database schema with RLS

**Phase 3**: Auth Module

- **Tasks**:
  - [ ] Create JWT validation middleware
  - [ ] Create auth routes (signup/login/logout)
  - [ ] Create login/signup HTML templates
  - [ ] Add CurrentUserDep dependency
- **Deliverable**: Working authentication flow

**Phase 4**: PostgresSaver Checkpointer

- **Tasks**:
  - [ ] Update checkpointer.py for AsyncPostgresSaver
  - [ ] Implement user_id to thread_id mapping
  - [ ] Update tests for new checkpointer
- **Deliverable**: Persistent conversations in Postgres

**Phase 5**: Protected Routes

- **Tasks**:
  - [ ] Add CurrentUserDep to chat routes
  - [ ] Add CurrentUserDep to progress routes
  - [ ] Simplify session management (user_id = thread)
- **Deliverable**: All routes require authentication

**Phase 6**: Repository Migration

- **Tasks**:
  - [ ] Update repository layer for Supabase client
  - [ ] Remove SQLAlchemy dependencies
  - [ ] Update vocabulary/progress queries
- **Deliverable**: All data access via Supabase

**Phase 7**: Tests + Cleanup

- **Tasks**:
  - [ ] Add auth test fixtures
  - [ ] Create auth endpoint tests
  - [ ] Update existing tests for auth
  - [ ] Remove deprecated code (MemorySaver, SQLite)
- **Deliverable**: Full test coverage, clean codebase

### Dependencies

**Prerequisites**:

- Supabase account and project created
- Database credentials obtained
- langgraph-checkpoint-postgres package tested

**Parallel Work**:

- Frontend auth UI can be built while backend auth is developed
- Database schema can be created while dependencies are added

**Blocked By**:

- None (can start immediately)

### Rollback Plan

**Trigger Conditions**:
- PostgresSaver incompatible with current LangGraph version
- Supabase free tier insufficient for basic testing
- Critical RLS bugs discovered

**Rollback Steps**:

1. Revert checkpointer.py to MemorySaver
2. Keep cookie-based thread_id management
3. Remove auth requirements from routes

**Fallback Option**:
Continue with MemorySaver and anonymous mode for MVP, revisit auth later

---

## Validation

### Pre-Implementation Checklist

- [x] Decision addresses the original problem
- [x] Success criteria are achievable
- [x] Risks are identified and mitigated
- [x] Implementation plan is realistic
- [x] Dependencies are understood
- [x] Rollback plan exists

### Architect Quality Standards

- [x] **Scalability**: Supabase handles 1000+ concurrent users
- [x] **Maintainability**: Managed auth reduces maintenance burden
- [x] **Best Practices**: RLS, JWT, httponly cookies follow standards
- [x] **Simplicity**: Supabase simplifies vs custom implementation
- [x] **Trade-offs**: Vendor lock-in accepted for benefits

### Post-Implementation Validation

**Success Metrics**:

- Auth response time: Target <200ms
- Database query time: Target <100ms
- RLS policy coverage: Target 100% of tables
- Test coverage: Target 95%+

**Validation Tests**:

- [ ] User A cannot access User B's conversations
- [ ] Conversations persist after server restart
- [ ] Login/logout flow works correctly
- [ ] Password reset flow works (if implemented)

**Review Date**: 2025-02-18 (1 month post-implementation)

---

## Related Decisions

**Supersedes**:

- Phase 4 MemorySaver implementation - Replaced by PostgresSaver

**Related To**:

- None (first ADR)

**Depends On**:

- None

**Informs**:

- Future OAuth integration (can add Supabase OAuth providers)
- Future multi-device sync features
- Future collaborative learning features

---

## References

### Documentation

- [Design Document](../design/phase5-supabase-auth.md) - Implementation details
- [Phase 4 Design](../design/phase4-persistence.md) - Previous persistence approach

### External Resources

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth) - Official docs
- [LangGraph PostgresSaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.postgres) - Checkpointer docs
- [Row Level Security](https://supabase.com/docs/guides/auth/row-level-security) - RLS patterns

### Code References

- `src/agent/checkpointer.py` - Current MemorySaver implementation
- `src/api/session.py` - Current cookie-based session management
- `src/api/routes/chat.py` - Chat endpoints to be protected

---

## Discussion and Updates

### Decision History

**2025-01-18**: Proposed

- Initial proposal for Supabase integration based on production requirements
- User confirmed: email/password only, single conversation per user, all data in Supabase

**2025-01-18**: Accepted

- Decision approved for implementation
- ADR and Design Doc created as documentation-first approach

### Questions Raised

**Q1**: Should we support OAuth (Google, GitHub) from the start?

- **A**: No, start with email/password for simplicity. OAuth can be added later via Supabase.

**Q2**: Should we support multiple conversations per user?

- **A**: No, single conversation simplifies UX and implementation. Can add later if needed.

**Q3**: What happens to existing anonymous conversations?

- **A**: They will be lost. This is acceptable as current system is development-only.

### Feedback Incorporated

- User requirement for production deployment drove the decision
- Simplicity preference (email/password, single conversation) shaped the scope

---

## Metadata

**ADR Number**: 001
**Created**: 2025-01-18
**Last Updated**: 2025-01-18
**Version**: 1.0

**Authors**: Claude (AI Assistant)
**Reviewers**: Project Owner

**Tags**: authentication, persistence, supabase, security, langgraph

**Project Phase**: Development

---

## Notes

This ADR represents a significant architectural shift from anonymous/ephemeral to authenticated/persistent. While this adds complexity, it's necessary for any production deployment of a language learning application where users expect to maintain their progress over time.

The choice of Supabase over alternatives is primarily driven by the native LangGraph PostgresSaver support, which avoids custom checkpointer code and its associated maintenance burden.

---

**Status**: ACCEPTED
**Next Review**: 2025-02-18
