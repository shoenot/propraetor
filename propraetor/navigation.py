"""
Centralized navigation configuration for primary links and dropdown menus.

This module defines a small schema for navigation items so templates or views
can render menus from a single source of truth. Each entry can be either a
simple link or a dropdown that contains nested links. The `active_paths`
collection supports prefix matching (see `nav_tags.active_path` for details).
"""

from dataclasses import dataclass, field
from django.urls import reverse_lazy


@dataclass(frozen=True)
class NavLink:
    """A single navigation link."""
    label: str
    href: str
    active_paths: tuple = field(default_factory=tuple)
    icon: str = None  # Reserved for future icon support

    def as_dict(self):
        return {
            "type": "link",
            "label": self.label,
            "href": self.href,
            "active_paths": self.active_paths,
            "icon": self.icon,
        }


@dataclass(frozen=True)
class NavDropdown:
    """A dropdown navigation group containing multiple links."""
    label: str
    items: tuple
    active_paths: tuple = field(default_factory=tuple)
    icon: str = None  # Reserved for future icon support

    def as_dict(self):
        return {
            "type": "dropdown",
            "label": self.label,
            "items": tuple(item.as_dict() for item in self.items),
            "active_paths": self.active_paths or self._infer_active_paths(),
            "icon": self.icon,
        }

    def _infer_active_paths(self):
        """If active paths are not explicitly provided, derive from children."""
        paths = []
        for item in self.items:
            paths.extend(item.active_paths or (item.href,))
        return tuple(paths)


def _paths(*parts):
    """Helper to create immutable path tuples."""
    return tuple(parts)


NAVIGATION = (
    NavLink(label="users", href=reverse_lazy("propraetor:users_list"), active_paths=_paths("/users/")),
    NavLink(label="assets", href=reverse_lazy("propraetor:assets_list"), active_paths=_paths("/assets/")),
    NavLink(label="components", href=reverse_lazy("propraetor:components_list"), active_paths=_paths("/components/")),
    NavDropdown(
        label="organization",
        active_paths=_paths(
            "/departments/",
            "/companies/",
            "/locations/",
            "/asset_models/",
            "/component_types/",
            "/categories/",
            "/spare-parts/",
            "/maintenance/",
        ),
        items=(
            NavLink(label="departments", href=reverse_lazy("propraetor:departments_list"), active_paths=_paths("/departments/")),
            NavLink(label="companies", href=reverse_lazy("propraetor:companies_list"), active_paths=_paths("/companies/")),
            NavLink(label="locations", href=reverse_lazy("propraetor:locations_list"), active_paths=_paths("/locations/")),
            NavLink(label="asset_models", href=reverse_lazy("propraetor:asset_models_list"), active_paths=_paths("/asset_models/")),
            NavLink(label="component_types", href=reverse_lazy("propraetor:component_types_list"), active_paths=_paths("/component_types/")),
            NavLink(label="categories", href=reverse_lazy("propraetor:categories_list"), active_paths=_paths("/categories/")),
            NavLink(label="spare_parts", href=reverse_lazy("propraetor:spare_parts_list"), active_paths=_paths("/spare-parts/")),
            NavLink(label="maintenance", href=reverse_lazy("propraetor:maintenance_list"), active_paths=_paths("/maintenance/")),
        ),
    ),
    NavDropdown(
        label="procurement",
        active_paths=_paths(
            "/requisitions/",
            "/invoices/",
            "/vendors/",
        ),
        items=(
            NavLink(label="requisitions", href=reverse_lazy("propraetor:requisition_list"), active_paths=_paths("/requisitions/")),
            NavLink(label="invoices", href=reverse_lazy("propraetor:invoices_list"), active_paths=_paths("/invoices/")),
            NavLink(label="vendors", href=reverse_lazy("propraetor:vendors_list"), active_paths=_paths("/vendors/")),
        ),
    ),
)


def build_navigation():
    """
    Return the full navigation structure as plain dictionaries,
    suitable for serializing or passing to templates.
    """
    return tuple(item.as_dict() for item in NAVIGATION)


__all__ = [
    "NavLink",
    "NavDropdown",
    "NAVIGATION",
    "build_navigation",
]