"""
tests/admin/test_navigation_link.py

Tests for NavigationLink admin configuration and behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite

from launchpad.admin.navigation_link import NavigationLinkAdmin
from launchpad.models import NavigationLink
from tests.builders import (
    build_request,
    create_navigation_link,
    create_user,
)

if TYPE_CHECKING:
    from django.http import HttpRequest

pytestmark = pytest.mark.django_db


def _request_with_user(user: Any) -> HttpRequest:
    """Return an admin-compatible POST request for the supplied user."""
    request = build_request(
        "/admin/launchpad/navigationlink/",
        user=user,
    )
    request.method = "POST"

    return request


def _navigation_link_admin() -> NavigationLinkAdmin:
    """Return an isolated NavigationLinkAdmin instance."""
    return NavigationLinkAdmin(
        NavigationLink,
        AdminSite(),
    )


def test_navigation_link_is_registered() -> None:
    """NavigationLink should be registered with the default admin site."""
    assert admin.site.is_registered(NavigationLink) is True


def test_navigation_link_admin_list_display() -> None:
    """NavigationLink admin should expose its primary changelist fields."""
    model_admin = _navigation_link_admin()

    assert model_admin.list_display == (
        "title",
        "code",
        "url_type",
        "url_value",
        "audience",
        "enabled",
        "active",
        "created_by",
        "updated_at",
    )


def test_navigation_link_admin_list_filter() -> None:
    """NavigationLink admin should expose its primary filters."""
    model_admin = _navigation_link_admin()

    assert model_admin.list_filter == (
        "active",
        "enabled",
        "audience",
        "url_type",
        "icon_type",
        "target",
        "permissions_mode",
    )


def test_navigation_link_admin_search_fields() -> None:
    """NavigationLink admin should search identifying destination fields."""
    model_admin = _navigation_link_admin()

    assert model_admin.search_fields == (
        "code",
        "title",
        "short_title",
        "description",
        "url_value",
        "search_aliases",
    )


def test_navigation_link_admin_autocomplete_fields() -> None:
    """NavigationLink admin should autocomplete user and group relations."""
    model_admin = _navigation_link_admin()

    assert model_admin.autocomplete_fields == (
        "users",
        "groups",
    )


def test_navigation_link_admin_readonly_fields() -> None:
    """Ownership, timestamps, and resolved URL fields should be read-only."""
    model_admin = _navigation_link_admin()

    assert model_admin.readonly_fields == (
        "created_by",
        "created_at",
        "updated_at",
        "parsable_url",
        "url",
    )


def test_navigation_link_admin_fieldsets_cover_core_areas() -> None:
    """NavigationLink admin should group all major configuration areas."""
    model_admin = _navigation_link_admin()

    fieldset_titles = [title for title, _options in model_admin.fieldsets]

    assert fieldset_titles == [
        "Identity",
        "Destination",
        "Icon",
        "State",
        "Active Matching",
        "Visibility",
        "Search / Metadata",
        "Timestamps",
    ]


def test_navigation_link_admin_sets_created_by_on_create() -> None:
    """NavigationLink admin should assign the creating user on first save."""
    creator = create_user()
    request = _request_with_user(creator)

    link = NavigationLink(
        code="ancestry",
        title="Ancestry",
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
    )

    model_admin = _navigation_link_admin()

    model_admin.save_model(
        request,
        link,
        MagicMock(),
        change=False,
    )

    assert link.pk is not None
    assert link.created_by == creator


def test_navigation_link_admin_preserves_created_by_on_change() -> None:
    """Editing an existing link should preserve its creating user."""
    original_creator = create_user()
    editing_user = create_user()

    link = create_navigation_link(
        created_by=original_creator,
    )

    request = _request_with_user(editing_user)
    model_admin = _navigation_link_admin()

    model_admin.save_model(
        request,
        link,
        MagicMock(),
        change=True,
    )

    link.refresh_from_db()

    assert link.created_by == original_creator


def test_navigation_link_admin_get_queryset_optimizes_relationships() -> None:
    """NavigationLink admin should optimize ownership and visibility relations."""
    link = create_navigation_link()
    request = _request_with_user(create_user())

    queryset = _navigation_link_admin().get_queryset(request)

    assert list(queryset) == [link]
    assert queryset.query.select_related == {
        "created_by": {},
    }
    assert cast("Any", queryset)._prefetch_related_lookups == (  # noqa: SLF001
        "users",
        "groups",
    )


def test_unknown_active_match_is_never_active() -> None:
    """Unknown active-match modes should fail closed."""
    request = build_request("/ancestry/")
    link = create_navigation_link(
        url_value="/ancestry/",
    )
    link.active_match = "unknown"

    assert link.is_active_for(request) is False
