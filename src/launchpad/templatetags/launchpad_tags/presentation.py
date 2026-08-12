"""
src/launchpad/templatetags/launchpad_tags/presentation.py

Optional presentation helpers for resolved Launchpad data.

Presentation helpers operate only on data that has already passed through
Launchpad resolution. They never create database records, alter Launchpad
configuration, participate in visibility evaluation, or modify persistent
cache data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .registry import register

if TYPE_CHECKING:
    from launchpad.readers import ResolvedNode


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


def _pad_items(
    items: list[Any],
    *,
    multiple: int,
) -> list[Any]:
    """
    Pad an item collection to the requested multiple.

    Padding is presentation-only.

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
    """
    return _pad_items(
        list(items),
        multiple=multiple,
    )


__all__ = [
    "launchpad_pad",
]
