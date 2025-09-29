#!/bin/bash

# entrypoint.sh
# This script orchestrates the entire action. It uses the GitHub API
# to fetch the pull request diff and post the generated briefing back as a comment.

set -euo pipefail # Exit immediately if a command exits with a non-zero status, undefined vars, or pipe failures.

# --- Helper Functions ---
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    log "ERROR: $*" >&2
}

warn() {
    log "WARN: $*" >&2
}

info() {
    log "INFO: $*"
}

die() {
    error "$*"
    exit 1
}

# Check if required commands are available
check_dependencies() {
    local missing_deps=()

    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq")
    fi

    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        die "Missing required dependencies: ${missing_deps[*]}. Please ensure they are installed."
    fi
}

# Retry a command with exponential backoff
retry() {
    local max_attempts=3
    local delay=1
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        info "Attempt $attempt/$max_attempts: $*"

        if "$@"; then
            return 0
        fi

        if [ $attempt -lt $max_attempts ]; then
            warn "Command failed, retrying in ${delay}s..."
            sleep $delay
            delay=$((delay * 2))
        fi

        ((attempt++))
    done

    error "Command failed after $max_attempts attempts: $*"
    return 1
}

# Validate that a file contains actual content
validate_diff_file() {
    local file="$1"

    if [ ! -s "$file" ]; then
        die "Diff file is empty or does not exist: $file"
    fi

    # Check if the diff contains actual changes (not just meta information)
    if ! grep -q '^@@' "$file" && ! grep -q '^[+-]' "$file"; then
        warn "Diff file appears to contain no actual code changes, only metadata"
        return 1
    fi

    info "Diff file validation passed: $(wc -l < "$file") lines"
    return 0
}

# Validate JSON response
validate_json() {
    local json="$1"

    if [ -z "$json" ]; then
        die "Empty response received"
    fi

    # Try to parse the JSON to ensure it's valid
    if ! echo "$json" | jq empty &> /dev/null; then
        die "Invalid JSON received: $json"
    fi

    info "JSON validation passed"
}

# Make HTTP request with timeout and retry logic
make_github_request() {
    local url="$1"
    local method="${2:-GET}"
    local data="${3:-}"
    local accept_header="${4:-application/vnd.github+json}"
    local timeout=30

    local curl_args=(
        -s -L
        --max-time "$timeout"
        -w "%{http_code}"
        -H "Accept: $accept_header"
        -H "Authorization: Bearer ${GITHUB_AUTH_TOKEN}"
        -H "User-Agent: PR-Pilot/1.0"
    )

    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        curl_args+=(
            -X POST
            -H "Content-Type: application/json"
            --data-raw "$data"
        )
    fi


    # Execute the request
    local response
    local http_code
    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        response=$(curl "${curl_args[@]}" "$url" --data-raw "$data" 2>/dev/null || echo "curl_error")
    else
        response=$(curl "${curl_args[@]}" "$url" 2>/dev/null || echo "curl_error")
    fi

    # Handle curl failures
    if [ "$response" = "curl_error" ]; then
        error "GitHub API request failed - network error or timeout"
        return 1
    fi

    # Extract HTTP code (last 3 characters) and response body
    if [ ${#response} -ge 3 ]; then
        http_code="${response: -3}"
        local response_body="${response%???}"
    else
        http_code="000"
        local response_body="$response"
    fi

    # Validate HTTP code is numeric
    if ! [[ "$http_code" =~ ^[0-9]{3}$ ]]; then
        error "GitHub API request failed - invalid HTTP response format"
        return 1
    fi

    # Check HTTP status code
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo "$response_body"
        return 0
    else
        error "GitHub API request failed with HTTP $http_code"
        echo "$response_body"
        return 1
    fi
}

# --- 1. Get Inputs & Environment ---


# Check dependencies first
check_dependencies

# Debug: Show available INPUT_ environment variables
info "Available INPUT_ environment variables:"
env | grep "^INPUT_" || info "No INPUT_ variables found"

# Check for GitHub token in both INPUT_GITHUB_TOKEN and GITHUB_TOKEN
if [ -n "${INPUT_GITHUB_TOKEN:-}" ]; then
    GITHUB_AUTH_TOKEN="$INPUT_GITHUB_TOKEN"
    info "Using INPUT_GITHUB_TOKEN for authentication"
elif [ -n "${GITHUB_TOKEN:-}" ]; then
    GITHUB_AUTH_TOKEN="$GITHUB_TOKEN"
    info "Using GITHUB_TOKEN for authentication"
else
    die "Neither INPUT_GITHUB_TOKEN nor GITHUB_TOKEN is set. Please configure your GitHub token in repository secrets."
fi

if [ -z "${GOOGLE_API_KEY:-}" ]; then
    die "GOOGLE_API_KEY is not set. Please add it to your repository secrets."
fi

# Validate event payload exists
if [ ! -f "$GITHUB_EVENT_PATH" ]; then
    die "GitHub event payload not found at $GITHUB_EVENT_PATH"
fi

# Extract the API URL for the pull request from the event payload.
PR_URL=$(jq -r ".pull_request.url // empty" "$GITHUB_EVENT_PATH" 2>/dev/null)
if [ -z "$PR_URL" ] || [ "$PR_URL" = "null" ]; then
    die "Could not determine PR URL from event payload. Make sure this action is triggered by a pull request event."
fi

# The URL for posting comments is different from the main PR URL.
PR_COMMENTS_URL=$(jq -r ".pull_request.comments_url // empty" "$GITHUB_EVENT_PATH" 2>/dev/null)
if [ -z "$PR_COMMENTS_URL" ] || [ "$PR_COMMENTS_URL" = "null" ]; then
    warn "Could not determine PR comments URL from event payload. Will try to construct it from PR URL."
    # Extract the base URL and construct comments URL
    PR_COMMENTS_URL="${PR_URL}/comments"
fi

info "PR URL: $PR_URL"
info "PR Comments URL: $PR_COMMENTS_URL"

# --- 2. Fetch the PR Diff ---

info "Fetching diff from ${PR_URL}.diff"
# Use curl to request the diff format for the PR.
# -H adds the necessary headers for authentication and specifying the format.
# -L follows redirects.
# -o saves the output to a file named 'pr.diff'.

# Use the improved GitHub request function with retry logic
if ! retry make_github_request "${PR_URL}.diff" "GET" "" "application/vnd.github.v3.diff" > pr.diff; then
    die "Failed to fetch PR diff after retries. This might indicate GitHub API issues or network problems."
fi

# Validate the diff file
if ! validate_diff_file "pr.diff"; then
    warn "PR diff appears to be empty or contain no changes. This might be a PR with only metadata changes."
    # Continue anyway - the AI might still be able to provide some analysis
fi

# --- 3. Run the Python Engine ---

info "Running PR-Pilot analysis..."

# We pass the fetched diff file to our Python script and capture its stdout.
# The GOOGLE_API_KEY is passed as an environment variable to the python process.
# We add a pre-comment header to the captured output.

# Run the Python script with timeout and error handling
if ! BRIEFING_BODY=$(timeout 300 env GOOGLE_API_KEY="$GOOGLE_API_KEY" python /app/src/pr_pilot/main.py --diff-file pr.diff 2>&1); then
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        die "Python script timed out after 5 minutes. This might indicate an issue with the AI service or a very large diff."
    else
        die "Python script failed with exit code $EXIT_CODE. Output: $BRIEFING_BODY"
    fi
fi

# Validate the AI response
if [ -z "$BRIEFING_BODY" ]; then
    die "Python script returned empty response. The AI service might be unavailable or the diff might be invalid."
fi

# Clean up the response (remove any control characters or excessive whitespace)
BRIEFING_BODY=$(echo "$BRIEFING_BODY" | tr -d '\000-\008\013-\037' | sed 's/[[:space:]]*$//')

if [ -z "$BRIEFING_BODY" ]; then
    die "Python script returned only whitespace/control characters. This might indicate an issue with the AI response format."
fi

BRIEFING_HEADER="### 🚀 PR-Pilot Analysis
"
BRIEFING_MARKDOWN="${BRIEFING_HEADER}${BRIEFING_BODY}"

info "AI analysis completed successfully ($(echo "$BRIEFING_MARKDOWN" | wc -c) characters)"

# --- 4. Post the Briefing as a Comment ---

info "Posting briefing to ${PR_COMMENTS_URL}"

# We need to format the markdown content into a JSON payload.
# The `body` key contains our comment.
JSON_PAYLOAD=$(echo "$BRIEFING_MARKDOWN" | jq -R --slurp '{body: .}' 2>/dev/null)
if [ $? -ne 0 ] || [ -z "$JSON_PAYLOAD" ]; then
    die "Failed to create JSON payload. This might indicate an issue with the briefing content or jq command."
fi

# Validate JSON payload
if ! validate_json "$JSON_PAYLOAD"; then
    die "Invalid JSON payload created. This should not happen - please check the briefing content."
fi

# Use the improved GitHub request function with retry logic for posting
if ! retry make_github_request "${PR_COMMENTS_URL}" "POST" "$JSON_PAYLOAD" "application/vnd.github+json" > /dev/null; then
    die "Failed to post briefing after retries. This might indicate GitHub API issues, rate limiting, or permission problems."
fi

info "PR-Pilot briefing posted successfully!"

# Optional: Clean up the diff file
rm -f pr.diff

info "PR-Pilot analysis completed successfully!"
