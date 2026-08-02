"""
tests/test_package.py

Basic package smoke tests.
"""

from __future__ import annotations

import launchpad


def test_package_has_version() -> None:
    """The package exposes a version string."""
    assert hasattr(launchpad, "__version__")
