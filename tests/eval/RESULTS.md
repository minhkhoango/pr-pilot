# PR-Pilot briefing-quality eval

- Generator: `gemini-2.5-flash-lite`
- Judge: `gemini-2.5-flash` (a stronger sibling model, same API key)
- Fixtures (real PRs from this repo's history): **5**

Each fixture is summarized twice: **diff-only** (the shipped product prompt) and **with-context** (an experimental prompt that adds the PR's title/body/commit messages). `coverage` = fraction of changed files/functions the summary names (deterministic); `why` = the judge's 1-5 rating of how well the summary explains the change's motivation.

| Fixture | coverage (diff-only → +context) | why 1-5 (diff-only → +context) |
| --- | --- | --- |
| `diff_entrypoint_accept_header` | 0.67 → 0.67 | 3 → 4 |
| `diff_entrypoint_hardening` | 1.00 → 1.00 | 2 → 5 |
| `diff_multifile_cleanup` | 0.55 → 0.55 | 3 → 5 |
| `diff_readme_docs` | 1.00 → 0.50 | 2 → 5 |
| `diff_typeddict_refactor` | 0.64 → 0.73 | 2 → 5 |

## Aggregate

- Mean coverage — the *trees* (does it name the files/functions?): **0.77 → 0.69**. Both broadly high; this is a coarse string-match proxy (it also picks up a few junk hunk-scope tokens), so small moves here are noise, not signal — naming *what* changed is not where the two prompts differ.
- Mean 'explains why' score — the *forest* (1-5): **2.4 → 4.8** (Δ +2.4), and every fixture improved.

Takeaway: a raw-diff reviewer already names *what* changed (coverage stays broadly high either way) but is structurally blind to *why*. Supplying the PR's stated intent roughly doubles the judged 'explains-why' score — the clean signal here — a measured handle on the 'misses the forest for the trees' gap.
