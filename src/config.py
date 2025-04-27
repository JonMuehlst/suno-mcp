"""Handles loading configuration from environment variables."""

import os
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# Suno API Credentials
SUNO_COOKIE = os.getenv("SUNO_COOKIE")
SUNO_SESSION_ID = os.getenv("SUNO_SESSION_ID")
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

# 2Captcha API Key
TWOCAPTCHA_API_KEY = os.getenv("TWOCAPTCHA_API_KEY")

# MCP Server Configuration (Optional)
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8080"))

# --- Add validation or default values as needed ---

if not SUNO_COOKIE:
    print("Warning: SUNO_COOKIE environment variable not set.")
# Add more checks as necessary, potentially raising errors if critical config is missing

print("Configuration loaded.") # Optional: confirmation message
