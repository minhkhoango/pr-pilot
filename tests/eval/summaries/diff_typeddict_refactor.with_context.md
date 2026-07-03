
---

#### 📝 **Overall Summary**

Fixes the PR briefing generation by introducing explicit TypedDicts for nested file changes, ensuring the prompt schema matches the markdown formatter's expectations and preventing missing file sections in rendered briefings.


#### 🗂️ **File-by-File Breakdown**

- **`src/pr_pilot/main.py`**
  - **Added:** Introduced `RiskAssessment`, `ChangeDetail`, `FileChange`, and `PRBriefing` TypedDicts.
    - Defines explicit shapes for the AI's response.
    - Ensures the prompt schema aligns with the markdown formatter's expected nested structure.
  - **Modified:** Updated type hints for `generate_briefing` and `format_markdown_briefing` functions.
    - Changed return type of `generate_briefing` from `Dict[str, Any]` to `PRBriefing`.
    - Changed parameter type of `format_markdown_briefing` from `Dict[str, Any]` to `PRBriefing`.
  - **Modified:** Adjusted the JSON schema example in `generate_prompt`.
    - Replaced flat `changes` key with nested `file_changes` structure.
    - Updated example `file_changes` and `changes` structure to match new TypedDicts.
  - **Modified:** Updated access patterns within `format_markdown_briefing`.
    - Changed dictionary key access (e.g., `briefing_data.get('file_changes', [])`) to be more robust with the new TypedDict structure.

#### 🚨 **Risk Assessment**

- **Low Risk:** This change primarily involves type definition and schema alignment, with minimal impact on core logic and no direct user-facing functionality changes.