"""
tests/readers/test_snapshots.py

Tests for cache-safe Launchpad configuration snapshots.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from launchpad.models import LaunchpadNode, NavigationLink
from launchpad.readers import snapshots
from tests.builders import (
    create_group,
    create_launchpad,
    create_link_node,
    create_navigation_link,
    create_section_node,
    create_user,
)


@pytest.mark.django_db
def test_snapshot_access_policy_copies_visibility_fields() -> None:
    """Access-policy snapshots should preserve all stable visibility fields."""
    user1 = create_user(
        username="user1",
    )
    user2 = create_user(
        username="user2",
    )

    group1 = create_group(
        name="group1",
    )
    group2 = create_group(
        name="group2",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        audience=NavigationLink.Audience.PRIVATE,
        permissions_required=[
            "reports.view_report",
            "reports.export_report",
        ],
        permissions_mode=NavigationLink.PermissionMode.ALL,
        visibility_rule="reports_access",
    )

    link.users.set(
        [
            user1,
            user2,
        ],
    )

    link.groups.set(
        [
            group1,
            group2,
        ],
    )

    snapshot = snapshots.snapshot_access_policy(
        link,
    )

    assert snapshot.active is True
    assert snapshot.audience == NavigationLink.Audience.PRIVATE

    assert snapshot.permissions_required == (
        "reports.view_report",
        "reports.export_report",
    )

    assert snapshot.permissions_mode == NavigationLink.PermissionMode.ALL
    assert snapshot.visibility_rule == "reports_access"

    assert snapshot.user_ids == (
        user1.pk,
        user2.pk,
    )

    assert snapshot.group_ids == (
        group1.pk,
        group2.pk,
    )


@pytest.mark.django_db
def test_snapshot_access_policy_preserves_visibility_window() -> None:
    """Visibility-window values should survive snapshot creation."""
    from datetime import timedelta  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    visible_from = timezone.now()
    visible_until = visible_from + timedelta(
        hours=1,
    )

    link = create_navigation_link(
        code="scheduled",
        title="Scheduled",
        visible_from=visible_from,
        visible_until=visible_until,
    )

    snapshot = snapshots.snapshot_access_policy(
        link,
    )

    assert snapshot.visible_from == visible_from
    assert snapshot.visible_until == visible_until


@pytest.mark.django_db
def test_snapshot_access_policy_normalizes_empty_permissions() -> None:
    """Empty permission configuration should become an immutable tuple."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
        permissions_required=[],
    )

    snapshot = snapshots.snapshot_access_policy(
        link,
    )

    assert snapshot.permissions_required == ()


@pytest.mark.django_db
def test_snapshot_access_policy_handles_empty_users_and_groups() -> None:
    """Unassigned visibility relations should snapshot as empty tuples."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    snapshot = snapshots.snapshot_access_policy(
        link,
    )

    assert snapshot.user_ids == ()
    assert snapshot.group_ids == ()


@pytest.mark.django_db
def test_snapshot_access_policy_uses_prefetched_relations() -> None:
    """
    Snapshotting prefetched users and groups should issue no extra queries.

    This protects against replacing ``.all()`` with ``values_list()``, which
    would bypass Django's prefetch cache.
    """
    user = create_user(
        username="visible-user",
    )

    group = create_group(
        name="visible-group",
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

    prefetched = NavigationLink.objects.prefetch_related(
        "users",
        "groups",
    ).get(
        pk=link.pk,
    )

    with CaptureQueriesContext(
        connection,
    ) as queries:
        snapshot = snapshots.snapshot_access_policy(
            prefetched,
        )

    assert len(queries) == 0

    assert snapshot.user_ids == (user.pk,)

    assert snapshot.group_ids == (group.pk,)


@pytest.mark.django_db
def test_snapshot_navigation_link_copies_all_fields() -> None:
    """NavigationLink snapshots should preserve stable destination data."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
        short_title="Rpt",
        description="Reporting tools.",
        tooltip="Open reports.",
        aria_label="Reports area",
        cta_label="Open",
        url_type=NavigationLink.URLType.NAMED,
        url_value="reports:index",
        url_args=[
            1,
            "abc",
        ],
        url_kwargs={
            "pk": 42,
        },
        query_params={
            "tab": "monthly",
        },
        fragment="summary",
        target=NavigationLink.Target.BLANK,
        rel="nofollow",
        download=True,
        icon_type=NavigationLink.IconType.FA,
        icon_class="fa-solid fa-chart-line",
        emoji="📊",
        enabled=False,
        disabled_reason="Unavailable",
        active_match=NavigationLink.ActiveMatch.VIEW_NAME,
        active_path="/reports/",
        active_view_name="reports:index",
        metadata={
            "category": "analytics",
        },
        audience=NavigationLink.Audience.PRIVATE,
        permissions_required=[
            "reports.view_report",
            "reports.export_report",
        ],
        permissions_mode=NavigationLink.PermissionMode.ALL,
        visibility_rule="reports_access",
    )

    snapshot = snapshots.snapshot_navigation_link(
        link,
    )

    assert snapshot.pk == link.pk

    assert snapshot.code == "reports"
    assert snapshot.title == "Reports"
    assert snapshot.short_title == "Rpt"
    assert snapshot.description == "Reporting tools."
    assert snapshot.tooltip == "Open reports."
    assert snapshot.aria_label == "Reports area"
    assert snapshot.cta_label == "Open"

    assert snapshot.url_type == NavigationLink.URLType.NAMED
    assert snapshot.url_value == "reports:index"

    assert snapshot.url_args == (
        1,
        "abc",
    )

    assert snapshot.url_kwargs == {
        "pk": 42,
    }

    assert snapshot.query_params == {
        "tab": "monthly",
    }

    assert snapshot.fragment == "summary"

    assert snapshot.target == NavigationLink.Target.BLANK
    assert snapshot.rel == "nofollow"
    assert snapshot.download is True

    assert snapshot.icon_type == NavigationLink.IconType.FA
    assert snapshot.icon_class == "fa-solid fa-chart-line"
    assert snapshot.emoji == "📊"

    assert snapshot.enabled is False
    assert snapshot.disabled_reason == "Unavailable"

    assert snapshot.active_match == NavigationLink.ActiveMatch.VIEW_NAME
    assert snapshot.active_path == "/reports/"
    assert snapshot.active_view_name == "reports:index"

    assert snapshot.metadata == {
        "category": "analytics",
    }

    assert snapshot.access.audience == NavigationLink.Audience.PRIVATE


@pytest.mark.django_db
def test_snapshot_navigation_link_copies_mutable_values() -> None:
    """Cached snapshots should not alias mutable model JSON values."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
        url_args=[
            1,
            "abc",
        ],
        url_kwargs={
            "pk": 42,
        },
        query_params={
            "tab": "monthly",
        },
        metadata={
            "category": "analytics",
        },
    )

    snapshot = snapshots.snapshot_navigation_link(
        link,
    )

    assert snapshot.url_kwargs is not link.url_kwargs
    assert snapshot.query_params is not link.query_params
    assert snapshot.metadata is not link.metadata

    link.url_args.append(
        "later",
    )
    link.url_kwargs["other"] = 99
    link.query_params["view"] = "yearly"
    link.metadata["new"] = True

    assert snapshot.url_args == (
        1,
        "abc",
    )

    assert snapshot.url_kwargs == {
        "pk": 42,
    }

    assert snapshot.query_params == {
        "tab": "monthly",
    }

    assert snapshot.metadata == {
        "category": "analytics",
    }


@pytest.mark.django_db
def test_snapshot_navigation_link_normalizes_empty_json_values() -> None:
    """Empty JSON containers should snapshot independently."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
        url_args=[],
        url_kwargs={},
        query_params={},
        metadata={},
    )

    snapshot = snapshots.snapshot_navigation_link(
        link,
    )

    assert snapshot.url_args == ()
    assert snapshot.url_kwargs == {}
    assert snapshot.query_params == {}
    assert snapshot.metadata == {}


@pytest.mark.django_db
def test_snapshot_navigation_link_captures_access_policy() -> None:
    """NavigationLink snapshots should embed their access policy."""
    user = create_user(
        username="allowed-user",
    )

    group = create_group(
        name="allowed-group",
    )

    link = create_navigation_link(
        code="private-reports",
        title="Private Reports",
        audience=NavigationLink.Audience.PRIVATE,
        permissions_required=[
            "reports.view_report",
        ],
    )

    link.users.add(
        user,
    )
    link.groups.add(
        group,
    )

    snapshot = snapshots.snapshot_navigation_link(
        link,
    )

    assert snapshot.access.audience == NavigationLink.Audience.PRIVATE

    assert snapshot.access.permissions_required == ("reports.view_report",)

    assert snapshot.access.user_ids == (user.pk,)

    assert snapshot.access.group_ids == (group.pk,)


@pytest.mark.django_db
def test_snapshot_node_copies_all_placement_fields() -> None:
    """LaunchpadNode snapshots should preserve stable placement data."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    parent = create_section_node(
        launchpad=launchpad,
        code="reports-section",
        title_override="Reports",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        parent=parent,
        code="reports-placement",
        sort_order=2000,
        title_override="Reports Override",
        short_title_override="Reports",
        description_override="Override description.",
        tooltip_override="Override tooltip.",
        aria_label_override="Override ARIA",
        cta_label_override="Launch",
        icon_type_override=NavigationLink.IconType.EMOJI,
        icon_class_override="fa-solid fa-star",
        emoji_override="⭐",
        enabled_override=False,
        disabled_reason_override="Disabled here.",
        metadata={
            "placement": "sidebar",
        },
        audience=LaunchpadNode.Audience.STAFF,
        permissions_required=[
            "reports.view_report",
        ],
        permissions_mode=LaunchpadNode.PermissionMode.ANY,
        visibility_rule="node_rule",
    )

    snapshot = snapshots.snapshot_node(
        node,
    )

    assert snapshot.pk == node.pk
    assert snapshot.parent_id == parent.pk

    assert snapshot.code == "reports-placement"
    assert snapshot.kind == LaunchpadNode.Kind.LINK
    assert snapshot.sort_order == 2000

    assert snapshot.title_override == "Reports Override"
    assert snapshot.short_title_override == "Reports"
    assert snapshot.description_override == "Override description."
    assert snapshot.tooltip_override == "Override tooltip."
    assert snapshot.aria_label_override == "Override ARIA"
    assert snapshot.cta_label_override == "Launch"

    assert snapshot.icon_type_override == NavigationLink.IconType.EMOJI
    assert snapshot.icon_class_override == "fa-solid fa-star"
    assert snapshot.emoji_override == "⭐"

    assert snapshot.enabled_override is False
    assert snapshot.disabled_reason_override == "Disabled here."

    assert snapshot.metadata == {
        "placement": "sidebar",
    }

    assert snapshot.navigation_link is not None
    assert snapshot.navigation_link.pk == link.pk

    assert snapshot.access.audience == LaunchpadNode.Audience.STAFF

    assert snapshot.access.permissions_required == ("reports.view_report",)

    assert snapshot.access.permissions_mode == LaunchpadNode.PermissionMode.ANY
    assert snapshot.access.visibility_rule == "node_rule"


@pytest.mark.django_db
def test_snapshot_node_without_parent_uses_none_parent_id() -> None:
    """Root nodes should snapshot with no parent ID."""
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
        code="reports",
    )

    snapshot = snapshots.snapshot_node(
        node,
    )

    assert snapshot.parent_id is None


@pytest.mark.django_db
def test_snapshot_node_without_navigation_link_uses_none() -> None:
    """Structural nodes should snapshot without a NavigationLink."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    node = create_section_node(
        launchpad=launchpad,
        code="reports",
        title_override="Reports",
    )

    snapshot = snapshots.snapshot_node(
        node,
    )

    assert snapshot.navigation_link is None


@pytest.mark.django_db
def test_snapshot_node_copies_metadata() -> None:
    """Placement metadata should not alias the live model dictionary."""
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
        metadata={
            "placement": "sidebar",
        },
    )

    snapshot = snapshots.snapshot_node(
        node,
    )

    assert snapshot.metadata is not node.metadata

    node.metadata["new"] = "value"

    assert snapshot.metadata == {
        "placement": "sidebar",
    }


@pytest.mark.django_db
def test_snapshot_node_normalizes_empty_metadata() -> None:
    """Empty placement metadata should become an empty mapping."""
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
        metadata={},
    )

    snapshot = snapshots.snapshot_node(
        node,
    )

    assert snapshot.metadata == {}


@pytest.mark.django_db
def test_snapshot_node_captures_node_visibility_relations() -> None:
    """Node-level users and groups should be included in the access snapshot."""
    user = create_user(
        username="node-user",
    )

    group = create_group(
        name="node-group",
    )

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

    node.users.add(
        user,
    )

    node.groups.add(
        group,
    )

    snapshot = snapshots.snapshot_node(
        node,
    )

    assert snapshot.access.user_ids == (user.pk,)

    assert snapshot.access.group_ids == (group.pk,)


@pytest.mark.django_db
def test_snapshot_node_uses_prefetched_parent_without_query() -> None:
    """Reading parent PK from a selected parent should require no extra query."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    parent = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        parent=parent,
    )

    loaded = (
        LaunchpadNode.objects.select_related(
            "parent",
            "navigation_link",
        )
        .prefetch_related(
            "users",
            "groups",
            "navigation_link__users",
            "navigation_link__groups",
        )
        .get(
            pk=node.pk,
        )
    )

    with CaptureQueriesContext(
        connection,
    ) as queries:
        snapshot = snapshots.snapshot_node(
            loaded,
        )

    assert len(queries) == 0
    assert snapshot.parent_id == parent.pk


def test_snapshots_module_exports_expected_symbols() -> None:
    """The snapshot module should expose only its intentional internal API."""
    assert snapshots.__all__ == [
        "CachedAccessPolicy",
        "CachedLaunchpadConfiguration",
        "CachedLaunchpadNode",
        "CachedNavigationLink",
        "snapshot_access_policy",
        "snapshot_navigation_link",
        "snapshot_node",
    ]
