"""
tests/test_visibility.py

Tests for the Launchpad visibility engine.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth.models import AnonymousUser, Permission
from django.utils import timezone

from launchpad.models import NavigationLink
from launchpad.visibility import (
    build_user_context,
    is_visible,
    register_visibility_rule,
)
from tests.builders import (
    create_group,
    create_navigation_link,
    create_superuser,
    create_user,
)

pytestmark = pytest.mark.django_db


def _permission_string(permission: Permission) -> str:
    """Return a Django ``app_label.codename`` permission string."""
    return f"{permission.content_type.app_label}.{permission.codename}"


def _view_group_permission() -> Permission:
    """Return a stable built-in permission for visibility tests."""
    return Permission.objects.get(
        content_type__app_label="auth",
        codename="view_group",
    )


def _add_group_permission() -> Permission:
    """Return another stable built-in permission for permission-mode tests."""
    return Permission.objects.get(
        content_type__app_label="auth",
        codename="add_group",
    )


def test_build_user_context_for_anonymous_user() -> None:
    """Anonymous users should produce an empty unauthenticated context."""
    ctx = build_user_context(AnonymousUser())

    assert ctx.is_authenticated is False
    assert ctx.is_staff is False
    assert ctx.is_superuser is False
    assert ctx.group_ids == frozenset()
    assert ctx.permissions == frozenset()


def test_build_user_context_for_authenticated_user() -> None:
    """Authenticated user context should include identity and group data."""
    group = create_group()
    user = create_user()
    user.groups.add(group)

    ctx = build_user_context(user)

    assert ctx.user == user
    assert ctx.user_id == user.pk
    assert ctx.is_authenticated is True
    assert group.pk in ctx.group_ids


def test_public_link_visible_to_anonymous_user() -> None:
    """Public links should be visible to anonymous users."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.PUBLIC,
    )

    assert (
        is_visible(
            link,
            user=AnonymousUser(),
        )
        is True
    )


def test_authenticated_link_hidden_from_anonymous_user() -> None:
    """Authenticated links should be hidden from anonymous users."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.AUTHENTICATED,
    )

    assert (
        is_visible(
            link,
            user=AnonymousUser(),
        )
        is False
    )


def test_authenticated_link_visible_to_authenticated_user() -> None:
    """Authenticated links should be visible to authenticated users."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.AUTHENTICATED,
    )

    assert (
        is_visible(
            link,
            user=create_user(),
        )
        is True
    )


def test_staff_link_hidden_from_non_staff_user() -> None:
    """Staff links should be hidden from ordinary users."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.STAFF,
    )

    assert (
        is_visible(
            link,
            user=create_user(is_staff=False),
        )
        is False
    )


def test_staff_link_visible_to_staff_user() -> None:
    """Staff links should be visible to staff users."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.STAFF,
    )

    assert (
        is_visible(
            link,
            user=create_user(is_staff=True),
        )
        is True
    )


def test_superuser_link_visible_to_superuser() -> None:
    """Superuser links should be visible to superusers."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.SUPERUSER,
    )

    assert (
        is_visible(
            link,
            user=create_superuser(),
        )
        is True
    )


def test_private_link_hidden_by_default() -> None:
    """Private links should be hidden without another visibility grant."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.PRIVATE,
    )

    assert (
        is_visible(
            link,
            user=create_user(),
        )
        is False
    )


def test_private_link_visible_to_explicit_user() -> None:
    """Explicit user assignment should grant visibility to private links."""
    user = create_user()

    link = create_navigation_link(
        audience=NavigationLink.Audience.PRIVATE,
        users=[user],
    )

    assert (
        is_visible(
            link,
            user=user,
        )
        is True
    )


def test_private_link_visible_to_group_member() -> None:
    """Assigned group membership should grant private-link visibility."""
    group = create_group()
    user = create_user()
    user.groups.add(group)

    link = create_navigation_link(
        audience=NavigationLink.Audience.PRIVATE,
        groups=[group],
    )

    assert (
        is_visible(
            link,
            user=user,
        )
        is True
    )


def test_permission_required_blocks_user_without_permission() -> None:
    """Configured permissions should act as a visibility gate."""
    permission = _view_group_permission()

    link = create_navigation_link(
        audience=NavigationLink.Audience.PUBLIC,
        permissions_required=[
            _permission_string(permission),
        ],
    )

    assert (
        is_visible(
            link,
            user=create_user(),
        )
        is False
    )


def test_permission_required_allows_user_with_permission() -> None:
    """Users with required permissions should pass the permission gate."""
    permission = _view_group_permission()
    user = create_user()
    user.user_permissions.add(permission)

    link = create_navigation_link(
        audience=NavigationLink.Audience.AUTHENTICATED,
        permissions_required=[
            _permission_string(permission),
        ],
    )

    assert (
        is_visible(
            link,
            user=user,
        )
        is True
    )


def test_private_link_visible_by_permission_only() -> None:
    """Permissions alone may grant visibility to private links."""
    permission = _view_group_permission()
    user = create_user()
    user.user_permissions.add(permission)

    link = create_navigation_link(
        audience=NavigationLink.Audience.PRIVATE,
        permissions_required=[
            _permission_string(permission),
        ],
    )

    assert (
        is_visible(
            link,
            user=user,
        )
        is True
    )


def test_permission_gate_still_blocks_explicit_user() -> None:
    """Explicit assignment should not bypass a configured permission gate."""
    permission = _view_group_permission()
    user = create_user()

    link = create_navigation_link(
        audience=NavigationLink.Audience.PRIVATE,
        users=[user],
        permissions_required=[
            _permission_string(permission),
        ],
    )

    assert (
        is_visible(
            link,
            user=user,
        )
        is False
    )


def test_permissions_mode_all_requires_all_permissions() -> None:
    """ALL mode should require every configured permission."""
    first_permission = _view_group_permission()
    second_permission = _add_group_permission()

    user = create_user()
    user.user_permissions.add(first_permission)

    link = create_navigation_link(
        audience=NavigationLink.Audience.AUTHENTICATED,
        permissions_mode=NavigationLink.PermissionMode.ALL,
        permissions_required=[
            _permission_string(first_permission),
            _permission_string(second_permission),
        ],
    )

    assert (
        is_visible(
            link,
            user=user,
        )
        is False
    )


def test_permissions_mode_any_requires_one_permission() -> None:
    """ANY mode should pass when one configured permission is present."""
    first_permission = _view_group_permission()
    second_permission = _add_group_permission()

    user = create_user()
    user.user_permissions.add(first_permission)

    link = create_navigation_link(
        audience=NavigationLink.Audience.AUTHENTICATED,
        permissions_mode=NavigationLink.PermissionMode.ANY,
        permissions_required=[
            _permission_string(first_permission),
            _permission_string(second_permission),
        ],
    )

    assert (
        is_visible(
            link,
            user=user,
        )
        is True
    )


def test_inactive_object_is_hidden_even_from_superuser() -> None:
    """Inactive objects should remain hidden from superusers."""
    link = create_navigation_link(
        active=False,
        audience=NavigationLink.Audience.PUBLIC,
    )

    assert (
        is_visible(
            link,
            user=create_superuser(),
        )
        is False
    )


def test_object_before_visible_from_is_hidden() -> None:
    """Objects should remain hidden before their visibility window."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.PUBLIC,
        visible_from=timezone.now() + timedelta(days=1),
    )

    assert (
        is_visible(
            link,
            user=create_user(),
        )
        is False
    )


def test_object_after_visible_until_is_hidden() -> None:
    """Objects should be hidden after their visibility window."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.PUBLIC,
        visible_until=timezone.now() - timedelta(days=1),
    )

    assert (
        is_visible(
            link,
            user=create_user(),
        )
        is False
    )


def test_superuser_bypasses_private_policy() -> None:
    """Superusers should bypass access-policy restrictions."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.PRIVATE,
        permissions_required=[
            "auth.view_group",
        ],
    )

    assert (
        is_visible(
            link,
            user=create_superuser(),
        )
        is True
    )


def test_runtime_visibility_rule_can_allow_object() -> None:
    """A registered runtime rule may allow an object."""

    @register_visibility_rule("allow_test_rule")
    def allow_test_rule(**_kwargs: Any) -> bool:
        return True

    link = create_navigation_link(
        audience=NavigationLink.Audience.PUBLIC,
        visibility_rule="allow_test_rule",
    )

    assert (
        is_visible(
            link,
            user=AnonymousUser(),
        )
        is True
    )


def test_runtime_visibility_rule_can_hide_object() -> None:
    """A registered runtime rule may hide an object."""

    @register_visibility_rule("deny_test_rule")
    def deny_test_rule(**_kwargs: Any) -> bool:
        return False

    link = create_navigation_link(
        audience=NavigationLink.Audience.PUBLIC,
        visibility_rule="deny_test_rule",
    )

    assert (
        is_visible(
            link,
            user=AnonymousUser(),
        )
        is False
    )


def test_unregistered_runtime_visibility_rule_hides_object() -> None:
    """Unknown runtime rules should fail closed."""
    link = create_navigation_link(
        audience=NavigationLink.Audience.PUBLIC,
        visibility_rule="missing_test_rule",
    )

    assert (
        is_visible(
            link,
            user=AnonymousUser(),
        )
        is False
    )
