"""
tests/test_signals.py

Tests for django-launchpad cache invalidation signals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from django.db import transaction

from launchpad import signals
from launchpad.cache import invalidate_configuration_cache
from launchpad.models import (
    Launchpad,
    LaunchpadNode,
    NavigationLink,
)
from tests.builders import (
    create_group,
    create_launchpad,
    create_link_node,
    create_navigation_link,
    create_user,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_schedule_cache_invalidation_registers_on_commit_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalidation should be scheduled through transaction.on_commit()."""
    callbacks: list[Callable[[], Any]] = []

    def on_commit(
        callback: Callable[[], Any],
    ) -> None:
        callbacks.append(
            callback,
        )

    monkeypatch.setattr(
        transaction,
        "on_commit",
        on_commit,
    )

    signals._schedule_cache_invalidation()  # noqa: SLF001

    assert callbacks == [
        invalidate_configuration_cache,
    ]


def test_scheduled_callback_performs_invalidation_when_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scheduled callback should perform semantic cache invalidation."""
    callbacks: list[Callable[[], Any]] = []
    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "new-generation"

    def on_commit(
        callback: Callable[[], Any],
    ) -> None:
        callbacks.append(
            callback,
        )

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    monkeypatch.setattr(
        transaction,
        "on_commit",
        on_commit,
    )

    signals._schedule_cache_invalidation()  # noqa: SLF001

    assert invalidations == 0
    assert len(callbacks) == 1

    callbacks[0]()

    assert invalidations == 1


def test_model_change_handler_schedules_invalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model mutation handlers should schedule one invalidation."""
    calls = 0

    def schedule() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        signals,
        "_schedule_cache_invalidation",
        schedule,
    )

    signals.invalidate_on_model_change(
        sender=Launchpad,
        instance=object(),
        created=True,
    )

    assert calls == 1


@pytest.mark.parametrize(
    "action",
    [
        "post_add",
        "post_remove",
        "post_clear",
    ],
)
def test_completed_m2m_actions_schedule_invalidation(
    action: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completed visibility-relation changes should invalidate configuration."""
    calls = 0

    def schedule() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        signals,
        "_schedule_cache_invalidation",
        schedule,
    )

    signals._invalidate_on_m2m_change(  # noqa: SLF001
        action=action,
    )

    assert calls == 1


@pytest.mark.parametrize(
    "action",
    [
        "pre_add",
        "pre_remove",
        "pre_clear",
    ],
)
def test_pre_m2m_actions_do_not_schedule_invalidation(
    action: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-change M2M signals should not invalidate configuration."""
    calls = 0

    def schedule() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        signals,
        "_schedule_cache_invalidation",
        schedule,
    )

    signals._invalidate_on_m2m_change(  # noqa: SLF001
        action=action,
    )

    assert calls == 0


def test_unknown_m2m_action_does_not_schedule_invalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected M2M actions should fail closed without invalidating."""
    calls = 0

    def schedule() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        signals,
        "_schedule_cache_invalidation",
        schedule,
    )

    signals._invalidate_on_m2m_change(  # noqa: SLF001
        action="unknown",
    )

    assert calls == 0


def test_navigation_link_relation_handler_delegates_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NavigationLink M2M receiver should delegate the signal action."""
    actions: list[str] = []

    def invalidate_on_m2m_change(
        *,
        action: str,
    ) -> None:
        actions.append(
            action,
        )

    monkeypatch.setattr(
        signals,
        "_invalidate_on_m2m_change",
        invalidate_on_m2m_change,
    )

    signals.invalidate_navigation_link_visibility_relations(
        sender=NavigationLink.users.through,
        action="post_add",
        instance=object(),
        reverse=False,
        model=object,
        pk_set={
            1,
        },
    )

    assert actions == [
        "post_add",
    ]


def test_launchpad_node_relation_handler_delegates_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LaunchpadNode M2M receiver should delegate the signal action."""
    actions: list[str] = []

    def invalidate_on_m2m_change(
        *,
        action: str,
    ) -> None:
        actions.append(
            action,
        )

    monkeypatch.setattr(
        signals,
        "_invalidate_on_m2m_change",
        invalidate_on_m2m_change,
    )

    signals.invalidate_launchpad_node_visibility_relations(
        sender=LaunchpadNode.groups.through,
        action="post_remove",
        instance=object(),
        reverse=False,
        model=object,
        pk_set={
            1,
        },
    )

    assert actions == [
        "post_remove",
    ]


@pytest.mark.django_db(transaction=True)
def test_launchpad_save_signal_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving a Launchpad should trigger registered cache invalidation."""
    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    Launchpad.objects.create(
        code="home",
        title="Home",
    )

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_launchpad_update_signal_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Updating a Launchpad through save() should invalidate configuration."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    launchpad.title = "Updated Home"
    launchpad.save()

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_launchpad_delete_signal_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a Launchpad should invalidate configuration."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    launchpad.delete()

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_navigation_link_save_signal_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving a NavigationLink should trigger invalidation."""
    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    NavigationLink.objects.create(
        code="reports",
        title="Reports",
        url_type=NavigationLink.URLType.RAW,
        url_value="/reports/",
    )

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_navigation_link_delete_signal_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a NavigationLink should trigger invalidation."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    link.delete()

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_launchpad_node_save_signal_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving a LaunchpadNode should trigger invalidation."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    LaunchpadNode.objects.create(
        launchpad=launchpad,
        navigation_link=link,
        kind=LaunchpadNode.Kind.LINK,
    )

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_launchpad_node_delete_signal_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a LaunchpadNode should trigger invalidation."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    node.delete()

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_navigation_link_user_add_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding a visible user to a NavigationLink should invalidate cache."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    user = create_user(
        username="visible-user",
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    link.users.add(
        user,
    )

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_navigation_link_user_remove_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing a visible user from a NavigationLink should invalidate cache."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    user = create_user(
        username="visible-user",
    )

    link.users.add(
        user,
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    link.users.remove(
        user,
    )

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_navigation_link_user_clear_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clearing visible users from a NavigationLink should invalidate cache."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    user = create_user(
        username="visible-user",
    )

    link.users.add(
        user,
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    link.users.clear()

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_navigation_link_group_change_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NavigationLink group membership changes should invalidate cache."""
    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    group = create_group(
        name="report-users",
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    link.groups.add(
        group,
    )

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_launchpad_node_user_change_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LaunchpadNode explicit-user changes should invalidate cache."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    user = create_user(
        username="visible-user",
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    node.users.add(
        user,
    )

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_launchpad_node_group_change_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LaunchpadNode group changes should invalidate cache."""
    launchpad = create_launchpad(
        code="home",
        title="Home",
    )

    link = create_navigation_link(
        code="reports",
        title="Reports",
    )

    node = create_link_node(
        launchpad=launchpad,
        navigation_link=link,
    )

    group = create_group(
        name="report-users",
    )

    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    node.groups.add(
        group,
    )

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_invalidation_occurs_only_after_transaction_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache generation should not change before a transaction commits."""
    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    with transaction.atomic():
        Launchpad.objects.create(
            code="home",
            title="Home",
        )

        assert invalidations == 0

    assert invalidations == 1


@pytest.mark.django_db(transaction=True)
def test_rolled_back_transaction_does_not_invalidate_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rolled-back configuration mutation should not invalidate cache."""
    invalidations = 0

    def invalidate_configuration_cache() -> str:
        nonlocal invalidations
        invalidations += 1
        return "generation"

    monkeypatch.setattr(
        signals,
        "invalidate_configuration_cache",
        invalidate_configuration_cache,
    )

    with (  # noqa: PT012
        pytest.raises(
            RuntimeError,
            match="rollback",
        ),
        transaction.atomic(),
    ):
        Launchpad.objects.create(
            code="home",
            title="Home",
        )

        msg = "rollback"
        raise RuntimeError(msg)

    assert invalidations == 0


def test_signals_module_exports_expected_symbols() -> None:
    """The signals module should expose only its intentional receiver API."""
    assert signals.__all__ == [
        "invalidate_launchpad_node_visibility_relations",
        "invalidate_navigation_link_visibility_relations",
        "invalidate_on_model_change",
    ]
