"""Checks for the demo seed rows (src/services/demo_seed.py); no database needed."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.db.encryption import decrypt_field
from src.db.models import LearningSession
from src.lessons.service import get_lesson_service
from src.services.demo_seed import LESSONS, build_rows
from src.services.progress import ProgressService

NOW = datetime.now(UTC)
ROWS = build_rows("demo-user", NOW)


def test_streak_is_nine_days_ending_today() -> None:
    sessions = [LearningSession(**row) for row in ROWS["learning_sessions"]]
    assert ProgressService("demo-user", client=MagicMock())._calculate_streak(sessions) == 9


def test_nothing_is_dated_in_the_future() -> None:
    for table in ("learning_sessions", "lesson_progress"):
        for row in ROWS[table]:
            stamp = row.get("started_at") or row["completed_at"]
            assert datetime.fromisoformat(stamp) <= NOW


def test_some_words_are_due_and_translations_are_encrypted() -> None:
    vocab = ROWS["vocabulary"]
    due = [v for v in vocab if datetime.fromisoformat(v["next_review_at"]) <= NOW]
    assert 0 < len(due) < len(vocab)
    assert vocab[0]["translation"] != "hello"
    assert decrypt_field(vocab[0]["translation"]) == "hello"
    assert len({v["word"] for v in vocab}) == len(vocab)  # unique (user_id, word, language)


def test_seeded_lessons_exist() -> None:
    known = {
        lesson.metadata.id.rsplit("/", 1)[-1] for lesson in get_lesson_service().get_all_lessons()
    }
    assert {lesson_id for lesson_id, _, _ in LESSONS} <= known
