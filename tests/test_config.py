"""Tests for configuration module."""

import pytest
from xcuitest_goblin.config import get_config, load_config, DEFAULT_THRESHOLDS


def test_default_config_exists():
    """Test that default thresholds are defined."""
    assert DEFAULT_THRESHOLDS is not None
    assert isinstance(DEFAULT_THRESHOLDS, dict)


def test_default_config_has_sections():
    """Test that default config has expected sections."""
    assert "test_inventory" in DEFAULT_THRESHOLDS
    assert "accessibility_ids" in DEFAULT_THRESHOLDS
    assert "test_plans" in DEFAULT_THRESHOLDS


def test_get_config_returns_config_object():
    """Test that get_config returns a Config object."""
    from xcuitest_goblin.config import Config
    config = get_config()
    assert isinstance(config, Config)
    # Config should have thresholds property that returns a dict
    assert isinstance(config.thresholds, dict)


def test_load_config_without_file():
    """Test that load_config works without a config file."""
    # Should not raise an exception
    load_config(None)
    config = get_config()
    assert config is not None
