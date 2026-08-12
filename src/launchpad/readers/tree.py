"""
src/launchpad/readers/tree.py

Tree-construction helpers for django-launchpad readers.

This module owns parent/child organization, recursive node resolution,
separator cleanup, and root-node construction for both live ORM and cached
Launchpad configuration.

It intentionally does not perform database access or persistent cache access.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from .resolution import (
    resolve_cached_node,
    resolve_database_node,
)

if TYPE_CHECKING:
    from launchpad.models import LaunchpadNode
    from launchpad.visibility import VisibilityContext

    from .models import ResolvedNode
    from .snapshots import CachedLaunchpadNode


def clean_separators(
    nodes: list[ResolvedNode],
) -> list[ResolvedNode]:
    """
    Remove leading, trailing, and consecutive separators.

    Children are cleaned recursively so renderers receive a structurally valid
    tree and do not need presentation-specific repair logic.

    Examples:

        [separator, link]
            -> [link]

        [link, separator, separator, link]
            -> [link, separator, link]

        [link, separator]
            -> [link]
    """
    cleaned: list[ResolvedNode] = []
    previous_was_separator = True

    for node in nodes:
        if node.children:
            node.children = clean_separators(
                node.children,
            )

        if node.is_separator:
            if previous_was_separator:
                continue

            cleaned.append(
                node,
            )
            previous_was_separator = True
            continue

        cleaned.append(
            node,
        )
        previous_was_separator = False

    while cleaned and cleaned[-1].is_separator:
        cleaned.pop()

    return cleaned


def build_database_children_map(
    nodes: list[LaunchpadNode],
) -> dict[int | None, list[LaunchpadNode]]:
    """Build a parent-ID mapping for live ORM Launchpad nodes."""
    children_map: dict[
        int | None,
        list[LaunchpadNode],
    ] = defaultdict(list)

    for node in nodes:
        parent_id = node.parent.pk if node.parent is not None else None

        children_map[parent_id].append(
            node,
        )

    return children_map


def build_cached_children_map(
    nodes: tuple[CachedLaunchpadNode, ...],
) -> dict[int | None, list[CachedLaunchpadNode]]:
    """Build a parent-ID mapping for cached Launchpad nodes."""
    children_map: dict[
        int | None,
        list[CachedLaunchpadNode],
    ] = defaultdict(list)

    for node in nodes:
        children_map[node.parent_id].append(
            node,
        )

    return children_map


def resolve_database_tree(
    nodes: list[LaunchpadNode],
    *,
    ctx: VisibilityContext,
) -> list[ResolvedNode]:
    """
    Resolve a complete live ORM Launchpad tree.

    Only nodes whose parent is ``None`` become roots.
    """
    children_map = build_database_children_map(
        nodes,
    )

    root_nodes = [
        resolved_node
        for node in children_map.get(
            None,
            [],
        )
        if (
            resolved_node := _resolve_database_tree_node(
                node,
                children_map=children_map,
                ctx=ctx,
            )
        )
        is not None
    ]

    return clean_separators(
        root_nodes,
    )


def _resolve_database_tree_node(
    node: LaunchpadNode,
    *,
    children_map: dict[int | None, list[LaunchpadNode]],
    ctx: VisibilityContext,
) -> ResolvedNode | None:
    """Resolve one live ORM node recursively."""
    resolved_children = [
        resolved_child
        for child in children_map.get(
            node.pk,
            [],
        )
        if (
            resolved_child := _resolve_database_tree_node(
                child,
                children_map=children_map,
                ctx=ctx,
            )
        )
        is not None
    ]

    resolved_children = clean_separators(
        resolved_children,
    )

    return resolve_database_node(
        node,
        children=resolved_children,
        ctx=ctx,
    )


def resolve_cached_tree(
    nodes: tuple[CachedLaunchpadNode, ...],
    *,
    ctx: VisibilityContext,
) -> list[ResolvedNode]:
    """
    Resolve a complete cached Launchpad tree.

    Cached configuration still receives live visibility, URL, context, and
    active-state evaluation during this step.
    """
    children_map = build_cached_children_map(
        nodes,
    )

    root_nodes = [
        resolved_node
        for node in children_map.get(
            None,
            [],
        )
        if (
            resolved_node := _resolve_cached_tree_node(
                node,
                children_map=children_map,
                ctx=ctx,
            )
        )
        is not None
    ]

    return clean_separators(
        root_nodes,
    )


def _resolve_cached_tree_node(
    node: CachedLaunchpadNode,
    *,
    children_map: dict[int | None, list[CachedLaunchpadNode]],
    ctx: VisibilityContext,
) -> ResolvedNode | None:
    """Resolve one cached Launchpad node recursively."""
    resolved_children = [
        resolved_child
        for child in children_map.get(
            node.pk,
            [],
        )
        if (
            resolved_child := _resolve_cached_tree_node(
                child,
                children_map=children_map,
                ctx=ctx,
            )
        )
        is not None
    ]

    resolved_children = clean_separators(
        resolved_children,
    )

    return resolve_cached_node(
        node,
        children=resolved_children,
        ctx=ctx,
    )


__all__ = [
    "build_cached_children_map",
    "build_database_children_map",
    "clean_separators",
    "resolve_cached_tree",
    "resolve_database_tree",
]
