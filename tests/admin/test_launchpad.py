"""
tests/admin/test_launchpad.py

Tests for Launchpad and LaunchpadNode admin configuration and behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite

from launchpad.admin.launchpad import (
    LaunchpadAdmin,
    LaunchpadNodeAdmin,
    LaunchpadNodeInline,
)
from launchpad.models import Launchpad, LaunchpadNode
from tests.builders import (
    build_request,
    create_launchpad,
    create_section_node,
    create_user,
)

if TYPE_CHECKING:
    from django.http import HttpRequest

pytestmark = pytest.mark.django_db


def _request_with_user(user: Any) -> HttpRequest:
    """Return an admin-compatible POST request for the supplied user."""
    request = build_request(
        "/admin/launchpad/",
        user=user,
    )
    request.method = "POST"

    return request


def _launchpad_admin() -> LaunchpadAdmin:
    """Return an isolated LaunchpadAdmin instance."""
    return LaunchpadAdmin(
        Launchpad,
        AdminSite(),
    )


def _launchpad_node_admin() -> LaunchpadNodeAdmin:
    """Return an isolated LaunchpadNodeAdmin instance."""
    return LaunchpadNodeAdmin(
        LaunchpadNode,
        AdminSite(),
    )


def test_launchpad_models_are_registered() -> None:
    """Both Launchpad models should be registered with the admin site."""
    assert admin.site.is_registered(Launchpad) is True
    assert admin.site.is_registered(LaunchpadNode) is True


def test_launchpad_admin_list_display() -> None:
    """Launchpad admin should expose its primary changelist fields."""
    model_admin = _launchpad_admin()

    assert model_admin.list_display == (
        "title",
        "code",
        "active",
        "created_by",
        "updated_at",
    )


def test_launchpad_admin_list_filter() -> None:
    """Launchpad admin should filter by active state."""
    model_admin = _launchpad_admin()

    assert model_admin.list_filter == ("active",)


def test_launchpad_admin_search_fields() -> None:
    """Launchpad admin should search identifying text fields."""
    model_admin = _launchpad_admin()

    assert model_admin.search_fields == (
        "code",
        "title",
        "description",
    )


def test_launchpad_admin_readonly_fields() -> None:
    """Ownership and timestamp fields should be read-only."""
    model_admin = _launchpad_admin()

    assert model_admin.readonly_fields == (
        "created_by",
        "created_at",
        "updated_at",
    )


def test_launchpad_admin_uses_node_inline() -> None:
    """Launchpad admin should include its node inline."""
    model_admin = _launchpad_admin()

    assert model_admin.inlines == [
        LaunchpadNodeInline,
    ]


def test_launchpad_node_inline_configuration() -> None:
    """The node inline should expose the intended placement fields."""
    inline = LaunchpadNodeInline(
        Launchpad,
        AdminSite(),
    )

    assert inline.extra == 0

    assert inline.fields == (
        "kind",
        "navigation_link",
        "parent",
        "code",
        "title_override",
        "sort_order",
        "audience",
        "active",
    )

    assert inline.autocomplete_fields == (
        "navigation_link",
        "parent",
    )

    assert inline.readonly_fields == ("created_by",)
    assert inline.show_change_link is True


def test_launchpad_admin_sets_created_by_on_create() -> None:
    """Launchpad admin should assign the creating user on first save."""
    creator = create_user()
    request = _request_with_user(creator)

    launchpad = Launchpad(
        code="primary_navigation",
        title="Primary Navigation",
    )

    model_admin = _launchpad_admin()

    model_admin.save_model(
        request,
        launchpad,
        MagicMock(),
        change=False,
    )

    assert launchpad.pk is not None
    assert launchpad.created_by == creator


def test_launchpad_admin_preserves_created_by_on_change() -> None:
    """Editing an existing Launchpad should preserve its creator."""
    original_creator = create_user()
    editing_user = create_user()

    launchpad = create_launchpad(
        created_by=original_creator,
    )

    request = _request_with_user(editing_user)
    model_admin = _launchpad_admin()

    model_admin.save_model(
        request,
        launchpad,
        MagicMock(),
        change=True,
    )

    launchpad.refresh_from_db()

    assert launchpad.created_by == original_creator


def test_launchpad_admin_sets_created_by_on_new_inline_node() -> None:
    """New inline nodes should inherit the current admin user."""
    creator = create_user()
    launchpad = create_launchpad()

    node = LaunchpadNode(
        launchpad=launchpad,
        kind=LaunchpadNode.Kind.SECTION,
        title_override="Apps",
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    formset = MagicMock()
    formset.save.return_value = [node]
    formset.deleted_objects = []

    request = _request_with_user(creator)
    model_admin = _launchpad_admin()

    model_admin.save_formset(
        request,
        MagicMock(),
        formset,
        change=True,
    )

    assert node.pk is not None
    assert node.created_by == creator

    formset.save.assert_called_once_with(
        commit=False,
    )
    formset.save_m2m.assert_called_once_with()


def test_launchpad_admin_deletes_removed_inline_nodes() -> None:
    """Removed inline nodes should be deleted."""
    node = create_section_node()
    node_pk = node.pk

    formset = MagicMock()
    formset.save.return_value = []
    formset.deleted_objects = [node]

    request = _request_with_user(create_user())
    model_admin = _launchpad_admin()

    model_admin.save_formset(
        request,
        MagicMock(),
        formset,
        change=True,
    )

    assert (
        LaunchpadNode.objects.filter(
            pk=node_pk,
        ).exists()
        is False
    )

    formset.save_m2m.assert_called_once_with()


def test_launchpad_node_admin_list_display() -> None:
    """Node admin should expose placement and visibility information."""
    model_admin = _launchpad_node_admin()

    assert model_admin.list_display == (
        "effective_title",
        "launchpad",
        "kind",
        "navigation_link",
        "parent",
        "sort_order",
        "audience",
        "active",
        "created_by",
    )


def test_launchpad_node_admin_list_filter() -> None:
    """Node admin should expose its primary filters."""
    model_admin = _launchpad_node_admin()

    assert model_admin.list_filter == (
        "active",
        "kind",
        "audience",
        "launchpad",
        "permissions_mode",
    )


def test_launchpad_node_admin_autocomplete_fields() -> None:
    """Node admin should autocomplete related records."""
    model_admin = _launchpad_node_admin()

    assert model_admin.autocomplete_fields == (
        "launchpad",
        "navigation_link",
        "parent",
        "users",
        "groups",
    )


def test_launchpad_node_admin_sets_created_by_on_create() -> None:
    """Node admin should assign the creating user on first save."""
    creator = create_user()
    launchpad = create_launchpad()

    node = LaunchpadNode(
        launchpad=launchpad,
        kind=LaunchpadNode.Kind.SECTION,
        title_override="Applications",
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    request = _request_with_user(creator)
    model_admin = _launchpad_node_admin()

    model_admin.save_model(
        request,
        node,
        MagicMock(),
        change=False,
    )

    assert node.pk is not None
    assert node.created_by == creator


def test_launchpad_node_admin_preserves_created_by_on_change() -> None:
    """Editing an existing node should preserve its creator."""
    original_creator = create_user()
    editing_user = create_user()

    node = create_section_node(
        created_by=original_creator,
    )

    request = _request_with_user(editing_user)
    model_admin = _launchpad_node_admin()

    model_admin.save_model(
        request,
        node,
        MagicMock(),
        change=True,
    )

    node.refresh_from_db()

    assert node.created_by == original_creator


def test_launchpad_admin_get_queryset_selects_created_by() -> None:
    """Launchpad admin should optimize its creator relationship."""
    launchpad = create_launchpad()
    request = _request_with_user(create_user())

    queryset = _launchpad_admin().get_queryset(request)

    assert list(queryset) == [launchpad]
    assert queryset.query.select_related == {
        "created_by": {},
    }


def test_launchpad_admin_preserves_created_by_on_new_inline_node() -> None:
    """Inline saving should preserve an explicitly assigned creator."""
    original_creator = create_user()
    editing_user = create_user()
    launchpad = create_launchpad()

    node = LaunchpadNode(
        created_by=original_creator,
        launchpad=launchpad,
        kind=LaunchpadNode.Kind.SECTION,
        title_override="Apps",
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    formset = MagicMock()
    formset.save.return_value = [node]
    formset.deleted_objects = []

    request = _request_with_user(editing_user)

    _launchpad_admin().save_formset(
        request,
        MagicMock(),
        formset,
        change=True,
    )

    node.refresh_from_db()

    assert node.created_by == original_creator
    formset.save_m2m.assert_called_once_with()


def test_launchpad_node_admin_get_queryset_optimizes_relationships() -> None:
    """Node admin should optimize its foreign-key and many-to-many relations."""
    node = create_section_node()
    request = _request_with_user(create_user())

    queryset = _launchpad_node_admin().get_queryset(request)

    assert list(queryset) == [node]
    assert queryset.query.select_related == {
        "created_by": {},
        "launchpad": {},
        "navigation_link": {},
        "parent": {},
    }
    assert cast("Any", queryset)._prefetch_related_lookups == (  # noqa: SLF001
        "users",
        "groups",
    )
