"""
src/launchpad/models/launchpad.py

Launchpad compositions.

A Launchpad is a named tree of LaunchpadNode records.

It is renderer-independent. It does not know whether it will be displayed as:

- a sidebar
- a topbar
- a homepage card grid
- a dropdown
- a footer
- a mobile menu
- a command palette
- an application workspace

Templates decide presentation.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from launchpad.visibility import is_visible

from .base import (
    AccessPolicyModel,
    LaunchpadModel,
    validate_code,
    validate_json_mapping,
)
from .navigation_link import NavigationLink

_ICON_OVERRIDE_CHOICES = (
    ("", _("Use default")),
    *NavigationLink.IconType.choices,
)


class Launchpad(LaunchpadModel):
    """
    Named renderer-independent composition of navigation nodes.

    Examples:

        primary_navigation
        homepage
        account_menu
        ancestry_actions
        mobile_navigation

    The code is the stable identifier used by template tags, fixtures,
    tests, and application code.
    """

    code = models.CharField(
        max_length=80,
        unique=True,
        validators=[validate_code],
        help_text=_("Stable code used by template tags, fixtures, and tests."),
    )

    title = models.CharField(
        max_length=120,
        help_text=_("Human-friendly name."),
    )

    description = models.CharField(
        max_length=255,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_json_mapping],
        help_text=_("Optional renderer-neutral metadata."),
    )

    class Meta:
        ordering = [
            "title",
            "code",
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def root_nodes(self) -> QuerySet[LaunchpadNode]:
        """
        Return this launchpad's root nodes.

        Readers should generally construct launchpad trees explicitly, but
        this property is useful for administration, inspection, and debugging.
        """
        return self.nodes.filter(parent__isnull=True)


class LaunchpadNode(AccessPolicyModel):
    """
    A node within a Launchpad tree.

    A node may be:

    - LINK:
        A placement of a NavigationLink.

    - SECTION:
        A structural grouping node.

    - SEPARATOR:
        A structural divider.

    The same NavigationLink may be placed in multiple launchpads. Each
    placement may define different ordering, parentage, presentation
    overrides, and visibility rules.
    """

    class Kind(models.TextChoices):
        LINK = "link", _("Link")
        SECTION = "section", _("Section")
        SEPARATOR = "separator", _("Separator")

    launchpad = models.ForeignKey(
        Launchpad,
        on_delete=models.CASCADE,
        related_name="nodes",
    )

    code = models.CharField(
        max_length=80,
        blank=True,
        validators=[validate_code],
        help_text=_(
            "Optional stable code for this placement. Unique within a "
            "launchpad when provided."
        ),
    )

    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.LINK,
    )

    navigation_link = models.ForeignKey(
        NavigationLink,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="placements",
        help_text=_("Required for link nodes. Empty for sections and separators."),
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="children",
        help_text=_(
            "Optional parent node. The parent must belong to the same launchpad."
        ),
    )

    sort_order = models.PositiveIntegerField(
        default=1000,
        help_text=_(
            "Lower values render first among sibling nodes. Use gaps such "
            "as 1000, 2000, and 3000 to make later reordering easier."
        ),
    )

    title_override = models.CharField(
        max_length=120,
        blank=True,
        help_text=_(
            "Optional placement-specific title. For sections, this is the "
            "section label."
        ),
    )

    short_title_override = models.CharField(
        max_length=60,
        blank=True,
    )

    description_override = models.CharField(
        max_length=255,
        blank=True,
    )

    tooltip_override = models.CharField(
        max_length=255,
        blank=True,
    )

    aria_label_override = models.CharField(
        max_length=255,
        blank=True,
    )

    cta_label_override = models.CharField(
        max_length=60,
        blank=True,
    )

    icon_type_override = models.CharField(
        max_length=10,
        choices=_ICON_OVERRIDE_CHOICES,
        blank=True,
        default="",
        help_text=_("Optional placement-specific icon type."),
    )

    icon_class_override = models.CharField(
        max_length=120,
        blank=True,
        help_text=_("Optional placement-specific FontAwesome class or Feather name."),
    )

    emoji_override = models.CharField(
        max_length=16,
        blank=True,
        help_text=_("Optional placement-specific emoji."),
    )

    enabled_override = models.BooleanField(
        null=True,
        blank=True,
        help_text=_(
            "Optional placement-specific enabled state. Blank uses the "
            "NavigationLink default."
        ),
    )

    disabled_reason_override = models.CharField(
        max_length=255,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_json_mapping],
        help_text=_("Optional renderer-neutral placement metadata."),
    )

    class Meta:
        ordering = [
            "launchpad_id",
            "parent_id",
            "sort_order",
            "pk",
        ]

        indexes = [
            models.Index(fields=["launchpad", "parent", "sort_order"]),
            models.Index(fields=["launchpad", "kind"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["launchpad", "code"],
                condition=~Q(code=""),
                name="launchpad_unique_node_code_per_launchpad",
            ),
            models.CheckConstraint(
                name="launchpad_link_nodes_require_link",
                condition=(
                    Q(kind="link", navigation_link__isnull=False)
                    | Q(kind="section", navigation_link__isnull=True)
                    | Q(kind="separator", navigation_link__isnull=True)
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.launchpad.code}: {self.effective_title}"

    def clean(self) -> None:  # noqa: C901, PLR0912
        """Validate LaunchpadNode tree and override rules."""
        super().clean()

        if self.kind == self.Kind.LINK and self.navigation_link_id is None:
            raise ValidationError(
                {
                    "navigation_link": _("Link nodes require a NavigationLink."),
                },
            )

        if self.kind != self.Kind.LINK and self.navigation_link_id is not None:
            raise ValidationError(
                {
                    "navigation_link": _(
                        "Only link nodes may reference a NavigationLink."
                    ),
                },
            )

        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError(
                {
                    "parent": _("A node cannot be its own parent."),
                },
            )

        if self.parent_id:
            parent = self.parent
            assert parent is not None

            if parent.launchpad_id != self.launchpad_id:
                raise ValidationError(
                    {
                        "parent": _(
                            "The parent node must belong to the same launchpad."
                        ),
                    },
                )

            if parent.kind == self.Kind.SEPARATOR:
                raise ValidationError(
                    {
                        "parent": _("Separator nodes cannot have children."),
                    },
                )

        if self.kind == self.Kind.SEPARATOR and self.pk:
            if self.children.exists():
                raise ValidationError(
                    {
                        "kind": _("Separator nodes cannot have children."),
                    },
                )

        if self.pk:
            ancestor = self.parent

            while ancestor is not None:
                if ancestor.pk == self.pk:
                    raise ValidationError(
                        {
                            "parent": _(
                                "Launchpad node hierarchies cannot contain cycles."
                            ),
                        },
                    )

                ancestor = ancestor.parent

        if (
            self.icon_type_override == NavigationLink.IconType.FA
            and not self.icon_class_override
        ):
            raise ValidationError(
                {
                    "icon_class_override": _(
                        "FontAwesome icon overrides require an icon class."
                    ),
                },
            )

        if (
            self.icon_type_override == NavigationLink.IconType.FE
            and not self.icon_class_override
        ):
            raise ValidationError(
                {
                    "icon_class_override": _(
                        "Feather icon overrides require an icon name."
                    ),
                },
            )

        if (
            self.icon_type_override == NavigationLink.IconType.EMOJI
            and not self.emoji_override
        ):
            raise ValidationError(
                {
                    "emoji_override": _("Emoji icon overrides require an emoji value."),
                },
            )

        if (
            self.enabled_override is False
            and not self.disabled_reason_override
            and not (self.navigation_link and self.navigation_link.disabled_reason)
        ):
            raise ValidationError(
                {
                    "disabled_reason_override": _(
                        "Disabled placements should explain why they are disabled."
                    ),
                },
            )

    @property
    def effective_code(self) -> str:
        """Return the placement code, linked code, or generated fallback."""
        if self.code:
            return self.code

        if self.navigation_link:
            return self.navigation_link.code

        if self.pk:
            return f"{self.kind}-{self.pk}"

        return self.kind

    @property
    def effective_title(self) -> str:
        """Return the title used to render this node."""
        if self.title_override:
            return self.title_override

        if self.navigation_link:
            return self.navigation_link.display_title

        return ""

    @property
    def effective_short_title(self) -> str:
        """Return the compact title used to render this node."""
        if self.short_title_override:
            return self.short_title_override

        if self.title_override:
            return self.title_override

        if self.navigation_link:
            return self.navigation_link.display_short_title

        return self.effective_title

    @property
    def effective_description(self) -> str:
        """Return the description used to render this node."""
        if self.description_override:
            return self.description_override

        if self.navigation_link:
            return self.navigation_link.description

        return ""

    @property
    def effective_tooltip(self) -> str:
        """Return the tooltip used to render this node."""
        if self.tooltip_override:
            return self.tooltip_override

        if self.navigation_link:
            return self.navigation_link.tooltip

        return ""

    @property
    def effective_aria_label(self) -> str:
        """Return the accessibility label used to render this node."""
        if self.aria_label_override:
            return self.aria_label_override

        if self.navigation_link:
            return self.navigation_link.display_aria_label

        return self.effective_title

    @property
    def effective_cta_label(self) -> str:
        """Return the call-to-action label used by card-style renderers."""
        if self.cta_label_override:
            return self.cta_label_override

        if self.navigation_link:
            return self.navigation_link.cta_label

        return ""

    @property
    def effective_enabled(self) -> bool:
        """Return whether this node should render as enabled."""
        if self.kind != self.Kind.LINK:
            return True

        if self.enabled_override is not None:
            return self.enabled_override

        if self.navigation_link:
            return self.navigation_link.enabled

        return False

    @property
    def effective_disabled_reason(self) -> str:
        """Return the effective disabled explanation for this node."""
        if self.disabled_reason_override:
            return self.disabled_reason_override

        if self.navigation_link:
            return self.navigation_link.disabled_reason

        return ""

    @property
    def effective_icon_descriptor(self) -> dict[str, str]:  # noqa: PLR0911
        """
        Return a renderer-neutral icon descriptor for this placement.

        Node-level icon overrides take precedence over NavigationLink defaults.
        """
        if self.icon_type_override == NavigationLink.IconType.EMOJI:
            return {
                "kind": "emoji",
                "value": self.emoji_override,
            }

        if self.icon_type_override == NavigationLink.IconType.FA:
            return {
                "kind": "fa",
                "value": self.icon_class_override,
            }

        if self.icon_type_override == NavigationLink.IconType.FE:
            return {
                "kind": "fe",
                "value": self.icon_class_override,
            }

        if self.icon_type_override == NavigationLink.IconType.NONE:
            return {
                "kind": "none",
                "value": "",
            }

        if self.emoji_override:
            return {
                "kind": "emoji",
                "value": self.emoji_override,
            }

        if self.navigation_link:
            return self.navigation_link.icon_descriptor

        return {
            "kind": "none",
            "value": "",
        }

    def resolve_url(
        self,
        *,
        request: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Resolve the node's URL.

        Non-link nodes and disabled links resolve to ``#``.
        """
        if self.kind != self.Kind.LINK:
            return "#"

        if not self.effective_enabled:
            return "#"

        if not self.navigation_link:
            return "#"

        return self.navigation_link.resolve_url(
            request=request,
            context=context,
        )

    def is_active_for(
        self,
        request: Any | None,
        *,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Return whether this node should be active for a request."""
        if self.kind != self.Kind.LINK:
            return False

        if not self.navigation_link:
            return False

        return self.navigation_link.is_active_for(
            request,
            context=context,
        )

    def visible_to(
        self,
        user: Any,
        *,
        request: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Return whether this node is visible to a user."""
        return is_visible(
            self,
            user=user,
            request=request,
            context=context,
        )
