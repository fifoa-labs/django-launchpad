"""
tests/readers/test_tree.py

Tests for Launchpad reader tree construction and separator cleanup.
"""

from __future__ import annotations

import pytest

from launchpad.models import LaunchpadNode
from launchpad.readers import tree
from launchpad.readers.models import ResolvedNode
from launchpad.readers.snapshots import (
    CachedAccessPolicy,
    CachedLaunchpadNode,
)
from launchpad.visibility import VisibilityContext
from tests.builders import (
    create_launchpad,
    create_link_node,
    create_navigation_link,
    create_section_node,
)


def _visibility_context() -> VisibilityContext:
    """Return a minimal visibility context for tree tests."""
    return VisibilityContext(
        user=None,
        request=None,
        extra_context={},
        is_authenticated=False,
        is_staff=False,
        is_superuser=False,
        user_id=None,
        group_ids=frozenset(),
        permissions=frozenset(),
    )


def _resolved_node(
    *,
    node_id: int,
    kind: str,
    code: str,
    active: bool = False,
    children: list[ResolvedNode] | None = None,
) -> ResolvedNode:
    """Return a minimal ResolvedNode for structural tests."""
    return ResolvedNode(
        node_id=node_id,
        link_id=None,
        kind=kind,
        code=code,
        link_code="",
        title=code,
        short_title=code,
        description="",
        tooltip="",
        aria_label=code,
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
        is_active=active,
        children=list(
            children or [],
        ),
    )


def _cached_access_policy() -> CachedAccessPolicy:
    """Return a public cached access policy."""
    return CachedAccessPolicy(
        active=True,
        audience="public",
        permissions_required=(),
        permissions_mode="all",
        visible_from=None,
        visible_until=None,
        visibility_rule="",
        user_ids=(),
        group_ids=(),
    )


def _cached_node(
    *,
    pk: int,
    parent_id: int | None = None,
    kind: str = LaunchpadNode.Kind.SECTION,
    code: str = "",
    sort_order: int = 1000,
) -> CachedLaunchpadNode:
    """Return a minimal cached node for tree tests."""
    return CachedLaunchpadNode(
        pk=pk,
        parent_id=parent_id,
        code=code,
        kind=kind,
        sort_order=sort_order,
        title_override=code,
        short_title_override="",
        description_override="",
        tooltip_override="",
        aria_label_override="",
        cta_label_override="",
        icon_type_override="",
        icon_class_override="",
        emoji_override="",
        enabled_override=None,
        disabled_reason_override="",
        metadata={},
        navigation_link=None,
        access=_cached_access_policy(),
    )


def test_clean_separators_removes_leading_separator() -> None:
    """Leading separators should never reach renderers."""
    nodes = [
        _resolved_node(
            node_id=1,
            kind=LaunchpadNode.Kind.SEPARATOR,
            code="separator",
        ),
        _resolved_node(
            node_id=2,
            kind=LaunchpadNode.Kind.LINK,
            code="reports",
        ),
    ]

    result = tree.clean_separators(
        nodes,
    )

    assert [node.code for node in result] == [
        "reports",
    ]


def test_clean_separators_removes_trailing_separator() -> None:
    """Trailing separators should never reach renderers."""
    nodes = [
        _resolved_node(
            node_id=1,
            kind=LaunchpadNode.Kind.LINK,
            code="reports",
        ),
        _resolved_node(
            node_id=2,
            kind=LaunchpadNode.Kind.SEPARATOR,
            code="separator",
        ),
    ]

    result = tree.clean_separators(
        nodes,
    )

    assert [node.code for node in result] == [
        "reports",
    ]


def test_clean_separators_removes_duplicate_separators() -> None:
    """Consecutive separators should collapse to one."""
    nodes = [
        _resolved_node(
            node_id=1,
            kind=LaunchpadNode.Kind.LINK,
            code="first",
        ),
        _resolved_node(
            node_id=2,
            kind=LaunchpadNode.Kind.SEPARATOR,
            code="separator-1",
        ),
        _resolved_node(
            node_id=3,
            kind=LaunchpadNode.Kind.SEPARATOR,
            code="separator-2",
        ),
        _resolved_node(
            node_id=4,
            kind=LaunchpadNode.Kind.LINK,
            code="second",
        ),
    ]

    result = tree.clean_separators(
        nodes,
    )

    assert [node.code for node in result] == [
        "first",
        "separator-1",
        "second",
    ]


def test_clean_separators_preserves_single_internal_separator() -> None:
    """A valid separator between two nodes should remain."""
    nodes = [
        _resolved_node(
            node_id=1,
            kind=LaunchpadNode.Kind.LINK,
            code="first",
        ),
        _resolved_node(
            node_id=2,
            kind=LaunchpadNode.Kind.SEPARATOR,
            code="separator",
        ),
        _resolved_node(
            node_id=3,
            kind=LaunchpadNode.Kind.LINK,
            code="second",
        ),
    ]

    result = tree.clean_separators(
        nodes,
    )

    assert result == nodes


def test_clean_separators_recursively_cleans_children() -> None:
    """Nested child lists should receive the same separator cleanup."""
    parent = _resolved_node(
        node_id=1,
        kind=LaunchpadNode.Kind.SECTION,
        code="section",
        children=[
            _resolved_node(
                node_id=2,
                kind=LaunchpadNode.Kind.SEPARATOR,
                code="leading",
            ),
            _resolved_node(
                node_id=3,
                kind=LaunchpadNode.Kind.LINK,
                code="reports",
            ),
            _resolved_node(
                node_id=4,
                kind=LaunchpadNode.Kind.SEPARATOR,
                code="trailing",
            ),
        ],
    )

    result = tree.clean_separators(
        [
            parent,
        ],
    )

    assert len(result) == 1

    assert [child.code for child in result[0].children] == [
        "reports",
    ]


def test_clean_separators_handles_empty_list() -> None:
    """Empty trees should remain empty."""
    assert (
        tree.clean_separators(
            [],
        )
        == []
    )


def test_clean_separators_handles_separator_only_list() -> None:
    """A separator-only list should resolve to nothing."""
    result = tree.clean_separators(
        [
            _resolved_node(
                node_id=1,
                kind=LaunchpadNode.Kind.SEPARATOR,
                code="separator-1",
            ),
            _resolved_node(
                node_id=2,
                kind=LaunchpadNode.Kind.SEPARATOR,
                code="separator-2",
            ),
        ],
    )

    assert result == []


@pytest.mark.django_db
def test_build_database_children_map_groups_roots_and_children() -> None:
    """ORM nodes should be grouped by parent primary key."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    section = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
    )

    root = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        code="root",
    )

    child = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        parent=section,
        code="child",
    )

    nodes = list(
        LaunchpadNode.objects.filter(
            pk__in=[
                section.pk,
                root.pk,
                child.pk,
            ],
        ).select_related(
            "parent",
        ),
    )

    result = tree.build_database_children_map(
        nodes,
    )

    assert {node.pk for node in result[None]} == {
        section.pk,
        root.pk,
    }

    assert result[section.pk] == [
        child,
    ]


def test_build_cached_children_map_groups_roots_and_children() -> None:
    """Cached nodes should be grouped by stored parent ID."""
    root = _cached_node(
        pk=1,
        parent_id=None,
        code="root",
    )

    section = _cached_node(
        pk=2,
        parent_id=None,
        code="section",
    )

    child = _cached_node(
        pk=3,
        parent_id=2,
        code="child",
    )

    result = tree.build_cached_children_map(
        (
            root,
            section,
            child,
        ),
    )

    assert result[None] == [
        root,
        section,
    ]

    assert result[2] == [
        child,
    ]


@pytest.mark.django_db
def test_resolve_database_tree_resolves_root_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Database tree resolution should resolve root nodes recursively."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    first = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        code="first",
    )

    second = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        code="second",
    )

    nodes = list(
        LaunchpadNode.objects.filter(
            pk__in=[
                first.pk,
                second.pk,
            ],
        ).select_related(
            "parent",
        ),
    )

    calls: list[tuple[int, list[str]]] = []

    def resolve_database_node(
        node: LaunchpadNode,
        *,
        children: list[ResolvedNode],
        ctx: VisibilityContext,
    ) -> ResolvedNode:
        calls.append(
            (
                node.pk,
                [child.code for child in children],
            ),
        )

        return _resolved_node(
            node_id=node.pk,
            kind=node.kind,
            code=node.code,
        )

    monkeypatch.setattr(
        tree,
        "resolve_database_node",
        resolve_database_node,
    )

    result = tree.resolve_database_tree(
        nodes,
        ctx=_visibility_context(),
    )

    assert [node.code for node in result] == [
        first.code,
        second.code,
    ]

    assert calls == [
        (
            first.pk,
            [],
        ),
        (
            second.pk,
            [],
        ),
    ]


@pytest.mark.django_db
def test_resolve_database_tree_resolves_children_before_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Descendants should be resolved before their parent section."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    section = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
    )

    child = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        parent=section,
        code="child",
    )

    nodes = list(
        LaunchpadNode.objects.filter(
            pk__in=[
                section.pk,
                child.pk,
            ],
        ).select_related(
            "parent",
        ),
    )

    calls: list[str] = []

    def resolve_database_node(
        node: LaunchpadNode,
        *,
        children: list[ResolvedNode],
        ctx: VisibilityContext,
    ) -> ResolvedNode:
        calls.append(
            node.code,
        )

        if node.pk == section.pk:
            assert [item.code for item in children] == [
                "child",
            ]

        return _resolved_node(
            node_id=node.pk,
            kind=node.kind,
            code=node.code,
            children=children,
        )

    monkeypatch.setattr(
        tree,
        "resolve_database_node",
        resolve_database_node,
    )

    result = tree.resolve_database_tree(
        nodes,
        ctx=_visibility_context(),
    )

    assert calls == [
        "child",
        "section",
    ]

    assert len(result) == 1
    assert result[0].code == "section"
    assert result[0].children[0].code == "child"


@pytest.mark.django_db
def test_resolve_database_tree_drops_unresolved_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nodes resolving to None should be removed from the tree."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    visible = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        code="visible",
    )

    hidden = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        code="hidden",
    )

    nodes = list(
        LaunchpadNode.objects.filter(
            pk__in=[
                visible.pk,
                hidden.pk,
            ],
        ).select_related(
            "parent",
        ),
    )

    def resolve_database_node(
        node: LaunchpadNode,
        *,
        children: list[ResolvedNode],
        ctx: VisibilityContext,
    ) -> ResolvedNode | None:
        if node.pk == hidden.pk:
            return None

        return _resolved_node(
            node_id=node.pk,
            kind=node.kind,
            code=node.code,
        )

    monkeypatch.setattr(
        tree,
        "resolve_database_node",
        resolve_database_node,
    )

    result = tree.resolve_database_tree(
        nodes,
        ctx=_visibility_context(),
    )

    assert [node.code for node in result] == [
        "visible",
    ]


def test_resolve_cached_tree_resolves_root_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached tree resolution should resolve root nodes recursively."""
    first = _cached_node(
        pk=1,
        code="first",
    )

    second = _cached_node(
        pk=2,
        code="second",
    )

    calls: list[int] = []

    def resolve_cached_node(
        node: CachedLaunchpadNode,
        *,
        children: list[ResolvedNode],
        ctx: VisibilityContext,
    ) -> ResolvedNode:
        calls.append(
            node.pk,
        )

        return _resolved_node(
            node_id=node.pk,
            kind=node.kind,
            code=node.code,
        )

    monkeypatch.setattr(
        tree,
        "resolve_cached_node",
        resolve_cached_node,
    )

    result = tree.resolve_cached_tree(
        (
            first,
            second,
        ),
        ctx=_visibility_context(),
    )

    assert calls == [
        1,
        2,
    ]

    assert [node.code for node in result] == [
        "first",
        "second",
    ]


def test_resolve_cached_tree_resolves_children_before_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached descendants should resolve before their parent."""
    section = _cached_node(
        pk=1,
        code="section",
    )

    child = _cached_node(
        pk=2,
        parent_id=1,
        kind=LaunchpadNode.Kind.LINK,
        code="child",
    )

    calls: list[str] = []

    def resolve_cached_node(
        node: CachedLaunchpadNode,
        *,
        children: list[ResolvedNode],
        ctx: VisibilityContext,
    ) -> ResolvedNode:
        calls.append(
            node.code,
        )

        if node.pk == section.pk:
            assert [item.code for item in children] == [
                "child",
            ]

        return _resolved_node(
            node_id=node.pk,
            kind=node.kind,
            code=node.code,
            children=children,
        )

    monkeypatch.setattr(
        tree,
        "resolve_cached_node",
        resolve_cached_node,
    )

    result = tree.resolve_cached_tree(
        (
            section,
            child,
        ),
        ctx=_visibility_context(),
    )

    assert calls == [
        "child",
        "section",
    ]

    assert result[0].children[0].code == "child"


def test_resolve_cached_tree_drops_unresolved_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached nodes resolving to None should disappear."""
    visible = _cached_node(
        pk=1,
        code="visible",
    )

    hidden = _cached_node(
        pk=2,
        code="hidden",
    )

    def resolve_cached_node(
        node: CachedLaunchpadNode,
        *,
        children: list[ResolvedNode],
        ctx: VisibilityContext,
    ) -> ResolvedNode | None:
        if node.pk == hidden.pk:
            return None

        return _resolved_node(
            node_id=node.pk,
            kind=node.kind,
            code=node.code,
        )

    monkeypatch.setattr(
        tree,
        "resolve_cached_node",
        resolve_cached_node,
    )

    result = tree.resolve_cached_tree(
        (
            visible,
            hidden,
        ),
        ctx=_visibility_context(),
    )

    assert [node.code for node in result] == [
        "visible",
    ]


def test_resolve_cached_tree_cleans_root_separators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root separator cleanup should run after cached resolution."""
    separator = _cached_node(
        pk=1,
        kind=LaunchpadNode.Kind.SEPARATOR,
        code="separator",
    )

    visible = _cached_node(
        pk=2,
        kind=LaunchpadNode.Kind.LINK,
        code="visible",
    )

    def resolve_cached_node(
        node: CachedLaunchpadNode,
        *,
        children: list[ResolvedNode],
        ctx: VisibilityContext,
    ) -> ResolvedNode:
        return _resolved_node(
            node_id=node.pk,
            kind=node.kind,
            code=node.code,
        )

    monkeypatch.setattr(
        tree,
        "resolve_cached_node",
        resolve_cached_node,
    )

    result = tree.resolve_cached_tree(
        (
            separator,
            visible,
        ),
        ctx=_visibility_context(),
    )

    assert [node.code for node in result] == [
        "visible",
    ]


def test_tree_module_exports_expected_symbols() -> None:
    """The tree module should expose only its intentional internal API."""
    assert tree.__all__ == [
        "build_cached_children_map",
        "build_database_children_map",
        "clean_separators",
        "resolve_cached_tree",
        "resolve_database_tree",
    ]
