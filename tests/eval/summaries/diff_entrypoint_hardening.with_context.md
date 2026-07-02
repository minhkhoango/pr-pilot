
---

#### 📝 **Overall Summary**

Enhance the entrypoint.sh script to be more production-resilient by adding retry logic for GitHub API requests, per-request timeouts, upfront dependency checks, and clearer error handling to prevent transient failures from aborting the action.


#### 🗂️ **File-by-File Breakdown**

- **`entrypoint.sh`**
  - **Modified:** Improve script robustness and error handling
    - Replaced `set -e` with `set -euo pipefail` for stricter error checking.
    - Added helper functions for logging (`log`, `error`, `warn`, `info`, `die`).
    - Implemented `check_dependencies` to verify `jq` and `curl` are available.
    - Introduced `retry` function with exponential backoff for transient API errors.
    - Added `validate_diff_file` to check for empty or non-standard diffs.
    - Added `validate_json` to ensure API responses are valid JSON.
    - Created `make_github_request` function to encapsulate API calls with timeouts and retry logic.
    - Enhanced input validation for GitHub token and Google API key.
    - Improved error messages for missing inputs and event payload issues.
    - Integrated `retry` and `make_github_request` into diff fetching and comment posting.
    - Added a timeout to the Python script execution using `timeout` command.
    - Cleaned up AI script output and added validation for empty or whitespace-only responses.
    - Removed the `jq -R --slurp` for creating the JSON payload and used `jq -R --slurp '{body: .}'` directly.
    - Added cleanup for the `pr.diff` file.

#### 🚨 **Risk Assessment**

- **Low Risk:** The changes focus on improving the reliability and error handling of the existing script without altering its core functionality or introducing new external dependencies.