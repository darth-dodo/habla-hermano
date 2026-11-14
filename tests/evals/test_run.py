"""End to end test of the eval runner: real graph, MemorySaver, fake chat model."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from evals.run import format_table, load_cases, main, run_cases, summarize, write_report
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver

from src.agent.graph import build_graph

TARGET = {
    "es": "Muy bien, yo también estoy aquí con mi familia y la música.",
    "de": "Ja, das ist sehr gut und ich bin auch hier.",
    "fr": "Oui, c'est très bien et je suis aussi avec toi.",
    "hi": "Haan ji, main bhi theek hoon aur bahut khush hoon.",
}
ENGLISH = "That is great, and you can do this with me."
# (target sentences, English sentences) per level, matching the prompt's language mix.
MIX = {"A0": (1, 3), "A1": (1, 1), "A2": (3, 1), "B1": (2, 0)}


def good_reply(case: dict[str, Any]) -> str:
    n_target, n_english = MIX[case["level"]]
    parts = [TARGET[case["language"]]] * n_target + [ENGLISH] * n_english
    expect = case.get("expect", {})
    parts += expect.get("recast", [])[:1] + expect.get("contains_any", [])[:1]
    return " ".join(parts)


class FakeTutor(BaseChatModel):
    """Answers like each node expects: free text for respond, JSON for scaffold/analyze."""

    replies: dict[str, str]
    error_messages: set[str]
    analysis_json: bool = True

    @property
    def _llm_type(self) -> str:
        return "fake-tutor"

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        last = str(messages[-1].content)
        if last == "Generate scaffolding for the learner.":
            text = json.dumps(
                {"word_bank": ["hola (hello)"], "hint": "Say hi", "sentence_starter": None}
            )
        elif last.startswith("Student's message: "):
            student = last.removeprefix("Student's message: ")
            errors = [
                {"original": "x", "correction": "y", "explanation": "z", "severity": "minor"}
            ] * (student in self.error_messages)
            payload = {"grammar_errors": errors, "new_vocabulary": [], "pronunciation_tips": []}
            text = json.dumps(payload) if self.analysis_json else "Sure! Here is my analysis."
        else:
            text = self.replies[last]
        usage = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
        message = AIMessage(content=text, usage_metadata=usage)  # type: ignore[arg-type]
        return ChatResult(generations=[ChatGeneration(message=message)])


def make_fake(cases: list[dict[str, Any]], **overrides: Any) -> FakeTutor:
    return FakeTutor(
        replies={c["message"]: good_reply(c) for c in cases},
        error_messages={c["message"] for c in cases if c.get("expect", {}).get("grammar_error")},
        **overrides,
    )


@contextmanager
def patched_llm(fake: FakeTutor) -> Iterator[None]:
    with (
        patch("src.agent.nodes.respond.get_llm", return_value=fake),
        patch("src.agent.nodes.scaffold.get_llm", return_value=fake),
        patch("src.agent.nodes.analyze.get_llm", return_value=fake),
    ):
        yield


@pytest.fixture
def cases() -> list[dict[str, Any]]:
    return load_cases()


async def run_with(
    fake: FakeTutor, cases: list[dict[str, Any]], **kwargs: Any
) -> list[dict[str, Any]]:
    with patched_llm(fake):
        return await run_cases(build_graph(checkpointer=MemorySaver()), cases, **kwargs)


async def test_well_behaved_model_passes_every_case(cases: list[dict[str, Any]]) -> None:
    results = await run_with(make_fake(cases), cases)

    failed = {r["id"]: [c for c in r["checks"] if c["passed"] is False] for r in results}
    assert all(r["passed"] for r in results), {k: v for k, v in failed.items() if v}
    summary = summarize(results)
    assert summary["pass_rate"] == 1.0
    # respond + analyze for every case, plus scaffold for A0/A1
    beginners = sum(c["level"] in ("A0", "A1") for c in cases)
    assert sum(r["llm_calls"] for r in results) == 2 * len(cases) + beginners
    assert summary["input_tokens"] == 100 * (2 * len(cases) + beginners)
    assert "pass rate 20/20 (100%)" in format_table(results)


async def test_lecturing_english_reply_fails(cases: list[dict[str, Any]]) -> None:
    case = next(c for c in cases if c["id"] == "es-b1-subjunctive-error")
    fake = make_fake([case])
    fake.replies[case["message"]] = (
        "That is wrong. The grammar rule is that after esperar que you must use the "
        "subjunctive, so this is an error you should fix in your sentence."
    )

    [result] = await run_with(fake, [case])

    failed = {c["name"] for c in result["checks"] if c["passed"] is False}
    assert failed == {"language_mix", "no_lecture", "recast_in_reply"}
    assert not result["passed"]
    assert "FAIL" in format_table([result])


async def test_unparseable_analysis_and_missing_feedback_fail(cases: list[dict[str, Any]]) -> None:
    case = next(c for c in cases if c["id"] == "es-a1-ser-error")

    [result] = await run_with(make_fake([case], analysis_json=False), [case])

    failed = {c["name"] for c in result["checks"] if c["passed"] is False}
    assert failed == {"json_parses", "grammar_feedback"}


async def test_judge_runs_only_on_error_cases(cases: list[dict[str, Any]]) -> None:
    judged: list[str] = []

    async def judge(case: dict[str, Any], reply: str) -> dict[str, Any]:
        judged.append(case["id"])
        return {"name": "judge_recast", "passed": True, "detail": "ok"}

    picked = [c for c in cases if c["id"] in ("es-a1-ser-error", "es-a1-food")]
    await run_with(make_fake(picked), picked, judge=judge)

    assert judged == ["es-a1-ser-error"]


async def test_graph_error_is_recorded_not_raised(cases: list[dict[str, Any]]) -> None:
    class Boom:
        async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    [result] = await run_cases(Boom(), cases[:1])

    assert not result["passed"]
    assert result["checks"][0]["name"] == "graph_invoke"


def test_write_report(tmp_path: Path) -> None:
    results = [{"id": "x", "passed": True, "input_tokens": 1, "output_tokens": 2, "latency_s": 0.5}]
    path = write_report(results, "some/model", out_dir=tmp_path)
    report = json.loads(path.read_text())
    assert report["model"] == "some/model"
    assert report["summary"]["pass_rate"] == 1.0


def test_main_refuses_without_api_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert main([]) == 2
    assert "OPENROUTER_API_KEY is not set" in capsys.readouterr().err
