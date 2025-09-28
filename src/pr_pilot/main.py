# src/pr_pilot/main.py
import os
import argparse
import json
import sys
import logging
from typing import Dict, Any, List

from google.generativeai.generative_models import GenerativeModel
from google.generativeai.client import configure  # type: ignore
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
    You are PR-Pilot, an expert software engineer reviewing a pull request.
    Your task is to analyze the following git diff and generate a structured JSON object.

    The JSON object must follow this exact schema:
    {{
      "summary": "A single, concise sentence summarizing the PR's core purpose.",
      "file_changes": [
        {{
          "file_name": "The full path of the file that was changed.",
          "changes": [
            "A very short, bullet-point description of a specific change. Start with 'Added:', 'Modified:', 'Removed:', or 'Refactored:'."
          ]
        }}
      ],
      "risk_assessment": {{
        "level": "Low|Medium|High",
        "reasoning": "A brief, single-sentence explanation for the assigned risk level."
      }}
    }}

    CRITICAL RULES:
    1.  **BE CONCISE.** Every description must be as short as possible. No long paragraphs. Use sentence fragments where appropriate.
    2.  **NO CONVERSATION.** Your entire output must be ONLY the JSON object. Do not include markdown, apologies, or any text before or after the JSON.
    3.  **STICK TO THE FACTS.** Analyze only the provided diff. Do not infer intent or functionality beyond the code shown.

    Analyze this diff:
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
    logging.info(f"Loading diff file from '{file_path}'...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f"The file '{file_path}' was not found.")
        raise


def generate_briefing(diff_content: str, api_key: str | None) -> Dict[str, Any]:
    """
    Calls the Gemini API to generate the PR briefing.

    Args:
        diff_content: The git diff content.
        api_key: The Google AI API key.

    Returns:
        A dictionary parsed from the API's JSON response.
    """
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set.")

    configure(api_key=api_key)
    model: GenerativeModel = GenerativeModel(MODEL_NAME)
    prompt: str = generate_prompt(diff_content)

    logging.info("Generating briefing from AI model...")
    response = None
    try:
        response = model.generate_content(prompt)  # type: ignore
        # The response text might be wrapped in ```json ... ```, so we clean it.
        cleaned_response = (
            response.text.strip().replace("```json", "").replace("```", "").strip()
        )
        return json.loads(cleaned_response)
    except Exception as e:
        logging.error(f"AI model communication failed: {e}")
        logging.error(f"Received raw response: {response.text if response else 'No response'}")
        raise


def format_markdown_briefing(briefing_data: Dict[str, Any]) -> str:
    """
    Formats the briefing data into a clean markdown string.

    Args:
        briefing_data: The dictionary containing briefing info.

    Returns:
        A formatted markdown string.
    """
    lines = [
        "\n---\n",
        "#### 📝 **Overall Summary**\n",
        briefing_data.get("summary", "No summary provided."),
        "\n",
        "#### 🗂️ **File-by-File Breakdown**\n",
    ]

    file_changes: List[Dict[str, Any]] = briefing_data.get("file_changes", [])
    if not file_changes:
        lines.append("*No file changes were detailed.")
    else:
        for file_change in file_changes:
            lines.append(f"- **`{file_change.get('file_name', 'Unknown file')}`**")
            changes = file_change.get("changes", [])
            for change in changes:
                lines.append(f"  - {change}")

    lines.append("\n#### 🚨 **Risk Assessment**\n")
    risk = briefing_data.get("risk_assessment", {})
    risk_level = risk.get("level", "Unknown")
    risk_reason = risk.get("reasoning", "No reasoning provided.")
    lines.append(f"- **{risk_level} Risk:** {risk_reason}")

    return "\n".join(lines)


def main() -> None:
    """
    Main function to run the script.
    """
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(levelname)s: %(message)s')
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

        print(markdown_output)

    except (FileNotFoundError, ValueError) as e:
        logging.error(f"A configuration or file error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
