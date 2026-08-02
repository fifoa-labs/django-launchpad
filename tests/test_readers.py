"""
tests/test_readers.py

Tests for renderer-neutral Launchpad readers.
"""

from __future__ import annotations

import pytest

from launchpad.models import LaunchpadNode, NavigationLink
from launchpad.readers import (
    ResolvedLaunchpad,
    ResolvedNode,
    _node_is_visible,
    get_launchpad,
)
from launchpad.visibility import build_user_context
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

pytestmark = pytest.mark.django_db


def test_get_launchpad_returns_empty_result_for_missing_launchpad() -> None:
    """Missing launchpads should return a safe empty result."""
    result = get_launchpad(
        "missing_launchpad",
        user=create_user(),
    )

    assert isinstance(result, ResolvedLaunchpad)
    assert result.exists is False
    assert result.code == "missing_launchpad"
    assert result.nodes == []
    assert result.is_empty is True


def test_get_launchpad_returns_empty_result_for_inactive_launchpad() -> None:
    """Inactive launchpads should behave like missing launchpads."""
    launchpad = create_launchpad(
        code="primary_navigation",
        active=False,
    )

    result = get_launchpad(
        launchpad.code,
        user=create_user(),
    )

    assert result.exists is False
    assert result.nodes == []


def test_get_launchpad_returns_visible_root_link() -> None:
    """Visible root links should resolve into renderer-neutral nodes."""
    user = create_user()
    launchpad = create_launchpad(code="primary_navigation")
    link = create_navigation_link(
        code="ancestry",
        title="Ancestry",
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        sort_order=1000,
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    assert result.exists is True
    assert len(result.nodes) == 1

    node = result.nodes[0]

    assert isinstance(node, ResolvedNode)
    assert node.kind == LaunchpadNode.Kind.LINK
    assert node.code == "ancestry"
    assert node.link_code == "ancestry"
    assert node.title == "Ancestry"
    assert node.url == "/ancestry/"
    assert node.enabled is True
    assert node.children == []


def test_get_launchpad_removes_link_hidden_by_link_visibility() -> None:
    """Link visibility should be enforced independently of node visibility."""
    user = create_user(is_staff=False)
    launchpad = create_launchpad(code="primary_navigation")
    link = create_navigation_link(
        audience=NavigationLink.Audience.STAFF,
        title="Staff Only",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    assert result.nodes == []


def test_get_launchpad_removes_link_hidden_by_node_visibility() -> None:
    """Node visibility should be enforced independently of link visibility."""
    user = create_user()
    launchpad = create_launchpad(code="primary_navigation")
    link = create_navigation_link(
        audience=NavigationLink.Audience.AUTHENTICATED,
        title="Ancestry",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        audience=LaunchpadNode.Audience.STAFF,
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    assert result.nodes == []


def test_get_launchpad_removes_empty_sections() -> None:
    """Sections without visible descendants should be omitted."""
    launchpad = create_launchpad(code="primary_navigation")

    create_section_node(
        launchpad=launchpad,
        title_override="Apps",
    )

    result = get_launchpad(
        launchpad.code,
        user=create_user(),
    )

    assert result.nodes == []


def test_get_launchpad_keeps_section_with_visible_child() -> None:
    """Sections with visible descendants should remain in the tree."""
    user = create_user()
    launchpad = create_launchpad(code="primary_navigation")

    section = create_section_node(
        launchpad=launchpad,
        title_override="Apps",
        sort_order=1000,
    )

    link = create_navigation_link(
        title="Ancestry",
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
    )

    create_link_node(
        launchpad=launchpad,
        parent=section,
        navigation_link=link,
        sort_order=1000,
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    assert len(result.nodes) == 1

    resolved_section = result.nodes[0]

    assert resolved_section.kind == LaunchpadNode.Kind.SECTION
    assert resolved_section.title == "Apps"
    assert resolved_section.has_children is True
    assert len(resolved_section.children) == 1
    assert resolved_section.children[0].title == "Ancestry"


def test_get_launchpad_builds_nested_children() -> None:
    """Readers should construct nested trees from parent relationships."""
    user = create_user()
    launchpad = create_launchpad(code="primary_navigation")

    section = create_section_node(
        launchpad=launchpad,
        title_override="Apps",
    )

    child_section = create_section_node(
        launchpad=launchpad,
        parent=section,
        title_override="Family",
    )

    link = create_navigation_link(title="Ancestry")

    create_link_node(
        launchpad=launchpad,
        parent=child_section,
        navigation_link=link,
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    root = result.nodes[0]
    nested_section = root.children[0]
    nested_link = nested_section.children[0]

    assert root.title == "Apps"
    assert nested_section.title == "Family"
    assert nested_link.title == "Ancestry"


def test_get_launchpad_orders_sibling_nodes_by_sort_order() -> None:
    """Sibling nodes should be ordered by their configured sort order."""
    user = create_user()
    launchpad = create_launchpad(code="primary_navigation")

    first_link = create_navigation_link(title="First")
    second_link = create_navigation_link(title="Second")
    third_link = create_navigation_link(title="Third")

    create_link_node(
        launchpad=launchpad,
        navigation_link=third_link,
        sort_order=3000,
    )
    create_link_node(
        launchpad=launchpad,
        navigation_link=first_link,
        sort_order=1000,
    )
    create_link_node(
        launchpad=launchpad,
        navigation_link=second_link,
        sort_order=2000,
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    assert [node.title for node in result.nodes] == [
        "First",
        "Second",
        "Third",
    ]


def test_get_launchpad_cleans_redundant_separators() -> None:
    """Leading, duplicate, and trailing separators should be removed."""
    user = create_user()
    launchpad = create_launchpad(code="primary_navigation")

    first_link = create_navigation_link(title="First")
    second_link = create_navigation_link(title="Second")

    create_separator_node(
        launchpad=launchpad,
        sort_order=500,
    )
    create_link_node(
        launchpad=launchpad,
        navigation_link=first_link,
        sort_order=1000,
    )
    create_separator_node(
        launchpad=launchpad,
        sort_order=2000,
    )
    create_separator_node(
        launchpad=launchpad,
        sort_order=2500,
    )
    create_link_node(
        launchpad=launchpad,
        navigation_link=second_link,
        sort_order=3000,
    )
    create_separator_node(
        launchpad=launchpad,
        sort_order=4000,
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    assert [node.kind for node in result.nodes] == [
        LaunchpadNode.Kind.LINK,
        LaunchpadNode.Kind.SEPARATOR,
        LaunchpadNode.Kind.LINK,
    ]

    assert [
        node.title for node in result.nodes if node.kind == LaunchpadNode.Kind.LINK
    ] == [
        "First",
        "Second",
    ]


def test_get_launchpad_marks_active_child_and_parent() -> None:
    """An active descendant should mark its containing section active."""
    user = create_user()
    request = build_request(
        "/ancestry/people/42/",
        user=user,
    )

    launchpad = create_launchpad(code="primary_navigation")

    section = create_section_node(
        launchpad=launchpad,
        title_override="Apps",
    )

    link = create_navigation_link(
        title="Ancestry",
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.PATH_PREFIX,
    )

    create_link_node(
        launchpad=launchpad,
        parent=section,
        navigation_link=link,
    )

    result = get_launchpad(
        launchpad.code,
        request=request,
    )

    section_node = result.nodes[0]
    child_node = section_node.children[0]

    assert child_node.is_active is True
    assert section_node.is_active is True


def test_node_overrides_beat_navigation_link_defaults() -> None:
    """Node-level presentation values should override link defaults."""
    user = create_user()
    launchpad = create_launchpad(code="homepage")

    link = create_emoji_navigation_link(
        title="Ancestry",
        short_title="Tree",
        description="Canonical description.",
        cta_label="Open",
        emoji="🌳",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        title_override="Family History",
        short_title_override="Family",
        description_override="Placement description.",
        cta_label_override="Explore",
        icon_type_override=NavigationLink.IconType.EMOJI,
        emoji_override="🚀",
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    node = result.nodes[0]

    assert node.title == "Family History"
    assert node.short_title == "Family"
    assert node.description == "Placement description."
    assert node.cta_label == "Explore"
    assert node.icon == {
        "kind": "emoji",
        "value": "🚀",
    }


def test_link_metadata_and_node_metadata_are_merged() -> None:
    """Node metadata should override matching link metadata keys."""
    user = create_user()
    launchpad = create_launchpad(code="homepage")

    link = create_navigation_link(
        metadata={
            "source": "link",
            "size": "sm",
        },
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        metadata={
            "size": "lg",
            "variant": "featured",
        },
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    assert result.nodes[0].metadata == {
        "source": "link",
        "size": "lg",
        "variant": "featured",
    }


def test_same_link_can_render_differently_in_different_launchpads() -> None:
    """One canonical link may have distinct presentation per placement."""
    user = create_user()

    link = create_navigation_link(
        code="ancestry",
        title="Ancestry",
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
    )

    primary = create_launchpad(code="primary_navigation")
    homepage = create_launchpad(code="homepage")

    create_link_node(
        launchpad=primary,
        navigation_link=link,
        title_override="Ancestry",
    )
    create_link_node(
        launchpad=homepage,
        navigation_link=link,
        title_override="Explore Family History",
        description_override="Build and explore the family tree.",
    )

    primary_result = get_launchpad(
        primary.code,
        user=user,
    )
    homepage_result = get_launchpad(
        homepage.code,
        user=user,
    )

    assert primary_result.nodes[0].title == "Ancestry"
    assert primary_result.nodes[0].description == ""

    assert homepage_result.nodes[0].title == "Explore Family History"
    assert homepage_result.nodes[0].description == "Build and explore the family tree."


def test_disabled_node_resolves_to_hash_but_still_renders() -> None:
    """Disabled nodes should remain visible but resolve to a safe target."""
    user = create_user()
    launchpad = create_launchpad(code="homepage")

    link = create_navigation_link(
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

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    node = result.nodes[0]

    assert node.enabled is False
    assert node.url == "#"
    assert node.disabled_reason == "Coming soon."


def test_resolved_node_helpers() -> None:
    """ResolvedNode helpers should describe the node kind and children."""
    user = create_user()
    launchpad = create_launchpad(code="primary_navigation")
    link = create_navigation_link(title="Ancestry")

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    result = get_launchpad(
        launchpad.code,
        user=user,
    )

    node = result.nodes[0]

    assert node.is_link is True
    assert node.is_section is False
    assert node.is_separator is False
    assert node.has_children is False


def test_node_visibility_rejects_link_without_navigation_link() -> None:
    """Malformed link nodes without destinations should fail closed."""
    node = LaunchpadNode(
        launchpad=create_launchpad(),
        created_by=create_user(),
        kind=LaunchpadNode.Kind.LINK,
        navigation_link=None,
        audience=LaunchpadNode.Audience.PUBLIC,
    )
    ctx = build_user_context(create_user())

    assert _node_is_visible(node, ctx) is False
