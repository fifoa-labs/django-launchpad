"""
src/launchpad/readers/context.py

Request-scoped visibility-context helpers for django-launchpad readers.

Resolving multiple Launchpads during one request should not repeatedly query
the same user's groups and permissions.

This module memoizes the expensive user-derived portion of VisibilityContext
on the request object while still providing a fresh runtime ``extra_context``
mapping for each Launchpad read.

This is request-local memoization only. It is separate from Launchpad's
persistent configuration cache.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from launchpad.visibility import (
    VisibilityContext,
    build_user_context,
)

_REQUEST_VISIBILITY_CONTEXT_ATTR = "_django_launchpad_visibility_contexts"


def build_visibility_context(
    *,
    user: Any | None,
    request: Any | None,
    context: dict[str, Any] | None,
) -> VisibilityContext:
    """
    Build a VisibilityContext with request-scoped user-data reuse.

    Group membership and permission resolution depend on the user, not on the
    Launchpad code or the template/runtime context supplied to one read.

    When several Launchpads are resolved during one HTTP request, the base
    user context is therefore cached on the request and reused.

    A fresh ``extra_context`` mapping is attached to every returned context so
    one Launchpad read cannot leak runtime values into another.

    When no request exists, normal visibility-context construction is used.
    """
    if request is None:
        return build_user_context(
            user=user,
            request=None,
            context=context,
        )

    resolved_user = (
        user
        if user is not None
        else getattr(
            request,
            "user",
            None,
        )
    )

    raw_cache = getattr(
        request,
        _REQUEST_VISIBILITY_CONTEXT_ATTR,
        None,
    )

    if isinstance(raw_cache, dict):
        context_cache = cast(
            "dict[int, VisibilityContext]",
            raw_cache,
        )
    else:
        context_cache = {}
        setattr(
            request,
            _REQUEST_VISIBILITY_CONTEXT_ATTR,
            context_cache,
        )

    cache_key = id(resolved_user)

    base_context = context_cache.get(
        cache_key,
    )

    if base_context is None:
        base_context = build_user_context(
            user=user,
            request=request,
            context=None,
        )

        context_cache[cache_key] = base_context

    return replace(
        base_context,
        extra_context=dict(
            context or {},
        ),
    )


__all__ = [
    "build_visibility_context",
]
