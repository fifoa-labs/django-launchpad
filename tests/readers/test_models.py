"""
tests/readers/test_models.py

Tests for renderer-neutral Launchpad reader result models.
"""

from __future__ import annotations

from launchpad.models import Launchpad, LaunchpadNode, NavigationLink
from launchpad.readers.models import ResolvedLaunchpad, ResolvedNode


def test_resolved_node_identifies_link_kind() -> None:
    """Link nodes should report only the link convenience flag."""
    node = ResolvedNode(
        node_id=1,
        link_id=10,
        kind=LaunchpadNode.Kind.LINK,
        code="reports",
        link_code="reports",
        title="Reports",
        short_title="Reports",
        description="",
        tooltip="",
        aria_label="Reports",
        cta_label="",
        url="/reports/",
        target="_self",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    assert node.is_link is True
    assert node.is_section is False
    assert node.is_separator is False


def test_resolved_node_identifies_section_kind() -> None:
    """Section nodes should report only the section convenience flag."""
    node = ResolvedNode(
        node_id=1,
        link_id=None,
        kind=LaunchpadNode.Kind.SECTION,
        code="reports",
        link_code="",
        title="Reports",
        short_title="Reports",
        description="",
        tooltip="",
        aria_label="Reports",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    assert node.is_link is False
    assert node.is_section is True
    assert node.is_separator is False


def test_resolved_node_identifies_separator_kind() -> None:
    """Separator nodes should report only the separator convenience flag."""
    node = ResolvedNode(
        node_id=1,
        link_id=None,
        kind=LaunchpadNode.Kind.SEPARATOR,
        code="separator-1",
        link_code="",
        title="",
        short_title="",
        description="",
        tooltip="",
        aria_label="",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    assert node.is_link is False
    assert node.is_section is False
    assert node.is_separator is True


def test_resolved_node_has_children_is_false_by_default() -> None:
    """Resolved nodes should default to having no children."""
    node = ResolvedNode(
        node_id=1,
        link_id=None,
        kind=LaunchpadNode.Kind.SECTION,
        code="reports",
        link_code="",
        title="Reports",
        short_title="Reports",
        description="",
        tooltip="",
        aria_label="Reports",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    assert node.children == []
    assert node.has_children is False


def test_resolved_node_has_children_is_true_when_children_exist() -> None:
    """Resolved nodes should report whether child nodes are present."""
    child = ResolvedNode(
        node_id=2,
        link_id=10,
        kind=LaunchpadNode.Kind.LINK,
        code="reports",
        link_code="reports",
        title="Reports",
        short_title="Reports",
        description="",
        tooltip="",
        aria_label="Reports",
        cta_label="",
        url="/reports/",
        target="_self",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    parent = ResolvedNode(
        node_id=1,
        link_id=None,
        kind=LaunchpadNode.Kind.SECTION,
        code="insights",
        link_code="",
        title="Insights",
        short_title="Insights",
        description="",
        tooltip="",
        aria_label="Insights",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
        children=[
            child,
        ],
    )

    assert parent.has_children is True
    assert parent.children == [
        child,
    ]


def test_resolved_node_uses_independent_default_metadata() -> None:
    """Default metadata mappings should not be shared between nodes."""
    first = ResolvedNode(
        node_id=1,
        link_id=None,
        kind=LaunchpadNode.Kind.SECTION,
        code="first",
        link_code="",
        title="First",
        short_title="First",
        description="",
        tooltip="",
        aria_label="First",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    second = ResolvedNode(
        node_id=2,
        link_id=None,
        kind=LaunchpadNode.Kind.SECTION,
        code="second",
        link_code="",
        title="Second",
        short_title="Second",
        description="",
        tooltip="",
        aria_label="Second",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    first.metadata["location"] = "sidebar"

    assert first.metadata == {
        "location": "sidebar",
    }
    assert second.metadata == {}


def test_resolved_node_uses_independent_default_children() -> None:
    """Default child lists should not be shared between nodes."""
    first = ResolvedNode(
        node_id=1,
        link_id=None,
        kind=LaunchpadNode.Kind.SECTION,
        code="first",
        link_code="",
        title="First",
        short_title="First",
        description="",
        tooltip="",
        aria_label="First",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    second = ResolvedNode(
        node_id=2,
        link_id=None,
        kind=LaunchpadNode.Kind.SECTION,
        code="second",
        link_code="",
        title="Second",
        short_title="Second",
        description="",
        tooltip="",
        aria_label="Second",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    child = ResolvedNode(
        node_id=3,
        link_id=None,
        kind=LaunchpadNode.Kind.SEPARATOR,
        code="separator-3",
        link_code="",
        title="",
        short_title="",
        description="",
        tooltip="",
        aria_label="",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    first.children.append(child)

    assert first.children == [
        child,
    ]
    assert second.children == []


def test_resolved_node_preserves_source_models() -> None:
    """Live reader results should be able to retain their source models."""
    link = NavigationLink(
        pk=10,
        code="reports",
        title="Reports",
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
    )

    source_node = LaunchpadNode(
        pk=20,
        kind=LaunchpadNode.Kind.LINK,
        navigation_link=link,
    )

    resolved = ResolvedNode(
        node_id=20,
        link_id=10,
        kind=LaunchpadNode.Kind.LINK,
        code="reports",
        link_code="reports",
        title="Reports",
        short_title="Reports",
        description="",
        tooltip="",
        aria_label="Reports",
        cta_label="",
        url="/reports/",
        target="_self",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
        source_node=source_node,
        source_link=link,
    )

    assert resolved.source_node is source_node
    assert resolved.source_link is link


def test_source_models_do_not_participate_in_resolved_node_equality() -> None:
    """Source model references should not alter renderer-neutral equality."""
    first_link = NavigationLink(
        pk=10,
        code="reports",
        title="Reports",
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
    )

    second_link = NavigationLink(
        pk=11,
        code="other",
        title="Other",
        url_type=NavigationLink.URLType.RAW,
        url_value="/other/",
    )

    first = ResolvedNode(
        node_id=20,
        link_id=10,
        kind=LaunchpadNode.Kind.LINK,
        code="reports",
        link_code="reports",
        title="Reports",
        short_title="Reports",
        description="",
        tooltip="",
        aria_label="Reports",
        cta_label="",
        url="/reports/",
        target="_self",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
        source_link=first_link,
    )

    second = ResolvedNode(
        node_id=20,
        link_id=10,
        kind=LaunchpadNode.Kind.LINK,
        code="reports",
        link_code="reports",
        title="Reports",
        short_title="Reports",
        description="",
        tooltip="",
        aria_label="Reports",
        cta_label="",
        url="/reports/",
        target="_self",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
        source_link=second_link,
    )

    assert first == second


def test_resolved_launchpad_is_empty_by_default() -> None:
    """Resolved Launchpads should default to an empty node list."""
    launchpad = ResolvedLaunchpad(
        code="home",
        title="Home",
        description="",
        metadata={},
        exists=True,
    )

    assert launchpad.nodes == []
    assert launchpad.is_empty is True


def test_resolved_launchpad_is_not_empty_when_nodes_exist() -> None:
    """Resolved Launchpads should report when renderable nodes exist."""
    node = ResolvedNode(
        node_id=1,
        link_id=None,
        kind=LaunchpadNode.Kind.SECTION,
        code="reports",
        link_code="",
        title="Reports",
        short_title="Reports",
        description="",
        tooltip="",
        aria_label="Reports",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    launchpad = ResolvedLaunchpad(
        code="home",
        title="Home",
        description="",
        metadata={},
        exists=True,
        nodes=[
            node,
        ],
    )

    assert launchpad.is_empty is False


def test_resolved_launchpad_uses_independent_default_nodes() -> None:
    """Default Launchpad node lists should not be shared."""
    first = ResolvedLaunchpad(
        code="first",
        title="First",
        description="",
        metadata={},
        exists=True,
    )

    second = ResolvedLaunchpad(
        code="second",
        title="Second",
        description="",
        metadata={},
        exists=True,
    )

    node = ResolvedNode(
        node_id=1,
        link_id=None,
        kind=LaunchpadNode.Kind.SEPARATOR,
        code="separator-1",
        link_code="",
        title="",
        short_title="",
        description="",
        tooltip="",
        aria_label="",
        cta_label="",
        url="#",
        target="",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=False,
    )

    first.nodes.append(node)

    assert first.nodes == [
        node,
    ]
    assert second.nodes == []


def test_resolved_launchpad_preserves_source_launchpad() -> None:
    """Live reader results should retain their source Launchpad when available."""
    source = Launchpad(
        pk=10,
        code="home",
        title="Home",
    )

    resolved = ResolvedLaunchpad(
        code="home",
        title="Home",
        description="",
        metadata={},
        exists=True,
        source_launchpad=source,
    )

    assert resolved.source_launchpad is source


def test_source_launchpad_does_not_participate_in_equality() -> None:
    """Source Launchpad references should not change resolved equality."""
    first_source = Launchpad(
        pk=1,
        code="home",
        title="Home",
    )

    second_source = Launchpad(
        pk=2,
        code="other",
        title="Other",
    )

    first = ResolvedLaunchpad(
        code="home",
        title="Home",
        description="",
        metadata={},
        exists=True,
        source_launchpad=first_source,
    )

    second = ResolvedLaunchpad(
        code="home",
        title="Home",
        description="",
        metadata={},
        exists=True,
        source_launchpad=second_source,
    )

    assert first == second


def test_models_module_exports_expected_symbols() -> None:
    """The result-model module should expose only its intentional API."""
    from launchpad.readers import models  # noqa: PLC0415

    assert models.__all__ == [
        "ResolvedLaunchpad",
        "ResolvedNode",
    ]
