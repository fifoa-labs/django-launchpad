"""
tests/test_cache.py

Tests for django-launchpad cache configuration, generation management,
invalidation, and cache-key construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from launchpad import cache as launchpad_cache


@dataclass
class FakeCacheBackend:
    """
    Minimal cache backend used to exercise Launchpad cache primitives.

    ``get_values`` allows tests to model multiple sequential cache reads,
    including races where a generation key disappears between operations.
    """

    get_values: list[Any] = field(default_factory=list)
    add_result: bool = True

    get_calls: list[str] = field(default_factory=list)
    add_calls: list[tuple[str, Any, int | None]] = field(default_factory=list)
    set_calls: list[tuple[str, Any, int | None]] = field(default_factory=list)

    def get(self, key: str) -> Any:
        """Return the next configured cache value."""
        self.get_calls.append(key)

        if self.get_values:
            return self.get_values.pop(0)

        return None

    def add(
        self,
        key: str,
        value: Any,
        timeout: int | None = None,
    ) -> bool:
        """Record an add operation and return the configured result."""
        self.add_calls.append(
            (
                key,
                value,
                timeout,
            ),
        )
        return self.add_result

    def set(
        self,
        key: str,
        value: Any,
        timeout: int | None = None,
    ) -> None:
        """Record a set operation."""
        self.set_calls.append(
            (
                key,
                value,
                timeout,
            ),
        )


def test_cache_defaults_are_stable() -> None:
    """Package cache defaults should remain explicit and conservative."""
    assert launchpad_cache.DEFAULT_CACHE_ENABLED is False
    assert launchpad_cache.DEFAULT_CACHE_ALIAS == "default"
    assert launchpad_cache.DEFAULT_CACHE_TIMEOUT == 900
    assert launchpad_cache.CACHE_FORMAT_VERSION == 1


def test_cache_is_disabled_by_default() -> None:
    """Persistent caching should be opt-in."""
    assert launchpad_cache.is_cache_enabled() is False


def test_cache_can_be_enabled() -> None:
    """Projects should be able to enable persistent caching explicitly."""
    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=True,
    ):
        assert launchpad_cache.is_cache_enabled() is True


@pytest.mark.parametrize(
    "value",
    [
        1,
        0,
        "true",
        "false",
        None,
        [],
        {},
    ],
)
def test_cache_enabled_rejects_non_boolean_values(
    value: Any,
) -> None:
    """Cache enablement should accept actual booleans only."""
    with (
        override_settings(
            LAUNCHPAD_CACHE_ENABLED=value,
        ),
        pytest.raises(
            ImproperlyConfigured,
            match="LAUNCHPAD_CACHE_ENABLED must be a boolean",
        ),
    ):
        launchpad_cache.is_cache_enabled()


def test_default_cache_alias_is_default() -> None:
    """Launchpad should use Django's default cache alias unless configured."""
    assert launchpad_cache.get_cache_alias() == "default"


def test_cache_alias_can_be_overridden() -> None:
    """Projects should be able to choose another configured cache alias."""
    configured_caches = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "launchpad-default",
        },
        "launchpad": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "launchpad-dedicated",
        },
    }

    with override_settings(
        CACHES=configured_caches,
        LAUNCHPAD_CACHE_ALIAS="launchpad",
    ):
        assert launchpad_cache.get_cache_alias() == "launchpad"


def test_cache_alias_is_stripped() -> None:
    """Surrounding whitespace in a configured cache alias should be ignored."""
    with override_settings(
        LAUNCHPAD_CACHE_ALIAS=" default ",
    ):
        assert launchpad_cache.get_cache_alias() == "default"


@pytest.mark.parametrize(
    "value",
    [
        1,
        True,
        None,
        [],
        {},
    ],
)
def test_cache_alias_rejects_non_string_values(
    value: Any,
) -> None:
    """Cache aliases should be configured as strings."""
    with (
        override_settings(
            LAUNCHPAD_CACHE_ALIAS=value,
        ),
        pytest.raises(
            ImproperlyConfigured,
            match="LAUNCHPAD_CACHE_ALIAS must be a string",
        ),
    ):
        launchpad_cache.get_cache_alias()


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "   ",
    ],
)
def test_cache_alias_rejects_empty_values(
    value: str,
) -> None:
    """Empty cache aliases should fail configuration validation."""
    with (
        override_settings(
            LAUNCHPAD_CACHE_ALIAS=value,
        ),
        pytest.raises(
            ImproperlyConfigured,
            match="LAUNCHPAD_CACHE_ALIAS must not be empty",
        ),
    ):
        launchpad_cache.get_cache_alias()


def test_cache_alias_rejects_unknown_django_alias() -> None:
    """An alias absent from Django CACHES should fail clearly."""
    with (
        override_settings(
            LAUNCHPAD_CACHE_ALIAS="missing-launchpad-cache",
        ),
        pytest.raises(
            ImproperlyConfigured,
            match=("LAUNCHPAD_CACHE_ALIAS references an unknown Django cache alias"),
        ),
    ):
        launchpad_cache.get_cache_alias()


def test_default_cache_timeout_is_fifteen_minutes() -> None:
    """The default persistent configuration lifetime should be 15 minutes."""
    assert launchpad_cache.get_cache_timeout() == 900


def test_cache_timeout_can_be_overridden() -> None:
    """Projects should be able to choose a different cache timeout."""
    with override_settings(
        LAUNCHPAD_CACHE_TIMEOUT=1800,
    ):
        assert launchpad_cache.get_cache_timeout() == 1800


def test_cache_timeout_accepts_zero() -> None:
    """A zero timeout should preserve Django's no-retention semantics."""
    with override_settings(
        LAUNCHPAD_CACHE_TIMEOUT=0,
    ):
        assert launchpad_cache.get_cache_timeout() == 0


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        1.5,
        "900",
        None,
        [],
        {},
    ],
)
def test_cache_timeout_rejects_non_integer_values(
    value: Any,
) -> None:
    """Cache timeout should require an integer and reject booleans."""
    with (
        override_settings(
            LAUNCHPAD_CACHE_TIMEOUT=value,
        ),
        pytest.raises(
            ImproperlyConfigured,
            match="LAUNCHPAD_CACHE_TIMEOUT must be an integer",
        ),
    ):
        launchpad_cache.get_cache_timeout()


@pytest.mark.parametrize(
    "value",
    [
        -1,
        -900,
    ],
)
def test_cache_timeout_rejects_negative_values(
    value: int,
) -> None:
    """Negative cache timeouts should fail configuration validation."""
    with (
        override_settings(
            LAUNCHPAD_CACHE_TIMEOUT=value,
        ),
        pytest.raises(
            ImproperlyConfigured,
            match=("LAUNCHPAD_CACHE_TIMEOUT must be greater than or equal to 0"),
        ),
    ):
        launchpad_cache.get_cache_timeout()


def test_get_cache_backend_returns_configured_backend() -> None:
    """Backend lookup should resolve through the configured cache alias."""
    assert launchpad_cache.get_cache_backend() is caches["default"]


def test_get_cache_backend_uses_custom_alias() -> None:
    """Backend lookup should honor LAUNCHPAD_CACHE_ALIAS."""
    configured_caches = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "launchpad-default-backend",
        },
        "launchpad": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "launchpad-special-backend",
        },
    }

    with override_settings(
        CACHES=configured_caches,
        LAUNCHPAD_CACHE_ALIAS="launchpad",
    ):
        assert launchpad_cache.get_cache_backend() is caches["launchpad"]


def test_get_cache_generation_does_not_touch_backend_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabled caching should avoid all persistent cache backend access."""

    def fail_backend_lookup() -> Any:
        pytest.fail("Cache backend should not be accessed when disabled.")

    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_backend",
        fail_backend_lookup,
    )

    assert launchpad_cache.get_cache_generation() == "disabled"


def test_get_cache_generation_returns_existing_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing valid generation should be returned unchanged."""
    backend = FakeCacheBackend(
        get_values=["generation-existing"],
    )

    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_backend",
        lambda: backend,
    )

    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=True,
    ):
        generation = launchpad_cache.get_cache_generation()

    assert generation == "generation-existing"

    assert len(backend.get_calls) == 1
    assert backend.add_calls == []
    assert backend.set_calls == []


def test_get_cache_generation_initializes_missing_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing generation should be initialized with cache.add()."""
    backend = FakeCacheBackend(
        get_values=[None],
        add_result=True,
    )

    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_backend",
        lambda: backend,
    )

    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=True,
    ):
        generation = launchpad_cache.get_cache_generation()

    assert isinstance(generation, str)
    assert len(generation) == 32
    assert generation != "disabled"

    assert len(backend.get_calls) == 1
    assert len(backend.add_calls) == 1
    assert backend.set_calls == []

    _, added_generation, timeout = backend.add_calls[0]

    assert added_generation == generation
    assert timeout is None


def test_get_cache_generation_uses_generation_created_by_another_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A failed add should read and use the concurrently initialized generation.

    This models another process creating the generation after the first
    process observes a cache miss.
    """
    backend = FakeCacheBackend(
        get_values=[
            None,
            "generation-from-other-process",
        ],
        add_result=False,
    )

    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_backend",
        lambda: backend,
    )

    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=True,
    ):
        generation = launchpad_cache.get_cache_generation()

    assert generation == "generation-from-other-process"

    assert len(backend.get_calls) == 2
    assert len(backend.add_calls) == 1
    assert backend.set_calls == []


@pytest.mark.parametrize(
    "existing_value",
    [
        "",
        1,
        True,
        False,
        [],
        {},
    ],
)
def test_get_cache_generation_replaces_invalid_cached_generation(
    existing_value: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid cached generation values should be repaired safely."""
    backend = FakeCacheBackend(
        get_values=[existing_value],
        add_result=True,
    )

    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_backend",
        lambda: backend,
    )

    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=True,
    ):
        generation = launchpad_cache.get_cache_generation()

    assert isinstance(generation, str)
    assert len(generation) == 32

    assert len(backend.add_calls) == 1
    assert backend.set_calls == []


def test_get_cache_generation_recovers_when_generation_disappears_during_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Generation initialization should recover if a cache race removes the key.

    The sequence modeled here is:

    1. initial lookup misses,
    2. add reports that another process owns initialization,
    3. the second lookup also misses,
    4. Launchpad writes a fresh defensive generation.
    """
    backend = FakeCacheBackend(
        get_values=[
            None,
            None,
        ],
        add_result=False,
    )

    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_backend",
        lambda: backend,
    )

    generations = iter(
        [
            "generation-attempt-one",
            "generation-recovery",
        ],
    )

    monkeypatch.setattr(
        launchpad_cache,
        "_new_generation",
        lambda: next(generations),
    )

    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=True,
    ):
        generation = launchpad_cache.get_cache_generation()

    assert generation == "generation-recovery"

    assert len(backend.get_calls) == 2

    assert backend.add_calls == [
        (
            backend.add_calls[0][0],
            "generation-attempt-one",
            None,
        ),
    ]

    assert backend.set_calls == [
        (
            backend.set_calls[0][0],
            "generation-recovery",
            None,
        ),
    ]

    assert backend.add_calls[0][0] == backend.set_calls[0][0]


def test_bump_cache_generation_does_not_touch_backend_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalidation should become a no-op when persistent caching is disabled."""

    def fail_backend_lookup() -> Any:
        pytest.fail("Cache backend should not be accessed when disabled.")

    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_backend",
        fail_backend_lookup,
    )

    assert launchpad_cache.bump_cache_generation() == "disabled"


def test_bump_cache_generation_replaces_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalidation should replace the current generation with a new token."""
    backend = FakeCacheBackend()

    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_backend",
        lambda: backend,
    )

    monkeypatch.setattr(
        launchpad_cache,
        "_new_generation",
        lambda: "new-generation",
    )

    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=True,
    ):
        generation = launchpad_cache.bump_cache_generation()

    assert generation == "new-generation"

    assert len(backend.set_calls) == 1

    _, stored_generation, timeout = backend.set_calls[0]

    assert stored_generation == "new-generation"
    assert timeout is None


def test_bump_cache_generation_produces_unique_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Consecutive invalidations should never intentionally reuse generations."""
    backend = FakeCacheBackend()

    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_backend",
        lambda: backend,
    )

    with override_settings(
        LAUNCHPAD_CACHE_ENABLED=True,
    ):
        first = launchpad_cache.bump_cache_generation()
        second = launchpad_cache.bump_cache_generation()

    assert first != second

    assert len(first) == 32
    assert len(second) == 32

    assert len(backend.set_calls) == 2


def test_configuration_cache_key_uses_explicit_generation() -> None:
    """Explicit generations should produce deterministic configuration keys."""
    key = launchpad_cache.configuration_cache_key(
        "primary_navigation",
        generation="generation-123",
    )

    assert key == (
        "django-launchpad:f1:ggeneration-123:configuration:primary_navigation"
    )


def test_configuration_cache_key_normalizes_code() -> None:
    """Surrounding whitespace should not alter a Launchpad cache key."""
    key = launchpad_cache.configuration_cache_key(
        "  home  ",
        generation="abc123",
    )

    assert key == ("django-launchpad:f1:gabc123:configuration:home")


def test_configuration_cache_key_uses_current_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitting generation should use the current configuration generation."""
    monkeypatch.setattr(
        launchpad_cache,
        "get_cache_generation",
        lambda: "current-generation",
    )

    key = launchpad_cache.configuration_cache_key(
        "home",
    )

    assert key == ("django-launchpad:f1:gcurrent-generation:configuration:home")


def test_configuration_cache_key_uses_disabled_generation_when_cache_disabled() -> None:
    """
    Key construction should remain deterministic even with caching disabled.

    This supports diagnostics without touching the configured cache backend.
    """
    key = launchpad_cache.configuration_cache_key(
        "home",
    )

    assert key == ("django-launchpad:f1:gdisabled:configuration:home")


@pytest.mark.parametrize(
    "code",
    [
        "",
        " ",
        "   ",
    ],
)
def test_configuration_cache_key_rejects_empty_code(
    code: str,
) -> None:
    """Configuration keys require a non-empty Launchpad code."""
    with pytest.raises(
        ValueError,
        match="Launchpad cache keys require a non-empty code",
    ):
        launchpad_cache.configuration_cache_key(
            code,
            generation="generation",
        )


@pytest.mark.parametrize(
    "generation",
    [
        1,
        True,
        False,
        None,
        [],
        {},
    ],
)
def test_configuration_cache_key_rejects_non_string_explicit_generation(
    generation: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit generation values must be strings."""
    if generation is None:
        monkeypatch.setattr(
            launchpad_cache,
            "get_cache_generation",
            lambda: 42,
        )

        with pytest.raises(
            ValueError,
            match="Launchpad cache generations must be strings",
        ):
            launchpad_cache.configuration_cache_key("home")

        return

    with pytest.raises(
        ValueError,
        match="Launchpad cache generations must be strings",
    ):
        launchpad_cache.configuration_cache_key(
            "home",
            generation=generation,
        )


@pytest.mark.parametrize(
    "generation",
    [
        "",
        " ",
        "   ",
    ],
)
def test_configuration_cache_key_rejects_empty_generation(
    generation: str,
) -> None:
    """Blank generation strings should not produce cache keys."""
    with pytest.raises(
        ValueError,
        match="Launchpad cache generations must not be empty",
    ):
        launchpad_cache.configuration_cache_key(
            "home",
            generation=generation,
        )


def test_configuration_cache_key_strips_generation() -> None:
    """Explicit generation strings should be normalized before use."""
    key = launchpad_cache.configuration_cache_key(
        "home",
        generation="  abc123  ",
    )

    assert key == ("django-launchpad:f1:gabc123:configuration:home")


def test_cache_format_version_is_embedded_in_configuration_key() -> None:
    """Cache keys should encode the serialization format independently."""
    key = launchpad_cache.configuration_cache_key(
        "home",
        generation="abc123",
    )

    assert f":f{launchpad_cache.CACHE_FORMAT_VERSION}:" in key


def test_invalidate_configuration_cache_delegates_to_generation_bump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The semantic invalidation API should delegate to generation replacement."""
    calls = 0

    def bump() -> str:
        nonlocal calls
        calls += 1
        return "invalidated-generation"

    monkeypatch.setattr(
        launchpad_cache,
        "bump_cache_generation",
        bump,
    )

    result = launchpad_cache.invalidate_configuration_cache()

    assert result == "invalidated-generation"
    assert calls == 1


def test_public_cache_api_exports_expected_symbols() -> None:
    """The cache module should expose only its intentional public primitives."""
    assert launchpad_cache.__all__ == [
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
