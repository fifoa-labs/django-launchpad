"""
tests/test_apps.py

Tests for the Launchpad Django application configuration.
"""

from __future__ import annotations

from django.apps import apps


def test_launchpad_app_config() -> None:
    """Django should register the Launchpad application correctly."""
    config = apps.get_app_config("launchpad")

    assert config.name == "launchpad"
    assert config.verbose_name == "Launchpad"
