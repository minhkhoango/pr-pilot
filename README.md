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


### PR-Pilot Briefing  
*A high-level summary of changes to help you start your review.*  

---

#### Overall Summary  
This PR introduces a new `JsonStore` class for handling session data with JSON persistence.  
It also refactors `BaseStore` to be more generic and updates `main.py` to use this new storage mechanism.

---

#### 🗂️ File-by-File Breakdown  
- **`src/storage.py`**  
  - **Added:** `JsonStore` class  
    - `__init__`: Loads initial data and sets file path  
    - `set(key, value)`: Adds/updates key-value pairs  
    - `get(key)`: Retrieves a value by key  
    - `save()`: Persists session data to JSON  
  - **Modified:** `BaseStore` simplified into a minimal abstract template  

- **`src/main.py`**  
  - **Modified:** Now instantiates `JsonStore` for session management  

---

#### 🚨 Risk Assessment  
- **Medium Risk:** `JsonStore.save()` writes directly to disk with no error handling. Disk failures or permission issues could cause data loss.  
- **Low Risk:** Swap in `main.py` is straightforward; as long as `JsonStore` follows the expected interface, regression risk is minimal.  

---

BRUH FOR TESTING !!!