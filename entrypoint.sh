#!/bin/sh -l

# entrypoint.sh
# This script will eventually be responsible for getting the PR diff
# from the GitHub context and calling the Python tool.

echo "🚀 PR-Pilot is running!"

# Placeholder for future logic:
# 1. Get PR number from GitHub event payload.
# 2. Use GitHub API with GITHUB_TOKEN to fetch the .diff for the PR.
# 3. Save the diff to a temporary file.
# 4. Run the python script: python src/pr_pilot/main.py --diff-file /tmp/pr.diff
# 5. Get the markdown output.
# 6. Use GitHub API to post the markdown as a comment on the PR.

echo "✅ PR-Pilot execution finished (placeholder)."
