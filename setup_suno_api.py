#!/usr/bin/env python3
"""
Setup and Run Suno API Server

This script automates the installation and running of the gcui-art/suno-api server,
which is required for the Suno MCP integration to work.

Requirements:
- Python 3.6+
- Git
- Node.js and npm

Usage:
    python setup_suno_api.py [--port PORT] [--install-only]

Environment variables needed:
    SUNO_COOKIE: Your Suno cookie from suno.com
    TWOCAPTCHA_KEY: Your 2Captcha API key

After running this script:
1. The Suno API server will be running at http://localhost:PORT
2. To use it with the Suno MCP server, set the BASE_URL in your .env file:
   SUNO_API_BASE_URL=http://localhost:PORT
3. Then run your MCP server with:
   python -m src.main
"""

import os
import sys
import argparse
import subprocess
import platform
import time
import webbrowser
from pathlib import Path

# Default port for the Suno API server
DEFAULT_PORT = 3000

def check_requirements():
    """Check if all required tools are installed."""
    requirements = {
        "git": "Git is required to clone the repository. Install it from https://git-scm.com/downloads",
        "node": "Node.js is required to run the Suno API. Install it from https://nodejs.org/",
        "npm": "npm is required to install dependencies. It should come with Node.js"
    }
    
    missing = []
    for cmd, message in requirements.items():
        try:
            subprocess.run([cmd, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            missing.append(f"{cmd}: {message}")
    
    if missing:
        print("Missing requirements:")
        for msg in missing:
            print(f"  - {msg}")
        return False
    return True

def check_env_vars():
    """Check if required environment variables are set."""
    required_vars = {
        "SUNO_COOKIE": "Your Suno cookie from suno.com/create (see README for instructions)",
        "TWOCAPTCHA_KEY": "Your 2Captcha API key (register at 2captcha.com)"
    }
    
    missing = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing.append(f"{var}: {description}")
    
    if missing:
        print("Missing environment variables:")
        for msg in missing:
            print(f"  - {msg}")
        return False
    return True

def clone_repository():
    """Clone the suno-api repository."""
    repo_dir = Path("suno-api")
    
    if repo_dir.exists():
        print(f"Repository directory {repo_dir} already exists.")
        return repo_dir
    
    print("Cloning suno-api repository...")
    subprocess.run(["git", "clone", "https://github.com/gcui-art/suno-api.git"], check=True)
    return repo_dir

def create_env_file(repo_dir):
    """Create .env file with required environment variables."""
    env_path = repo_dir / ".env"
    
    # Default browser settings
    browser = "chromium"  # chromium or firefox
    browser_ghost_cursor = "false"
    browser_locale = "en"
    browser_headless = "true"
    
    # Get environment variables
    suno_cookie = os.environ.get("SUNO_COOKIE", "")
    twocaptcha_key = os.environ.get("TWOCAPTCHA_KEY", "")
    
    # Create .env file content
    env_content = f"""SUNO_COOKIE={suno_cookie}
TWOCAPTCHA_KEY={twocaptcha_key}
BROWSER={browser}
BROWSER_GHOST_CURSOR={browser_ghost_cursor}
BROWSER_LOCALE={browser_locale}
BROWSER_HEADLESS={browser_headless}
"""
    
    # Write to .env file
    with open(env_path, "w") as f:
        f.write(env_content)
    
    print(f"Created .env file at {env_path}")

def install_dependencies(repo_dir):
    """Install npm dependencies."""
    print("Installing dependencies (this may take a few minutes)...")
    subprocess.run(["npm", "install"], cwd=repo_dir, check=True)

def run_server(repo_dir, port):
    """Run the Suno API server."""
    # Set the port in the environment
    env = os.environ.copy()
    env["PORT"] = str(port)
    
    print(f"Starting Suno API server on port {port}...")
    print("Press Ctrl+C to stop the server")
    
    # Run the server
    process = None
    try:
        process = subprocess.Popen(["npm", "run", "dev"], cwd=repo_dir, env=env)
        
        # Wait for server to start
        print("Waiting for server to start...")
        time.sleep(5)
        
        # Test the API endpoint
        test_url = f"http://localhost:{port}/api/get_limit"
        print(f"Testing API endpoint: {test_url}")
        
        # Try to connect to the API for up to 30 seconds
        max_attempts = 6
        for attempt in range(max_attempts):
            try:
                import requests
                import json
                response = requests.get(test_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if all(key in data for key in ["credits_left", "monthly_limit", "monthly_usage"]):
                        print("\n✅ API is running successfully!")
                        print(f"API Response: {json.dumps(data, indent=2)}")
                        print("\nSuno API is ready to use with your MCP server.")
                        break
                    else:
                        print(f"Warning: API response missing expected fields: {data}")
                else:
                    print(f"Attempt {attempt+1}/{max_attempts}: API returned status code {response.status_code}")
            except requests.RequestException as e:
                if attempt < max_attempts - 1:
                    print(f"Attempt {attempt+1}/{max_attempts}: API not ready yet ({str(e)}). Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    print(f"Error: Could not connect to API after {max_attempts} attempts.")
                    print("The server might still be starting up. Check the browser or try again later.")
        
        # Open the API test endpoint in browser
        print(f"Opening test endpoint in browser: {test_url}")
        webbrowser.open(test_url)
        
        # Keep the server running until interrupted
        print("\nServer is running. Press Ctrl+C to stop.")
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping server...")
        if process:
            process.terminate()
            process.wait()
    except Exception as e:
        print(f"Error running server: {e}")
        if process:
            process.terminate()
            process.wait()

def main():
    """Main function to set up and run the Suno API server."""
    parser = argparse.ArgumentParser(description="Set up and run the Suno API server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to run the server on (default: {DEFAULT_PORT})")
    parser.add_argument("--install-only", action="store_true", help="Install dependencies but don't run the server")
    args = parser.parse_args()
    
    print("=== Suno API Setup and Run ===")
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check for requests package
    try:
        import requests
    except ImportError:
        print("Installing requests package for API testing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        print("Requests package installed successfully.")
    
    # Check environment variables
    if not check_env_vars():
        print("\nPlease set the required environment variables and try again.")
        print("You can set them in your shell before running this script:")
        if platform.system() == "Windows":
            print("  set SUNO_COOKIE=your_cookie_value")
            print("  set TWOCAPTCHA_KEY=your_api_key")
        else:
            print("  export SUNO_COOKIE=your_cookie_value")
            print("  export TWOCAPTCHA_KEY=your_api_key")
        sys.exit(1)
    
    try:
        # Clone repository
        repo_dir = clone_repository()
        
        # Create .env file
        create_env_file(repo_dir)
        
        # Install dependencies
        install_dependencies(repo_dir)
        
        # If install-only flag is set, exit after installation
        if args.install_only:
            print("\n✅ Installation complete!")
            print(f"To run the server later, use: python {sys.argv[0]} --port {args.port}")
            sys.exit(0)
        
        # Run server
        run_server(repo_dir, args.port)
    except subprocess.SubprocessError as e:
        print(f"Error in subprocess: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
