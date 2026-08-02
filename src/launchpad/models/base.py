"""
src/launchpad/models/base.py

Shared model helpers for the Launchpad application.

Launchpad models separate three concerns:

- NavigationLink:
    A canonical navigation destination.

- Launchpad:
    A named collection of navigation nodes.

- LaunchpadNode:
    A placement of a link, section, or separator inside a Launchpad.

This module contains shared validators, lifecycle fields, and access-policy
fields used by Launchpad models.
"""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

_CODE_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


def validate_code(value: str) -> None:
    """
    Validate a stable Launchpad code.

    Codes are intentionally simple because templates, fixtures, tests, and
    application code may reference them directly.

    Valid examples:

        primary_navigation
        homepage
        account_menu
        ancestry_actions
        beancount_reports

    Invalid examples:

        PrimaryNavigation
        primary navigation
        primary.navigation
        primary/navigation
    """
    if not value:
        raise ValidationError(_("Code is required."))

    if not _CODE_RE.fullmatch(value):
        raise ValidationError(
            _(
                "%(value)s must start with a lowercase letter and contain "
                "only lowercase letters, numbers, underscores, or hyphens."
            ),
            params={"value": value},
        )


def validate_string_list(value: Any) -> None:
    """Validate a JSON value that must be a list of strings."""
    if not isinstance(value, list):
        raise ValidationError(_("Value must be a list."))

    for item in value:
        if not isinstance(item, str):
            raise ValidationError(_("All items must be strings."))


def _is_json_scalar(value: Any) -> bool:
    """Return whether a value is a supported JSON scalar."""
    return value is None or isinstance(value, str | int | float | bool)


def validate_json_args(value: Any) -> None:
    """
    Validate URL positional arguments.

    The value must be a list containing only JSON scalar values.
    """
    if not isinstance(value, list):
        raise ValidationError(_("URL args must be a list."))

    for item in value:
        if not _is_json_scalar(item):
            raise ValidationError(
                _("URL args may only contain JSON scalar values."),
            )


def validate_json_mapping(value: Any) -> None:
    """
    Validate a JSON object containing scalars or lists of scalars.

    This validator is used for URL keyword arguments, query parameters,
    metadata, and other simple JSON mappings.
    """
    if not isinstance(value, dict):
        raise ValidationError(_("Value must be an object."))

    for key, item in value.items():
        if not isinstance(key, str):
            raise ValidationError(_("All object keys must be strings."))

        if isinstance(item, list):
            for list_item in item:
                if not _is_json_scalar(list_item):
                    raise ValidationError(
                        _("List values may only contain JSON scalar values."),
                    )
            continue

        if not _is_json_scalar(item):
            raise ValidationError(
                _("Object values may only be JSON scalars or scalar lists."),
            )


class LaunchpadModel(models.Model):
    """
    Abstract base model for persistent Launchpad objects.

    The model provides common ownership, activation, and timestamp fields
    without depending on infrastructure from the consuming Django project.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_created",
        help_text=_("User who originally created this object."),
    )

    active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Inactive objects are excluded from normal use."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        abstract = True


class AccessPolicyModel(LaunchpadModel):
    """
    Abstract access policy for user-aware Launchpad objects.

    This model controls visibility only.

    It does not replace authorization in destination views. Destination views
    must still enforce their own permissions. Launchpad only determines whether
    a navigation object should be shown to a user.
    """

    class Audience(models.TextChoices):
        PUBLIC = "public", _("Public")
        AUTHENTICATED = "authenticated", _("Authenticated")
        STAFF = "staff", _("Staff")
        SUPERUSER = "superuser", _("Superuser")
        PRIVATE = "private", _("Private")

    class PermissionMode(models.TextChoices):
        ALL = "all", _("Require all permissions")
        ANY = "any", _("Require any permission")

    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.AUTHENTICATED,
        help_text=_(
            "Base audience for this object. More specific users, groups, "
            "and permissions may further restrict visibility."
        ),
    )

    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="%(app_label)s_%(class)s_visible_items",
        help_text=_(
            "Optional explicit users who may see this object. "
            "Permission gates still apply."
        ),
    )

    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="%(app_label)s_%(class)s_visible_items",
        help_text=_(
            "Optional groups whose members may see this object. "
            "Permission gates still apply."
        ),
    )

    permissions_required = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_string_list],
        help_text=_(
            "Optional list of Django permission strings, for example "
            "['ancestry.view_person']."
        ),
    )

    permissions_mode = models.CharField(
        max_length=10,
        choices=PermissionMode.choices,
        default=PermissionMode.ALL,
        help_text=_(
            "Whether all listed permissions are required or any one of them "
            "is sufficient."
        ),
    )

    visible_from = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Optional start time for visibility."),
    )

    visible_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Optional end time for visibility."),
    )

    visibility_rule = models.CharField(
        max_length=80,
        blank=True,
        validators=[validate_code],
        help_text=_(
            "Optional registered runtime visibility rule. Blank means no "
            "additional runtime rule. This is a safe code, not a Python path."
        ),
    )

    class Meta:
        abstract = True

    def clean(self) -> None:
        """Validate shared access-policy fields."""
        super().clean()

        if (
            self.visible_from
            and self.visible_until
            and self.visible_from > self.visible_until
        ):
            raise ValidationError(
                {
                    "visible_until": _("Visible-until must be after visible-from."),
                },
            )

    def is_available_now(self) -> bool:
        """Return whether the current time is within the visibility window."""
        now = timezone.now()

        if self.visible_from and now < self.visible_from:
            return False

        return not (self.visible_until and now > self.visible_until)
