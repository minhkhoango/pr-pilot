#!/bin/bash

# entrypoint.sh
# This script orchestrates the entire action. It uses the GitHub API
# to fetch the pull request diff and post the generated briefing back as a comment.

set -e # Exit immediately if a command exits with a non-zero status.

# --- 1. Get Inputs & Environment ---
# The INPUT_GITHUB_TOKEN is automatically provided by GitHub.
# The GITHUB_EVENT_PATH contains the JSON payload of the event that triggered the workflow.
# We use `jq` (a command-line JSON processor) to parse this file.

# Debug: Show available INPUT_ environment variables
echo "DEBUG: Available INPUT_ environment variables:"
env | grep "^INPUT_" || echo "No INPUT_ variables found"

# Check for GitHub token in both INPUT_GITHUB_TOKEN and GITHUB_TOKEN
if [ -n "$INPUT_GITHUB_TOKEN" ]; then
    GITHUB_AUTH_TOKEN="$INPUT_GITHUB_TOKEN"
    echo "INFO: Using INPUT_GITHUB_TOKEN for authentication"
elif [ -n "$GITHUB_TOKEN" ]; then
    GITHUB_AUTH_TOKEN="$GITHUB_TOKEN"
    echo "INFO: Using GITHUB_TOKEN for authentication"
else
    echo "Error: Neither INPUT_GITHUB_TOKEN nor GITHUB_TOKEN is set."
    echo "DEBUG: All environment variables:"
    env | sort
    exit 1
fi

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "Error: GOOGLE_API_KEY is not set. Please add it to your repository secrets."
    exit 1
fi

# Extract the API URL for the pull request from the event payload.
PR_URL=$(jq -r ".pull_request.url" "$GITHUB_EVENT_PATH")
if [ -z "$PR_URL" ]; then
    echo "Error: Could not determine PR URL from event payload."
    exit 1
fi

# The URL for posting comments is different from the main PR URL.
PR_COMMENTS_URL=$(jq -r ".pull_request.comments_url" "$GITHUB_EVENT_PATH")


# --- 2. Fetch the PR Diff ---
echo "INFO: Fetching diff from ${PR_URL}.diff"
# Use curl to request the diff format for the PR.
# -H adds the necessary headers for authentication and specifying the format.
# -L follows redirects.
# -o saves the output to a file named 'pr.diff'.
HTTP_CODE=$(curl -s -L -w "%{http_code}" -o pr.diff \
  -H "Accept: application/vnd.github.v3.diff" \
  -H "Authorization: Bearer ${GITHUB_AUTH_TOKEN}" \
  "${PR_URL}")

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "INFO: Diff saved to pr.diff"
else
    echo "❌ Failed to fetch PR diff. HTTP Status: $HTTP_CODE"
    exit 1
fi

# --- 3. Run the Python Engine ---
echo "INFO: Running PR-Pilot analysis..."
# We pass the fetched diff file to our Python script and capture its stdout.
# The GOOGLE_API_KEY is passed as an environment variable to the python process.
# We add a pre-comment header to the captured output.
BRIEFING_HEADER="### 🚀 PR-Pilot Analysis"
BRIEFING_BODY=$(GOOGLE_API_KEY=$GOOGLE_API_KEY python /app/src/pr_pilot/main.py --diff-file pr.diff)

# Combine header and body
BRIEFING_MARKDOWN="${BRIEFING_HEADER}${BRIEFING_BODY}"

# --- 4. Post the Briefing as a Comment ---
echo "INFO: Posting briefing to ${PR_COMMENTS_URL}"
# We need to format the markdown content into a JSON payload.
# The `body` key contains our comment.
JSON_PAYLOAD=$(echo "$BRIEFING_MARKDOWN" | jq -R --slurp '{body: .}')

# Use curl again to POST the JSON payload to the PR's comments URL.
# Check the HTTP response code to ensure the request succeeded.
HTTP_STATUS=$(curl -s -L -w "%{http_code}" \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  "${PR_COMMENTS_URL}" \
  --data-raw "$JSON_PAYLOAD")

# Extract the response body (everything except the last 3 characters which are the status code)
RESPONSE_BODY="${HTTP_STATUS%???}"
HTTP_CODE="${HTTP_STATUS: -3}"

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "✅ PR-Pilot briefing posted successfully!"
else
    echo "❌ Failed to post briefing. HTTP Status: $HTTP_CODE"
    echo "Response: $RESPONSE_BODY"
    exit 1
fi