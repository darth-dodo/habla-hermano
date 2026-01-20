"""Vocabulary extraction and management service."""

from dataclasses import dataclass

from src.db.repository import VocabularyRepository


@dataclass(frozen=True)
class ExtractedWord:
    """A word extracted from conversation with metadata."""

    word: str
    translation: str
    part_of_speech: str | None
    context: str


@dataclass(frozen=True)
class VocabularyStats:
    """Statistics about vocabulary learning progress."""

    total_words: int
    words_by_part_of_speech: dict[str, int]
    most_seen: list[tuple[str, int]]
    recently_learned: list[str]


class VocabularyService:
    """Service for vocabulary extraction and tracking."""

    def __init__(self, user_id: str) -> None:
        """Initialize vocabulary service for a user.

        Args:
            user_id: Supabase auth user UUID.
        """
        self._user_id = user_id
        self._repo = VocabularyRepository(user_id)

    def extract_vocabulary(
        self,
        text: str,  # noqa: ARG002
        language: str,  # noqa: ARG002
        level: str,  # noqa: ARG002
    ) -> list[ExtractedWord]:
        """
        Extract notable vocabulary from text based on learner level.

        This is a stub implementation. In production, this would use
        LLM analysis to identify words appropriate for the learner's level.

        Args:
            text: The text to extract vocabulary from
            language: Target language code (es, de)
            level: CEFR level (A0, A1, A2, B1)

        Returns:
            List of extracted words with translations and metadata
        """
        return []

    def save_vocabulary(
        self,
        words: list[ExtractedWord],
        language: str,
    ) -> int:
        """
        Save extracted vocabulary to database.

        Args:
            words: List of extracted words to save
            language: Target language code

        Returns:
            Number of new words added
        """
        new_count = 0
        for word in words:
            existing = self._repo.get_by_word_and_language(word.word, language)
            if existing is None:
                new_count += 1
            self._repo.upsert(
                word=word.word,
                translation=word.translation,
                language=language,
                part_of_speech=word.part_of_speech,
            )
        return new_count

    def get_word_bank(
        self,
        language: str,
        topic: str | None = None,  # noqa: ARG002
        count: int = 6,
    ) -> list[str]:
        """
        Get a word bank for scaffolding UI.

        This is a stub implementation. In production, this would
        select contextually relevant words based on conversation topic.

        Args:
            language: Target language code
            topic: Optional topic to filter words by
            count: Number of words to return

        Returns:
            List of words for the word bank
        """
        recent = self._repo.get_recent(language, limit=count)
        return [v.word for v in recent]

    def get_statistics(self, language: str) -> VocabularyStats:
        """
        Get vocabulary learning statistics.

        Args:
            language: Target language code

        Returns:
            Statistics about vocabulary progress
        """
        all_vocab = self._repo.get_all(language=language)

        pos_counts: dict[str, int] = {}
        for v in all_vocab:
            if v.part_of_speech:
                pos_counts[v.part_of_speech] = pos_counts.get(v.part_of_speech, 0) + 1

        sorted_by_seen = sorted(all_vocab, key=lambda x: x.times_seen, reverse=True)
        most_seen = [(v.word, v.times_seen) for v in sorted_by_seen[:10]]

        recent = self._repo.get_recent(language, limit=10)
        recently_learned = [v.word for v in recent]

        return VocabularyStats(
            total_words=len(all_vocab),
            words_by_part_of_speech=pos_counts,
            most_seen=most_seen,
            recently_learned=recently_learned,
        )
