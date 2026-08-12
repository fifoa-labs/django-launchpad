"""
src/launchpad/readers/resolution.py

Request-sensitive Launchpad resolution helpers.

This module turns live or cached Launchpad configuration into renderer-neutral
resolved nodes.

Persistent cache storage deliberately stops before this layer. The helpers
here evaluate behavior that may depend on:

- the current user,
- the current request,
- runtime visibility rules,
- scheduled visibility windows,
- context-aware URL values,
- query parameters,
- active-state calculation,
- and placement overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from launchpad.models import LaunchpadNode, NavigationLink
from launchpad.visibility import VisibilityContext, is_visible

from .models import ResolvedNode

if TYPE_CHECKING:
    from .snapshots import (
        CachedAccessPolicy,
        CachedLaunchpadNode,
        CachedNavigationLink,
    )


@dataclass(frozen=True, slots=True)
class _CachedIdentity:
    """Minimal cached identity exposing a primary key."""

    pk: Any


class _CachedRelatedManager:
    """
    Minimal relation-manager adapter for cached visibility evaluation.

    ``launchpad.visibility`` consumes ``obj.users.all()`` and
    ``obj.groups.all()``. Cached snapshots store only primary keys, so this
    adapter exposes the small relation API required by the visibility engine.
    """

    def __init__(self, ids: tuple[Any, ...]) -> None:
        self._ids = ids

    def all(self) -> list[_CachedIdentity]:
        """Return cached identities exposing only primary keys."""
        return [_CachedIdentity(pk=value) for value in self._ids]


class _CachedVisibilityObject:
    """
    Visibility-compatible adapter around a cached access policy.

    The adapter intentionally exposes only fields consumed by
    ``launchpad.visibility.is_visible``.
    """

    def __init__(
        self,
        *,
        pk: int,
        access: CachedAccessPolicy,
    ) -> None:
        self.pk = pk

        self.active = access.active
        self.audience = access.audience
        self.permissions_required = list(
            access.permissions_required,
        )
        self.permissions_mode = access.permissions_mode

        self.visible_from = access.visible_from
        self.visible_until = access.visible_until
        self.visibility_rule = access.visibility_rule

        self.users = _CachedRelatedManager(
            access.user_ids,
        )
        self.groups = _CachedRelatedManager(
            access.group_ids,
        )

    def is_available_now(self) -> bool:
        """Return whether the current time falls within the visibility window."""
        from django.utils import timezone  # noqa: PLC0415

        now = timezone.now()

        if self.visible_from and now < self.visible_from:
            return False

        return not (self.visible_until and now > self.visible_until)


def cached_object_is_visible(
    *,
    pk: int,
    access: CachedAccessPolicy,
    ctx: VisibilityContext,
) -> bool:
    """Evaluate one cached access policy through the visibility engine."""
    return is_visible(
        _CachedVisibilityObject(
            pk=pk,
            access=access,
        ),
        ctx=ctx,
    )


def cached_node_is_visible(
    node: CachedLaunchpadNode,
    ctx: VisibilityContext,
) -> bool:
    """
    Return whether a cached node and its linked destination are visible.

    Link nodes require both placement visibility and NavigationLink
    visibility. Structural nodes require only placement visibility.
    """
    if not cached_object_is_visible(
        pk=node.pk,
        access=node.access,
        ctx=ctx,
    ):
        return False

    if node.kind != LaunchpadNode.Kind.LINK:
        return True

    link = node.navigation_link

    if link is None:
        return False

    return cached_object_is_visible(
        pk=link.pk,
        access=link.access,
        ctx=ctx,
    )


def database_node_is_visible(
    node: LaunchpadNode,
    ctx: VisibilityContext,
) -> bool:
    """
    Return whether a live ORM node and its linked destination are visible.

    This preserves the original Launchpad visibility behavior when persistent
    caching is disabled or a configuration remains on the ORM path.
    """
    if not is_visible(
        node,
        ctx=ctx,
    ):
        return False

    if node.kind != LaunchpadNode.Kind.LINK:
        return True

    link = node.navigation_link

    if link is None:
        return False

    return is_visible(
        link,
        ctx=ctx,
    )


def metadata_for_cached_node(
    node: CachedLaunchpadNode,
) -> dict[str, Any]:
    """
    Return merged renderer-neutral metadata for a cached node.

    Link metadata forms the base and placement metadata overrides matching
    keys.
    """
    metadata: dict[str, Any] = {}

    if node.navigation_link is not None:
        metadata.update(
            node.navigation_link.metadata,
        )

    metadata.update(
        node.metadata,
    )

    return metadata


def metadata_for_database_node(
    node: LaunchpadNode,
) -> dict[str, Any]:
    """
    Return merged renderer-neutral metadata for a live ORM node.

    Placement metadata takes precedence over NavigationLink metadata.
    """
    metadata: dict[str, Any] = {}

    if node.navigation_link is not None:
        metadata.update(
            node.navigation_link.metadata or {},
        )

    metadata.update(
        node.metadata or {},
    )

    return metadata


def _materialize_cached_link(
    link: CachedNavigationLink,
) -> NavigationLink:
    """
    Recreate a non-persistent NavigationLink from a cached snapshot.

    Re-materializing the model lets the cached reader path reuse the canonical
    model implementation for URL resolution, active matching, icons, labels,
    enabled state, and related behavior instead of duplicating that logic.
    """
    return NavigationLink(
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
        url_args=list(link.url_args),
        url_kwargs=dict(link.url_kwargs),
        query_params=dict(link.query_params),
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
        metadata=dict(link.metadata),
        active=link.access.active,
        audience=link.access.audience,
        permissions_required=list(
            link.access.permissions_required,
        ),
        permissions_mode=link.access.permissions_mode,
        visible_from=link.access.visible_from,
        visible_until=link.access.visible_until,
        visibility_rule=link.access.visibility_rule,
    )


def _materialize_cached_node(
    node: CachedLaunchpadNode,
) -> LaunchpadNode:
    """
    Recreate a non-persistent LaunchpadNode from a cached snapshot.

    The returned instance is used only for canonical placement helper methods.
    It is never saved to the database.
    """
    materialized = LaunchpadNode(
        pk=node.pk,
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
        metadata=dict(node.metadata),
        active=node.access.active,
        audience=node.access.audience,
        permissions_required=list(
            node.access.permissions_required,
        ),
        permissions_mode=node.access.permissions_mode,
        visible_from=node.access.visible_from,
        visible_until=node.access.visible_until,
        visibility_rule=node.access.visibility_rule,
    )

    materialized.navigation_link = (
        _materialize_cached_link(node.navigation_link)
        if node.navigation_link is not None
        else None
    )

    return materialized


def resolve_database_node(
    node: LaunchpadNode,
    *,
    children: list[ResolvedNode],
    ctx: VisibilityContext,
) -> ResolvedNode | None:
    """
    Resolve one live ORM node into renderer-neutral data.

    ``children`` must already contain resolved and separator-cleaned
    descendants.
    """
    if not database_node_is_visible(
        node,
        ctx,
    ):
        return None

    if node.kind == LaunchpadNode.Kind.SECTION and not children:
        return None

    link = node.navigation_link

    enabled = node.effective_enabled

    url = "#"

    if node.kind == LaunchpadNode.Kind.LINK and enabled and link is not None:
        url = node.resolve_url(
            request=ctx.request,
            context=ctx.extra_context,
        )

    self_is_active = node.is_active_for(
        ctx.request,
        context=ctx.extra_context,
    )

    child_is_active = any(child.is_active for child in children)

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
        link_id=link.pk if link is not None else None,
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
        enabled=enabled,
        disabled_reason=node.effective_disabled_reason,
        is_active=bool(self_is_active or child_is_active),
        metadata=metadata_for_database_node(
            node,
        ),
        children=children,
        source_node=node,
        source_link=link,
    )


def resolve_cached_node(
    node: CachedLaunchpadNode,
    *,
    children: list[ResolvedNode],
    ctx: VisibilityContext,
) -> ResolvedNode | None:
    """
    Resolve one cached node into renderer-neutral request data.

    Visibility is evaluated against cached primitive access-policy snapshots.
    All non-visibility model behavior is delegated back to canonical model
    helpers through non-persistent materialized model instances.
    """
    if not cached_node_is_visible(
        node,
        ctx,
    ):
        return None

    if node.kind == LaunchpadNode.Kind.SECTION and not children:
        return None

    materialized = _materialize_cached_node(
        node,
    )

    link = materialized.navigation_link

    enabled = materialized.effective_enabled

    url = "#"

    if materialized.kind == LaunchpadNode.Kind.LINK and enabled and link is not None:
        url = materialized.resolve_url(
            request=ctx.request,
            context=ctx.extra_context,
        )

    self_is_active = materialized.is_active_for(
        ctx.request,
        context=ctx.extra_context,
    )

    child_is_active = any(child.is_active for child in children)

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
        link_id=link.pk if link is not None else None,
        kind=node.kind,
        code=materialized.effective_code,
        link_code=link_code,
        title=materialized.effective_title,
        short_title=materialized.effective_short_title,
        description=materialized.effective_description,
        tooltip=materialized.effective_tooltip,
        aria_label=materialized.effective_aria_label,
        cta_label=materialized.effective_cta_label,
        url=url,
        target=target,
        rel=rel,
        download=download,
        icon=materialized.effective_icon_descriptor,
        enabled=enabled,
        disabled_reason=materialized.effective_disabled_reason,
        is_active=bool(self_is_active or child_is_active),
        metadata=metadata_for_cached_node(
            node,
        ),
        children=children,
        source_node=None,
        source_link=None,
    )


__all__ = [
    "cached_node_is_visible",
    "cached_object_is_visible",
    "database_node_is_visible",
    "metadata_for_cached_node",
    "metadata_for_database_node",
    "resolve_cached_node",
    "resolve_database_node",
]
