"""
src/launchpad/admin/navigation_link.py

Admin configuration for canonical Launchpad navigation links.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias, cast

from django.contrib import admin

from launchpad.models import NavigationLink

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

    NavigationLinkAdminBase: TypeAlias = admin.ModelAdmin[NavigationLink]
else:
    NavigationLinkAdminBase = admin.ModelAdmin


@admin.register(NavigationLink)
class NavigationLinkAdmin(NavigationLinkAdminBase):
    """Admin configuration for reusable navigation destinations."""

    list_display = (
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

    list_filter = (
        "active",
        "enabled",
        "audience",
        "url_type",
        "icon_type",
        "target",
        "permissions_mode",
    )

    search_fields = (
        "code",
        "title",
        "short_title",
        "description",
        "url_value",
        "search_aliases",
    )

    autocomplete_fields = (
        "users",
        "groups",
    )

    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
        "parsable_url",
        "url",
    )

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "created_by",
                    "code",
                    "title",
                    "short_title",
                    "description",
                    "tooltip",
                    "aria_label",
                    "cta_label",
                ),
            },
        ),
        (
            "Destination",
            {
                "fields": (
                    "url_type",
                    "url_value",
                    "url_args",
                    "url_kwargs",
                    "query_params",
                    "fragment",
                    "parsable_url",
                    "url",
                    "target",
                    "rel",
                    "download",
                ),
            },
        ),
        (
            "Icon",
            {
                "fields": (
                    "icon_type",
                    "icon_class",
                    "emoji",
                ),
            },
        ),
        (
            "State",
            {
                "fields": (
                    "active",
                    "enabled",
                    "disabled_reason",
                ),
            },
        ),
        (
            "Active Matching",
            {
                "classes": ("collapse",),
                "fields": (
                    "active_match",
                    "active_path",
                    "active_view_name",
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
            "Search / Metadata",
            {
                "classes": ("collapse",),
                "fields": (
                    "search_aliases",
                    "metadata",
                ),
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
    ) -> QuerySet[NavigationLink]:
        """Return an optimized queryset for the changelist."""
        return (
            super()
            .get_queryset(request)
            .select_related("created_by")
            .prefetch_related("users", "groups")
        )

    def save_model(
        self,
        request: HttpRequest,
        obj: NavigationLink,
        form: Any,
        change: bool,  # noqa: FBT001
    ) -> None:
        """Set the creating user when the link is first saved."""
        if not change and obj.created_by_id is None:
            obj.created_by = cast("Any", request.user)

        super().save_model(
            request,
            obj,
            form,
            change,
        )
