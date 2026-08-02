"""
src/launchpad/templatetags/launchpad_tags.py

Template tags for loading renderer-neutral Launchpad trees.

Launchpad deliberately separates data loading from presentation.

Example:

    {% load launchpad_tags %}

    {% get_launchpad "primary_navigation" as navigation %}

    {% include "launchpad/generic/tree.html" with launchpad=navigation only %}

The current template context is passed to the reader, allowing configured
URLs such as ``@context.person.pk`` to resolve at render time.
"""

from __future__ import annotations

from typing import Any, cast

from django import template

from launchpad.readers import (
    ResolvedLaunchpad,
    get_launchpad as read_launchpad,
)

register = template.Library()


def _flatten_context(
    template_context: template.Context,
) -> dict[str, Any]:
    """
    Return the template context as a plain dictionary.

    Django's built-in literal context values are removed because they are
    implementation details rather than meaningful Launchpad context.
    """
    values = cast(
        "dict[str, Any]",
        template_context.flatten(),
    )

    values.pop("True", None)
    values.pop("False", None)
    values.pop("None", None)

    return values


@register.simple_tag(takes_context=True)
def get_launchpad(
    context: template.Context,
    code: str,
    user: Any | None = None,
    **context_overrides: Any,
) -> ResolvedLaunchpad:
    """
    Return a renderer-neutral Launchpad tree.

    The tag is intended primarily as an assignment tag:

        {% get_launchpad "primary_navigation" as navigation %}

    An explicit user may be supplied:

        {% get_launchpad "primary_navigation"
        user=request.user as navigation %}

    Additional context values may also be supplied:

        {% get_launchpad "person_actions" person=person as navigation %}
    """
    resolved_context = _flatten_context(
        context,
    )

    resolved_context.update(
        context_overrides,
    )

    request = resolved_context.get(
        "request",
    )

    if user is None:
        user = getattr(
            request,
            "user",
            resolved_context.get("user"),
        )

    return read_launchpad(
        str(code).strip(),
        user=user,
        request=request,
        context=resolved_context,
    )


__all__ = [
    "get_launchpad",
]
