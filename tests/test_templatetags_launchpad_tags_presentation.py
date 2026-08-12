"""
tests/test_templatetags_launchpad_tags_presentation.py

Tests for optional responsive Launchpad presentation helpers.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.template import Context, Template

from launchpad.models import NavigationLink
from launchpad.templatetags.launchpad_tags import presentation
from tests.builders import (
    build_request,
    create_launchpad,
    create_link_node,
    create_navigation_link,
    create_user,
)

pytestmark = pytest.mark.django_db


def _render(
    source: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Render an in-memory Django template."""
    return Template(source).render(
        Context(context or {}),
    )


@pytest.mark.parametrize(
    ("item_count", "columns", "expected"),
    [
        (0, 1, None),
        (1, 1, None),
        (3, 1, None),
        (16, 1, None),
        (1, 2, 6),
        (2, 2, None),
        (3, 2, 6),
        (16, 2, None),
        (1, 3, 8),
        (2, 3, 4),
        (3, 3, None),
        (4, 3, 8),
        (16, 3, 8),
        (1, 4, 9),
        (2, 4, 6),
        (3, 4, 3),
        (4, 4, None),
        (16, 4, None),
        (1, 6, 10),
        (2, 6, 8),
        (3, 6, 6),
        (4, 6, 4),
        (5, 6, 2),
        (6, 6, None),
        (16, 6, 4),
    ],
)
def test_padding_span_returns_missing_grid_width(
    item_count: int,
    columns: int,
    expected: int | None,
) -> None:
    """Padding span should consume exactly the unused portion of a row."""
    assert (
        presentation._padding_span(  # noqa: SLF001
            item_count,
            columns=columns,
        )
        == expected
    )


@pytest.mark.parametrize(
    "columns",
    [
        0,
        -1,
        -6,
    ],
)
def test_padding_span_rejects_non_positive_columns(
    columns: int,
) -> None:
    """Responsive grid column counts must be positive."""
    with pytest.raises(
        ValueError,
        match="Launchpad grid columns must be greater than 0",
    ):
        presentation._padding_span(  # noqa: SLF001
            3,
            columns=columns,
        )


@pytest.mark.parametrize(
    "columns",
    [
        5,
        7,
        8,
        9,
        10,
        11,
    ],
)
def test_padding_span_rejects_columns_that_do_not_divide_bootstrap_grid(
    columns: int,
) -> None:
    """Configured column counts must divide Bootstrap's 12-unit grid."""
    with pytest.raises(
        ValueError,
        match="Launchpad grid columns must divide evenly into 12",
    ):
        presentation._padding_span(  # noqa: SLF001
            3,
            columns=columns,
        )


@pytest.mark.parametrize(
    ("breakpoint", "span", "expected"),
    [
        ("", 12, "col-12"),
        ("", 6, "col-6"),
        ("sm", 6, "col-sm-6"),
        ("md", 8, "col-md-8"),
        ("lg", 3, "col-lg-3"),
        ("xl", 4, "col-xl-4"),
    ],
)
def test_column_class_builds_bootstrap_class(
    breakpoint: str,  # noqa: A002
    span: int,
    expected: str,
) -> None:
    """Column helper should build the expected Bootstrap class."""
    assert (
        presentation._column_class(  # noqa: SLF001
            breakpoint,
            span=span,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("breakpoint", "visible", "expected"),
    [
        ("", False, "d-none"),
        ("", True, "d-block"),
        ("sm", False, "d-sm-none"),
        ("sm", True, "d-sm-block"),
        ("md", False, "d-md-none"),
        ("md", True, "d-md-block"),
        ("lg", False, "d-lg-none"),
        ("lg", True, "d-lg-block"),
        ("xl", False, "d-xl-none"),
        ("xl", True, "d-xl-block"),
    ],
)
def test_display_class_builds_bootstrap_class(
    breakpoint: str,  # noqa: A002
    visible: bool,  # noqa: FBT001
    expected: str,
) -> None:
    """Display helper should explicitly control each responsive breakpoint."""
    assert (
        presentation._display_class(  # noqa: SLF001
            breakpoint,
            visible=visible,
        )
        == expected
    )


def test_responsive_padding_classes_for_three_items() -> None:
    """Three items should balance only breakpoints with incomplete rows."""
    result = presentation._responsive_padding_classes(  # noqa: SLF001
        3,
    )

    assert result == (
        "d-none d-sm-block col-sm-6 d-md-none d-lg-block col-lg-3 d-xl-block col-xl-6"
    )


def test_responsive_padding_classes_for_sixteen_items() -> None:
    """Sixteen items should fill missing space only at md and xl."""
    result = presentation._responsive_padding_classes(  # noqa: SLF001
        16,
    )

    assert result == (
        "d-none d-sm-none d-md-block col-md-8 d-lg-none d-xl-block col-xl-4"
    )


def test_responsive_padding_classes_for_twelve_items() -> None:
    """Twelve items should require no placeholder at any breakpoint."""
    assert (
        presentation._responsive_padding_classes(  # noqa: SLF001
            12,
        )
        is None
    )


def test_responsive_padding_classes_for_zero_items() -> None:
    """An empty collection should not produce a presentation placeholder."""
    assert (
        presentation._responsive_padding_classes(  # noqa: SLF001
            0,
        )
        is None
    )


@pytest.mark.parametrize(
    ("item_count", "expected"),
    [
        (0, False),
        (1, True),
        (2, True),
        (3, True),
        (4, True),
        (5, True),
        (6, True),
        (12, False),
        (16, True),
        (18, True),
        (24, False),
    ],
)
def test_build_placeholder_only_when_a_breakpoint_needs_balance(
    item_count: int,
    expected: bool,  # noqa: FBT001
) -> None:
    """A placeholder should exist only when at least one layout needs it."""
    result = presentation._build_placeholder(  # noqa: SLF001
        item_count,
    )

    assert (result is not None) is expected


def test_build_placeholder_for_three_items_has_expected_classes() -> None:
    """The responsive descriptor should carry its computed CSS classes."""
    placeholder = presentation._build_placeholder(  # noqa: SLF001
        3,
    )

    assert placeholder is not None

    assert placeholder.classes == (
        "d-none d-sm-block col-sm-6 d-md-none d-lg-block col-lg-3 d-xl-block col-xl-6"
    )


def test_launchpad_placeholder_has_render_only_contract() -> None:
    """The placeholder should expose predictable non-navigation values."""
    placeholder = presentation._LaunchpadPlaceholder(  # noqa: SLF001
        classes="d-none d-md-block col-md-8",
    )

    assert placeholder.is_placeholder is True
    assert placeholder.classes == "d-none d-md-block col-md-8"

    assert placeholder.title == "More to Explore"
    assert placeholder.short_title == "More to Explore"

    assert placeholder.description == (
        "New tools, reports, and operational insights will appear here."
    )

    assert placeholder.tooltip == ""
    assert placeholder.aria_label == "More to Explore"
    assert placeholder.cta_label == ""

    assert placeholder.url == "#"
    assert placeholder.target == ""
    assert placeholder.rel == ""
    assert placeholder.download is False

    assert placeholder.icon == {
        "kind": "emoji",
        "value": "✨",
    }

    assert placeholder.enabled is False
    assert placeholder.disabled_reason == ""
    assert placeholder.is_active is False

    assert placeholder.metadata == {}
    assert placeholder.children == ()


def test_launchpad_placeholder_is_not_navigation_node() -> None:
    """Presentation placeholders should not impersonate Launchpad node kinds."""
    placeholder = presentation._LaunchpadPlaceholder(  # noqa: SLF001
        classes="d-none",
    )

    assert placeholder.is_link is False
    assert placeholder.is_section is False
    assert placeholder.is_separator is False
    assert placeholder.has_children is False


def test_launchpad_placeholders_have_independent_metadata() -> None:
    """Placeholder metadata mappings should never be shared."""
    first = presentation._LaunchpadPlaceholder(  # noqa: SLF001
        classes="d-none",
    )
    second = presentation._LaunchpadPlaceholder(  # noqa: SLF001
        classes="d-none",
    )

    first.metadata["example"] = True

    assert first.metadata == {
        "example": True,
    }

    assert second.metadata == {}


def test_launchpad_placeholders_have_independent_icons() -> None:
    """Placeholder icon mappings should never be shared."""
    first = presentation._LaunchpadPlaceholder(  # noqa: SLF001
        classes="d-none",
    )
    second = presentation._LaunchpadPlaceholder(  # noqa: SLF001
        classes="d-none",
    )

    first.icon["value"] = "🚀"

    assert first.icon == {
        "kind": "emoji",
        "value": "🚀",
    }

    assert second.icon == {
        "kind": "emoji",
        "value": "✨",
    }


def test_launchpad_pad_template_tag_returns_responsive_placeholder() -> None:
    """The public tag should expose one responsive placeholder descriptor."""
    output = _render(
        """
        {% load launchpad_tags %}
        {% launchpad_pad items as padding %}
        {{ padding.is_placeholder }}|
        {{ padding.title }}|
        {{ padding.classes }}
        """,
        {
            "items": [
                object(),
                object(),
                object(),
            ],
        },
    )

    normalized = " ".join(
        output.split(),
    )

    assert normalized == (
        "True| More to Explore| "
        "d-none d-sm-block col-sm-6 d-md-none "
        "d-lg-block col-lg-3 d-xl-block col-xl-6"
    )


def test_launchpad_pad_template_tag_returns_none_when_fully_balanced() -> None:
    """A collection balanced at every breakpoint should need no placeholder."""
    output = _render(
        """
        {% load launchpad_tags %}
        {% launchpad_pad items as padding %}
        {% if padding %}padding{% else %}none{% endif %}
        """,
        {
            "items": [object() for _ in range(12)],
        },
    )

    assert output.strip() == "none"


def test_launchpad_pad_works_with_real_resolved_nodes() -> None:
    """Responsive padding should operate after normal Launchpad resolution."""
    user = create_user()

    launchpad = create_launchpad(
        code="home_cards",
    )

    for index in range(3):
        link = create_navigation_link(
            code=f"item_{index}",
            title=f"Item {index}",
            url_type=NavigationLink.URLType.RAW,
            url_value=f"/items/{index}/",
        )

        create_link_node(
            launchpad=launchpad,
            navigation_link=link,
        )

    output = _render(
        """
        {% load launchpad_tags %}
        {% get_launchpad "home_cards" as navigation %}
        {% launchpad_pad navigation.nodes as padding %}
        {{ navigation.nodes|length }}|
        {{ padding.is_placeholder }}|
        {{ padding.classes }}
        """,
        {
            "request": build_request(
                user=user,
            ),
        },
    )

    normalized = " ".join(
        output.split(),
    )

    assert normalized == (
        "3| True| "
        "d-none d-sm-block col-sm-6 d-md-none "
        "d-lg-block col-lg-3 d-xl-block col-xl-6"
    )


def test_launchpad_pad_does_not_change_resolved_launchpad_nodes() -> None:
    """Responsive balancing should leave canonical navigation unchanged."""
    user = create_user()

    launchpad = create_launchpad(
        code="home_cards",
    )

    for index in range(3):
        link = create_navigation_link(
            code=f"item_{index}",
            title=f"Item {index}",
        )

        create_link_node(
            launchpad=launchpad,
            navigation_link=link,
        )

    output = _render(
        """
        {% load launchpad_tags %}
        {% get_launchpad "home_cards" as navigation %}
        {% launchpad_pad navigation.nodes as padding %}
        {{ navigation.nodes|length }}
        """,
        {
            "request": build_request(
                user=user,
            ),
        },
    )

    assert output.strip() == "3"


def test_presentation_module_exports_launchpad_pad() -> None:
    """The presentation module should expose only its public helper."""
    assert presentation.__all__ == [
        "launchpad_pad",
    ]
