"""
Tests for ReviewState TypedDict and review subgraph structures.

This module tests:
1. ReviewState TypedDict structure, fields, and types
2. Review subgraph compilation and node connectivity
3. Answer evaluation subgraph compilation and node connectivity
4. Pre-compiled graph instances
5. ConversationState extensions for spaced repetition (Phase 12)
"""

from typing import ClassVar, get_type_hints

import pytest
from langgraph.graph.state import CompiledStateGraph

from src.agent.review_graph import (
    answer_evaluation_graph,
    build_answer_evaluation_graph,
    build_review_subgraph,
    review_subgraph,
)
from src.agent.review_state import ReviewState
from src.agent.state import (
    ConversationState,
    ReviewWordOffered,
    ReviewWordUsed,
)

# ---------------------------------------------------------------------------
# 1. ReviewState TypedDict Structure
# ---------------------------------------------------------------------------


class TestReviewStateRequiredFields:
    """Tests for ReviewState required fields."""

    REQUIRED_FIELDS: ClassVar[list[str]] = [
        "user_id",
        "language",
        "level",
        "words_to_review",
        "current_word_index",
        "session_size",
        "results",
    ]

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_has_required_field(self, field: str) -> None:
        """ReviewState should have each required field."""
        hints = get_type_hints(ReviewState, include_extras=True)
        assert field in hints, f"Missing required field: {field}"

    def test_has_exactly_seven_required_fields(self) -> None:
        """ReviewState should have exactly 7 required fields.

        Required: user_id, language, level, words_to_review,
        current_word_index, session_size, results.
        """
        required = ReviewState.__required_keys__
        assert len(required) == 7

    def test_required_keys_match_expected(self) -> None:
        """ReviewState required keys should match the expected set."""
        expected = {
            "user_id",
            "language",
            "level",
            "words_to_review",
            "current_word_index",
            "session_size",
            "results",
        }
        assert ReviewState.__required_keys__ == expected


class TestReviewStateOptionalFields:
    """Tests for ReviewState optional (NotRequired) fields."""

    OPTIONAL_FIELDS: ClassVar[list[str]] = [
        "current_word",
        "question_type",
        "question_text",
        "user_answer",
        "quality_score",
        "feedback_text",
    ]

    @pytest.mark.parametrize("field", OPTIONAL_FIELDS)
    def test_has_optional_field(self, field: str) -> None:
        """ReviewState should have each optional field."""
        hints = get_type_hints(ReviewState, include_extras=True)
        assert field in hints, f"Missing optional field: {field}"

    def test_has_exactly_seven_optional_fields(self) -> None:
        """ReviewState should have exactly 7 optional fields.

        Optional: current_word, question_type, question_text,
        user_answer, quality_score, feedback_text, supabase_client.
        """
        optional = ReviewState.__optional_keys__
        assert len(optional) == 7

    def test_optional_keys_match_expected(self) -> None:
        """ReviewState optional keys should match the expected set."""
        expected = {
            "current_word",
            "question_type",
            "question_text",
            "user_answer",
            "quality_score",
            "feedback_text",
            "supabase_client",
        }
        assert ReviewState.__optional_keys__ == expected


class TestReviewStateTotalFields:
    """Tests for total field count in ReviewState."""

    def test_has_exactly_fourteen_fields(self) -> None:
        """ReviewState should have exactly 14 fields (7 required + 7 optional)."""
        hints = get_type_hints(ReviewState, include_extras=True)
        assert len(hints) == 14


class TestReviewStateFieldTypes:
    """Tests for ReviewState field type correctness."""

    def test_user_id_is_str(self) -> None:
        """user_id should be typed as str."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["user_id"] is str

    def test_language_is_str(self) -> None:
        """language should be typed as str."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["language"] is str

    def test_level_is_str(self) -> None:
        """level should be typed as str."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["level"] is str

    def test_words_to_review_is_list_of_dicts(self) -> None:
        """words_to_review should be typed as list[dict[str, object]]."""
        hints = get_type_hints(ReviewState, include_extras=False)
        field_type = hints["words_to_review"]
        assert hasattr(field_type, "__origin__")
        assert field_type.__origin__ is list

    def test_current_word_index_is_int(self) -> None:
        """current_word_index should be typed as int."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["current_word_index"] is int

    def test_session_size_is_int(self) -> None:
        """session_size should be typed as int."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["session_size"] is int

    def test_results_is_list_of_dicts(self) -> None:
        """results should be typed as list[dict[str, object]]."""
        hints = get_type_hints(ReviewState, include_extras=False)
        field_type = hints["results"]
        assert hasattr(field_type, "__origin__")
        assert field_type.__origin__ is list

    def test_current_word_is_dict(self) -> None:
        """current_word should be typed as dict[str, object]."""
        hints = get_type_hints(ReviewState, include_extras=False)
        field_type = hints["current_word"]
        assert hasattr(field_type, "__origin__")
        assert field_type.__origin__ is dict

    def test_question_type_is_str(self) -> None:
        """question_type should be typed as str."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["question_type"] is str

    def test_question_text_is_str(self) -> None:
        """question_text should be typed as str."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["question_text"] is str

    def test_user_answer_is_str(self) -> None:
        """user_answer should be typed as str."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["user_answer"] is str

    def test_quality_score_is_int(self) -> None:
        """quality_score should be typed as int."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["quality_score"] is int

    def test_feedback_text_is_str(self) -> None:
        """feedback_text should be typed as str."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints["feedback_text"] is str

    @pytest.mark.parametrize(
        "field,expected_type",
        [
            ("user_id", str),
            ("language", str),
            ("level", str),
            ("current_word_index", int),
            ("session_size", int),
            ("question_type", str),
            ("question_text", str),
            ("user_answer", str),
            ("quality_score", int),
            ("feedback_text", str),
        ],
    )
    def test_scalar_field_types(self, field: str, expected_type: type) -> None:
        """Scalar fields should have the expected primitive type."""
        hints = get_type_hints(ReviewState, include_extras=False)
        assert hints[field] is expected_type, (
            f"Field {field} expected {expected_type}, got {hints[field]}"
        )


# ---------------------------------------------------------------------------
# 2. ReviewState Instantiation
# ---------------------------------------------------------------------------


class TestReviewStateCreation:
    """Tests for creating ReviewState instances."""

    @pytest.fixture
    def required_only_state(self) -> ReviewState:
        """Return a ReviewState with only required fields."""
        return ReviewState(
            user_id="test-uuid-1234",
            language="es",
            level="A1",
            words_to_review=[
                {"id": 1, "word": "hola", "translation": "hello"},
                {"id": 2, "word": "adios", "translation": "goodbye"},
            ],
            current_word_index=0,
            session_size=2,
            results=[],
        )

    @pytest.fixture
    def full_state(self) -> ReviewState:
        """Return a ReviewState with all fields populated."""
        return ReviewState(
            user_id="test-uuid-5678",
            language="de",
            level="A2",
            words_to_review=[{"id": 10, "word": "danke", "translation": "thank you"}],
            current_word_index=0,
            session_size=1,
            results=[],
            current_word={"id": 10, "word": "danke", "translation": "thank you"},
            question_type="translate",
            question_text="How do you say 'thank you' in German?",
            user_answer="danke",
            quality_score=5,
            feedback_text="Perfect! You nailed it.",
        )

    def test_instantiate_with_required_fields_only(self, required_only_state: ReviewState) -> None:
        """Should be able to create ReviewState with only required fields."""
        assert required_only_state["user_id"] == "test-uuid-1234"
        assert required_only_state["language"] == "es"
        assert required_only_state["level"] == "A1"
        assert len(required_only_state["words_to_review"]) == 2
        assert required_only_state["current_word_index"] == 0
        assert required_only_state["session_size"] == 2
        assert required_only_state["results"] == []

    def test_instantiate_with_all_fields(self, full_state: ReviewState) -> None:
        """Should be able to create ReviewState with all fields."""
        assert full_state["user_id"] == "test-uuid-5678"
        assert full_state["language"] == "de"
        assert full_state["level"] == "A2"
        assert full_state["current_word"]["word"] == "danke"
        assert full_state["question_type"] == "translate"
        assert full_state["question_text"] == "How do you say 'thank you' in German?"
        assert full_state["user_answer"] == "danke"
        assert full_state["quality_score"] == 5
        assert full_state["feedback_text"] == "Perfect! You nailed it."

    def test_required_state_has_no_optional_fields(self, required_only_state: ReviewState) -> None:
        """A required-only state should not contain optional keys."""
        assert "current_word" not in required_only_state
        assert "question_type" not in required_only_state
        assert "question_text" not in required_only_state
        assert "user_answer" not in required_only_state
        assert "quality_score" not in required_only_state
        assert "feedback_text" not in required_only_state

    def test_state_is_dictionary_like(self, required_only_state: ReviewState) -> None:
        """ReviewState should behave like a dictionary."""
        assert "user_id" in required_only_state
        assert "language" in required_only_state
        assert len(required_only_state) == 7  # Only required keys populated

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_create_state_with_valid_levels(self, level: str) -> None:
        """Should be able to create ReviewState with all valid CEFR levels."""
        state: ReviewState = {
            "user_id": "u1",
            "language": "es",
            "level": level,
            "words_to_review": [],
            "current_word_index": 0,
            "session_size": 0,
            "results": [],
        }
        assert state["level"] == level

    @pytest.mark.parametrize("language", ["es", "de", "fr"])
    def test_create_state_with_valid_languages(self, language: str) -> None:
        """Should be able to create ReviewState with all supported languages."""
        state: ReviewState = {
            "user_id": "u1",
            "language": language,
            "level": "A1",
            "words_to_review": [],
            "current_word_index": 0,
            "session_size": 0,
            "results": [],
        }
        assert state["language"] == language

    @pytest.mark.parametrize("session_size", [5, 10, 25])
    def test_create_state_with_valid_session_sizes(self, session_size: int) -> None:
        """Should be able to create ReviewState with typical session sizes."""
        state: ReviewState = {
            "user_id": "u1",
            "language": "es",
            "level": "A1",
            "words_to_review": [],
            "current_word_index": 0,
            "session_size": session_size,
            "results": [],
        }
        assert state["session_size"] == session_size


class TestReviewStateEdgeCases:
    """Edge case tests for ReviewState."""

    def test_state_with_empty_word_list(self) -> None:
        """ReviewState should accept an empty words_to_review list."""
        state: ReviewState = {
            "user_id": "u1",
            "language": "es",
            "level": "A1",
            "words_to_review": [],
            "current_word_index": 0,
            "session_size": 0,
            "results": [],
        }
        assert state["words_to_review"] == []

    def test_state_with_results_populated(self) -> None:
        """ReviewState should hold result dicts from completed reviews."""
        state: ReviewState = {
            "user_id": "u1",
            "language": "es",
            "level": "A1",
            "words_to_review": [],
            "current_word_index": 2,
            "session_size": 2,
            "results": [
                {"word_id": 1, "quality": 5, "correct": True},
                {"word_id": 2, "quality": 2, "correct": False},
            ],
        }
        assert len(state["results"]) == 2
        assert state["results"][0]["quality"] == 5
        assert state["results"][1]["correct"] is False

    def test_state_with_empty_strings(self) -> None:
        """ReviewState should accept empty strings (TypedDict has no runtime validation)."""
        state: ReviewState = {
            "user_id": "",
            "language": "",
            "level": "",
            "words_to_review": [],
            "current_word_index": 0,
            "session_size": 0,
            "results": [],
        }
        assert state["user_id"] == ""

    @pytest.mark.parametrize("question_type", ["translate", "fill_blank", "recognize"])
    def test_state_with_valid_question_types(self, question_type: str) -> None:
        """ReviewState should accept all valid question type strings."""
        state: ReviewState = {
            "user_id": "u1",
            "language": "es",
            "level": "A1",
            "words_to_review": [],
            "current_word_index": 0,
            "session_size": 0,
            "results": [],
            "question_type": question_type,
        }
        assert state["question_type"] == question_type

    @pytest.mark.parametrize("quality", [0, 1, 2, 3, 4, 5])
    def test_state_with_valid_quality_scores(self, quality: int) -> None:
        """ReviewState should accept SM-2 quality scores in range 0-5."""
        state: ReviewState = {
            "user_id": "u1",
            "language": "es",
            "level": "A1",
            "words_to_review": [],
            "current_word_index": 0,
            "session_size": 0,
            "results": [],
            "quality_score": quality,
        }
        assert state["quality_score"] == quality


# ---------------------------------------------------------------------------
# 3. build_review_subgraph()
# ---------------------------------------------------------------------------


class TestBuildReviewSubgraph:
    """Tests for the build_review_subgraph function."""

    def test_returns_compiled_state_graph(self) -> None:
        """build_review_subgraph should return a CompiledStateGraph."""
        graph = build_review_subgraph()
        assert isinstance(graph, CompiledStateGraph)

    def test_compiles_without_error(self) -> None:
        """build_review_subgraph should compile without raising exceptions."""
        try:
            graph = build_review_subgraph()
            assert graph is not None
        except Exception as e:
            pytest.fail(f"Review subgraph compilation failed with: {e}")

    def test_has_generate_question_node(self) -> None:
        """Review subgraph should have a 'generate_question' node."""
        graph = build_review_subgraph()
        assert "generate_question" in graph.nodes

    def test_has_start_node(self) -> None:
        """Review subgraph should have a '__start__' entry point node."""
        graph = build_review_subgraph()
        assert "__start__" in graph.nodes

    def test_has_expected_processing_nodes(self) -> None:
        """Review subgraph should have only generate_question as a processing node."""
        graph = build_review_subgraph()
        processing_nodes = [n for n in graph.nodes if not n.startswith("__")]
        assert processing_nodes == ["generate_question"]

    def test_callable_multiple_times(self) -> None:
        """build_review_subgraph should be callable multiple times without side effects."""
        g1 = build_review_subgraph()
        g2 = build_review_subgraph()
        assert isinstance(g1, CompiledStateGraph)
        assert isinstance(g2, CompiledStateGraph)
        assert g1 is not g2

    def test_has_invoke_method(self) -> None:
        """Compiled review subgraph should have an invoke method."""
        graph = build_review_subgraph()
        assert hasattr(graph, "invoke")
        assert callable(graph.invoke)

    def test_has_ainvoke_method(self) -> None:
        """Compiled review subgraph should have an ainvoke method for async."""
        graph = build_review_subgraph()
        assert hasattr(graph, "ainvoke")
        assert callable(graph.ainvoke)

    def test_has_stream_method(self) -> None:
        """Compiled review subgraph should have a stream method."""
        graph = build_review_subgraph()
        assert hasattr(graph, "stream")
        assert callable(graph.stream)


# ---------------------------------------------------------------------------
# 4. build_answer_evaluation_graph()
# ---------------------------------------------------------------------------


class TestBuildAnswerEvaluationGraph:
    """Tests for the build_answer_evaluation_graph function."""

    def test_returns_compiled_state_graph(self) -> None:
        """build_answer_evaluation_graph should return a CompiledStateGraph."""
        graph = build_answer_evaluation_graph()
        assert isinstance(graph, CompiledStateGraph)

    def test_compiles_without_error(self) -> None:
        """build_answer_evaluation_graph should compile without raising exceptions."""
        try:
            graph = build_answer_evaluation_graph()
            assert graph is not None
        except Exception as e:
            pytest.fail(f"Answer evaluation graph compilation failed with: {e}")

    def test_has_evaluate_answer_node(self) -> None:
        """Answer evaluation graph should have an 'evaluate_answer' node."""
        graph = build_answer_evaluation_graph()
        assert "evaluate_answer" in graph.nodes

    def test_has_update_sm2_node(self) -> None:
        """Answer evaluation graph should have an 'update_sm2' node."""
        graph = build_answer_evaluation_graph()
        assert "update_sm2" in graph.nodes

    def test_has_start_node(self) -> None:
        """Answer evaluation graph should have a '__start__' entry point node."""
        graph = build_answer_evaluation_graph()
        assert "__start__" in graph.nodes

    def test_has_expected_processing_nodes(self) -> None:
        """Answer evaluation graph should have evaluate_answer and update_sm2 as processing nodes."""
        graph = build_answer_evaluation_graph()
        processing_nodes = sorted([n for n in graph.nodes if not n.startswith("__")])
        assert processing_nodes == ["evaluate_answer", "update_sm2"]

    def test_callable_multiple_times(self) -> None:
        """build_answer_evaluation_graph should be callable multiple times."""
        g1 = build_answer_evaluation_graph()
        g2 = build_answer_evaluation_graph()
        assert isinstance(g1, CompiledStateGraph)
        assert isinstance(g2, CompiledStateGraph)
        assert g1 is not g2

    def test_has_invoke_method(self) -> None:
        """Compiled answer evaluation graph should have an invoke method."""
        graph = build_answer_evaluation_graph()
        assert hasattr(graph, "invoke")
        assert callable(graph.invoke)

    def test_has_ainvoke_method(self) -> None:
        """Compiled answer evaluation graph should have an ainvoke method for async."""
        graph = build_answer_evaluation_graph()
        assert hasattr(graph, "ainvoke")
        assert callable(graph.ainvoke)


# ---------------------------------------------------------------------------
# 5. Pre-compiled graph instances
# ---------------------------------------------------------------------------


class TestPreCompiledInstances:
    """Tests for module-level pre-compiled graph instances."""

    def test_review_subgraph_is_not_none(self) -> None:
        """Pre-compiled review_subgraph should not be None."""
        assert review_subgraph is not None

    def test_review_subgraph_is_compiled_state_graph(self) -> None:
        """Pre-compiled review_subgraph should be a CompiledStateGraph."""
        assert isinstance(review_subgraph, CompiledStateGraph)

    def test_answer_evaluation_graph_is_not_none(self) -> None:
        """Pre-compiled answer_evaluation_graph should not be None."""
        assert answer_evaluation_graph is not None

    def test_answer_evaluation_graph_is_compiled_state_graph(self) -> None:
        """Pre-compiled answer_evaluation_graph should be a CompiledStateGraph."""
        assert isinstance(answer_evaluation_graph, CompiledStateGraph)

    def test_review_subgraph_matches_builder(self) -> None:
        """Pre-compiled review_subgraph should have same nodes as build_review_subgraph()."""
        fresh = build_review_subgraph()
        assert set(review_subgraph.nodes) == set(fresh.nodes)

    def test_answer_evaluation_graph_matches_builder(self) -> None:
        """Pre-compiled answer_evaluation_graph should have same nodes as build_answer_evaluation_graph()."""
        fresh = build_answer_evaluation_graph()
        assert set(answer_evaluation_graph.nodes) == set(fresh.nodes)


# ---------------------------------------------------------------------------
# 6. ConversationState extensions for Phase 12
# ---------------------------------------------------------------------------


class TestReviewWordOfferedTypedDict:
    """Tests for ReviewWordOffered TypedDict structure."""

    def test_exists_and_importable(self) -> None:
        """ReviewWordOffered should be importable from state module."""
        assert ReviewWordOffered is not None

    def test_has_vocab_id_field(self) -> None:
        """ReviewWordOffered should have a vocab_id field."""
        hints = get_type_hints(ReviewWordOffered, include_extras=True)
        assert "vocab_id" in hints

    def test_has_word_field(self) -> None:
        """ReviewWordOffered should have a word field."""
        hints = get_type_hints(ReviewWordOffered, include_extras=True)
        assert "word" in hints

    def test_has_translation_field(self) -> None:
        """ReviewWordOffered should have a translation field."""
        hints = get_type_hints(ReviewWordOffered, include_extras=True)
        assert "translation" in hints

    def test_has_exactly_three_fields(self) -> None:
        """ReviewWordOffered should have exactly 3 fields: vocab_id, word, translation."""
        hints = get_type_hints(ReviewWordOffered, include_extras=True)
        assert len(hints) == 3

    def test_vocab_id_is_int(self) -> None:
        """ReviewWordOffered vocab_id should be typed as int."""
        hints = get_type_hints(ReviewWordOffered, include_extras=False)
        assert hints["vocab_id"] is int

    def test_word_is_str(self) -> None:
        """ReviewWordOffered word should be typed as str."""
        hints = get_type_hints(ReviewWordOffered, include_extras=False)
        assert hints["word"] is str

    def test_translation_is_str(self) -> None:
        """ReviewWordOffered translation should be typed as str."""
        hints = get_type_hints(ReviewWordOffered, include_extras=False)
        assert hints["translation"] is str

    def test_can_instantiate(self) -> None:
        """Should be able to create a ReviewWordOffered instance."""
        offered: ReviewWordOffered = {
            "vocab_id": 42,
            "word": "gato",
            "translation": "cat",
        }
        assert offered["vocab_id"] == 42
        assert offered["word"] == "gato"
        assert offered["translation"] == "cat"


class TestReviewWordUsedTypedDict:
    """Tests for ReviewWordUsed TypedDict structure."""

    def test_exists_and_importable(self) -> None:
        """ReviewWordUsed should be importable from state module."""
        assert ReviewWordUsed is not None

    def test_has_vocab_id_field(self) -> None:
        """ReviewWordUsed should have a vocab_id field."""
        hints = get_type_hints(ReviewWordUsed, include_extras=True)
        assert "vocab_id" in hints

    def test_has_word_field(self) -> None:
        """ReviewWordUsed should have a word field."""
        hints = get_type_hints(ReviewWordUsed, include_extras=True)
        assert "word" in hints

    def test_has_quality_field(self) -> None:
        """ReviewWordUsed should have a quality field."""
        hints = get_type_hints(ReviewWordUsed, include_extras=True)
        assert "quality" in hints

    def test_has_exactly_three_fields(self) -> None:
        """ReviewWordUsed should have exactly 3 fields: vocab_id, word, quality."""
        hints = get_type_hints(ReviewWordUsed, include_extras=True)
        assert len(hints) == 3

    def test_vocab_id_is_int(self) -> None:
        """ReviewWordUsed vocab_id should be typed as int."""
        hints = get_type_hints(ReviewWordUsed, include_extras=False)
        assert hints["vocab_id"] is int

    def test_word_is_str(self) -> None:
        """ReviewWordUsed word should be typed as str."""
        hints = get_type_hints(ReviewWordUsed, include_extras=False)
        assert hints["word"] is str

    def test_quality_is_int(self) -> None:
        """ReviewWordUsed quality should be typed as int."""
        hints = get_type_hints(ReviewWordUsed, include_extras=False)
        assert hints["quality"] is int

    def test_can_instantiate(self) -> None:
        """Should be able to create a ReviewWordUsed instance."""
        used: ReviewWordUsed = {
            "vocab_id": 42,
            "word": "gato",
            "quality": 5,
        }
        assert used["vocab_id"] == 42
        assert used["word"] == "gato"
        assert used["quality"] == 5

    @pytest.mark.parametrize("quality", [4, 5])
    def test_valid_quality_for_correct_usage(self, quality: int) -> None:
        """ReviewWordUsed quality should accept 4-5 for correct context usage."""
        used: ReviewWordUsed = {
            "vocab_id": 1,
            "word": "hola",
            "quality": quality,
        }
        assert used["quality"] == quality


class TestConversationStateReviewExtensions:
    """Tests for Phase 12 review extensions to ConversationState."""

    def test_has_review_words_offered_field(self) -> None:
        """ConversationState should have a review_words_offered field (Phase 12)."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert "review_words_offered" in hints

    def test_has_review_words_used_field(self) -> None:
        """ConversationState should have a review_words_used field (Phase 12)."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert "review_words_used" in hints

    def test_has_user_id_field(self) -> None:
        """ConversationState should have a user_id field (Phase 12)."""
        hints = get_type_hints(ConversationState, include_extras=True)
        assert "user_id" in hints

    def test_review_words_offered_is_optional(self) -> None:
        """review_words_offered should be a NotRequired field."""
        assert "review_words_offered" in ConversationState.__optional_keys__

    def test_review_words_used_is_optional(self) -> None:
        """review_words_used should be a NotRequired field."""
        assert "review_words_used" in ConversationState.__optional_keys__

    def test_user_id_is_optional(self) -> None:
        """user_id should be a NotRequired field."""
        assert "user_id" in ConversationState.__optional_keys__


# ---------------------------------------------------------------------------
# 7. Graph documentation
# ---------------------------------------------------------------------------


class TestGraphDocumentation:
    """Tests for review graph module documentation."""

    def test_build_review_subgraph_has_docstring(self) -> None:
        """build_review_subgraph should have a docstring."""
        assert build_review_subgraph.__doc__ is not None
        assert len(build_review_subgraph.__doc__) > 0

    def test_build_answer_evaluation_graph_has_docstring(self) -> None:
        """build_answer_evaluation_graph should have a docstring."""
        assert build_answer_evaluation_graph.__doc__ is not None
        assert len(build_answer_evaluation_graph.__doc__) > 0

    def test_review_subgraph_docstring_mentions_generate_question(self) -> None:
        """build_review_subgraph docstring should reference generate_question."""
        assert "generate_question" in build_review_subgraph.__doc__

    def test_evaluation_graph_docstring_mentions_evaluate_answer(self) -> None:
        """build_answer_evaluation_graph docstring should reference evaluate_answer."""
        assert "evaluate_answer" in build_answer_evaluation_graph.__doc__

    def test_evaluation_graph_docstring_mentions_sm2(self) -> None:
        """build_answer_evaluation_graph docstring should reference SM-2."""
        assert "SM-2" in build_answer_evaluation_graph.__doc__


# ---------------------------------------------------------------------------
# 8. Node imports
# ---------------------------------------------------------------------------


class TestReviewNodeImports:
    """Tests for proper node imports in review graph module."""

    def test_generate_question_node_is_importable(self) -> None:
        """generate_question_node should be importable from review nodes."""
        from src.agent.nodes.review import generate_question_node

        assert generate_question_node is not None
        assert callable(generate_question_node)

    def test_evaluate_answer_node_is_importable(self) -> None:
        """evaluate_answer_node should be importable from review nodes."""
        from src.agent.nodes.review import evaluate_answer_node

        assert evaluate_answer_node is not None
        assert callable(evaluate_answer_node)

    def test_update_sm2_node_is_importable(self) -> None:
        """update_sm2_node should be importable from review nodes."""
        from src.agent.nodes.review import update_sm2_node

        assert update_sm2_node is not None
        assert callable(update_sm2_node)

    def test_generate_question_node_is_async(self) -> None:
        """generate_question_node should be an async function."""
        import inspect

        from src.agent.nodes.review import generate_question_node

        assert inspect.iscoroutinefunction(generate_question_node)

    def test_evaluate_answer_node_is_async(self) -> None:
        """evaluate_answer_node should be an async function."""
        import inspect

        from src.agent.nodes.review import evaluate_answer_node

        assert inspect.iscoroutinefunction(evaluate_answer_node)

    def test_update_sm2_node_is_async(self) -> None:
        """update_sm2_node should be an async function."""
        import inspect

        from src.agent.nodes.review import update_sm2_node

        assert inspect.iscoroutinefunction(update_sm2_node)
