"""
tests/test_templatetags_launchpad_tags.py

Tests for Launchpad template tags and the generic recursive tree renderer.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from django.template import Context, Template
from django.utils.translation import override

from launchpad.models import LaunchpadNode, NavigationLink
from launchpad.templatetags import launchpad_tags
from tests.builders import (
    build_request,
    create_emoji_navigation_link,
    create_launchpad,
    create_link_node,
    create_navigation_link,
    create_section_node,
    create_separator_node,
    create_user,
)

if TYPE_CHECKING:
    from django.http import HttpRequest

pytestmark = pytest.mark.django_db


_GENERIC_TREE_TEMPLATE = """
{% load launchpad_tags %}
{% get_launchpad launchpad_code as navigation %}
{% include "launchpad/generic/tree.html" with launchpad=navigation only %}
"""


def _render(
    source: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Render an in-memory Django template."""
    return Template(source).render(
        Context(context or {}),
    )


def _render_tree(
    launchpad_code: str,
    *,
    request: HttpRequest,
    **context: Any,
) -> str:
    """Resolve and render a Launchpad using the generic tree template."""
    return _render(
        _GENERIC_TREE_TEMPLATE,
        {
            "launchpad_code": launchpad_code,
            "request": request,
            **context,
        },
    )


def test_get_launchpad_assignment_tag_returns_resolved_launchpad() -> None:
    """The assignment tag should return a resolved Launchpad object."""
    launchpad = create_launchpad(
        code="primary_navigation",
        title="Primary Navigation",
    )

    output = _render(
        """
        {% load launchpad_tags %}
        {% get_launchpad "primary_navigation" as navigation %}
        {{ navigation.code }}|{{ navigation.title }}|{{ navigation.exists }}
        """,
        {
            "request": build_request(
                user=create_user(),
            ),
        },
    )

    normalized = " ".join(output.split())

    assert "primary_navigation|Primary Navigation|True" in normalized
    assert launchpad.code == "primary_navigation"


def test_get_launchpad_uses_request_user_for_visibility() -> None:
    """The assignment tag should use request.user by default."""
    allowed_user = create_user()
    denied_user = create_user()

    launchpad = create_launchpad(
        code="private_navigation",
    )

    link = create_navigation_link(
        code="ancestry",
        title="Ancestry",
        audience=NavigationLink.Audience.PRIVATE,
        users=[allowed_user],
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    allowed_output = _render_tree(
        launchpad.code,
        request=build_request(user=allowed_user),
    )

    denied_output = _render_tree(
        launchpad.code,
        request=build_request(user=denied_user),
    )

    assert "Ancestry" in allowed_output
    assert "Ancestry" not in denied_output


def test_get_launchpad_accepts_explicit_user_without_request() -> None:
    """The assignment tag should accept an explicit user."""
    user = create_user()

    launchpad = create_launchpad(
        code="account_navigation",
    )

    link = create_navigation_link(
        code="profile",
        title="My Profile",
        audience=NavigationLink.Audience.PRIVATE,
        users=[user],
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    output = _render(
        """
        {% load launchpad_tags %}
        {% get_launchpad "account_navigation" user=user as navigation %}
        {{ navigation.nodes.0.title }}
        """,
        {
            "user": user,
        },
    )

    assert "My Profile" in output


def test_get_launchpad_returns_safe_result_for_missing_code() -> None:
    """Missing Launchpad codes should produce a safe empty result."""
    output = _render(
        """
        {% load launchpad_tags %}
        {% get_launchpad "missing_navigation" as navigation %}
        {{ navigation.exists }}|{{ navigation.is_empty }}
        """,
        {
            "request": build_request(
                user=create_user(),
            ),
        },
    )

    normalized = "".join(output.split())

    assert normalized == "False|True"


def test_generic_tree_renders_nesting_sections_and_separators() -> None:
    """The generic renderer should support nested structural nodes."""
    user = create_user()

    launchpad = create_launchpad(
        code="primary_navigation",
    )

    home_link = create_emoji_navigation_link(
        code="home",
        title="Home",
        emoji="🏠",
        url_type=NavigationLink.URLType.RAW,
        url_value="/",
    )

    ancestry_link = create_navigation_link(
        code="ancestry",
        title="Ancestry",
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=home_link,
        sort_order=1000,
    )

    create_separator_node(
        launchpad=launchpad,
        sort_order=2000,
    )

    apps_section = create_section_node(
        launchpad=launchpad,
        code="apps",
        title_override="Apps",
        sort_order=3000,
    )

    create_link_node(
        launchpad=launchpad,
        parent=apps_section,
        navigation_link=ancestry_link,
        sort_order=1000,
    )

    output = _render_tree(
        launchpad.code,
        request=build_request(user=user),
    )

    assert 'data-launchpad-code="primary_navigation"' in output
    assert "launchpad-node-link" in output
    assert "launchpad-node-section" in output
    assert "launchpad-node-separator" in output

    assert 'data-launchpad-level="0"' in output
    assert 'data-launchpad-level="1"' in output

    assert 'href="/"' in output
    assert 'href="/ancestry/"' in output

    assert "Home" in output
    assert "Apps" in output
    assert "Ancestry" in output
    assert "🏠" in output


def test_generic_tree_resolves_additional_context_values() -> None:
    """Template-provided context values should resolve in URLs."""
    user = create_user()

    launchpad = create_launchpad(
        code="person_actions",
    )

    link = create_navigation_link(
        code="person_detail",
        title="View Person",
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/people/",
        query_params={
            "person": "@context.person.pk",
        },
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render(
        """
        {% load launchpad_tags %}
        {% get_launchpad "person_actions" person=person as navigation %}
        {% include "launchpad/generic/tree.html" with launchpad=navigation only %}
        """,
        {
            "request": build_request(user=user),
            "person": SimpleNamespace(pk=42),
        },
    )

    assert 'href="/ancestry/people/?person=42"' in output


def test_generic_tree_renders_disabled_link_as_non_clickable() -> None:
    """Disabled links should render as non-clickable content."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        enabled_override=False,
        disabled_reason_override="Coming soon.",
    )

    output = _render_tree(
        launchpad.code,
        request=build_request(user=user),
    )

    assert 'href="/reports/"' not in output
    assert "<a" not in output
    assert 'aria-disabled="true"' in output
    assert "launchpad-link-disabled" in output
    assert "Coming soon." in output


def test_generic_tree_marks_active_link_with_aria_current() -> None:
    """Active links should receive visual and accessibility state."""
    user = create_user()

    launchpad = create_launchpad(
        code="primary_navigation",
    )

    link = create_navigation_link(
        code="ancestry",
        title="Ancestry",
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.PATH_PREFIX,
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_tree(
        launchpad.code,
        request=build_request(
            "/ancestry/people/42/",
            user=user,
        ),
    )

    assert "launchpad-node-link is-active" in output
    assert 'aria-current="page"' in output


def test_generic_tree_renders_new_tab_and_download_attributes() -> None:
    """External downloads should render target, rel, and download attributes."""
    user = create_user()

    launchpad = create_launchpad(
        code="documentation",
    )

    link = create_navigation_link(
        code="download_guide",
        title="Download Guide",
        url_type=NavigationLink.URLType.RAW,
        url_value="https://example.com/guide.pdf",
        target=NavigationLink.Target.BLANK,
        rel="",
        download=True,
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_tree(
        launchpad.code,
        request=build_request(user=user),
    )

    assert 'href="https://example.com/guide.pdf"' in output
    assert 'target="_blank"' in output
    assert 'rel="noopener noreferrer"' in output
    assert "download" in output


def test_generic_tree_renders_tooltip_and_accessibility_label() -> None:
    """Tooltip and accessibility attributes should be rendered."""
    user = create_user()

    launchpad = create_launchpad(
        code="primary_navigation",
    )

    link = create_navigation_link(
        code="ancestry",
        title="Ancestry",
        tooltip="Open the family tree",
        aria_label="Open Ancestry",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_tree(
        launchpad.code,
        request=build_request(user=user),
    )

    assert 'title="Open the family tree"' in output
    assert 'aria-label="Open Ancestry"' in output


def test_generic_tree_renders_empty_state_for_empty_launchpad() -> None:
    """Existing launchpads without visible nodes should render an empty state."""
    launchpad = create_launchpad(
        code="empty_navigation",
    )

    with override("en"):
        output = _render_tree(
            launchpad.code,
            request=build_request(user=create_user()),
        )

    assert 'data-launchpad-code="empty_navigation"' in output
    assert "launchpad-empty" in output
    assert "No navigation items are available." in output


def test_generic_tree_renders_nothing_for_missing_launchpad() -> None:
    """Missing launchpads should render no markup."""
    output = _render_tree(
        "missing_navigation",
        request=build_request(user=create_user()),
    )

    assert output.strip() == ""


def test_launchpad_pad_leaves_even_collection_unchanged() -> None:
    """Padding to two should not add placeholders to an even collection."""
    items = [
        object(),
        object(),
    ]

    result = launchpad_tags._pad_items(  # noqa: SLF001
        items,
        multiple=2,
    )

    assert result == items
    assert result is not items


def test_launchpad_pad_adds_placeholder_for_odd_collection() -> None:
    """Padding to two should add one placeholder to an odd collection."""
    items = [
        object(),
        object(),
        object(),
    ]

    result = launchpad_tags._pad_items(  # noqa: SLF001
        items,
        multiple=2,
    )

    assert len(result) == 4

    assert result[:3] == items

    placeholder = result[-1]

    assert isinstance(
        placeholder,
        launchpad_tags._LaunchpadPlaceholder,  # noqa: SLF001
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
def test_launchpad_pad_pads_to_requested_multiple(
    count: int,
    multiple: int,
    expected_count: int,
) -> None:
    """Padding should extend collections to the requested item multiple."""
    items = [object() for _ in range(count)]

    result = launchpad_tags._pad_items(  # noqa: SLF001
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
def test_launchpad_pad_rejects_invalid_multiple(
    multiple: int,
) -> None:
    """Padding multiples must be positive integers."""
    with pytest.raises(
        ValueError,
        match="Launchpad padding multiple must be greater than 0",
    ):
        launchpad_tags._pad_items(  # noqa: SLF001
            [],
            multiple=multiple,
        )


def test_launchpad_pad_does_not_modify_original_collection() -> None:
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

    result = launchpad_tags._pad_items(  # noqa: SLF001
        items,
        multiple=2,
    )

    assert items == original

    assert result[:3] == original
    assert len(result) == 4


def test_launchpad_pad_preserves_existing_item_identity() -> None:
    """Padding should reuse original resolved items rather than copying them."""
    first = object()
    second = object()
    third = object()

    result = launchpad_tags._pad_items(  # noqa: SLF001
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


def test_launchpad_pad_creates_independent_placeholders() -> None:
    """Every required padding slot should receive its own placeholder."""
    result = launchpad_tags._pad_items(  # noqa: SLF001
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
            launchpad_tags._LaunchpadPlaceholder,  # noqa: SLF001
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
    placeholder = launchpad_tags._LaunchpadPlaceholder()  # noqa: SLF001

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


def test_launchpad_placeholder_is_not_a_navigation_node() -> None:
    """Presentation placeholders should not impersonate Launchpad node kinds."""
    placeholder = launchpad_tags._LaunchpadPlaceholder()  # noqa: SLF001

    assert placeholder.is_link is False
    assert placeholder.is_section is False
    assert placeholder.is_separator is False
    assert placeholder.has_children is False


def test_launchpad_placeholders_have_independent_metadata() -> None:
    """Placeholder metadata mappings should never be shared."""
    first = launchpad_tags._LaunchpadPlaceholder()  # noqa: SLF001
    second = launchpad_tags._LaunchpadPlaceholder()  # noqa: SLF001

    first.metadata["example"] = True

    assert first.metadata == {
        "example": True,
    }

    assert second.metadata == {}


def test_launchpad_placeholders_have_independent_icons() -> None:
    """Placeholder icon mappings should never be shared."""
    first = launchpad_tags._LaunchpadPlaceholder()  # noqa: SLF001
    second = launchpad_tags._LaunchpadPlaceholder()  # noqa: SLF001

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
    """The public template tag should default to padding in multiples of two."""
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
    """Templates should be able to distinguish padding from real items."""
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
    """Using the presentation helper should leave navigation truth unchanged."""
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


def test_launchpad_tags_exports_public_tags() -> None:
    """The template-tag module should expose both public Launchpad helpers."""
    assert launchpad_tags.__all__ == [
        "get_launchpad",
        "launchpad_pad",
    ]
