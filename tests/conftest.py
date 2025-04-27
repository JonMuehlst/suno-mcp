import os
import sys
import pytest

# Add the project root to the Python path
@pytest.fixture(scope="session", autouse=True)
def setup_python_path():
    """Add the project root to the Python path for all tests."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    yield
