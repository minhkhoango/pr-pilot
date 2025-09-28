# src/pr_pilot/main.py
import os
import argparse
import json
import sys
import logging
from typing import List, TypedDict, Literal

from google.generativeai.generative_models import GenerativeModel
from google.generativeai.client import configure  # type: ignore
from dotenv import load_dotenv

# --- Constants ---
# Using the latest Flash model available.
MODEL_NAME = "gemini-2.5-flash-lite"


# --- Type Definitions ---
class RiskAssessment(TypedDict):
    level: Literal["Low", "Medium", "High", "Unknown"]
    reasoning: str


class ChangeDetail(TypedDict):
    type: Literal["Added", "Modified", "Removed", "Refactored", "Unknown"]
    item: str
    details: List[str]


class FileChange(TypedDict):
    file_name: str
    changes: List[ChangeDetail]


class PRBriefing(TypedDict):
    summary: str
    file_changes: List[FileChange]
    risk_assessment: RiskAssessment


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
                "file_name": "Name of the file that was changed",
                "changes": [
                    {{
                        "type": "Added|Modified|Removed|Refactored",
                        "item": "A description of the high-level item (e.g., `JsonStore` class, a specific function).",
                        "details": [
                            "A very short, bullet-point description of a sub-change (e.g., `__init__`: Loads data, `save()`: Persists data)."
                        ]
                    }}
                ]
            }}
        ],
        "risk_assessment": {{
            "level": "Low|Medium|High",
            "reasoning": "A brief, single-sentence explanation for the assigned risk level."
        }}
    }}

    CRITICAL RULES:
    1.  **USE THE NESTED STRUCTURE.** For each file, describe high-level changes (like adding a class) in the `item` field, and specific sub-changes (like methods of that class) in the `details` array.
    2.  **SUMMARIZE LOGICALLY.** Group related line-level changes. For example, instead of listing every line modified for logging, summarize it as "Integrated the `logging` module."
    3.  **BE CONCISE.** Every description must be as short as possible. Use sentence fragments where appropriate.
    4.  **NO CONVERSATION.** Your entire output must be ONLY the JSON object.
    5.  **STICK TO THE FACTS.** Analyze only the provided diff.

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
    """
    logging.info(f"Loading diff file from '{file_path}'...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f"The file '{file_path}' was not found.")
        raise


def generate_briefing(diff_content: str, api_key: str | None) -> PRBriefing:
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
        # Clean the response to ensure it's valid JSON
        cleaned_response = (
            response.text.strip().replace("```json", "").replace("```", "").strip()
        )
        return json.loads(cleaned_response)
    except Exception as e:
        logging.error(f"AI model communication failed: {e}")
        logging.error(
            f"Received raw response: {response.text if response else 'No response'}"
        )
        raise


def format_markdown_briefing(briefing_data: PRBriefing) -> str:
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

    file_changes = briefing_data.get("file_changes", [])
    if not file_changes:
        lines.append("*No file changes were detailed.")
    else:
        for file_change in file_changes:
            lines.append(f"- **`{file_change.get('file_name', 'Unknown file')}`**")
            changes = file_change.get("changes", [])
            for change in changes:
                change_type = change.get("type", "Unknown")
                item = change.get("item", "No item description.")
                lines.append(f"  - **{change_type}:** {item}")
                details = change.get("details", [])
                for detail in details:
                    lines.append(f"    - {detail}")

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
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s: %(message)s"
    )
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
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not found.")

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
