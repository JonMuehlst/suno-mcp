"""
Simple script to test if the Suno MCP server is running properly via HTTP.

This script checks if an *already running* MCP server is accessible via HTTP.
It does NOT start the server itself.

Usage:
1. Start the MCP server in HTTP mode in one terminal:
   python -m src.main --http
   (Ensure it's running on the expected host/port, default is localhost:8000)

2. Run this script in another terminal:
   python manual_test_mcp_server.py [URL]
   (If URL is omitted, it defaults to http://localhost:8000/health)
"""

import subprocess
import sys
import time
import os

def check_server_status(url="http://localhost:8000/health", max_retries=3, retry_delay=2):
    """
    Check if the MCP server is running by making a curl request to its health endpoint.
    
    Args:
        url: The URL to check, including the health endpoint
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        True if server is running, False otherwise
    """
    print(f"Testing MCP server availability at {url}...")
    
    # Determine the curl command based on the platform
    curl_cmd = "curl" if os.name != "nt" else "curl.exe"
    
    # Build the curl command
    cmd = [
        curl_cmd, 
        "-s",                  # Silent mode
        "-o", "NUL" if os.name == "nt" else "/dev/null",  # Discard output
        "-w", "%{http_code}",  # Output only the status code
        "-m", "5",             # Timeout after 5 seconds
        url
    ]
    
    for attempt in range(1, max_retries + 1):
        try:
            # Run the curl command
            result = subprocess.run(cmd, capture_output=True, text=True)
            status_code = result.stdout.strip()
            
            # Check if we got a successful status code
            if status_code == "200":
                print(f"✅ Success! MCP server is running (Status code: {status_code})")
                return True
            else:
                print(f"❌ Attempt {attempt}/{max_retries}: Server returned status code: {status_code}")
        except subprocess.SubprocessError as e:
            print(f"❌ Attempt {attempt}/{max_retries}: Error executing curl: {e}")
        
        # If we haven't succeeded and have more retries, wait before trying again
        if attempt < max_retries:
            print(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    
    print("❌ Failed to connect to the MCP server after multiple attempts.")
    print("\nTroubleshooting tips:")
    print("1. Make sure the server is running")
    print("2. Check if the port is correct (default is 8000)")
    print("3. Verify that curl is installed and accessible in your PATH")
    print("4. Check your firewall settings")
    return False

def main():
    # Default URL for FastMCP server health check
    default_url = "http://localhost:8000/health"  # FastMCP uses port 8000 by default for HTTP mode
    
    # Allow custom URL from command line argument
    url = sys.argv[1] if len(sys.argv) > 1 else default_url
    
    # Check server status
    success = check_server_status(url)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
