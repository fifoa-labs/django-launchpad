"""
src/launchpad/templatetags/launchpad_tags/presentation.py

Optional presentation helpers for resolved Launchpad data.

Presentation helpers operate only on data that has already passed through
Launchpad resolution. They never create database records, alter Launchpad
configuration, participate in visibility evaluation, or modify persistent
cache data.

The responsive padding helper provides one render-only placeholder that may
expand to consume the unused portion of a responsive grid row.

The default layout matches a common Bootstrap card grid:

- xs: 1 column
- sm: 2 columns
- md: 3 columns
- lg: 4 columns
- xl: 6 columns

The placeholder is hidden at breakpoints where the real items already fill
their final row exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .registry import register

if TYPE_CHECKING:
    from launchpad.readers import ResolvedNode


_DEFAULT_BREAKPOINT_COLUMNS = (
    ("", 1),
    ("sm", 2),
    ("md", 3),
    ("lg", 4),
    ("xl", 6),
)


@dataclass(frozen=True, slots=True)
class _LaunchpadPlaceholder:
    """
    Internal render-only placeholder used to balance responsive grids.

    A placeholder is not a NavigationLink or LaunchpadNode and is never stored
    in the database or persistent cache.

    Its responsive CSS classes allow one placeholder to appear only where a
    grid has unused space and to expand across exactly that unused space.
    """

    classes: str

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


def _column_class(
    breakpoint: str,  # noqa: A002
    *,
    span: int,
) -> str:
    """Return one responsive Bootstrap column class."""
    if breakpoint:
        return f"col-{breakpoint}-{span}"

    return f"col-{span}"


def _display_class(
    breakpoint: str,  # noqa: A002
    *,
    visible: bool,
) -> str:
    """Return one responsive Bootstrap display class."""
    display = "block" if visible else "none"

    if breakpoint:
        return f"d-{breakpoint}-{display}"

    return f"d-{display}"


def _padding_span(
    item_count: int,
    *,
    columns: int,
) -> int | None:
    """
    Return the Bootstrap grid span needed to complete one row.

    Bootstrap rows use twelve grid units.

    If the real items already complete the row, return ``None``.

    Examples:

        3 items / 2 columns
            remainder = 1
            missing = 1
            span = 6

        16 items / 3 columns
            remainder = 1
            missing = 2
            span = 8

        16 items / 4 columns
            remainder = 0
            no placeholder
    """
    if columns < 1:
        msg = "Launchpad grid columns must be greater than 0."
        raise ValueError(msg)

    if 12 % columns != 0:
        msg = "Launchpad grid columns must divide evenly into 12."
        raise ValueError(msg)

    remainder = item_count % columns

    if remainder == 0:
        return None

    missing_columns = columns - remainder
    units_per_column = 12 // columns

    return missing_columns * units_per_column


def _responsive_padding_classes(
    item_count: int,
) -> str | None:
    """
    Return responsive classes for one balancing placeholder.

    The placeholder is explicitly shown or hidden at every supported
    breakpoint so display behavior does not leak upward from a smaller
    breakpoint.

    Returns ``None`` when no breakpoint requires padding.
    """
    classes: list[str] = []
    has_visible_breakpoint = False

    for breakpoint, columns in _DEFAULT_BREAKPOINT_COLUMNS:  # noqa: A001
        span = _padding_span(
            item_count,
            columns=columns,
        )

        visible = span is not None

        classes.append(
            _display_class(
                breakpoint,
                visible=visible,
            ),
        )

        if span is None:
            continue

        has_visible_breakpoint = True

        classes.append(
            _column_class(
                breakpoint,
                span=span,
            ),
        )

    if not has_visible_breakpoint:
        return None

    return " ".join(classes)


def _build_placeholder(
    item_count: int,
) -> _LaunchpadPlaceholder | None:
    """Return one responsive placeholder when any breakpoint needs padding."""
    classes = _responsive_padding_classes(
        item_count,
    )

    if classes is None:
        return None

    return _LaunchpadPlaceholder(
        classes=classes,
    )


@register.simple_tag
def launchpad_pad(
    items: list[ResolvedNode] | tuple[ResolvedNode, ...],
) -> _LaunchpadPlaceholder | None:
    """
    Return one optional responsive balancing placeholder.

    Real Launchpad items are never copied, replaced, or modified.

    The placeholder is visible only at breakpoints where the final row has
    unused space. Its width expands to consume exactly that unused portion.

    With the default 1 / 2 / 3 / 4 / 6-column grid, three real items behave
    like:

        xs:
            1 / 1 / 1
            no placeholder

        sm:
            2 / 1
            placeholder fills the remaining 1 column

        md:
            3
            no placeholder

        lg:
            3 + placeholder spanning 1 column

        xl:
            3 + placeholder spanning 3 columns

    Templates may ignore this helper entirely when balancing is unnecessary.
    """
    return _build_placeholder(
        len(items),
    )


__all__ = [
    "launchpad_pad",
]
