"""
src/launchpad/signals.py

Cache invalidation signals for django-launchpad.

Launchpad configuration is read frequently and changes comparatively rarely.
Persistent configuration caching therefore requires reliable invalidation when
Launchpad-owned models or visibility relationships change.

Invalidation is scheduled with ``transaction.on_commit()`` so a new cache
generation is not exposed before the database mutation that caused it has
successfully committed.

Covered mutations:

- Launchpad save/delete
- NavigationLink save/delete
- LaunchpadNode save/delete
- NavigationLink users/groups M2M changes
- LaunchpadNode users/groups M2M changes

Bulk operations that bypass Django model signals, such as ``QuerySet.update()``
or direct SQL, must call ``invalidate_configuration_cache()`` explicitly.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
)
from django.dispatch import receiver

from launchpad.cache import invalidate_configuration_cache
from launchpad.models import (
    Launchpad,
    LaunchpadNode,
    NavigationLink,
)


def _schedule_cache_invalidation() -> None:
    """
    Schedule Launchpad configuration invalidation after transaction commit.

    ``on_commit`` prevents a cache generation from advancing while the
    database transaction that caused the invalidation is still pending.

    Outside an explicit transaction, Django executes the callback
    immediately.
    """
    transaction.on_commit(
        invalidate_configuration_cache,
    )


@receiver(
    post_save,
    sender=Launchpad,
)
@receiver(
    post_delete,
    sender=Launchpad,
)
@receiver(
    post_save,
    sender=NavigationLink,
)
@receiver(
    post_delete,
    sender=NavigationLink,
)
@receiver(
    post_save,
    sender=LaunchpadNode,
)
@receiver(
    post_delete,
    sender=LaunchpadNode,
)
def invalidate_on_model_change(
    sender: type[Any],
    **kwargs: Any,
) -> None:
    """
    Invalidate cached configuration after a Launchpad model mutation.

    The signal intentionally treats all saves and deletes as globally
    invalidating because cache generations make whole-configuration
    invalidation cheap and deterministic.
    """
    del sender
    del kwargs

    _schedule_cache_invalidation()


_M2M_INVALIDATION_ACTIONS = {
    "post_add",
    "post_remove",
    "post_clear",
}


def _invalidate_on_m2m_change(
    *,
    action: str,
) -> None:
    """Invalidate configuration after relevant completed M2M mutations."""
    if action not in _M2M_INVALIDATION_ACTIONS:
        return

    _schedule_cache_invalidation()


@receiver(
    m2m_changed,
    sender=NavigationLink.users.through,
)
@receiver(
    m2m_changed,
    sender=NavigationLink.groups.through,
)
def invalidate_navigation_link_visibility_relations(
    sender: type[Any],
    *,
    action: str,
    **kwargs: Any,
) -> None:
    """Invalidate cache after NavigationLink user/group membership changes."""
    del sender
    del kwargs

    _invalidate_on_m2m_change(
        action=action,
    )


@receiver(
    m2m_changed,
    sender=LaunchpadNode.users.through,
)
@receiver(
    m2m_changed,
    sender=LaunchpadNode.groups.through,
)
def invalidate_launchpad_node_visibility_relations(
    sender: type[Any],
    *,
    action: str,
    **kwargs: Any,
) -> None:
    """Invalidate cache after LaunchpadNode user/group membership changes."""
    del sender
    del kwargs

    _invalidate_on_m2m_change(
        action=action,
    )


__all__ = [
    "invalidate_launchpad_node_visibility_relations",
    "invalidate_navigation_link_visibility_relations",
    "invalidate_on_model_change",
]
