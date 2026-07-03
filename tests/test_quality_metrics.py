# tests/test_quality_metrics.py
"""
Tests for the diff-coverage quality metric (src/pr_pilot/quality_metrics.py).

Each fixture in tests/fixtures/ is a real diff pulled straight from this
repo's own git history (`git show <commit>`), so the test is exercising the
metric against genuine PR-Pilot-shaped input rather than synthetic text. For
each real diff we pair it with two hand-written summaries: a "good" one that
actually names the files/functions/classes that changed (the way a careful
human reviewer, or a well-behaved LLM, would write it), and a "bad" one that
is generic filler of the kind an LLM produces when it is hand-waving instead
of reading the diff. The test asserts the metric scores the good summary
meaningfully higher than the bad one, which is the property that makes this
a useful quality signal in the first place.
"""

from pathlib import Path

import pytest

from pr_pilot.quality_metrics import coverage_score, extract_diff_coverage_items

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(file_name: str) -> str:
    return (FIXTURES_DIR / file_name).read_text(encoding="utf-8")


# --- Fixture: refactor from loose Dict[str, Any] typing to strict TypedDicts ---
TYPEDDICT_DIFF = _load_fixture("diff_typeddict_refactor.diff")
TYPEDDICT_GOOD_SUMMARY = (
    "Refactored src/pr_pilot/main.py to replace loose Dict[str, Any] typing "
    "with strict TypedDicts (RiskAssessment, ChangeDetail, FileChange, "
    "PRBriefing), and updated generate_briefing and format_markdown_briefing "
    "to use the new PRBriefing type."
)
TYPEDDICT_BAD_SUMMARY = (
    "Made some improvements and cleaned up the code for better readability."
)

# --- Fixture: entrypoint.sh gains a configurable Accept header ---
ENTRYPOINT_DIFF = _load_fixture("diff_entrypoint_accept_header.diff")
ENTRYPOINT_GOOD_SUMMARY = (
    "Updated entrypoint.sh: make_github_request now accepts a configurable "
    "accept_header parameter, fixing the missing .diff suffix bug."
)
ENTRYPOINT_BAD_SUMMARY = (
    "Fixed a bug in the script and improved error handling overall."
)

# --- Fixture: README docs tweak ---
README_DIFF = _load_fixture("diff_readme_docs.diff")
README_GOOD_SUMMARY = (
    "Updated README.md to add a link to the Hacker News discussion."
)
README_BAD_SUMMARY = "Minor documentation tweak."


@pytest.mark.parametrize(
    "diff_text,good_summary,bad_summary",
    [
        (TYPEDDICT_DIFF, TYPEDDICT_GOOD_SUMMARY, TYPEDDICT_BAD_SUMMARY),
        (ENTRYPOINT_DIFF, ENTRYPOINT_GOOD_SUMMARY, ENTRYPOINT_BAD_SUMMARY),
        (README_DIFF, README_GOOD_SUMMARY, README_BAD_SUMMARY),
    ],
    ids=["typeddict_refactor", "entrypoint_accept_header", "readme_docs"],
)
def test_coverage_score_discriminates_good_from_bad_summary(
    diff_text: str, good_summary: str, bad_summary: str
) -> None:
    good_score = coverage_score(diff_text, good_summary)
    bad_score = coverage_score(diff_text, bad_summary)

    assert good_score > bad_score
    assert good_score >= 0.5
    assert bad_score <= 0.1


def test_coverage_score_is_perfect_when_summary_repeats_the_whole_diff() -> None:
    # A summary that literally contains the diff text must cover every
    # extracted file/symbol name, since each name was extracted from that
    # same text.
    assert coverage_score(TYPEDDICT_DIFF, TYPEDDICT_DIFF) == 1.0


def test_coverage_score_is_zero_for_completely_unrelated_summary() -> None:
    unrelated_summary = "The weather today is sunny with a light breeze."
    assert coverage_score(TYPEDDICT_DIFF, unrelated_summary) == 0.0


def test_coverage_score_returns_one_when_diff_has_no_extractable_items() -> None:
    # A diff with no "diff --git" header and no hunk headers yields no
    # checkable file/symbol names, so there is nothing for the summary to
    # have missed.
    empty_diff = "not a real diff, just plain text"
    assert coverage_score(empty_diff, "anything goes here") == 1.0


def test_extract_diff_coverage_items_finds_expected_file_and_symbols() -> None:
    items = extract_diff_coverage_items(TYPEDDICT_DIFF)

    assert "src/pr_pilot/main.py" in items.file_names
    assert "PRBriefing" in items.symbol_names
    assert "generate_briefing" in items.symbol_names
    assert "format_markdown_briefing" in items.symbol_names


def test_extract_diff_coverage_items_finds_shell_function_scope() -> None:
    items = extract_diff_coverage_items(ENTRYPOINT_DIFF)

    assert "entrypoint.sh" in items.file_names
    assert "make_github_request" in items.symbol_names


# --- Larger, messier fixtures (added for the eval A/B) ------------------------
# A big single-file hardening diff and a 5-file cleanup diff. These have many
# named symbols, so we assert the discrimination property (good names the
# entities, generic filler does not) without a brittle upper bound on the bad
# score -- messy diffs surface short scope tokens (e.g. "so", "log") that a
# generic sentence can match incidentally.
HARDENING_DIFF = _load_fixture("diff_entrypoint_hardening.diff")
HARDENING_GOOD_SUMMARY = (
    "Hardened entrypoint.sh for production: wrapped make_github_request in retry "
    "with a timeout, added a check_dependencies preflight, validate_diff_file and "
    "validate_json guards, and die/error/info/warn logging helpers."
)
HARDENING_BAD_SUMMARY = "Improved the shell script's reliability and robustness."

MULTIFILE_DIFF = _load_fixture("diff_multifile_cleanup.diff")
MULTIFILE_GOOD_SUMMARY = (
    "Removed the unused .env.example and assets/sample.diff, and tidied "
    "README.md, entrypoint.sh, and src/pr_pilot/main.py -- trimming "
    "generate_briefing, main, and load_dotenv."
)
MULTIFILE_BAD_SUMMARY = "Deleted a couple files and made minor cleanups."


@pytest.mark.parametrize(
    "diff_text,good_summary,bad_summary",
    [
        (HARDENING_DIFF, HARDENING_GOOD_SUMMARY, HARDENING_BAD_SUMMARY),
        (MULTIFILE_DIFF, MULTIFILE_GOOD_SUMMARY, MULTIFILE_BAD_SUMMARY),
    ],
    ids=["entrypoint_hardening", "multifile_cleanup"],
)
def test_coverage_score_discriminates_on_messy_diffs(
    diff_text: str, good_summary: str, bad_summary: str
) -> None:
    good_score = coverage_score(diff_text, good_summary)
    bad_score = coverage_score(diff_text, bad_summary)

    assert good_score > bad_score
    assert good_score >= 0.5


def test_extract_diff_coverage_items_finds_all_files_in_multifile_diff() -> None:
    items = extract_diff_coverage_items(MULTIFILE_DIFF)

    assert {
        ".env.example",
        "README.md",
        "assets/sample.diff",
        "entrypoint.sh",
        "src/pr_pilot/main.py",
    } <= items.file_names


def test_extract_diff_coverage_items_finds_hardening_shell_symbols() -> None:
    items = extract_diff_coverage_items(HARDENING_DIFF)

    assert "entrypoint.sh" in items.file_names
    assert {"retry", "make_github_request", "check_dependencies"} <= items.symbol_names
