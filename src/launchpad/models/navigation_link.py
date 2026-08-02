"""
src/launchpad/models/navigation_link.py

Canonical navigation links.

A NavigationLink represents a real destination such as:

    Ancestry       -> ancestry:index
    My Profile     -> users:detail
    Django Admin   -> admin:index
    Documentation  -> https://example.com/docs/

It is intentionally renderer-independent.

It does not know whether it will appear in a sidebar, topbar, dashboard,
card grid, footer, dropdown menu, mobile menu, or command palette.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _

from launchpad.visibility import is_visible

from .base import (
    AccessPolicyModel,
    validate_code,
    validate_json_args,
    validate_json_mapping,
    validate_string_list,
)

_CONTEXT_PREFIX = "@"

_ALLOWED_RAW_URL_SCHEMES = {
    "http",
    "https",
    "mailto",
    "tel",
}


def _contains_context_reference(value: Any) -> bool:
    """
    Return whether a JSON-like value contains a context reference.

    Context references look like:

        @user.username
        @request.resolver_match.view_name
        @context.person.pk
    """
    if isinstance(value, str):
        return value.startswith(_CONTEXT_PREFIX)

    if isinstance(value, list):
        return any(_contains_context_reference(item) for item in value)

    if isinstance(value, dict):
        return any(_contains_context_reference(item) for item in value.values())

    return False


def _resolve_attr_chain(value: Any, parts: list[str]) -> Any:
    """
    Resolve a dotted attribute or dictionary-key chain.

    Missing attributes resolve to an empty string. Callables are not invoked.
    """
    current = value

    for part in parts:
        if current is None:
            return ""

        if isinstance(current, dict):
            current = current.get(part, "")
            continue

        current = getattr(current, part, "")

    return current


def _resolve_context_reference(
    reference: str,
    *,
    request: Any | None = None,
    context: dict[str, Any] | None = None,
) -> Any:
    """
    Resolve a context reference.

    Supported roots:

        @user
        @request
        @context
    """
    expression = reference.removeprefix(_CONTEXT_PREFIX)
    parts = expression.split(".")

    root = parts[0]
    tail = parts[1:]

    if root == "user":
        return _resolve_attr_chain(
            getattr(request, "user", None),
            tail,
        )

    if root == "request":
        return _resolve_attr_chain(
            request,
            tail,
        )

    if root == "context":
        return _resolve_attr_chain(
            context or {},
            tail,
        )

    return ""


def _resolve_json_value(
    value: Any,
    *,
    request: Any | None = None,
    context: dict[str, Any] | None = None,
) -> Any:
    """Resolve context references within a JSON-like value."""
    if isinstance(value, str) and value.startswith(_CONTEXT_PREFIX):
        return _resolve_context_reference(
            value,
            request=request,
            context=context,
        )

    if isinstance(value, list):
        return [
            _resolve_json_value(
                item,
                request=request,
                context=context,
            )
            for item in value
        ]

    if isinstance(value, dict):
        return {
            key: _resolve_json_value(
                item,
                request=request,
                context=context,
            )
            for key, item in value.items()
        }

    return value


def _append_query_and_fragment(
    base_url: str,
    *,
    query_params: dict[str, Any],
    fragment: str = "",
) -> str:
    """
    Append query parameters and an optional fragment to a URL.

    Existing query parameters are preserved.
    """
    split = urlsplit(base_url)

    existing_params = parse_qsl(
        split.query,
        keep_blank_values=True,
    )

    new_params: list[tuple[str, Any]] = []

    for key, value in query_params.items():
        if value is None:
            continue

        if isinstance(value, list):
            new_params.extend((key, item) for item in value if item is not None)
            continue

        new_params.append((key, value))

    query = urlencode(
        [
            *existing_params,
            *new_params,
        ],
        doseq=True,
    )

    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            query,
            fragment or split.fragment,
        ),
    )


def validate_raw_url(value: str) -> None:
    """
    Validate a raw URL.

    Raw URLs may be:

    - relative paths
    - absolute HTTP or HTTPS URLs
    - mailto links
    - telephone links

    Unsafe values are rejected.
    """
    if not value:
        raise ValidationError(
            _("Raw URL is required."),
        )

    if value != value.strip():
        raise ValidationError(
            _("Raw URL may not contain surrounding spaces."),
        )

    lowered = value.lower()

    if value == "#":
        raise ValidationError(
            _("Use enabled=False for disabled links instead of '#'."),
        )

    if lowered.startswith(("javascript:", "data:", "vbscript:")):
        raise ValidationError(
            _("Unsafe URL scheme."),
        )

    if value.startswith("//"):
        raise ValidationError(
            _("Protocol-relative URLs are not allowed."),
        )

    split = urlsplit(value)

    if split.scheme and split.scheme not in _ALLOWED_RAW_URL_SCHEMES:
        raise ValidationError(
            _("URL scheme '%(scheme)s' is not allowed."),
            params={"scheme": split.scheme},
        )


class NavigationLink(AccessPolicyModel):
    """
    Canonical navigation destination.

    A NavigationLink does not decide where it renders. It may be placed into
    one or many Launchpads through LaunchpadNode records.

    Example:

        code: ancestry
        title: Ancestry
        url_type: named
        url_value: ancestry:index
    """

    class URLType(models.TextChoices):
        NAMED = "named", _("Named Django URL")
        RAW = "raw", _("Raw URL")

    class IconType(models.TextChoices):
        NONE = "none", _("None")
        FA = "fa", _("FontAwesome")
        FE = "fe", _("Feather")
        EMOJI = "emoji", _("Emoji")

    class Target(models.TextChoices):
        SELF = "_self", _("Same tab")
        BLANK = "_blank", _("New tab")

    class ActiveMatch(models.TextChoices):
        AUTO = "auto", _("Automatic")
        NONE = "none", _("Never active")
        EXACT_PATH = "exact_path", _("Exact path")
        PATH_PREFIX = "path_prefix", _("Path prefix")
        VIEW_NAME = "view_name", _("View name")
        VIEW_PREFIX = "view_prefix", _("View name prefix")

    code = models.CharField(
        max_length=80,
        unique=True,
        validators=[validate_code],
        help_text=_(
            "Stable unique code used by fixtures, tests, and application "
            "logic. Do not change casually."
        ),
    )

    title = models.CharField(
        max_length=100,
        help_text=_("Primary display label."),
    )

    short_title = models.CharField(
        max_length=60,
        blank=True,
        help_text=_("Optional compact label for tight renderers."),
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Optional longer description."),
    )

    tooltip = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Optional tooltip text."),
    )

    aria_label = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Optional accessibility label."),
    )

    cta_label = models.CharField(
        max_length=60,
        blank=True,
        help_text=_("Optional call-to-action label for card-style renderers."),
    )

    url_type = models.CharField(
        max_length=10,
        choices=URLType.choices,
        default=URLType.NAMED,
    )

    url_value = models.CharField(
        max_length=255,
        help_text=_(
            "Django URL name when url_type=named, or raw URL when url_type=raw."
        ),
    )

    url_args = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_json_args],
        help_text=_(
            "Optional positional arguments for named URLs. Values may "
            "contain context references such as '@user.username'."
        ),
    )

    url_kwargs = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_json_mapping],
        help_text=_(
            "Optional keyword arguments for named URLs. Values may "
            "contain context references such as '@context.person.pk'."
        ),
    )

    query_params = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_json_mapping],
        help_text=_("Optional query parameters appended after URL resolution."),
    )

    fragment = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Optional URL fragment without '#'."),
    )

    target = models.CharField(
        max_length=10,
        choices=Target.choices,
        default=Target.SELF,
    )

    rel = models.CharField(
        max_length=120,
        blank=True,
        help_text=_(
            "Optional rel attribute. New-tab links default to "
            "'noopener noreferrer' when blank."
        ),
    )

    download = models.BooleanField(
        default=False,
        help_text=_("Whether renderers should mark this link as a download."),
    )

    icon_type = models.CharField(
        max_length=10,
        choices=IconType.choices,
        default=IconType.NONE,
    )

    icon_class = models.CharField(
        max_length=120,
        blank=True,
        help_text=_("FontAwesome class or Feather icon name, depending on icon_type."),
    )

    emoji = models.CharField(
        max_length=16,
        blank=True,
        help_text=_("Optional emoji icon."),
    )

    enabled = models.BooleanField(
        default=True,
        help_text=_("Disabled links may still render, but should not navigate."),
    )

    disabled_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Optional explanation shown when enabled is false."),
    )

    active_match = models.CharField(
        max_length=20,
        choices=ActiveMatch.choices,
        default=ActiveMatch.AUTO,
        help_text=_("How this link should be marked active."),
    )

    active_path = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Optional path used for exact-path or path-prefix matching."),
    )

    active_view_name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Optional view name used for view-based active matching."),
    )

    search_aliases = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_string_list],
        help_text=_("Optional aliases for search or command-palette integrations."),
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

        indexes = [
            models.Index(fields=["audience"]),
            models.Index(fields=["url_type", "url_value"]),
        ]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        """Validate destination, icon, and enabled-state configuration."""
        super().clean()

        if self.url_type == self.URLType.RAW:
            validate_raw_url(self.url_value)

        if self.url_type == self.URLType.NAMED and not self.url_value:
            raise ValidationError(
                {
                    "url_value": _("Named URL value is required."),
                },
            )

        if (
            self.url_type == self.URLType.NAMED
            and not _contains_context_reference(self.url_args)
            and not _contains_context_reference(self.url_kwargs)
        ):
            try:
                reverse(
                    self.url_value,
                    args=self.url_args,
                    kwargs=self.url_kwargs,
                )
            except NoReverseMatch as exc:
                raise ValidationError(
                    {
                        "url_value": _(
                            "Named URL could not be reversed with the "
                            "configured arguments."
                        ),
                    },
                ) from exc

        if self.icon_type == self.IconType.FA and not self.icon_class:
            raise ValidationError(
                {
                    "icon_class": _("FontAwesome links require an icon class."),
                },
            )

        if self.icon_type == self.IconType.FE and not self.icon_class:
            raise ValidationError(
                {
                    "icon_class": _("Feather links require an icon name."),
                },
            )

        if self.icon_type == self.IconType.EMOJI and not self.emoji:
            raise ValidationError(
                {
                    "emoji": _("Emoji links require an emoji."),
                },
            )

        if not self.enabled and not self.disabled_reason:
            raise ValidationError(
                {
                    "disabled_reason": _(
                        "Disabled links should explain why they are disabled."
                    ),
                },
            )

    @property
    def display_title(self) -> str:
        """Return the normal display title."""
        return self.title

    @property
    def display_short_title(self) -> str:
        """Return the compact display title."""
        return self.short_title or self.title

    @property
    def display_aria_label(self) -> str:
        """Return the effective accessibility label."""
        return self.aria_label or self.title

    @property
    def effective_rel(self) -> str:
        """Return the effective rel attribute."""
        if self.rel:
            return self.rel

        if self.target == self.Target.BLANK:
            return "noopener noreferrer"

        return ""

    @property
    def icon_descriptor(self) -> dict[str, str]:
        """
        Return a renderer-neutral icon descriptor.

        No HTML is generated by the model.
        """
        if self.icon_type == self.IconType.EMOJI:
            return {
                "kind": "emoji",
                "value": self.emoji,
            }

        if self.icon_type == self.IconType.FA:
            return {
                "kind": "fa",
                "value": self.icon_class,
            }

        if self.icon_type == self.IconType.FE:
            return {
                "kind": "fe",
                "value": self.icon_class,
            }

        if self.emoji:
            return {
                "kind": "emoji",
                "value": self.emoji,
            }

        return {
            "kind": "none",
            "value": "",
        }

    @property
    def parsable_url(self) -> bool:
        """
        Return whether the configured URL appears resolvable.

        Context-aware named URLs are considered parsable because they cannot
        be fully resolved without a request or runtime context.
        """
        if self.url_type == self.URLType.RAW:
            try:
                validate_raw_url(self.url_value)
            except ValidationError:
                return False

            return True

        if self.url_type != self.URLType.NAMED:
            return False

        if _contains_context_reference(self.url_args) or _contains_context_reference(
            self.url_kwargs
        ):
            return True

        try:
            reverse(
                self.url_value,
                args=self.url_args,
                kwargs=self.url_kwargs,
            )
        except NoReverseMatch:
            return False

        return True

    @property
    def url(self) -> str:
        """
        Resolve the URL without request or template context.

        Context references resolve to empty strings in this mode.
        """
        return self.resolve_url()

    def resolve_url(
        self,
        *,
        request: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Resolve this navigation link to a concrete URL.

        Invalid and disabled URLs fail closed to ``#``.
        """
        if not self.enabled:
            return "#"

        if self.url_type == self.URLType.RAW:
            try:
                validate_raw_url(self.url_value)
            except ValidationError:
                return "#"

            base_url = self.url_value

        elif self.url_type == self.URLType.NAMED:
            resolved_args = _resolve_json_value(
                self.url_args,
                request=request,
                context=context,
            )

            resolved_kwargs = _resolve_json_value(
                self.url_kwargs,
                request=request,
                context=context,
            )

            try:
                base_url = reverse(
                    self.url_value,
                    args=resolved_args,
                    kwargs=resolved_kwargs,
                )
            except NoReverseMatch:
                return "#"

        else:
            return "#"

        resolved_query_params = _resolve_json_value(
            self.query_params,
            request=request,
            context=context,
        )

        return _append_query_and_fragment(
            base_url,
            query_params=resolved_query_params,
            fragment=self.fragment,
        )

    def _active_path_target(
        self,
        *,
        request: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Return the path target used for path-based active matching."""
        if self.active_path:
            return self.active_path

        resolved_url = self.resolve_url(
            request=request,
            context=context,
        )

        return urlsplit(resolved_url).path

    def _query_params_match(
        self,
        *,
        request: Any,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """
        Return whether configured query parameters match the request.

        When no query parameters are configured, this always returns True.
        """
        if not self.query_params:
            return True

        request_get = getattr(request, "GET", None)

        if request_get is None:
            return False

        expected = _resolve_json_value(
            self.query_params,
            request=request,
            context=context,
        )

        for key, value in expected.items():
            if isinstance(value, list):
                actual_values = request_get.getlist(key)
                expected_values = [str(item) for item in value]

                if actual_values != expected_values:
                    return False

                continue

            if request_get.get(key) != str(value):
                return False

        return True

    def is_active_for(
        self,
        request: Any | None,
        *,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Return whether this link should be active for a request."""
        if request is None:
            return False

        if self.active_match == self.ActiveMatch.NONE:
            return False

        current_path = getattr(request, "path", "") or ""
        resolver_match = getattr(request, "resolver_match", None)
        current_view_name = (
            getattr(
                resolver_match,
                "view_name",
                "",
            )
            or ""
        )

        matched = False

        if self.active_match == self.ActiveMatch.VIEW_NAME:
            target_view = self.active_view_name or self.url_value
            matched = current_view_name == target_view

        elif self.active_match == self.ActiveMatch.VIEW_PREFIX:
            target_view = self.active_view_name or self.url_value
            matched = bool(target_view and current_view_name.startswith(target_view))

        elif self.active_match == self.ActiveMatch.EXACT_PATH:
            target_path = self._active_path_target(
                request=request,
                context=context,
            )
            matched = current_path == target_path

        elif self.active_match == self.ActiveMatch.PATH_PREFIX:
            target_path = self._active_path_target(
                request=request,
                context=context,
            ).rstrip("/")

            matched = bool(
                target_path
                and (
                    current_path == target_path
                    or current_path.startswith(f"{target_path}/")
                )
            )

        elif self.active_match == self.ActiveMatch.AUTO:
            if self.url_type == self.URLType.NAMED:
                target_view = self.active_view_name or self.url_value
                matched = current_view_name == target_view

            if not matched:
                target_path = self._active_path_target(
                    request=request,
                    context=context,
                ).rstrip("/")

                matched = bool(
                    target_path
                    and (
                        current_path == target_path
                        or current_path.startswith(f"{target_path}/")
                    )
                )

        return matched and self._query_params_match(
            request=request,
            context=context,
        )

    def visible_to(
        self,
        user: Any,
        *,
        request: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """
        Return whether this link is visible to a user.

        The visibility implementation lives in ``launchpad.visibility`` so
        policy can evolve independently of the model.
        """
        return is_visible(
            self,
            user=user,
            request=request,
            context=context,
        )
