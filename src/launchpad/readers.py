"""
src/launchpad/readers.py

Reader helpers for resolving Launchpad trees.

Readers return renderer-neutral data.

They do not know about sidebars, topbars, cards, dropdowns, footers,
mobile menus, or command palettes. Templates decide presentation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from launchpad.models import (
    Launchpad,
    LaunchpadNode,
    NavigationLink,
)
from launchpad.visibility import (
    VisibilityContext,
    build_user_context,
    is_visible,
)


@dataclass(slots=True)
class ResolvedNode:
    """
    Renderer-neutral launchpad node.

    Templates can render this as a sidebar item, topbar item, card, dropdown
    entry, footer link, mobile menu row, or anything else.
    """

    node_id: int | None
    link_id: int | None
    kind: str

    code: str
    link_code: str

    title: str
    short_title: str
    description: str
    tooltip: str
    aria_label: str
    cta_label: str

    url: str
    target: str
    rel: str
    download: bool

    icon: dict[str, str]

    enabled: bool
    disabled_reason: str

    is_active: bool

    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[ResolvedNode] = field(default_factory=list)

    source_node: LaunchpadNode | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    source_link: NavigationLink | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @property
    def is_link(self) -> bool:
        """
        Return True if this node represents a clickable navigation link.
        """
        return self.kind == LaunchpadNode.Kind.LINK

    @property
    def is_section(self) -> bool:
        """
        Return True if this node represents a structural section.
        """
        return self.kind == LaunchpadNode.Kind.SECTION

    @property
    def is_separator(self) -> bool:
        """
        Return True if this node represents a separator.
        """
        return self.kind == LaunchpadNode.Kind.SEPARATOR

    @property
    def has_children(self) -> bool:
        """
        Return True if this node has child nodes.
        """
        return bool(self.children)


@dataclass(slots=True)
class ResolvedLaunchpad:
    """
    Renderer-neutral resolved launchpad.
    """

    code: str
    title: str
    description: str
    metadata: dict[str, Any]
    exists: bool
    nodes: list[ResolvedNode] = field(default_factory=list)

    source_launchpad: Launchpad | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @property
    def is_empty(self) -> bool:
        """
        Return True if this launchpad has no renderable nodes.
        """
        return not self.nodes


def _empty_launchpad(code: str) -> ResolvedLaunchpad:
    """
    Return an empty launchpad result.
    """
    return ResolvedLaunchpad(
        code=code,
        title=code,
        description="",
        metadata={},
        exists=False,
        nodes=[],
    )


def _metadata_for_node(node: LaunchpadNode) -> dict[str, Any]:
    """
    Return merged metadata for a node.

    Link-level metadata is the default. Node-level metadata overrides it.
    """
    metadata: dict[str, Any] = {}

    if node.navigation_link:
        metadata.update(node.navigation_link.metadata or {})

    metadata.update(node.metadata or {})

    return metadata


def _node_is_visible(
    node: LaunchpadNode,
    ctx: VisibilityContext,
) -> bool:
    """
    Return True if a LaunchpadNode and its link are visible.
    """
    if not is_visible(
        node,
        ctx=ctx,
    ):
        return False

    if node.kind != LaunchpadNode.Kind.LINK:
        return True

    if node.navigation_link is None:
        return False

    return is_visible(
        node.navigation_link,
        ctx=ctx,
    )


def _resolve_node(
    node: LaunchpadNode,
    *,
    children_map: dict[int | None, list[LaunchpadNode]],
    ctx: VisibilityContext,
) -> ResolvedNode | None:
    """
    Resolve a LaunchpadNode into renderer-neutral data.
    """
    if not _node_is_visible(
        node,
        ctx,
    ):
        return None

    resolved_children = [
        resolved_child
        for child in children_map.get(node.pk, [])
        if (
            resolved_child := _resolve_node(
                child,
                children_map=children_map,
                ctx=ctx,
            )
        )
        is not None
    ]

    resolved_children = _clean_separators(
        resolved_children,
    )

    if node.kind == LaunchpadNode.Kind.SECTION and not resolved_children:
        return None

    link = node.navigation_link

    url = node.resolve_url(
        request=ctx.request,
        context=ctx.extra_context,
    )

    self_is_active = node.is_active_for(
        ctx.request,
        context=ctx.extra_context,
    )

    child_is_active = any(child.is_active for child in resolved_children)

    is_active_node = bool(self_is_active or child_is_active)

    target = ""
    rel = ""
    download = False
    link_code = ""

    if link is not None:
        target = link.target
        rel = link.effective_rel
        download = link.download
        link_code = link.code

    return ResolvedNode(
        node_id=node.pk,
        link_id=link.pk if link else None,
        kind=node.kind,
        code=node.effective_code,
        link_code=link_code,
        title=node.effective_title,
        short_title=node.effective_short_title,
        description=node.effective_description,
        tooltip=node.effective_tooltip,
        aria_label=node.effective_aria_label,
        cta_label=node.effective_cta_label,
        url=url,
        target=target,
        rel=rel,
        download=download,
        icon=node.effective_icon_descriptor,
        enabled=node.effective_enabled,
        disabled_reason=node.effective_disabled_reason,
        is_active=is_active_node,
        metadata=_metadata_for_node(node),
        children=resolved_children,
        source_node=node,
        source_link=link,
    )


def _clean_separators(
    nodes: list[ResolvedNode],
) -> list[ResolvedNode]:
    """
    Remove leading, trailing, and duplicate separators.

    This lets administrators place separators naturally without renderers
    needing to know how to repair empty/invisible structures.
    """
    cleaned: list[ResolvedNode] = []
    previous_was_separator = True

    for node in nodes:
        if node.children:
            node.children = _clean_separators(
                node.children,
            )

        if node.kind == LaunchpadNode.Kind.SEPARATOR:
            if previous_was_separator:
                continue

            cleaned.append(node)
            previous_was_separator = True
            continue

        cleaned.append(node)
        previous_was_separator = False

    while cleaned and cleaned[-1].kind == LaunchpadNode.Kind.SEPARATOR:
        cleaned.pop()

    return cleaned


def _load_launchpad(
    code: str,
) -> Launchpad | None:
    """
    Load an active launchpad by code.
    """
    return Launchpad.objects.filter(
        code=code,
        active=True,
    ).first()


def _load_nodes(
    launchpad: Launchpad,
) -> list[LaunchpadNode]:
    """
    Load active launchpad nodes with related visibility/link data.
    """
    return list(
        LaunchpadNode.objects.filter(
            launchpad=launchpad,
            active=True,
        )
        .select_related(
            "launchpad",
            "parent",
            "navigation_link",
        )
        .prefetch_related(
            "users",
            "groups",
            "navigation_link__users",
            "navigation_link__groups",
        )
        .order_by(
            "parent_id",
            "sort_order",
            "pk",
        ),
    )


def _build_children_map(
    nodes: list[LaunchpadNode],
) -> dict[int | None, list[LaunchpadNode]]:
    """
    Build parent-id to child-node mapping.
    """
    children_map: dict[int | None, list[LaunchpadNode]] = defaultdict(list)

    for node in nodes:
        children_map[node.parent_id].append(node)

    return children_map


def get_launchpad(
    code: str,
    *,
    user: Any | None = None,
    request: Any | None = None,
    context: dict[str, Any] | None = None,
) -> ResolvedLaunchpad:
    """
    Return a renderer-neutral launchpad tree.

    Missing or inactive launchpads fail safely and return an empty result.

    Reader responsibilities:

    - load the launchpad
    - load active nodes
    - apply node visibility
    - apply linked NavigationLink visibility
    - resolve URLs
    - compute effective labels/icons
    - build the parent/child tree
    - remove empty sections
    - clean separators
    - mark active links/parents

    Presentation is intentionally left to templates.
    """
    ctx = build_user_context(
        user=user,
        request=request,
        context=context,
    )

    launchpad = _load_launchpad(
        code,
    )

    if launchpad is None:
        return _empty_launchpad(
            code,
        )

    nodes = _load_nodes(
        launchpad,
    )

    children_map = _build_children_map(
        nodes,
    )

    root_nodes = [
        resolved_node
        for node in children_map.get(None, [])
        if (
            resolved_node := _resolve_node(
                node,
                children_map=children_map,
                ctx=ctx,
            )
        )
        is not None
    ]

    root_nodes = _clean_separators(
        root_nodes,
    )

    return ResolvedLaunchpad(
        code=launchpad.code,
        title=launchpad.title,
        description=launchpad.description,
        metadata=dict(launchpad.metadata or {}),
        exists=True,
        nodes=root_nodes,
        source_launchpad=launchpad,
    )


__all__ = [
    "ResolvedLaunchpad",
    "ResolvedNode",
    "get_launchpad",
]
