"""Handles loading configuration from environment variables."""

import os
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# Required Suno API Cookie
SUNO_COOKIE = os.getenv("SUNO_COOKIE")

# Optional Default Suno Model
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "chirp-v3-5")

# --- Validation ---

if not SUNO_COOKIE:
    raise ValueError("Critical environment variable SUNO_COOKIE is not set.")

# You can add more checks here if needed in the future.
