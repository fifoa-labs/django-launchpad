"""
tests/builders.py

Typed test-object builders for Launchpad models and Django authentication
objects.

These helpers use the Django ORM directly. They intentionally avoid dynamic
factory libraries so returned model types remain explicit and understandable
to static type checkers.
"""

from __future__ import annotations

from itertools import count
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import RequestFactory

from launchpad.models import Launchpad, LaunchpadNode, NavigationLink

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.http import HttpRequest

_user_sequence = count(1)
_group_sequence = count(1)
_link_sequence = count(1)
_launchpad_sequence = count(1)
_section_sequence = count(1)


def build_request(
    path: str = "/",
    *,
    user: User | AnonymousUser | None = None,
    query: dict[str, Any] | list[tuple[str, Any]] | None = None,
) -> HttpRequest:
    """Build a typed Django GET request for tests."""
    request = RequestFactory().get(
        path,
        data=query or {},
    )

    request.user = user or AnonymousUser()

    return cast("HttpRequest", request)


def build_request_with_view(
    path: str = "/",
    *,
    view_name: str,
    user: User | AnonymousUser | None = None,
    query: dict[str, Any] | list[tuple[str, Any]] | None = None,
) -> HttpRequest:
    """Build a typed request with a resolved Django view name."""
    request = build_request(
        path,
        user=user,
        query=query,
    )

    request.resolver_match = cast(
        "Any",
        SimpleNamespace(view_name=view_name),
    )

    return request


def create_user(**overrides: Any) -> User:
    """Create and return a Django test user."""
    number = next(_user_sequence)

    values: dict[str, Any] = {
        "username": f"launchpad_user_{number}",
        "email": f"launchpad_user_{number}@example.com",
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
    }
    values.update(overrides)

    return User.objects.create_user(**values)


def create_staff_user(**overrides: Any) -> User:
    """Create and return a staff user."""
    overrides.setdefault("is_staff", True)

    return create_user(**overrides)


def create_superuser(**overrides: Any) -> User:
    """Create and return a superuser."""
    overrides.setdefault("is_staff", True)
    overrides.setdefault("is_superuser", True)

    return create_user(**overrides)


def create_group(**overrides: Any) -> Group:
    """Create and return a Django authentication group."""
    number = next(_group_sequence)

    values: dict[str, Any] = {
        "name": f"Launchpad Group {number}",
    }
    values.update(overrides)

    return Group.objects.create(**values)


def create_navigation_link(
    *,
    users: Iterable[User] | None = None,
    groups: Iterable[Group] | None = None,
    **overrides: Any,
) -> NavigationLink:
    """Create and return a valid canonical navigation link."""
    number = next(_link_sequence)

    values: dict[str, Any] = {
        "created_by": create_user(),
        "code": f"navigation_link_{number}",
        "title": f"Navigation Link {number}",
        "short_title": "",
        "description": "",
        "tooltip": "",
        "aria_label": "",
        "cta_label": "",
        "url_type": NavigationLink.URLType.RAW,
        "url_value": "/",
        "url_args": [],
        "url_kwargs": {},
        "query_params": {},
        "fragment": "",
        "target": NavigationLink.Target.SELF,
        "rel": "",
        "download": False,
        "icon_type": NavigationLink.IconType.NONE,
        "icon_class": "",
        "emoji": "",
        "enabled": True,
        "disabled_reason": "",
        "active_match": NavigationLink.ActiveMatch.AUTO,
        "active_path": "",
        "active_view_name": "",
        "audience": NavigationLink.Audience.AUTHENTICATED,
        "permissions_required": [],
        "permissions_mode": NavigationLink.PermissionMode.ALL,
        "visibility_rule": "",
        "search_aliases": [],
        "metadata": {},
        "active": True,
    }
    values.update(overrides)

    link = NavigationLink.objects.create(**values)

    if users is not None:
        link.users.add(*users)

    if groups is not None:
        link.groups.add(*groups)

    return link


def create_public_navigation_link(**overrides: Any) -> NavigationLink:
    """Create and return a publicly visible navigation link."""
    overrides.setdefault(
        "audience",
        NavigationLink.Audience.PUBLIC,
    )

    return create_navigation_link(**overrides)


def create_staff_navigation_link(**overrides: Any) -> NavigationLink:
    """Create and return a staff-visible navigation link."""
    overrides.setdefault(
        "audience",
        NavigationLink.Audience.STAFF,
    )

    return create_navigation_link(**overrides)


def create_private_navigation_link(**overrides: Any) -> NavigationLink:
    """Create and return a private navigation link."""
    overrides.setdefault(
        "audience",
        NavigationLink.Audience.PRIVATE,
    )

    return create_navigation_link(**overrides)


def create_named_navigation_link(**overrides: Any) -> NavigationLink:
    """
    Create and return a navigation link using a named Django URL.

    Tests should override ``url_value`` with a URL name provided by the test
    URL configuration.
    """
    overrides.setdefault(
        "url_type",
        NavigationLink.URLType.NAMED,
    )
    overrides.setdefault(
        "url_value",
        "home",
    )

    return create_navigation_link(**overrides)


def create_emoji_navigation_link(**overrides: Any) -> NavigationLink:
    """Create and return a navigation link using an emoji icon."""
    overrides.setdefault(
        "icon_type",
        NavigationLink.IconType.EMOJI,
    )
    overrides.setdefault(
        "emoji",
        "🚀",
    )

    return create_navigation_link(**overrides)


def create_fontawesome_navigation_link(
    **overrides: Any,
) -> NavigationLink:
    """Create and return a navigation link using a FontAwesome icon."""
    overrides.setdefault(
        "icon_type",
        NavigationLink.IconType.FA,
    )
    overrides.setdefault(
        "icon_class",
        "fa-solid fa-rocket",
    )

    return create_navigation_link(**overrides)


def create_feather_navigation_link(
    **overrides: Any,
) -> NavigationLink:
    """Create and return a navigation link using a Feather icon."""
    overrides.setdefault(
        "icon_type",
        NavigationLink.IconType.FE,
    )
    overrides.setdefault(
        "icon_class",
        "navigation",
    )

    return create_navigation_link(**overrides)


def create_launchpad(**overrides: Any) -> Launchpad:
    """Create and return a Launchpad composition."""
    number = next(_launchpad_sequence)

    values: dict[str, Any] = {
        "created_by": create_user(),
        "code": f"launchpad_{number}",
        "title": f"Launchpad {number}",
        "description": "",
        "metadata": {},
        "active": True,
    }
    values.update(overrides)

    return Launchpad.objects.create(**values)


def create_launchpad_node(
    *,
    users: Iterable[User] | None = None,
    groups: Iterable[Group] | None = None,
    **overrides: Any,
) -> LaunchpadNode:
    """
    Create and return a Launchpad node.

    The default object is a valid link node.
    """
    values: dict[str, Any] = {
        "created_by": create_user(),
        "launchpad": create_launchpad(),
        "code": "",
        "kind": LaunchpadNode.Kind.LINK,
        "navigation_link": create_navigation_link(),
        "parent": None,
        "sort_order": 1000,
        "title_override": "",
        "short_title_override": "",
        "description_override": "",
        "tooltip_override": "",
        "aria_label_override": "",
        "cta_label_override": "",
        "icon_type_override": "",
        "icon_class_override": "",
        "emoji_override": "",
        "enabled_override": None,
        "disabled_reason_override": "",
        "audience": LaunchpadNode.Audience.PUBLIC,
        "permissions_required": [],
        "permissions_mode": LaunchpadNode.PermissionMode.ALL,
        "visibility_rule": "",
        "metadata": {},
        "active": True,
    }
    values.update(overrides)

    node = LaunchpadNode.objects.create(**values)

    if users is not None:
        node.users.add(*users)

    if groups is not None:
        node.groups.add(*groups)

    return node


def create_link_node(**overrides: Any) -> LaunchpadNode:
    """Create and return a valid link node."""
    overrides.setdefault(
        "kind",
        LaunchpadNode.Kind.LINK,
    )

    return create_launchpad_node(**overrides)


def create_section_node(**overrides: Any) -> LaunchpadNode:
    """Create and return a structural section node."""
    number = next(_section_sequence)

    overrides.setdefault(
        "kind",
        LaunchpadNode.Kind.SECTION,
    )
    overrides.setdefault(
        "navigation_link",
        None,
    )
    overrides.setdefault(
        "title_override",
        f"Section {number}",
    )

    return create_launchpad_node(**overrides)


def create_separator_node(**overrides: Any) -> LaunchpadNode:
    """Create and return a structural separator node."""
    overrides.setdefault(
        "kind",
        LaunchpadNode.Kind.SEPARATOR,
    )
    overrides.setdefault(
        "navigation_link",
        None,
    )
    overrides.setdefault(
        "title_override",
        "",
    )

    return create_launchpad_node(**overrides)


__all__ = [
    "create_emoji_navigation_link",
    "create_feather_navigation_link",
    "create_fontawesome_navigation_link",
    "create_group",
    "create_launchpad",
    "create_launchpad_node",
    "create_link_node",
    "create_named_navigation_link",
    "create_navigation_link",
    "create_private_navigation_link",
    "create_public_navigation_link",
    "create_section_node",
    "create_separator_node",
    "create_staff_navigation_link",
    "create_staff_user",
    "create_superuser",
    "create_user",
]
