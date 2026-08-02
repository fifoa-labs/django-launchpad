"""
tests/models/test_base.py

Tests for shared Launchpad model helpers and access-policy behavior.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from launchpad.models.base import (
    validate_code,
    validate_json_args,
    validate_json_mapping,
    validate_string_list,
)
from tests.builders import create_navigation_link

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "code",
    [
        "primary_navigation",
        "homepage",
        "account-menu",
        "ancestry_actions",
        "beancount_reports_2026",
    ],
)
def test_validate_code_accepts_valid_codes(code: str) -> None:
    """Valid stable codes should pass validation."""
    validate_code(code)


@pytest.mark.parametrize(
    "code",
    [
        "",
        "PrimaryNavigation",
        "primary navigation",
        "primary.navigation",
        "primary/navigation",
        "_primary",
        "1primary",
    ],
)
def test_validate_code_rejects_invalid_codes(code: str) -> None:
    """Invalid stable codes should raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_code(code)


def test_validate_string_list_accepts_list_of_strings() -> None:
    """Lists containing only strings should pass validation."""
    validate_string_list(
        [
            "ancestry.view_person",
            "beancount.view_account",
        ],
    )


@pytest.mark.parametrize(
    "value",
    [
        "not-a-list",
        {"permission": "ancestry.view_person"},
        [1, 2, 3],
        ["ancestry.view_person", 1],
    ],
)
def test_validate_string_list_rejects_invalid_values(value: Any) -> None:
    """Non-lists and lists containing non-strings should be rejected."""
    with pytest.raises(ValidationError):
        validate_string_list(value)


def test_validate_json_args_accepts_scalar_list() -> None:
    """URL arguments may contain supported JSON scalar values."""
    validate_json_args(
        [
            "abc",
            123,
            1.5,
            True,
            None,
            "@user.username",
        ],
    )


@pytest.mark.parametrize(
    "value",
    [
        "not-a-list",
        {"pk": 1},
        [{"bad": "object"}],
        [["nested"]],
    ],
)
def test_validate_json_args_rejects_invalid_values(value: Any) -> None:
    """URL arguments should reject containers other than the outer list."""
    with pytest.raises(ValidationError):
        validate_json_args(value)


def test_validate_json_mapping_accepts_scalars_and_scalar_lists() -> None:
    """JSON mappings may contain scalars and lists of scalar values."""
    validate_json_mapping(
        {
            "tab": "monthly",
            "page": 1,
            "show": True,
            "empty": None,
            "tags": ["a", "b", 3],
        },
    )


@pytest.mark.parametrize(
    "value",
    [
        "not-a-dict",
        ["not", "a", "dict"],
        {1: "bad-key"},
        {"bad": {"nested": "object"}},
        {"bad": [{"nested": "object"}]},
    ],
)
def test_validate_json_mapping_rejects_invalid_values(value: Any) -> None:
    """Invalid mapping shapes and nested objects should be rejected."""
    with pytest.raises(ValidationError):
        validate_json_mapping(value)


def test_access_policy_rejects_invalid_visibility_window() -> None:
    """Visible-until must not precede visible-from."""
    now = timezone.now()

    link = create_navigation_link(
        visible_from=now + timedelta(days=1),
        visible_until=now,
    )

    with pytest.raises(ValidationError):
        link.full_clean()


def test_access_policy_is_available_now_when_no_window() -> None:
    """Objects without a visibility window should be available."""
    link = create_navigation_link(
        visible_from=None,
        visible_until=None,
    )

    assert link.is_available_now() is True


def test_access_policy_is_not_available_before_visible_from() -> None:
    """Objects should be unavailable before their visibility window."""
    link = create_navigation_link(
        visible_from=timezone.now() + timedelta(days=1),
        visible_until=None,
    )

    assert link.is_available_now() is False


def test_access_policy_is_not_available_after_visible_until() -> None:
    """Objects should be unavailable after their visibility window."""
    link = create_navigation_link(
        visible_from=None,
        visible_until=timezone.now() - timedelta(days=1),
    )

    assert link.is_available_now() is False


def test_access_policy_is_available_inside_window() -> None:
    """Objects should be available during their visibility window."""
    link = create_navigation_link(
        visible_from=timezone.now() - timedelta(days=1),
        visible_until=timezone.now() + timedelta(days=1),
    )

    assert link.is_available_now() is True
