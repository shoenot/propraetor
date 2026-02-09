from django.contrib import admin
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    ActivityLog,
    Asset,
    AssetAssignment,
    AssetModel,
    Category,
    Company,
    Component,
    ComponentHistory,
    ComponentType,
    Department,
    Employee,
    InvoiceLineItem,
    Location,
    MaintenanceRecord,
    PurchaseInvoice,
    Requisition,
    RequisitionItem,
    SparePartsInventory,
    Vendor,
)

# ============================================================================
# CORE ADMIN
# ============================================================================


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "city", "country", "is_active", "asset_count"]
    list_filter = ["is_active", "country", "city"]
    search_fields = ["name", "code", "city"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "code", "is_active")}),
        ("Contact Details", {"fields": ("address", "city", "country", "phone")}),
        ("Additional Information", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def asset_count(self, obj):
        """Show number of assets for this company"""
        count = obj.assets.count()
        url = (
            reverse("admin:propraetor_asset_changelist")
            + f"?company__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{} assets</a>', url, count)

    asset_count.short_description = "Assets"


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "country", "asset_count", "employee_count"]
    list_filter = ["country", "city"]
    search_fields = ["name", "address", "city"]
    readonly_fields = ["created_at"]

    def asset_count(self, obj):
        return obj.assets.count()

    asset_count.short_description = "Assets"

    def employee_count(self, obj):
        return obj.employees.count()

    employee_count.short_description = "Employees"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "default_location", "employee_count"]
    list_filter = ["company"]
    search_fields = ["name", "company__name"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["company", "default_location"]

    def employee_count(self, obj):
        return obj.employees.count()

    employee_count.short_description = "Employees"


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "employee_id",
        "email",
        "company",
        "department",
        "position",
        "status",
        "assigned_assets_count",
    ]
    list_filter = ["status", "company", "department", "position"]
    search_fields = ["name", "employee_id", "email", "phone"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["company", "department", "location"]

    fieldsets = (
        (
            "Personal Information",
            {"fields": ("employee_id", "name", "email", "phone", "extension")},
        ),
        (
            "Company Information",
            {"fields": ("company", "department", "location", "position", "status")},
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if "company" not in initial:
            active_companies = Company.objects.filter(is_active=True)
            if active_companies.count() == 1:
                initial["company"] = active_companies.first().pk
        return initial

    def assigned_assets_count(self, obj):
        count = obj.assigned_assets.filter(status="active").count()
        if count > 0:
            url = (
                reverse("admin:propraetor_asset_changelist")
                + f"?assigned_to__id__exact={obj.id}"
            )
            return format_html('<a href="{}">{}</a>', url, count)
        return count

    assigned_assets_count.short_description = "Active Assets"


# ============================================================================
# ASSET ADMIN
# ============================================================================


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "model_count", "asset_count", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _model_count=Count("models", distinct=True),
            _asset_count=Count("models__assets", distinct=True),
        )

    @admin.display(description="Models", ordering="_model_count")
    def model_count(self, obj):
        return obj._model_count

    @admin.display(description="Assets", ordering="_asset_count")
    def asset_count(self, obj):
        return obj._asset_count


@admin.register(AssetModel)
class AssetModelAdmin(admin.ModelAdmin):
    list_display = [
        "display_name",
        "category",
        "manufacturer",
        "model_name",
        "model_number",
        "asset_count_display",
        "created_at",
    ]
    list_filter = ["category", "manufacturer", "created_at"]
    search_fields = ["manufacturer", "model_name", "model_number", "notes"]
    readonly_fields = ["created_at", "updated_at", "asset_count_display"]

    fieldsets = [
        (
            "Model Information",
            {"fields": ["category", "manufacturer", "model_name", "model_number"]},
        ),
        (
            "Additional Information",
            {"fields": ["notes", "asset_count_display", "created_at", "updated_at"]},
        ),
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("category").annotate(_asset_count=Count("assets"))

    @admin.display(description="Model", ordering="manufacturer")
    def display_name(self, obj):
        if obj.manufacturer:
            return f"{obj.manufacturer} {obj.model_name}"
        return obj.model_name

    @admin.display(description="Assets", ordering="_asset_count")
    def asset_count_display(self, obj):
        count = obj._asset_count
        if count > 0:
            return format_html(
                '<a href="/admin/propraetor/asset/?asset_model__id__exact={}">{} assets</a>',
                obj.id,
                count,
            )
        return "0 assets"


class ComponentInline(admin.TabularInline):
    """Show components inline when viewing an asset"""

    model = Component
    extra = 0
    fields = [
        "component_type",
        "manufacturer",
        "model",
        "specifications",
        "serial_number",
        "status",
    ]
    readonly_fields = ["created_at"]
    can_delete = False


class MaintenanceRecordInline(admin.TabularInline):
    """Show maintenance records inline when viewing an asset"""

    model = MaintenanceRecord
    extra = 0
    fields = [
        "maintenance_date",
        "maintenance_type",
        "description",
        "cost",
        "next_maintenance_date",
    ]
    readonly_fields = ["created_at"]


class AssetInline(admin.TabularInline):
    """Inline to show assets in AssetModel admin"""

    model = Asset
    extra = 0
    fields = ["asset_tag", "serial_number", "status", "assigned_to", "location"]
    readonly_fields = ["asset_tag"]
    can_delete = False
    max_num = 10  # Limit inline display

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = [
        "asset_tag",
        "display_model",
        "serial_number",
        "status",
        "assigned_to",
        "location",
        "company",
        "purchase_date",
    ]
    list_filter = [
        "status",
        "asset_model__category",
        "asset_model__manufacturer",
        "company",
        "location",
        "purchase_date",
    ]
    search_fields = [
        "asset_tag",
        "serial_number",
        "asset_model__manufacturer",
        "asset_model__model_name",
        "notes",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "category_display",
        "manufacturer_display",
        "model_name_display",
    ]

    autocomplete_fields = [
        "asset_model",
        "company",
        "location",
        "assigned_to",
        "requisition",
        "invoice",
    ]

    fieldsets = [
        (
            "Basic Information",
            {"fields": ["asset_tag", "asset_model", "serial_number", "status"]},
        ),
        (
            "Model Details (Read-only)",
            {
                "fields": [
                    "category_display",
                    "manufacturer_display",
                    "model_name_display",
                ],
                "classes": ["collapse"],
            },
        ),
        ("Assignment", {"fields": ["company", "assigned_to", "location"]}),
        (
            "Financial Information",
            {
                "fields": [
                    "purchase_date",
                    "purchase_cost",
                    "warranty_expiry_date",
                    "requisition",
                    "invoice",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Specifications",
            {
                "fields": ["attributes"],
                "classes": ["collapse"],
                "description": "Asset-specific specs (CPU, RAM, SSD, IP address, etc.)",
            },
        ),
        (
            "Notes & History",
            {"fields": ["notes", "created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "asset_model", "asset_model__category", "company", "location", "assigned_to"
        )

    @admin.display(description="Model", ordering="asset_model__manufacturer")
    def display_model(self, obj):
        return str(obj.asset_model)

    @admin.display(description="Category")
    def category_display(self, obj):
        return obj.category.name if obj.category else "-"

    @admin.display(description="Manufacturer")
    def manufacturer_display(self, obj):
        return obj.manufacturer or "(None)"

    @admin.display(description="Model Name")
    def model_name_display(self, obj):
        return obj.model_name

    # Add actions
    actions = ["mark_as_active", "mark_as_retired", "mark_as_pending"]

    @admin.action(description="Mark selected assets as Active")
    def mark_as_active(self, request, queryset):
        updated = queryset.update(status="active")
        self.message_user(request, f"{updated} assets marked as Active.")

    @admin.action(description="Mark selected assets as Retired")
    def mark_as_retired(self, request, queryset):
        updated = queryset.update(status="retired")
        self.message_user(request, f"{updated} assets marked as Retired.")

    @admin.action(description="Mark selected assets as Pending")
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status="pending")
        self.message_user(request, f"{updated} assets marked as Pending.")


# ============================================================================
# COMPONENT ADMIN
# ============================================================================


@admin.register(ComponentType)
class ComponentTypeAdmin(admin.ModelAdmin):
    list_display = ["type_name", "component_count", "spare_parts_count"]
    search_fields = ["type_name"]
    readonly_fields = ["created_at"]

    def component_count(self, obj):
        return obj.components.count()

    component_count.short_description = "Components"

    def spare_parts_count(self, obj):
        return obj.spare_parts.count()

    spare_parts_count.short_description = "Spare Parts"


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = [
        "component_type",
        "manufacturer",
        "model",
        "specifications",
        "parent_asset",
        "status",
        "installation_date",
    ]
    list_filter = ["status", "component_type", "manufacturer"]
    search_fields = [
        "serial_number",
        "manufacturer",
        "model",
        "specifications",
        "parent_asset__asset_tag",
    ]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["parent_asset", "component_type", "requisition", "invoice"]
    date_hierarchy = "installation_date"

    fieldsets = (
        (
            "Component Information",
            {
                "fields": (
                    "component_type",
                    "manufacturer",
                    "model",
                    "serial_number",
                    "specifications",
                )
            },
        ),
        (
            "Installation",
            {"fields": ("parent_asset", "status", "installation_date", "removal_date")},
        ),
        (
            "Purchase Information",
            {
                "fields": ("purchase_date", "warranty_expiry_date"),
                "classes": ("collapse",),
            },
        ),
        (
            "Procurement Tracking",
            {"fields": ("requisition", "invoice"), "classes": ("collapse",)},
        ),
        ("Additional Information", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(ComponentHistory)
class ComponentHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "component",
        "parent_asset",
        "action",
        "action_date",
        "performed_by",
    ]
    list_filter = ["action", "action_date"]
    search_fields = ["component__serial_number", "parent_asset__asset_tag"]
    readonly_fields = ["action_date"]
    autocomplete_fields = [
        "component",
        "parent_asset",
        "performed_by",
        "previous_component",
    ]
    date_hierarchy = "action_date"


@admin.register(SparePartsInventory)
class SparePartsInventoryAdmin(admin.ModelAdmin):
    list_display = [
        "component_type",
        "manufacturer",
        "model",
        "quantity_available",
        "quantity_minimum",
        "stock_status",
        "location",
    ]
    list_filter = ["component_type", "location"]
    search_fields = ["manufacturer", "model", "specifications"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["component_type", "location"]

    def stock_status(self, obj):
        """Show stock status with color coding"""
        if obj.quantity_available == 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">OUT OF STOCK</span>'
            )
        elif obj.needs_restock:
            return format_html('<span style="color: orange;">LOW STOCK</span>')
        else:
            return format_html('<span style="color: green;">OK</span>')

    stock_status.short_description = "Status"


# ============================================================================
# ASSET MANAGEMENT ADMIN
# ============================================================================


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "asset",
        "user",
        "location",
        "assigned_date",
        "returned_date",
        "is_active",
    ]
    list_filter = ["assigned_date", "returned_date"]
    search_fields = ["asset__asset_tag", "user__name", "location__name"]
    readonly_fields = ["assigned_date"]
    autocomplete_fields = ["asset", "user", "location"]
    date_hierarchy = "assigned_date"

    def is_active(self, obj):
        """Show if assignment is currently active"""
        if obj.returned_date:
            return format_html('<span style="color: gray;">Returned</span>')
        return format_html('<span style="color: green;">Active</span>')

    is_active.short_description = "Status"


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = [
        "asset",
        "maintenance_type",
        "maintenance_date",
        "cost",
        "next_maintenance_date",
        "performed_by",
    ]
    list_filter = ["maintenance_type", "maintenance_date"]
    search_fields = ["asset__asset_tag", "description", "performed_by"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["asset"]
    date_hierarchy = "maintenance_date"


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ["vendor_name", "contact_person", "email", "phone", "invoice_count"]
    search_fields = ["vendor_name", "contact_person", "email", "phone"]
    readonly_fields = ["created_at", "updated_at"]

    def invoice_count(self, obj):
        return obj.invoices.count()

    invoice_count.short_description = "Invoices"


# ============================================================================
# PROCUREMENT ADMIN
# ============================================================================


class RequisitionItemInline(admin.TabularInline):
    """Show requisition items inline when viewing a requisition."""

    model = RequisitionItem
    extra = 0
    fields = [
        "item_type",
        "asset",
        "component",
        "notes",
        "created_at",
    ]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["asset", "component"]


@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = [
        "requisition_number",
        "company",
        "requested_by",
        "item_count",
        "priority_badge",
        "status_badge",
        "requisition_date",
    ]
    list_filter = [
        "status",
        "priority",
        "company",
        "requisition_date",
    ]
    search_fields = [
        "requisition_number",
        "requested_by__name",
        "specifications",
        "notes",
    ]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = [
        "company",
        "department",
        "requested_by",
        "approved_by",
    ]
    date_hierarchy = "requisition_date"

    fieldsets = (
        (
            "Requisition Details",
            {
                "fields": (
                    "requisition_number",
                    "company",
                    "department",
                    "requested_by",
                    "approved_by",
                    "requisition_date",
                )
            },
        ),
        (
            "Request Info",
            {
                "fields": (
                    "specifications",
                    "priority",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "fulfilled_date",
                )
            },
        ),
        (
            "Cancellation",
            {"fields": ("cancellation_reason",), "classes": ("collapse",)},
        ),
        ("Additional Information", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    inlines = [RequisitionItemInline]

    def item_count(self, obj):
        """Display the number of items on this requisition."""
        count = obj.items.count()
        if count == 0:
            return "-"
        return count

    item_count.short_description = "Items"

    def priority_badge(self, obj):
        """Show priority with color coding"""
        colors = {
            "low": "gray",
            "normal": "blue",
            "high": "orange",
            "urgent": "red",
        }
        color = colors.get(obj.priority, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display(),
        )

    priority_badge.short_description = "Priority"
    priority_badge.admin_order_field = "priority"

    def status_badge(self, obj):
        """Show status with color coding"""
        colors = {
            "pending": "orange",
            "fulfilled": "green",
            "cancelled": "red",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"


class InvoiceLineItemInline(admin.TabularInline):
    """Show invoice line items inline when viewing an invoice"""

    model = InvoiceLineItem
    extra = 1
    fields = [
        "line_number",
        "item_type",
        "description",
        "asset_model",
        "component_type",
        "quantity",
        "item_cost",
        "company",
        "department",
    ]
    readonly_fields = ["line_total"]
    autocomplete_fields = ["asset_model", "component_type", "company", "department"]


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_number",
        "vendor",
        "invoice_date",
        "total_amount",
        "payment_status_badge",
        "company",
    ]
    list_filter = ["payment_status", "company", "vendor", "invoice_date"]
    search_fields = ["invoice_number", "vendor__vendor_name", "payment_reference"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["company", "vendor", "received_by"]
    date_hierarchy = "invoice_date"

    fieldsets = (
        (
            "Invoice Details",
            {
                "fields": (
                    "invoice_number",
                    "company",
                    "vendor",
                    "invoice_date",
                    "total_amount",
                )
            },
        ),
        (
            "Payment Information",
            {
                "fields": (
                    "payment_status",
                    "payment_date",
                    "payment_method",
                    "payment_reference",
                )
            },
        ),
        (
            "Receiving",
            {"fields": ("received_by", "received_date"), "classes": ("collapse",)},
        ),
        ("Additional Information", {"fields": ("notes",), "classes": ("collapse",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    inlines = [InvoiceLineItemInline]

    actions = ["mark_as_paid"]

    def payment_status_badge(self, obj):
        """Show payment status with color coding"""
        colors = {
            "unpaid": "red",
            "partially_paid": "orange",
            "paid": "green",
        }
        color = colors.get(obj.payment_status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_payment_status_display(),
        )

    payment_status_badge.short_description = "Payment Status"

    def mark_as_paid(self, request, queryset):
        """Bulk action to mark invoices as paid"""
        from django.utils import timezone

        updated = queryset.filter(
            payment_status__in=["unpaid", "partially_paid"]
        ).update(payment_status="paid", payment_date=timezone.now().date())
        self.message_user(request, f"{updated} invoices marked as paid.")

    mark_as_paid.short_description = "Mark selected as Paid"


@admin.register(InvoiceLineItem)
class InvoiceLineItemAdmin(admin.ModelAdmin):
    list_display = [
        "invoice",
        "line_number",
        "item_type",
        "description",
        "quantity",
        "item_cost",
        "line_total",
    ]
    readonly_fields = ["line_total"]
    list_filter = ["item_type", "company", "department"]
    search_fields = ["invoice__invoice_number", "description"]
    autocomplete_fields = [
        "invoice",
        "company",
        "department",
        "asset_model",
        "component_type",
    ]


@admin.register(RequisitionItem)
class RequisitionItemAdmin(admin.ModelAdmin):
    list_display = [
        "get_requisition_number",
        "item_type_badge",
        "get_item_detail",
        "created_at",
    ]
    list_filter = ["item_type", "requisition__status", "created_at"]
    search_fields = [
        "requisition__requisition_number",
        "asset__asset_tag",
        "asset__serial_number",
        "component__serial_number",
        "component__specifications",
        "notes",
    ]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["requisition", "asset", "component"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Item Details",
            {"fields": ("requisition", "item_type", "asset", "component")},
        ),
        ("Additional Information", {"fields": ("notes",), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def get_requisition_number(self, obj):
        """Get the requisition number"""
        return obj.requisition.requisition_number if obj.requisition else "-"

    get_requisition_number.short_description = "Requisition #"
    get_requisition_number.admin_order_field = "requisition__requisition_number"

    def item_type_badge(self, obj):
        """Show item type with color coding"""
        colors = {
            "asset": "#2196F3",  # Blue
            "component": "#9C27B0",  # Purple
        }
        color = colors.get(obj.item_type, "black")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_item_type_display(),
        )

    item_type_badge.short_description = "Type"
    item_type_badge.admin_order_field = "item_type"

    def get_item_detail(self, obj):
        """Display the specific asset or component"""
        if obj.item_type == "asset" and obj.asset:
            return str(obj.asset)
        elif obj.item_type == "component" and obj.component:
            return str(obj.component)
        return "-"

    get_item_detail.short_description = "Item"




# ============================================================================
# ACTIVITY LOG ADMIN
# ============================================================================


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "event_type",
        "action",
        "message",
        "detail",
        "actor_name",
        "object_repr",
    )
    list_filter = ("event_type", "action", "timestamp")
    search_fields = ("message", "detail", "actor_name", "object_repr")
    readonly_fields = (
        "timestamp",
        "event_type",
        "action",
        "message",
        "detail",
        "actor",
        "actor_name",
        "content_type",
        "object_id",
        "object_repr",
        "url",
        "changes",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ============================================================================
# ADMIN SITE CUSTOMIZATION
# ============================================================================

# Customize the admin site header and title
admin.site.site_header = "propraetor"
admin.site.site_title = "propraetor"
admin.site.index_title = "propraetor"
