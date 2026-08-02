# django-launchpad

Renderer-independent navigation and application launchpads for Django.

## Overview

`django-launchpad` is a reusable Django application for building composable,
permission-aware navigation structures that are independent of how they are
rendered.

Whether your application presents navigation as:

* sidebars
* dashboards
* application launchers
* top navigation
* dropdown menus
* mobile navigation
* command palettes

the underlying navigation model remains the same.

## Philosophy

Launchpad separates three distinct concerns:

* **Navigation destinations** — where users can go.
* **Navigation composition** — how destinations are organized.
* **Presentation** — how navigation is rendered.

Renderers consume Launchpad data but do not define it.

## Status

This project is under active development.

The public API is not yet stable and may change before the first production
release.

## License

MIT
