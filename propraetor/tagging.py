"""
Tag prefix resolution and tag generation for assets and components.

Reads ``tag_prefixes.toml`` from the project root and generates unique,
sequentially-numbered tags whose prefix is determined by the resolution
hierarchy:

    Department → Company → Global default

Usage::

    from propraetor.tagging import generate_asset_tag, generate_component_tag

    tag = generate_asset_tag(company=some_company)
    tag = generate_component_tag(company=some_company, department=some_dept)
"""

import logging
import time
import tomllib
from pathlib import Path

from django.conf import settings as django_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in fallbacks (used when the config file is missing or incomplete)
# ---------------------------------------------------------------------------
_FALLBACK_DEFAULTS = {
    "asset": "ASSET",
    "component": "COMP",
}
_FALLBACK_TAG_SETTINGS = {
    "sequence_digits": 5,
    "separator": "",
}

# ---------------------------------------------------------------------------
# Config loading & caching
# ---------------------------------------------------------------------------
_config_cache: dict | None = None
_config_mtime: float = 0.0


def _config_path() -> Path:
    return Path(django_settings.BASE_DIR) / "tag_prefixes.toml"


def load_config(*, force_reload: bool = False) -> dict:
    """Load and cache ``tag_prefixes.toml``.

    The file's mtime is checked on every call so edits take effect without
    restarting the server.  Pass *force_reload=True* to bypass the cache
    unconditionally (useful in tests).
    """
    global _config_cache, _config_mtime

    path = _config_path()

    if not path.exists():
        logger.debug("Tag config file not found at %s — using built-in fallbacks.", path)
        _config_cache = {}
        _config_mtime = 0.0
        return _config_cache

    try:
        current_mtime = path.stat().st_mtime
    except OSError:
        current_mtime = 0.0

    if _config_cache is not None and not force_reload and current_mtime == _config_mtime:
        return _config_cache

    try:
        with open(path, "rb") as fh:
            _config_cache = tomllib.load(fh)
        _config_mtime = current_mtime
        logger.info("Loaded tag prefix config from %s", path)
    except Exception:
        logger.exception("Failed to parse %s — using built-in fallbacks.", path)
        _config_cache = {}
        _config_mtime = 0.0

    return _config_cache


def clear_config_cache() -> None:
    """Reset the cached config.  Mainly useful in tests."""
    global _config_cache, _config_mtime
    _config_cache = None
    _config_mtime = 0.0


# ---------------------------------------------------------------------------
# Tag settings helpers
# ---------------------------------------------------------------------------

def get_tag_settings() -> dict:
    """Return the ``[tag_settings]`` section merged with fallback defaults."""
    config = load_config()
    section = config.get("tag_settings", {})
    return {
        "sequence_digits": section.get("sequence_digits", _FALLBACK_TAG_SETTINGS["sequence_digits"]),
        "separator": section.get("separator", _FALLBACK_TAG_SETTINGS["separator"]),
    }


# ---------------------------------------------------------------------------
# Prefix resolution
# ---------------------------------------------------------------------------

def resolve_prefix(
    entity_type: str,
    *,
    company_code: str | None = None,
    department_name: str | None = None,
) -> str:
    """Resolve the tag prefix for *entity_type* (``"asset"`` or ``"component"``).

    Resolution order (most specific wins):

    1. ``[companies.<company_code>.departments.<department_name>]``
    2. ``[companies.<company_code>]``
    3. ``[defaults]``
    4. Built-in fallback

    Parameters
    ----------
    entity_type:
        ``"asset"`` or ``"component"``.
    company_code:
        The ``Company.code`` value.  If *None* or empty, company/department
        look-ups are skipped.
    department_name:
        The ``Department.name`` value.  Ignored when *company_code* is not
        provided.
    """
    config = load_config()
    defaults = config.get("defaults", {})

    # 3/4 — global default, then built-in fallback
    prefix = defaults.get(entity_type, _FALLBACK_DEFAULTS.get(entity_type, "TAG"))

    if company_code:
        company_section = config.get("companies", {}).get(company_code, {})

        # 2 — company-level override
        if entity_type in company_section:
            prefix = company_section[entity_type]

        # 1 — department-level override (most specific)
        if department_name:
            dept_section = company_section.get("departments", {}).get(department_name, {})
            if entity_type in dept_section:
                prefix = dept_section[entity_type]

    return prefix


# ---------------------------------------------------------------------------
# Tag generation (generic)
# ---------------------------------------------------------------------------

def _generate_tag(
    entity_type: str,
    model_class,
    tag_field: str,
    *,
    company_code: str | None = None,
    department_name: str | None = None,
) -> str:
    """Generate the next unique tag for *entity_type*.

    Scans the database for the highest existing sequence number under the
    resolved prefix and returns ``prefix + separator + (max+1)``.
    """
    prefix = resolve_prefix(
        entity_type,
        company_code=company_code,
        department_name=department_name,
    )
    tag_settings = get_tag_settings()
    separator = tag_settings["separator"]
    digits = tag_settings["sequence_digits"]

    full_prefix = f"{prefix}{separator}"

    # ------------------------------------------------------------------
    # Find the highest existing sequence number for this prefix
    # ------------------------------------------------------------------
    existing_tags = list(
        model_class.objects.filter(**{f"{tag_field}__startswith": full_prefix})
        .order_by(f"-{tag_field}")
        .values_list(tag_field, flat=True)[:100]
    )

    max_seq = 0
    prefix_len = len(full_prefix)
    for tag in existing_tags:
        suffix = tag[prefix_len:]
        try:
            seq = int(suffix)
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue

    # ------------------------------------------------------------------
    # Generate a candidate and verify uniqueness
    # ------------------------------------------------------------------
    for attempt in range(500):
        candidate = f"{full_prefix}{max_seq + attempt + 1:0{digits}d}"
        if not model_class.objects.filter(**{tag_field: candidate}).exists():
            return candidate

    # Absolute fallback — timestamp-based to guarantee uniqueness
    fallback = f"{full_prefix}{int(time.time())}"
    logger.warning(
        "Exhausted 500 sequential candidates for prefix '%s'; "
        "falling back to timestamp-based tag: %s",
        full_prefix,
        fallback,
    )
    return fallback


# ---------------------------------------------------------------------------
# Convenience helpers for extracting context from model instances
# ---------------------------------------------------------------------------

def _extract_company_code(company) -> str | None:
    """Return *company.code* if *company* is a model instance with a code."""
    if company is not None and getattr(company, "code", None):
        return company.code
    return None


def _extract_department_name(department) -> str | None:
    """Return *department.name* if *department* is a model instance."""
    if department is not None and getattr(department, "name", None):
        return department.name
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_asset_tag(*, company=None, department=None) -> str:
    """Generate the next unique asset tag.

    Parameters
    ----------
    company:
        A ``Company`` model instance (or *None*).
    department:
        A ``Department`` model instance (or *None*).  Falls back to company
        level (then global) if not provided.
    """
    from propraetor.models import Asset  # noqa: avoid circular import

    return _generate_tag(
        "asset",
        Asset,
        "asset_tag",
        company_code=_extract_company_code(company),
        department_name=_extract_department_name(department),
    )


def generate_component_tag(*, company=None, department=None) -> str:
    """Generate the next unique component tag.

    Parameters
    ----------
    company:
        A ``Company`` model instance (or *None*).
    department:
        A ``Department`` model instance (or *None*).
    """
    from propraetor.models import Component  # noqa: avoid circular import

    return _generate_tag(
        "component",
        Component,
        "component_tag",
        company_code=_extract_company_code(company),
        department_name=_extract_department_name(department),
    )


def generate_asset_tag_for_instance(asset) -> str:
    """Derive company/department context from an ``Asset`` instance and
    generate a tag.

    Context resolution:

    * **Company** — ``asset.company``
    * **Department** — ``asset.assigned_to.department`` (if the asset is
      assigned to an employee who belongs to a department)
    """
    company = getattr(asset, "company", None)
    department = None
    assigned_to = getattr(asset, "assigned_to", None)
    if assigned_to is not None:
        department = getattr(assigned_to, "department", None)
    return generate_asset_tag(company=company, department=department)


def generate_component_tag_for_instance(component) -> str:
    """Derive company/department context from a ``Component`` instance and
    generate a tag.

    Context resolution (via ``parent_asset``):

    * **Company** — ``component.parent_asset.company``
    * **Department** — ``component.parent_asset.assigned_to.department``
    """
    company = None
    department = None
    parent = getattr(component, "parent_asset", None)
    if parent is not None:
        company = getattr(parent, "company", None)
        assigned_to = getattr(parent, "assigned_to", None)
        if assigned_to is not None:
            department = getattr(assigned_to, "department", None)
    return generate_component_tag(company=company, department=department)