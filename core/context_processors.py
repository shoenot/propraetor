"""
Context processors for propraetor.

Exposes the centralized navigation configuration to templates so the menu can
be rendered from a single source of truth.
"""

from propraetor.navigation import build_navigation


def navigation(_request):
    """
    Add navigation data to the template context.

    Returns a dictionary with a ``navigation`` key containing a tuple of
    navigation items (links and dropdowns) represented as plain dictionaries.
    """
    return {
        "navigation": build_navigation(),
    }