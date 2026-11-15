"""complete_lesson_and_persist saves a signed-in user's lesson under the bare lesson ID."""

from unittest.mock import MagicMock, patch

from src.api.auth import AuthenticatedUser
from src.services.lesson_completion import complete_lesson_and_persist


def test_saves_progress_and_queues_vocabulary_for_the_user() -> None:
    user = AuthenticatedUser(id="user-1", email="a@b.c")
    vocab = [{"word": "hola", "translation": "hello"}]
    with (
        patch("src.services.lesson_completion.LessonProgressRepository") as repo_cls,
        patch(
            "src.services.lesson_completion.initialize_lesson_vocabulary_for_review"
        ) as init_vocab,
    ):
        repo_cls.return_value = MagicMock()
        complete_lesson_and_persist(
            user=user, lesson_id="es/A1/greetings-001", score=90, vocabulary=vocab, language="es"
        )

    repo_cls.assert_called_once_with("user-1")
    repo_cls.return_value.complete_lesson.assert_called_once_with("greetings-001", score=90)
    init_vocab.assert_called_once_with(effective_id="user-1", vocabulary=vocab, language="es")
