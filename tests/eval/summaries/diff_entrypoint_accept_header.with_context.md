
---

#### 📝 **Overall Summary**

Fixes the action to request the unified diff for a PR instead of JSON by appending `.diff` to the URL and parameterizing the Accept header, and hardens HTTP code extraction to fail loudly on malformed responses.


#### 🗂️ **File-by-File Breakdown**

- **`entrypoint.sh`**
  - **Modified:** Parameterize the Accept header in the `make_github_request` function.
    - Added a new parameter `accept_header` with a default value.
    - Used the `accept_header` parameter in the `curl` command.
    - Modified the extraction of HTTP code and response body to be more robust.
    - Added validation for numeric HTTP codes.
  - **Modified:** Update the PR diff fetching logic to use the `.diff` suffix and the correct Accept header.
    - Appended `.diff` to the `PR_URL` when calling `make_github_request`.
    - Passed `application/vnd.github.v3.diff` as the Accept header for diff fetching.
  - **Modified:** Ensure the correct Accept header is used when posting PR comments.
    - Passed `application/vnd.github+json` as the Accept header for POST requests.

#### 🚨 **Risk Assessment**

- **Low Risk:** The changes are focused on correctly fetching PR diffs and handling API responses, with added robustness, minimizing the risk of introducing new bugs.