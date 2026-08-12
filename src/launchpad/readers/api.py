"""
src/launchpad/readers/api.py

Public reader orchestration for django-launchpad.

This module provides the stable ``get_launchpad`` entry point while delegating
database/cache loading, request-sensitive resolution, and tree construction to
smaller internal reader modules.
"""

from __future__ import annotations

from typing import Any

from .context import build_visibility_context
from .loader import (
    DatabaseLaunchpadConfiguration,
    load_configuration,
)
from .models import ResolvedLaunchpad
from .snapshots import CachedLaunchpadConfiguration
from .tree import (
    resolve_cached_tree,
    resolve_database_tree,
)


def _empty_launchpad(
    code: str,
) -> ResolvedLaunchpad:
    """Return a missing/inactive Launchpad result."""
    return ResolvedLaunchpad(
        code=code,
        title=code,
        description="",
        metadata={},
        exists=False,
        nodes=[],
        source_launchpad=None,
    )


def _resolve_database_configuration(
    configuration: DatabaseLaunchpadConfiguration,
    *,
    user: Any | None,
    request: Any | None,
    context: dict[str, Any] | None,
) -> ResolvedLaunchpad:
    """Resolve one live ORM Launchpad configuration."""
    visibility_context = build_visibility_context(
        user=user,
        request=request,
        context=context,
    )

    nodes = resolve_database_tree(
        configuration.nodes,
        ctx=visibility_context,
    )

    launchpad = configuration.launchpad

    return ResolvedLaunchpad(
        code=launchpad.code,
        title=launchpad.title,
        description=launchpad.description,
        metadata=dict(
            launchpad.metadata or {},
        ),
        exists=True,
        nodes=nodes,
        source_launchpad=launchpad,
    )


def _resolve_cached_configuration(
    configuration: CachedLaunchpadConfiguration,
    *,
    user: Any | None,
    request: Any | None,
    context: dict[str, Any] | None,
) -> ResolvedLaunchpad:
    """Resolve one cached Launchpad configuration."""
    visibility_context = build_visibility_context(
        user=user,
        request=request,
        context=context,
    )

    nodes = resolve_cached_tree(
        configuration.nodes,
        ctx=visibility_context,
    )

    return ResolvedLaunchpad(
        code=configuration.code,
        title=configuration.title,
        description=configuration.description,
        metadata=dict(
            configuration.metadata,
        ),
        exists=True,
        nodes=nodes,
        source_launchpad=None,
    )


def get_launchpad(
    code: str,
    *,
    user: Any | None = None,
    request: Any | None = None,
    context: dict[str, Any] | None = None,
) -> ResolvedLaunchpad:
    """
    Return a renderer-neutral Launchpad tree.

    Stable Launchpad configuration may be loaded through Django's persistent
    cache when package caching is enabled.

    User-, request-, time-, and context-sensitive behavior remains live for
    every call, including:

    - visibility evaluation,
    - scheduled visibility,
    - runtime visibility rules,
    - context-aware URL resolution,
    - query-parameter resolution,
    - active-state calculation,
    - and ancestor active-state propagation.

    Missing or inactive Launchpads fail safely and return an empty result.

    Args:
        code:
            Stable Launchpad code.

        user:
            Optional explicit user. When omitted, the visibility layer may use
            ``request.user`` when a request is available.

        request:
            Optional Django request used for user visibility, URL context,
            query parameters, view-name matching, and active-state resolution.

        context:
            Optional runtime context mapping available to context-aware
            Launchpad values and registered visibility rules.

    Returns:
        A renderer-neutral ``ResolvedLaunchpad``.
    """
    normalized_code = str(code).strip()

    configuration = load_configuration(
        normalized_code,
    )

    if configuration is None:
        return _empty_launchpad(
            normalized_code,
        )

    if isinstance(
        configuration,
        DatabaseLaunchpadConfiguration,
    ):
        return _resolve_database_configuration(
            configuration,
            user=user,
            request=request,
            context=context,
        )

    if isinstance(
        configuration,
        CachedLaunchpadConfiguration,
    ):
        return _resolve_cached_configuration(
            configuration,
            user=user,
            request=request,
            context=context,
        )

    msg = (
        "Launchpad reader loader returned an unsupported "
        f"configuration type: {type(configuration)!r}."
    )
    raise TypeError(msg)


__all__ = [
    "get_launchpad",
]
