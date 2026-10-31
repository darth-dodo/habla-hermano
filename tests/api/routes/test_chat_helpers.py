"""Unit tests for the private helpers extracted from the chat routes.

Covers the shared turn helpers in src/api/routes/chat.py and the SSE
helpers in src/api/routes/chat_stream.py.
"""

import json
from typing import Any
from unittest.mock import MagicMock

from postgrest.exceptions import APIError

from src.api.auth import AuthenticatedUser
from src.api.routes.chat import (
    ChatCookies,
    ChatIdentity,
    _freeform_inputs,
    _graph_config,
    _level_language_error,
    _message_error,
    _persist_chat_turn,
    _resolve_freeform_identity,
    _voice_ws_token,
)
from src.api.routes.chat_stream import (
    _lesson_inputs,
    _lesson_state_events,
    _resolve_stream_identity,
    _StreamTurn,
    _validate_stream_input,
)
from src.api.validation import MAX_MESSAGE_LENGTH

USER = AuthenticatedUser(id="user-1", email="u@example.com")


def _api_error() -> APIError:
    return APIError({"code": "500", "message": "boom", "hint": None, "details": None})


class TestValidation:
    """Tests for _message_error and _level_language_error."""

    def test_empty_message(self) -> None:
        assert _message_error("") == "Message cannot be empty."

    def test_too_long_message_with_hint(self) -> None:
        error = _message_error("a" * (MAX_MESSAGE_LENGTH + 1), " Shorten it.")
        assert error == f"Message is too long (max {MAX_MESSAGE_LENGTH} characters). Shorten it."

    def test_valid_message(self) -> None:
        assert _message_error("Hola") is None

    def test_invalid_level(self) -> None:
        error = _level_language_error("Z9", "es")
        assert error is not None
        assert error.startswith("Invalid level 'Z9'")

    def test_invalid_language(self) -> None:
        error = _level_language_error("A1", "xx")
        assert error is not None
        assert error.startswith("Invalid language 'xx'")

    def test_valid_level_and_language(self) -> None:
        assert _level_language_error("A1", "es") is None


class TestResolveFreeformIdentity:
    """Tests for _resolve_freeform_identity."""

    def _resolve(self, **overrides: Any) -> tuple[ChatIdentity | None, MagicMock]:
        factory = MagicMock()
        kwargs: dict[str, Any] = {
            "user": USER,
            "user_client": MagicMock(),
            "requested_thread_id": None,
            "cookies": ChatCookies(),
            "language": "es",
            "level": "A1",
            "thread_service_factory": factory,
        }
        kwargs.update(overrides)
        return _resolve_freeform_identity(**kwargs), factory

    def test_guest_uses_cookie_session(self) -> None:
        identity, factory = self._resolve(
            user=None, user_client=None, cookies=ChatCookies(session_id="sess-1")
        )
        assert identity == ChatIdentity("sess-1", None, None, None)
        factory.assert_not_called()

    def test_first_time_guest_gets_new_session(self) -> None:
        identity, _ = self._resolve(user=None, user_client=None)
        assert identity is not None
        assert identity.new_session_id == identity.thread_id
        assert identity.user_id is None

    def test_user_without_client_uses_versioned_thread(self) -> None:
        identity, factory = self._resolve(
            user_client=None, cookies=ChatCookies(conversation_version="v2")
        )
        assert identity is not None
        assert identity.thread_id.endswith(":v2")
        assert identity.user_id == USER.id
        factory.assert_not_called()

    def test_owned_requested_thread(self) -> None:
        identity, factory = self._resolve(requested_thread_id="user:abc:1")
        assert identity == ChatIdentity("user:abc:1", USER.id, touch_thread_id="user:abc:1")
        factory.return_value.get_thread.assert_called_once_with("user:abc:1")

    def test_unowned_requested_thread_returns_none(self) -> None:
        factory = MagicMock()
        factory.return_value.get_thread.return_value = None
        identity, _ = self._resolve(
            requested_thread_id="user:other:1", thread_service_factory=factory
        )
        assert identity is None

    def test_auto_creates_thread(self) -> None:
        factory = MagicMock()
        factory.return_value.create_thread.return_value.thread_id = "user:new:1"
        identity, _ = self._resolve(thread_service_factory=factory, language="de", level="A2")
        assert identity == ChatIdentity(
            "user:new:1", USER.id, touch_thread_id="user:new:1", created_thread_id="user:new:1"
        )
        factory.return_value.create_thread.assert_called_once_with(language="de", level="A2")


class TestGraphInputs:
    """Tests for _freeform_inputs and _graph_config."""

    def test_freeform_inputs(self) -> None:
        inputs = _freeform_inputs("Hola", "A1", "es", "user-1")
        assert inputs["messages"][0].content == "Hola"
        assert (inputs["level"], inputs["language"], inputs["user_id"]) == ("A1", "es", "user-1")

    def test_graph_config(self) -> None:
        client = MagicMock()
        config = _graph_config("t-1", client)
        assert config == {"configurable": {"thread_id": "t-1", "supabase_client": client}}


class TestPersistChatTurn:
    """Tests for _persist_chat_turn."""

    def _persist(self, identity: ChatIdentity, **overrides: Any) -> tuple[MagicMock, MagicMock]:
        progress, threads = MagicMock(), MagicMock()
        kwargs: dict[str, Any] = {
            "identity": identity,
            "user": USER,
            "user_client": MagicMock(),
            "language": "es",
            "level": "A1",
            "new_vocabulary": [{"word": "hola"}],
            "progress_service_factory": progress,
            "thread_service_factory": threads,
        }
        kwargs.update(overrides)
        _persist_chat_turn(**kwargs)
        return progress, threads

    def test_records_vocab_and_touches_thread(self) -> None:
        identity = ChatIdentity("t-1", USER.id, touch_thread_id="t-1")
        progress, threads = self._persist(identity)
        progress.return_value.record_chat_activity.assert_called_once_with(
            language="es", level="A1", new_vocab=[{"word": "hola"}]
        )
        threads.return_value.touch.assert_called_once_with("t-1")

    def test_guest_is_not_tracked(self) -> None:
        identity = ChatIdentity("sess", None, touch_thread_id="t-1")
        progress, threads = self._persist(identity, user=None, user_client=None)
        progress.assert_not_called()
        threads.assert_not_called()

    def test_no_vocab_skips_progress(self) -> None:
        identity = ChatIdentity("t-1", USER.id)
        progress, threads = self._persist(identity, new_vocabulary=[])
        progress.assert_not_called()
        threads.assert_not_called()

    def test_failures_are_swallowed(self) -> None:
        progress, threads = MagicMock(), MagicMock()
        progress.return_value.record_chat_activity.side_effect = _api_error()
        threads.return_value.touch.side_effect = RuntimeError("db down")
        identity = ChatIdentity("t-1", USER.id, touch_thread_id="t-1")
        self._persist(identity, progress_service_factory=progress, thread_service_factory=threads)
        threads.return_value.touch.assert_called_once_with("t-1")


class TestVoiceWsToken:
    """Tests for _voice_ws_token."""

    def test_voice_disabled(self) -> None:
        settings = MagicMock(voice_enabled=False)
        assert _voice_ws_token(settings, USER, "sess") == (None, None)

    def test_authenticated_user(self) -> None:
        token, new_session = _voice_ws_token(MagicMock(voice_enabled=True), USER, None)
        assert token
        assert new_session is None

    def test_returning_guest_reuses_cookie(self) -> None:
        assert _voice_ws_token(MagicMock(voice_enabled=True), None, "signed") == ("signed", None)

    def test_new_guest_gets_matching_session(self) -> None:
        token, new_session = _voice_ws_token(MagicMock(voice_enabled=True), None, None)
        assert token
        assert token == new_session


def _make_turn(**overrides: Any) -> _StreamTurn:
    fields: dict[str, Any] = {
        "message": "Hola",
        "level": "A1",
        "language": "es",
        "lesson_id": "lesson-1",
        "lesson": MagicMock(),
        "user": USER,
        "user_client": MagicMock(),
        "session_id": None,
        "identity": ChatIdentity("lesson:user-1:lesson-1:s", USER.id),
        "templates": MagicMock(),
        "lesson_service": MagicMock(),
    }
    fields.update(overrides)
    return _StreamTurn(**fields)


class TestValidateStreamInput:
    """Tests for _validate_stream_input."""

    def test_message_error_skips_lesson_lookup(self) -> None:
        service = MagicMock()
        error, lesson, _, _ = _validate_stream_input("", "A1", "es", "lesson-1", service)
        assert error == "Message cannot be empty."
        assert lesson is None
        service.get_lesson.assert_not_called()

    def test_missing_lesson(self) -> None:
        service = MagicMock()
        service.get_lesson.return_value = None
        error, _, _, _ = _validate_stream_input("Hola", "A1", "es", "nope", service)
        assert error == "Lesson not found: nope"

    def test_lesson_metadata_overrides_form_values(self) -> None:
        service = MagicMock()
        service.get_lesson.return_value.metadata.level = "A2"
        service.get_lesson.return_value.metadata.language = "fr"
        error, lesson, level, language = _validate_stream_input(
            "Hola", "Z9", "xx", "lesson-1", service
        )
        assert error is None
        assert lesson is service.get_lesson.return_value
        assert (level, language) == ("A2", "fr")

    def test_freeform_validates_form_values(self) -> None:
        error, lesson, _, _ = _validate_stream_input("Hola", "Z9", "es", None, MagicMock())
        assert error is not None
        assert error.startswith("Invalid level")
        assert lesson is None


class TestResolveStreamIdentity:
    """Tests for _resolve_stream_identity in lesson mode."""

    def test_lesson_thread_for_user(self) -> None:
        identity = _resolve_stream_identity(
            USER, None, ChatCookies(), "form-thread", "lesson-1", "sess-uuid", "es", "A1"
        )
        assert identity == ChatIdentity(
            "lesson:user-1:lesson-1:sess-uuid", USER.id, None, "form-thread"
        )


class TestLessonInputs:
    """Tests for _lesson_inputs."""

    def test_first_turn_includes_lesson_state(self) -> None:
        lesson = MagicMock()
        lesson.model_dump.return_value = {"id": "lesson-1"}
        inputs = _lesson_inputs(_make_turn(), lesson, has_checkpoint=False)
        assert inputs["lesson_data"] == {"id": "lesson-1"}
        assert inputs["lesson_phase"] == "intro"
        assert (inputs["level"], inputs["language"]) == ("A1", "es")

    def test_later_turn_only_sends_message(self) -> None:
        inputs = _lesson_inputs(_make_turn(), MagicMock(), has_checkpoint=True)
        assert set(inputs) == {"messages", "user_id"}


async def _collect(turn: _StreamTurn, state: dict[str, Any]) -> list[dict[str, str]]:
    return [event async for event in _lesson_state_events(turn, state)]


class TestLessonStateEvents:
    """Tests for _lesson_state_events."""

    async def test_progress_and_exercise_events(self) -> None:
        ui = {"phase": "practice", "exercise_result": {"correct": True}}
        events = await _collect(_make_turn(), {"lesson_ui": ui})
        assert [e["event"] for e in events] == ["lesson_progress", "exercise_result"]
        assert json.loads(events[1]["data"]) == {"correct": True}

    async def test_no_lesson_ui_emits_nothing(self) -> None:
        assert await _collect(_make_turn(), {}) == []

    async def test_completion_event_for_guest_skips_persistence(self) -> None:
        turn = _make_turn(user=None, identity=ChatIdentity("t", None))
        events = await _collect(turn, {"lesson_completed": True, "lesson_score": 7})
        assert events[0]["event"] == "lesson_complete"
        payload = json.loads(events[0]["data"])
        assert payload == {"score": 7, "vocab_count": 0, "lesson_id": "lesson-1"}
        turn.lesson_service.get_lesson_vocabulary.assert_not_called()

    async def test_completion_persist_failure_is_swallowed(self) -> None:
        turn = _make_turn()
        turn.lesson_service.get_lesson_vocabulary.side_effect = _api_error()
        state = {"lesson_completed": True, "lesson_ui": {"score": 9}}
        events = await _collect(turn, state)
        assert [e["event"] for e in events] == ["lesson_complete", "lesson_progress"]
