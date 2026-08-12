"""
src/launchpad/apps.py

Django application configuration for Launchpad.
"""

from __future__ import annotations

from importlib import import_module

from django.apps import AppConfig


class LaunchpadConfig(AppConfig):
    """Configure the Launchpad Django application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "launchpad"
    verbose_name = "Launchpad"

    def ready(self) -> None:
        """Register Launchpad signal handlers."""
        import_module(
            "launchpad.signals",
        )
