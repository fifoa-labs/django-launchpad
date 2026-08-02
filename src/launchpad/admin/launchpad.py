"""
src/launchpad/admin/launchpad.py

Admin configuration for Launchpad compositions and node placements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias, cast

from django.contrib import admin

from launchpad.models import Launchpad, LaunchpadNode

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

    LaunchpadNodeInlineBase: TypeAlias = admin.TabularInline[
        LaunchpadNode,
        Launchpad,
    ]
    LaunchpadAdminBase: TypeAlias = admin.ModelAdmin[Launchpad]
    LaunchpadNodeAdminBase: TypeAlias = admin.ModelAdmin[LaunchpadNode]
else:
    LaunchpadNodeInlineBase = admin.TabularInline
    LaunchpadAdminBase = admin.ModelAdmin
    LaunchpadNodeAdminBase = admin.ModelAdmin


class LaunchpadNodeInline(LaunchpadNodeInlineBase):
    """Inline editor for nodes contained in a Launchpad."""

    model = LaunchpadNode
    extra = 0

    fields = (
        "kind",
        "navigation_link",
        "parent",
        "code",
        "title_override",
        "sort_order",
        "audience",
        "active",
    )

    autocomplete_fields = (
        "navigation_link",
        "parent",
    )

    readonly_fields = ("created_by",)

    show_change_link = True


@admin.register(Launchpad)
class LaunchpadAdmin(LaunchpadAdminBase):
    """Admin configuration for renderer-independent Launchpad compositions."""

    list_display = (
        "title",
        "code",
        "active",
        "created_by",
        "updated_at",
    )

    list_filter = ("active",)

    search_fields = (
        "code",
        "title",
        "description",
    )

    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "created_by",
                    "code",
                    "title",
                    "description",
                    "active",
                ),
            },
        ),
        (
            "Metadata",
            {
                "classes": ("collapse",),
                "fields": ("metadata",),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    inlines = [
        LaunchpadNodeInline,
    ]

    def get_queryset(
        self,
        request: HttpRequest,
    ) -> QuerySet[Launchpad]:
        """Return an optimized queryset for the changelist."""
        return super().get_queryset(request).select_related("created_by")

    def save_model(
        self,
        request: HttpRequest,
        obj: Launchpad,
        form: Any,
        change: bool,  # noqa: FBT001
    ) -> None:
        """Set the creating user when the object is first saved."""
        if not change and obj.created_by_id is None:
            obj.created_by = cast("Any", request.user)

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    def save_formset(
        self,
        request: HttpRequest,
        form: Any,
        formset: Any,
        change: bool,  # noqa: FBT001
    ) -> None:
        """Set the creating user on newly created inline nodes."""
        instances = formset.save(commit=False)

        for obj in instances:
            if isinstance(obj, LaunchpadNode) and obj.created_by_id is None:
                obj.created_by = cast("Any", request.user)

            obj.save()

        for obj in formset.deleted_objects:
            obj.delete()

        formset.save_m2m()


@admin.register(LaunchpadNode)
class LaunchpadNodeAdmin(LaunchpadNodeAdminBase):
    """
    Admin configuration for individual Launchpad node placements.

    This interface supports inspecting and editing larger Launchpad trees
    outside the inline Launchpad editor.
    """

    list_display = (
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

    list_filter = (
        "active",
        "kind",
        "audience",
        "launchpad",
        "permissions_mode",
    )

    search_fields = (
        "code",
        "title_override",
        "short_title_override",
        "description_override",
        "navigation_link__code",
        "navigation_link__title",
        "launchpad__code",
        "launchpad__title",
    )

    autocomplete_fields = (
        "launchpad",
        "navigation_link",
        "parent",
        "users",
        "groups",
    )

    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
        "effective_code",
        "effective_title",
        "effective_short_title",
        "effective_description",
        "effective_tooltip",
        "effective_aria_label",
        "effective_cta_label",
        "effective_enabled",
        "effective_disabled_reason",
        "effective_icon_descriptor",
    )

    fieldsets = (
        (
            "Placement",
            {
                "fields": (
                    "created_by",
                    "launchpad",
                    "kind",
                    "navigation_link",
                    "parent",
                    "code",
                    "sort_order",
                    "active",
                ),
            },
        ),
        (
            "Display Overrides",
            {
                "fields": (
                    "title_override",
                    "short_title_override",
                    "description_override",
                    "tooltip_override",
                    "aria_label_override",
                    "cta_label_override",
                ),
            },
        ),
        (
            "Icon Override",
            {
                "fields": (
                    "icon_type_override",
                    "icon_class_override",
                    "emoji_override",
                ),
            },
        ),
        (
            "Enabled Override",
            {
                "fields": (
                    "enabled_override",
                    "disabled_reason_override",
                ),
            },
        ),
        (
            "Visibility",
            {
                "fields": (
                    "audience",
                    "users",
                    "groups",
                    "permissions_required",
                    "permissions_mode",
                    "visible_from",
                    "visible_until",
                    "visibility_rule",
                ),
            },
        ),
        (
            "Resolved Values",
            {
                "classes": ("collapse",),
                "fields": (
                    "effective_code",
                    "effective_title",
                    "effective_short_title",
                    "effective_description",
                    "effective_tooltip",
                    "effective_aria_label",
                    "effective_cta_label",
                    "effective_enabled",
                    "effective_disabled_reason",
                    "effective_icon_descriptor",
                ),
            },
        ),
        (
            "Metadata",
            {
                "classes": ("collapse",),
                "fields": ("metadata",),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_queryset(
        self,
        request: HttpRequest,
    ) -> QuerySet[LaunchpadNode]:
        """Return an optimized queryset for the changelist."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "created_by",
                "launchpad",
                "navigation_link",
                "parent",
            )
            .prefetch_related(
                "users",
                "groups",
            )
        )

    def save_model(
        self,
        request: HttpRequest,
        obj: LaunchpadNode,
        form: Any,
        change: bool,  # noqa: FBT001
    ) -> None:
        """Set the creating user when the node is first saved."""
        if not change and obj.created_by_id is None:
            obj.created_by = cast("Any", request.user)

        super().save_model(
            request,
            obj,
            form,
            change,
        )
