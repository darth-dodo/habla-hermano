"""
Review state for the spaced repetition review subgraph.

Phase 12: Conversational vocabulary review with SM-2 scheduling.

This state is designed to:
1. Track review session progress (words to review, current index, results)
2. Hold current question data (type, text, word being reviewed)
3. Store answer evaluation (quality score, feedback)
"""

from typing import NotRequired

from typing_extensions import TypedDict


class ReviewState(TypedDict):
    """State for the review session subgraph.

    Session context:
        user_id: Supabase auth user UUID or guest session UUID.
        language: Target language code (es, de, fr).
        level: CEFR level (A0, A1, A2, B1).

    Session tracking:
        words_to_review: Queue of vocabulary items to review.
        current_word_index: Index of current word in the queue.
        session_size: Number of words in this session (5, 10, or total count).

    Current question:
        current_word: The vocabulary item being reviewed.
        question_type: Type of question (translate, fill_blank, recognize).
        question_text: The formatted question text from Hermano.

    Answer evaluation:
        user_answer: The user's submitted answer.
        quality_score: SM-2 quality score (0-5) inferred from response.
        feedback_text: Hermano's personalized feedback on the answer.

    Session results:
        results: List of review outcomes [{word_id, quality, correct}].
    """

    # Session context
    user_id: str
    language: str
    level: str

    # Session tracking
    words_to_review: list[dict[str, object]]  # List of vocab items as dicts
    current_word_index: int
    session_size: int  # 5, 10, or total count

    # Current question (populated by generate_question node)
    current_word: NotRequired[dict[str, object]]
    question_type: NotRequired[str]  # translate, fill_blank, recognize
    question_text: NotRequired[str]

    # Answer evaluation (populated by evaluate_answer node)
    user_answer: NotRequired[str]
    quality_score: NotRequired[int]  # 0-5 SM-2 score
    feedback_text: NotRequired[str]

    # Session results
    results: list[dict[str, object]]  # [{word_id, quality, correct}]
