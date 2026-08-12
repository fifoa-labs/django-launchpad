"""
src/launchpad/readers/loader.py

Database and persistent-cache loading for Launchpad reader configuration.

This module owns the boundary between Django ORM objects and cache-safe
configuration snapshots.

Caching is deliberately limited to stable Launchpad configuration. When
persistent caching is disabled, readers receive the original Django model
instances. When caching is enabled, stable configurations may be loaded from
or written to Django's configured Launchpad cache backend.

Launchpads containing registered runtime visibility-rule references bypass
persistent configuration caching. Runtime visibility rules may rely on real
model objects, so preserving the ORM path avoids changing their public
behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

from launchpad.cache import (
    configuration_cache_key,
    get_cache_backend,
    get_cache_timeout,
    is_cache_enabled,
)
from launchpad.models import Launchpad, LaunchpadNode

from .snapshots import (
    CachedLaunchpadConfiguration,
    snapshot_node,
)


@dataclass(slots=True)
class DatabaseLaunchpadConfiguration:
    """
    Database-backed Launchpad configuration.

    This representation retains live Django model instances and is used when
    persistent caching is disabled or when the configuration cannot safely be
    represented by the persistent snapshot cache.
    """

    launchpad: Launchpad
    nodes: list[LaunchpadNode]


def _load_database_configuration(
    code: str,
) -> DatabaseLaunchpadConfiguration | None:
    """
    Load one active Launchpad and its active nodes from the database.

    Node relationships required by resolution are loaded eagerly.

    ``navigation_link`` is selected because it is a foreign key. User and
    group visibility relationships are prefetched for both nodes and linked
    NavigationLinks so later visibility evaluation does not produce N+1
    queries.
    """
    launchpad = (
        Launchpad.objects.filter(
            code=code,
            active=True,
        )
        .order_by()
        .first()
    )

    if launchpad is None:
        return None

    nodes = list(
        LaunchpadNode.objects.filter(
            launchpad_id=launchpad.pk,
            active=True,
        )
        .select_related(
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

    return DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=nodes,
    )


def _has_runtime_visibility_rules(
    configuration: DatabaseLaunchpadConfiguration,
) -> bool:
    """
    Return whether the configuration uses runtime visibility rules.

    Persistent snapshots intentionally avoid caching configurations whose
    visibility contract may rely on passing live Django model instances to a
    registered runtime rule.

    A rule on either a LaunchpadNode or its NavigationLink is sufficient to
    force the live ORM path.
    """
    for node in configuration.nodes:
        if node.visibility_rule:
            return True

        link = node.navigation_link

        if link is not None and link.visibility_rule:
            return True

    return False


def _snapshot_configuration(
    configuration: DatabaseLaunchpadConfiguration,
) -> CachedLaunchpadConfiguration:
    """Convert a live database configuration into a cache-safe snapshot."""
    launchpad = configuration.launchpad

    return CachedLaunchpadConfiguration(
        pk=launchpad.pk,
        code=launchpad.code,
        title=launchpad.title,
        description=launchpad.description,
        metadata=dict(launchpad.metadata or {}),
        nodes=tuple(snapshot_node(node) for node in configuration.nodes),
    )


def load_database_configuration(
    code: str,
) -> DatabaseLaunchpadConfiguration | None:
    """
    Return one active Launchpad through the live ORM path.

    This public-to-the-reader-package helper does not use persistent caching.
    It is useful when callers explicitly require real model instances.
    """
    normalized_code = str(code).strip()

    if not normalized_code:
        return None

    return _load_database_configuration(
        normalized_code,
    )


def load_cached_configuration(  # noqa: PLR0911
    code: str,
) -> CachedLaunchpadConfiguration | None:
    """
    Return one cache-safe Launchpad configuration.

    Behavior:

    - When caching is disabled, the database is loaded and immediately
      snapshotted without touching Django's cache backend.
    - When caching is enabled, the configured Launchpad cache alias is checked.
    - Valid cached snapshots are returned directly.
    - Cache misses load fresh ORM data and snapshot it.
    - Configurations containing runtime visibility rules are not persisted.
    - Missing Launchpads are not cached.

    Request-, user-, context-, schedule-, URL-, and active-state resolution is
    intentionally not performed here.
    """
    normalized_code = str(code).strip()

    if not normalized_code:
        return None

    if not is_cache_enabled():
        configuration = _load_database_configuration(
            normalized_code,
        )

        if configuration is None:
            return None

        return _snapshot_configuration(
            configuration,
        )

    backend = get_cache_backend()

    key = configuration_cache_key(
        normalized_code,
    )

    cached = backend.get(
        key,
    )

    if isinstance(
        cached,
        CachedLaunchpadConfiguration,
    ):
        return cached

    configuration = _load_database_configuration(
        normalized_code,
    )

    if configuration is None:
        return None

    snapshot = _snapshot_configuration(
        configuration,
    )

    if _has_runtime_visibility_rules(
        configuration,
    ):
        return snapshot

    backend.set(
        key,
        snapshot,
        timeout=get_cache_timeout(),
    )

    return snapshot


def load_configuration(
    code: str,
) -> DatabaseLaunchpadConfiguration | CachedLaunchpadConfiguration | None:
    """
    Load configuration using the appropriate reader path.

    When persistent caching is disabled, return live ORM configuration so
    django-launchpad preserves its original reader behavior and source-model
    references.

    When caching is enabled, stable configuration is returned as a cache-safe
    snapshot.

    Configurations using runtime visibility rules remain on the live ORM path
    even when caching is enabled.
    """
    normalized_code = str(code).strip()

    if not normalized_code:
        return None

    if not is_cache_enabled():
        return _load_database_configuration(
            normalized_code,
        )

    backend = get_cache_backend()

    key = configuration_cache_key(
        normalized_code,
    )

    cached = backend.get(
        key,
    )

    if isinstance(
        cached,
        CachedLaunchpadConfiguration,
    ):
        return cached

    configuration = _load_database_configuration(
        normalized_code,
    )

    if configuration is None:
        return None

    if _has_runtime_visibility_rules(
        configuration,
    ):
        return configuration

    snapshot = _snapshot_configuration(
        configuration,
    )

    backend.set(
        key,
        snapshot,
        timeout=get_cache_timeout(),
    )

    return snapshot


__all__ = [
    "DatabaseLaunchpadConfiguration",
    "load_cached_configuration",
    "load_configuration",
    "load_database_configuration",
]
