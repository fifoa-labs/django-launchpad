"""
tests/test_apps.py

Tests for the Launchpad Django application configuration.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from django.apps import apps

from launchpad import apps as launchpad_apps
from launchpad.apps import LaunchpadConfig

if TYPE_CHECKING:
    import pytest


def test_launchpad_app_config() -> None:
    """Django should register the Launchpad application correctly."""
    config = apps.get_app_config("launchpad")

    assert config.name == "launchpad"
    assert config.verbose_name == "Launchpad"
    assert config.default_auto_field == "django.db.models.BigAutoField"


def test_launchpad_app_ready_registers_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """App startup should import Launchpad signal registrations."""
    imported: list[str] = []

    original_import_module = importlib.import_module

    def import_module(
        name: str,
        package: str | None = None,
    ) -> Any:
        imported.append(name)
        return original_import_module(
            name,
            package,
        )

    monkeypatch.setattr(
        launchpad_apps,
        "import_module",
        import_module,
    )

    config = LaunchpadConfig(
        "launchpad",
        importlib.import_module("launchpad"),
    )

    config.ready()

    assert imported == [
        "launchpad.signals",
    ]
