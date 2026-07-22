"""
setup_env.py
------------
Checks for a .env file and creates one with placeholder values if missing.
Also verifies that required API keys are populated before the pipeline runs.
"""

import os
import subprocess
import sys
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"

ENV_TEMPLATE = """\
# Recruitment Automation – Environment Variables
# Replace the placeholder values below with your actual API keys.

GEMINI_API_KEY=your_gemini_api_key_here
PROXYCURL_API_KEY=your_proxycurl_api_key_here
"""


def create_env_file() -> None:
    """Create a .env file with placeholder keys if it does not already exist."""
    if not ENV_FILE.exists():
        ENV_FILE.write_text(ENV_TEMPLATE, encoding="utf-8")
        print(f"[setup_env] Created .env file at: {ENV_FILE}")
        print("[setup_env] ⚠  Please fill in your API keys in the .env file before running the pipeline.")
    else:
        print(f"[setup_env] .env file already exists at: {ENV_FILE}")


def verify_api_keys() -> bool:
    """
    Load the .env file and check that both API keys have been filled in.
    Returns True if both keys are set to non-placeholder values, False otherwise.
    """
    # Import here so dotenv is available after pip install
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=ENV_FILE, override=True)
    except ImportError:
        print("[setup_env] python-dotenv not installed – skipping key verification.")
        return False

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    proxycurl_key = os.getenv("PROXYCURL_API_KEY", "")

    issues = []
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        issues.append("GEMINI_API_KEY")
    if not proxycurl_key or proxycurl_key == "your_proxycurl_api_key_here":
        issues.append("PROXYCURL_API_KEY")

    if issues:
        print(f"[setup_env] ❌ Missing or placeholder API keys: {', '.join(issues)}")
        print("[setup_env]    Update your .env file and re-run the pipeline.")
        return False

    print("[setup_env] ✅ All API keys verified successfully.")
    return True


def install_dependencies() -> None:
    """Install packages listed in requirements.txt using pip."""
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print("[setup_env] requirements.txt not found – skipping dependency installation.")
        return

    try:
        from dotenv import load_dotenv
        import openpyxl
        import pandas
        print("[setup_env] ✅ Core dependencies verified.")
        return
    except ImportError:
        pass

    print("[setup_env] Installing dependencies from requirements.txt …")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("[setup_env] ✅ Dependencies installed successfully.")
    else:
        print("[setup_env] ℹ️ Dependency check notice (continuing execution).")


def initialize() -> bool:
    """
    Full initialization routine:
      1. Create .env if missing
      2. Install Python dependencies
      3. Verify API keys
    Returns True if setup is complete and keys are valid.
    """
    create_env_file()
    install_dependencies()
    return verify_api_keys()


if __name__ == "__main__":
    success = initialize()
    sys.exit(0 if success else 1)
