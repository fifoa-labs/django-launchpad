"""
tests/test_visibility_helpers.py

Tests for internal helpers used by the Launchpad visibility engine.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth.models import AnonymousUser

from launchpad import visibility
from launchpad.models.base import AccessPolicyModel
from launchpad.visibility import VisibilityContext

if TYPE_CHECKING:
    from collections.abc import Iterable


def _context(  # noqa: PLR0913
    *,
    user: Any | None = None,
    user_id: Any | None = None,
    is_authenticated: bool = False,
    is_staff: bool = False,
    is_superuser: bool = False,
    group_ids: frozenset[Any] = frozenset(),
    permissions: frozenset[str] = frozenset(),
    request: Any | None = None,
    extra_context: dict[str, Any] | None = None,
) -> VisibilityContext:
    """Build a visibility context with explicit test values."""
    return VisibilityContext(
        user=user,
        user_id=user_id,
        is_authenticated=is_authenticated,
        is_staff=is_staff,
        is_superuser=is_superuser,
        group_ids=group_ids,
        permissions=permissions,
        request=request,
        extra_context=extra_context or {},
    )


def test_get_visibility_rule_returns_registered_rule() -> None:
    """Registered visibility rules should be retrievable by code."""

    @visibility.register_visibility_rule("helper_registered_rule")
    def helper_registered_rule(**_kwargs: Any) -> bool:
        return True

    assert (
        visibility.get_visibility_rule("helper_registered_rule")
        is helper_registered_rule
    )


def test_get_visibility_rule_returns_none_for_unknown_code() -> None:
    """Unknown visibility-rule codes should return None."""
    assert visibility.get_visibility_rule("unknown_helper_rule") is None


def test_truthy_attr_reads_boolean_attribute() -> None:
    """Ordinary boolean attributes should be converted to bool."""
    obj = SimpleNamespace(enabled=1)

    assert visibility._truthy_attr(obj, "enabled") is True  # noqa: SLF001


def test_truthy_attr_invokes_callable_attribute() -> None:
    """Callable compatibility attributes should be invoked."""
    obj = SimpleNamespace(
        is_authenticated=lambda: True,
    )

    assert visibility._truthy_attr(obj, "is_authenticated") is True  # noqa: SLF001


def test_truthy_attr_returns_false_for_missing_attribute() -> None:
    """Missing attributes should default to false."""
    assert visibility._truthy_attr(object(), "missing") is False  # noqa: SLF001


def test_is_authenticated_user_rejects_none() -> None:
    """A missing user should not be authenticated."""
    assert visibility._is_authenticated_user(None) is False  # noqa: SLF001


def test_is_authenticated_user_rejects_anonymous_user() -> None:
    """Django AnonymousUser instances should not be authenticated."""
    assert visibility._is_authenticated_user(AnonymousUser()) is False  # noqa: SLF001


def test_is_authenticated_user_supports_callable_attribute() -> None:
    """Callable authentication attributes should remain supported."""
    user = SimpleNamespace(
        is_authenticated=lambda: True,
    )

    assert visibility._is_authenticated_user(user) is True  # noqa: SLF001


def test_resolve_user_prefers_explicit_user() -> None:
    """An explicit user should take precedence over request.user."""
    explicit_user = object()
    request_user = object()
    request = SimpleNamespace(user=request_user)

    assert (
        visibility._resolve_user(  # noqa: SLF001
            user=explicit_user,
            request=request,
        )
        is explicit_user
    )


def test_resolve_user_uses_request_user() -> None:
    """request.user should be used when no explicit user is supplied."""
    request_user = object()
    request = SimpleNamespace(user=request_user)

    assert visibility._resolve_user(request=request) is request_user  # noqa: SLF001


def test_resolve_user_handles_request_without_user() -> None:
    """Requests without a user attribute should resolve safely."""
    assert visibility._resolve_user(request=object()) is None  # noqa: SLF001


def test_resolve_user_returns_none_without_inputs() -> None:
    """Missing user and request values should resolve to None."""
    assert visibility._resolve_user() is None  # noqa: SLF001


def test_build_user_context_uses_request_user() -> None:
    """Context construction should resolve users from requests."""

    class User:
        pk = 42
        is_authenticated = True
        is_staff = True
        is_superuser = False

    user = User()
    request = SimpleNamespace(user=user)

    ctx = visibility.build_user_context(
        request=request,
        context={"section": "reports"},
    )

    assert ctx.user is user
    assert ctx.user_id == 42
    assert ctx.is_authenticated is True
    assert ctx.is_staff is True
    assert ctx.is_superuser is False
    assert ctx.request is request
    assert ctx.extra_context == {
        "section": "reports",
    }


def test_build_user_context_handles_user_without_groups() -> None:
    """Custom users without a groups manager should remain supported."""

    class User:
        pk = 42
        is_authenticated = True
        is_staff = False
        is_superuser = False

    ctx = visibility.build_user_context(User())

    assert ctx.group_ids == frozenset()
    assert ctx.permissions == frozenset()


def test_build_user_context_ignores_non_callable_permission_attribute() -> None:
    """Non-callable permission attributes should not be invoked."""

    class User:
        pk = 42
        is_authenticated = True
        is_staff = False
        is_superuser = False
        groups = None
        get_all_permissions = {"auth.view_group"}

    ctx = visibility.build_user_context(User())

    assert ctx.permissions == frozenset()


def test_build_user_context_collects_custom_permissions() -> None:
    """Callable permission getters should populate the context."""

    class User:
        pk = 42
        is_authenticated = True
        is_staff = False
        is_superuser = False
        groups = None

        def get_all_permissions(self) -> Iterable[str]:
            return [
                "auth.view_group",
                "auth.add_group",
            ]

    ctx = visibility.build_user_context(User())

    assert ctx.permissions == frozenset(
        {
            "auth.view_group",
            "auth.add_group",
        },
    )


def test_is_active_defaults_to_true() -> None:
    """Objects without active state should be treated as active."""
    assert visibility._is_active(object()) is True  # noqa: SLF001


def test_is_active_reads_object_state() -> None:
    """Explicit inactive state should be respected."""
    assert visibility._is_active(SimpleNamespace(active=False)) is False  # noqa: SLF001


def test_is_available_now_invokes_checker() -> None:
    """Availability helpers should invoke compatible checker methods."""
    obj = SimpleNamespace(
        is_available_now=lambda: False,
    )

    assert visibility._is_available_now(obj) is False  # noqa: SLF001


def test_is_available_now_defaults_to_true() -> None:
    """Objects without availability helpers should remain available."""
    assert visibility._is_available_now(object()) is True  # noqa: SLF001


@pytest.mark.parametrize(
    ("audience", "ctx", "expected"),
    [
        (
            AccessPolicyModel.Audience.PUBLIC,
            _context(),
            True,
        ),
        (
            AccessPolicyModel.Audience.AUTHENTICATED,
            _context(is_authenticated=True),
            True,
        ),
        (
            AccessPolicyModel.Audience.AUTHENTICATED,
            _context(is_authenticated=False),
            False,
        ),
        (
            AccessPolicyModel.Audience.STAFF,
            _context(is_staff=True),
            True,
        ),
        (
            AccessPolicyModel.Audience.STAFF,
            _context(is_staff=False),
            False,
        ),
        (
            AccessPolicyModel.Audience.SUPERUSER,
            _context(is_superuser=True),
            True,
        ),
        (
            AccessPolicyModel.Audience.SUPERUSER,
            _context(is_superuser=False),
            False,
        ),
        (
            AccessPolicyModel.Audience.PRIVATE,
            _context(is_authenticated=True),
            False,
        ),
        (
            "unknown",
            _context(is_authenticated=True),
            False,
        ),
    ],
)
def test_audience_passes(
    audience: str,
    ctx: VisibilityContext,
    expected: bool,  # noqa: FBT001
) -> None:
    """Audience checks should implement every supported policy."""
    obj = SimpleNamespace(audience=audience)

    assert visibility._audience_passes(obj, ctx) is expected  # noqa: SLF001


def test_audience_passes_defaults_to_authenticated() -> None:
    """Objects without audience values should default to authenticated."""
    assert (
        visibility._audience_passes(  # noqa: SLF001
            object(),
            _context(is_authenticated=True),
        )
        is True
    )


def test_explicit_user_rejects_unauthenticated_context() -> None:
    """Explicit-user matching should require authentication."""
    assert (
        visibility._explicit_user_passes(  # noqa: SLF001
            object(),
            _context(),
        )
        is False
    )


def test_explicit_user_rejects_missing_user_id() -> None:
    """Explicit-user matching should require a resolved user ID."""
    assert (
        visibility._explicit_user_passes(  # noqa: SLF001
            object(),
            _context(is_authenticated=True),
        )
        is False
    )


def test_explicit_user_rejects_unsaved_object() -> None:
    """Unsaved objects should not attempt many-to-many user access."""
    obj = SimpleNamespace(
        pk=None,
        users=object(),
    )

    assert (
        visibility._explicit_user_passes(  # noqa: SLF001
            obj,
            _context(
                user_id=1,
                is_authenticated=True,
            ),
        )
        is False
    )


def test_explicit_user_rejects_object_without_users_relation() -> None:
    """Objects without a users relation should fail safely."""
    obj = SimpleNamespace(pk=1)

    assert (
        visibility._explicit_user_passes(  # noqa: SLF001
            obj,
            _context(
                user_id=1,
                is_authenticated=True,
            ),
        )
        is False
    )


def test_explicit_user_matches_assigned_user() -> None:
    """Assigned users should pass explicit-user matching."""
    assigned_user = SimpleNamespace(pk=1)
    manager = SimpleNamespace(
        all=lambda: [assigned_user],
    )
    obj = SimpleNamespace(
        pk=10,
        users=manager,
    )

    assert (
        visibility._explicit_user_passes(  # noqa: SLF001
            obj,
            _context(
                user_id=1,
                is_authenticated=True,
            ),
        )
        is True
    )


def test_explicit_user_rejects_unassigned_user() -> None:
    """Unassigned users should fail explicit-user matching."""
    assigned_user = SimpleNamespace(pk=2)
    manager = SimpleNamespace(
        all=lambda: [assigned_user],
    )
    obj = SimpleNamespace(
        pk=10,
        users=manager,
    )

    assert (
        visibility._explicit_user_passes(  # noqa: SLF001
            obj,
            _context(
                user_id=1,
                is_authenticated=True,
            ),
        )
        is False
    )


def test_group_rejects_context_without_groups() -> None:
    """Group matching should require authenticated group membership."""
    assert (
        visibility._group_passes(  # noqa: SLF001
            object(),
            _context(
                user_id=1,
                is_authenticated=True,
            ),
        )
        is False
    )


def test_group_rejects_unsaved_object() -> None:
    """Unsaved objects should not attempt group-relation access."""
    obj = SimpleNamespace(
        pk=None,
        groups=object(),
    )

    assert (
        visibility._group_passes(  # noqa: SLF001
            obj,
            _context(
                user_id=1,
                is_authenticated=True,
                group_ids=frozenset({1}),
            ),
        )
        is False
    )


def test_group_rejects_object_without_groups_relation() -> None:
    """Objects without a groups relation should fail safely."""
    obj = SimpleNamespace(pk=1)

    assert (
        visibility._group_passes(  # noqa: SLF001
            obj,
            _context(
                user_id=1,
                is_authenticated=True,
                group_ids=frozenset({1}),
            ),
        )
        is False
    )


def test_group_matches_assigned_group() -> None:
    """Assigned groups should pass group matching."""
    assigned_group = SimpleNamespace(pk=1)
    manager = SimpleNamespace(
        all=lambda: [assigned_group],
    )
    obj = SimpleNamespace(
        pk=10,
        groups=manager,
    )

    assert (
        visibility._group_passes(  # noqa: SLF001
            obj,
            _context(
                user_id=2,
                is_authenticated=True,
                group_ids=frozenset({1}),
            ),
        )
        is True
    )


def test_group_rejects_unassigned_group() -> None:
    """Unassigned groups should fail group matching."""
    assigned_group = SimpleNamespace(pk=2)
    manager = SimpleNamespace(
        all=lambda: [assigned_group],
    )
    obj = SimpleNamespace(
        pk=10,
        groups=manager,
    )

    assert (
        visibility._group_passes(  # noqa: SLF001
            obj,
            _context(
                user_id=2,
                is_authenticated=True,
                group_ids=frozenset({1}),
            ),
        )
        is False
    )


def test_permissions_passes_without_requirements() -> None:
    """Empty permission requirements should not create a gate."""
    assert visibility._permissions_pass(object(), _context()) is True  # noqa: SLF001


def test_permissions_reject_unauthenticated_context() -> None:
    """Configured permissions should require authentication."""
    obj = SimpleNamespace(
        permissions_required=["auth.view_group"],
    )

    assert visibility._permissions_pass(obj, _context()) is False  # noqa: SLF001


def test_permissions_allow_superuser() -> None:
    """Superusers should pass configured permission requirements."""
    obj = SimpleNamespace(
        permissions_required=["auth.view_group"],
    )

    assert (
        visibility._permissions_pass(  # noqa: SLF001
            obj,
            _context(
                is_authenticated=True,
                is_superuser=True,
            ),
        )
        is True
    )


def test_permissions_any_accepts_one_match() -> None:
    """ANY mode should accept one matching permission."""
    obj = SimpleNamespace(
        permissions_required=[
            "auth.view_group",
            "auth.add_group",
        ],
        permissions_mode=AccessPolicyModel.PermissionMode.ANY,
    )

    assert (
        visibility._permissions_pass(  # noqa: SLF001
            obj,
            _context(
                is_authenticated=True,
                permissions=frozenset({"auth.view_group"}),
            ),
        )
        is True
    )


def test_permissions_all_rejects_partial_match() -> None:
    """ALL mode should reject incomplete permission sets."""
    obj = SimpleNamespace(
        permissions_required=[
            "auth.view_group",
            "auth.add_group",
        ],
        permissions_mode=AccessPolicyModel.PermissionMode.ALL,
    )

    assert (
        visibility._permissions_pass(  # noqa: SLF001
            obj,
            _context(
                is_authenticated=True,
                permissions=frozenset({"auth.view_group"}),
            ),
        )
        is False
    )


def test_permission_itself_does_not_grant_without_requirements() -> None:
    """Missing permission configuration should not grant visibility."""
    assert (
        visibility._permission_itself_grants_visibility(  # noqa: SLF001
            object(),
            _context(),
        )
        is False
    )


def test_permission_itself_grants_when_gate_passes() -> None:
    """A passing permission gate may independently grant visibility."""
    obj = SimpleNamespace(
        permissions_required=["auth.view_group"],
    )

    assert (
        visibility._permission_itself_grants_visibility(  # noqa: SLF001
            obj,
            _context(
                is_authenticated=True,
                permissions=frozenset({"auth.view_group"}),
            ),
        )
        is True
    )


def test_runtime_rule_passes_without_rule() -> None:
    """Objects without runtime rules should pass."""
    assert visibility._runtime_rule_passes(object(), _context()) is True  # noqa: SLF001


def test_runtime_rule_rejects_unknown_rule() -> None:
    """Unknown runtime rules should fail closed."""
    obj = SimpleNamespace(
        visibility_rule="unknown_helper_runtime_rule",
    )

    assert visibility._runtime_rule_passes(obj, _context()) is False  # noqa: SLF001


def test_runtime_rule_receives_visibility_context() -> None:
    """Runtime rules should receive the object and resolved context."""
    received: dict[str, Any] = {}

    @visibility.register_visibility_rule("helper_context_rule")
    def helper_context_rule(**kwargs: Any) -> bool:
        received.update(kwargs)
        return True

    obj = SimpleNamespace(
        visibility_rule="helper_context_rule",
    )
    user = object()
    request = object()
    extra_context = {
        "section": "reports",
    }
    ctx = _context(
        user=user,
        request=request,
        extra_context=extra_context,
    )

    assert visibility._runtime_rule_passes(obj, ctx) is True  # noqa: SLF001
    assert received == {
        "obj": obj,
        "user": user,
        "request": request,
        "context": extra_context,
    }


def test_runtime_rule_exception_fails_closed() -> None:
    """Exceptions raised by runtime rules should fail closed."""

    @visibility.register_visibility_rule("helper_raising_rule")
    def helper_raising_rule(**_kwargs: Any) -> bool:
        msg = "visibility failure"
        raise RuntimeError(msg)

    obj = SimpleNamespace(
        visibility_rule="helper_raising_rule",
    )

    assert visibility._runtime_rule_passes(obj, _context()) is False  # noqa: SLF001
