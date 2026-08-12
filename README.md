# django-launchpad

[![PyPI version](https://img.shields.io/pypi/v/django-launchpad.svg)](https://pypi.org/project/django-launchpad/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-launchpad.svg)](https://pypi.org/project/django-launchpad/)
[![CI](https://github.com/fifoa-labs/django-launchpad/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fifoa-labs/django-launchpad/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/fifoa-labs/django-launchpad/branch/main/graph/badge.svg)](https://codecov.io/gh/fifoa-labs/django-launchpad)
[![License](https://img.shields.io/pypi/l/django-launchpad.svg)](https://github.com/fifoa-labs/django-launchpad/blob/main/LICENSE)

**Renderer-independent navigation and application launchpads for Django.**

Every Django application eventually needs navigation: a sidebar, a
dashboard, a mobile menu, an account menu, an application launcher, or a
command palette.

Most projects build each surface separately.

`django-launchpad` models them as different presentations of the same
navigation system.

- **PyPI:** https://pypi.org/project/django-launchpad/
- **Source:** https://github.com/fifoa-labs/django-launchpad
- **License:** MIT

Define destinations once. Compose them into named launchpads. Apply
user-aware visibility. Resolve the result into a renderer-neutral tree.
Then present that tree however your application needs.

```text
NavigationLink
      │
      ▼
LaunchpadNode
      │
      ▼
   Launchpad
      │
      ▼
ResolvedLaunchpad
      │
      ├── Sidebar
      ├── Dashboard cards
      ├── Top navigation
      ├── Mobile menu
      ├── Footer
      └── Command palette
```

The package solves navigation structure, policy, resolution, and optional
configuration caching.

Your project owns the user interface.

---

## Why Launchpad?

Navigation often begins as a few hard-coded links and gradually grows into
duplicated logic spread across templates, context processors, views,
permission checks, and frontend components.

Common problems follow:

- The same destination is defined repeatedly.
- Sidebars and dashboards drift out of sync.
- Permission checks differ between renderers.
- Active-state logic is duplicated.
- Project-specific templates become responsible for data loading.
- Changing navigation requires editing application code.
- A destination cannot be reused with different labels or placement rules.
- Navigation configuration is queried on every request even though it
  changes rarely.

Launchpad separates the problem into durable layers:

- **NavigationLink** — the canonical destination.
- **LaunchpadNode** — one placement of a destination or structural item.
- **Launchpad** — a named composition of nodes.
- **Reader** — resolves stored configuration into renderer-neutral data.
- **Renderer** — remains entirely project-owned.

The same destination can appear in multiple launchpads with different
titles, hierarchy, ordering, visibility, metadata, icons, and enabled
states—without duplicating the destination itself.

---

## Core Concepts

### `NavigationLink`

A `NavigationLink` represents a reusable destination.

Examples:

- A Django named URL such as `reports:index`
- A relative path such as `/documentation/`
- An external HTTPS URL
- A `mailto:` or `tel:` link
- A context-aware detail URL resolved at render time

A link defines canonical information such as:

- stable code
- title and short title
- description, tooltip, and ARIA label
- destination and URL arguments
- query parameters and fragment
- target, `rel`, and download behavior
- icon descriptor
- enabled state and disabled reason
- active-match strategy
- visibility policy
- search aliases
- renderer-neutral metadata

A `NavigationLink` does not decide where it appears.

### `Launchpad`

A `Launchpad` is a named, renderer-independent navigation composition.

Typical codes include:

- `primary_navigation`
- `homepage`
- `account_menu`
- `mobile_navigation`
- `report_actions`
- `command_palette`

Templates, tests, fixtures, and application code address a Launchpad by
its stable `code`.

### `LaunchpadNode`

A `LaunchpadNode` places something inside a Launchpad tree.

A node can be:

- **Link** — a placement of a `NavigationLink`
- **Section** — a structural grouping node
- **Separator** — a structural divider

Nodes can be nested and ordered. A placement may override the linked
destination's presentation without changing the canonical link.

Supported placement overrides include:

- code
- title and short title
- description and tooltip
- ARIA label
- call-to-action label
- icon
- enabled state and disabled reason
- visibility policy
- metadata

Link-level visibility and node-level visibility are both enforced.

This means the link can define a global minimum policy, while an individual
placement may restrict visibility further.

---

## Resolution Pipeline

`get_launchpad()` resolves stored configuration into a
`ResolvedLaunchpad` tree suitable for any renderer.

The reader:

1. Normalizes the requested Launchpad code.
2. Loads stable Launchpad configuration from the database or optional
   persistent cache.
3. Loads active nodes and related navigation links efficiently.
4. Builds or reuses the request-scoped visibility context.
5. Applies node visibility.
6. Applies linked `NavigationLink` visibility.
7. Resolves context-aware URLs.
8. Applies placement overrides.
9. Builds the parent-child tree.
10. Removes empty sections.
11. Removes leading, trailing, and duplicate separators.
12. Computes active state for links and their ancestors.
13. Returns renderer-neutral data.

Missing or inactive Launchpads fail safely and return an empty
`ResolvedLaunchpad` rather than raising during template rendering.

### Reader Public API

The internal reader implementation is split into focused modules, while
the public API remains intentionally small:

```python
from launchpad.readers import (
    ResolvedLaunchpad,
    ResolvedNode,
    get_launchpad,
)
```

Cache snapshots, database loaders, tree construction, and resolution
internals are implementation details and are not part of the supported
public reader API.

---

## Features

- Renderer-independent navigation architecture
- Reusable canonical destinations
- Named Launchpad compositions
- Arbitrarily nested node trees
- Link, section, and separator nodes
- Placement-specific presentation overrides
- Public, authenticated, staff, superuser, and private audiences
- Explicit user and group visibility
- Django permission gates
- `all` and `any` permission modes
- Scheduled visibility windows
- Registered runtime visibility rules
- Named Django URLs and validated raw URLs
- Positional and keyword URL arguments
- Query parameters and fragments
- Context-aware URL values
- Active matching by path or Django view name
- Disabled links that remain visible but non-navigable
- Renderer-neutral metadata
- Generic recursive Django template
- Optional presentation-only collection padding
- Optional persistent configuration caching
- Generation-based cache invalidation
- Configurable Django cache alias
- Request-scoped visibility-context reuse
- Transaction-safe cache invalidation
- Django admin integration
- Fully typed package with `py.typed`
- Strict mypy validation
- 100% statement and branch coverage

---

## Installation

Install from PyPI:

```bash
python -m pip install django-launchpad
```

With `uv`:

```bash
uv add django-launchpad
```

Add Launchpad to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "launchpad.apps.LaunchpadConfig",
]
```

Run migrations:

```bash
python manage.py migrate
```

No package settings are required for normal operation.

Persistent configuration caching is optional and disabled by default.

---

## Quick Start

Launchpad configuration can be created through Django admin, fixtures,
migrations, the Django shell, or application code.

The following example creates one canonical destination and places it in a
primary navigation Launchpad.

```python
from launchpad.models import Launchpad, LaunchpadNode, NavigationLink


reports_link = NavigationLink.objects.create(
    code="reports",
    title="Reports",
    description="View operational reports.",
    url_type=NavigationLink.URLType.NAMED,
    url_value="reports:index",
    audience=NavigationLink.Audience.AUTHENTICATED,
)

primary_navigation = Launchpad.objects.create(
    code="primary_navigation",
    title="Primary Navigation",
)

LaunchpadNode.objects.create(
    launchpad=primary_navigation,
    kind=LaunchpadNode.Kind.LINK,
    navigation_link=reports_link,
    audience=LaunchpadNode.Audience.PUBLIC,
    sort_order=1000,
)
```

The node is public at the placement level, but the linked destination still
requires an authenticated user. Both policies must pass.

### Resolve in Python

```python
from launchpad.readers import get_launchpad


navigation = get_launchpad(
    "primary_navigation",
    request=request,
)
```

The result is a `ResolvedLaunchpad` containing renderer-neutral
`ResolvedNode` objects.

### Resolve in a Template

```django
{% load launchpad_tags %}

{% get_launchpad "primary_navigation" as navigation %}
```

Render the bundled generic tree:

```django
{% include "launchpad/generic/tree.html" with launchpad=navigation only %}
```

Or pass the same `navigation` object to a project-owned renderer.

---

## Optional Configuration Caching

Launchpad configuration is naturally read-heavy and write-light.

A primary navigation tree may be resolved on nearly every request while
the underlying Launchpad, nodes, links, user assignments, and group
assignments change only occasionally.

`django-launchpad` therefore provides optional persistent caching for
**stable Launchpad configuration**.

Caching is disabled by default.

Enable it explicitly:

```python
LAUNCHPAD_CACHE_ENABLED = True
```

Default cache settings are:

```python
LAUNCHPAD_CACHE_ENABLED = False
LAUNCHPAD_CACHE_ALIAS = "default"
LAUNCHPAD_CACHE_TIMEOUT = 900
```

All three settings are optional.

### `LAUNCHPAD_CACHE_ENABLED`

Controls persistent configuration caching.

```python
LAUNCHPAD_CACHE_ENABLED = True
```

Default:

```python
False
```

When disabled, the normal ORM-backed reader path is used.

### `LAUNCHPAD_CACHE_ALIAS`

Selects the Django cache alias Launchpad should use:

```python
LAUNCHPAD_CACHE_ALIAS = "default"
```

A project may dedicate a separate cache:

```python
CACHES = {
    "default": {
        # ...
    },
    "launchpad": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
    },
}

LAUNCHPAD_CACHE_ENABLED = True
LAUNCHPAD_CACHE_ALIAS = "launchpad"
```

### `LAUNCHPAD_CACHE_TIMEOUT`

Controls how long stable configuration snapshots remain physically stored:

```python
LAUNCHPAD_CACHE_TIMEOUT = 900
```

The default is 15 minutes.

A timeout of `0` follows Django cache semantics and effectively prevents
cached configuration values from being retained.

Negative values are rejected as configuration errors.

### What Is Cached?

Persistent caching stores stable configuration snapshots containing data
such as:

- Launchpad identity and metadata
- active Launchpad nodes
- parent relationships
- canonical NavigationLink configuration
- placement overrides
- visibility policy fields
- explicit user IDs
- explicit group IDs

Snapshots contain cache-safe data rather than live querysets.

### What Is Not Cached?

`ResolvedLaunchpad` objects are **not** persistently cached.

User-, request-, time-, and context-sensitive behavior continues to run on
every call, including:

- current user visibility
- scheduled visibility windows
- context-aware URL references
- current path
- resolved Django view name
- query-parameter matching
- active-state calculation
- ancestor active-state propagation

This boundary allows Launchpad to cache the expensive, stable configuration
layer without freezing request-specific behavior.

### Runtime Visibility Rules

Configurations containing registered runtime visibility rules deliberately
stay on the live ORM path.

Runtime rules may depend on receiving real Django model instances through
their `obj` argument. Launchpad therefore does not persist those
configurations as cache snapshots.

This preserves the existing runtime-rule contract.

### Request-Scoped Visibility Reuse

Persistent caching is only one part of reader efficiency.

During a single HTTP request, several Launchpads may be resolved:

```text
primary_navigation
home
account_menu
```

Group membership and Django permission collection are user-derived and do
not need to be rebuilt separately for every Launchpad.

Launchpad therefore memoizes the expensive base `VisibilityContext` on the
request object and attaches a fresh runtime `extra_context` mapping to each
read.

This is request-scoped memoization, not persistent caching.

### Cache Invalidation

Launchpad uses generation-based invalidation.

Conceptually:

```text
django-launchpad:f1:gABC:configuration:home
```

After a configuration change:

```text
django-launchpad:f1:gXYZ:configuration:home
```

Existing entries become unreachable immediately and disappear naturally
according to their cache timeout.

Launchpad does not depend on Redis-specific wildcard deletion or
`delete_pattern()`.

### Automatic Invalidation

Configuration cache invalidation is triggered automatically after:

- `Launchpad` save
- `Launchpad` delete
- `NavigationLink` save
- `NavigationLink` delete
- `LaunchpadNode` save
- `LaunchpadNode` delete
- `NavigationLink.users` add/remove/clear
- `NavigationLink.groups` add/remove/clear
- `LaunchpadNode.users` add/remove/clear
- `LaunchpadNode.groups` add/remove/clear

Invalidation uses `transaction.on_commit()`.

This means a new cache generation is not exposed until the database
mutation that caused it has committed successfully.

A rolled-back transaction does not invalidate the cache.

### Bulk Updates and Direct SQL

Operations that bypass Django model signals also bypass automatic
invalidation.

Examples include:

```python
NavigationLink.objects.filter(...).update(...)
```

and direct SQL.

In those cases, explicitly invalidate configuration:

```python
from launchpad.cache import invalidate_configuration_cache


NavigationLink.objects.filter(...).update(active=False)

invalidate_configuration_cache()
```

### Multi-Process Deployments

For multi-process production deployments, use a shared cache backend such
as Redis or Memcached.

Django's local-memory cache is process-local. It is useful for development
and testing, but it cannot provide cross-process cache sharing or
invalidation.

---

## Optional Presentation Padding

Some card or tile renderers look better when their item count is divisible
by a particular number.

Launchpad provides an optional presentation-only template helper:

```django
{% load launchpad_tags %}

{% get_launchpad "home" as navigation %}
{% launchpad_pad navigation.nodes multiple=2 as cards %}
```

Then render the padded collection:

```django
{% for card in cards %}
    {% if card.is_placeholder %}
        {# render a visual placeholder #}
    {% else %}
        {# render the real ResolvedNode #}
    {% endif %}
{% endfor %}
```

### The Important Boundary

Padding happens **after** normal Launchpad resolution.

The original navigation remains unchanged:

```text
database
    ↓
Launchpad reader
    ↓
ResolvedLaunchpad
    ↓
optional launchpad_pad
    ↓
renderer
```

A placeholder is:

- not a `NavigationLink`
- not a `LaunchpadNode`
- not stored in the database
- not part of persistent caching
- not evaluated by the visibility engine
- not part of the canonical navigation tree
- not navigable

Projects that do not need padding simply do not use `launchpad_pad`.

### Padding Multiples

The default multiple is `2`:

```django
{% launchpad_pad navigation.nodes as cards %}
```

An explicit multiple may be supplied:

```django
{% launchpad_pad navigation.nodes multiple=3 as cards %}
```

Examples:

```text
5 items, multiple=2  -> 6
5 items, multiple=3  -> 6
5 items, multiple=4  -> 8
6 items, multiple=3  -> 6
```

Padding does not attempt to infer browser viewport size or responsive CSS
breakpoints.

The renderer chooses the multiple appropriate for its presentation.

### Placeholder Contract

The built-in render-only placeholder exposes predictable presentation
values such as:

```text
is_placeholder = True
title          = "More to Explore"
url            = "#"
enabled        = False
icon           = {"kind": "emoji", "value": "✨"}
```

The placeholder is deliberately a presentation artifact, not fake
navigation data.

---

## Custom Rendering

Launchpad deliberately does not choose a visual framework.

The package does not require:

- Bootstrap
- Tailwind CSS
- Phoenix
- Bulma
- Material UI
- AdminLTE
- JavaScript navigation libraries

The generic template uses neutral `launchpad-*` classes and demonstrates
recursive rendering. It does not ship a theme, CSS, or JavaScript.

A consuming project may create any renderer it needs:

```text
templates/
└── navigation/
    ├── sidebar.html
    ├── dashboard_cards.html
    ├── mobile_menu.html
    └── command_palette.html
```

Example:

```django
{% load launchpad_tags %}

{% get_launchpad "homepage" as homepage_navigation %}

{% include "navigation/dashboard_cards.html" with launchpad=homepage_navigation only %}
```

Renderers receive resolved data, not ORM query responsibilities.

### Resolved Node Data

A `ResolvedNode` exposes values such as:

- `kind`
- `code`
- `link_code`
- `title`
- `short_title`
- `description`
- `tooltip`
- `aria_label`
- `cta_label`
- `url`
- `target`
- `rel`
- `download`
- `icon`
- `enabled`
- `disabled_reason`
- `is_active`
- `metadata`
- `children`

Convenience properties include:

- `is_link`
- `is_section`
- `is_separator`
- `has_children`

---

## Visibility

Launchpad visibility controls whether a navigation object is shown.

It does **not** replace authorization in the destination view.

Destination views must continue to enforce their own permissions.

### Audiences

Each visibility-aware link or node has a base audience:

- `public`
- `authenticated`
- `staff`
- `superuser`
- `private`

These values express different policies.

For example, a destination that should be visible to every signed-in user
should normally use:

```python
link.audience = NavigationLink.Audience.AUTHENTICATED
```

A `private` object with no explicit users, groups, or permission grant is
intentionally hidden from ordinary users.

Additional user, group, permission, schedule, and runtime-rule constraints
may refine the base policy.

### Explicit Users and Groups

Private navigation can be granted to selected users or groups:

```python
link.users.add(user)
link.groups.add(group)
```

Permission gates still apply when configured.

### Permission Gates

Permissions use standard Django permission strings:

```python
link.permissions_required = [
    "reports.view_report",
    "reports.export_report",
]
```

Require every permission:

```python
link.permissions_mode = NavigationLink.PermissionMode.ALL
```

Require any one permission:

```python
link.permissions_mode = NavigationLink.PermissionMode.ANY
```

Permissions are gates, not optional alternate grants. An explicitly
assigned user still fails visibility when a configured permission gate
fails.

Permission-only visibility is supported:

```python
link.audience = NavigationLink.Audience.PRIVATE
link.permissions_required = ["reports.view_report"]
```

In this configuration, the permission itself may grant visibility.

### Scheduled Visibility

Use `visible_from` and `visible_until` to make links or placements visible
only during a time window.

Inactive or scheduled-off objects remain hidden from everyone, including
superusers.

### Runtime Visibility Rules

Runtime rules support application-specific visibility that cannot be
expressed through stored fields alone.

Register a rule under a safe code:

```python
from launchpad.visibility import register_visibility_rule


@register_visibility_rule("has_reports_access")
def has_reports_access(*, obj, user, request, context) -> bool:
    return bool(
        user
        and user.is_authenticated
        and context.get("reports_enabled")
    )
```

Store only the rule code:

```python
link.visibility_rule = "has_reports_access"
```

Launchpad never stores or imports arbitrary Python paths from the database.

Missing rules and rule exceptions fail closed and hide the object.

---

## URL Resolution

### Named Django URLs

```python
link.url_type = NavigationLink.URLType.NAMED
link.url_value = "people:detail"
link.url_kwargs = {"pk": 42}
```

### Raw URLs

Supported raw URL forms include:

- relative paths
- `http`
- `https`
- `mailto`
- `tel`

Unsafe and unsupported values are rejected, including:

- `javascript:`
- `data:`
- `vbscript:`
- protocol-relative URLs
- unsupported schemes
- `#` as a disabled-link substitute

Use `enabled=False` for disabled navigation.

### Query Parameters and Fragments

```python
link.query_params = {
    "tab": "monthly",
    "tag": ["finance", "operations"],
}
link.fragment = "summary"
```

Existing query parameters are preserved.

### Context-Aware Values

URL arguments, keyword arguments, and query parameters may resolve values
at runtime.

Supported roots:

- `@user`
- `@request`
- `@context`

Example:

```python
link.url_type = NavigationLink.URLType.NAMED
link.url_value = "people:detail"
link.url_kwargs = {
    "pk": "@context.person.pk",
}
link.query_params = {
    "next": "@request.path",
    "viewer": "@user.username",
}
```

In a template:

```django
{% get_launchpad "person_actions" person=person as navigation %}
```

Context traversal reads attributes and dictionary keys. Callables are not
invoked. Missing values fail closed to an empty string.

---

## Active Navigation

Links can determine whether they represent the current request.

Supported strategies:

- `auto`
- `none`
- `exact_path`
- `path_prefix`
- `view_name`
- `view_prefix`

`auto` prefers named-view matching for named URLs and then falls back to
path matching.

Configured query parameters also participate in active-state matching.

When a descendant is active, its resolved ancestors are marked active as
well, allowing renderers to expand the appropriate sections.

---

## Disabled Navigation

Disabled destinations may remain visible while becoming non-navigable.

```python
link.enabled = False
link.disabled_reason = "Coming soon."
```

A placement can override the canonical enabled state:

```python
node.enabled_override = False
node.disabled_reason_override = "Unavailable in this workspace."
```

Disabled nodes resolve to `#`, and the generic renderer emits
non-clickable markup with `aria-disabled="true"`.

---

## Icons

Launchpad stores renderer-neutral icon descriptors.

Supported descriptors:

- `none`
- `emoji`
- `fa`
- `fe`

Example:

```python
link.icon_type = NavigationLink.IconType.EMOJI
link.emoji = "📊"
```

Or:

```python
link.icon_type = NavigationLink.IconType.FA
link.icon_class = "fa-solid fa-chart-line"
```

The package does not bundle Font Awesome, Feather, or any other icon
library. Renderers decide how descriptors are presented.

---

## Django Admin

Launchpad registers all three models with Django admin:

- `NavigationLink`
- `Launchpad`
- `LaunchpadNode`

The admin provides:

- structured fieldsets
- search and filtering
- related-object autocomplete
- inline node editing inside a Launchpad
- direct node editing for larger trees
- resolved-value inspection
- automatic `created_by` assignment
- optimized changelist querysets

Django admin is a management interface, not a rendering requirement.

---

## Public Python API

Models:

```python
from launchpad.models import Launchpad, LaunchpadNode, NavigationLink
```

Reader:

```python
from launchpad.readers import (
    ResolvedLaunchpad,
    ResolvedNode,
    get_launchpad,
)
```

Visibility:

```python
from launchpad.visibility import (
    VisibilityContext,
    build_user_context,
    get_visibility_rule,
    is_visible,
    register_visibility_rule,
)
```

Cache invalidation for signal-bypassing bulk operations:

```python
from launchpad.cache import invalidate_configuration_cache
```

Template tags:

```django
{% load launchpad_tags %}

{% get_launchpad "primary_navigation" as navigation %}
{% launchpad_pad navigation.nodes multiple=2 as cards %}
```

---

## What Launchpad Does Not Do

Launchpad intentionally does not:

- replace authorization in Django views
- generate project views or URL patterns
- require a frontend framework
- ship an opinionated visual theme
- bundle CSS or JavaScript
- bundle icon libraries
- store executable Python import paths
- force navigation definitions into code or templates
- assume a specific user model
- require django-allauth
- require Django REST Framework
- require Redis
- require persistent caching
- persist presentation placeholders

It is a focused Django application for navigation data, policy, resolution,
composition, and optional configuration caching.

---

## Custom User Models and django-allauth

User relationships use `settings.AUTH_USER_MODEL`.

Launchpad works with:

- Django's built-in user model
- custom `AbstractUser` models
- custom `AbstractBaseUser` models
- django-allauth with the project's configured user model

The visibility engine relies only on Django's standard authentication
interface, including:

- `is_authenticated`
- `is_staff`
- `is_superuser`
- `groups`
- `get_all_permissions()`

---

## Supported Versions

| Python | Django 5.2 | Django 6.0 |
|---|---:|---:|
| 3.11 | Yes | No |
| 3.12 | Yes | Yes |
| 3.13 | Yes | Yes |
| 3.14 | Yes | Yes |

Package metadata currently allows:

```text
Python >= 3.11
Django >= 5.2, < 6.1
```

---

## Quality

`django-launchpad` is developed with the same quality standards used across
FIFOA Labs packages.

- Ruff formatting and linting
- Strict mypy validation across source and tests
- `django-stubs`
- Pytest and pytest-django
- 100% statement coverage
- 100% branch coverage
- CI across supported Python and Django combinations
- Django system checks
- Migration drift checks
- Migration application smoke testing
- Source and wheel distribution validation
- Required wheel-content validation
- Clean-wheel installation testing
- Typed distribution via `py.typed`
- PyPI Trusted Publishing

---

## Project Status

The current version is `0.2.0`.

`django-launchpad` is suitable for integration and real-world use, but its
public API remains pre-1.0 and may continue to evolve as the package is
adopted by additional Django projects.

`0.2.0` adds optional configuration caching, request-scoped visibility
reuse, automatic transaction-safe cache invalidation, a modularized reader
implementation, and optional presentation-only Launchpad padding.

Semantic versioning is used:

- patch releases fix bugs and documentation
- minor `0.x` releases may add features or refine pre-1.0 APIs
- `1.0.0` will mark a stable public compatibility commitment

---

## Contributing

Issues and pull requests are welcome.

Before submitting changes, run:

```bash
make check
make coverage
make build
make check-dist
make install-wheel
```

For the full local release validation pipeline:

```bash
make release-check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for project guidelines.

---

## License

`django-launchpad` is released under the MIT License.

See [LICENSE](LICENSE) for the full license text.

---

Built and maintained by [FIFOA Labs](https://github.com/fifoa-labs).
