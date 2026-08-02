"""
tests/models/test_launchpad.py

Tests for Launchpad and LaunchpadNode models.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

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

pytestmark = pytest.mark.django_db


def test_launchpad_str_returns_title() -> None:
    """Launchpad string conversion should return its title."""
    launchpad = create_launchpad(
        title="Primary Navigation",
    )

    assert str(launchpad) == "Primary Navigation"


def test_launchpad_root_nodes_returns_nodes_without_parent() -> None:
    """Root nodes should exclude descendants."""
    launchpad = create_launchpad()
    root = create_section_node(
        launchpad=launchpad,
        title_override="Apps",
    )
    create_link_node(
        launchpad=launchpad,
        parent=root,
    )

    assert list(launchpad.root_nodes) == [root]


def test_launchpad_code_is_unique() -> None:
    """Launchpad codes should be globally unique."""
    create_launchpad(code="primary_navigation")

    with pytest.raises(IntegrityError):
        create_launchpad(code="primary_navigation")


def test_launchpad_node_str_uses_launchpad_code_and_effective_title() -> None:
    """Node string conversion should include launchpad code and title."""
    launchpad = create_launchpad(code="primary_navigation")
    node = create_section_node(
        launchpad=launchpad,
        title_override="Apps",
    )

    assert str(node) == "primary_navigation: Apps"


def test_launchpad_node_default_sort_order_is_1000() -> None:
    """Launchpad nodes should default to sort order 1000."""
    node = LaunchpadNode(
        launchpad=create_launchpad(),
        created_by=create_user(),
        kind=LaunchpadNode.Kind.SECTION,
        title_override="Apps",
    )

    assert node.sort_order == 1000


def test_launchpad_node_code_unique_per_launchpad_when_provided() -> None:
    """Nonblank node codes should be unique within a launchpad."""
    launchpad = create_launchpad()

    create_section_node(
        launchpad=launchpad,
        code="apps",
    )

    with pytest.raises(IntegrityError):
        create_section_node(
            launchpad=launchpad,
            code="apps",
        )


def test_launchpad_node_allows_blank_code_more_than_once() -> None:
    """Blank node codes may be reused within a launchpad."""
    launchpad = create_launchpad()

    first = create_section_node(
        launchpad=launchpad,
        code="",
    )
    second = create_section_node(
        launchpad=launchpad,
        code="",
    )

    assert first.pk is not None
    assert second.pk is not None


def test_link_node_requires_navigation_link() -> None:
    """Link nodes must reference a NavigationLink."""
    node = create_link_node()
    node.navigation_link = None

    with pytest.raises(ValidationError):
        node.full_clean()


def test_section_node_cannot_reference_navigation_link() -> None:
    """Section nodes must not reference a NavigationLink."""
    node = create_section_node()
    node.navigation_link = create_navigation_link()

    with pytest.raises(ValidationError):
        node.full_clean()


def test_separator_node_cannot_reference_navigation_link() -> None:
    """Separator nodes must not reference a NavigationLink."""
    node = create_separator_node()
    node.navigation_link = create_navigation_link()

    with pytest.raises(ValidationError):
        node.full_clean()


def test_node_cannot_be_its_own_parent() -> None:
    """A node must not reference itself as parent."""
    node = create_section_node()
    node.parent = node

    with pytest.raises(ValidationError):
        node.full_clean()


def test_node_parent_must_belong_to_same_launchpad() -> None:
    """A node parent must belong to the same launchpad."""
    first_launchpad = create_launchpad()
    second_launchpad = create_launchpad()

    parent = create_section_node(
        launchpad=first_launchpad,
    )
    child = create_section_node(
        launchpad=second_launchpad,
    )

    child.parent = parent

    with pytest.raises(ValidationError):
        child.full_clean()


def test_separator_node_cannot_be_parent() -> None:
    """Separator nodes must not have child nodes."""
    launchpad = create_launchpad()
    separator = create_separator_node(
        launchpad=launchpad,
    )

    child = create_section_node(
        launchpad=launchpad,
    )
    child.parent = separator

    with pytest.raises(ValidationError):
        child.full_clean()


def test_separator_node_cannot_have_children() -> None:
    """Separator validation should reject existing descendants."""
    launchpad = create_launchpad()
    separator = create_separator_node(
        launchpad=launchpad,
    )

    # Bypass model validation intentionally so the separator itself can
    # detect the invalid existing child.
    LaunchpadNode.objects.create(
        created_by=create_user(),
        launchpad=launchpad,
        kind=LaunchpadNode.Kind.SECTION,
        parent=separator,
        title_override="Invalid child",
    )

    with pytest.raises(ValidationError):
        separator.full_clean()


def test_launchpad_node_cycle_is_rejected() -> None:
    """Node hierarchies must not contain cycles."""
    launchpad = create_launchpad()

    root = create_section_node(
        launchpad=launchpad,
        title_override="Root",
    )
    child = create_section_node(
        launchpad=launchpad,
        parent=root,
        title_override="Child",
    )

    root.parent = child

    with pytest.raises(ValidationError):
        root.full_clean()


def test_effective_code_uses_node_code_first() -> None:
    """Placement code should override linked destination code."""
    node = create_link_node(
        code="custom-placement",
    )

    assert node.effective_code == "custom-placement"


def test_effective_code_falls_back_to_navigation_link_code() -> None:
    """Blank placement code should fall back to linked destination code."""
    link = create_navigation_link(code="ancestry")
    node = create_link_node(
        code="",
        navigation_link=link,
    )

    assert node.effective_code == "ancestry"


def test_effective_title_uses_override_first() -> None:
    """Placement title should override the canonical link title."""
    link = create_navigation_link(title="Ancestry")
    node = create_link_node(
        navigation_link=link,
        title_override="Family Tree",
    )

    assert node.effective_title == "Family Tree"


def test_effective_title_falls_back_to_navigation_link_title() -> None:
    """Blank placement title should use the canonical link title."""
    link = create_navigation_link(title="Ancestry")
    node = create_link_node(
        navigation_link=link,
        title_override="",
    )

    assert node.effective_title == "Ancestry"


def test_effective_short_title_uses_override_first() -> None:
    """Placement short title should override the canonical short title."""
    link = create_navigation_link(
        title="Ancestry",
        short_title="Tree",
    )
    node = create_link_node(
        navigation_link=link,
        short_title_override="Family",
    )

    assert node.effective_short_title == "Family"


def test_effective_description_uses_override_first() -> None:
    """Placement description should override the canonical description."""
    link = create_navigation_link(
        description="Canonical description.",
    )
    node = create_link_node(
        navigation_link=link,
        description_override="Placement description.",
    )

    assert node.effective_description == "Placement description."


def test_effective_icon_descriptor_uses_node_emoji_override() -> None:
    """Node icon override should take precedence over the linked icon."""
    link = create_emoji_navigation_link(emoji="🌳")
    node = create_link_node(
        navigation_link=link,
        icon_type_override=NavigationLink.IconType.EMOJI,
        emoji_override="🚀",
    )

    assert node.effective_icon_descriptor == {
        "kind": "emoji",
        "value": "🚀",
    }


def test_effective_icon_descriptor_falls_back_to_link_icon() -> None:
    """Nodes without icon overrides should use the linked icon."""
    link = create_emoji_navigation_link(emoji="🌳")
    node = create_link_node(
        navigation_link=link,
    )

    assert node.effective_icon_descriptor == {
        "kind": "emoji",
        "value": "🌳",
    }


def test_icon_override_requires_matching_icon_value() -> None:
    """Configured icon overrides should require matching icon data."""
    node = create_link_node(
        icon_type_override=NavigationLink.IconType.FA,
        icon_class_override="",
    )

    with pytest.raises(ValidationError):
        node.full_clean()


def test_effective_enabled_uses_node_override() -> None:
    """Node enabled override should take precedence over the link default."""
    link = create_navigation_link(enabled=True)
    node = create_link_node(
        navigation_link=link,
        enabled_override=False,
        disabled_reason_override="Not ready.",
    )

    assert node.effective_enabled is False
    assert node.effective_disabled_reason == "Not ready."


def test_disabled_override_requires_reason() -> None:
    """Disabled placement overrides should include a reason."""
    link = create_navigation_link(
        enabled=True,
        disabled_reason="",
    )
    node = create_link_node(
        navigation_link=link,
        enabled_override=False,
        disabled_reason_override="",
    )

    with pytest.raises(ValidationError):
        node.full_clean()


def test_link_node_resolves_url_from_navigation_link() -> None:
    """Link nodes should delegate URL resolution to NavigationLink."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
    )
    node = create_link_node(
        navigation_link=link,
    )

    assert node.resolve_url() == "/ancestry/"


def test_disabled_link_node_resolves_to_hash() -> None:
    """Disabled link nodes should resolve to a safe hash target."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
    )
    node = create_link_node(
        navigation_link=link,
        enabled_override=False,
        disabled_reason_override="Coming soon.",
    )

    assert node.resolve_url() == "#"


def test_non_link_node_resolves_to_hash() -> None:
    """Structural nodes should resolve to a safe hash target."""
    node = create_section_node(
        title_override="Apps",
    )

    assert node.resolve_url() == "#"


def test_same_navigation_link_can_be_placed_multiple_times() -> None:
    """One canonical link may have multiple launchpad placements."""
    link = create_navigation_link(code="ancestry")

    first_launchpad = create_launchpad(code="primary_navigation")
    second_launchpad = create_launchpad(code="homepage")

    first_node = create_link_node(
        launchpad=first_launchpad,
        navigation_link=link,
        title_override="Ancestry",
    )
    second_node = create_link_node(
        launchpad=second_launchpad,
        navigation_link=link,
        title_override="Family Tree",
    )

    assert first_node.navigation_link == link
    assert second_node.navigation_link == link
    assert first_node.effective_title == "Ancestry"
    assert second_node.effective_title == "Family Tree"


def test_effective_code_falls_back_to_kind_before_save() -> None:
    """Unsaved structural nodes should fall back to their kind."""
    node = LaunchpadNode(
        launchpad=create_launchpad(),
        created_by=create_user(),
        kind=LaunchpadNode.Kind.SECTION,
    )

    assert node.effective_code == "section"


def test_effective_code_falls_back_to_generated_identifier_after_save() -> None:
    """Saved structural nodes should generate a stable fallback code."""
    node = create_section_node(
        title_override="Apps",
    )
    node.code = ""
    node.title_override = ""

    assert node.effective_code == f"section-{node.pk}"


def test_effective_title_for_structure_without_title_is_empty() -> None:
    """Structural nodes without overrides should have an empty title."""
    node = create_separator_node()

    assert node.effective_title == ""


def test_effective_short_title_falls_back_to_effective_title() -> None:
    """Short title should ultimately fall back to the effective title."""
    node = create_section_node(
        title_override="Apps",
        short_title_override="",
    )

    assert node.effective_short_title == "Apps"


def test_effective_description_for_structure_without_link_is_empty() -> None:
    """Structural nodes should default to an empty description."""
    node = create_separator_node()

    assert node.effective_description == ""


def test_effective_tooltip_for_structure_without_link_is_empty() -> None:
    """Structural nodes should default to an empty tooltip."""
    node = create_separator_node()

    assert node.effective_tooltip == ""


def test_effective_aria_label_falls_back_to_effective_title() -> None:
    """ARIA labels should fall back to the effective title."""
    node = create_section_node(
        title_override="Applications",
    )

    assert node.effective_aria_label == "Applications"


def test_effective_cta_label_for_structure_without_link_is_empty() -> None:
    """Structural nodes should not expose a CTA label."""
    node = create_separator_node()

    assert node.effective_cta_label == ""


def test_effective_enabled_returns_true_for_structural_nodes() -> None:
    """Structural nodes should always be enabled."""
    node = create_separator_node()

    assert node.effective_enabled is True


def test_effective_enabled_without_link_is_false() -> None:
    """Broken link nodes should fail closed."""
    node = create_link_node()
    node.navigation_link = None

    assert node.effective_enabled is False


def test_effective_disabled_reason_defaults_to_empty() -> None:
    """Nodes without disabled reasons should return an empty string."""
    node = create_section_node()

    assert node.effective_disabled_reason == ""


def test_effective_icon_descriptor_none_override() -> None:
    """Explicit none overrides should suppress inherited icons."""
    link = create_emoji_navigation_link()

    node = create_link_node(
        navigation_link=link,
        icon_type_override=NavigationLink.IconType.NONE,
    )

    assert node.effective_icon_descriptor == {
        "kind": "none",
        "value": "",
    }


def test_effective_icon_descriptor_emoji_override_without_type() -> None:
    """Emoji overrides should work without an explicit override type."""
    link = create_navigation_link()

    node = create_link_node(
        navigation_link=link,
        emoji_override="🚀",
    )

    assert node.effective_icon_descriptor == {
        "kind": "emoji",
        "value": "🚀",
    }


def test_effective_icon_descriptor_without_link_returns_none() -> None:
    """Structural nodes without icons should return a none descriptor."""
    node = create_section_node()

    assert node.effective_icon_descriptor == {
        "kind": "none",
        "value": "",
    }


def test_link_node_without_navigation_link_resolves_to_hash() -> None:
    """Broken link nodes should fail closed."""
    node = create_link_node()
    node.navigation_link = None

    assert node.resolve_url() == "#"


def test_link_node_without_navigation_link_is_never_active() -> None:
    """Broken link nodes should never become active."""
    node = create_link_node()
    node.navigation_link = None

    assert node.is_active_for(None) is False


def test_structural_node_is_never_active() -> None:
    """Structural nodes should never be active."""
    node = create_section_node()

    assert node.is_active_for(None) is False


def test_valid_parent_relationship_passes_validation() -> None:
    """A child may reference a non-separator node in the same launchpad."""
    launchpad = create_launchpad()
    parent = create_section_node(launchpad=launchpad)
    child = create_section_node(
        launchpad=launchpad,
        parent=parent,
    )

    child.full_clean()


def test_feather_icon_override_requires_icon_name() -> None:
    """Feather overrides should require an icon name."""
    node = create_link_node(
        icon_type_override=NavigationLink.IconType.FE,
        icon_class_override="",
    )

    with pytest.raises(ValidationError):
        node.full_clean()


def test_emoji_icon_override_requires_emoji() -> None:
    """Emoji overrides should require an emoji value."""
    node = create_link_node(
        icon_type_override=NavigationLink.IconType.EMOJI,
        emoji_override="",
    )

    with pytest.raises(ValidationError):
        node.full_clean()


def test_disabled_override_accepts_link_disabled_reason() -> None:
    """A linked disabled reason should satisfy placement validation."""
    link = create_navigation_link(
        enabled=False,
        disabled_reason="Unavailable.",
    )
    node = create_link_node(
        navigation_link=link,
        enabled_override=False,
        disabled_reason_override="",
    )

    node.full_clean()


def test_effective_tooltip_uses_override_first() -> None:
    """Placement tooltip should override the linked tooltip."""
    link = create_navigation_link(tooltip="Canonical tooltip")
    node = create_link_node(
        navigation_link=link,
        tooltip_override="Placement tooltip",
    )

    assert node.effective_tooltip == "Placement tooltip"


def test_effective_tooltip_falls_back_to_link() -> None:
    """Blank placement tooltip should use the linked tooltip."""
    link = create_navigation_link(tooltip="Canonical tooltip")
    node = create_link_node(
        navigation_link=link,
        tooltip_override="",
    )

    assert node.effective_tooltip == "Canonical tooltip"


def test_effective_cta_label_uses_override_first() -> None:
    """Placement CTA should override the linked CTA."""
    link = create_navigation_link(cta_label="Open")
    node = create_link_node(
        navigation_link=link,
        cta_label_override="Explore",
    )

    assert node.effective_cta_label == "Explore"


def test_effective_cta_label_falls_back_to_link() -> None:
    """Blank placement CTA should use the linked CTA."""
    link = create_navigation_link(cta_label="Open")
    node = create_link_node(
        navigation_link=link,
        cta_label_override="",
    )

    assert node.effective_cta_label == "Open"


def test_effective_icon_descriptor_fontawesome_override() -> None:
    """FontAwesome overrides should return an FA descriptor."""
    node = create_link_node(
        icon_type_override=NavigationLink.IconType.FA,
        icon_class_override="fa-solid fa-tree",
    )

    assert node.effective_icon_descriptor == {
        "kind": "fa",
        "value": "fa-solid fa-tree",
    }


def test_effective_icon_descriptor_feather_override() -> None:
    """Feather overrides should return an FE descriptor."""
    node = create_link_node(
        icon_type_override=NavigationLink.IconType.FE,
        icon_class_override="navigation",
    )

    assert node.effective_icon_descriptor == {
        "kind": "fe",
        "value": "navigation",
    }


def test_visible_to_delegates_to_visibility_engine() -> None:
    """LaunchpadNode.visible_to should delegate to the visibility engine."""
    user = create_user()
    node = create_section_node(
        audience=LaunchpadNode.Audience.AUTHENTICATED,
    )

    assert node.visible_to(user) is True


def test_effective_short_title_falls_back_to_link_short_title() -> None:
    """Blank placement titles should use the linked compact title."""
    link = create_navigation_link(
        title="Ancestry",
        short_title="Tree",
    )
    node = create_link_node(
        navigation_link=link,
        title_override="",
        short_title_override="",
    )

    assert node.effective_short_title == "Tree"


def test_effective_disabled_reason_falls_back_to_link() -> None:
    """Blank placement reasons should use the linked disabled reason."""
    link = create_navigation_link(
        enabled=False,
        disabled_reason="Unavailable.",
    )
    node = create_link_node(
        navigation_link=link,
        disabled_reason_override="",
    )

    assert node.effective_disabled_reason == "Unavailable."


def test_unsaved_section_passes_tree_validation() -> None:
    """Unsaved root sections should skip persisted-tree checks."""
    node = LaunchpadNode(
        created_by=create_user(),
        launchpad=create_launchpad(),
        kind=LaunchpadNode.Kind.SECTION,
        navigation_link=None,
        title_override="Applications",
    )

    node.full_clean()


def test_saved_separator_without_children_passes_validation() -> None:
    """A saved separator remains valid while it has no children."""
    node = create_separator_node()

    node.full_clean()


def test_valid_ancestor_chain_terminates_without_cycle() -> None:
    """A normal multi-level hierarchy should finish cycle inspection."""
    launchpad = create_launchpad()

    root = create_section_node(
        launchpad=launchpad,
        title_override="Root",
    )
    middle = create_section_node(
        launchpad=launchpad,
        parent=root,
        title_override="Middle",
    )
    child = create_section_node(
        launchpad=launchpad,
        parent=middle,
        title_override="Child",
    )

    child.full_clean()


def test_effective_short_title_for_untitled_structure_is_empty() -> None:
    """Untitled structural nodes should have an empty compact title."""
    node = create_separator_node()

    assert node.effective_short_title == ""


def test_effective_description_uses_link_description() -> None:
    """Blank placement descriptions should use the linked description."""
    link = create_navigation_link(
        description="Canonical description.",
    )
    node = create_link_node(
        navigation_link=link,
        description_override="",
    )

    assert node.effective_description == "Canonical description."


def test_effective_description_without_link_is_empty() -> None:
    """Structural nodes without descriptions should return an empty value."""
    node = create_separator_node()

    assert node.effective_description == ""


def test_effective_aria_label_uses_override() -> None:
    """Placement ARIA labels should override linked values."""
    link = create_navigation_link(
        aria_label="Canonical label",
    )
    node = create_link_node(
        navigation_link=link,
        aria_label_override="Placement label",
    )

    assert node.effective_aria_label == "Placement label"


def test_effective_aria_label_uses_link_label() -> None:
    """Blank placement ARIA labels should use the linked label."""
    link = create_navigation_link(
        title="Ancestry",
        aria_label="Open family tree",
    )
    node = create_link_node(
        navigation_link=link,
        aria_label_override="",
    )

    assert node.effective_aria_label == "Open family tree"


def test_enabled_link_node_without_navigation_link_resolves_to_hash() -> None:
    """An enabled but malformed link node should fail closed."""
    node = create_link_node(
        enabled_override=True,
    )
    node.navigation_link = None

    assert node.resolve_url() == "#"


def test_link_node_without_navigation_link_is_not_active() -> None:
    """A malformed link node should never be active."""
    node = create_link_node()
    node.navigation_link = None

    assert node.is_active_for(object()) is False


def test_link_node_delegates_active_state_to_navigation_link() -> None:
    """Link nodes should delegate active matching to their navigation link."""
    link = create_navigation_link(
        url_type=NavigationLink.URLType.RAW,
        url_value="/ancestry/",
        active_match=NavigationLink.ActiveMatch.PATH_PREFIX,
    )
    node = create_link_node(
        navigation_link=link,
    )
    request = build_request("/ancestry/people/42/")

    assert node.is_active_for(request) is True
