"""Configuration dictionaries for modal creation and search functionality."""

from ..forms import (
    AssetForm,
    AssetModelForm,
    CategoryForm,
    CompanyForm,
    ComponentForm,
    ComponentTypeForm,
    DepartmentForm,
    EmployeeForm,
    LocationForm,
    PurchaseInvoiceForm,
    RequisitionForm,
    VendorForm,
)
from ..models import (
    Asset,
    AssetModel,
    Category,
    Company,
    Component,
    ComponentType,
    Department,
    Employee,
    Location,
    PurchaseInvoice,
    Requisition,
    Vendor,
)


# ============================================================================
# MODAL INLINE-CREATE CONFIGURATIONS
# ============================================================================

# Maps the same model keys used by data-searchable / _SEARCH_CONFIGS to the
# form class needed to create a new instance inline.  The JS widget reads the
# key from the <select data-searchable="…"> attribute so the mapping is
# consistent across search and creation.

MODAL_CREATE_CONFIGS = {
    "company":           {"form_class": CompanyForm,              "title": "new company"},
    "asset_model":       {"form_class": AssetModelForm,           "title": "new asset model"},
    "employee":          {"form_class": EmployeeForm,             "title": "new employee"},
    "location":          {"form_class": LocationForm,             "title": "new location"},
    "category":          {"form_class": CategoryForm,             "title": "new category"},
    "department":        {"form_class": DepartmentForm,           "title": "new department"},
    "vendor":            {"form_class": VendorForm,               "title": "new vendor"},
    "component_type":    {"form_class": ComponentTypeForm,        "title": "new component type"},
    "requisition":       {"form_class": RequisitionForm,          "title": "new requisition"},
    "invoice":           {"form_class": PurchaseInvoiceForm,      "title": "new invoice"},
    "asset":             {"form_class": AssetForm,                "title": "new asset"},
    "component":         {"form_class": ComponentForm,            "title": "new component"},
}


# ============================================================================
# SEARCH API CONFIGURATIONS
# ============================================================================

# Each key maps to the model, the fields to search on (icontains),
# optional default queryset filters, select_related, ordering, and
# a whitelist of extra filter kwargs the client may pass via
# ?filter_<field>=<value>.

SEARCH_CONFIGS = {
    "company": {
        "model": Company,
        "search_fields": ["name", "code"],
        "default_filters": {"is_active": True},
        "order_by": ["name"],
    },
    "asset_model": {
        "model": AssetModel,
        "search_fields": ["manufacturer", "model_name", "model_number", "category__name"],
        "select_related": ["category"],
        "order_by": ["manufacturer", "model_name"],
    },
    "employee": {
        "model": Employee,
        "search_fields": ["name", "employee_id", "email", "department__name",
                          "position", "company__name", "company__code", "phone"],
        "default_filters": {"status": "active"},
        "order_by": ["name"],
    },
    "location": {
        "model": Location,
        "search_fields": ["name", "city"],
        "order_by": ["name"],
    },
    "requisition": {
        "model": Requisition,
        "search_fields": ["requisition_number"],
        "order_by": ["-requisition_date"],
    },
    "invoice": {
        "model": PurchaseInvoice,
        "search_fields": ["invoice_number", "vendor__vendor_name"],
        "select_related": ["vendor"],
        "order_by": ["-invoice_date"],
    },
    "category": {
        "model": Category,
        "search_fields": ["name"],
        "order_by": ["name"],
    },
    "asset": {
        "model": Asset,
        "search_fields": ["asset_tag", "serial_number", "asset_model__category__name",
                          "asset_model__model_name", "asset_model__manufacturer",
                          "assigned_to__name", "assigned_to__employee_id"],
        "select_related": ["asset_model"],
        "order_by": ["asset_tag"],
        "allowed_filters": ["company"],
    },
    "component_type": {
        "model": ComponentType,
        "search_fields": ["type_name"],
        "order_by": ["type_name"],
    },
    "department": {
        "model": Department,
        "search_fields": ["name", "company__name", "company__code"],
        "select_related": ["company"],
        "order_by": ["company__code", "name"],
    },
    "vendor": {
        "model": Vendor,
        "search_fields": ["vendor_name", "contact_person"],
        "order_by": ["vendor_name"],
    },
    "component": {
        "model": Component,
        "search_fields": [
            "component_tag",
            "manufacturer",
            "model",
            "serial_number",
            "component_type__type_name",
        ],
        "select_related": ["component_type"],
        "order_by": ["component_tag"],
        "allowed_filters": ["parent_asset__company"],
    },
}
