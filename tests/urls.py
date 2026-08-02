"""
tests/urls.py

Minimal URL configuration for the Launchpad test suite.
"""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path


def home_view(request: object) -> HttpResponse:
    """Return a minimal response for named-URL tests."""
    return HttpResponse("Home")


urlpatterns = [
    path("", home_view, name="home"),
    path("admin/", admin.site.urls),
]
