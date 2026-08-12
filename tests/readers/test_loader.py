"""
tests/readers/test_loader.py

Tests for Launchpad reader database and persistent-cache loading.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from launchpad.models import Launchpad
from launchpad.readers import loader
from launchpad.readers.snapshots import CachedLaunchpadConfiguration
from tests.builders import (
    create_group,
    create_launchpad,
    create_link_node,
    create_navigation_link,
    create_section_node,
    create_user,
)


class FakeCacheBackend:
    """Minimal Django-cache test double for loader orchestration tests."""

    def __init__(
        self,
        *,
        get_value: Any = None,
    ) -> None:
        self.get_value = get_value

        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, Any, int | None]] = []

    def get(
        self,
        key: str,
    ) -> Any:
        """Return the configured cache value."""
        self.get_calls.append(
            key,
        )
        return self.get_value

    def set(
        self,
        key: str,
        value: Any,
        timeout: int | None = None,
    ) -> None:
        """Record one cache write."""
        self.set_calls.append(
            (
                key,
                value,
                timeout,
            ),
        )


@pytest.mark.django_db
def test_load_database_configuration_returns_active_launchpad() -> None:
    """The live loader should return the requested active Launchpad."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    result = loader.load_database_configuration(
        "home",
    )

    assert result is not None
    assert result.launchpad == launchpad
    assert result.nodes == []


@pytest.mark.django_db
def test_load_database_configuration_returns_none_for_missing_code() -> None:
    """Unknown Launchpad codes should fail safely."""
    assert (
        loader.load_database_configuration(
            "missing",
        )
        is None
    )


@pytest.mark.django_db
def test_load_database_configuration_returns_none_for_inactive_launchpad() -> None:
    """Inactive Launchpads should not be returned."""
    create_launchpad(
        code="home",
        title="Home",
        active=False,
    )

    assert (
        loader.load_database_configuration(
            "home",
        )
        is None
    )


@pytest.mark.django_db
def test_load_database_configuration_normalizes_code() -> None:
    """Surrounding whitespace should be ignored."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    result = loader.load_database_configuration(
        "  home  ",
    )

    assert result is not None
    assert result.launchpad == launchpad


@pytest.mark.django_db
def test_load_database_configuration_rejects_empty_code() -> None:
    """Empty normalized codes should avoid database lookup."""
    with CaptureQueriesContext(
        connection,
    ) as queries:
        result = loader.load_database_configuration(
            "   ",
        )

    assert result is None
    assert len(queries) == 0


@pytest.mark.django_db
def test_database_loader_returns_only_active_nodes() -> None:
    """Inactive nodes should not participate in reader configuration."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    active_node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        active=True,
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        code="inactive-reports",
        active=False,
    )

    result = loader.load_database_configuration(
        "home",
    )

    assert result is not None
    assert result.nodes == [
        active_node,
    ]


@pytest.mark.django_db
def test_database_loader_orders_nodes_by_parent_sort_order_and_pk() -> None:
    """Database loading should preserve deterministic tree ordering."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    first_link = create_navigation_link(
        code="first",
        title="First",
    )

    second_link = create_navigation_link(
        code="second",
        title="Second",
    )

    section = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
        sort_order=3000,
    )

    second = create_link_node(
        launchpad=launchpad,
        navigation_link=second_link,
        sort_order=2000,
    )

    first = create_link_node(
        launchpad=launchpad,
        navigation_link=first_link,
        sort_order=1000,
    )

    child = create_link_node(
        launchpad=launchpad,
        navigation_link=first_link,
        parent=section,
        code="section-child",
        sort_order=1000,
    )

    result = loader.load_database_configuration(
        "home",
    )

    assert result is not None

    assert result.nodes == [
        first,
        second,
        section,
        child,
    ]


@pytest.mark.django_db
def test_database_loader_eagerly_loads_snapshot_relationships() -> None:
    """
    Snapshotting a loaded configuration should issue no additional queries.

    This verifies parent, NavigationLink, users, and groups are loaded using
    select_related/prefetch_related before snapshot construction.
    """
    user = create_user(
        username="visible-user",
    )

    group = create_group(
        name="visible-group",
    )

    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    section = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    link.users.add(
        user,
    )
    link.groups.add(
        group,
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        parent=section,
    )

    node.users.add(
        user,
    )
    node.groups.add(
        group,
    )

    configuration = loader.load_database_configuration(
        "home",
    )

    assert configuration is not None

    with CaptureQueriesContext(
        connection,
    ) as queries:
        snapshot = loader._snapshot_configuration(  # noqa: SLF001
            configuration,
        )

    assert len(queries) == 0
    assert snapshot.code == "home"
    assert len(snapshot.nodes) == 2


@pytest.mark.django_db
def test_snapshot_configuration_copies_launchpad_fields() -> None:
    """Snapshot conversion should preserve Launchpad configuration."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
        description="Homepage navigation.",
        metadata={
            "renderer": "cards",
        },
    )

    configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    snapshot = loader._snapshot_configuration(  # noqa: SLF001
        configuration,
    )

    assert snapshot.pk == launchpad.pk
    assert snapshot.code == "home"
    assert snapshot.title == "Home"
    assert snapshot.description == "Homepage navigation."

    assert snapshot.metadata == {
        "renderer": "cards",
    }

    assert snapshot.metadata is not launchpad.metadata
    assert snapshot.nodes == ()


@pytest.mark.django_db
def test_runtime_rule_detection_finds_node_rule() -> None:
    """A node runtime rule should make configuration non-cacheable."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    node = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
        visibility_rule="node_rule",
    )

    configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[
            node,
        ],
    )

    assert (
        loader._has_runtime_visibility_rules(  # noqa: SLF001
            configuration,
        )
        is True
    )


@pytest.mark.django_db
def test_runtime_rule_detection_finds_link_rule() -> None:
    """A NavigationLink runtime rule should make configuration non-cacheable."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        visibility_rule="link_rule",
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[
            node,
        ],
    )

    assert (
        loader._has_runtime_visibility_rules(  # noqa: SLF001
            configuration,
        )
        is True
    )


@pytest.mark.django_db
def test_runtime_rule_detection_returns_false_without_rules() -> None:
    """Stable configurations should be eligible for persistent caching."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[
            node,
        ],
    )

    assert (
        loader._has_runtime_visibility_rules(  # noqa: SLF001
            configuration,
        )
        is False
    )


@pytest.mark.django_db
def test_load_configuration_uses_live_database_path_when_cache_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabled caching should preserve the original ORM-backed reader path."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: False,
    )

    result = loader.load_configuration(
        "home",
    )

    assert isinstance(
        result,
        loader.DatabaseLaunchpadConfiguration,
    )

    assert result.launchpad == launchpad


def test_cache_disabled_path_does_not_access_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabled caching should never touch Django's cache backend."""
    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: False,
    )

    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: None,
    )

    def fail_backend() -> Any:
        pytest.fail("Cache backend should not be accessed when caching is disabled.")

    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        fail_backend,
    )

    assert (
        loader.load_configuration(
            "home",
        )
        is None
    )


def test_load_configuration_returns_cached_snapshot_on_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid cached configuration should bypass the database."""
    cached = CachedLaunchpadConfiguration(
        pk=1,
        code="home",
        title="Home",
        description="",
        metadata={},
        nodes=(),
    )

    backend = FakeCacheBackend(
        get_value=cached,
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )

    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )

    def fail_database(
        code: str,
    ) -> Any:
        pytest.fail("Database should not be accessed on a valid cache hit.")

    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        fail_database,
    )

    result = loader.load_configuration(
        "home",
    )

    assert result is cached
    assert backend.get_calls == [
        "cache-key",
    ]
    assert backend.set_calls == []


def test_load_configuration_ignores_invalid_cached_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected cache values should be treated as misses."""
    backend = FakeCacheBackend(
        get_value={
            "not": "a launchpad snapshot",
        },
    )

    launchpad = Launchpad(
        pk=1,
        code="home",
        title="Home",
    )

    database_configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    snapshot = CachedLaunchpadConfiguration(
        pk=1,
        code="home",
        title="Home",
        description="",
        metadata={},
        nodes=(),
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )

    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )

    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: database_configuration,
    )

    monkeypatch.setattr(
        loader,
        "_has_runtime_visibility_rules",
        lambda configuration: False,
    )

    monkeypatch.setattr(
        loader,
        "_snapshot_configuration",
        lambda configuration: snapshot,
    )

    monkeypatch.setattr(
        loader,
        "get_cache_timeout",
        lambda: 900,
    )

    result = loader.load_configuration(
        "home",
    )

    assert result is snapshot

    assert backend.set_calls == [
        (
            "cache-key",
            snapshot,
            900,
        ),
    ]


def test_load_configuration_returns_none_for_database_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache misses followed by database misses should return None."""
    backend = FakeCacheBackend()

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )

    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )

    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: None,
    )

    result = loader.load_configuration(
        "missing",
    )

    assert result is None
    assert backend.set_calls == []


def test_load_configuration_keeps_runtime_rule_configuration_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime visibility rules should force the ORM-backed path."""
    backend = FakeCacheBackend()

    launchpad = Launchpad(
        pk=1,
        code="home",
        title="Home",
    )

    database_configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )

    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )

    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: database_configuration,
    )

    monkeypatch.setattr(
        loader,
        "_has_runtime_visibility_rules",
        lambda configuration: True,
    )

    result = loader.load_configuration(
        "home",
    )

    assert result is database_configuration
    assert backend.set_calls == []


def test_load_configuration_snapshots_and_caches_stable_database_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stable cache misses should be snapshotted and persisted."""
    backend = FakeCacheBackend()

    launchpad = Launchpad(
        pk=1,
        code="home",
        title="Home",
    )

    database_configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    snapshot = CachedLaunchpadConfiguration(
        pk=1,
        code="home",
        title="Home",
        description="",
        metadata={},
        nodes=(),
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )

    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )

    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: database_configuration,
    )

    monkeypatch.setattr(
        loader,
        "_has_runtime_visibility_rules",
        lambda configuration: False,
    )

    monkeypatch.setattr(
        loader,
        "_snapshot_configuration",
        lambda configuration: snapshot,
    )

    monkeypatch.setattr(
        loader,
        "get_cache_timeout",
        lambda: 1800,
    )

    result = loader.load_configuration(
        "home",
    )

    assert result is snapshot

    assert backend.set_calls == [
        (
            "cache-key",
            snapshot,
            1800,
        ),
    ]


def test_load_configuration_normalizes_code_before_cache_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The loader should normalize codes before cache access."""
    backend = FakeCacheBackend()

    received_codes: list[str] = []

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )

    def configuration_cache_key(
        code: str,
    ) -> str:
        received_codes.append(
            code,
        )
        return "cache-key"

    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        configuration_cache_key,
    )

    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: None,
    )

    loader.load_configuration(
        "  home  ",
    )

    assert received_codes == [
        "home",
    ]


def test_load_configuration_empty_code_avoids_cache_and_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty normalized codes should short-circuit before any I/O."""

    def fail_cache_enabled() -> bool:
        pytest.fail("Cache configuration should not be consulted for empty codes.")

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        fail_cache_enabled,
    )

    assert (
        loader.load_configuration(
            "   ",
        )
        is None
    )


def test_load_cached_configuration_returns_snapshot_when_cache_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Explicit cached loading should snapshot database configuration even when
    persistent caching is disabled.
    """
    launchpad = Launchpad(
        pk=1,
        code="home",
        title="Home",
    )

    database_configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    snapshot = CachedLaunchpadConfiguration(
        pk=1,
        code="home",
        title="Home",
        description="",
        metadata={},
        nodes=(),
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: False,
    )

    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: database_configuration,
    )

    monkeypatch.setattr(
        loader,
        "_snapshot_configuration",
        lambda configuration: snapshot,
    )

    result = loader.load_cached_configuration(
        "home",
    )

    assert result is snapshot


@pytest.mark.django_db
def test_load_cached_configuration_returns_none_when_database_missing() -> None:
    """Empty explicit cached loads should fail safely."""
    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=False,
    ):
        result = loader.load_cached_configuration(
            "missing",
        )

    assert result is None
    """Empty explicit cached loads should fail safely."""
    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=False,
    ):
        result = loader.load_cached_configuration(
            "missing",
        )

    assert result is None


def test_load_cached_configuration_returns_valid_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit cached loading should honor valid persistent snapshots."""
    snapshot = CachedLaunchpadConfiguration(
        pk=1,
        code="home",
        title="Home",
        description="",
        metadata={},
        nodes=(),
    )

    backend = FakeCacheBackend(
        get_value=snapshot,
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )

    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )

    result = loader.load_cached_configuration(
        "home",
    )

    assert result is snapshot
    assert backend.set_calls == []


def test_loader_module_exports_expected_symbols() -> None:
    """The loader module should expose only its intentional reader API."""
    assert loader.__all__ == [
        "DatabaseLaunchpadConfiguration",
        "load_cached_configuration",
        "load_configuration",
        "load_database_configuration",
    ]


def test_load_cached_configuration_returns_none_after_cache_and_database_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistent cache miss followed by a database miss should return None."""
    backend = FakeCacheBackend(
        get_value=None,
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )
    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: None,
    )

    result = loader.load_cached_configuration(
        "missing",
    )

    assert result is None
    assert backend.get_calls == [
        "cache-key",
    ]
    assert backend.set_calls == []


def test_load_cached_configuration_returns_cached_snapshot_without_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid cached snapshot should bypass the database entirely."""
    snapshot = CachedLaunchpadConfiguration(
        pk=1,
        code="home",
        title="Home",
        description="",
        metadata={},
        nodes=(),
    )

    backend = FakeCacheBackend(
        get_value=snapshot,
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )

    def fail_database(
        code: str,
    ) -> Any:
        pytest.fail("Database should not be accessed on cache hit.")

    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        fail_database,
    )

    result = loader.load_cached_configuration(
        "home",
    )

    assert result is snapshot
    assert backend.get_calls == [
        "cache-key",
    ]
    assert backend.set_calls == []


def test_load_cached_configuration_persists_stable_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stable database configuration should be snapshotted and cached."""
    backend = FakeCacheBackend(
        get_value=None,
    )

    launchpad = Launchpad(
        pk=1,
        code="home",
        title="Home",
    )

    database_configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    snapshot = CachedLaunchpadConfiguration(
        pk=1,
        code="home",
        title="Home",
        description="",
        metadata={},
        nodes=(),
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )
    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: database_configuration,
    )
    monkeypatch.setattr(
        loader,
        "_snapshot_configuration",
        lambda configuration: snapshot,
    )
    monkeypatch.setattr(
        loader,
        "_has_runtime_visibility_rules",
        lambda configuration: False,
    )
    monkeypatch.setattr(
        loader,
        "get_cache_timeout",
        lambda: 1800,
    )

    result = loader.load_cached_configuration(
        "home",
    )

    assert result is snapshot

    assert backend.set_calls == [
        (
            "cache-key",
            snapshot,
            1800,
        ),
    ]


def test_load_cached_configuration_does_not_persist_runtime_rule_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime-rule snapshots may be returned but should not be persisted."""
    backend = FakeCacheBackend(
        get_value=None,
    )

    launchpad = Launchpad(
        pk=1,
        code="home",
        title="Home",
    )

    database_configuration = loader.DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    snapshot = CachedLaunchpadConfiguration(
        pk=1,
        code="home",
        title="Home",
        description="",
        metadata={},
        nodes=(),
    )

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        loader,
        "get_cache_backend",
        lambda: backend,
    )
    monkeypatch.setattr(
        loader,
        "configuration_cache_key",
        lambda code: "cache-key",
    )
    monkeypatch.setattr(
        loader,
        "_load_database_configuration",
        lambda code: database_configuration,
    )
    monkeypatch.setattr(
        loader,
        "_snapshot_configuration",
        lambda configuration: snapshot,
    )
    monkeypatch.setattr(
        loader,
        "_has_runtime_visibility_rules",
        lambda configuration: True,
    )

    result = loader.load_cached_configuration(
        "home",
    )

    assert result is snapshot
    assert backend.set_calls == []


def test_load_cached_configuration_empty_code_avoids_cache_and_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty normalized codes should short-circuit before any I/O."""

    def fail_cache_enabled() -> bool:
        pytest.fail("Cache configuration should not be consulted for empty codes.")

    monkeypatch.setattr(
        loader,
        "is_cache_enabled",
        fail_cache_enabled,
    )

    assert (
        loader.load_cached_configuration(
            "   ",
        )
        is None
    )
