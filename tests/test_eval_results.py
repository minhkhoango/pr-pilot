# tests/test_eval_results.py
"""
Regression tests over the RECORDED eval run (tests/eval/results.json).

The A/B benchmark (tests/eval/run_eval.py) hits live Gemini and is not run in
CI. Instead we commit its output and assert the properties that make the
résumé claim true: the run is well-formed, and adding PR context does not
regress coverage while it *improves* the 'explains why' score. If a future
re-record breaks these, the test catches it. These tests read only the JSON --
no API, no SDK -- so they stay hermetic and fast.

The one live test (opt-in via `-m live`) re-runs the product pipeline against a
fixture to confirm it still returns a valid briefing; it lazy-imports the Gemini
SDK so this file imports fine in an environment without it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

EVAL_DIR = Path(__file__).parent / "eval"
RESULTS_PATH = EVAL_DIR / "results.json"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_results() -> dict[str, Any]:
    if not RESULTS_PATH.exists():
        pytest.skip(
            "tests/eval/results.json not recorded yet "
            "(run: PYTHONPATH=src python tests/eval/run_eval.py)"
        )
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


def test_results_are_wellformed() -> None:
    results = _load_results()
    assert results["n_fixtures"] == len(results["fixtures"])
    assert results["n_fixtures"] >= 3
    for r in results["fixtures"]:
        for variant in ("diff_only", "with_context"):
            assert 0.0 <= r[variant]["coverage"] <= 1.0


def test_both_variants_cover_the_diff_well() -> None:
    # Coverage is the "trees" axis (does the summary name the changed
    # files/functions?). Both prompts are decent at it -- this is NOT where they
    # differ -- so we assert both stay high rather than that context wins here.
    results = _load_results()
    assert results["diff_only"]["mean_coverage"] >= 0.6
    assert results["with_context"]["mean_coverage"] >= 0.6


def test_context_sharply_improves_explains_why_score() -> None:
    # The core thesis and the résumé claim: the raw-diff baseline is blind to
    # *why*; supplying intent roughly doubles the judged 'explains why' score.
    results = _load_results()
    if results["judge_delta"] is None:
        pytest.skip("judge disabled in this recording (--no-judge)")
    assert results["judge_delta"] >= 1.0
    assert results["with_context"]["mean_judge_score"] >= 4.0
    assert (
        results["with_context"]["mean_judge_score"]
        > results["diff_only"]["mean_judge_score"]
    )


def test_every_fixture_explains_why_at_least_as_well_with_context() -> None:
    # Monotonic: on no fixture does adding intent make the 'why' worse.
    results = _load_results()
    if results["judge_delta"] is None:
        pytest.skip("judge disabled in this recording (--no-judge)")
    for r in results["fixtures"]:
        assert r["with_context"]["judge_score"] >= r["diff_only"]["judge_score"], (
            f"{r['stem']} regressed on the 'why' axis"
        )


@pytest.mark.live
def test_live_product_pipeline_returns_valid_briefing() -> None:
    # Opt-in (`pytest -m live`): actually calls Gemini via the shipped product
    # function, confirming the diff-only pipeline still returns a valid briefing.
    import os

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not set")

    from pr_pilot.main import generate_briefing  # lazy: needs the Gemini SDK

    raw = (FIXTURES_DIR / "diff_typeddict_refactor.diff").read_text(encoding="utf-8")
    pure_diff = raw[raw.find("diff --git ") :]
    briefing = generate_briefing(pure_diff, api_key)

    assert isinstance(briefing.get("summary"), str) and briefing["summary"]
    assert isinstance(briefing.get("file_changes"), list)
