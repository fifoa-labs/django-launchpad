"""
src/launchpad/templatetags/launchpad_tags/__init__.py

Django template-tag library for django-launchpad.

Templates load the complete Launchpad tag library with:

    {% load launchpad_tags %}
"""

from __future__ import annotations

from .base import get_launchpad
from .presentation import launchpad_pad
from .registry import register

__all__ = [
    "get_launchpad",
    "launchpad_pad",
    "register",
]
