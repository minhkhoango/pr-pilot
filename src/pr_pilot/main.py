# src/pr_pilot/main.py
import os
import argparse
import json
import sys
from typing import Dict, Any, List

import google.generativeai as genai
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
    ...


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
    ...


def generate_briefing(diff_content: str, api_key: str) -> Dict[str, Any]:
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
    ...


def format_markdown_briefing(briefing_data: Dict[str, Any]) -> str:
    """
    Formats the briefing data into a clean markdown string.

    Args:
        briefing_data: The dictionary containing briefing info.

    Returns:
        A formatted markdown string.
    """
    ...


def main() -> None:
    """
    Main function to run the script.
    """
    ...


if __name__ == "__main__":
    main()
