"""Unit tests for the deterministic eval checks in evals/scoring.py."""

import pytest
from evals.run import load_cases
from evals.scoring import (
    LEVEL_BANDS,
    case_passed,
    check_contains_any,
    check_grammar_feedback,
    check_json_outputs,
    check_language_mix,
    check_length,
    check_no_lecture,
    check_recast,
    check_scaffolding,
    score_case,
    stopwords_for,
    target_share,
)

ES = "Muy bien, yo también estoy aquí con mi familia y la música."
EN = "That is great, and you can do this with me."


class TestTargetShare:
    def test_all_target(self) -> None:
        share, n = target_share(ES, "es")
        assert share == 1.0
        assert n >= 5

    def test_all_english(self) -> None:
        share, _ = target_share(EN, "es")
        assert share == 0.0

    def test_half_and_half(self) -> None:
        share, _ = target_share(f"{ES} {EN}", "es")
        assert share == pytest.approx(0.5)

    def test_too_few_words_is_none(self) -> None:
        assert target_share("Hola amigo!", "es") == (None, 1)

    @pytest.mark.parametrize(
        ("language", "text"),
        [
            ("de", "Ja, das ist sehr gut und ich bin auch hier."),
            ("fr", "Oui, c'est très bien et je suis aussi avec toi."),
            ("hi", "Haan ji, main bhi theek hoon aur bahut khush hoon."),
        ],
    )
    def test_other_languages(self, language: str, text: str) -> None:
        assert target_share(text, language)[0] == 1.0

    def test_curly_apostrophe_is_normalized(self) -> None:
        assert target_share("Oui, c\u2019est très bien et je suis là.", "fr")[0] == 1.0

    def test_shared_words_count_for_neither(self) -> None:
        english, target = stopwords_for("es")
        assert not english & target


class TestLanguageMix:
    @pytest.mark.parametrize(
        ("level", "text", "expected"),
        [
            ("A0", f"{ES} {EN} {EN} {EN}", True),
            ("A0", ES, False),
            ("A1", f"{ES} {EN}", True),
            ("A2", f"{ES} {ES} {ES} {EN}", True),
            ("A2", f"{ES} {EN} {EN}", False),
            ("B1", ES, True),
            ("B1", f"{ES} {EN}", False),
        ],
    )
    def test_bands(self, level: str, text: str, expected: bool) -> None:
        assert check_language_mix(text, "es", level)["passed"] is expected

    def test_skipped_when_too_short(self) -> None:
        assert check_language_mix("Hola!", "es", "B1")["passed"] is None

    def test_every_level_has_a_band(self) -> None:
        assert set(LEVEL_BANDS) == {"A0", "A1", "A2", "B1"}


class TestScaffolding:
    def test_beginner_needs_word_bank(self) -> None:
        result = {"scaffolding": {"enabled": True, "word_bank": ["hola (hello)"]}}
        assert check_scaffolding(result, "A0")["passed"] is True

    def test_beginner_empty_word_bank_fails(self) -> None:
        # The scaffold node falls back to an empty word bank when JSON parsing fails.
        result = {"scaffolding": {"enabled": True, "word_bank": []}}
        assert check_scaffolding(result, "A1")["passed"] is False

    def test_beginner_missing_fails(self) -> None:
        assert check_scaffolding({}, "A0")["passed"] is False

    def test_advanced_must_not_have_it(self) -> None:
        assert check_scaffolding({}, "B1")["passed"] is True
        result = {"scaffolding": {"enabled": True, "word_bank": ["x"]}}
        assert check_scaffolding(result, "A2")["passed"] is False


class TestOtherChecks:
    def test_json_outputs(self) -> None:
        assert check_json_outputs(['{"a": 1}', '```json\n{"b": 2}\n```'])["passed"] is True
        assert check_json_outputs(['{"a": 1}', "Sure! here you go"])["passed"] is False
        assert check_json_outputs(["[1, 2]"])["passed"] is False

    def test_length(self) -> None:
        assert check_length("one two", "A0")["passed"] is False
        assert check_length(" ".join(["palabra"] * 50), "A0")["passed"] is True
        assert check_length(" ".join(["palabra"] * 300), "B1")["passed"] is False

    def test_grammar_feedback(self) -> None:
        assert check_grammar_feedback({"grammar_feedback": [{"original": "x"}]})["passed"]
        assert not check_grammar_feedback({"grammar_feedback": []})["passed"]

    def test_recast(self) -> None:
        assert check_recast("¡Ah, eres estudiante!", ["soy", "eres"])["passed"] is True
        assert check_recast("Tu as 25 ans, super !", ["j'ai 25", "tu as 25"])["passed"] is True
        assert check_recast("Muy bien.", ["soy"])["passed"] is False

    def test_no_lecture(self) -> None:
        assert check_no_lecture("¡Eres estudiante! Qué bien.")["passed"] is True
        failed = check_no_lecture("That is wrong. The grammar rule says...")
        assert failed["passed"] is False
        assert "wrong" in failed["detail"]

    def test_contains_any(self) -> None:
        assert check_contains_any("Say Danke!", ["danke"])["passed"] is True
        assert check_contains_any("Say Hallo!", ["danke"])["passed"] is False


class TestScoreCase:
    def test_error_case_adds_checks(self) -> None:
        case = {
            "language": "es",
            "level": "B1",
            "expect": {"grammar_error": True, "recast": ["vengas"], "contains_any": ["fiesta"]},
        }
        names = [c["name"] for c in score_case(case, ES, {}, [])]
        assert names == [
            "language_mix",
            "scaffolding",
            "json_parses",
            "length",
            "grammar_feedback",
            "no_lecture",
            "recast_in_reply",
            "contains_any",
        ]

    def test_case_passed_ignores_skipped(self) -> None:
        assert case_passed([{"passed": True}, {"passed": None}])
        assert not case_passed([{"passed": True}, {"passed": False}])


class TestDataset:
    def test_cases_are_well_formed(self) -> None:
        cases = load_cases()
        ids = [c["id"] for c in cases]
        assert len(ids) == len(set(ids))
        assert 18 <= len(cases) <= 25
        assert {c["level"] for c in cases} == {"A0", "A1", "A2", "B1"}
        assert {c["language"] for c in cases} == {"es", "de", "fr", "hi"}
        assert sum(bool(c.get("expect", {}).get("grammar_error")) for c in cases) >= 4
        for c in cases:
            assert c["message"].strip()
            stopwords_for(c["language"])  # raises KeyError for an unsupported language
