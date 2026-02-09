from django.shortcuts import redirect
from django.conf import settings

from propraetor.activity import set_current_user


class ActivityUserMiddleware:
    """
    Stores the current authenticated user in thread-local storage so that
    Django signal handlers (which have no access to the request) can stamp
    the actor on every ``ActivityLog`` row.

    Must be placed **after** ``AuthenticationMiddleware`` in MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_user(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)


class LoginRequiredMiddleware:
    """
    Middleware that redirects unauthenticated users to the login page
    for all views except those whose URL paths are explicitly exempt.

    Exempt paths are defined in settings.LOGIN_EXEMPT_URLS and should
    be a list of URL path prefixes (e.g. ['/login/', '/admin/']).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            login_url = getattr(settings, "LOGIN_URL", "/login/")
            exempt_urls = getattr(settings, "LOGIN_EXEMPT_URLS", [login_url])

            path = request.path

            # Allow access to exempt paths without authentication
            if not any(path.startswith(url) for url in exempt_urls):
                # Preserve the original URL so we can redirect back after login
                return redirect(f"{login_url}?next={path}")

        return self.get_response(request)