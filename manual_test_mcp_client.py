"""
Test script for verifying the Suno MCP server's internal logic using the FastMCP Client.

This script imports the MCP instance directly from src.main and runs it *in-process*.
It does NOT connect to an external HTTP server. It tests the tool registration and
basic functionality by interacting with the MCP object directly.

Usage:
Run this script directly from the project root directory:
   python manual_test_mcp_client.py

It will initialize the necessary components (like the Suno client) and attempt
to call the 'generate_song' tool internally.
"""

import asyncio
import sys
from fastmcp import Client

async def test_server():
    """
    Test the MCP server by connecting to it and calling a tool.
    This approach works with both HTTP and stdio transport modes.
    """
    try:
        # Import the MCP server instance directly from your module
        from src.main import mcp, init_suno_client
        print("Successfully imported MCP server from src.main")
        
        # Initialize the Suno client before testing
        print("Initializing Suno client for testing...")
        await init_suno_client()
        
        # Initialize the client with the FastMCP instance
        print("Connecting to MCP server...")
        async with Client(mcp) as client:
            # List available tools to verify connection
            tools = await client.list_tools()
            print(f"Connected successfully! Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            
            # Try to call a simple tool if available
            if any(tool.name == "generate_song" for tool in tools):
                print("\nTesting 'generate_song' tool with a simple prompt...")
                try:
                    result = await client.call_tool(
                        "generate_song", 
                        {"prompt": "Test prompt: short happy melody", "instrumental": True}
                    )
                    print(f"Tool execution successful!")
                    
                    # Handle different response formats
                    if hasattr(result, 'content') and result.content:
                        print(f"Response: {result.content[0].text[:100]}...")
                    elif hasattr(result, 'text'):
                        print(f"Response: {result.text[:100]}...")
                    elif isinstance(result, str):
                        print(f"Response: {result[:100]}...")
                    else:
                        print(f"Response type: {type(result)}")
                        print(f"Response details: {result}")
                except Exception as e:
                    print(f"Error calling tool: {e}")
            else:
                print("\nThe 'generate_song' tool was not found. Available tools:")
                for tool in tools:
                    print(f"  - {tool.name}")
                    
            print("\nServer verification complete!")
            
    except ImportError as e:
        print(f"Error importing MCP server: {e}")
        print("Make sure you're running this script from the project root directory.")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    
    return True

def main():
    """Run the async test function and return appropriate exit code."""
    success = asyncio.run(test_server())
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
