"""
src/launchpad/cache.py

Cache infrastructure for django-launchpad.

Launchpad is intentionally read-heavy and write-light. Navigation
configuration is typically read on many requests while changes through
Django admin, fixtures, migrations, or application code are comparatively
rare.

This module provides package-level cache primitives for stable Launchpad
configuration data.

Design goals:

- Use Django's standard cache framework only.
- Avoid backend-specific operations such as delete_pattern().
- Keep cache keys explicit, deterministic, and generation-based.
- Make invalidation cheap by replacing one global generation token.
- Avoid integer cache versions that could collide after cache eviction.
- Keep request-sensitive resolution out of the persistent cache.
- Allow consuming projects to opt in to caching.
- Allow projects to choose a dedicated Django cache alias.
- Allow projects to configure cache lifetime.
- Remain safe across Django-supported cache backends.

Persistent caching is disabled by default.

Projects may enable it with:

    LAUNCHPAD_CACHE_ENABLED = True

Optional settings:

    LAUNCHPAD_CACHE_ALIAS = "default"
    LAUNCHPAD_CACHE_TIMEOUT = 900

For multi-process production deployments, a shared cache backend such as
Redis or Memcached is strongly recommended. Django's local-memory cache is
process-local and therefore cannot provide cross-process invalidation.

Important boundary:

This module does not cache ResolvedLaunchpad objects directly.

Resolved navigation may depend on:

- the current user,
- the current request path,
- the resolved Django view,
- query parameters,
- runtime context values,
- scheduled visibility,
- registered visibility rules,
- and active-state calculation.

Persistent caching is therefore intended for stable Launchpad
configuration inputs. User-, request-, time-, and context-sensitive
resolution remains the reader's responsibility.
"""

from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.core.cache.backends.base import InvalidCacheBackendError
from django.core.exceptions import ImproperlyConfigured

DEFAULT_CACHE_ENABLED = False
DEFAULT_CACHE_ALIAS = "default"
DEFAULT_CACHE_TIMEOUT = 900  # 15 minutes

CACHE_FORMAT_VERSION = 1

_CACHE_KEY_PREFIX = "django-launchpad"

_CACHE_GENERATION_KEY = (
    f"{_CACHE_KEY_PREFIX}:f{CACHE_FORMAT_VERSION}:configuration-generation"
)

_SETTING_CACHE_ENABLED = "LAUNCHPAD_CACHE_ENABLED"
_SETTING_CACHE_ALIAS = "LAUNCHPAD_CACHE_ALIAS"
_SETTING_CACHE_TIMEOUT = "LAUNCHPAD_CACHE_TIMEOUT"


def is_cache_enabled() -> bool:
    """
    Return whether Launchpad persistent caching is enabled.

    Persistent caching is disabled by default.

    Projects may enable it with:

        LAUNCHPAD_CACHE_ENABLED = True

    Disabling caching does not change Launchpad behavior. Readers should
    simply use the normal database-backed configuration path.
    """
    value = getattr(
        settings,
        _SETTING_CACHE_ENABLED,
        DEFAULT_CACHE_ENABLED,
    )

    if not isinstance(value, bool):
        msg = f"{_SETTING_CACHE_ENABLED} must be a boolean."
        raise ImproperlyConfigured(msg)

    return value


def get_cache_alias() -> str:
    """
    Return the Django cache alias used by Launchpad.

    The default alias is:

        default

    Projects may select another configured Django cache:

        LAUNCHPAD_CACHE_ALIAS = "launchpad"

    A dedicated alias can be useful when Launchpad configuration should
    have independent capacity, timeout, or backend behavior.
    """
    value = getattr(
        settings,
        _SETTING_CACHE_ALIAS,
        DEFAULT_CACHE_ALIAS,
    )

    if not isinstance(value, str):
        msg = f"{_SETTING_CACHE_ALIAS} must be a string."
        raise ImproperlyConfigured(msg)

    alias = value.strip()

    if not alias:
        msg = f"{_SETTING_CACHE_ALIAS} must not be empty."
        raise ImproperlyConfigured(msg)

    try:
        caches[alias]
    except InvalidCacheBackendError as exc:
        msg = (
            f"{_SETTING_CACHE_ALIAS} references an unknown "
            f"Django cache alias: {alias!r}."
        )
        raise ImproperlyConfigured(msg) from exc

    return alias


def get_cache_timeout() -> int:
    """
    Return the configured Launchpad cache timeout in seconds.

    The default is 15 minutes:

        LAUNCHPAD_CACHE_TIMEOUT = 900

    Projects may override it:

        LAUNCHPAD_CACHE_TIMEOUT = 1800

    A value of ``0`` follows Django cache semantics and effectively prevents
    cached configuration values from being retained.

    Negative values are rejected because their behavior may vary between
    cache backends and almost certainly indicates a configuration mistake.
    """
    value = getattr(
        settings,
        _SETTING_CACHE_TIMEOUT,
        DEFAULT_CACHE_TIMEOUT,
    )

    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"{_SETTING_CACHE_TIMEOUT} must be an integer."
        raise ImproperlyConfigured(msg)

    if value < 0:
        msg = f"{_SETTING_CACHE_TIMEOUT} must be greater than or equal to 0."
        raise ImproperlyConfigured(msg)

    return value


def get_cache_backend() -> BaseCache:
    """
    Return the Django cache backend configured for Launchpad.

    This helper centralizes cache lookup so all Launchpad cache operations
    consistently use ``LAUNCHPAD_CACHE_ALIAS``.
    """
    alias = get_cache_alias()
    return caches[alias]


def _new_generation() -> str:
    """
    Return a new unique cache generation token.

    Generations use random UUID values rather than incrementing integers.

    This avoids accidental reuse if the generation key itself is evicted
    while older configuration entries remain in the cache.
    """
    return uuid4().hex


def get_cache_generation() -> str:
    """
    Return the current Launchpad configuration cache generation.

    Generation-based keys allow Launchpad to invalidate every previously
    cached configuration entry without enumerating or deleting individual
    keys.

    Example:

        django-launchpad:f1:gabc123:configuration:home

    After invalidation:

        django-launchpad:f1:gdef456:configuration:home

    Old entries immediately become unreachable and disappear according to
    their normal cache timeout.

    If the generation key does not yet exist, one is initialized lazily.

    When persistent caching is disabled, a stable non-persistent generation
    value is returned because callers may still construct diagnostic cache
    keys without touching Django's cache backend.
    """
    if not is_cache_enabled():
        return "disabled"

    backend = get_cache_backend()

    value = backend.get(
        _CACHE_GENERATION_KEY,
    )

    if isinstance(value, str) and value:
        return value

    generation = _new_generation()

    created = backend.add(
        _CACHE_GENERATION_KEY,
        generation,
        timeout=None,
    )

    if created:
        return generation

    value = backend.get(
        _CACHE_GENERATION_KEY,
    )

    if isinstance(value, str) and value:
        return value

    # Defensive recovery for unusual cache backends or a generation key
    # disappearing between add() and get().
    generation = _new_generation()

    backend.set(
        _CACHE_GENERATION_KEY,
        generation,
        timeout=None,
    )

    return generation


def bump_cache_generation() -> str:
    """
    Replace the global Launchpad configuration cache generation.

    This is the low-level invalidation primitive.

    A unique generation token is written instead of incrementing an integer.
    This avoids relying on atomic ``cache.incr()`` behavior and prevents old
    cache generations from becoming reachable again if the generation key is
    evicted.

    Concurrent invalidations are safe. Whichever generation is written last
    becomes authoritative. Cache entries written under an earlier concurrent
    generation simply become unreachable.

    Returns:
        The newly generated cache generation.

    When persistent caching is disabled, no cache backend is modified.
    """
    if not is_cache_enabled():
        return "disabled"

    generation = _new_generation()

    get_cache_backend().set(
        _CACHE_GENERATION_KEY,
        generation,
        timeout=None,
    )

    return generation


def configuration_cache_key(
    code: str,
    *,
    generation: str | None = None,
) -> str:
    """
    Return the cache key for one Launchpad configuration snapshot.

    Args:
        code:
            Stable Launchpad code.

        generation:
            Optional explicit cache generation. When omitted, the current
            global Launchpad configuration generation is used.

    Example:

        django-launchpad:f1:gabc123:configuration:primary_navigation

    ``CACHE_FORMAT_VERSION`` is included separately from the cache generation.

    The format version protects future releases from trying to consume cached
    configuration serialized by an incompatible package version.

    The Launchpad code is normalized with ``strip()`` because the public
    reader API treats surrounding whitespace as insignificant.
    """
    normalized_code = str(code).strip()

    if not normalized_code:
        msg = "Launchpad cache keys require a non-empty code."
        raise ValueError(msg)

    resolved_generation = get_cache_generation() if generation is None else generation

    if not isinstance(resolved_generation, str):
        msg = "Launchpad cache generations must be strings."
        raise ValueError(msg)  # noqa: TRY004

    resolved_generation = resolved_generation.strip()

    if not resolved_generation:
        msg = "Launchpad cache generations must not be empty."
        raise ValueError(msg)

    return (
        f"{_CACHE_KEY_PREFIX}:"
        f"f{CACHE_FORMAT_VERSION}:"
        f"g{resolved_generation}:"
        f"configuration:{normalized_code}"
    )


def invalidate_configuration_cache() -> str:
    """
    Invalidate all persistent Launchpad configuration cache entries.

    Invalidation replaces the global cache generation instead of deleting
    individual keys.

    Existing configuration entries remain physically present until their
    normal cache timeout expires, but they become unreachable immediately
    because new reads use the new generation.

    Model signals, admin integration, and application code should call this
    semantic helper rather than depending directly on generation internals.

    Database-backed invalidation should normally be scheduled with
    ``transaction.on_commit()`` so a new cache generation is not exposed
    before the database mutation that caused it has successfully committed.

    Returns:
        The new configuration cache generation.
    """
    return bump_cache_generation()


__all__ = [
    "CACHE_FORMAT_VERSION",
    "DEFAULT_CACHE_ALIAS",
    "DEFAULT_CACHE_ENABLED",
    "DEFAULT_CACHE_TIMEOUT",
    "bump_cache_generation",
    "configuration_cache_key",
    "get_cache_alias",
    "get_cache_backend",
    "get_cache_generation",
    "get_cache_timeout",
    "invalidate_configuration_cache",
    "is_cache_enabled",
]
