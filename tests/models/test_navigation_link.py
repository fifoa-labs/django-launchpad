"""
tests/models/test_navigation_link.py

Tests for NavigationLink model behavior.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from launchpad.models import NavigationLink
from tests.builders import (
    build_request,
    build_request_with_view,
    create_emoji_navigation_link,
    create_feather_navigation_link,
    create_fontawesome_navigation_link,
    create_named_navigation_link,
    create_navigation_link,
    create_user,
)

pytestmark = pytest.mark.django_db


def test_navigation_link_str_returns_title() -> None:
    """NavigationLink string conversion should return its title."""
    link = create_navigation_link(title="Ancestry")

    assert str(link) == "Ancestry"


def test_navigation_link_code_is_unique() -> None:
    """NavigationLink codes should be globally unique."""
    create_navigation_link(code="ancestry")

    with pytest.raises(IntegrityError):
        create_navigation_link(code="ancestry")


def test_display_title_returns_title() -> None:
    """Display title should return the canonical title."""
    link = create_navigation_link(title="Ancestry")

    assert link.display_title == "Ancestry"


def test_display_short_title_falls_back_to_title() -> None:
    """Blank short titles should fall back to the canonical title."""
    link = create_navigation_link(
        title="Ancestry",
        short_title="",
    )

    assert link.display_short_title == "Ancestry"


def test_display_short_title_uses_short_title() -> None:
    """Configured short titles should take precedence."""
    link = create_navigation_link(
        title="Ancestry",
        short_title="Tree",
    )

    assert link.display_short_title == "Tree"


def test_display_aria_label_falls_back_to_title() -> None:
    """Blank accessibility labels should fall back to the title."""
    link = create_navigation_link(
        title="Ancestry",
        aria_label="",
    )

    assert link.display_aria_label == "Ancestry"


def test_display_aria_label_uses_aria_label() -> None:
    """Configured accessibility labels should take precedence."""
    link = create_navigation_link(
        title="Ancestry",
        aria_label="Open family tree",
    )

    assert link.display_aria_label == "Open family tree"


def test_effective_rel_defaults_for_new_tab() -> None:
    """New-tab links should receive safe default rel attributes."""
    link = create_navigation_link(
        target=NavigationLink.Target.BLANK,
        rel="",
    )

    assert link.effective_rel == "noopener noreferrer"


def test_effective_rel_uses_custom_rel() -> None:
    """Custom rel values should override the default."""
    link = create_navigation_link(
        target=NavigationLink.Target.BLANK,
        rel="nofollow",
    )

    assert link.effective_rel == "nofollow"


def test_raw_url_resolves_as_configured() -> None:
    """Valid raw URLs should resolve unchanged."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
    )

    assert link.url == "/ancestry/"
    assert link.parsable_url is True


def test_raw_url_with_query_and_fragment_resolves() -> None:
    """Query parameters and fragments should be appended."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
        query_params={
            "tab": "monthly",
            "year": 2026,
        },
        fragment="summary",
    )

    assert link.resolve_url() == "/reports/?tab=monthly&year=2026#summary"


def test_existing_query_params_are_preserved() -> None:
    """Existing raw URL query parameters should be preserved."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/?existing=1",
        query_params={
            "tab": "monthly",
        },
    )

    assert link.resolve_url() == "/reports/?existing=1&tab=monthly"


def test_list_query_params_are_encoded() -> None:
    """List query parameters should be encoded as repeated keys."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
        query_params={
            "tag": ["a", "b"],
        },
    )

    assert link.resolve_url() == "/reports/?tag=a&tag=b"


@pytest.mark.parametrize(
    "url",
    [
        "#",
        " javascript:alert(1)",
        "javascript:alert(1)",
        "data:text/html,bad",
        "vbscript:alert(1)",
        "//example.com/path",
        "ftp://example.com/file",
    ],
)
def test_unsafe_raw_urls_fail_validation(url: str) -> None:
    """Unsafe raw URL values should fail model validation."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/safe/",
    )
    link.url_value = url

    with pytest.raises(ValidationError):
        link.full_clean()


def test_invalid_raw_url_is_not_parsable() -> None:
    """Invalid raw URLs should fail closed."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="javascript:alert(1)",
    )

    assert link.parsable_url is False
    assert link.resolve_url() == "#"


def test_named_url_resolves() -> None:
    """Valid named Django URLs should resolve."""
    link = create_named_navigation_link(
        url_value="admin:index",
    )

    assert link.parsable_url is True
    assert link.resolve_url().endswith("/admin/")


def test_invalid_named_url_is_not_parsable() -> None:
    """Invalid named URLs should fail closed."""
    link = create_named_navigation_link(
        url_value="not_a_real_url_name",
    )

    assert link.parsable_url is False
    assert link.resolve_url() == "#"


def test_context_reference_in_query_params_resolves() -> None:
    """Runtime user and context references should resolve."""
    user = create_user(username="huy")
    request = build_request(
        "/",
        user=user,
    )

    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/profile/",
        query_params={
            "username": "@user.username",
            "person": "@context.person_id",
        },
    )

    assert (
        link.resolve_url(
            request=request,
            context={"person_id": 123},
        )
        == "/profile/?username=huy&person=123"
    )


def test_disabled_link_resolves_to_hash() -> None:
    """Disabled links should resolve to a safe hash target."""
    link = create_navigation_link(
        enabled=False,
        disabled_reason="Coming soon.",
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
    )

    assert link.resolve_url() == "#"


def test_disabled_link_requires_reason() -> None:
    """Disabled links should include an explanation."""
    link = create_navigation_link(
        enabled=False,
        disabled_reason="",
    )

    with pytest.raises(ValidationError):
        link.full_clean()


def test_emoji_icon_descriptor() -> None:
    """Emoji links should return an emoji descriptor."""
    link = create_emoji_navigation_link(emoji="🌳")

    assert link.icon_descriptor == {
        "kind": "emoji",
        "value": "🌳",
    }


def test_fontawesome_icon_descriptor() -> None:
    """FontAwesome links should return a FontAwesome descriptor."""
    link = create_fontawesome_navigation_link(
        icon_class="fa-solid fa-tree",
    )

    assert link.icon_descriptor == {
        "kind": "fa",
        "value": "fa-solid fa-tree",
    }


def test_feather_icon_descriptor() -> None:
    """Feather links should return a Feather descriptor."""
    link = create_feather_navigation_link(
        icon_class="navigation",
    )

    assert link.icon_descriptor == {
        "kind": "fe",
        "value": "navigation",
    }


def test_none_icon_descriptor() -> None:
    """Links without icons should return a none descriptor."""
    link = create_navigation_link(
        icon_type=NavigationLink.IconType.NONE,
        icon_class="",
        emoji="",
    )

    assert link.icon_descriptor == {
        "kind": "none",
        "value": "",
    }


def test_fontawesome_icon_requires_icon_class() -> None:
    """FontAwesome links should require an icon class."""
    link = create_navigation_link(
        icon_type=NavigationLink.IconType.FA,
        icon_class="",
    )

    with pytest.raises(ValidationError):
        link.full_clean()


def test_feather_icon_requires_icon_class() -> None:
    """Feather links should require an icon name."""
    link = create_navigation_link(
        icon_type=NavigationLink.IconType.FE,
        icon_class="",
    )

    with pytest.raises(ValidationError):
        link.full_clean()


def test_emoji_icon_requires_emoji() -> None:
    """Emoji links should require an emoji value."""
    link = create_navigation_link(
        icon_type=NavigationLink.IconType.EMOJI,
        emoji="",
    )

    with pytest.raises(ValidationError):
        link.full_clean()


def test_exact_path_active_match() -> None:
    """Exact-path matching should activate identical paths."""
    request = build_request("/ancestry/")
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.EXACT_PATH,
    )

    assert link.is_active_for(request) is True


def test_path_prefix_active_match() -> None:
    """Path-prefix matching should activate descendant paths."""
    request = build_request("/ancestry/people/42/")
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.PATH_PREFIX,
    )

    assert link.is_active_for(request) is True


def test_view_name_active_match() -> None:
    """View-name matching should compare the resolved view name."""
    request = build_request_with_view(
        "/anything/",
        view_name="ancestry:index",
    )

    link = create_navigation_link(
        active_match=NavigationLink.ActiveMatch.VIEW_NAME,
        active_view_name="ancestry:index",
    )

    assert link.is_active_for(request) is True


def test_view_prefix_active_match() -> None:
    """View-prefix matching should support application namespaces."""
    request = build_request_with_view(
        "/anything/",
        view_name="ancestry:person-detail",
    )

    link = create_navigation_link(
        active_match=NavigationLink.ActiveMatch.VIEW_PREFIX,
        active_view_name="ancestry:",
    )

    assert link.is_active_for(request) is True


def test_query_params_must_match_for_active_state() -> None:
    """Configured query parameters should participate in active matching."""
    monthly_request = build_request(
        "/reports/",
        query={"tab": "monthly"},
    )
    annual_request = build_request(
        "/reports/",
        query={"tab": "annual"},
    )

    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
        query_params={
            "tab": "monthly",
        },
        active_match=NavigationLink.ActiveMatch.PATH_PREFIX,
    )

    assert link.is_active_for(monthly_request) is True
    assert link.is_active_for(annual_request) is False


def test_active_match_none_is_never_active() -> None:
    """Never-active links should remain inactive."""
    request = build_request("/ancestry/")
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.NONE,
    )

    assert link.is_active_for(request) is False


def test_visible_to_delegates_to_visibility_engine() -> None:
    """NavigationLink.visible_to should delegate to visibility policy."""
    user = create_user()
    link = create_navigation_link(
        audience=NavigationLink.Audience.AUTHENTICATED,
    )

    assert link.visible_to(user) is True


def test_valid_raw_url_passes_full_clean() -> None:
    """Valid raw links should pass complete model validation."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
    )

    link.full_clean()


def test_named_url_requires_value() -> None:
    """Named links should require a URL name."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.NAMED,
        url_value="",
    )

    with pytest.raises(ValidationError):
        link.full_clean()


def test_named_url_must_reverse_during_validation() -> None:
    """Static named URLs should reverse successfully during validation."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.NAMED,
        url_value="missing:view",
    )

    with pytest.raises(ValidationError):
        link.full_clean()


def test_context_aware_named_url_skips_static_reverse_validation() -> None:
    """Context-aware named URLs should defer reversal until runtime."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.NAMED,
        url_value="person-detail",
        url_args=[
            "@context.person_id",
        ],
    )

    link.full_clean(exclude={"url_value"})


def test_icon_descriptor_uses_emoji_fallback() -> None:
    """An emoji value should remain usable without an explicit icon type."""
    link = create_navigation_link(
        icon_type=NavigationLink.IconType.NONE,
        emoji="🌳",
    )

    assert link.icon_descriptor == {
        "kind": "emoji",
        "value": "🌳",
    }


def test_blank_rel_for_same_tab_is_empty() -> None:
    """Same-tab links without a rel value should keep it blank."""
    link = create_navigation_link(
        target=NavigationLink.Target.SELF,
        rel="",
    )

    assert link.effective_rel == ""


def test_unknown_url_type_is_not_parsable() -> None:
    """Unknown URL types should fail closed during inspection."""
    link = create_navigation_link()
    link.url_type = "unknown"

    assert link.parsable_url is False


def test_context_aware_named_url_is_considered_parsable() -> None:
    """Named URLs containing runtime references should be parsable."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.NAMED,
        url_value="person-detail",
        url_kwargs={
            "pk": "@context.person.pk",
        },
    )

    assert link.parsable_url is True


def test_unknown_url_type_resolves_to_hash() -> None:
    """Unknown URL types should resolve to a safe hash target."""
    link = create_navigation_link()
    link.url_type = "unknown"

    assert link.resolve_url() == "#"


def test_active_path_overrides_resolved_url() -> None:
    """Configured active paths should override the destination URL."""
    request = build_request("/custom-active-path/")
    link = create_navigation_link(
        url_value="/different-destination/",
        active_path="/custom-active-path/",
        active_match=NavigationLink.ActiveMatch.EXACT_PATH,
    )

    assert link.is_active_for(request) is True


def test_query_params_fail_without_request_get() -> None:
    """Query matching should fail when the request has no GET mapping."""
    request = type(
        "RequestWithoutGet",
        (),
        {
            "path": "/reports/",
            "resolver_match": None,
        },
    )()

    link = create_navigation_link(
        url_value="/reports/",
        query_params={
            "tab": "monthly",
        },
        active_match=NavigationLink.ActiveMatch.EXACT_PATH,
    )

    assert link.is_active_for(request) is False


def test_list_query_params_must_match_in_order() -> None:
    """List query parameters should match all values in configured order."""
    matching_request = build_request(
        "/reports/",
        query=[
            ("tag", "a"),
            ("tag", "b"),
        ],
    )
    mismatching_request = build_request(
        "/reports/",
        query=[
            ("tag", "b"),
            ("tag", "a"),
        ],
    )

    link = create_navigation_link(
        url_value="/reports/",
        query_params={
            "tag": ["a", "b"],
        },
        active_match=NavigationLink.ActiveMatch.EXACT_PATH,
    )

    assert link.is_active_for(matching_request) is True
    assert link.is_active_for(mismatching_request) is False


def test_is_active_for_returns_false_without_request() -> None:
    """Active-state evaluation should require a request."""
    link = create_navigation_link()

    assert link.is_active_for(None) is False


def test_view_name_match_defaults_to_url_value() -> None:
    """View-name matching should fall back to the configured URL name."""
    request = build_request_with_view(
        "/anything/",
        view_name="admin:index",
    )
    link = create_named_navigation_link(
        url_value="admin:index",
        active_match=NavigationLink.ActiveMatch.VIEW_NAME,
        active_view_name="",
    )

    assert link.is_active_for(request) is True


def test_view_prefix_match_defaults_to_url_value() -> None:
    """View-prefix matching should fall back to the configured URL value."""
    request = build_request_with_view(
        "/anything/",
        view_name="admin:index",
    )
    link = create_named_navigation_link(
        url_value="admin:",
        active_match=NavigationLink.ActiveMatch.VIEW_PREFIX,
        active_view_name="",
    )

    assert link.is_active_for(request) is True


def test_path_prefix_matches_exact_target_without_trailing_slash() -> None:
    """Path-prefix mode should match the target path itself."""
    request = build_request("/ancestry")
    link = create_navigation_link(
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.PATH_PREFIX,
    )

    assert link.is_active_for(request) is True


def test_path_prefix_rejects_similar_unrelated_path() -> None:
    """Path-prefix mode should not match merely similar path names."""
    request = build_request("/ancestry-tools/")
    link = create_navigation_link(
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.PATH_PREFIX,
    )

    assert link.is_active_for(request) is False


def test_auto_named_url_matches_view_name() -> None:
    """Automatic matching should prefer named-view identity."""
    request = build_request_with_view(
        "/admin/",
        view_name="admin:index",
    )
    link = create_named_navigation_link(
        url_value="admin:index",
        active_match=NavigationLink.ActiveMatch.AUTO,
    )

    assert link.is_active_for(request) is True


def test_auto_named_url_falls_back_to_resolved_path() -> None:
    """Automatic named matching should fall back to the resolved path."""
    request = build_request("/admin/")
    link = create_named_navigation_link(
        url_value="admin:index",
        active_match=NavigationLink.ActiveMatch.AUTO,
    )

    assert link.is_active_for(request) is True


def test_auto_raw_url_matches_descendant_path() -> None:
    """Automatic raw matching should activate descendant paths."""
    request = build_request("/ancestry/people/42/")
    link = create_navigation_link(
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.AUTO,
    )

    assert link.is_active_for(request) is True


def test_auto_matching_rejects_unrelated_path() -> None:
    """Automatic matching should reject unrelated paths."""
    request = build_request("/reports/")
    link = create_navigation_link(
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.AUTO,
    )

    assert link.is_active_for(request) is False
