"""
tests/readers/test_resolution.py

Tests for request-sensitive Launchpad node resolution.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from launchpad.models import LaunchpadNode, NavigationLink
from launchpad.readers import resolution
from launchpad.readers.models import ResolvedNode
from launchpad.readers.snapshots import (
    CachedAccessPolicy,
    CachedLaunchpadNode,
    CachedNavigationLink,
)
from launchpad.visibility import VisibilityContext
from tests.builders import (
    create_launchpad,
    create_link_node,
    create_navigation_link,
    create_section_node,
)


def _visibility_context(  # noqa: PLR0913
    *,
    user: Any | None = None,
    request: Any | None = None,
    context: dict[str, Any] | None = None,
    is_authenticated: bool = False,
    is_staff: bool = False,
    is_superuser: bool = False,
    user_id: Any | None = None,
    group_ids: frozenset[Any] | None = None,
    permissions: frozenset[str] | None = None,
) -> VisibilityContext:
    """Return a VisibilityContext for reader-resolution tests."""
    return VisibilityContext(
        user=user,
        request=request,
        extra_context=dict(context or {}),
        is_authenticated=is_authenticated,
        is_staff=is_staff,
        is_superuser=is_superuser,
        user_id=user_id,
        group_ids=group_ids or frozenset(),
        permissions=permissions or frozenset(),
    )


def _cached_access_policy(  # noqa: PLR0913
    *,
    active: bool = True,
    audience: str = NavigationLink.Audience.PUBLIC,
    permissions_required: tuple[str, ...] = (),
    permissions_mode: str = NavigationLink.PermissionMode.ALL,
    visible_from: Any | None = None,
    visible_until: Any | None = None,
    visibility_rule: str = "",
    user_ids: tuple[Any, ...] = (),
    group_ids: tuple[Any, ...] = (),
) -> CachedAccessPolicy:
    """Return a cached access policy for resolution tests."""
    return CachedAccessPolicy(
        active=active,
        audience=audience,
        permissions_required=permissions_required,
        permissions_mode=permissions_mode,
        visible_from=visible_from,
        visible_until=visible_until,
        visibility_rule=visibility_rule,
        user_ids=user_ids,
        group_ids=group_ids,
    )


def _cached_link(  # noqa: PLR0913
    *,
    pk: int = 10,
    code: str = "reports",
    title: str = "Reports",
    short_title: str = "",
    description: str = "",
    tooltip: str = "",
    aria_label: str = "",
    cta_label: str = "",
    url_type: str = NavigationLink.URLType.RAW,
    url_value: str = "/reports/",
    url_args: tuple[Any, ...] = (),
    url_kwargs: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    fragment: str = "",
    target: str = NavigationLink.Target.SELF,
    rel: str = "",
    download: bool = False,
    icon_type: str = NavigationLink.IconType.NONE,
    icon_class: str = "",
    emoji: str = "",
    enabled: bool = True,
    disabled_reason: str = "",
    active_match: str = NavigationLink.ActiveMatch.AUTO,
    active_path: str = "",
    active_view_name: str = "",
    metadata: dict[str, Any] | None = None,
    access: CachedAccessPolicy | None = None,
) -> CachedNavigationLink:
    """Return a cached NavigationLink snapshot."""
    return CachedNavigationLink(
        pk=pk,
        code=code,
        title=title,
        short_title=short_title,
        description=description,
        tooltip=tooltip,
        aria_label=aria_label,
        cta_label=cta_label,
        url_type=url_type,
        url_value=url_value,
        url_args=url_args,
        url_kwargs=dict(url_kwargs or {}),
        query_params=dict(query_params or {}),
        fragment=fragment,
        target=target,
        rel=rel,
        download=download,
        icon_type=icon_type,
        icon_class=icon_class,
        emoji=emoji,
        enabled=enabled,
        disabled_reason=disabled_reason,
        active_match=active_match,
        active_path=active_path,
        active_view_name=active_view_name,
        metadata=dict(metadata or {}),
        access=access or _cached_access_policy(),
    )


def _cached_node(  # noqa: PLR0913
    *,
    pk: int = 20,
    parent_id: int | None = None,
    code: str = "reports",
    kind: str = LaunchpadNode.Kind.LINK,
    sort_order: int = 1000,
    title_override: str = "",
    short_title_override: str = "",
    description_override: str = "",
    tooltip_override: str = "",
    aria_label_override: str = "",
    cta_label_override: str = "",
    icon_type_override: str = "",
    icon_class_override: str = "",
    emoji_override: str = "",
    enabled_override: bool | None = None,
    disabled_reason_override: str = "",
    metadata: dict[str, Any] | None = None,
    navigation_link: CachedNavigationLink | None = None,
    access: CachedAccessPolicy | None = None,
) -> CachedLaunchpadNode:
    """Return a cached LaunchpadNode snapshot."""
    return CachedLaunchpadNode(
        pk=pk,
        parent_id=parent_id,
        code=code,
        kind=kind,
        sort_order=sort_order,
        title_override=title_override,
        short_title_override=short_title_override,
        description_override=description_override,
        tooltip_override=tooltip_override,
        aria_label_override=aria_label_override,
        cta_label_override=cta_label_override,
        icon_type_override=icon_type_override,
        icon_class_override=icon_class_override,
        emoji_override=emoji_override,
        enabled_override=enabled_override,
        disabled_reason_override=disabled_reason_override,
        metadata=dict(metadata or {}),
        navigation_link=navigation_link,
        access=access or _cached_access_policy(),
    )


def _resolved_child(
    *,
    active: bool = False,
) -> ResolvedNode:
    """Return a minimal resolved child node."""
    return ResolvedNode(
        node_id=99,
        link_id=199,
        kind=LaunchpadNode.Kind.LINK,
        code="child",
        link_code="child",
        title="Child",
        short_title="Child",
        description="",
        tooltip="",
        aria_label="Child",
        cta_label="",
        url="/child/",
        target="_self",
        rel="",
        download=False,
        icon={
            "kind": "none",
            "value": "",
        },
        enabled=True,
        disabled_reason="",
        is_active=active,
    )


def test_cached_related_manager_returns_identity_objects() -> None:
    """Cached relation adapters should expose primary keys through all()."""
    manager = resolution._CachedRelatedManager(  # noqa: SLF001
        (
            1,
            2,
        ),
    )

    identities = manager.all()

    assert [identity.pk for identity in identities] == [
        1,
        2,
    ]


def test_cached_visibility_object_copies_policy_fields() -> None:
    """The cached visibility adapter should expose visibility-engine fields."""
    access = _cached_access_policy(
        audience=NavigationLink.Audience.PRIVATE,
        permissions_required=("reports.view_report",),
        permissions_mode=NavigationLink.PermissionMode.ANY,
        visibility_rule="reports_rule",
        user_ids=(1,),
        group_ids=(2,),
    )

    obj = resolution._CachedVisibilityObject(  # noqa: SLF001
        pk=10,
        access=access,
    )

    assert obj.pk == 10
    assert obj.active is True
    assert obj.audience == NavigationLink.Audience.PRIVATE

    assert obj.permissions_required == [
        "reports.view_report",
    ]

    assert obj.permissions_mode == NavigationLink.PermissionMode.ANY
    assert obj.visibility_rule == "reports_rule"

    assert [identity.pk for identity in obj.users.all()] == [
        1,
    ]

    assert [identity.pk for identity in obj.groups.all()] == [
        2,
    ]


def test_cached_visibility_object_is_available_now_without_schedule() -> None:
    """Unscheduled cached policies should be available now."""
    obj = resolution._CachedVisibilityObject(  # noqa: SLF001
        pk=1,
        access=_cached_access_policy(),
    )

    assert obj.is_available_now() is True


def test_cached_visibility_object_is_unavailable_before_start() -> None:
    """Future visibility windows should fail availability."""
    from datetime import timedelta  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    obj = resolution._CachedVisibilityObject(  # noqa: SLF001
        pk=1,
        access=_cached_access_policy(
            visible_from=timezone.now()
            + timedelta(
                hours=1,
            ),
        ),
    )

    assert obj.is_available_now() is False


def test_cached_visibility_object_is_unavailable_after_end() -> None:
    """Expired visibility windows should fail availability."""
    from datetime import timedelta  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    obj = resolution._CachedVisibilityObject(  # noqa: SLF001
        pk=1,
        access=_cached_access_policy(
            visible_until=timezone.now()
            - timedelta(
                hours=1,
            ),
        ),
    )

    assert obj.is_available_now() is False


def test_cached_object_is_visible_delegates_to_visibility_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached policy evaluation should delegate through is_visible()."""
    ctx = _visibility_context()

    received: dict[str, Any] = {}

    def is_visible(
        obj: Any,
        *,
        ctx: VisibilityContext,
    ) -> bool:
        received["obj"] = obj
        received["ctx"] = ctx
        return True

    monkeypatch.setattr(
        resolution,
        "is_visible",
        is_visible,
    )

    result = resolution.cached_object_is_visible(
        pk=10,
        access=_cached_access_policy(),
        ctx=ctx,
    )

    assert result is True
    assert received["ctx"] is ctx
    assert received["obj"].pk == 10


def test_cached_node_visibility_fails_when_node_policy_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hidden placement should hide the node without checking its link."""
    node = _cached_node(
        navigation_link=_cached_link(),
    )

    calls: list[int] = []

    def cached_object_is_visible(
        *,
        pk: int,
        access: CachedAccessPolicy,
        ctx: VisibilityContext,
    ) -> bool:
        calls.append(pk)
        return False

    monkeypatch.setattr(
        resolution,
        "cached_object_is_visible",
        cached_object_is_visible,
    )

    result = resolution.cached_node_is_visible(
        node,
        _visibility_context(),
    )

    assert result is False
    assert calls == [
        node.pk,
    ]


def test_cached_structural_node_visibility_uses_node_policy_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structural nodes should not require a NavigationLink policy."""
    node = _cached_node(
        kind=LaunchpadNode.Kind.SECTION,
        navigation_link=None,
    )

    monkeypatch.setattr(
        resolution,
        "cached_object_is_visible",
        lambda **kwargs: True,
    )

    assert (
        resolution.cached_node_is_visible(
            node,
            _visibility_context(),
        )
        is True
    )


def test_cached_link_node_without_link_is_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed cached link nodes should fail closed."""
    node = _cached_node(
        kind=LaunchpadNode.Kind.LINK,
        navigation_link=None,
    )

    monkeypatch.setattr(
        resolution,
        "cached_object_is_visible",
        lambda **kwargs: True,
    )

    assert (
        resolution.cached_node_is_visible(
            node,
            _visibility_context(),
        )
        is False
    )


def test_cached_link_node_requires_link_visibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Link placements should require both node and link policies."""
    link = _cached_link(
        pk=10,
    )

    node = _cached_node(
        pk=20,
        navigation_link=link,
    )

    calls: list[int] = []

    def cached_object_is_visible(
        *,
        pk: int,
        access: CachedAccessPolicy,
        ctx: VisibilityContext,
    ) -> bool:
        calls.append(pk)
        return pk == node.pk

    monkeypatch.setattr(
        resolution,
        "cached_object_is_visible",
        cached_object_is_visible,
    )

    assert (
        resolution.cached_node_is_visible(
            node,
            _visibility_context(),
        )
        is False
    )

    assert calls == [
        node.pk,
        link.pk,
    ]


@pytest.mark.django_db
def test_database_node_visibility_fails_when_node_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hidden ORM placement should fail before its link is checked."""
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

    calls: list[Any] = []

    def is_visible(
        obj: Any,
        *,
        ctx: VisibilityContext,
    ) -> bool:
        calls.append(obj)
        return False

    monkeypatch.setattr(
        resolution,
        "is_visible",
        is_visible,
    )

    assert (
        resolution.database_node_is_visible(
            node,
            _visibility_context(),
        )
        is False
    )

    assert calls == [
        node,
    ]


@pytest.mark.django_db
def test_database_structural_node_visibility_uses_node_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structural ORM nodes should require only their own policy."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    node = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
    )

    calls: list[Any] = []

    def is_visible(
        obj: Any,
        *,
        ctx: VisibilityContext,
    ) -> bool:
        calls.append(obj)
        return True

    monkeypatch.setattr(
        resolution,
        "is_visible",
        is_visible,
    )

    assert (
        resolution.database_node_is_visible(
            node,
            _visibility_context(),
        )
        is True
    )

    assert calls == [
        node,
    ]


@pytest.mark.django_db
def test_database_link_node_requires_link_visibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ORM link nodes should require both node and destination policies."""
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

    calls: list[Any] = []

    def is_visible(
        obj: Any,
        *,
        ctx: VisibilityContext,
    ) -> bool:
        calls.append(obj)
        return obj is node

    monkeypatch.setattr(
        resolution,
        "is_visible",
        is_visible,
    )

    assert (
        resolution.database_node_is_visible(
            node,
            _visibility_context(),
        )
        is False
    )

    assert calls == [
        node,
        link,
    ]


def test_cached_metadata_merges_link_then_node() -> None:
    """Placement metadata should override matching cached link metadata."""
    node = _cached_node(
        metadata={
            "shared": "node",
            "node_only": True,
        },
        navigation_link=_cached_link(
            metadata={
                "shared": "link",
                "link_only": True,
            },
        ),
    )

    assert resolution.metadata_for_cached_node(
        node,
    ) == {
        "shared": "node",
        "link_only": True,
        "node_only": True,
    }


def test_cached_metadata_without_link_uses_node_only() -> None:
    """Structural cached nodes should resolve metadata independently."""
    node = _cached_node(
        kind=LaunchpadNode.Kind.SECTION,
        navigation_link=None,
        metadata={
            "section": True,
        },
    )

    assert resolution.metadata_for_cached_node(
        node,
    ) == {
        "section": True,
    }


@pytest.mark.django_db
def test_database_metadata_merges_link_then_node() -> None:
    """ORM placement metadata should override link metadata."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        metadata={
            "shared": "link",
            "link_only": True,
        },
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        metadata={
            "shared": "node",
            "node_only": True,
        },
    )

    assert resolution.metadata_for_database_node(
        node,
    ) == {
        "shared": "node",
        "link_only": True,
        "node_only": True,
    }


@pytest.mark.django_db
def test_database_metadata_without_link_uses_node_only() -> None:
    """Structural ORM metadata should not require a NavigationLink."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    node = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
        metadata={
            "section": True,
        },
    )

    assert resolution.metadata_for_database_node(
        node,
    ) == {
        "section": True,
    }


def test_materialize_cached_link_restores_model_fields() -> None:
    """Cached links should materialize into equivalent unsaved model objects."""
    snapshot = _cached_link(
        pk=10,
        code="reports",
        title="Reports",
        short_title="Rpt",
        description="Reporting tools.",
        tooltip="Open reports.",
        aria_label="Reports area",
        cta_label="Open",
        url_type=NavigationLink.URLType.NAMED,
        url_value="home",
        url_args=(1,),
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
        icon_type=NavigationLink.IconType.EMOJI,
        emoji="📊",
        enabled=False,
        disabled_reason="Unavailable",
        active_match=NavigationLink.ActiveMatch.VIEW_NAME,
        active_path="/reports/",
        active_view_name="reports:index",
        metadata={
            "category": "analytics",
        },
        access=_cached_access_policy(
            audience=NavigationLink.Audience.PRIVATE,
            permissions_required=("reports.view_report",),
        ),
    )

    link = resolution._materialize_cached_link(  # noqa: SLF001
        snapshot,
    )

    assert isinstance(
        link,
        NavigationLink,
    )

    assert link.pk == 10
    assert link.code == "reports"
    assert link.title == "Reports"
    assert link.url_args == [
        1,
    ]

    assert link.url_kwargs == {
        "pk": 42,
    }

    assert link.metadata == {
        "category": "analytics",
    }

    assert link.audience == NavigationLink.Audience.PRIVATE
    assert link.permissions_required == [
        "reports.view_report",
    ]


def test_materialize_cached_node_without_link() -> None:
    """Structural cached nodes should materialize without a linked model."""
    snapshot = _cached_node(
        kind=LaunchpadNode.Kind.SECTION,
        navigation_link=None,
        title_override="Reports",
    )

    node = resolution._materialize_cached_node(  # noqa: SLF001
        snapshot,
    )

    assert isinstance(
        node,
        LaunchpadNode,
    )

    assert node.pk == snapshot.pk
    assert node.kind == LaunchpadNode.Kind.SECTION
    assert node.title_override == "Reports"
    assert node.navigation_link is None


def test_materialize_cached_node_with_link() -> None:
    """Cached link placements should materialize their NavigationLink."""
    snapshot = _cached_node(
        navigation_link=_cached_link(
            code="reports",
            title="Reports",
        ),
    )

    node = resolution._materialize_cached_node(  # noqa: SLF001
        snapshot,
    )

    assert node.navigation_link is not None
    assert node.navigation_link.code == "reports"


@pytest.mark.django_db
def test_resolve_database_node_returns_none_when_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hidden ORM nodes should not produce resolved data."""
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

    monkeypatch.setattr(
        resolution,
        "database_node_is_visible",
        lambda node, ctx: False,
    )

    result = resolution.resolve_database_node(
        node,
        children=[],
        ctx=_visibility_context(),
    )

    assert result is None


@pytest.mark.django_db
def test_resolve_database_empty_section_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sections without visible descendants should be removed."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    node = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
    )

    monkeypatch.setattr(
        resolution,
        "database_node_is_visible",
        lambda node, ctx: True,
    )

    assert (
        resolution.resolve_database_node(
            node,
            children=[],
            ctx=_visibility_context(),
        )
        is None
    )


@pytest.mark.django_db
def test_resolve_database_link_uses_effective_values() -> None:
    """ORM resolution should expose canonical effective model values."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        short_title="Rpt",
        description="Reports description.",
        tooltip="Reports tooltip.",
        aria_label="Reports ARIA",
        cta_label="Open",
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
        target=NavigationLink.Target.BLANK,
        icon_type=NavigationLink.IconType.EMOJI,
        emoji="📊",
        metadata={
            "from_link": True,
        },
        audience=NavigationLink.Audience.PUBLIC,
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        code="reports-placement",
        title_override="Reports Override",
        metadata={
            "from_node": True,
        },
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    request = RequestFactory().get(
        "/other/",
    )
    request.user = AnonymousUser()

    result = resolution.resolve_database_node(
        node,
        children=[],
        ctx=_visibility_context(
            request=request,
        ),
    )

    assert result is not None

    assert result.node_id == node.pk
    assert result.link_id == link.pk
    assert result.kind == LaunchpadNode.Kind.LINK

    assert result.code == "reports-placement"
    assert result.link_code == "reports"

    assert result.title == "Reports Override"
    assert result.short_title == "Reports Override"
    assert result.description == "Reports description."
    assert result.tooltip == "Reports tooltip."
    assert result.aria_label == "Reports ARIA"
    assert result.cta_label == "Open"

    assert result.url == "/reports/"
    assert result.target == NavigationLink.Target.BLANK
    assert result.rel == "noopener noreferrer"
    assert result.download is False

    assert result.icon == {
        "kind": "emoji",
        "value": "📊",
    }

    assert result.enabled is True
    assert result.disabled_reason == ""
    assert result.is_active is False

    assert result.metadata == {
        "from_link": True,
        "from_node": True,
    }

    assert result.source_node is node
    assert result.source_link is link


@pytest.mark.django_db
def test_resolve_database_disabled_link_uses_hash_url() -> None:
    """Disabled ORM links should remain visible but non-navigable."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        enabled=False,
        disabled_reason="Coming soon.",
        audience=NavigationLink.Audience.PUBLIC,
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    result = resolution.resolve_database_node(
        node,
        children=[],
        ctx=_visibility_context(),
    )

    assert result is not None
    assert result.enabled is False
    assert result.url == "#"
    assert result.disabled_reason == "Coming soon."


@pytest.mark.django_db
def test_resolve_database_parent_inherits_active_child() -> None:
    """Resolved parent active state should include descendant activity."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    section = create_section_node(
        launchpad=launchpad,
        code="section",
        title_override="Section",
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    result = resolution.resolve_database_node(
        section,
        children=[
            _resolved_child(
                active=True,
            ),
        ],
        ctx=_visibility_context(),
    )

    assert result is not None
    assert result.is_active is True


def test_resolve_cached_node_returns_none_when_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hidden cached nodes should not resolve."""
    node = _cached_node(
        navigation_link=_cached_link(),
    )

    monkeypatch.setattr(
        resolution,
        "cached_node_is_visible",
        lambda node, ctx: False,
    )

    assert (
        resolution.resolve_cached_node(
            node,
            children=[],
            ctx=_visibility_context(),
        )
        is None
    )


def test_resolve_cached_empty_section_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached empty sections should be removed."""
    node = _cached_node(
        kind=LaunchpadNode.Kind.SECTION,
        navigation_link=None,
    )

    monkeypatch.setattr(
        resolution,
        "cached_node_is_visible",
        lambda node, ctx: True,
    )

    assert (
        resolution.resolve_cached_node(
            node,
            children=[],
            ctx=_visibility_context(),
        )
        is None
    )


def test_resolve_cached_link_matches_effective_model_behavior() -> None:
    """Cached resolution should reuse the canonical model behavior."""
    node = _cached_node(
        code="reports-placement",
        title_override="Reports Override",
        metadata={
            "from_node": True,
        },
        navigation_link=_cached_link(
            code="reports",
            title="Reports",
            description="Reports description.",
            tooltip="Reports tooltip.",
            aria_label="Reports ARIA",
            cta_label="Open",
            url_type=NavigationLink.URLType.RAW,
            url_value="/reports/",
            target=NavigationLink.Target.BLANK,
            icon_type=NavigationLink.IconType.EMOJI,
            emoji="📊",
            metadata={
                "from_link": True,
            },
        ),
    )

    request = RequestFactory().get(
        "/other/",
    )
    request.user = AnonymousUser()

    result = resolution.resolve_cached_node(
        node,
        children=[],
        ctx=_visibility_context(
            request=request,
        ),
    )

    assert result is not None

    assert result.node_id == node.pk
    assert node.navigation_link is not None
    assert result.link_id == node.navigation_link.pk
    assert result.code == "reports-placement"
    assert result.link_code == "reports"

    assert result.title == "Reports Override"
    assert result.description == "Reports description."
    assert result.tooltip == "Reports tooltip."
    assert result.aria_label == "Reports ARIA"
    assert result.cta_label == "Open"

    assert result.url == "/reports/"
    assert result.target == NavigationLink.Target.BLANK
    assert result.rel == "noopener noreferrer"

    assert result.icon == {
        "kind": "emoji",
        "value": "📊",
    }

    assert result.metadata == {
        "from_link": True,
        "from_node": True,
    }

    assert result.source_node is None
    assert result.source_link is None


def test_resolve_cached_disabled_link_uses_hash_url() -> None:
    """Disabled cached destinations should remain non-navigable."""
    node = _cached_node(
        navigation_link=_cached_link(
            enabled=False,
            disabled_reason="Coming soon.",
        ),
    )

    result = resolution.resolve_cached_node(
        node,
        children=[],
        ctx=_visibility_context(),
    )

    assert result is not None
    assert result.enabled is False
    assert result.url == "#"
    assert result.disabled_reason == "Coming soon."


def test_resolve_cached_parent_inherits_active_child() -> None:
    """Cached parents should inherit active state from descendants."""
    node = _cached_node(
        kind=LaunchpadNode.Kind.SECTION,
        title_override="Section",
        navigation_link=None,
    )

    result = resolution.resolve_cached_node(
        node,
        children=[
            _resolved_child(
                active=True,
            ),
        ],
        ctx=_visibility_context(),
    )

    assert result is not None
    assert result.is_active is True


def test_resolution_module_exports_expected_symbols() -> None:
    """Resolution should expose only its intentional internal API."""
    assert resolution.__all__ == [
        "cached_node_is_visible",
        "cached_object_is_visible",
        "database_node_is_visible",
        "metadata_for_cached_node",
        "metadata_for_database_node",
        "resolve_cached_node",
        "resolve_database_node",
    ]


def test_database_link_node_without_link_is_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed ORM link nodes without a destination should fail closed."""
    node = LaunchpadNode(
        pk=20,
        kind=LaunchpadNode.Kind.LINK,
        navigation_link=None,
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    monkeypatch.setattr(
        resolution,
        "is_visible",
        lambda obj, *, ctx: True,
    )

    assert (
        resolution.database_node_is_visible(
            node,
            _visibility_context(),
        )
        is False
    )
