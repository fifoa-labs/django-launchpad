"""
tests/models/test_navigation_link_helpers.py

Tests for NavigationLink URL, context-resolution, and validation helpers.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from launchpad.models import navigation_link


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("@user.username", True),
        ("ordinary-value", False),
        (["@context.person.pk"], True),
        (["ordinary-value", 42], False),
        ({"person": "@context.person.pk"}, True),
        ({"person": 42}, False),
        (42, False),
        (None, False),
    ],
)
def test_contains_context_reference(
    value: Any,
    expected: bool,  # noqa: FBT001
) -> None:
    """Context-reference detection should recurse through JSON-like values."""
    assert navigation_link._contains_context_reference(value) is expected  # noqa: SLF001


def test_resolve_attr_chain_reads_object_attributes() -> None:
    """Attribute chains should traverse ordinary Python objects."""
    value = SimpleNamespace(
        profile=SimpleNamespace(
            username="huy",
        ),
    )

    assert (
        navigation_link._resolve_attr_chain(  # noqa: SLF001
            value,
            ["profile", "username"],
        )
        == "huy"
    )


def test_resolve_attr_chain_reads_dictionary_keys() -> None:
    """Attribute chains should traverse dictionary keys."""
    value = {
        "person": {
            "pk": 42,
        },
    }

    assert (
        navigation_link._resolve_attr_chain(  # noqa: SLF001
            value,
            ["person", "pk"],
        )
        == 42
    )


def test_resolve_attr_chain_returns_empty_string_for_missing_value() -> None:
    """Missing attributes and keys should fail closed to an empty string."""
    value: dict[str, Any] = {
        "person": {},
    }

    assert (
        navigation_link._resolve_attr_chain(  # noqa: SLF001
            value,
            ["person", "missing"],
        )
        == ""
    )


def test_resolve_attr_chain_returns_empty_string_after_none() -> None:
    """A None value encountered in a chain should stop resolution safely."""
    value = {
        "person": None,
    }

    assert (
        navigation_link._resolve_attr_chain(  # noqa: SLF001
            value,
            ["person", "pk"],
        )
        == ""
    )


def test_resolve_attr_chain_does_not_invoke_callables() -> None:
    """Callable attributes should be returned without being invoked."""

    def callback() -> str:
        return "called"

    value = SimpleNamespace(callback=callback)

    assert (
        navigation_link._resolve_attr_chain(  # noqa: SLF001
            value,
            ["callback"],
        )
        is callback
    )


def test_resolve_context_reference_reads_request_user() -> None:
    """User references should resolve from request.user."""
    request = SimpleNamespace(
        user=SimpleNamespace(username="huy"),
    )

    assert (
        navigation_link._resolve_context_reference(  # noqa: SLF001
            "@user.username",
            request=request,
        )
        == "huy"
    )


def test_resolve_context_reference_reads_request() -> None:
    """Request references should resolve from the request object."""
    request = SimpleNamespace(
        resolver_match=SimpleNamespace(
            view_name="ancestry:index",
        ),
    )

    assert (
        navigation_link._resolve_context_reference(  # noqa: SLF001
            "@request.resolver_match.view_name",
            request=request,
        )
        == "ancestry:index"
    )


def test_resolve_context_reference_reads_template_context() -> None:
    """Context references should resolve from the supplied context mapping."""
    context = {
        "person": SimpleNamespace(pk=42),
    }

    assert (
        navigation_link._resolve_context_reference(  # noqa: SLF001
            "@context.person.pk",
            context=context,
        )
        == 42
    )


def test_resolve_context_reference_handles_missing_request_user() -> None:
    """User references without a request should fail closed."""
    assert (
        navigation_link._resolve_context_reference(  # noqa: SLF001
            "@user.username",
            request=None,
        )
        == ""
    )


def test_resolve_context_reference_handles_missing_context() -> None:
    """Context references without context data should fail closed."""
    assert (
        navigation_link._resolve_context_reference(  # noqa: SLF001
            "@context.person.pk",
            context=None,
        )
        == ""
    )


def test_resolve_context_reference_rejects_unknown_root() -> None:
    """Unknown context-reference roots should fail closed."""
    assert (
        navigation_link._resolve_context_reference(  # noqa: SLF001
            "@session.account_id",
        )
        == ""
    )


def test_resolve_json_value_resolves_nested_structures() -> None:
    """JSON-like containers should resolve references recursively."""
    request = SimpleNamespace(
        user=SimpleNamespace(username="huy"),
    )
    context = {
        "person": SimpleNamespace(pk=42),
    }

    value = {
        "username": "@user.username",
        "filters": [
            "@context.person.pk",
            "active",
            7,
        ],
        "nested": {
            "view": "@request.resolver_match.view_name",
        },
    }

    request.resolver_match = SimpleNamespace(
        view_name="ancestry:index",
    )

    assert navigation_link._resolve_json_value(  # noqa: SLF001
        value,
        request=request,
        context=context,
    ) == {
        "username": "huy",
        "filters": [
            42,
            "active",
            7,
        ],
        "nested": {
            "view": "ancestry:index",
        },
    }


@pytest.mark.parametrize(
    "value",
    [
        "ordinary-value",
        42,
        1.5,
        True,
        None,
    ],
)
def test_resolve_json_value_preserves_non_reference_scalars(
    value: Any,
) -> None:
    """Ordinary scalar values should remain unchanged."""
    assert navigation_link._resolve_json_value(value) == value  # noqa: SLF001


def test_append_query_and_fragment_preserves_existing_values() -> None:
    """New query parameters should append to existing query parameters."""
    result = navigation_link._append_query_and_fragment(  # noqa: SLF001
        "/reports/?existing=1#old-fragment",
        query_params={
            "tab": "monthly",
        },
        fragment="summary",
    )

    assert result == "/reports/?existing=1&tab=monthly#summary"


def test_append_query_and_fragment_preserves_existing_fragment() -> None:
    """An existing fragment should remain when no replacement is supplied."""
    result = navigation_link._append_query_and_fragment(  # noqa: SLF001
        "/reports/#summary",
        query_params={},
    )

    assert result == "/reports/#summary"


def test_append_query_and_fragment_omits_none_values() -> None:
    """None query values should not be encoded."""
    result = navigation_link._append_query_and_fragment(  # noqa: SLF001
        "/reports/",
        query_params={
            "tab": None,
            "year": 2026,
        },
    )

    assert result == "/reports/?year=2026"


def test_append_query_and_fragment_expands_lists_and_omits_none_items() -> None:
    """List parameters should repeat keys while omitting None items."""
    result = navigation_link._append_query_and_fragment(  # noqa: SLF001
        "/reports/",
        query_params={
            "tag": [
                "a",
                None,
                "b",
            ],
        },
    )

    assert result == "/reports/?tag=a&tag=b"


@pytest.mark.parametrize(
    "url",
    [
        "/relative/path/",
        "https://example.com/docs/",
        "http://example.com/docs/",
        "mailto:hello@example.com",
        "tel:+15551234567",
    ],
)
def test_validate_raw_url_accepts_supported_urls(url: str) -> None:
    """Supported relative and absolute URLs should pass validation."""
    navigation_link.validate_raw_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "#",
        " /surrounding-space/",
        "/surrounding-space/ ",
        "javascript:alert(1)",
        "data:text/html,bad",
        "vbscript:alert(1)",
        "//example.com/path",
        "ftp://example.com/file",
    ],
)
def test_validate_raw_url_rejects_unsafe_values(url: str) -> None:
    """Unsafe or unsupported raw URLs should fail validation."""
    with pytest.raises(ValidationError):
        navigation_link.validate_raw_url(url)
