"""
tests/settings.py

Minimal Django settings used exclusively for Launchpad's test suite.

These settings intentionally provide only the pieces required to
initialize Django, run migrations, and exercise the package in
isolation. They are not intended for development or production use.
"""

SECRET_KEY = "test-secret-key"  # noqa: S105

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "launchpad.apps.LaunchpadConfig",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
