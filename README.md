# PR-Pilot

PR-Pilot is a GitHub Action that acts as an **AI Intelligence Officer** for your code reviews. It automatically analyzes pull requests and posts a structured, high-signal briefing comment, giving reviewers instant context so they can focus on what matters.

To quickly try out pr-pilot, go to https://github.com/minhkhoango/pr-pilot-sandbox and make a simple pull request!

<img src="assets/image.png" alt="PR-Pilot GitHub Action Demo" width="600">

## The Problem: Review Overload

Pull request reviews are critical for quality, but they're often a bottleneck. Reviewers face **immense cognitive load**, trying to reconstruct the *why* behind hundreds of lines of changes across dozens of files. This leads to slow reviews, low-quality feedback ("LGTM"), and team friction.

## The Solution: An Automated Briefing

PR-Pilot solves this by creating the briefing a senior engineer would, automatically. It reads the raw diff and delivers a **concise, factual summary** directly to the PR thread. It provides the context one team member needs, without demanding extra "performance theatre" from another.

By analyzing the git diff, PR-Pilot provides objective, factual summaries — so human reviewers can focus on what really matters.

## Quick Start: 3 Steps to Launch

Get PR-Pilot running in your repository in under 5 minutes.

### 1. Create the Workflow File

In your repository, create a new file at `.github/workflows/pr-pilot.yml` and paste the following content:

```yml
name: "PR-Pilot Briefing"

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  pull-requests: write
  contents: read

jobs:
  briefing:
    runs-on: ubuntu-latest
    steps:
      - name: Run PR-Pilot analysis
        uses: minhkhoango/pr-pilot@v1.0.0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
```

### 2. Add Your API Key

PR-Pilot uses the Google Gemini API to generate its analysis.

1.  Go to [Google AI Studio](https://aistudio.google.com/app/apikey) and get your API key.
2.  In your GitHub repository, go to **Settings > Secrets and variables > Actions**.
3.  Click **New repository secret**.
4.  Name the secret `GOOGLE_API_KEY`.
5.  Paste your API key into the value field and save.

### 3. Open a Pull Request

That's it. The next time a pull request is opened, PR-Pilot will post its briefing as a comment.

## What PR-Pilot Is (and Is Not)

Managing expectations is key to a successful tool.

**PR-Pilot Is:**

- **An Intelligence Officer for Code**: It analyzes the diff to create a factual summary of *what* changed.
- **A Context Builder**: It helps reviewers understand the scope and nature of changes at a glance.
- **A Time Saver**: It automates the tedious task of summarizing work, letting engineers focus on building and reviewing.

**PR-Pilot Is Not:**

- **A Code Quality Linter**: It will not critique your coding style or suggest alternative implementations.
- **A Business Logic Expert**: It analyzes the code, not your company's internal processes. It won't understand the domain-specific implications of a change.
- **A Replacement for Human Review**: It's a tool to assist human reviewers, not replace their critical judgment.

## Known Limitations

- **The Architect Blindspot**: For very large, multi-faceted PRs (e.g., a major architectural refactor across 15+ files), the pilot currently provides an accurate file-by-file summary but may miss the single overarching strategic theme that connects all the changes.
- **The Intent Gap**: For certain types of changes, like porting a file from one language to another, the pilot will correctly identify that one file was removed and another was added, but may not infer the high-level intent of a "language migration."

## License

This project is licensed under the MIT License.
