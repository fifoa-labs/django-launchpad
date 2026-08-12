"""
src/launchpad/templatetags/launchpad_tags.py

Template tags for loading renderer-neutral Launchpad trees and applying
optional presentation-only helpers.

Launchpad deliberately separates data loading from presentation.

Example:

    {% load launchpad_tags %}

    {% get_launchpad "primary_navigation" as navigation %}

    {% include "launchpad/generic/tree.html" with launchpad=navigation only %}

The current template context is passed to the reader, allowing configured
URLs such as ``@context.person.pk`` to resolve at render time.

Presentation helpers such as ``launchpad_pad`` operate only on already
resolved data. They never create database records or alter Launchpad
configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from django import template

from launchpad.readers import (
    ResolvedLaunchpad,
    ResolvedNode,
    get_launchpad as read_launchpad,
)

register = template.Library()


@dataclass(frozen=True, slots=True)
class _LaunchpadPlaceholder:
    """
    Internal render-only placeholder used to balance item collections.

    A placeholder is not a NavigationLink or LaunchpadNode and is never stored
    in the database or persistent cache.

    It exists only after Launchpad resolution and is intended for optional
    presentation balancing such as card grids.
    """

    is_placeholder: bool = True

    title: str = "More to Explore"
    short_title: str = "More to Explore"

    description: str = "New tools, reports, and operational insights will appear here."

    tooltip: str = ""
    aria_label: str = "More to Explore"
    cta_label: str = ""

    url: str = "#"
    target: str = ""
    rel: str = ""
    download: bool = False

    icon: dict[str, str] = field(
        default_factory=lambda: {
            "kind": "emoji",
            "value": "✨",
        },
    )

    enabled: bool = False
    disabled_reason: str = ""

    is_active: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    children: tuple[()] = ()

    @property
    def is_link(self) -> bool:
        """Return False because placeholders are not navigation links."""
        return False

    @property
    def is_section(self) -> bool:
        """Return False because placeholders are not structural sections."""
        return False

    @property
    def is_separator(self) -> bool:
        """Return False because placeholders are not separators."""
        return False

    @property
    def has_children(self) -> bool:
        """Return False because placeholders never contain children."""
        return False


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


def _pad_items(
    items: list[Any],
    *,
    multiple: int,
) -> list[Any]:
    """
    Pad an item collection to the requested multiple.

    Padding is presentation-only.

    Examples:

        5 items, multiple=2
            -> 6 items

        5 items, multiple=3
            -> 6 items

        5 items, multiple=4
            -> 8 items

        6 items, multiple=3
            -> unchanged

    Existing items are never mutated.

    Args:
        items:
            Resolved items to prepare for rendering.

        multiple:
            Positive number of items that should divide the final collection
            evenly.

    Returns:
        A new list containing the original items plus zero or more
        render-only placeholders.

    Raises:
        ValueError:
            If ``multiple`` is less than 1.
    """
    if multiple < 1:
        msg = "Launchpad padding multiple must be greater than 0."
        raise ValueError(msg)

    remainder = len(items) % multiple

    if remainder == 0:
        return list(items)

    placeholder_count = multiple - remainder

    return [
        *items,
        *(_LaunchpadPlaceholder() for _ in range(placeholder_count)),
    ]


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


@register.simple_tag
def launchpad_pad(
    items: list[ResolvedNode] | tuple[ResolvedNode, ...],
    *,
    multiple: int = 2,
) -> list[ResolvedNode | _LaunchpadPlaceholder]:
    """
    Return a presentation-only padded copy of resolved Launchpad items.

    The original resolved collection is never modified.

    This helper is optional. Projects that do not need visual balancing should
    render ``navigation.nodes`` directly.

    Example:

        {% get_launchpad "home" as navigation %}
        {% launchpad_pad navigation.nodes multiple=2 as cards %}

        {% for item in cards %}
            ...
        {% endfor %}

    ``multiple`` does not attempt to detect browser viewport width or CSS
    breakpoints. It simply pads the collection to a requested item multiple.

    Examples:

        multiple=2
            useful for paired layouts

        multiple=3
            useful for three-column presentation

        multiple=6
            useful when a renderer wants complete groups of six

    A placeholder is:

    - not persisted,
    - not cached,
    - not visible to the reader,
    - not part of permission evaluation,
    - and not a NavigationLink or LaunchpadNode.
    """
    return _pad_items(
        list(items),
        multiple=multiple,
    )


__all__ = [
    "get_launchpad",
    "launchpad_pad",
]
