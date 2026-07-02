# src/pr_pilot/quality_metrics.py
"""
Lightweight, LLM-free quality metric for PR-Pilot's generated briefings.

The metric answers one honest question: "did the generated summary actually
talk about the things that changed, or did it hand-wave?" It does this by
parsing the raw unified diff for the concrete, checkable facts a reviewer
would look for -- which files changed, and which functions/classes/blocks
those changes fall inside of (from the diff's hunk-header scope, which git
already computes for most common languages) -- and then measuring what
fraction of those facts are named, verbatim, somewhere in the generated
summary text.

This is deliberately not a semantic-similarity or LLM-judge metric: it is a
coverage/recall proxy over named entities, computed with plain string
matching, so it is fully deterministic, requires no API calls, and is cheap
enough to run in CI against fixture diffs.
"""

import re
from typing import NamedTuple


class DiffCoverageItems(NamedTuple):
    """The concrete, named facts extracted from a unified diff."""

    file_names: frozenset[str]
    symbol_names: frozenset[str]


_DIFF_GIT_LINE_RE = re.compile(r"^diff --git a/(?P<a_path>.+?) b/(?P<b_path>.+)$")
_HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@\s*(?P<scope>.*)$")
_PY_DEF_CLASS_RE = re.compile(r"^[+-]\s*(?:async\s+def|def|class)\s+(?P<name>\w+)")
_SH_FUNC_RE = re.compile(
    r"^[+-]?\s*(?:function\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{?\s*$"
)
_FUNC_CALL_SCOPE_RE = re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_TRAILING_SCOPE_NAME_RE = re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:?\s*$")


def extract_diff_coverage_items(diff_text: str) -> DiffCoverageItems:
    """
    Parses a unified git diff and extracts the concrete facts a faithful
    summary should mention: the changed file paths, and the function/class
    names those changes touch.

    Function/class names are recovered two ways, since a diff can come from
    any language: (1) git's own hunk-header scope (the text after the
    second "@@", which git derives from a language-aware heuristic for most
    common file types), and (2) a direct regex match on added/removed lines
    that look like a Python "def"/"class" statement or a shell
    "name() {" function definition. Both are best-effort static heuristics,
    not a real parser, so they intentionally err on the side of only
    picking up unambiguous, name-shaped tokens.

    Args:
        diff_text: Raw unified diff text (e.g. from `git diff` or `git show`).

    Returns:
        A DiffCoverageItems with the deduplicated file names and symbol
        names found in the diff.
    """
    file_names: set[str] = set()
    symbol_names: set[str] = set()

    for line in diff_text.splitlines():
        git_line_match = _DIFF_GIT_LINE_RE.match(line)
        if git_line_match is not None:
            file_names.add(git_line_match.group("b_path"))
            continue

        hunk_match = _HUNK_HEADER_RE.match(line)
        if hunk_match is not None:
            scope = hunk_match.group("scope").strip()
            if scope:
                # Prefer a "name(" call/definition-like token (covers both
                # "def foo(...)" and shell's "foo() {"); fall back to a bare
                # trailing identifier (covers "class Foo:").
                scope_name_match = _FUNC_CALL_SCOPE_RE.search(
                    scope
                ) or _TRAILING_SCOPE_NAME_RE.search(scope)
                if scope_name_match is not None:
                    symbol_names.add(scope_name_match.group("name"))
            continue

        py_match = _PY_DEF_CLASS_RE.match(line)
        if py_match is not None:
            symbol_names.add(py_match.group("name"))
            continue

        sh_match = _SH_FUNC_RE.match(line)
        if sh_match is not None and line.strip().lstrip("+-").rstrip().endswith(
            (")", "{", ") {")
        ):
            symbol_names.add(sh_match.group("name"))

    return DiffCoverageItems(
        file_names=frozenset(file_names), symbol_names=frozenset(symbol_names)
    )


def coverage_score(diff_text: str, summary_text: str) -> float:
    """
    Computes the fraction of a diff's named files and functions/classes
    that are explicitly mentioned (case-insensitive substring match)
    somewhere in the generated summary text.

    This is a cheap, deterministic proxy for "did the summary actually
    cover the changes, or just hand-wave with generic language." A summary
    that names the touched files and symbols scores high; a generic
    "improved some code" summary scores low or zero, regardless of how
    fluent it reads.

    A file counts as covered if either its full path or its basename
    appears in the summary. A symbol (function/class name) counts as
    covered if it appears anywhere in the summary text.

    Args:
        diff_text: Raw unified diff text the summary was generated from.
        summary_text: The generated natural-language/markdown summary to
            score against that diff.

    Returns:
        A float in [0.0, 1.0]: the fraction of extracted files+symbols that
        were named in the summary. Returns 1.0 (vacuously "fully covered")
        if the diff yielded no checkable file or symbol names at all, since
        there is nothing the summary could have failed to mention.
    """
    items = extract_diff_coverage_items(diff_text)
    total_item_count = len(items.file_names) + len(items.symbol_names)
    if total_item_count == 0:
        return 1.0

    summary_lower = summary_text.lower()

    def _file_is_covered(file_name: str) -> bool:
        basename = file_name.rsplit("/", 1)[-1]
        return file_name.lower() in summary_lower or basename.lower() in summary_lower

    covered_count = sum(1 for f in items.file_names if _file_is_covered(f))
    covered_count += sum(
        1 for s in items.symbol_names if s.lower() in summary_lower
    )
    return covered_count / total_item_count
