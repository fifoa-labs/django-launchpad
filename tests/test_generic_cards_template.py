"""
tests/test_generic_cards_template.py

Tests for the generic Launchpad card renderer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from django.template import Context, Template
from django.utils.translation import override

from launchpad.models import LaunchpadNode, NavigationLink
from tests.builders import (
    build_request,
    create_emoji_navigation_link,
    create_launchpad,
    create_link_node,
    create_navigation_link,
    create_section_node,
    create_separator_node,
    create_user,
)

if TYPE_CHECKING:
    from django.http import HttpRequest

pytestmark = pytest.mark.django_db


_GENERIC_CARDS_TEMPLATE = """
{% load launchpad_tags %}
{% get_launchpad launchpad_code as navigation %}
{% include "launchpad/generic/cards.html" with launchpad=navigation only %}
"""


def _render(
    source: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Render an in-memory Django template."""
    return Template(source).render(
        Context(context or {}),
    )


def _render_cards(
    launchpad_code: str,
    *,
    request: HttpRequest,
    **context: Any,
) -> str:
    """Resolve and render a Launchpad using the generic card renderer."""
    return _render(
        _GENERIC_CARDS_TEMPLATE,
        {
            "launchpad_code": launchpad_code,
            "request": request,
            **context,
        },
    )


def test_generic_cards_render_top_level_link() -> None:
    """A top-level link node should render as one semantic card."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        description="View operational reports.",
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
        cta_label="Open Reports",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert 'class="launchpad-cards"' in output
    assert 'data-launchpad-code="homepage"' in output

    assert "launchpad-card" in output
    assert 'data-launchpad-node="reports"' in output

    assert "Reports" in output
    assert "View operational reports." in output
    assert "Open Reports" in output

    assert 'href="/reports/"' in output


def test_generic_cards_render_emoji_icon() -> None:
    """Emoji icon descriptors should render inside card markup."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    link = create_emoji_navigation_link(
        code="home",
        title="Home",
        emoji="🏠",
        url_type=NavigationLink.URLType.RAW,
        url_value="/",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert "launchpad-card-icon" in output
    assert "🏠" in output


def test_generic_cards_render_font_awesome_icon() -> None:
    """Font Awesome descriptors should render their configured CSS class."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        icon_type=NavigationLink.IconType.FA,
        icon_class="fa-solid fa-chart-line",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert '<i class="fa-solid fa-chart-line"></i>' in output


def test_generic_cards_render_feather_icon() -> None:
    """Feather descriptors should render their configured icon name."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    link = create_navigation_link(
        code="settings",
        title="Settings",
        icon_type=NavigationLink.IconType.FE,
        icon_class="settings",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert 'data-feather="settings"' in output


def test_generic_cards_render_section_children_as_cards() -> None:
    """Link children inside a section should render as cards."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    section = create_section_node(
        launchpad=launchpad,
        code="operations",
        title_override="Operations",
    )

    first = create_navigation_link(
        code="shipping",
        title="Shipping",
        url_type=NavigationLink.URLType.RAW,
        url_value="/shipping/",
    )

    second = create_navigation_link(
        code="inventory",
        title="Inventory",
        url_type=NavigationLink.URLType.RAW,
        url_value="/inventory/",
    )

    create_link_node(
        launchpad=launchpad,
        parent=section,
        navigation_link=first,
        sort_order=1000,
    )

    create_link_node(
        launchpad=launchpad,
        parent=section,
        navigation_link=second,
        sort_order=2000,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert "Shipping" in output
    assert "Inventory" in output

    assert 'href="/shipping/"' in output
    assert 'href="/inventory/"' in output

    assert 'data-launchpad-section="operations"' in output


def test_generic_cards_do_not_render_section_as_card() -> None:
    """Structural section nodes should not become cards themselves."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    section = create_section_node(
        launchpad=launchpad,
        code="operations",
        title_override="Operations Section",
    )

    link = create_navigation_link(
        code="shipping",
        title="Shipping",
    )

    create_link_node(
        launchpad=launchpad,
        parent=section,
        navigation_link=link,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert "Shipping" in output
    assert "Operations Section" not in output


def test_generic_cards_ignore_separators() -> None:
    """Separators should not produce card markup."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    first = create_navigation_link(
        code="first",
        title="First",
    )

    second = create_navigation_link(
        code="second",
        title="Second",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=first,
        sort_order=1000,
    )

    create_separator_node(
        launchpad=launchpad,
        sort_order=2000,
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=second,
        sort_order=3000,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert "First" in output
    assert "Second" in output

    assert "launchpad-node-separator" not in output
    assert 'role="separator"' not in output


def test_generic_cards_render_active_state() -> None:
    """Active links should expose semantic active state."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
        active_match=NavigationLink.ActiveMatch.PATH_PREFIX,
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            "/reports/monthly/",
            user=user,
        ),
    )

    assert "launchpad-card is-active" in output
    assert 'aria-current="page"' in output


def test_generic_cards_render_disabled_link_as_non_clickable() -> None:
    """Disabled card destinations should not render an anchor."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        enabled_override=False,
        disabled_reason_override="Coming soon.",
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert "launchpad-card is-disabled" in output
    assert 'href="/reports/"' not in output
    assert "launchpad-card-action-disabled" in output
    assert 'aria-disabled="true"' in output
    assert "Coming soon." in output


def test_generic_cards_render_target_rel_and_download() -> None:
    """Link transport attributes should be preserved in card rendering."""
    user = create_user()

    launchpad = create_launchpad(
        code="downloads",
    )

    link = create_navigation_link(
        code="guide",
        title="Guide",
        url_type=NavigationLink.URLType.RAW,
        url_value="https://example.com/guide.pdf",
        target=NavigationLink.Target.BLANK,
        rel="noopener",
        download=True,
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert 'href="https://example.com/guide.pdf"' in output
    assert 'target="_blank"' in output
    assert 'rel="noopener"' in output
    assert "download" in output


def test_generic_cards_render_tooltip_and_aria_label() -> None:
    """Card links should preserve tooltip and accessibility metadata."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        tooltip="Open reports",
        aria_label="Open operational reports",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render_cards(
        launchpad.code,
        request=build_request(
            user=user,
        ),
    )

    assert 'title="Open reports"' in output
    assert 'aria-label="Open operational reports"' in output


def test_generic_cards_use_open_as_default_cta() -> None:
    """Cards without a CTA override should fall back to Open."""
    user = create_user()

    launchpad = create_launchpad(
        code="homepage",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
        cta_label="",
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    with override("en"):
        output = _render_cards(
            launchpad.code,
            request=build_request(
                user=user,
            ),
        )

    assert ">Open<" in "".join(
        output.split(),
    )


def test_generic_cards_render_empty_state() -> None:
    """An existing Launchpad without nodes should render its empty state."""
    launchpad = create_launchpad(
        code="empty_cards",
    )

    with override("en"):
        output = _render_cards(
            launchpad.code,
            request=build_request(
                user=create_user(),
            ),
        )

    assert 'data-launchpad-code="empty_cards"' in output
    assert "launchpad-empty" in output
    assert "No navigation items are available." in output


def test_generic_cards_render_nothing_for_missing_launchpad() -> None:
    """A missing Launchpad should render no card markup."""
    output = _render_cards(
        "missing_cards",
        request=build_request(
            user=create_user(),
        ),
    )

    assert output.strip() == ""


def test_generic_cards_apply_visibility_before_rendering() -> None:
    """Only nodes surviving Launchpad visibility should become cards."""
    allowed_user = create_user()
    denied_user = create_user()

    launchpad = create_launchpad(
        code="private_cards",
    )

    link = create_navigation_link(
        code="private_report",
        title="Private Report",
        audience=NavigationLink.Audience.PRIVATE,
        users=[allowed_user],
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
        audience=LaunchpadNode.Audience.PUBLIC,
    )

    allowed_output = _render_cards(
        launchpad.code,
        request=build_request(
            user=allowed_user,
        ),
    )

    denied_output = _render_cards(
        launchpad.code,
        request=build_request(
            user=denied_user,
        ),
    )

    assert "Private Report" in allowed_output
    assert "Private Report" not in denied_output


def test_generic_cards_render_context_aware_url() -> None:
    """Resolved runtime context should flow into generic card URLs."""
    user = create_user()

    launchpad = create_launchpad(
        code="person_cards",
    )

    link = create_navigation_link(
        code="person",
        title="Person",
        url_type=NavigationLink.URLType.RAW,
        url_value="/people/",
        query_params={
            "person": "@context.person.pk",
        },
    )

    create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    output = _render(
        """
        {% load launchpad_tags %}
        {% get_launchpad "person_cards" person=person as navigation %}
        {% include "launchpad/generic/cards.html" with launchpad=navigation only %}
        """,
        {
            "request": build_request(
                user=user,
            ),
            "person": type(
                "Person",
                (),
                {
                    "pk": 42,
                },
            )(),
        },
    )

    assert 'href="/people/?person=42"' in output
