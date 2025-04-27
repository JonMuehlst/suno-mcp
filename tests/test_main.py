import os
import sys
import pytest
import traceback
from dotenv import load_dotenv

# Add project root to path to ensure imports work correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Attempt to import the mcp instance from your main application file
try:
    # Make sure we're importing from the correct location
    from src.main import mcp
    import_success = True
except ImportError as e:
    print(f"\nFailed to import mcp from src.main: {e}")
    print(f"Current sys.path: {sys.path}")
    print("Ensure your PYTHONPATH includes the project root or run tests using 'python -m pytest'.")
    mcp = None  # Set to None to handle import failure gracefully in tests
    import_success = False
except Exception as e:
    print(f"\nAn unexpected error occurred during import:")
    traceback.print_exc()
    mcp = None
    import_success = False

# Load environment variables before tests run.
load_dotenv()
# Check if SUNO_COOKIE is present, though not strictly needed for these basic tests
suno_cookie_present = bool(os.getenv("SUNO_COOKIE"))
if not suno_cookie_present:
    print("\nWarning: SUNO_COOKIE not found in environment. Lifespan initialization might log warnings.")


def test_mcp_instance_imported():
    """Verify that the MCP instance (mcp) could be imported from src.main."""
    if not import_success:
        pytest.fail("MCP instance (mcp) failed to import from src.main. Check the import error above.")
    assert mcp is not None, "MCP instance (mcp) failed to import from src.main."


def test_tools_registered():
    """Verify that the expected tools are registered with the MCP instance."""
    if mcp is None:
        pytest.skip("Skipping tool registration test because MCP instance failed to import.")

    # Import the manually maintained set of registered tools
    from src.main import registered_tools
    
    expected_tools = {"generate_song", "custom_generate_song"}
    
    # Check if all expected tools are in the registered_tools set
    for tool in expected_tools:
        assert tool in registered_tools, f"Tool '{tool}' is not registered"


def test_resource_handler_registered():
    """Verify that the resource handler for 'suno://' URIs is registered."""
    if mcp is None:
        pytest.skip("Skipping resource handler test because MCP instance failed to import.")

    # Import the manually maintained set of registered resource handlers
    from src.main import registered_resource_handlers
    
    # Check if the 'suno' scheme is registered
    assert "suno" in registered_resource_handlers, \
        f"Resource handler for 'suno://' URIs not found. Registered handlers: {registered_resource_handlers}"
