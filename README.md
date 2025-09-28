# PR-Pilot  
*An AI-powered briefing officer for your pull requests. Get context, not critique.*

---

## The Problem: The Great War of the PR  
Pull request reviews are the backbone of quality software — but they often turn into bottlenecks.  
Reviewers face immense cognitive load: scanning dozens of files, hundreds of lines, and sparse descriptions while trying to reconstruct the *why* behind a change.  

---

## The Solution: Your Reviewer's Command Center  
PR-Pilot is your automated **briefing officer**, delivering a **single, structured, high-signal briefing** that instantly equips reviewers with context.  

By analyzing the git diff, PR-Pilot provides objective, factual summaries — so human reviewers can focus on what really matters.

---

## The MVP Promise  

### What PR-Pilot **Does**:
- **Summarizes Intent:** Explains the high-level purpose of the pull request.  
- **Breaks Down Changes:** Provides a file-by-file walkthrough in plain English.  
- **Assesses Potential Risk:** Flags areas with hidden side effects or touching critical code paths.  

### What PR-Pilot **Does NOT Do**:
- Critique code quality or style  
- Suggest alternative implementations  
- Replace human reviewers  

---

## Example Briefing  


### 🚀 PR-Pilot Analysis
---

#### 📝 **Overall Summary**

Refines PR-Pilot's prompt, type definitions, and error handling for more structured and robust AI-driven pull request analysis.


#### 🗂️ **File-by-File Breakdown**

- **`.env.example`**
  - **Removed:** Removed unused .env.example file.
- **`README.md`**
  - **Modified:** Cleaned up and standardized markdown formatting.
- **`assets/sample.diff`**
  - **Removed:** Removed example diff file.
- **`entrypoint.sh`**
  - **Modified:** Simplified the PR-Pilot briefing header.
- **`src/pr_pilot/main.py`**
  - **Modified:** Enhanced AI prompt for structured JSON output and stricter adherence to rules.
    - Introduced explicit type definitions for PR briefing components (RiskAssessment, ChangeDetail, FileChange, PRBriefing).
    - Improved error handling for file loading and AI API communication.
    - Added logging for better diagnostics.

#### 🚨 **Risk Assessment**

- **Low Risk:** Changes primarily focus on prompt engineering, type safety, and logging, with no direct impact on core functionality.