"""
tests/test_templatetags_launchpad_tags_registry.py

Tests for the shared Launchpad template-tag registry.
"""

from __future__ import annotations

from django import template

from launchpad.templatetags.launchpad_tags import registry


def test_register_is_django_template_library() -> None:
    """The shared registry should be a Django template Library."""
    assert isinstance(
        registry.register,
        template.Library,
    )


def test_registry_module_exports_register() -> None:
    """The registry module should expose only the shared registry."""
    assert registry.__all__ == [
        "register",
    ]
