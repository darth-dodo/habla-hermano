"""Deterministic scoring for the LLM eval harness.

Everything here is a pure function over a case and a graph result, so it is
unit tested in CI without any network access.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.agent.utils import extract_json_from_response

_STOPWORDS_PATH = Path(__file__).resolve().parents[1] / "data" / "stopwords.json"

_STOPWORD_KEYS = {"es": "spanish", "de": "german", "fr": "french", "hi": "hinglish"}

# Target-language share of recognised words, per CEFR level. Prompts ask for
# A0 ~20%, A1 ~50%, A2 ~80%, B1 95%+; bands are wide because the heuristic is crude.
LEVEL_BANDS: dict[str, tuple[float, float]] = {
    "A0": (0.05, 0.5),
    "A1": (0.2, 0.8),
    "A2": (0.55, 1.0),
    "B1": (0.8, 1.0),
}

# Reply length bounds in words.
LENGTH_BOUNDS: dict[str, tuple[int, int]] = {
    "A0": (5, 150),
    "A1": (5, 150),
    "A2": (5, 220),
    "B1": (5, 220),
}

# Fewer recognised words than this and the mix check is skipped as too noisy.
MIN_RECOGNISED_WORDS = 5

LECTURE_MARKERS = ("wrong", "incorrect", "mistake", "error", "grammar rule")

_WORD_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")


@lru_cache(maxsize=1)
def _load_stopwords() -> dict[str, frozenset[str]]:
    with _STOPWORDS_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return {key: frozenset(data[key]) for key in ("english", *_STOPWORD_KEYS.values())}


def stopwords_for(language: str) -> tuple[frozenset[str], frozenset[str]]:
    """Return (english, target) stopword sets with shared words removed from both."""
    data = _load_stopwords()
    english, target = data["english"], data[_STOPWORD_KEYS[language]]
    shared = english & target
    return english - shared, target - shared


def normalize(text: str) -> str:
    """Lowercase and unify curly apostrophes so substring checks are stable."""
    return text.lower().replace("\u2019", "'").replace("\u2018", "'")


def words(text: str) -> list[str]:
    return _WORD_RE.findall(normalize(text))


def target_share(text: str, language: str) -> tuple[float | None, int]:
    """Share of recognised stopwords that are target language, and how many were recognised.

    Returns (None, n) when fewer than MIN_RECOGNISED_WORDS were recognised.
    """
    english, target = stopwords_for(language)
    tokens = words(text)
    n_target = sum(t in target for t in tokens)
    n_english = sum(t in english for t in tokens)
    total = n_target + n_english
    if total < MIN_RECOGNISED_WORDS:
        return None, total
    return n_target / total, total


def _check(name: str, passed: bool | None, detail: str) -> dict[str, Any]:
    """passed=None means the check was skipped."""
    return {"name": name, "passed": passed, "detail": detail}


def check_language_mix(reply: str, language: str, level: str) -> dict[str, Any]:
    low, high = LEVEL_BANDS[level]
    share, n = target_share(reply, language)
    if share is None:
        return _check("language_mix", None, f"only {n} recognised words")
    return _check(
        "language_mix", low <= share <= high, f"target {share:.0%} (band {low:.0%}-{high:.0%})"
    )


def check_scaffolding(result: dict[str, Any], level: str) -> dict[str, Any]:
    scaffolding = result.get("scaffolding") or {}
    enabled = bool(scaffolding.get("enabled"))
    if level in ("A0", "A1"):
        word_bank = scaffolding.get("word_bank") or []
        return _check(
            "scaffolding",
            enabled and len(word_bank) > 0,
            f"enabled={enabled}, words={len(word_bank)}",
        )
    return _check("scaffolding", not enabled, f"enabled={enabled} (expected absent)")


def check_json_outputs(json_outputs: list[str]) -> dict[str, Any]:
    """Every structured node output (scaffold, analyze) must parse as a JSON object."""
    bad = 0
    for raw in json_outputs:
        try:
            if not isinstance(extract_json_from_response(raw), dict):
                bad += 1
        except (json.JSONDecodeError, IndexError):
            bad += 1
    return _check("json_parses", bad == 0, f"{len(json_outputs) - bad}/{len(json_outputs)} parsed")


def check_length(reply: str, level: str) -> dict[str, Any]:
    low, high = LENGTH_BOUNDS[level]
    n = len(words(reply))
    return _check("length", low <= n <= high, f"{n} words (bounds {low}-{high})")


def check_grammar_feedback(result: dict[str, Any]) -> dict[str, Any]:
    feedback = result.get("grammar_feedback") or []
    return _check("grammar_feedback", len(feedback) > 0, f"{len(feedback)} corrections")


def check_recast(reply: str, forms: list[str]) -> dict[str, Any]:
    """The reply should model a corrected form instead of only talking about it."""
    hit = check_contains_any(reply, forms)
    return _check("recast_in_reply", hit["passed"], hit["detail"])


def check_no_lecture(reply: str) -> dict[str, Any]:
    text = normalize(reply)
    found = [m for m in LECTURE_MARKERS if re.search(rf"\b{re.escape(m)}", text)]
    return _check("no_lecture", not found, f"markers: {', '.join(found)}" if found else "none")


def check_contains_any(reply: str, options: list[str]) -> dict[str, Any]:
    text = normalize(reply)
    hit = next((o for o in options if normalize(o) in text), None)
    return _check("contains_any", hit is not None, f"matched '{hit}'" if hit else "no match")


def score_case(
    case: dict[str, Any], reply: str, result: dict[str, Any], json_outputs: list[str]
) -> list[dict[str, Any]]:
    """Run every deterministic check that applies to this case."""
    level, language = case["level"], case["language"]
    expect = case.get("expect", {})
    checks = [
        check_language_mix(reply, language, level),
        check_scaffolding(result, level),
        check_json_outputs(json_outputs),
        check_length(reply, level),
    ]
    if expect.get("grammar_error"):
        checks += [check_grammar_feedback(result), check_no_lecture(reply)]
    if expect.get("recast"):
        checks.append(check_recast(reply, expect["recast"]))
    if expect.get("contains_any"):
        checks.append(check_contains_any(reply, expect["contains_any"]))
    return checks


def case_passed(checks: list[dict[str, Any]]) -> bool:
    """A case passes when no check failed; skipped checks do not count."""
    return all(c["passed"] is not False for c in checks)
