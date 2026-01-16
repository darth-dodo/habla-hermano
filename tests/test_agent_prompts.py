"""
Tests for the prompt generation system.

This module tests the get_prompt_for_level function and the LEVEL_PROMPTS dictionary
that define system prompts for each CEFR level.
"""

import pytest

from src.agent.prompts import LEVEL_PROMPTS, get_prompt_for_level


class TestLevelPromptsStructure:
    """Tests for the LEVEL_PROMPTS dictionary structure."""

    def test_level_prompts_contains_a0(self) -> None:
        """LEVEL_PROMPTS should contain A0 (absolute beginner)."""
        assert "A0" in LEVEL_PROMPTS

    def test_level_prompts_contains_a1(self) -> None:
        """LEVEL_PROMPTS should contain A1 (beginner)."""
        assert "A1" in LEVEL_PROMPTS

    def test_level_prompts_contains_a2(self) -> None:
        """LEVEL_PROMPTS should contain A2 (elementary)."""
        assert "A2" in LEVEL_PROMPTS

    def test_level_prompts_contains_b1(self) -> None:
        """LEVEL_PROMPTS should contain B1 (intermediate)."""
        assert "B1" in LEVEL_PROMPTS

    def test_level_prompts_has_exactly_four_levels(self) -> None:
        """LEVEL_PROMPTS should have exactly 4 levels for Phase 1."""
        assert len(LEVEL_PROMPTS) == 4

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_all_prompts_are_non_empty_strings(self, level: str) -> None:
        """All level prompts should be non-empty strings."""
        assert isinstance(LEVEL_PROMPTS[level], str)
        assert len(LEVEL_PROMPTS[level]) > 0


class TestPromptContent:
    """Tests for the content of individual level prompts."""

    def test_a0_prompt_mentions_absolute_beginners(self) -> None:
        """A0 prompt should mention absolute beginners."""
        prompt = LEVEL_PROMPTS["A0"]
        assert "absolute beginner" in prompt.lower()

    def test_a0_prompt_has_high_english_ratio(self) -> None:
        """A0 prompt should specify 80% English, 20% Spanish."""
        prompt = LEVEL_PROMPTS["A0"]
        assert "80%" in prompt
        assert "20%" in prompt

    def test_a1_prompt_mentions_beginners(self) -> None:
        """A1 prompt should mention beginners."""
        prompt = LEVEL_PROMPTS["A1"]
        assert "beginner" in prompt.lower()

    def test_a1_prompt_has_balanced_language_ratio(self) -> None:
        """A1 prompt should specify 50% Spanish, 50% English."""
        prompt = LEVEL_PROMPTS["A1"]
        assert "50%" in prompt

    def test_a2_prompt_mentions_elementary(self) -> None:
        """A2 prompt should mention elementary learners."""
        prompt = LEVEL_PROMPTS["A2"]
        assert "elementary" in prompt.lower()

    def test_a2_prompt_has_higher_spanish_ratio(self) -> None:
        """A2 prompt should specify 80% Spanish, 20% English."""
        prompt = LEVEL_PROMPTS["A2"]
        assert "80%" in prompt
        assert "20%" in prompt

    def test_b1_prompt_mentions_intermediate(self) -> None:
        """B1 prompt should mention intermediate learners."""
        prompt = LEVEL_PROMPTS["B1"]
        assert "intermediate" in prompt.lower()

    def test_b1_prompt_has_high_spanish_ratio(self) -> None:
        """B1 prompt should specify 95%+ Spanish."""
        prompt = LEVEL_PROMPTS["B1"]
        assert "95%" in prompt

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_all_prompts_mention_spanish(self, level: str) -> None:
        """All prompts should mention Spanish (base language)."""
        prompt = LEVEL_PROMPTS[level]
        assert "Spanish" in prompt or "spanish" in prompt

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_all_prompts_have_behavior_section(self, level: str) -> None:
        """All prompts should have a BEHAVIOR section."""
        prompt = LEVEL_PROMPTS[level]
        assert "BEHAVIOR" in prompt

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_all_prompts_have_topics_section(self, level: str) -> None:
        """All prompts should have a TOPICS section."""
        prompt = LEVEL_PROMPTS[level]
        assert "TOPICS" in prompt

    @pytest.mark.parametrize("level", ["A1", "A2", "B1"])
    def test_non_a0_prompts_have_grammar_focus(self, level: str) -> None:
        """A1, A2, B1 prompts should have GRAMMAR FOCUS section."""
        prompt = LEVEL_PROMPTS[level]
        assert "GRAMMAR FOCUS" in prompt


class TestPromptGrammarProgression:
    """Tests for grammar progression across levels."""

    def test_a1_focuses_on_present_tense(self) -> None:
        """A1 should focus on present tense and basics."""
        prompt = LEVEL_PROMPTS["A1"]
        assert "present tense" in prompt.lower()
        assert "ser/estar" in prompt.lower()

    def test_a2_introduces_past_tense(self) -> None:
        """A2 should introduce past tense."""
        prompt = LEVEL_PROMPTS["A2"]
        assert "past tense" in prompt.lower() or "preterite" in prompt.lower()

    def test_b1_covers_advanced_grammar(self) -> None:
        """B1 should cover subjunctive and conditionals."""
        prompt = LEVEL_PROMPTS["B1"]
        assert "subjunctive" in prompt.lower()
        assert "conditional" in prompt.lower()


class TestGetPromptForLevelSpanish:
    """Tests for get_prompt_for_level with Spanish."""

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_returns_prompt_for_valid_level(self, level: str) -> None:
        """Should return the corresponding prompt for valid levels."""
        prompt = get_prompt_for_level("es", level)
        assert prompt == LEVEL_PROMPTS[level]

    def test_returns_string(self) -> None:
        """Should always return a string."""
        prompt = get_prompt_for_level("es", "A1")
        assert isinstance(prompt, str)

    def test_prompt_not_empty(self) -> None:
        """Should return a non-empty prompt."""
        prompt = get_prompt_for_level("es", "A1")
        assert len(prompt) > 0

    def test_unknown_level_defaults_to_a1(self) -> None:
        """Unknown level should default to A1 prompt."""
        prompt = get_prompt_for_level("es", "C2")
        assert prompt == LEVEL_PROMPTS["A1"]

    def test_empty_level_defaults_to_a1(self) -> None:
        """Empty string level should default to A1 prompt."""
        prompt = get_prompt_for_level("es", "")
        assert prompt == LEVEL_PROMPTS["A1"]

    def test_case_sensitive_level(self) -> None:
        """Level should be case-sensitive (lowercase fails)."""
        prompt = get_prompt_for_level("es", "a1")
        # Lowercase 'a1' is not in LEVEL_PROMPTS, should default to A1
        assert prompt == LEVEL_PROMPTS["A1"]


class TestGetPromptForLevelGerman:
    """Tests for get_prompt_for_level with German."""

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_returns_prompt_for_all_levels(self, level: str) -> None:
        """Should return a prompt for all valid levels in German."""
        prompt = get_prompt_for_level("de", level)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_replaces_spanish_with_german(self) -> None:
        """German prompt should replace Spanish references with German."""
        prompt = get_prompt_for_level("de", "A1")
        assert "German" in prompt
        assert "Spanish" not in prompt

    def test_replaces_spanish_lowercase(self) -> None:
        """German prompt should also replace lowercase 'spanish'."""
        prompt = get_prompt_for_level("de", "A0")
        assert "german" in prompt.lower()
        assert "spanish" not in prompt.lower()

    def test_replaces_hola_with_hallo(self) -> None:
        """German A0 prompt should replace 'Hola' with 'Hallo'."""
        prompt = get_prompt_for_level("de", "A0")
        assert "Hallo" in prompt or "hallo" in prompt
        assert "Hola" not in prompt
        assert "hola" not in prompt

    def test_replaces_me_llamo_with_ich_heisse(self) -> None:
        """German A0 prompt should replace 'Me llamo' with 'Ich heisse'."""
        prompt = get_prompt_for_level("de", "A0")
        assert "Ich heisse" in prompt
        assert "Me llamo" not in prompt

    def test_german_a0_mentions_tutor(self) -> None:
        """German A0 prompt should still mention being a tutor."""
        prompt = get_prompt_for_level("de", "A0")
        assert "tutor" in prompt.lower()

    def test_german_b1_mentions_intermediate(self) -> None:
        """German B1 prompt should mention intermediate level."""
        prompt = get_prompt_for_level("de", "B1")
        assert "intermediate" in prompt.lower()


class TestGetPromptForLevelComparison:
    """Tests comparing Spanish and German prompts."""

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_german_and_spanish_prompts_differ(self, level: str) -> None:
        """German and Spanish prompts for same level should differ."""
        spanish_prompt = get_prompt_for_level("es", level)
        german_prompt = get_prompt_for_level("de", level)
        assert spanish_prompt != german_prompt

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_same_structure_different_language_references(self, level: str) -> None:
        """Prompts should have same structure but different language references."""
        spanish_prompt = get_prompt_for_level("es", level)
        german_prompt = get_prompt_for_level("de", level)

        # Both should have BEHAVIOR section
        assert "BEHAVIOR" in spanish_prompt
        assert "BEHAVIOR" in german_prompt

        # Both should have TOPICS section
        assert "TOPICS" in spanish_prompt
        assert "TOPICS" in german_prompt


class TestGetPromptForLevelEdgeCases:
    """Edge case tests for get_prompt_for_level."""

    def test_empty_language_still_works(self) -> None:
        """Empty language string should return Spanish prompt (no replacements)."""
        prompt = get_prompt_for_level("", "A1")
        assert "Spanish" in prompt

    def test_unknown_language_returns_spanish(self) -> None:
        """Unknown language should return original Spanish prompt."""
        prompt = get_prompt_for_level("fr", "A1")
        # French is not handled, so no replacements made
        assert "Spanish" in prompt

    def test_none_like_behavior(self) -> None:
        """Function should handle edge cases gracefully."""
        # Just test that it doesn't crash with unusual inputs
        try:
            get_prompt_for_level("es", "X")
        except KeyError:
            pytest.fail("Should not raise KeyError for unknown level")

    @pytest.mark.parametrize(
        "language,level",
        [
            ("es", "A0"),
            ("es", "A1"),
            ("es", "A2"),
            ("es", "B1"),
            ("de", "A0"),
            ("de", "A1"),
            ("de", "A2"),
            ("de", "B1"),
        ],
    )
    def test_all_language_level_combinations(self, language: str, level: str) -> None:
        """All valid language/level combinations should return valid prompts."""
        prompt = get_prompt_for_level(language, level)
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Prompts should be substantial


class TestPromptQuality:
    """Tests for prompt quality and consistency."""

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_prompts_are_substantial(self, level: str) -> None:
        """Prompts should be substantial enough to guide the AI."""
        prompt = LEVEL_PROMPTS[level]
        # Each prompt should have meaningful content
        assert len(prompt) > 200

    @pytest.mark.parametrize("level", ["A0", "A1", "A2", "B1"])
    def test_prompts_mention_language_mix(self, level: str) -> None:
        """All prompts should specify LANGUAGE MIX ratio."""
        prompt = LEVEL_PROMPTS[level]
        assert "LANGUAGE MIX" in prompt

    def test_difficulty_progression_in_behavior(self) -> None:
        """Prompts should show progression in expected complexity."""
        a0_prompt = LEVEL_PROMPTS["A0"]
        b1_prompt = LEVEL_PROMPTS["B1"]

        # A0 should emphasize simplicity
        assert "simple" in a0_prompt.lower() or "VERY simple" in a0_prompt

        # B1 should mention natural conversations
        assert "natural" in b1_prompt.lower()
