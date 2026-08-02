"""
src/launchpad/visibility.py

Visibility engine for Launchpad objects.

Visibility determines whether a NavigationLink or LaunchpadNode should be
shown to a user.

Important doctrine:

- Launchpad visibility is UI visibility only.
- Destination views must still enforce their own authorization.
- Superusers bypass access-policy rules, but inactive objects remain hidden.
- Permissions act as a gate when configured.
- Runtime visibility rules are registered by safe code, not Python import path.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, cast

from django.contrib.auth.models import AnonymousUser

from launchpad.models.base import (
    AccessPolicyModel,
    validate_code,
)

logger = logging.getLogger(__name__)


VisibilityRule = Callable[..., bool]

_VISIBILITY_RULES: dict[str, VisibilityRule] = {}


@dataclass(frozen=True, slots=True)
class VisibilityContext:
    """
    Resolved visibility context for a single render/read operation.

    Readers should build this once and reuse it across all nodes to avoid
    repeated user/group/permission work.
    """

    user: Any | None
    user_id: Any | None
    is_authenticated: bool
    is_staff: bool
    is_superuser: bool
    group_ids: frozenset[Any]
    permissions: frozenset[str]
    request: Any | None
    extra_context: dict[str, Any]


def register_visibility_rule(
    code: str,
) -> Callable[[VisibilityRule], VisibilityRule]:
    """
    Register a runtime visibility rule.

    Example:

        @register_visibility_rule("has_ancestry_data")
        def has_ancestry_data(*, obj, user, request, context) -> bool:
            return Person.objects.exists()

    The database stores only the safe ``code`` value.
    """

    validate_code(code)

    def decorator(func: VisibilityRule) -> VisibilityRule:
        _VISIBILITY_RULES[code] = func
        return func

    return decorator


def get_visibility_rule(code: str) -> VisibilityRule | None:
    """
    Return a registered visibility rule by code.
    """
    return _VISIBILITY_RULES.get(code)


def _truthy_attr(obj: Any, name: str) -> bool:
    """
    Return a boolean attribute value, supporting callable Django-era attrs.
    """
    value = getattr(obj, name, False)

    if callable(value):
        value = value()

    return bool(value)


def _is_authenticated_user(user: Any | None) -> bool:
    """
    Return True if user is authenticated.
    """
    if user is None:
        return False

    if isinstance(user, AnonymousUser):
        return False

    return _truthy_attr(user, "is_authenticated")


def _resolve_user(
    *,
    user: Any | None = None,
    request: Any | None = None,
) -> Any | None:
    """
    Return explicit user or request.user if available.
    """
    if user is not None:
        return user

    if request is not None:
        return getattr(request, "user", None)

    return None


def build_user_context(
    user: Any | None = None,
    *,
    request: Any | None = None,
    context: dict[str, Any] | None = None,
) -> VisibilityContext:
    """
    Build a reusable visibility context.
    """
    resolved_user = _resolve_user(
        user=user,
        request=request,
    )

    is_authenticated = resolved_user is not None and _is_authenticated_user(
        resolved_user
    )

    user_id = getattr(resolved_user, "pk", None)

    is_staff = bool(is_authenticated and getattr(resolved_user, "is_staff", False))

    is_superuser = bool(
        is_authenticated and getattr(resolved_user, "is_superuser", False)
    )

    group_ids: frozenset[Any] = frozenset()
    permissions: frozenset[str] = frozenset()

    if is_authenticated and resolved_user is not None:
        groups_manager = getattr(resolved_user, "groups", None)

        if groups_manager is not None:
            try:
                group_ids = frozenset(
                    groups_manager.values_list(
                        "pk",
                        flat=True,
                    ),
                )
            except Exception:  # pragma: no cover - defensive for custom users.
                logger.exception(
                    "Unable to resolve user groups for Launchpad visibility.",
                )

        get_all_permissions = getattr(
            resolved_user,
            "get_all_permissions",
            None,
        )

        if callable(get_all_permissions):
            permission_getter = cast(
                "Callable[[], Iterable[str]]",
                get_all_permissions,
            )

            try:
                permissions = frozenset(
                    permission_getter(),
                )
            except Exception:  # pragma: no cover - defensive for custom users.
                logger.exception(
                    "Unable to resolve user permissions for Launchpad visibility.",
                )

    return VisibilityContext(
        user=resolved_user,
        user_id=user_id,
        is_authenticated=is_authenticated,
        is_staff=is_staff,
        is_superuser=is_superuser,
        group_ids=group_ids,
        permissions=permissions,
        request=request,
        extra_context=dict(context or {}),
    )


def _is_active(obj: Any) -> bool:
    """
    Return True if object is active.

    Objects without an ``active`` attribute are treated as active.
    """
    return bool(getattr(obj, "active", True))


def _is_available_now(obj: Any) -> bool:
    """
    Return True if object is within its visibility window.
    """
    checker = getattr(obj, "is_available_now", None)

    if callable(checker):
        return bool(checker())

    return True


def _audience_passes(
    obj: Any,
    ctx: VisibilityContext,
) -> bool:
    """
    Return True if the base audience allows this user.
    """
    audience = getattr(
        obj,
        "audience",
        AccessPolicyModel.Audience.AUTHENTICATED,
    )

    if audience == AccessPolicyModel.Audience.PUBLIC:
        return True

    if audience == AccessPolicyModel.Audience.AUTHENTICATED:
        return ctx.is_authenticated

    if audience == AccessPolicyModel.Audience.STAFF:
        return ctx.is_staff

    if audience == AccessPolicyModel.Audience.SUPERUSER:
        return ctx.is_superuser

    if audience == AccessPolicyModel.Audience.PRIVATE:
        return False

    return False


def _explicit_user_passes(
    obj: Any,
    ctx: VisibilityContext,
) -> bool:
    """
    Return True if the user is explicitly assigned to the object.
    """
    if not ctx.is_authenticated or ctx.user_id is None:
        return False

    if not getattr(obj, "pk", None):
        return False

    users = getattr(obj, "users", None)

    if users is None:
        return False

    try:
        return any(assigned_user.pk == ctx.user_id for assigned_user in users.all())
    except Exception:  # pragma: no cover - defensive for unsaved/mocked objs.
        logger.exception(
            "Unable to resolve explicit Launchpad users.",
        )
        return False


def _group_passes(
    obj: Any,
    ctx: VisibilityContext,
) -> bool:
    """
    Return True if the user belongs to one of the object's assigned groups.
    """
    if not ctx.is_authenticated or not ctx.group_ids:
        return False

    if not getattr(obj, "pk", None):
        return False

    groups = getattr(obj, "groups", None)

    if groups is None:
        return False

    try:
        return any(group.pk in ctx.group_ids for group in groups.all())
    except Exception:  # pragma: no cover - defensive for unsaved/mocked objs.
        logger.exception(
            "Unable to resolve Launchpad groups.",
        )
        return False


def _permissions_pass(
    obj: Any,
    ctx: VisibilityContext,
) -> bool:
    """
    Return True if configured permissions pass.

    Empty permissions mean no permission gate.
    """
    permissions_required = list(
        getattr(obj, "permissions_required", []) or [],
    )

    if not permissions_required:
        return True

    if not ctx.is_authenticated:
        return False

    if ctx.is_superuser:
        return True

    permissions_mode = getattr(
        obj,
        "permissions_mode",
        AccessPolicyModel.PermissionMode.ALL,
    )

    if permissions_mode == AccessPolicyModel.PermissionMode.ANY:
        return any(permission in ctx.permissions for permission in permissions_required)

    return all(permission in ctx.permissions for permission in permissions_required)


def _permission_itself_grants_visibility(
    obj: Any,
    ctx: VisibilityContext,
) -> bool:
    """
    Return True if permission configuration itself grants visibility.

    This allows permission-only navigation:

        audience = private
        permissions_required = ["ancestry.view_person"]

    while still making permissions a gate for explicit users/groups.
    """
    permissions_required = list(
        getattr(obj, "permissions_required", []) or [],
    )

    if not permissions_required:
        return False

    return _permissions_pass(
        obj,
        ctx,
    )


def _runtime_rule_passes(
    obj: Any,
    ctx: VisibilityContext,
) -> bool:
    """
    Return True if the optional runtime visibility rule passes.
    """
    rule_code = getattr(obj, "visibility_rule", "") or ""

    if not rule_code:
        return True

    rule = get_visibility_rule(rule_code)

    if rule is None:
        logger.warning(
            "Launchpad visibility rule '%s' is not registered.",
            rule_code,
        )
        return False

    try:
        return bool(
            rule(
                obj=obj,
                user=ctx.user,
                request=ctx.request,
                context=ctx.extra_context,
            ),
        )
    except Exception:
        logger.exception(
            "Launchpad visibility rule '%s' failed.",
            rule_code,
        )
        return False


def is_visible(
    obj: Any,
    *,
    user: Any | None = None,
    request: Any | None = None,
    context: dict[str, Any] | None = None,
    ctx: VisibilityContext | None = None,
) -> bool:
    """
    Return whether ``obj`` should be visible.

    Supported objects are expected to use AccessPolicyModel, but this function
    intentionally works defensively with any object exposing compatible fields.
    """
    resolved_ctx = ctx or build_user_context(
        user=user,
        request=request,
        context=context,
    )

    if not _is_active(obj):
        return False

    if not _is_available_now(obj):
        return False

    # Superusers bypass access policy, but not inactive/scheduled-off state.
    if resolved_ctx.is_superuser:
        return True

    permissions_pass = _permissions_pass(
        obj,
        resolved_ctx,
    )

    if not permissions_pass:
        return False

    visible_by_policy = any(
        (
            _audience_passes(obj, resolved_ctx),
            _explicit_user_passes(obj, resolved_ctx),
            _group_passes(obj, resolved_ctx),
            _permission_itself_grants_visibility(obj, resolved_ctx),
        ),
    )

    if not visible_by_policy:
        return False

    return _runtime_rule_passes(
        obj,
        resolved_ctx,
    )


__all__ = [
    "VisibilityContext",
    "build_user_context",
    "get_visibility_rule",
    "is_visible",
    "register_visibility_rule",
]
