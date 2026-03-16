# Privacy & Security Page Design

> User-facing transparency page with data management controls

---

## Summary

Add a dedicated `/privacy/` page accessible from the hamburger sidebar menu (all users) and the guest dropdown menu. The page shows how Habla Hermano protects user data and gives authenticated users controls to delete conversation history or their entire account.

## Goals

1. Build user trust by surfacing the security infrastructure that already exists (Fernet encryption, RLS, no data selling)
2. Highlight that the project is open source
3. Give authenticated users self-service data management (delete history, delete account)

## Non-Goals

- Legal privacy policy or terms of service (this is a learning project, not a commercial product)
- Data export functionality
- Granular per-thread or per-conversation deletion (already handled in the thread sidebar)
- Cookie consent banners or GDPR compliance flows

---

## Navigation

### Authenticated users (sidebar drawer)

New link in `thread_sidebar.html` bottom nav section, between "Progress" and "Theme":

```
Lessons
Progress
Privacy & Security   ← NEW (shield icon)
Theme
Logout
```

### Guest users (hamburger dropdown)

New link in `app_header.html` guest dropdown, between "Free Chat" and the divider before themes:

```
Lessons
Progress
Free Chat
Privacy & Security   ← NEW (shield icon)
---
Theme options...
---
Login
```

---

## Page Layout

Route: `GET /privacy/`
Template: `src/templates/privacy.html` (extends `base.html`)
Pattern: Same as `progress.html` — header with back-to-chat link, scrollable content area.

### Section A: "How we protect your data" (all users)

Card grid (responsive: 1 col mobile, 2 col desktop). Each card has an icon, title, and 1-2 sentence description.

| Card | Icon | Title | Description |
|------|------|-------|-------------|
| 1 | Lock/shield | Encrypted at rest | Your conversations and personal data are encrypted using AES-128 (Fernet). |
| 2 | Users/isolate | Data isolation | Your data is isolated at the database level with row-level security. No user can access another user's data. |
| 3 | X-circle | No data selling | We never sell, share, or monetize your learning data. Your conversations exist to help you learn, nothing else. |
| 4 | Code/github | Open source | Habla Hermano is fully open source. You can inspect every line of code that handles your data. |

Card 4 includes a link to the GitHub repository.

### Section B: "Your data" (authenticated only)

Single card with:
- **Delete conversation history** button (accent-colored, not red)
- Inline confirmation: "This will permanently delete all your conversations. This cannot be undone." with Confirm (red) / Cancel buttons
- On success: toast/flash message, redirect to `/`

### Section C: "Account" (authenticated only)

Single card with:
- **Delete my account** button (red/danger styled)
- Two-step confirmation: first click reveals a text input where user must type "DELETE" to confirm
- On success: clears auth cookies, redirects to `/` with a flash message

### Guest fallback (sections B & C)

When not authenticated, sections B and C are replaced with:
> "Log in to manage your data and account."
> [Log in] button

---

## Backend

### New route file: `src/api/routes/privacy.py`

```python
router = APIRouter(prefix="/privacy")

GET  /              → render privacy.html
POST /delete-history → delete all user threads + checkpoint data
POST /delete-account → delete Supabase auth user (cascades all data)
```

### `GET /privacy/`

- Accepts `OptionalUserDep` (works for both guests and authenticated users)
- Renders `privacy.html` with `user` context variable

### `POST /privacy/delete-history`

- Requires authentication (return 401 if not authenticated)
- Requires CSRF header (`HX-Request: true`)
- Deletes all rows from `conversation_threads` where `user_id = auth.uid()`
- Deletes all checkpoint data for threads matching `user:{user_id}:*` pattern
- Returns redirect to `/` on success

### `POST /privacy/delete-account`

- Requires authentication
- Requires CSRF header
- Validates that request body contains `confirm=DELETE`
- Calls Supabase admin API to delete the auth user
- All user data cascades via `ON DELETE CASCADE` foreign keys
- Clears auth cookies
- Returns redirect to `/` on success

---

## Security Considerations

- Both destructive endpoints require authentication + CSRF headers
- Delete account requires explicit typed confirmation ("DELETE")
- Delete history uses inline confirm/cancel (consistent with thread delete pattern in sidebar)
- No data is returned in responses — just redirects
- Rate limiting applies via existing middleware

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/templates/privacy.html` | Create — new page template |
| `src/api/routes/privacy.py` | Create — new route file |
| `src/api/routes/__init__.py` | Modify — register privacy router |
| `src/templates/partials/thread_sidebar.html` | Modify — add Privacy & Security nav link |
| `src/templates/partials/app_header.html` | Modify — add Privacy & Security to guest dropdown |

---

## Design Tokens

Uses existing design system: `bg-surface`, `bg-surface-elevated`, `border-border`, `text-text`, `text-text-muted`, `bg-accent`, `text-accent-text`, `rounded-2xl`, etc. No new CSS or design tokens needed.

Danger buttons use `bg-red-500/15 text-red-500` for the delete account action (consistent with thread delete styling in sidebar).
