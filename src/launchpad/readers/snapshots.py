"""
src/launchpad/readers/snapshots.py

Cache-safe Launchpad configuration snapshots.

Snapshots contain only stable configuration data suitable for persistent
caching. Request-, user-, time-, and context-sensitive resolution remains in
the reader resolution layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from launchpad.models import LaunchpadNode, NavigationLink


@dataclass(frozen=True, slots=True)
class CachedAccessPolicy:
    """
    Cache-safe access-policy snapshot.

    Only primitive values required by the visibility engine are stored.
    """

    active: bool
    audience: str
    permissions_required: tuple[str, ...]
    permissions_mode: str

    visible_from: Any | None
    visible_until: Any | None
    visibility_rule: str

    user_ids: tuple[Any, ...]
    group_ids: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class CachedNavigationLink:
    """Cache-safe snapshot of one NavigationLink."""

    pk: int

    code: str
    title: str
    short_title: str
    description: str
    tooltip: str
    aria_label: str
    cta_label: str

    url_type: str
    url_value: str
    url_args: tuple[Any, ...]
    url_kwargs: dict[str, Any]
    query_params: dict[str, Any]
    fragment: str

    target: str
    rel: str
    download: bool

    icon_type: str
    icon_class: str
    emoji: str

    enabled: bool
    disabled_reason: str

    active_match: str
    active_path: str
    active_view_name: str

    metadata: dict[str, Any]

    access: CachedAccessPolicy


@dataclass(frozen=True, slots=True)
class CachedLaunchpadNode:
    """Cache-safe snapshot of one LaunchpadNode."""

    pk: int
    parent_id: int | None

    code: str
    kind: str
    sort_order: int

    title_override: str
    short_title_override: str
    description_override: str
    tooltip_override: str
    aria_label_override: str
    cta_label_override: str

    icon_type_override: str
    icon_class_override: str
    emoji_override: str

    enabled_override: bool | None
    disabled_reason_override: str

    metadata: dict[str, Any]

    navigation_link: CachedNavigationLink | None
    access: CachedAccessPolicy


@dataclass(frozen=True, slots=True)
class CachedLaunchpadConfiguration:
    """Cache-safe snapshot of one Launchpad and all active nodes."""

    pk: int
    code: str
    title: str
    description: str
    metadata: dict[str, Any]

    nodes: tuple[CachedLaunchpadNode, ...]


def snapshot_access_policy(
    obj: LaunchpadNode | NavigationLink,
) -> CachedAccessPolicy:
    """
    Return a cache-safe access-policy snapshot.

    Related user and group IDs are read through ``.all()`` so callers can
    benefit from Django's prefetch cache.
    """
    return CachedAccessPolicy(
        active=obj.active,
        audience=obj.audience,
        permissions_required=tuple(
            obj.permissions_required or [],
        ),
        permissions_mode=obj.permissions_mode,
        visible_from=obj.visible_from,
        visible_until=obj.visible_until,
        visibility_rule=obj.visibility_rule,
        user_ids=tuple(user.pk for user in obj.users.all()),
        group_ids=tuple(group.pk for group in obj.groups.all()),
    )


def snapshot_navigation_link(
    link: NavigationLink,
) -> CachedNavigationLink:
    """Return a cache-safe snapshot of one NavigationLink."""
    return CachedNavigationLink(
        pk=link.pk,
        code=link.code,
        title=link.title,
        short_title=link.short_title,
        description=link.description,
        tooltip=link.tooltip,
        aria_label=link.aria_label,
        cta_label=link.cta_label,
        url_type=link.url_type,
        url_value=link.url_value,
        url_args=tuple(link.url_args or []),
        url_kwargs=dict(link.url_kwargs or {}),
        query_params=dict(link.query_params or {}),
        fragment=link.fragment,
        target=link.target,
        rel=link.rel,
        download=link.download,
        icon_type=link.icon_type,
        icon_class=link.icon_class,
        emoji=link.emoji,
        enabled=link.enabled,
        disabled_reason=link.disabled_reason,
        active_match=link.active_match,
        active_path=link.active_path,
        active_view_name=link.active_view_name,
        metadata=dict(link.metadata or {}),
        access=snapshot_access_policy(link),
    )


def snapshot_node(
    node: LaunchpadNode,
) -> CachedLaunchpadNode:
    """Return a cache-safe snapshot of one LaunchpadNode."""
    return CachedLaunchpadNode(
        pk=node.pk,
        parent_id=node.parent.pk if node.parent is not None else None,
        code=node.code,
        kind=node.kind,
        sort_order=node.sort_order,
        title_override=node.title_override,
        short_title_override=node.short_title_override,
        description_override=node.description_override,
        tooltip_override=node.tooltip_override,
        aria_label_override=node.aria_label_override,
        cta_label_override=node.cta_label_override,
        icon_type_override=node.icon_type_override,
        icon_class_override=node.icon_class_override,
        emoji_override=node.emoji_override,
        enabled_override=node.enabled_override,
        disabled_reason_override=node.disabled_reason_override,
        metadata=dict(node.metadata or {}),
        navigation_link=(
            snapshot_navigation_link(node.navigation_link)
            if node.navigation_link is not None
            else None
        ),
        access=snapshot_access_policy(node),
    )


__all__ = [
    "CachedAccessPolicy",
    "CachedLaunchpadConfiguration",
    "CachedLaunchpadNode",
    "CachedNavigationLink",
    "snapshot_access_policy",
    "snapshot_navigation_link",
    "snapshot_node",
]
