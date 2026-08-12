"""
tests/readers/test_context.py

Tests for request-scoped Launchpad visibility-context reuse.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from launchpad.readers import context as reader_context
from launchpad.visibility import VisibilityContext


def _visibility_context(
    *,
    user: Any = None,
    request: Any = None,
    extra_context: dict[str, Any] | None = None,
) -> VisibilityContext:
    """Return a minimal VisibilityContext for reader-context tests."""
    return VisibilityContext(
        user=user,
        request=request,
        extra_context=dict(extra_context or {}),
        is_authenticated=False,
        is_staff=False,
        is_superuser=False,
        user_id=None,
        group_ids=frozenset(),
        permissions=frozenset(),
    )


def test_build_visibility_context_without_request_delegates_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reads without a request should use normal context construction."""
    user = object()
    runtime_context = {
        "person_id": 42,
    }

    expected = _visibility_context(
        user=user,
        extra_context=runtime_context,
    )

    received: dict[str, Any] = {}

    def build_user_context(
        *,
        user: Any,
        request: Any,
        context: dict[str, Any] | None,
    ) -> VisibilityContext:
        received["user"] = user
        received["request"] = request
        received["context"] = context
        return expected

    monkeypatch.setattr(
        reader_context,
        "build_user_context",
        build_user_context,
    )

    result = reader_context.build_visibility_context(
        user=user,
        request=None,
        context=runtime_context,
    )

    assert result is expected

    assert received == {
        "user": user,
        "request": None,
        "context": runtime_context,
    }


def test_build_visibility_context_creates_request_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first request-scoped read should initialize the context cache."""
    user = object()
    request = SimpleNamespace()

    base_context = _visibility_context(
        user=user,
        request=request,
    )

    calls = 0

    def build_user_context(
        *,
        user: Any,
        request: Any,
        context: dict[str, Any] | None,
    ) -> VisibilityContext:
        nonlocal calls
        calls += 1

        assert context is None

        return base_context

    monkeypatch.setattr(
        reader_context,
        "build_user_context",
        build_user_context,
    )

    result = reader_context.build_visibility_context(
        user=user,
        request=request,
        context={
            "workspace_id": 7,
        },
    )

    assert calls == 1

    assert result is not base_context
    assert result.extra_context == {
        "workspace_id": 7,
    }

    stored = request._django_launchpad_visibility_contexts  # noqa: SLF001

    assert isinstance(stored, dict)
    assert stored[id(user)] is base_context


def test_build_visibility_context_reuses_base_context_for_same_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Multiple Launchpad reads in one request should reuse user identity work.

    This is the optimization that prevents repeated user group and permission
    queries when several Launchpads are rendered during one request.
    """
    user = object()
    request = SimpleNamespace()

    base_context = _visibility_context(
        user=user,
        request=request,
    )

    calls = 0

    def build_user_context(
        *,
        user: Any,
        request: Any,
        context: dict[str, Any] | None,
    ) -> VisibilityContext:
        nonlocal calls
        calls += 1

        assert context is None

        return base_context

    monkeypatch.setattr(
        reader_context,
        "build_user_context",
        build_user_context,
    )

    first = reader_context.build_visibility_context(
        user=user,
        request=request,
        context={
            "launchpad": "primary_navigation",
        },
    )

    second = reader_context.build_visibility_context(
        user=user,
        request=request,
        context={
            "launchpad": "home",
        },
    )

    assert calls == 1

    assert first.extra_context == {
        "launchpad": "primary_navigation",
    }

    assert second.extra_context == {
        "launchpad": "home",
    }


def test_reused_contexts_do_not_share_extra_context() -> None:
    """Runtime context dictionaries should remain isolated between reads."""
    user = object()
    request = SimpleNamespace()

    base_context = _visibility_context(
        user=user,
        request=request,
    )

    request._django_launchpad_visibility_contexts = {id(user): base_context}  # noqa: SLF001

    first_source = {
        "value": 1,
    }

    first = reader_context.build_visibility_context(
        user=user,
        request=request,
        context=first_source,
    )

    second = reader_context.build_visibility_context(
        user=user,
        request=request,
        context={
            "value": 2,
        },
    )

    assert first.extra_context == {
        "value": 1,
    }

    assert second.extra_context == {
        "value": 2,
    }

    assert first.extra_context is not second.extra_context
    assert first.extra_context is not first_source


def test_build_visibility_context_uses_request_user_when_explicit_user_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """request.user should determine the request-cache key when user is omitted."""
    request_user = object()

    request = SimpleNamespace(
        user=request_user,
    )

    base_context = _visibility_context(
        user=request_user,
        request=request,
    )

    received: dict[str, Any] = {}

    def build_user_context(
        *,
        user: Any,
        request: Any,
        context: dict[str, Any] | None,
    ) -> VisibilityContext:
        received["user"] = user
        received["request"] = request
        received["context"] = context
        return base_context

    monkeypatch.setattr(
        reader_context,
        "build_user_context",
        build_user_context,
    )

    reader_context.build_visibility_context(
        user=None,
        request=request,
        context=None,
    )

    stored = request._django_launchpad_visibility_contexts  # noqa: SLF001

    assert stored[id(request_user)] is base_context

    assert received == {
        "user": None,
        "request": request,
        "context": None,
    }


def test_explicit_user_takes_precedence_over_request_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicitly supplied user should own the request-cache entry."""
    request_user = object()
    explicit_user = object()

    request = SimpleNamespace(
        user=request_user,
    )

    base_context = _visibility_context(
        user=explicit_user,
        request=request,
    )

    monkeypatch.setattr(
        reader_context,
        "build_user_context",
        lambda *, user, request, context: base_context,
    )

    reader_context.build_visibility_context(
        user=explicit_user,
        request=request,
        context=None,
    )

    stored = request._django_launchpad_visibility_contexts  # noqa: SLF001

    assert id(explicit_user) in stored
    assert id(request_user) not in stored


def test_different_users_receive_separate_request_cache_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Request-scoped memoization should not share contexts between users."""
    first_user = object()
    second_user = object()

    request = SimpleNamespace()

    calls: list[Any] = []

    def build_user_context(
        *,
        user: Any,
        request: Any,
        context: dict[str, Any] | None,
    ) -> VisibilityContext:
        calls.append(user)

        return _visibility_context(
            user=user,
            request=request,
        )

    monkeypatch.setattr(
        reader_context,
        "build_user_context",
        build_user_context,
    )

    reader_context.build_visibility_context(
        user=first_user,
        request=request,
        context=None,
    )

    reader_context.build_visibility_context(
        user=second_user,
        request=request,
        context=None,
    )

    reader_context.build_visibility_context(
        user=first_user,
        request=request,
        context=None,
    )

    assert calls == [
        first_user,
        second_user,
    ]

    stored = request._django_launchpad_visibility_contexts  # noqa: SLF001

    assert set(stored) == {
        id(first_user),
        id(second_user),
    }


@pytest.mark.parametrize(
    "existing_value",
    [
        None,
        "invalid",
        42,
        [],
        (),
        object(),
    ],
)
def test_invalid_existing_request_cache_is_replaced(
    existing_value: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected request attribute values should be replaced safely."""
    user = object()

    request = SimpleNamespace()

    request._django_launchpad_visibility_contexts = existing_value  # noqa: SLF001

    base_context = _visibility_context(
        user=user,
        request=request,
    )

    monkeypatch.setattr(
        reader_context,
        "build_user_context",
        lambda *, user, request, context: base_context,
    )

    reader_context.build_visibility_context(
        user=user,
        request=request,
        context=None,
    )

    stored = request._django_launchpad_visibility_contexts  # noqa: SLF001

    assert isinstance(stored, dict)
    assert stored == {
        id(user): base_context,
    }


def test_existing_request_cache_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing context-cache dictionary should be reused in place."""
    existing_user = object()
    new_user = object()

    request = SimpleNamespace()

    existing_context = _visibility_context(
        user=existing_user,
        request=request,
    )

    existing_cache = {
        id(existing_user): existing_context,
    }

    request._django_launchpad_visibility_contexts = existing_cache  # noqa: SLF001

    new_context = _visibility_context(
        user=new_user,
        request=request,
    )

    monkeypatch.setattr(
        reader_context,
        "build_user_context",
        lambda *, user, request, context: new_context,
    )

    reader_context.build_visibility_context(
        user=new_user,
        request=request,
        context=None,
    )

    stored = request._django_launchpad_visibility_contexts  # noqa: SLF001

    assert stored is existing_cache

    assert stored == {
        id(existing_user): existing_context,
        id(new_user): new_context,
    }


def test_none_runtime_context_becomes_empty_mapping() -> None:
    """A reused base context should receive an empty mapping when context is None."""
    user = object()
    request = SimpleNamespace()

    base_context = _visibility_context(
        user=user,
        request=request,
        extra_context={
            "old": "value",
        },
    )

    request._django_launchpad_visibility_contexts = {id(user): base_context}  # noqa: SLF001

    result = reader_context.build_visibility_context(
        user=user,
        request=request,
        context=None,
    )

    assert result.extra_context == {}


def test_base_visibility_context_is_not_mutated() -> None:
    """Per-read context replacement should leave the cached base object unchanged."""
    user = object()
    request = SimpleNamespace()

    base_context = _visibility_context(
        user=user,
        request=request,
        extra_context={},
    )

    request._django_launchpad_visibility_contexts = {id(user): base_context}  # noqa: SLF001

    result = reader_context.build_visibility_context(
        user=user,
        request=request,
        context={
            "person": 42,
        },
    )

    assert result is not base_context

    assert base_context.extra_context == {}

    assert result.extra_context == {
        "person": 42,
    }


def test_reused_context_preserves_base_visibility_data() -> None:
    """Replacing extra_context should preserve all user-derived visibility data."""
    user = object()
    request = SimpleNamespace()

    base_context = replace(
        _visibility_context(
            user=user,
            request=request,
        ),
        is_authenticated=True,
        is_staff=True,
        is_superuser=False,
        user_id=42,
        group_ids=frozenset(
            {
                1,
                2,
            },
        ),
        permissions=frozenset(
            {
                "reports.view_report",
            },
        ),
    )

    request._django_launchpad_visibility_contexts = {id(user): base_context}  # noqa: SLF001

    result = reader_context.build_visibility_context(
        user=user,
        request=request,
        context={
            "workspace": "atlas",
        },
    )

    assert result.user is user
    assert result.request is request

    assert result.is_authenticated is True
    assert result.is_staff is True
    assert result.is_superuser is False
    assert result.user_id == 42

    assert result.group_ids == frozenset(
        {
            1,
            2,
        },
    )

    assert result.permissions == frozenset(
        {
            "reports.view_report",
        },
    )

    assert result.extra_context == {
        "workspace": "atlas",
    }


def test_context_module_exports_expected_public_helper() -> None:
    """The context module should expose only its intentional helper."""
    assert reader_context.__all__ == [
        "build_visibility_context",
    ]
