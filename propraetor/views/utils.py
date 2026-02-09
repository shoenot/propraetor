"""Utility functions for views."""

from django.shortcuts import redirect
from django.urls import reverse
from django_htmx.http import HttpResponseClientRedirect

from ..models import ActivityLog


def get_base_template(request):
    """Return partial base for HTMX requests, full base otherwise."""
    if request.htmx:
        return "partials/partial_base.html"
    return "base.html"


def htmx_redirect(request, viewname, *args, **kwargs):
    """Redirect that works correctly for both HTMX and regular requests.

    For HTMX requests, sends an HX-Redirect header so the browser does a
    proper client-side navigation (URL bar updates, full page load).
    For regular requests, returns a normal Django redirect.
    """
    url = reverse(viewname, args=args, kwargs=kwargs)
    if request.htmx:
        return HttpResponseClientRedirect(url)
    return redirect(url)


def get_activity_qs(event_type_filter=None):
    """
    Return an ``ActivityLog`` queryset, optionally filtered by event type.
    The queryset is ordered by ``-timestamp`` (model default).
    """
    qs = ActivityLog.objects.all()
    if event_type_filter:
        qs = qs.filter(event_type=event_type_filter)
    return qs
