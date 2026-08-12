"""
tests/test_templatetags_launchpad_tags_presentation.py

Tests for optional Launchpad presentation template helpers.
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


def test_pad_items_leaves_even_collection_unchanged() -> None:
    """Padding to two should not add placeholders to an even collection."""
    items = [
        object(),
        object(),
    ]

    result = presentation._pad_items(  # noqa: SLF001
        items,
        multiple=2,
    )

    assert result == items
    assert result is not items


def test_pad_items_adds_placeholder_for_odd_collection() -> None:
    """Padding to two should add one placeholder to an odd collection."""
    items = [
        object(),
        object(),
        object(),
    ]

    result = presentation._pad_items(  # noqa: SLF001
        items,
        multiple=2,
    )

    assert len(result) == 4
    assert result[:3] == items

    placeholder = result[-1]

    assert isinstance(
        placeholder,
        presentation._LaunchpadPlaceholder,  # noqa: SLF001
    )


@pytest.mark.parametrize(
    ("count", "multiple", "expected_count"),
    [
        (0, 2, 0),
        (1, 2, 2),
        (2, 2, 2),
        (3, 2, 4),
        (5, 2, 6),
        (5, 3, 6),
        (6, 3, 6),
        (7, 3, 9),
        (5, 4, 8),
        (7, 6, 12),
        (12, 6, 12),
    ],
)
def test_pad_items_pads_to_requested_multiple(
    count: int,
    multiple: int,
    expected_count: int,
) -> None:
    """Padding should extend collections to the requested item multiple."""
    items = [object() for _ in range(count)]

    result = presentation._pad_items(  # noqa: SLF001
        items,
        multiple=multiple,
    )

    assert len(result) == expected_count


@pytest.mark.parametrize(
    "multiple",
    [
        0,
        -1,
        -10,
    ],
)
def test_pad_items_rejects_invalid_multiple(
    multiple: int,
) -> None:
    """Padding multiples must be positive integers."""
    with pytest.raises(
        ValueError,
        match="Launchpad padding multiple must be greater than 0",
    ):
        presentation._pad_items(  # noqa: SLF001
            [],
            multiple=multiple,
        )


def test_pad_items_does_not_modify_original_collection() -> None:
    """Presentation padding should never mutate resolved navigation data."""
    first = object()
    second = object()
    third = object()

    items = [
        first,
        second,
        third,
    ]

    original = list(
        items,
    )

    result = presentation._pad_items(  # noqa: SLF001
        items,
        multiple=2,
    )

    assert items == original

    assert result[:3] == original
    assert len(result) == 4


def test_pad_items_preserves_existing_item_identity() -> None:
    """Padding should reuse original items rather than copying them."""
    first = object()
    second = object()
    third = object()

    result = presentation._pad_items(  # noqa: SLF001
        [
            first,
            second,
            third,
        ],
        multiple=2,
    )

    assert result[0] is first
    assert result[1] is second
    assert result[2] is third


def test_pad_items_creates_independent_placeholders() -> None:
    """Every required padding slot should receive its own placeholder."""
    result = presentation._pad_items(  # noqa: SLF001
        [
            object(),
        ],
        multiple=4,
    )

    placeholders = result[1:]

    assert len(placeholders) == 3

    assert all(
        isinstance(
            item,
            presentation._LaunchpadPlaceholder,  # noqa: SLF001
        )
        for item in placeholders
    )

    assert (
        len(
            {id(item) for item in placeholders},
        )
        == 3
    )


def test_launchpad_placeholder_has_render_only_contract() -> None:
    """The placeholder should expose predictable non-navigation values."""
    placeholder = presentation._LaunchpadPlaceholder()  # noqa: SLF001

    assert placeholder.is_placeholder is True

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
    placeholder = presentation._LaunchpadPlaceholder()  # noqa: SLF001

    assert placeholder.is_link is False
    assert placeholder.is_section is False
    assert placeholder.is_separator is False
    assert placeholder.has_children is False


def test_launchpad_placeholders_have_independent_metadata() -> None:
    """Placeholder metadata mappings should never be shared."""
    first = presentation._LaunchpadPlaceholder()  # noqa: SLF001
    second = presentation._LaunchpadPlaceholder()  # noqa: SLF001

    first.metadata["example"] = True

    assert first.metadata == {
        "example": True,
    }

    assert second.metadata == {}


def test_launchpad_placeholders_have_independent_icons() -> None:
    """Placeholder icon mappings should never be shared."""
    first = presentation._LaunchpadPlaceholder()  # noqa: SLF001
    second = presentation._LaunchpadPlaceholder()  # noqa: SLF001

    first.icon["value"] = "🚀"

    assert first.icon == {
        "kind": "emoji",
        "value": "🚀",
    }

    assert second.icon == {
        "kind": "emoji",
        "value": "✨",
    }


def test_launchpad_pad_template_tag_defaults_to_pairs() -> None:
    """The public tag should default to padding in multiples of two."""
    output = _render(
        """
        {% load launchpad_tags %}
        {% launchpad_pad items as padded %}
        {{ padded|length }}
        """,
        {
            "items": [
                1,
                2,
                3,
            ],
        },
    )

    assert output.strip() == "4"


def test_launchpad_pad_template_tag_accepts_multiple() -> None:
    """Templates should be able to choose their preferred padding multiple."""
    output = _render(
        """
        {% load launchpad_tags %}
        {% launchpad_pad items multiple=4 as padded %}
        {{ padded|length }}
        """,
        {
            "items": [
                1,
                2,
                3,
                4,
                5,
            ],
        },
    )

    assert output.strip() == "8"


def test_launchpad_pad_template_tag_exposes_placeholder() -> None:
    """Templates should be able to distinguish placeholders from real items."""
    output = _render(
        """
        {% load launchpad_tags %}
        {% launchpad_pad items multiple=2 as padded %}
        {% for item in padded %}
            {% if item.is_placeholder %}
                PLACEHOLDER:{{ item.title }}:{{ item.icon.value }}
            {% else %}
                REAL
            {% endif %}
        {% endfor %}
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

    assert normalized.count("REAL") == 3
    assert "PLACEHOLDER:More to Explore:✨" in normalized


def test_launchpad_pad_works_with_real_resolved_nodes() -> None:
    """Padding should operate after normal Launchpad resolution."""
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
        {% launchpad_pad navigation.nodes multiple=2 as cards %}
        {{ navigation.nodes|length }}|{{ cards|length }}|
        {% for card in cards %}
            {% if card.is_placeholder %}
                placeholder
            {% else %}
                {{ card.title }}
            {% endif %}
        {% endfor %}
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

    assert normalized.startswith(
        "3|4|",
    )

    assert "Item 0" in normalized
    assert "Item 1" in normalized
    assert "Item 2" in normalized
    assert "placeholder" in normalized


def test_launchpad_pad_does_not_change_resolved_launchpad_nodes() -> None:
    """Presentation padding should leave navigation truth unchanged."""
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
        {% launchpad_pad navigation.nodes multiple=2 as cards %}
        {{ navigation.nodes|length }}|{{ cards|length }}
        """,
        {
            "request": build_request(
                user=user,
            ),
        },
    )

    assert (
        "".join(
            output.split(),
        )
        == "3|4"
    )


def test_presentation_module_exports_launchpad_pad() -> None:
    """The presentation module should expose only its public helper."""
    assert presentation.__all__ == [
        "launchpad_pad",
    ]
