"""Seed a demo account with about four weeks of believable learning history.

Writes, for ONE demo user only: profile, learning sessions (a streak ending
today), vocabulary with SM-2 review state (some due today), and completed
lessons. Chat threads are not written here; create them through the live
site so checkpoints are real.

Needs the TARGET environment's settings in the shell, because encrypted
fields (translations, display name) must use that environment's key:
    SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, SECRET_KEY, ENCRYPTION_SALT
    DEMO_PASSWORD   (only needed when the user does not exist yet)

Usage (on the Render shell the env is already set):
    make seed-demo EMAIL=demo@example.com          # dry run
    make seed-demo EMAIL=demo@example.com YES=1    # write
or directly:
    uv run python -m scripts.seed_demo --email demo@example.com         # dry run
    uv run python -m scripts.seed_demo --email demo@example.com --yes   # write

Each write first deletes the demo user's rows in the seeded tables, so runs
never duplicate. The streak counts days ending today: re-run on demo day.
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from src.config import get_settings
from src.db.client import get_supabase_admin
from src.db.encryption import encrypt_field

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
        first_seen = now - timedelta(days=27 - (i * 27) // len(WORDS))
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


def find_or_create_user(admin: Any, email: str) -> str:
    """Return the demo user's ID, creating a confirmed account if missing."""
    page = 1
    while users := admin.auth.admin.list_users(page=page, per_page=200):
        for user in users:
            if (user.email or "").lower() == email.lower():
                return str(user.id)
        page += 1
    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        sys.exit("User does not exist. Set DEMO_PASSWORD to create it.")
    created = admin.auth.admin.create_user(
        {"email": email, "password": password, "email_confirm": True}
    )
    return str(created.user.id)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--email", required=True, help="the demo account's email")
    parser.add_argument("--yes", action="store_true", help="write (default is a dry run)")
    args = parser.parse_args()

    settings = get_settings()
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY and settings.ENCRYPTION_SALT):
        sys.exit(
            "Set SUPABASE_URL, SUPABASE_SERVICE_KEY, SECRET_KEY and ENCRYPTION_SALT for the target env."
        )

    rows = build_rows("<demo-user-id>", datetime.now(UTC))
    host = settings.SUPABASE_URL.split("//")[-1].split(".")[0]
    print(f"Target Supabase project: {host}")
    print(f"Demo account: {args.email}")
    for table, items in rows.items():
        print(f"  {table}: {len(items)} rows")
    due = sum(1 for v in rows["vocabulary"] if v["next_review_at"] <= datetime.now(UTC).isoformat())
    print(f"  words due for review now: {due}; streak: 9 days")
    if not args.yes:
        print("Dry run. Re-run with --yes to write.")
        return

    admin = get_supabase_admin()
    user_id = find_or_create_user(admin, args.email)
    for table in SEEDED_TABLES:  # only this user's rows
        admin.table(table).delete().eq("user_id", user_id).execute()

    admin.table("user_profiles").upsert(
        {
            "id": user_id,
            "display_name": encrypt_field(DISPLAY_NAME),
            "preferred_language": LANGUAGE,
            "current_level": LEVEL,
        }
    ).execute()
    for table, items in build_rows(user_id, datetime.now(UTC)).items():
        admin.table(table).insert(items).execute()
        print(f"Wrote {len(items)} rows to {table}")
    print("Done. Sign in as the demo user and open /progress to check.")


if __name__ == "__main__":
    main()
