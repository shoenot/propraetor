"""
Views package for the application.

This package organizes views into logical modules:
- api.py: AJAX/API endpoints (search, modal create)
- utils.py: Helper functions and utilities
- configs.py: Configuration dicts for modal create and search
- assets.py: Asset CRUD operations
- asset_models.py: Asset model CRUD operations
- components.py: Component CRUD operations
- component_types.py: Component type CRUD operations
- employees.py: Employee/User CRUD operations
- locations.py: Location CRUD operations
- companies.py: Company CRUD operations
- departments.py: Department CRUD operations
- categories.py: Category CRUD operations
- vendors.py: Vendor CRUD operations
- invoices.py: Invoice operations
- invoices_extended.py: Invoice line items, receiving, and requisition item deletion
- requisitions.py: Requisition and requisition item operations
- maintenance.py: Maintenance record operations
- spare_parts.py: Spare parts inventory operations
- activity_logs.py: Activity log views
- dashboard.py: Dashboard and reporting views
"""

# ── API ──────────────────────────────────────────────────────────────────────
# ── Activity Logs ────────────────────────────────────────────────────────────
from .activity_logs import activity_list
from .api import api_search, modal_create

# ── Asset Models ─────────────────────────────────────────────────────────────
from .asset_models import (
    asset_model_create,
    asset_model_delete,
    asset_model_details,
    asset_model_edit,
    asset_models_bulk_delete,
    asset_models_list,
)

# ── Assets ───────────────────────────────────────────────────────────────────
from .assets import (
    asset_change_status,
    asset_create,
    asset_delete,
    asset_details,
    asset_details_ht,
    asset_duplicate,
    asset_edit,
    asset_transfer_location,
    asset_unassign,
    assets_bulk_delete,
    assets_bulk_status,
    assets_bulk_unassign,
    assets_list,
)

# ── Categories ───────────────────────────────────────────────────────────────
from .categories import (
    categories_bulk_delete,
    categories_list,
    category_create,
    category_delete,
    category_details,
    category_edit,
)

# ── Companies ────────────────────────────────────────────────────────────────
from .companies import (
    companies_bulk_delete,
    companies_list,
    company_create,
    company_delete,
    company_details,
    company_edit,
)

# ── Component Types ──────────────────────────────────────────────────────────
from .component_types import (
    component_type_create,
    component_type_delete,
    component_type_details,
    component_type_edit,
    component_types_bulk_delete,
    component_types_list,
)

# ── Components ───────────────────────────────────────────────────────────────
from .components import (
    component_change_status,
    component_create,
    component_delete,
    component_details,
    component_edit,
    component_unassign,
    components_bulk_delete,
    components_bulk_unassign,
    components_list,
)

# ── Dashboard ────────────────────────────────────────────────────────────────
from .dashboard import dashboard

# ── Departments ──────────────────────────────────────────────────────────────
from .departments import (
    department_create,
    department_delete,
    department_details,
    department_edit,
    departments_bulk_delete,
    departments_list,
)

# ── Users / Employees ────────────────────────────────────────────────────────
from .employees import (
    user_activate,
    user_create,
    user_deactivate,
    user_delete,
    user_details,
    user_edit,
    users_bulk_deactivate,
    users_bulk_delete,
    users_list,
)

# ── Invoices ─────────────────────────────────────────────────────────────────
from .invoices import (
    invoice_create,
    invoice_delete,
    invoice_details,
    invoice_duplicate,
    invoice_edit,
    invoice_mark_paid,
    invoices_bulk_delete,
    invoices_bulk_mark_paid,
    invoices_list,
)

# ── Invoice Line Items & Receiving ───────────────────────────────────────────
from .invoices_extended import (
    invoice_line_item_create,
    invoice_line_item_delete,
    invoice_line_item_edit,
    receive_invoice_items,
    requisition_item_delete,
)

# ── Locations ────────────────────────────────────────────────────────────────
from .locations import (
    location_create,
    location_delete,
    location_details,
    location_edit,
    locations_bulk_delete,
    locations_list,
)

# ── Maintenance ──────────────────────────────────────────────────────────────
from .maintenance import (
    maintenance_bulk_delete,
    maintenance_create,
    maintenance_delete,
    maintenance_details,
    maintenance_edit,
    maintenance_list,
)

# ── Requisitions ─────────────────────────────────────────────────────────────
from .requisitions import (
    requisition_cancel,
    requisition_create,
    requisition_delete,
    requisition_details,
    requisition_edit,
    requisition_fulfill,
    requisition_item_create,
    requisitions_bulk_cancel,
    requisitions_bulk_delete,
    requisitions_bulk_fulfill,
    requisitions_list,
)

# ── Spare Parts ──────────────────────────────────────────────────────────────
from .spare_parts import (
    spare_part_create,
    spare_part_delete,
    spare_part_details,
    spare_part_edit,
    spare_parts_bulk_delete,
    spare_parts_list,
)

# ── Utilities ────────────────────────────────────────────────────────────────
from .utils import get_base_template, htmx_redirect

# ── Vendors ──────────────────────────────────────────────────────────────────
from .vendors import (
    vendor_create,
    vendor_delete,
    vendor_details,
    vendor_edit,
    vendors_bulk_delete,
    vendors_list,
)

__all__ = [
    # API
    "api_search",
    "modal_create",
    # Utils
    "get_base_template",
    "htmx_redirect",
    # Dashboard
    "dashboard",
    # Activity
    "activity_list",
    # Users / Employees
    "users_list",
    "user_create",
    "user_edit",
    "user_details",
    "user_delete",
    "user_activate",
    "user_deactivate",
    "users_bulk_deactivate",
    "users_bulk_delete",
    # Assets
    "assets_list",
    "asset_create",
    "asset_edit",
    "asset_details",
    "asset_details_ht",
    "asset_delete",
    "asset_transfer_location",
    "asset_unassign",
    "asset_change_status",
    "asset_duplicate",
    "assets_bulk_unassign",
    "assets_bulk_delete",
    "assets_bulk_status",
    # Asset Models
    "asset_models_list",
    "asset_model_create",
    "asset_model_edit",
    "asset_model_details",
    "asset_model_delete",
    "asset_models_bulk_delete",
    # Components
    "components_list",
    "component_create",
    "component_edit",
    "component_details",
    "component_delete",
    "component_unassign",
    "component_change_status",
    "components_bulk_unassign",
    "components_bulk_delete",
    # Component Types
    "component_types_list",
    "component_type_create",
    "component_type_edit",
    "component_type_details",
    "component_type_delete",
    "component_types_bulk_delete",
    # Requisitions
    "requisitions_list",
    "requisition_create",
    "requisition_edit",
    "requisition_details",
    "requisition_delete",
    "requisition_item_create",
    "requisition_fulfill",
    "requisition_cancel",
    "requisitions_bulk_delete",
    "requisitions_bulk_cancel",
    "requisitions_bulk_fulfill",
    # Invoices
    "invoices_list",
    "invoice_create",
    "invoice_edit",
    "invoice_details",
    "invoice_delete",
    "invoices_bulk_delete",
    "invoices_bulk_mark_paid",
    "invoice_mark_paid",
    "invoice_duplicate",
    # Invoice Line Items & Receiving
    "invoice_line_item_create",
    "invoice_line_item_edit",
    "invoice_line_item_delete",
    "receive_invoice_items",
    "requisition_item_delete",
    # Locations
    "locations_list",
    "location_create",
    "location_edit",
    "location_details",
    "location_delete",
    "locations_bulk_delete",
    # Departments
    "departments_list",
    "department_create",
    "department_edit",
    "department_details",
    "department_delete",
    "departments_bulk_delete",
    # Vendors
    "vendors_list",
    "vendor_create",
    "vendor_edit",
    "vendor_details",
    "vendor_delete",
    "vendors_bulk_delete",
    # Companies
    "companies_list",
    "company_create",
    "company_edit",
    "company_details",
    "company_delete",
    "companies_bulk_delete",
    # Categories
    "categories_list",
    "category_create",
    "category_edit",
    "category_details",
    "category_delete",
    "categories_bulk_delete",
    # Spare Parts
    "spare_parts_list",
    "spare_part_create",
    "spare_part_edit",
    "spare_part_details",
    "spare_part_delete",
    "spare_parts_bulk_delete",
    # Maintenance
    "maintenance_list",
    "maintenance_create",
    "maintenance_edit",
    "maintenance_details",
    "maintenance_delete",
    "maintenance_bulk_delete",
]
