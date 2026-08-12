"""
tests/readers/test_api.py

Tests for the public django-launchpad reader API.
"""

from __future__ import annotations

from typing import Any

import pytest

from launchpad.models import Launchpad
from launchpad.readers import (
    ResolvedLaunchpad,
    ResolvedNode,
    api,
    get_launchpad,
    models as reader_models,
)
from launchpad.readers.loader import DatabaseLaunchpadConfiguration
from launchpad.readers.snapshots import CachedLaunchpadConfiguration


def test_public_reader_api_exports_expected_symbols() -> None:
    """The reader package should expose only its intentional public API."""
    from launchpad import readers  # noqa: PLC0415

    assert readers.__all__ == [
        "ResolvedLaunchpad",
        "ResolvedNode",
        "get_launchpad",
    ]


def test_get_launchpad_is_exported_from_reader_package() -> None:
    """The package-level get_launchpad export should be the API function."""
    assert get_launchpad is api.get_launchpad


def test_resolved_launchpad_is_exported_from_reader_package() -> None:
    """ResolvedLaunchpad should remain available from launchpad.readers."""
    assert ResolvedLaunchpad is reader_models.ResolvedLaunchpad


def test_resolved_node_is_exported_from_reader_package() -> None:
    """ResolvedNode should remain available from launchpad.readers."""
    assert ResolvedNode is reader_models.ResolvedNode


def test_get_launchpad_normalizes_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public API should strip surrounding whitespace from codes."""
    received_codes: list[str] = []

    def load_configuration(
        code: str,
    ) -> None:
        received_codes.append(code)

    monkeypatch.setattr(
        api,
        "load_configuration",
        load_configuration,
    )

    result = get_launchpad(
        "  primary_navigation  ",
    )

    assert received_codes == [
        "primary_navigation",
    ]

    assert result.code == "primary_navigation"


def test_get_launchpad_returns_empty_result_when_configuration_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing Launchpads should fail safely rather than raise."""
    monkeypatch.setattr(
        api,
        "load_configuration",
        lambda code: None,
    )

    result = get_launchpad(
        "missing",
    )

    assert result == ResolvedLaunchpad(
        code="missing",
        title="missing",
        description="",
        metadata={},
        exists=False,
        nodes=[],
        source_launchpad=None,
    )

    assert result.exists is False
    assert result.is_empty is True


def test_get_launchpad_handles_empty_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty normalized code should produce an empty result safely."""
    received_codes: list[str] = []

    def load_configuration(
        code: str,
    ) -> None:
        received_codes.append(code)

    monkeypatch.setattr(
        api,
        "load_configuration",
        load_configuration,
    )

    result = get_launchpad(
        "   ",
    )

    assert received_codes == [
        "",
    ]

    assert result.code == ""
    assert result.title == ""
    assert result.exists is False
    assert result.is_empty is True


def test_get_launchpad_resolves_database_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live ORM configurations should use the database-resolution path."""
    launchpad = Launchpad(
        pk=42,
        code="primary_navigation",
        title="Primary Navigation",
        description="Primary application navigation.",
        metadata={
            "location": "sidebar",
        },
        active=True,
    )

    configuration = DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    monkeypatch.setattr(
        api,
        "load_configuration",
        lambda code: configuration,
    )

    resolved_nodes: list[ResolvedNode] = []

    def resolve_database_tree(
        nodes: list[Any],
        *,
        ctx: Any,
    ) -> list[ResolvedNode]:
        assert nodes == []
        assert ctx is not None
        return resolved_nodes

    monkeypatch.setattr(
        api,
        "resolve_database_tree",
        resolve_database_tree,
    )

    result = get_launchpad(
        "primary_navigation",
    )

    assert result.code == "primary_navigation"
    assert result.title == "Primary Navigation"
    assert result.description == "Primary application navigation."
    assert result.metadata == {
        "location": "sidebar",
    }
    assert result.exists is True
    assert result.nodes is resolved_nodes

    assert result.source_launchpad is launchpad


def test_database_resolution_receives_runtime_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Database resolution should receive user, request, and runtime context."""
    launchpad = Launchpad(
        pk=42,
        code="primary_navigation",
        title="Primary Navigation",
        active=True,
    )

    configuration = DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    monkeypatch.setattr(
        api,
        "load_configuration",
        lambda code: configuration,
    )

    user = object()
    request = object()
    context = {
        "workspace_id": 123,
    }

    received: dict[str, Any] = {}

    def build_visibility_context(
        *,
        user: Any,
        request: Any,
        context: dict[str, Any] | None,
    ) -> Any:
        received["user"] = user
        received["request"] = request
        received["context"] = context
        return object()

    monkeypatch.setattr(
        api,
        "build_visibility_context",
        build_visibility_context,
    )

    monkeypatch.setattr(
        api,
        "resolve_database_tree",
        lambda nodes, *, ctx: [],
    )

    get_launchpad(
        "primary_navigation",
        user=user,
        request=request,
        context=context,
    )

    assert received == {
        "user": user,
        "request": request,
        "context": context,
    }


def test_get_launchpad_resolves_cached_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached configuration should use the cached-resolution path."""
    configuration = CachedLaunchpadConfiguration(
        pk=42,
        code="home",
        title="Home",
        description="Homepage navigation.",
        metadata={
            "renderer": "cards",
        },
        nodes=(),
    )

    monkeypatch.setattr(
        api,
        "load_configuration",
        lambda code: configuration,
    )

    resolved_nodes: list[ResolvedNode] = []

    def resolve_cached_tree(
        nodes: tuple[Any, ...],
        *,
        ctx: Any,
    ) -> list[ResolvedNode]:
        assert nodes == ()
        assert ctx is not None
        return resolved_nodes

    monkeypatch.setattr(
        api,
        "resolve_cached_tree",
        resolve_cached_tree,
    )

    result = get_launchpad(
        "home",
    )

    assert result.code == "home"
    assert result.title == "Home"
    assert result.description == "Homepage navigation."
    assert result.metadata == {
        "renderer": "cards",
    }
    assert result.exists is True
    assert result.nodes is resolved_nodes

    assert result.source_launchpad is None


def test_cached_resolution_receives_runtime_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached resolution should still build a live visibility context."""
    configuration = CachedLaunchpadConfiguration(
        pk=42,
        code="home",
        title="Home",
        description="",
        metadata={},
        nodes=(),
    )

    monkeypatch.setattr(
        api,
        "load_configuration",
        lambda code: configuration,
    )

    user = object()
    request = object()
    context = {
        "person_id": 456,
    }

    received: dict[str, Any] = {}

    visibility_context = object()

    def build_visibility_context(
        *,
        user: Any,
        request: Any,
        context: dict[str, Any] | None,
    ) -> Any:
        received["user"] = user
        received["request"] = request
        received["context"] = context
        return visibility_context

    def resolve_cached_tree(
        nodes: tuple[Any, ...],
        *,
        ctx: Any,
    ) -> list[ResolvedNode]:
        assert ctx is visibility_context
        return []

    monkeypatch.setattr(
        api,
        "build_visibility_context",
        build_visibility_context,
    )

    monkeypatch.setattr(
        api,
        "resolve_cached_tree",
        resolve_cached_tree,
    )

    get_launchpad(
        "home",
        user=user,
        request=request,
        context=context,
    )

    assert received == {
        "user": user,
        "request": request,
        "context": context,
    }


def test_database_metadata_is_copied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolved database metadata should not alias the model dictionary."""
    metadata = {
        "location": "sidebar",
    }

    launchpad = Launchpad(
        pk=42,
        code="navigation",
        title="Navigation",
        metadata=metadata,
        active=True,
    )

    configuration = DatabaseLaunchpadConfiguration(
        launchpad=launchpad,
        nodes=[],
    )

    monkeypatch.setattr(
        api,
        "load_configuration",
        lambda code: configuration,
    )

    monkeypatch.setattr(
        api,
        "resolve_database_tree",
        lambda nodes, *, ctx: [],
    )

    result = get_launchpad(
        "navigation",
    )

    assert result.metadata == metadata
    assert result.metadata is not metadata


def test_cached_metadata_is_copied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolved cached metadata should not alias the cached snapshot mapping."""
    metadata = {
        "renderer": "cards",
    }

    configuration = CachedLaunchpadConfiguration(
        pk=42,
        code="home",
        title="Home",
        description="",
        metadata=metadata,
        nodes=(),
    )

    monkeypatch.setattr(
        api,
        "load_configuration",
        lambda code: configuration,
    )

    monkeypatch.setattr(
        api,
        "resolve_cached_tree",
        lambda nodes, *, ctx: [],
    )

    result = get_launchpad(
        "home",
    )

    assert result.metadata == metadata
    assert result.metadata is not metadata


def test_get_launchpad_rejects_unsupported_loader_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected loader return types should fail loudly."""
    unexpected = object()

    monkeypatch.setattr(
        api,
        "load_configuration",
        lambda code: unexpected,
    )

    with pytest.raises(
        TypeError,
        match="Launchpad reader loader returned an unsupported configuration type",
    ):
        get_launchpad(
            "home",
        )
