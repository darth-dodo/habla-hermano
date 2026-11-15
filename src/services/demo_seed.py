"""Demo account seed data: about four weeks of believable learning history.

Used by ``make seed-demo`` (scripts/seed_demo.py) and the /demo admin page.
Writes, for ONE user only: profile, learning sessions (a 9-day streak ending
today), vocabulary with SM-2 review state (some due today), and completed
lessons, plus ten scripted conversations (demo_conversations.py). Encrypted
fields use the running environment's key.
"""

import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from src.db.encryption import encrypt_field
from src.services.demo_conversations import seed_conversations
from src.services.user_data import delete_user_rows

LANGUAGE, LEVEL, DISPLAY_NAME = "es", "A1", "Demo"
SEEDED_TABLES = ("vocabulary", "learning_sessions", "lesson_progress")

# Days ago with a session: a 9-day streak ending today, plus earlier gaps.
SESSION_DAYS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 13, 16, 17, 19, 22, 24, 27]

# (lesson_id, days ago completed, score)
LESSONS = [
    ("greetings-001", 27, 92),
    ("essentials-001", 24, 88),
    ("numbers-001", 22, 75),
    ("colors-001", 19, 96),
    ("about-me-001", 16, 84),
    ("family-001", 11, 80),
    ("food-drink-001", 6, 71),
    ("daily-routine-001", 2, 86),
]

# (word, translation, part of speech)
WORDS = [
    ("hola", "hello", "interjection"),
    ("gracias", "thank you", "interjection"),
    ("por favor", "please", "phrase"),
    ("buenos días", "good morning", "phrase"),
    ("me llamo", "my name is", "phrase"),
    ("mucho gusto", "nice to meet you", "phrase"),
    ("uno", "one", "number"),
    ("diez", "ten", "number"),
    ("rojo", "red", "adjective"),
    ("azul", "blue", "adjective"),
    ("verde", "green", "adjective"),
    ("la madre", "mother", "noun"),
    ("el padre", "father", "noun"),
    ("el hermano", "brother", "noun"),
    ("la hermana", "sister", "noun"),
    ("los abuelos", "grandparents", "noun"),
    ("el agua", "water", "noun"),
    ("el pan", "bread", "noun"),
    ("el café", "coffee", "noun"),
    ("la manzana", "apple", "noun"),
    ("comer", "to eat", "verb"),
    ("beber", "to drink", "verb"),
    ("despertarse", "to wake up", "verb"),
    ("ducharse", "to shower", "verb"),
    ("trabajar", "to work", "verb"),
    ("ser", "to be (permanent)", "verb"),
    ("estar", "to be (temporary)", "verb"),
    ("tener", "to have", "verb"),
    ("vivir", "to live", "verb"),
    ("hablar", "to speak", "verb"),
    ("cansado", "tired", "adjective"),
    ("contento", "happy", "adjective"),
    ("temprano", "early", "adverb"),
    ("tarde", "late", "adverb"),
    ("siempre", "always", "adverb"),
    ("a veces", "sometimes", "phrase"),
    ("el desayuno", "breakfast", "noun"),
    ("la cena", "dinner", "noun"),
    ("el trabajo", "work, job", "noun"),
    ("la casa", "house", "noun"),
]


def build_rows(user_id: str, now: datetime) -> dict[str, list[dict[str, Any]]]:
    """Build every row to insert. Pure, so it can be checked without a database."""
    sessions = []
    for i, days_ago in enumerate(SESSION_DAYS):
        # Today's session started an hour ago, so it is never in the future.
        start = (
            now - timedelta(hours=1)
            if days_ago == 0
            else now - timedelta(days=days_ago, hours=i % 5)
        )
        sessions.append(
            {
                "user_id": user_id,
                "language": LANGUAGE,
                "level": LEVEL if days_ago < 20 else "A0",
                "started_at": start.isoformat(),
                "ended_at": (start + timedelta(minutes=12 + i % 9)).isoformat(),
                "messages_count": 8 + (i * 3) % 14,
                "words_learned": 1 + i % 4,
            }
        )

    vocabulary = []
    for i, (word, translation, pos) in enumerate(WORDS):
        first_seen = now - timedelta(days=27 - (i * 28) // len(WORDS), hours=1)
        if i < 12:  # well known: long intervals, not due
            ef, interval, reps, due_in = 2.6, 16 + i, 4, 3 + i % 6
        elif i < 30:  # learning: short intervals, a few due today
            ef, interval, reps = 2.3, 2 + i % 4, 2
            due_in = -1 if i % 3 == 0 else 1 + i % 3
        else:  # new: due today
            ef, interval, reps, due_in = 2.5, 1, 1, 0
        seen = reps + 2
        vocabulary.append(
            {
                "user_id": user_id,
                "word": word,
                "translation": encrypt_field(translation),
                "language": LANGUAGE,
                "part_of_speech": pos,
                "first_seen_at": first_seen.isoformat(),
                "times_seen": seen,
                "times_correct": max(seen - 1 - i % 2, 0),
                "easiness_factor": ef,
                "interval_days": interval,
                "repetition_count": reps,
                "last_reviewed_at": (now - timedelta(days=max(interval - due_in, 1))).isoformat(),
                "next_review_at": (now + timedelta(days=due_in)).isoformat(),
            }
        )

    lessons = [
        {
            "user_id": user_id,
            "lesson_id": lesson_id,
            "completed_at": (now - timedelta(days=days_ago)).isoformat(),
            "score": score,
        }
        for lesson_id, days_ago, score in LESSONS
    ]
    return {"learning_sessions": sessions, "vocabulary": vocabulary, "lesson_progress": lessons}


def seed_user(admin: Any, user_id: str) -> dict[str, int]:
    """Replace this user's seeded rows with fresh demo history. Returns rows per table."""
    for table in SEEDED_TABLES:  # only this user's rows, so re-runs never duplicate
        admin.table(table).delete().eq("user_id", user_id).execute()
    admin.table("user_profiles").upsert(
        {
            "id": user_id,
            "display_name": encrypt_field(DISPLAY_NAME),
            "preferred_language": LANGUAGE,
            "current_level": LEVEL,
        }
    ).execute()
    written = {}
    for table, items in build_rows(user_id, datetime.now(UTC)).items():
        admin.table(table).insert(items).execute()
        written[table] = len(items)
    return written


DEMO_EMAIL_PREFIX, DEMO_EMAIL_DOMAIN = "demo-", "@example.com"


def is_demo_email(email: str | None) -> bool:
    """True only for accounts this module created, so real users are never touched."""
    email = (email or "").lower()
    return email.startswith(DEMO_EMAIL_PREFIX) and email.endswith(DEMO_EMAIL_DOMAIN)


def list_demo_accounts(admin: Any) -> list[dict[str, Any]]:
    """Every demo account, newest first."""
    accounts, page = [], 1
    while users := admin.auth.admin.list_users(page=page, per_page=200):
        accounts += [
            {
                "id": str(u.id),
                "email": u.email,
                "created_at": u.created_at,
                "last_sign_in_at": u.last_sign_in_at,
            }
            for u in users
            if is_demo_email(u.email)
        ]
        page += 1
    return sorted(accounts, key=lambda a: str(a["created_at"]), reverse=True)


def get_demo_email(admin: Any, user_id: str) -> str:
    """Return the account's email, or raise LookupError if it is missing or not a demo."""
    try:
        email = admin.auth.admin.get_user_by_id(user_id).user.email
    except Exception as exc:
        raise LookupError(user_id) from exc
    if not is_demo_email(email):
        raise LookupError(user_id)
    return str(email)


def new_demo_password(admin: Any, user_id: str) -> str:
    """Give a demo account a fresh password and return it (passwords are never stored)."""
    password = secrets.token_urlsafe(12)
    admin.auth.admin.update_user_by_id(user_id, {"password": password})
    return password


def delete_demo_account(admin: Any, user_id: str) -> None:
    """Delete a demo account and all its rows."""
    delete_user_rows(admin, user_id)
    admin.auth.admin.delete_user(user_id)


async def reseed_demo_account(admin: Any, user_id: str) -> None:
    """Wipe the account's data, then write the history and the ten conversations."""
    await asyncio.to_thread(delete_user_rows, admin, user_id)
    await asyncio.to_thread(seed_user, admin, user_id)
    await seed_conversations(admin, user_id, datetime.now(UTC))


async def create_demo_account(admin: Any) -> tuple[str, str]:
    """Create a new confirmed demo user, seed it, and return (email, password)."""
    email = f"{DEMO_EMAIL_PREFIX}{secrets.token_hex(4)}{DEMO_EMAIL_DOMAIN}"
    password = secrets.token_urlsafe(12)
    created = await asyncio.to_thread(
        admin.auth.admin.create_user,
        {"email": email, "password": password, "email_confirm": True},
    )
    await reseed_demo_account(admin, str(created.user.id))
    return email, password
