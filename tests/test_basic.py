"""Basic tests to verify setup."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import ai_agent_platform


def test_package_version():
    """Test that package version is correctly set."""
    assert ai_agent_platform.__version__ == "1.0.0"


def test_package_metadata():
    """Test that package metadata is correctly set."""
    assert ai_agent_platform.__author__ == "AI Agent Platform Team"
    assert ai_agent_platform.__email__ == "dev@company.com"