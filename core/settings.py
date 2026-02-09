"""
Django settings for Propraetor — Asset Management System.

Reads configuration from environment variables (with sensible defaults for
local development).  In production, set these in a `.env` file or in the
process environment.

See env.example in the project root for a documented list of every variable.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file in project root
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")


# ==============================================================================
# ENVIRONMENT HELPERS
# ==============================================================================


def _env(key, default=""):
    """Return an environment variable or *default*."""
    return os.environ.get(key, default)


def _env_bool(key, default=False):
    """Return an environment variable as a boolean."""
    return _env(key, str(default)).lower() in ("true", "1", "yes")


def _env_list(key, default="", sep=","):
    """Return an environment variable as a list of strings."""
    raw = _env(key, default)
    return [item.strip() for item in raw.split(sep) if item.strip()]


def _env_int(key, default=0):
    """Return an environment variable as an integer."""
    try:
        return int(_env(key, str(default)))
    except (ValueError, TypeError):
        return default


# ==============================================================================
# SECURITY
# ==============================================================================

SECRET_KEY = _env("SECRET_KEY")
if not SECRET_KEY and DEBUG:
    SECRET_KEY = "insecure-secret-key-do-NOT-use-in-prod"

DEBUG = _env_bool("DEBUG", False)

ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")


# ==============================================================================
# APPLICATIONS
# ==============================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "propraetor",
    "django_htmx",
]

# Conditionally add debug toolbar (dev only)
if DEBUG:
    try:
        import debug_toolbar  # noqa: F401

        INSTALLED_APPS.append("debug_toolbar")
    except ImportError:
        pass


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.ActivityUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "core.middleware.LoginRequiredMiddleware",
]

if DEBUG and "debug_toolbar" in INSTALLED_APPS:
    # Insert early, after SecurityMiddleware
    MIDDLEWARE.insert(1, "debug_toolbar.middleware.DebugToolbarMiddleware")


ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# ==============================================================================
# DATABASE
# ==============================================================================

_database_url = _env("DATABASE_URL", "")

if _database_url:
    # ---------------------------------------------------------------
    # Parse DATABASE_URL (postgres://user:pass@host:port/dbname or
    # mysql://user:pass@host:port/dbname)
    # ---------------------------------------------------------------
    from urllib.parse import urlparse

    _parsed = urlparse(_database_url)
    _ENGINE_MAP = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "mysql": "django.db.backends.mysql",
        "sqlite": "django.db.backends.sqlite3",
    }
    DATABASES = {
        "default": {
            "ENGINE": _ENGINE_MAP.get(_parsed.scheme, "django.db.backends.postgresql"),
            "NAME": _parsed.path.lstrip("/") or "propraetor",
            "USER": _parsed.username or "",
            "PASSWORD": _parsed.password or "",
            "HOST": _parsed.hostname or "localhost",
            "PORT": str(_parsed.port or ""),
        }
    }
else:
    # Default: SQLite for local development
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ==============================================================================
# PASSWORD VALIDATION
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ==============================================================================
# INTERNATIONALIZATION
# ==============================================================================

LANGUAGE_CODE = _env("LANGUAGE_CODE", "en-us")
TIME_ZONE = _env("TIME_ZONE", "Asia/Dhaka")
USE_I18N = True
USE_TZ = True


# ==============================================================================
# STATIC & MEDIA FILES
# ==============================================================================

STATIC_URL = _env("STATIC_URL", "/static/")
STATIC_ROOT = _env("STATIC_ROOT", "") or (BASE_DIR / "staticfiles")

MEDIA_URL = _env("MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ==============================================================================
# OTHER SETTINGS
# ==============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==============================================================================
# AUTHENTICATION
# ==============================================================================

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

LOGIN_EXEMPT_URLS = [
    "/login/",
    "/admin/",
    "/__debug__/",
    "/static/",
    "/media/",
    "/ht/",
]


# ==============================================================================
# DEBUG TOOLBAR
# ==============================================================================

if DEBUG and "debug_toolbar" in INSTALLED_APPS:
    INTERNAL_IPS = ["127.0.0.1", "::1"]


# ==============================================================================
# PRODUCTION SECURITY (only active when DEBUG=False)
# ==============================================================================

if not DEBUG:
    # HTTPS
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = _env_int("SECURE_HSTS_SECONDS", 0)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0

    # Cookies
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", True)

    # CSRF trusted origins
    _csrf_origins = _env("CSRF_TRUSTED_ORIGINS", "")
    if _csrf_origins:
        CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS")


# ==============================================================================
# LOGGING
# ==============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": _env("DJANGO_LOG_LEVEL", "INFO"),
        },
        "propraetor": {
            "handlers": ["console"],
            "level": _env("APP_LOG_LEVEL", "INFO"),
        },
    },
}
