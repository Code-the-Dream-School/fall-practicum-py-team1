import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = next(
    (
        parent
        for parent in BASE_DIR.parents
        if (parent / ".env").is_file()
    ),
    None,
)

if PROJECT_ROOT is not None:
    load_dotenv(PROJECT_ROOT / ".env")


OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PROMPT_VERSION = "v1"