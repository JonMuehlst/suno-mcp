import os
import pytest
from dotenv import load_dotenv

# Attempt to import the mcp instance from your main application file
# This assumes tests are run from the project root directory or PYTHONPATH is set.
try:
    from src.main import mcp
except ImportError as e:
    print(f"Failed to import mcp from src.main: {e}")
    print("Ensure your PYTHONPATH includes the project root or run tests using 'python -m unittest discover'.")
    mcp = None # Set to None to handle import failure gracefully in tests
except Exception as e:
    print(f"An unexpected error occurred during import: {e}")
    mcp = None

# Load environment variables before tests run.
load_dotenv()
# Check if SUNO_COOKIE is present, though not strictly needed for these basic tests
suno_cookie_present = bool(os.getenv("SUNO_COOKIE"))
if not suno_cookie_present:
    print("\nWarning: SUNO_COOKIE not found in environment. Lifespan initialization might log warnings.")


def test_mcp_instance_imported():
    """Verify that the MCP instance (mcp) could be imported from src.main."""
    assert mcp is not None, "MCP instance (mcp) failed to import from src.main."


def test_tools_registered():
    """Verify that the expected tools are registered with the MCP instance."""
    if mcp is None:
        pytest.skip("Skipping tool registration test because MCP instance failed to import.")

    expected_tools = {"generate_song", "custom_generate_song"}
    # Access registered tools via the .tools attribute of the FastMCP instance
    registered_tools = set(mcp.tools.keys())

    assert expected_tools.issubset(registered_tools), \
        f"Expected tools {expected_tools} not found or not fully registered. Registered tools: {registered_tools}"


def test_resource_handler_registered():
    """Verify that the 'suno' resource handler is registered."""
    if mcp is None:
        pytest.skip("Skipping resource handler test because MCP instance failed to import.")

    # Access registered resource handlers via the .resource_handlers attribute
    assert "suno" in mcp.resource_handlers, \
        "Expected resource handler 'suno' not found in mcp.resource_handlers."
