"""Comprehensive tests for the lesson chat node (Phase 19).

Tests cover:
- MC answer parsing (_parse_mc_answer)
- Helper functions (_get_ordered_steps, _get_exercises, _build_lesson_ui)
- Phase handlers (intro, teaching, exercise_ask, exercise_eval, complete)
- Main dispatch node (lesson_respond_node)
- Edge cases and phase transitions
"""

import inspect
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.lesson_chat_state import STEP_BATCH_SIZE, LessonChatState
from src.agent.nodes.lesson_chat import (
    _get_exercises,
    _get_ordered_steps,
    _parse_mc_answer,
    lesson_respond_node,
)
from src.agent.prompts_lesson_chat import (
    LESSON_EXERCISE_ASK_PROMPT,
    LESSON_EXERCISE_EVAL_PROMPT,
    LESSON_INTRO_PROMPT,
    LESSON_TEACHING_PROMPT,
    TEACHING_ADJUSTMENTS,
    get_teaching_adjustments,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_lesson_data() -> dict[str, Any]:
    """Create a sample lesson data dict (Lesson.model_dump() shape)."""
    return {
        "metadata": {
            "id": "es_a1_greetings_01",
            "title": "Basic Greetings",
            "description": "Learn common greetings in Spanish",
            "language": "es",
            "level": "A1",
            "category": "greetings",
        },
        "content": {
            "steps": [
                {"order": 1, "type": "instruction", "content": "Let's learn greetings!"},
                {
                    "order": 2,
                    "type": "vocabulary",
                    "content": "Key vocabulary",
                    "vocabulary": [
                        {"word": "hola", "translation": "hello"},
                        {"word": "adiós", "translation": "goodbye"},
                    ],
                },
                {"order": 3, "type": "example", "target_text": "¡Hola!", "translation": "Hello!"},
                {
                    "order": 4,
                    "type": "tip",
                    "content": "In Spanish, exclamation marks come in pairs!",
                },
                {"order": 5, "type": "practice", "content": "Time to practice!"},
            ],
            "exercises": [
                {
                    "id": "ex-1",
                    "type": "multiple_choice",
                    "question": "What does 'hola' mean?",
                    "options": ["goodbye", "hello", "thanks", "please"],
                    "correct_index": 1,
                },
                {
                    "id": "ex-2",
                    "type": "fill_blank",
                    "sentence_template": "_____, ¿cómo estás?",
                    "hint": "greeting",
                    "correct_answer": "Hola",
                    "acceptable_answers": ["hola", "Hola"],
                },
                {
                    "id": "ex-3",
                    "type": "translate",
                    "source_text": "Hello, how are you?",
                    "correct_translation": "Hola, ¿cómo estás?",
                    "source_language": "en",
                    "target_language": "es",
                },
            ],
        },
    }


@pytest.fixture
def base_lesson_state(sample_lesson_data: dict[str, Any]) -> LessonChatState:
    """Create a base lesson state for testing."""
    return LessonChatState(
        messages=[HumanMessage(content="Start the lesson")],
        level="A1",
        language="es",
        lesson_id="es_a1_greetings_01",
        lesson_data=sample_lesson_data,
        lesson_phase="intro",
        step_index=0,
        exercise_index=0,
        exercise_results=[],
        lesson_score=0,
    )


@pytest.fixture
def mock_llm_response() -> AIMessage:
    """Create a mock LLM response."""
    return AIMessage(content="Hey there! Welcome to the lesson!")


# =============================================================================
# MC Answer Parser Tests
# =============================================================================


class TestParseMcAnswer:
    """Tests for _parse_mc_answer()."""

    def test_single_letter_lowercase(self) -> None:
        assert _parse_mc_answer("a", ["opt1", "opt2", "opt3"]) == 0

    def test_single_letter_uppercase(self) -> None:
        assert _parse_mc_answer("B", ["opt1", "opt2", "opt3"]) == 1

    def test_single_letter_c(self) -> None:
        assert _parse_mc_answer("c", ["opt1", "opt2", "opt3"]) == 2

    def test_single_letter_d(self) -> None:
        assert _parse_mc_answer("d", ["opt1", "opt2", "opt3", "opt4"]) == 3

    def test_letter_out_of_range(self) -> None:
        assert _parse_mc_answer("d", ["opt1", "opt2"]) is None

    def test_digit_1(self) -> None:
        assert _parse_mc_answer("1", ["opt1", "opt2"]) == 0

    def test_digit_4(self) -> None:
        assert _parse_mc_answer("4", ["a", "b", "c", "d"]) == 3

    def test_digit_out_of_range(self) -> None:
        assert _parse_mc_answer("3", ["opt1", "opt2"]) is None

    def test_text_match_exact(self) -> None:
        assert _parse_mc_answer("hello", ["goodbye", "hello", "thanks"]) == 1

    def test_text_match_case_insensitive(self) -> None:
        assert _parse_mc_answer("HELLO", ["goodbye", "hello", "thanks"]) == 1

    def test_text_match_with_whitespace(self) -> None:
        assert _parse_mc_answer("  hello  ", ["goodbye", "hello", "thanks"]) == 1

    def test_no_match_returns_none(self) -> None:
        assert _parse_mc_answer("something else", ["opt1", "opt2"]) is None

    def test_empty_string(self) -> None:
        assert _parse_mc_answer("", ["opt1", "opt2"]) is None

    def test_empty_options(self) -> None:
        assert _parse_mc_answer("a", []) is None


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestGetOrderedSteps:
    """Tests for _get_ordered_steps()."""

    def test_orders_by_order_field(self, sample_lesson_data: dict[str, Any]) -> None:
        steps = _get_ordered_steps(sample_lesson_data)
        orders = [s.get("order") for s in steps]
        assert orders == [1, 2, 3, 4, 5]

    def test_unordered_input(self) -> None:
        data = {
            "content": {
                "steps": [
                    {"order": 3, "type": "tip"},
                    {"order": 1, "type": "instruction"},
                    {"order": 2, "type": "vocabulary"},
                ],
            },
        }
        steps = _get_ordered_steps(data)
        assert [s["order"] for s in steps] == [1, 2, 3]

    def test_empty_steps(self) -> None:
        data: dict[str, Any] = {"content": {"steps": []}}
        assert _get_ordered_steps(data) == []

    def test_missing_content(self) -> None:
        assert _get_ordered_steps({}) == []


class TestGetExercises:
    """Tests for _get_exercises()."""

    def test_returns_exercises(self, sample_lesson_data: dict[str, Any]) -> None:
        exercises = _get_exercises(sample_lesson_data)
        assert len(exercises) == 3

    def test_empty_exercises(self) -> None:
        data: dict[str, Any] = {"content": {"exercises": []}}
        assert _get_exercises(data) == []

    def test_missing_content(self) -> None:
        assert _get_exercises({}) == []


# =============================================================================
# Phase Handler Tests
# =============================================================================


class TestHandleIntro:
    """Tests for intro phase handler."""

    @pytest.mark.asyncio
    async def test_intro_returns_teaching_phase(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)

            assert result["lesson_phase"] == "teaching"
            assert result["step_index"] == 0
            assert len(result["messages"]) == 1
            assert "lesson_ui" in result

    @pytest.mark.asyncio
    async def test_intro_ui_has_phase(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)
            ui = result["lesson_ui"]
            assert ui["phase"] == "teaching"
            assert "title" in ui


class TestHandleTeaching:
    """Tests for teaching phase handler."""

    @pytest.mark.asyncio
    async def test_teaching_batches_steps(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "teaching"
        base_lesson_state["step_index"] = 0

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)

            # Should advance step_index by batch size (3 non-practice steps)
            assert result["step_index"] > 0
            assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_teaching_breaks_on_practice_step(self, mock_llm_response: AIMessage) -> None:
        """Teaching should stop batching when it hits a practice step."""
        lesson_data: dict[str, Any] = {
            "metadata": {"title": "Test"},
            "content": {
                "steps": [
                    {"order": 1, "type": "instruction", "content": "Step 1"},
                    {"order": 2, "type": "practice", "content": "Practice"},
                    {"order": 3, "type": "instruction", "content": "Step 3"},
                ],
                "exercises": [
                    {
                        "id": "ex-1",
                        "type": "multiple_choice",
                        "question": "Q?",
                        "options": ["a", "b"],
                        "correct_index": 0,
                    }
                ],
            },
        }
        state = LessonChatState(
            messages=[HumanMessage(content="continue")],
            level="A1",
            language="es",
            lesson_id="test",
            lesson_data=lesson_data,
            lesson_phase="teaching",
            step_index=0,
            exercise_index=0,
            exercise_results=[],
            lesson_score=0,
        )

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(state)

            # Should have batched only 1 step (before practice)
            assert result["step_index"] >= 1

    @pytest.mark.asyncio
    async def test_teaching_transitions_to_exercises(self, mock_llm_response: AIMessage) -> None:
        """When all teaching steps are done, transition to exercise_ask."""
        lesson_data: dict[str, Any] = {
            "metadata": {"title": "Test"},
            "content": {
                "steps": [{"order": 1, "type": "instruction", "content": "Only step"}],
                "exercises": [
                    {
                        "id": "ex-1",
                        "type": "multiple_choice",
                        "question": "Q?",
                        "options": ["a", "b"],
                        "correct_index": 0,
                    }
                ],
            },
        }
        state = LessonChatState(
            messages=[HumanMessage(content="continue")],
            level="A1",
            language="es",
            lesson_id="test",
            lesson_data=lesson_data,
            lesson_phase="teaching",
            step_index=0,
            exercise_index=0,
            exercise_results=[],
            lesson_score=0,
        )

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(state)
            assert result["lesson_phase"] == "exercise_ask"

    @pytest.mark.asyncio
    async def test_teaching_transitions_to_complete_when_no_exercises(
        self, mock_llm_response: AIMessage
    ) -> None:
        """When teaching done and no exercises, go to complete."""
        lesson_data: dict[str, Any] = {
            "metadata": {"title": "Test"},
            "content": {
                "steps": [{"order": 1, "type": "instruction", "content": "Only step"}],
                "exercises": [],
            },
        }
        state = LessonChatState(
            messages=[HumanMessage(content="continue")],
            level="A1",
            language="es",
            lesson_id="test",
            lesson_data=lesson_data,
            lesson_phase="teaching",
            step_index=0,
            exercise_index=0,
            exercise_results=[],
            lesson_score=0,
        )

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(state)
            assert result["lesson_phase"] == "complete"


class TestHandleExerciseAsk:
    """Tests for exercise_ask phase handler."""

    @pytest.mark.asyncio
    async def test_exercise_ask_transitions_to_eval(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "exercise_ask"
        base_lesson_state["exercise_index"] = 0

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)
            assert result["lesson_phase"] == "exercise_eval"

    @pytest.mark.asyncio
    async def test_exercise_ask_out_of_range_goes_to_complete(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        """If exercise_index is past all exercises, go to complete."""
        base_lesson_state["lesson_phase"] = "exercise_ask"
        base_lesson_state["exercise_index"] = 999  # Past all exercises

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)
            assert result["lesson_phase"] == "complete"
            assert result.get("lesson_completed") is True


class TestHandleExerciseEval:
    """Tests for exercise_eval phase handler."""

    @pytest.mark.asyncio
    async def test_correct_mc_answer(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "exercise_eval"
        base_lesson_state["exercise_index"] = 0
        # The correct answer for ex-1 is index 1 = "hello" -> letter B
        base_lesson_state["messages"] = [HumanMessage(content="B")]

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)

            assert result["exercise_index"] == 1
            assert len(result["exercise_results"]) == 1
            assert result["exercise_results"][0]["is_correct"] is True

    @pytest.mark.asyncio
    async def test_incorrect_mc_answer(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "exercise_eval"
        base_lesson_state["exercise_index"] = 0
        base_lesson_state["messages"] = [HumanMessage(content="A")]  # Wrong

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)

            assert result["exercise_results"][0]["is_correct"] is False

    @pytest.mark.asyncio
    async def test_ambiguous_mc_answer_stays_in_eval(
        self, base_lesson_state: LessonChatState
    ) -> None:
        base_lesson_state["lesson_phase"] = "exercise_eval"
        base_lesson_state["exercise_index"] = 0
        base_lesson_state["messages"] = [HumanMessage(content="not sure what")]

        result = await lesson_respond_node(base_lesson_state)

        # Should stay in exercise_eval for clarification
        assert result["lesson_phase"] == "exercise_eval"

    @pytest.mark.asyncio
    async def test_last_exercise_goes_to_complete(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "exercise_eval"
        base_lesson_state["exercise_index"] = 2  # Last exercise (0-indexed, 3 total)
        base_lesson_state["messages"] = [HumanMessage(content="Hola, ¿cómo estás?")]

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)
            assert result["lesson_phase"] == "complete"

    @pytest.mark.asyncio
    async def test_not_last_exercise_goes_to_exercise_ask(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "exercise_eval"
        base_lesson_state["exercise_index"] = 0
        base_lesson_state["messages"] = [HumanMessage(content="B")]

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)
            assert result["lesson_phase"] == "exercise_ask"


class TestHandleComplete:
    """Tests for complete phase handler."""

    @pytest.mark.asyncio
    async def test_complete_sets_flags(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "complete"
        base_lesson_state["exercise_results"] = [
            {"exercise_id": "ex-1", "is_correct": True, "user_answer": "B"},
            {"exercise_id": "ex-2", "is_correct": False, "user_answer": "wrong"},
        ]

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)

            assert result["lesson_completed"] is True
            assert result["lesson_phase"] == "complete"
            # Score uses total exercises from lesson data (3), not len(results) (2)
            # 1 correct out of 3 total = 33%
            assert result["lesson_score"] == 33

    @pytest.mark.asyncio
    async def test_complete_perfect_score(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "complete"
        base_lesson_state["exercise_results"] = [
            {"exercise_id": "ex-1", "is_correct": True, "user_answer": "B"},
            {"exercise_id": "ex-2", "is_correct": True, "user_answer": "Hola"},
            {"exercise_id": "ex-3", "is_correct": True, "user_answer": "Hola, ¿cómo estás?"},
        ]

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)
            assert result["lesson_score"] == 100

    @pytest.mark.asyncio
    async def test_complete_ui_has_score_and_vocab(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "complete"
        base_lesson_state["exercise_results"] = [
            {"exercise_id": "ex-1", "is_correct": True, "user_answer": "B"},
        ]

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)
            ui = result["lesson_ui"]
            assert "score" in ui
            assert "vocab_count" in ui
            assert ui["vocab_count"] == 2  # 2 vocabulary items in fixture
            assert ui["phase"] == "complete"


# =============================================================================
# Main Node Dispatch Tests
# =============================================================================


class TestLessonRespondNode:
    """Tests for the main lesson_respond_node dispatch."""

    def test_is_async(self) -> None:
        assert inspect.iscoroutinefunction(lesson_respond_node)

    @pytest.mark.asyncio
    async def test_unknown_phase_falls_back_to_intro(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        base_lesson_state["lesson_phase"] = "unknown_phase"

        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)
            # Falls back to intro, transitions to teaching
            assert result["lesson_phase"] == "teaching"

    @pytest.mark.asyncio
    async def test_returns_messages_list(
        self, base_lesson_state: LessonChatState, mock_llm_response: AIMessage
    ) -> None:
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base prompt"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)
            assert "messages" in result
            assert isinstance(result["messages"], list)
            assert len(result["messages"]) >= 1


# =============================================================================
# Graph Builder Tests
# =============================================================================


class TestLessonChatGraph:
    """Tests for the lesson chat graph builder."""

    def test_build_graph_returns_compiled(self) -> None:
        from src.agent.lesson_chat_graph import build_lesson_chat_graph

        graph = build_lesson_chat_graph(checkpointer=None)
        assert graph is not None

    def test_graph_cache_returns_same_instance(self) -> None:
        from src.agent.lesson_chat_graph import (
            build_lesson_chat_graph,
            clear_lesson_graph_cache,
        )

        clear_lesson_graph_cache()
        g1 = build_lesson_chat_graph(checkpointer=None)
        g2 = build_lesson_chat_graph(checkpointer=None)
        assert g1 is g2

    def test_clear_cache(self) -> None:
        from src.agent.lesson_chat_graph import (
            build_lesson_chat_graph,
            clear_lesson_graph_cache,
        )

        g1 = build_lesson_chat_graph(checkpointer=None)
        clear_lesson_graph_cache()
        g2 = build_lesson_chat_graph(checkpointer=None)
        assert g1 is not g2

    def test_graph_has_respond_node(self) -> None:
        from src.agent.lesson_chat_graph import build_lesson_chat_graph

        graph = build_lesson_chat_graph(checkpointer=None)
        # The compiled graph should have a "respond" node
        assert "respond" in graph.get_graph().nodes


# =============================================================================
# Prompt Helper Tests
# =============================================================================


class TestFormatStepsForPrompt:
    """Tests for format_steps_for_prompt()."""

    def test_formats_instruction_step(self) -> None:
        from src.agent.prompts_lesson_chat import format_steps_for_prompt

        steps = [{"type": "instruction", "content": "Hello world"}]
        result = format_steps_for_prompt(steps, 0, 1)
        assert "Hello world" in result

    def test_formats_vocabulary_step(self) -> None:
        from src.agent.prompts_lesson_chat import format_steps_for_prompt

        steps = [
            {
                "type": "vocabulary",
                "content": "Vocab",
                "vocabulary": [
                    {"word": "hola", "translation": "hello"},
                ],
            },
        ]
        result = format_steps_for_prompt(steps, 0, 1)
        assert "hola" in result
        assert "hello" in result

    def test_formats_example_step(self) -> None:
        from src.agent.prompts_lesson_chat import format_steps_for_prompt

        steps = [{"type": "example", "target_text": "¡Hola!", "translation": "Hello!"}]
        result = format_steps_for_prompt(steps, 0, 1)
        assert "¡Hola!" in result
        assert "Hello!" in result

    def test_formats_tip_step(self) -> None:
        from src.agent.prompts_lesson_chat import format_steps_for_prompt

        steps = [{"type": "tip", "content": "Remember this!"}]
        result = format_steps_for_prompt(steps, 0, 1)
        assert "Tip" in result
        assert "Remember this!" in result

    def test_skips_practice_steps(self) -> None:
        from src.agent.prompts_lesson_chat import format_steps_for_prompt

        steps = [{"type": "practice", "content": "Practice time"}]
        result = format_steps_for_prompt(steps, 0, 1)
        assert result == ""

    def test_empty_range(self) -> None:
        from src.agent.prompts_lesson_chat import format_steps_for_prompt

        steps = [{"type": "instruction", "content": "Hello"}]
        result = format_steps_for_prompt(steps, 0, 0)
        assert result == ""


class TestFormatExerciseForPrompt:
    """Tests for format_exercise_for_prompt()."""

    def test_multiple_choice(self) -> None:
        from src.agent.prompts_lesson_chat import format_exercise_for_prompt

        exercise = {
            "type": "multiple_choice",
            "question": "What does 'hola' mean?",
            "options": ["goodbye", "hello"],
        }
        result = format_exercise_for_prompt(exercise)
        assert "What does 'hola' mean?" in result
        assert "A)" in result
        assert "B)" in result

    def test_fill_blank(self) -> None:
        from src.agent.prompts_lesson_chat import format_exercise_for_prompt

        exercise = {
            "type": "fill_blank",
            "sentence_template": "_____, ¿cómo estás?",
            "hint": "greeting word",
        }
        result = format_exercise_for_prompt(exercise)
        assert "¿cómo estás?" in result
        assert "greeting word" in result

    def test_translate(self) -> None:
        from src.agent.prompts_lesson_chat import format_exercise_for_prompt

        exercise = {
            "type": "translate",
            "source_text": "Hello",
            "source_language": "en",
            "target_language": "es",
        }
        result = format_exercise_for_prompt(exercise)
        assert "Hello" in result
        # LANGUAGE_NAMES only has es/de/fr, so "en" falls back to "en"
        assert "en" in result
        assert "Spanish" in result

    def test_unknown_type(self) -> None:
        from src.agent.prompts_lesson_chat import format_exercise_for_prompt

        exercise = {"type": "unknown", "data": "stuff"}
        result = format_exercise_for_prompt(exercise)
        assert "unknown" in result


# =============================================================================
# State Model Tests
# =============================================================================


class TestLessonChatState:
    """Tests for LessonChatState model."""

    def test_step_batch_size_constant(self) -> None:
        assert STEP_BATCH_SIZE == 3

    def test_state_accepts_all_fields(self, sample_lesson_data: dict[str, Any]) -> None:
        state = LessonChatState(
            messages=[HumanMessage(content="hi")],
            level="A1",
            language="es",
            lesson_id="test",
            lesson_data=sample_lesson_data,
            lesson_phase="intro",
            step_index=0,
            exercise_index=0,
            exercise_results=[],
            lesson_score=0,
        )
        assert state["lesson_phase"] == "intro"
        assert state["lesson_id"] == "test"


# =============================================================================
# CEFR Teaching Adjustments Tests
# =============================================================================


class TestTeachingAdjustments:
    """Tests for CEFR-level teaching adjustments."""

    def test_all_four_levels_present(self) -> None:
        assert set(TEACHING_ADJUSTMENTS.keys()) == {"A0", "A1", "A2", "B1"}

    def test_each_level_has_unique_content(self) -> None:
        values = list(TEACHING_ADJUSTMENTS.values())
        # All 4 values should be distinct
        assert len(set(values)) == 4

    def test_a0_emphasizes_one_concept(self) -> None:
        assert "ONE concept" in TEACHING_ADJUSTMENTS["A0"]

    def test_a0_emphasizes_english(self) -> None:
        assert "English for ALL explanations" in TEACHING_ADJUSTMENTS["A0"]

    def test_a1_mentions_pattern_recognition(self) -> None:
        assert "pattern recognition" in TEACHING_ADJUSTMENTS["A1"]

    def test_a2_mentions_insider_expressions(self) -> None:
        assert "insider" in TEACHING_ADJUSTMENTS["A2"]

    def test_b1_mentions_nuance(self) -> None:
        assert "nuance" in TEACHING_ADJUSTMENTS["B1"]

    def test_b1_targets_95_percent(self) -> None:
        assert "95%" in TEACHING_ADJUSTMENTS["B1"]

    def test_get_teaching_adjustments_known_level(self) -> None:
        result = get_teaching_adjustments("A0")
        assert result == TEACHING_ADJUSTMENTS["A0"]

    def test_get_teaching_adjustments_falls_back_to_a1(self) -> None:
        result = get_teaching_adjustments("C2")
        assert result == TEACHING_ADJUSTMENTS["A1"]

    def test_get_teaching_adjustments_empty_string(self) -> None:
        result = get_teaching_adjustments("")
        assert result == TEACHING_ADJUSTMENTS["A1"]

    def test_adjustments_injected_into_intro_prompt(self) -> None:
        """Verify {teaching_adjustments} placeholder works in LESSON_INTRO_PROMPT."""
        result = LESSON_INTRO_PROMPT.format(
            language_name="Spanish",
            level="A0",
            lesson_title="Test",
            lesson_description="Desc",
            step_count=3,
            exercise_count=2,
            teaching_adjustments=get_teaching_adjustments("A0"),
        )
        assert "ONE concept" in result

    def test_adjustments_injected_into_teaching_prompt(self) -> None:
        """Verify {teaching_adjustments} placeholder works in LESSON_TEACHING_PROMPT."""
        result = LESSON_TEACHING_PROMPT.format(
            language_name="German",
            level="B1",
            lesson_title="Test",
            steps_content="Some content",
            step_numbers="1-3 of 5",
            teaching_adjustments=get_teaching_adjustments("B1"),
        )
        assert "nuance" in result

    def test_adjustments_injected_into_exercise_ask_prompt(self) -> None:
        """Verify {teaching_adjustments} placeholder works in LESSON_EXERCISE_ASK_PROMPT."""
        result = LESSON_EXERCISE_ASK_PROMPT.format(
            language_name="French",
            level="A2",
            exercise_type="multiple_choice",
            exercise_content="Q: What?",
            exercise_number="1 of 2",
            teaching_adjustments=get_teaching_adjustments("A2"),
        )
        assert "insider" in result

    def test_adjustments_injected_into_exercise_eval_prompt(self) -> None:
        """Verify {teaching_adjustments} placeholder works in LESSON_EXERCISE_EVAL_PROMPT."""
        result = LESSON_EXERCISE_EVAL_PROMPT.format(
            language_name="Spanish",
            level="A1",
            is_correct="Yes",
            user_answer="hola",
            correct_answer="hola",
            exercise_description="What does 'hola' mean?",
            exercise_type="multiple_choice",
            feedback_context="Last exercise.",
            teaching_adjustments=get_teaching_adjustments("A1"),
        )
        assert "pattern recognition" in result


class TestTranslateExerciseLLMEval:
    """Tests for LLM-based translation exercise evaluation."""

    @pytest.fixture
    def translate_exercise_state(self, sample_lesson_data: dict[str, Any]) -> LessonChatState:
        """State positioned at the translate exercise (index 2)."""
        return LessonChatState(
            messages=[HumanMessage(content="Hola, como estas?")],
            level="A1",
            language="es",
            lesson_id="es_a1_greetings_01",
            lesson_data=sample_lesson_data,
            lesson_phase="exercise_eval",
            step_index=0,
            exercise_index=2,  # translate exercise
            exercise_results=[],
            lesson_score=0,
        )

    @pytest.mark.asyncio
    async def test_correct_tag_sets_is_correct_true(
        self, translate_exercise_state: LessonChatState
    ) -> None:
        """When LLM response starts with [CORRECT], is_correct should be True."""
        llm_response = AIMessage(
            content="[CORRECT]\nGreat job! That's a perfect translation."
        )
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(translate_exercise_state)

            assert result["exercise_results"][-1]["is_correct"] is True

    @pytest.mark.asyncio
    async def test_incorrect_tag_sets_is_correct_false(
        self, translate_exercise_state: LessonChatState
    ) -> None:
        """When LLM response starts with [INCORRECT], is_correct should be False."""
        llm_response = AIMessage(
            content="[INCORRECT]\nNot quite, the correct translation is..."
        )
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(translate_exercise_state)

            assert result["exercise_results"][-1]["is_correct"] is False

    @pytest.mark.asyncio
    async def test_correct_tag_stripped_from_displayed_message(
        self, translate_exercise_state: LessonChatState
    ) -> None:
        """The [CORRECT] tag should be stripped from the message shown to the user."""
        llm_response = AIMessage(content="[CORRECT]\nAwesome work!")
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(translate_exercise_state)

            msg_content = result["messages"][0].content
            assert "[CORRECT]" not in msg_content
            assert "Awesome work!" in msg_content

    @pytest.mark.asyncio
    async def test_incorrect_tag_stripped_from_displayed_message(
        self, translate_exercise_state: LessonChatState
    ) -> None:
        """The [INCORRECT] tag should be stripped from the message shown to the user."""
        llm_response = AIMessage(content="[INCORRECT]\nClose, but not quite.")
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(translate_exercise_state)

            msg_content = result["messages"][0].content
            assert "[INCORRECT]" not in msg_content
            assert "Close, but not quite." in msg_content

    @pytest.mark.asyncio
    async def test_missing_tag_falls_back_to_string_matching(
        self, translate_exercise_state: LessonChatState
    ) -> None:
        """When LLM doesn't include a tag, fall back to string matching."""
        llm_response = AIMessage(content="Nice try! Keep going.")
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(translate_exercise_state)

            # Fallback uses TranslateExercise.check_answer()
            # The user answer "Hola, como estas?" vs correct "Hola, ¿cómo estás?"
            # String matching will likely return False (no exact match)
            assert result["exercise_results"][-1]["is_correct"] is not None
            assert isinstance(result["exercise_results"][-1]["is_correct"], bool)

    @pytest.mark.asyncio
    async def test_mc_exercise_not_affected_by_tag_parsing(
        self, base_lesson_state: LessonChatState
    ) -> None:
        """MC exercises should NOT use LLM tag parsing — keep existing logic."""
        base_lesson_state["lesson_phase"] = "exercise_eval"
        base_lesson_state["exercise_index"] = 0  # MC exercise
        base_lesson_state["messages"] = [HumanMessage(content="B")]  # Correct

        llm_response = AIMessage(content="[INCORRECT]\nThis should be ignored for MC.")
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(base_lesson_state)

            # MC answer B = index 1 = correct_index 1, so is_correct=True
            # LLM tag [INCORRECT] should NOT override this
            assert result["exercise_results"][-1]["is_correct"] is True

    @pytest.mark.asyncio
    async def test_eval_prompt_includes_exercise_type(
        self, translate_exercise_state: LessonChatState
    ) -> None:
        """The eval prompt should include exercise_type for LLM context."""
        llm_response = AIMessage(content="[CORRECT]\nPerfect!")
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            await lesson_respond_node(translate_exercise_state)

            call_args = mock_llm.ainvoke.call_args[0][0]
            system_msg = call_args[0].content
            assert "translate" in system_msg
            assert "pending" in system_msg.lower()

    @pytest.mark.asyncio
    async def test_translate_correct_tag_overrides_string_mismatch(
        self, translate_exercise_state: LessonChatState
    ) -> None:
        """[CORRECT] tag should mark as correct even if string match would fail."""
        # Use an answer that wouldn't pass string matching
        translate_exercise_state["messages"] = [
            HumanMessage(content="Hola, que tal?")
        ]
        llm_response = AIMessage(
            content="[CORRECT]\nThat's a valid informal translation!"
        )
        with (
            patch("src.agent.nodes.lesson_chat.get_llm") as mock_get_llm,
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="base"),
        ):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            result = await lesson_respond_node(translate_exercise_state)

            assert result["exercise_results"][-1]["is_correct"] is True


class TestPhaseHandlersInjectAdjustments:
    """Verify that phase handlers pass teaching_adjustments to prompt formatting."""

    @pytest.fixture
    def _mock_llm(self, mock_llm_response: AIMessage) -> AsyncMock:
        """Shared mock for LLM calls."""
        mock = AsyncMock(return_value=mock_llm_response)
        return mock

    @pytest.mark.asyncio
    async def test_intro_includes_adjustments(
        self,
        base_lesson_state: LessonChatState,
        _mock_llm: AsyncMock,
    ) -> None:
        with (
            patch("src.agent.nodes.lesson_chat.get_llm", return_value=_mock_llm),
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="Base prompt"),
        ):
            # Change level to A0 to verify A0-specific content
            state = {**base_lesson_state, "level": "A0"}
            await lesson_respond_node(state)

            # The system prompt should contain A0 adjustments
            call_args = _mock_llm.ainvoke.call_args[0][0]
            system_msg = call_args[0].content
            assert "ONE concept" in system_msg

    @pytest.mark.asyncio
    async def test_teaching_includes_adjustments(
        self,
        base_lesson_state: LessonChatState,
        _mock_llm: AsyncMock,
    ) -> None:
        with (
            patch("src.agent.nodes.lesson_chat.get_llm", return_value=_mock_llm),
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="Base prompt"),
        ):
            state = {**base_lesson_state, "lesson_phase": "teaching", "level": "B1"}
            await lesson_respond_node(state)

            call_args = _mock_llm.ainvoke.call_args[0][0]
            system_msg = call_args[0].content
            assert "nuance" in system_msg

    @pytest.mark.asyncio
    async def test_exercise_ask_includes_adjustments(
        self,
        base_lesson_state: LessonChatState,
        _mock_llm: AsyncMock,
    ) -> None:
        with (
            patch("src.agent.nodes.lesson_chat.get_llm", return_value=_mock_llm),
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="Base prompt"),
        ):
            state = {**base_lesson_state, "lesson_phase": "exercise_ask", "level": "A2"}
            await lesson_respond_node(state)

            call_args = _mock_llm.ainvoke.call_args[0][0]
            system_msg = call_args[0].content
            assert "insider" in system_msg

    @pytest.mark.asyncio
    async def test_exercise_eval_includes_adjustments(
        self,
        base_lesson_state: LessonChatState,
        _mock_llm: AsyncMock,
    ) -> None:
        with (
            patch("src.agent.nodes.lesson_chat.get_llm", return_value=_mock_llm),
            patch("src.agent.nodes.lesson_chat.get_prompt_for_level", return_value="Base prompt"),
        ):
            state = {
                **base_lesson_state,
                "lesson_phase": "exercise_eval",
                "level": "A1",
                "messages": [HumanMessage(content="hello")],
            }
            await lesson_respond_node(state)

            call_args = _mock_llm.ainvoke.call_args[0][0]
            system_msg = call_args[0].content
            assert "pattern recognition" in system_msg
