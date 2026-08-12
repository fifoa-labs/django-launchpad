"""
src/launchpad/readers/models.py

Renderer-neutral data models returned by the Launchpad reader API.

These objects intentionally contain no renderer-specific behavior. They can be
consumed by sidebars, dashboards, dropdowns, mobile navigation, command
palettes, or any other presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from launchpad.models import Launchpad, LaunchpadNode, NavigationLink


@dataclass(slots=True)
class ResolvedNode:
    """
    Renderer-neutral Launchpad node.

    A resolved node contains all information a renderer needs after Launchpad
    has applied visibility, URL resolution, active-state logic, hierarchy,
    placement overrides, and metadata merging.
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
        """Return whether this node represents a navigation link."""
        return self.kind == LaunchpadNode.Kind.LINK

    @property
    def is_section(self) -> bool:
        """Return whether this node represents a structural section."""
        return self.kind == LaunchpadNode.Kind.SECTION

    @property
    def is_separator(self) -> bool:
        """Return whether this node represents a structural separator."""
        return self.kind == LaunchpadNode.Kind.SEPARATOR

    @property
    def has_children(self) -> bool:
        """Return whether this node has resolved child nodes."""
        return bool(self.children)


@dataclass(slots=True)
class ResolvedLaunchpad:
    """
    Renderer-neutral resolved Launchpad.

    ``exists`` distinguishes a missing/inactive Launchpad from a valid
    Launchpad whose visible node list happens to be empty.
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
        """Return whether this Launchpad has no renderable nodes."""
        return not self.nodes


__all__ = [
    "ResolvedLaunchpad",
    "ResolvedNode",
]
