"""Tests for CLI module."""

import pytest
from xcuitest_goblin.cli import create_parser, EXIT_SUCCESS, EXIT_PROJECT_NOT_FOUND


def test_create_parser():
    """Test that parser is created successfully."""
    parser = create_parser()
    assert parser is not None


def test_parser_has_analyze_command():
    """Test that parser has analyze subcommand."""
    parser = create_parser()
    # Parse with analyze command and a dummy path
    args = parser.parse_args(["analyze", "/tmp/test"])
    assert args.command == "analyze"
    assert args.project_path == "/tmp/test"


def test_parser_default_output():
    """Test default output directory."""
    parser = create_parser()
    args = parser.parse_args(["analyze", "/tmp/test"])
    assert args.output == "./analysis/"


def test_parser_default_format():
    """Test default format."""
    parser = create_parser()
    args = parser.parse_args(["analyze", "/tmp/test"])
    assert args.format == "json,html"


def test_parser_custom_options():
    """Test custom options parsing."""
    parser = create_parser()
    args = parser.parse_args([
        "analyze", "/tmp/test",
        "--output", "/custom/output",
        "--format", "json",
        "--verbose"
    ])
    assert args.output == "/custom/output"
    assert args.format == "json"
    assert args.verbose is True


def test_exit_codes_defined():
    """Test that exit codes are defined."""
    assert EXIT_SUCCESS == 0
    assert EXIT_PROJECT_NOT_FOUND == 3
