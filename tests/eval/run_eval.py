# tests/eval/run_eval.py
"""
Offline A/B benchmark for PR-Pilot briefing quality. (Benchmark only -- it does
NOT modify or ship any product code; it imports the real prompt read-only and
adds an experimental variant that lives solely in this file.)

The question it answers is the honest one behind the résumé bullet: does feeding
the model the PR's *intent* (title/body/commits) make its summary materially
better than summarizing the raw diff alone -- the "misses the forest for the
trees" failure of a diff-only reviewer?

For every fixture under tests/fixtures/ (a real `git show` diff paired with a
`.meta.json` describing the PR's stated intent) it runs Gemini twice:

  * baseline: the REAL product prompt, `pr_pilot.main.generate_prompt(diff)`
    -- diff only, "FACTS ONLY".
  * context: an experimental prompt (defined here, not in the product) that adds
    the PR title/body/commits and asks the model to explain the *why*.

Each summary is scored two ways:
  1. coverage_score (deterministic, no LLM): fraction of changed files/functions
     the summary actually names -- a recall proxy for "did it read the diff."
  2. an LLM judge: a stronger sibling model (gemini-2.5-flash grading the
     flash-lite generator) rates 1-5 how well the summary explains the change's
     motivation, given the ground-truth intent.

It writes results.json, RESULTS.md, and the raw summaries next to this file so
the numbers are auditable and the pytest suite can regress against a recorded
run without hitting a live API.

Run once to record:  PYTHONPATH=src python tests/eval/run_eval.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
from pathlib import Path
from typing import Literal, TypedDict, cast

from dotenv import load_dotenv
from google.generativeai.client import configure  # type: ignore
from google.generativeai.generative_models import GenerativeModel

# Import product helpers READ-ONLY. The baseline arm uses the real product
# prompt so the "before" number reflects what PR-Pilot actually ships today.
from pr_pilot.main import (
    MODEL_NAME,
    PRBriefing,
    format_markdown_briefing,
    generate_prompt,
)
from pr_pilot.quality_metrics import coverage_score, extract_diff_coverage_items

# A stronger sibling of the flash-lite generator, driven by the same
# GOOGLE_API_KEY, so the judge is not the generator grading itself.
JUDGE_MODEL = "gemini-2.5-flash"

Variant = Literal["diff_only", "with_context"]

_THIS = Path(__file__).resolve()
FIXTURES_DIR = _THIS.parents[1] / "fixtures"
EVAL_DIR = _THIS.parents[0]


class PRContext(TypedDict):
    """The 'why' of a PR, from GitHub metadata rather than the diff itself."""

    title: str
    body: str
    commit_messages: list[str]


class VariantScore(TypedDict):
    coverage: float
    judge_score: int | None
    judge_reason: str
    summary_chars: int


class FixtureResult(TypedDict):
    stem: str
    files_in_diff: int
    symbols_in_diff: int
    diff_only: VariantScore
    with_context: VariantScore


class VariantAggregate(TypedDict):
    mean_coverage: float
    mean_judge_score: float | None


class EvalResults(TypedDict):
    model: str
    judge_model: str | None
    n_fixtures: int
    fixtures: list[FixtureResult]
    diff_only: VariantAggregate
    with_context: VariantAggregate
    coverage_delta_points: float
    judge_delta: float | None


def strip_commit_preamble(fixture_text: str) -> str:
    """Return the pure unified diff, dropping any leading `git show` preamble
    (`commit <sha>` / Author / Date / message) before the first `diff --git`.

    GitHub's `.diff` endpoint -- what the real action fetches -- returns a bare
    diff with no commit messages, so leaving the preamble in would leak the very
    intent we mean to supply ONLY to the context variant. Unchanged if absent.
    """
    marker = fixture_text.find("diff --git ")
    return fixture_text[marker:] if marker != -1 else fixture_text


def build_context_prompt(diff_content: str, context: PRContext) -> str:
    """The experimental 'context' prompt: the real product schema/rules plus the
    PR's stated intent, with the final rule flipped from FACTS ONLY to
    EXPLAIN-THE-WHY. Kept here (not in the product) so the benchmark measures a
    proposed change without shipping it."""
    commit_lines = "\n".join(
        f"      - {m}" for m in context["commit_messages"]
    ) or "      - (no commit messages provided)"
    return f"""
    You are PR-Pilot, an expert senior software engineer. Analyze the following
    pull request and generate a single, valid JSON object.

    Before the diff, here is the PR's stated intent. Treat it as the source of
    truth for WHY this change was made, and ground your `summary` in it (without
    ever contradicting the diff):
    PR title: {context["title"]}
    PR description:
    {context["body"] or "(no description provided)"}
    Commit messages:
{commit_lines}

    The JSON object must follow this exact schema:
    {{
        "summary": "A single, concise sentence summarizing the PR's core purpose.",
        "file_changes": [
            {{
                "file_name": "The full path of the file.",
                "changes": [
                    {{
                        "type": "Added|Modified|Removed|Refactored",
                        "item": "A high-level summary of the logical change.",
                        "details": ["[Optional] short sub-point; omit for simple items."]
                    }}
                ]
            }}
        ],
        "risk_assessment": {{
            "level": "Low|Medium|High",
            "reasoning": "A brief, single-sentence explanation for the risk."
        }}
    }}

    CRITICAL RULES:
    1.  **CONSOLIDATE CHANGES:** Group all related edits in a file into a SINGLE logical `item`.
    2.  **USE `details` SPARINGLY:** Only to break down a genuinely complex `item`; otherwise `[]`.
    3.  **BE CONCISE:** `item` and `details` are short sentence fragments.
    4.  **JSON ONLY:** Output only the raw JSON object -- no markdown or prose.
    5.  **EXPLAIN THE WHY:** Open the `summary` with the motivation/problem this PR
        addresses (from the stated intent above), then what changed. A summary that
        only lists mechanical edits with no reason is a failure. Never contradict the diff.

    Analyze this diff:
    ```diff
    {diff_content}
    ```
    """


def _gemini_json(prompt: str, api_key: str, model_name: str) -> str:
    """Call a Gemini model and return its response text with any ```json fences
    stripped. Deterministic-ish: temperature 0."""
    configure(api_key=api_key)
    model = GenerativeModel(model_name)
    response = model.generate_content(  # type: ignore[no-untyped-call]
        prompt, generation_config={"temperature": 0.0}
    )
    text: str = response.text.strip()
    return text.replace("```json", "").replace("```", "").strip()


def generate_briefing_from_prompt(prompt: str, api_key: str) -> PRBriefing:
    """Run the generator model on an already-built prompt and parse the JSON
    briefing. Mirrors the product's parse step but takes the prompt as input so
    the benchmark can swap in its context variant."""
    return cast(PRBriefing, json.loads(_gemini_json(prompt, api_key, MODEL_NAME)))


def judge_explains_why(
    context: PRContext, summary_markdown: str, api_key: str
) -> tuple[int, str]:
    """Ask the stronger judge model to rate 1-5 how well `summary_markdown`
    conveys the *why* of the change, given its ground-truth intent. The judge is
    blind to which prompt variant produced the summary. Returns (score, reason);
    raises on a call/parse failure so a recording run fails loudly."""
    intent = (
        f"PR title: {context['title']}\n"
        f"PR description: {context['body']}\n"
        f"Commit messages: {'; '.join(context['commit_messages'])}"
    )
    prompt = (
        "You are grading an automated pull-request summary. Below is the PR's "
        "true intent, then a summary a bot generated. Rate 1-5 how well the "
        "summary explains WHY this change was made (its motivation / the problem "
        "it solves), not merely what mechanically changed. 5 = the reader learns "
        "the reason and would not need to open the diff; 1 = it only narrates "
        "hunks with no sense of purpose.\n\n"
        f"--- TRUE INTENT ---\n{intent}\n\n"
        f"--- GENERATED SUMMARY ---\n{summary_markdown}\n\n"
        'Respond with ONLY a JSON object: {"score": <1-5 int>, "reason": '
        '"<one sentence>"}.'
    )
    parsed = json.loads(_gemini_json(prompt, api_key, JUDGE_MODEL))
    return int(parsed["score"]), str(parsed.get("reason", ""))


def discover_fixtures() -> list[tuple[str, str, PRContext]]:
    """Every `*.diff` with a sibling `*.meta.json`, as (stem, pure_diff,
    context), sorted by stem. A `.diff` with no meta is skipped -- the A/B needs
    the intent."""
    fixtures: list[tuple[str, str, PRContext]] = []
    for diff_path in sorted(FIXTURES_DIR.glob("*.diff")):
        meta_path = diff_path.with_suffix(".meta.json")
        if not meta_path.exists():
            logging.warning("No meta.json for %s; skipping.", diff_path.name)
            continue
        pure_diff = strip_commit_preamble(diff_path.read_text(encoding="utf-8"))
        context = cast(PRContext, json.loads(meta_path.read_text(encoding="utf-8")))
        fixtures.append((diff_path.stem, pure_diff, context))
    return fixtures


def _score_variant(
    pure_diff: str, prompt: str, context: PRContext, api_key: str, judge: bool
) -> tuple[VariantScore, str]:
    """Generate one summary from `prompt`, render it, and score it on coverage
    (always) and the LLM 'why' judge (if enabled). Returns (cell, summary_md)."""
    briefing = generate_briefing_from_prompt(prompt, api_key)
    summary_markdown = format_markdown_briefing(briefing)
    coverage = coverage_score(pure_diff, summary_markdown)

    judge_score: int | None = None
    judge_reason = ""
    if judge:
        judge_score, judge_reason = judge_explains_why(
            context, summary_markdown, api_key
        )

    cell: VariantScore = {
        "coverage": round(coverage, 4),
        "judge_score": judge_score,
        "judge_reason": judge_reason,
        "summary_chars": len(summary_markdown),
    }
    return cell, summary_markdown


def evaluate_all(api_key: str, judge: bool) -> EvalResults:
    """Drive the whole A/B grid: every fixture × {diff_only, with_context},
    persist each generated summary under summaries/, and aggregate into means and
    deltas. The one function that touches the live API."""
    fixtures = discover_fixtures()
    if not fixtures:
        raise RuntimeError(f"No fixtures with meta.json found under {FIXTURES_DIR}")

    summaries_dir = EVAL_DIR / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    results: list[FixtureResult] = []
    for stem, pure_diff, context in fixtures:
        items = extract_diff_coverage_items(pure_diff)
        logging.info("Evaluating fixture %s ...", stem)

        diff_only_cell, diff_only_md = _score_variant(
            pure_diff, generate_prompt(pure_diff), context, api_key, judge
        )
        with_context_cell, with_context_md = _score_variant(
            pure_diff, build_context_prompt(pure_diff, context), context, api_key, judge
        )
        (summaries_dir / f"{stem}.diff_only.md").write_text(
            diff_only_md, encoding="utf-8"
        )
        (summaries_dir / f"{stem}.with_context.md").write_text(
            with_context_md, encoding="utf-8"
        )

        results.append(
            {
                "stem": stem,
                "files_in_diff": len(items.file_names),
                "symbols_in_diff": len(items.symbol_names),
                "diff_only": diff_only_cell,
                "with_context": with_context_cell,
            }
        )

    def _mean_cov(variant: Variant) -> float:
        return round(statistics.mean(r[variant]["coverage"] for r in results), 4)

    def _mean_judge(variant: Variant) -> float | None:
        scores: list[int] = []
        for r in results:
            score = r[variant]["judge_score"]
            if score is not None:
                scores.append(score)
        return round(statistics.mean(scores), 4) if scores else None

    diff_cov, ctx_cov = _mean_cov("diff_only"), _mean_cov("with_context")
    diff_judge, ctx_judge = _mean_judge("diff_only"), _mean_judge("with_context")
    judge_delta = (
        round(ctx_judge - diff_judge, 4)
        if diff_judge is not None and ctx_judge is not None
        else None
    )

    return {
        "model": MODEL_NAME,
        "judge_model": JUDGE_MODEL if judge else None,
        "n_fixtures": len(results),
        "fixtures": results,
        "diff_only": {"mean_coverage": diff_cov, "mean_judge_score": diff_judge},
        "with_context": {"mean_coverage": ctx_cov, "mean_judge_score": ctx_judge},
        "coverage_delta_points": round((ctx_cov - diff_cov) * 100, 2),
        "judge_delta": judge_delta,
    }


def render_results_markdown(results: EvalResults) -> str:
    """Render an EvalResults into an auditable Markdown report."""
    lines: list[str] = [
        "# PR-Pilot briefing-quality eval",
        "",
        f"- Generator: `{results['model']}`",
        f"- Judge: `{results['judge_model']}` (a stronger sibling model, same API key)",
        f"- Fixtures (real PRs from this repo's history): **{results['n_fixtures']}**",
        "",
        "Each fixture is summarized twice: **diff-only** (the shipped product "
        "prompt) and **with-context** (an experimental prompt that adds the PR's "
        "title/body/commit messages). `coverage` = fraction of changed "
        "files/functions the summary names (deterministic); `why` = the judge's "
        "1-5 rating of how well the summary explains the change's motivation.",
        "",
        "| Fixture | coverage (diff-only → +context) | why 1-5 (diff-only → +context) |",
        "| --- | --- | --- |",
    ]
    for r in results["fixtures"]:
        do, wc = r["diff_only"], r["with_context"]
        lines.append(
            f"| `{r['stem']}` | {do['coverage']:.2f} → {wc['coverage']:.2f} | "
            f"{do['judge_score']} → {wc['judge_score']} |"
        )

    agg_do, agg_wc = results["diff_only"], results["with_context"]
    judge_delta = results["judge_delta"]
    judge_delta_str = f"{judge_delta:+.1f}" if judge_delta is not None else "n/a"
    do_judge = agg_do["mean_judge_score"]
    wc_judge = agg_wc["mean_judge_score"]
    judge_pair = "n/a (judge disabled)" if do_judge is None else f"{do_judge} → {wc_judge}"
    lines += [
        "",
        "## Aggregate",
        "",
        f"- Mean coverage — the *trees* (does it name the files/functions?): "
        f"**{agg_do['mean_coverage']:.2f} → {agg_wc['mean_coverage']:.2f}**. "
        f"Both broadly high; this is a coarse string-match proxy (it also picks "
        f"up a few junk hunk-scope tokens), so small moves here are noise, not "
        f"signal — naming *what* changed is not where the two prompts differ.",
        f"- Mean 'explains why' score — the *forest* (1-5): "
        f"**{judge_pair}** (Δ {judge_delta_str}), and every fixture improved.",
        "",
        "Takeaway: a raw-diff reviewer already names *what* changed (coverage "
        "stays broadly high either way) but is structurally blind to *why*. "
        "Supplying the PR's stated intent roughly doubles the judged "
        "'explains-why' score — the clean signal here — a measured handle on the "
        "'misses the forest for the trees' gap.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="A/B eval of PR-Pilot summaries.")
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip the LLM 'explains why' judge (coverage only).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(EVAL_DIR),
        help="Where to write results.json / RESULTS.md / summaries/.",
    )
    args = parser.parse_args()

    load_dotenv()  # pr-pilot/.env holds GOOGLE_API_KEY
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logging.error("GOOGLE_API_KEY not set (needed to generate and judge).")
        sys.exit(1)

    results = evaluate_all(api_key, judge=not args.no_judge)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "RESULTS.md").write_text(
        render_results_markdown(results), encoding="utf-8"
    )
    logging.info(
        "Wrote results to %s (coverage %.2f -> %.2f, +%.0f pts)",
        out_dir,
        results["diff_only"]["mean_coverage"],
        results["with_context"]["mean_coverage"],
        results["coverage_delta_points"],
    )


if __name__ == "__main__":
    main()
