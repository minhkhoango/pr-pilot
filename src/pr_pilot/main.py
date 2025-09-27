# src/pr_pilot/main.py
from google.generativeai.types.generation_types import GenerateContentResponse
from google.generativeai.generative_models import GenerativeModel
from google.generativeai.client import configure  # type: ignore
import os
import argparse
import json
import sys
from typing import Dict, Any, List

from dotenv import load_dotenv

# --- Constants ---
# Using the latest Flash model available.
MODEL_NAME = "gemini-2.5-flash-lite"


def generate_prompt(diff_content: str) -> str:
    """
    Engineers the prompt to be sent to the AI model.

    Args:
        diff_content: A string containing the git diff.

    Returns:
        A formatted prompt string.
    """
    return f"""
    You are PR-Pilot, an expert senior software engineer. Your sole purpose is to analyze a given git diff and provide a structured, objective briefing for the pull request reviewer.

    Analyze the following git diff and generate a JSON object that contains the briefing.

    The JSON object must follow this exact schema:
    {{
      "summary": "A high-level, concise summary of the pull request's purpose and overall change.",
      "file_changes": [
        {{
          "file_name": "The full path of the file that was changed.",
          "changes": [
            "A clear, bullet-point-style description of a specific change made within that file.",
            "Another description of a change in the same file."
          ]
        }}
      ],
      "risk_assessment": {{
        "level": "Low|Medium|High",
        "reasoning": "A detailed explanation for the assigned risk level, pointing out potential side effects, critical code modifications, or lack of error handling."
      }}
    }}

    IMPORTANT RULES:
    1.  Do NOT critique the code or suggest any changes.
    2.  The output MUST be a single, valid JSON object. Do not include any text or markdown before or after the JSON.
    3.  Base your analysis solely on the provided diff. Do not invent context.
    4.  The "changes" for each file should be a list of strings, not a single string.

    Here is the git diff:
    ```diff
    {diff_content}
    ```
    """


def load_diff_file(file_path: str) -> str:
    """
    Loads the content of the specified diff file.

    Args:
        file_path: The path to the .diff file.

    Returns:
        The content of the file as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    print(f"INFO: Loading diff file from '{file_path}'...")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: The file '{file_path}' was not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_briefing(diff_content: str, api_key: str | None) -> Dict[str, Any]:
    """
    Calls the Gemini API to generate the PR briefing.

    Args:
        diff_content: The git diff content.
        api_key: The Google AI API key.

    Returns:
        A dictionary parsed from the API's JSON response.

    Raises:
        ValueError: If the API key is missing.
        Exception: For any other API-related errors.
    """
    if not api_key:
        raise ValueError(
            "Error: GOOGLE_API_KEY is not set. Please create a .env file or set the environment variable."
        )

    print("INFO: Configuring AI model...")
    configure(api_key=api_key)
    model: GenerativeModel = GenerativeModel(MODEL_NAME)

    prompt: str = generate_prompt(diff_content)

    print("INFO: Generating briefing from AI. This may take a moment...")
    try:
        response: GenerateContentResponse = model.generate_content(prompt)  # type: ignore
        # The response text might be wrapped in ```json ... ```, so we clean it.
        cleaned_response = (
            response.text.strip().replace("```json", "").replace("```", "").strip()
        )
        return json.loads(cleaned_response)
    except Exception as e:
        print(
            f"FATAL: An error occurred while communicating with the AI model: {e}",
            file=sys.stderr,
        )
        raise


def format_markdown_briefing(briefing_data: Dict[str, Any]) -> str:
    """
    Formats the briefing data into a clean markdown string.

    Args:
        briefing_data: The dictionary containing briefing info.

    Returns:
        A formatted markdown string.
    """
    markdown_lines = [
        "### 🚀 PR-Pilot Briefing\n",
        "**A high-level summary of changes to help you start your review.**",
        "\n---\n",
        "#### 📝 **Overall Summary**\n",
        briefing_data.get("summary", "No summary provided."),
        "\n",
        "#### 🗂️ **File-by-File Breakdown**\n",
    ]

    file_changes: List[Dict[str, Any]] = briefing_data.get("file_changes", [])
    if not file_changes:
        markdown_lines.append("* No file changes were detailed.")
    else:
        for file_change in file_changes:
            markdown_lines.append(
                f"* **`{file_change.get('file_name', 'Unknown file')}`**:"
            )
            changes = file_change.get("changes", [])
            if not changes:
                markdown_lines.append("    * No specific changes were detailed.")
            else:
                for change in changes:
                    markdown_lines.append(f"    * {change}")

    markdown_lines.append("\n#### 🚨 **Risk Assessment**\n")
    risk = briefing_data.get("risk_assessment", {})
    risk_level = risk.get("level", "Unknown")
    risk_reason = risk.get("reasoning", "No reasoning provided.")

    markdown_lines.append(f"* **{risk_level} Risk:** {risk_reason}")

    return "\n".join(markdown_lines)


def main() -> None:
    """
    Main function to run the script.
    """
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate a PR briefing from a .diff file."
    )
    parser.add_argument(
        "--diff-file",
        type=str,
        required=True,
        help="Path to the .diff file to analyze.",
    )
    args = parser.parse_args()

    try:
        api_key: str | None = os.getenv("GOOGLE_API_KEY")
        diff_content = load_diff_file(args.diff_file)
        briefing_json = generate_briefing(diff_content, api_key)
        markdown_output = format_markdown_briefing(briefing_json)

        print("\n--- GENERATED BRIEFING ---\n")
        print(markdown_output)
        print("\n--- END OF BRIEFING ---\n")

    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
