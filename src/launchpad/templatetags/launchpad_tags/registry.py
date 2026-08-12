"""
src/launchpad/templatetags/launchpad_tags/registry.py

Shared Django template-tag registry for django-launchpad.
"""

from __future__ import annotations

from django import template

register = template.Library()


__all__ = [
    "register",
]
