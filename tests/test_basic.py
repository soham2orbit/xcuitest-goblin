"""Basic tests for xcuitest-goblin."""

import pytest
from xcuitest_goblin import __version__


def test_version():
    """Test that version is defined."""
    assert __version__ is not None
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_format():
    """Test that version follows semver format."""
    parts = __version__.split(".")
    assert len(parts) >= 2
    # First two parts should be numeric
    assert parts[0].isdigit()
    assert parts[1].isdigit()
