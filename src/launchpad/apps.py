"""
src/launchpad/apps.py

Django application configuration for Launchpad.
"""

from __future__ import annotations

from django.apps import AppConfig


class LaunchpadConfig(AppConfig):
    """Configure the Launchpad Django application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "launchpad"
    verbose_name = "Launchpad"
