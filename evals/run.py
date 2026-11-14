"""Run the Hermano LLM evals against the real model.

Usage:
    make eval
    uv run python -m evals.run [--judge] [--only es-b1]

Builds the real chat graph (respond -> scaffold -> analyze) with an in-memory
checkpointer, sends one learner turn per case from evals/cases.yaml, scores the
result with the deterministic checks in evals/scoring.py and writes a JSON
report to evals/results/. Calls OpenRouter, so it costs money and never runs in CI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langgraph.checkpoint.memory import MemorySaver

from evals.scoring import case_passed, score_case
from src.agent.utils import extract_json_from_response

EVALS_DIR = Path(__file__).resolve().parent
CASES_PATH = EVALS_DIR / "cases.yaml"
RESULTS_DIR = EVALS_DIR / "results"

Judge = Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]

JUDGE_PROMPT = """You grade a language tutor. The learner wrote: "{message}"
That message has a grammar error. The tutor replied:
---
{reply}
---
A gentle recast models the correct form naturally inside the conversation, with at
most a short friendly aside. A lecture explains grammar rules at length, dwells on
the error, or tells the learner they were wrong.

Return ONLY JSON: {{"recast": true or false, "reason": "one short sentence"}}"""


class _Recorder(BaseCallbackHandler):
    """Collects raw outputs and token usage of every LLM call in one graph run."""

    run_inline = True

    def __init__(self) -> None:
        self.outputs: list[str] = []
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:  # noqa: ARG002
        gen = response.generations[0][0]
        self.outputs.append(gen.text)
        message = gen.message if isinstance(gen, ChatGeneration) else None
        usage = message.usage_metadata if isinstance(message, AIMessage) else None
        if usage:
            self.input_tokens += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        cases: list[dict[str, Any]] = yaml.safe_load(fh)["cases"]
    return cases


async def llm_judge(case: dict[str, Any], reply: str) -> dict[str, Any]:
    """LLM-as-judge: is the correction a gentle recast rather than a lecture?"""
    from src.agent.llm import get_llm  # noqa: PLC0415  # needs settings, only load when judging

    prompt = JUDGE_PROMPT.format(message=case["message"], reply=reply)
    response = await get_llm("analysis").ainvoke([SystemMessage(content=prompt)])
    try:
        data = extract_json_from_response(str(response.content))
        return {"name": "judge_recast", "passed": bool(data["recast"]), "detail": data["reason"]}
    except (json.JSONDecodeError, KeyError, IndexError):
        return {"name": "judge_recast", "passed": False, "detail": "unparseable judge output"}


async def run_case(graph: Any, case: dict[str, Any], judge: Judge | None = None) -> dict[str, Any]:
    recorder = _Recorder()
    config = {"configurable": {"thread_id": f"eval-{case['id']}"}, "callbacks": [recorder]}
    state = {
        "messages": [HumanMessage(content=case["message"])],
        "level": case["level"],
        "language": case["language"],
    }
    start = time.perf_counter()
    try:
        result = await graph.ainvoke(state, config=config)
    except Exception as e:  # keep going so one bad call does not sink the run
        checks = [{"name": "graph_invoke", "passed": False, "detail": repr(e)}]
        reply = ""
    else:
        reply = str(result["messages"][-1].content)
        # The first LLM call is respond (free text); the rest are scaffold/analyze JSON.
        checks = score_case(case, reply, result, recorder.outputs[1:])
        if judge and case.get("expect", {}).get("grammar_error"):
            checks.append(await judge(case, reply))
    latency = time.perf_counter() - start
    return {
        "id": case["id"],
        "language": case["language"],
        "level": case["level"],
        "message": case["message"],
        "reply": reply,
        "passed": case_passed(checks),
        "checks": checks,
        "latency_s": round(latency, 2),
        "llm_calls": len(recorder.outputs),
        "input_tokens": recorder.input_tokens,
        "output_tokens": recorder.output_tokens,
    }


async def run_cases(
    graph: Any, cases: list[dict[str, Any]], judge: Judge | None = None
) -> list[dict[str, Any]]:
    # Sequential on purpose: keeps latency numbers honest and rate limits happy.
    return [await run_case(graph, case, judge) for case in cases]


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(r["passed"] for r in results)
    return {
        "cases": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "input_tokens": sum(r["input_tokens"] for r in results),
        "output_tokens": sum(r["output_tokens"] for r in results),
        "total_latency_s": round(sum(r["latency_s"] for r in results), 2),
    }


def format_table(results: list[dict[str, Any]]) -> str:
    lines = [
        f"{'case':<28} {'lvl':<3} {'checks':>6} {'latency':>8} {'tokens':>7}  result",
        "-" * 64,
    ]
    failures = []
    for r in results:
        ran = [c for c in r["checks"] if c["passed"] is not None]
        ok = sum(c["passed"] is True for c in ran)
        tokens = r["input_tokens"] + r["output_tokens"]
        lines.append(
            f"{r['id']:<28} {r['level']:<3} {f'{ok}/{len(ran)}':>6} "
            f"{r['latency_s']:>7.2f}s {tokens:>7}  {'PASS' if r['passed'] else 'FAIL'}"
        )
        failures += [
            f"  {r['id']}: {c['name']} ({c['detail']})" for c in r["checks"] if c["passed"] is False
        ]
    s = summarize(results)
    lines += [
        "-" * 64,
        f"pass rate {s['passed']}/{s['cases']} ({s['pass_rate']:.0%}), "
        f"tokens in/out {s['input_tokens']}/{s['output_tokens']}, total {s['total_latency_s']}s",
    ]
    if failures:
        lines += ["", "failed checks:", *failures]
    return "\n".join(lines)


def write_report(results: list[dict[str, Any]], model: str, out_dir: Path = RESULTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"eval-{stamp}.json"
    report = {
        "model": model,
        "created_at": stamp,
        "summary": summarize(results),
        "results": results,
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Hermano LLM evals")
    parser.add_argument("--judge", action="store_true", help="add LLM-as-judge recast check")
    parser.add_argument("--only", default="", help="run cases whose id contains this text")
    args = parser.parse_args(argv)

    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "OPENROUTER_API_KEY is not set. The evals call the real model through OpenRouter.\n"
            "Export it first, e.g. OPENROUTER_API_KEY=sk-or-... make eval",
            file=sys.stderr,
        )
        return 2

    # Imported late so the key check above runs before settings are loaded.
    from src.agent.graph import build_graph  # noqa: PLC0415
    from src.config import get_settings  # noqa: PLC0415

    cases = [c for c in load_cases() if args.only in c["id"]]
    graph = build_graph(checkpointer=MemorySaver())
    results = asyncio.run(run_cases(graph, cases, llm_judge if args.judge else None))

    print(format_table(results))
    print(f"\nreport: {write_report(results, get_settings().LLM_MODEL)}")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
