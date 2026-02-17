from django.contrib.auth.models import User as DjangoUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

# ============================================================================
# CORE MODELS
# ============================================================================


class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True, default="", blank=True)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, default="", blank=True)
    zip = models.CharField(max_length=10, default="", blank=True)
    country = models.CharField(max_length=100, default="", blank=True)
    phone = models.CharField(max_length=50, default="", blank=True)
    notes = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "companies"
        verbose_name_plural = "Companies"
        ordering = ["pk"]

    def __str__(self):
        return self.name


class Location(models.Model):
    name = models.CharField(max_length=255, default="")
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, default="", blank=True)
    zipcode = models.CharField(max_length=10, default="", blank=True)
    country = models.CharField(max_length=100, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "locations"
        ordering = ["name"]

    def __str__(self):
        return self.name or f"Location {self.id}"


class Department(models.Model):
    """Departments within companies"""

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="departments"
    )
    name = models.CharField(max_length=255)
    default_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_departments",
        help_text="Default location for users in this department",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "departments"
        ordering = ["company", "name"]
        unique_together = [["company", "name"]]

    def __str__(self):
        return f"{self.company.code} - {self.name}"


class Employee(models.Model):
    """
    Employees/Users in the system
    This extends Django's User model for authentication
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    employee_id = models.CharField(max_length=100, unique=True, default=None, blank=True, null=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, default="", blank=True)
    extension = models.CharField(max_length=20, default="", blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="employees",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    position = models.CharField(max_length=255, default="", blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    django_user = models.OneToOneField(
        DjangoUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee",
    )

    class Meta:
        db_table = "users"
        verbose_name_plural = "Employees"
        ordering = ["name"]

    def __str__(self):
        if self.employee_id:
            return f"{self.name} ({self.employee_id})"
        return str(self.name)

    def save(self, *args, **kwargs):
        """Auto-set company and location from department if not specified"""
        if self.department:
            if not self.company:
                self.company = self.department.company
            if not self.location and self.department.default_location:
                self.location = self.department.default_location
        super().save(*args, **kwargs)


# ============================================================================
# ASSET MODELS
# ============================================================================


class Category(models.Model):
    """Asset Categories (Desktop, Laptop, AIO, Printer, etc.)"""

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AssetModel(models.Model):
    """Specific models of Assets, such as MacBook Pro, MacBook Air, Pixma G1010, etc."""

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="models"
    )
    manufacturer = models.CharField(
        max_length=255, blank=True, help_text="Leave blank for custom builds or unknown"
    )
    model_name = models.CharField(
        max_length=255,
        help_text="e.g., '15', 'Satellite Pro C40-G', 'Custom', 'Unidentified'",
    )
    model_number = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Official model/part number from manufacturer",
    )
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="General notes (common issues, EOL date, warranty period, etc.)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_models"
        ordering = ["manufacturer", "model_name"]
        indexes = [
            models.Index(fields=["manufacturer", "model_name"]),
            models.Index(fields=["category"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "manufacturer", "model_name"],
                name="unique_model_per_category",
            )
        ]

    def __str__(self):
        if self.manufacturer:
            return f"{self.manufacturer} {self.model_name}"
        return self.model_name

    @property
    def asset_count(self):
        """Number of assets using this model"""
        return self.assets.count()


class Asset(models.Model):
    """Physical and virtual assets"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("in_repair", "In Repair"),
        ("retired", "Retired"),
        ("disposed", "Disposed"),
        ("inactive", "Inactive"),
    ]

    # Core Identification
    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL, related_name="assets", null=True
    )
    asset_tag = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        help_text="Unique identifier for this asset (auto-generated if left blank).",
    )
    asset_model = models.ForeignKey(
        AssetModel, on_delete=models.PROTECT, related_name="assets"
    )
    notes = models.TextField(null=True, blank=True)

    # Asset Specific Information
    serial_number = models.CharField(max_length=255, default="", blank=True)
    attributes = models.JSONField(
        null=True, blank=True, help_text="Additional custom attributes as JSON"
    )

    # Financials and lifecycle
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    warranty_expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Relationships
    # Assignment: Either to a user (Employee) or a location, but not both
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    assigned_to = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_assets",
    )
    requisition = models.ForeignKey(
        "Requisition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    invoice = models.ForeignKey(
        "PurchaseInvoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    invoice_line_item = models.ForeignKey(
        "InvoiceLineItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
        help_text="The specific invoice line item this asset was purchased under.",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assets"
        ordering = ["asset_tag"]
        indexes = [
            models.Index(fields=["asset_tag"]),
            models.Index(fields=["serial_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["company"]),
            models.Index(fields=["asset_model"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(assigned_to__isnull=False, location__isnull=False),
                name="asset_not_assigned_to_both",
            ),
        ]

    def clean(self):
        """Ensure asset is assigned to either a user or a location, but not both."""
        from django.core.exceptions import ValidationError

        if self.assigned_to and self.location:
            raise ValidationError(
                "Asset can only be assigned to either a user or a location, not both."
            )

    def save(self, *args, **kwargs):
        if not self.asset_tag:
            from propraetor.tagging import generate_asset_tag_for_instance

            self.asset_tag = generate_asset_tag_for_instance(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset_tag} - {self.asset_model}"

    @property
    def assignee(self):
        """Returns the current assignee, either an Employee or a Location."""
        return self.assigned_to if self.assigned_to else self.location

    # Get properties through model relationships
    @property
    def category(self):
        return self.asset_model.category

    @property
    def manufacturer(self):
        return self.asset_model.manufacturer

    @property
    def model_name(self):
        return self.asset_model.model_name

    @property
    def location_resolved(self):
        """
        Returns the asset's location.
        - If assigned to an employee, returns the employee's location.
        - Otherwise, returns the asset's own location field.
        """
        if self.assigned_to and self.assigned_to.location:
            return self.assigned_to.location
        return self.location


# ============================================================================
# COMPONENT MODELS
# ============================================================================


class ComponentType(models.Model):
    """Types of components (CPU, RAM, SSD, etc.)"""

    type_name = models.CharField(max_length=100, unique=True)
    attributes = models.JSONField(
        null=True, blank=True, help_text="Type-specific attributes as JSON"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "component_types"
        ordering = ["type_name"]

    def __str__(self):
        return self.type_name


class Component(models.Model):
    """Components within assets or spare parts"""

    STATUS_CHOICES = [
        ("installed", "Installed"),
        ("spare", "Spare"),
        ("failed", "Failed"),
        ("removed", "Removed"),
        ("disposed", "Disposed"),
    ]

    # Core Identification
    component_tag = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        help_text="Unique identifier for this component (auto-generated if left blank).",
    )
    parent_asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="components",
    )
    component_type = models.ForeignKey(
        ComponentType, on_delete=models.PROTECT, related_name="components"
    )
    manufacturer = models.CharField(max_length=255, default="", blank=True)
    model = models.CharField(max_length=255, default="", blank=True)
    serial_number = models.CharField(max_length=255, default="", blank=True)
    specifications = models.TextField(
        null=True, blank=True, help_text="e.g., '16GB', '1TB', 'Intel i7-12700'"
    )
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="installed"
    )
    installation_date = models.DateField(null=True, blank=True)
    removal_date = models.DateField(null=True, blank=True)
    requisition = models.ForeignKey(
        "Requisition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="components",
    )
    invoice = models.ForeignKey(
        "PurchaseInvoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="components",
    )
    invoice_line_item = models.ForeignKey(
        "InvoiceLineItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="components",
        help_text="The specific invoice line item this component was purchased under.",
    )
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "components"
        ordering = ["component_tag"]
        indexes = [models.Index(fields=["serial_number"])]

    def clean(self):
        if self.status == "installed" and not self.parent_asset:
            raise ValidationError(
                "A component cannot be marked as installed without being assigned to a parent asset."
            )

    def save(self, *args, **kwargs):
        if not self.component_tag:
            from propraetor.tagging import generate_component_tag_for_instance

            self.component_tag = generate_component_tag_for_instance(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.component_tag} ({self.component_type})"


# Legacy _generate_component_tag removed — tag generation is now handled by
# propraetor.tagging which uses prefix configuration from tag_prefixes.toml.


class ComponentHistory(models.Model):
    """Audit trail for component changes"""

    ACTION_CHOICES = [
        ("installed", "Installed"),
        ("removed", "Removed"),
        ("replaced", "Replaced"),
        ("upgraded", "Upgraded"),
        ("failed", "Failed"),
    ]

    component = models.ForeignKey(
        Component, on_delete=models.CASCADE, related_name="history"
    )
    parent_asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="component_history"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    action_date = models.DateTimeField(default=timezone.now)
    performed_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="component_actions",
    )
    reason = models.TextField(null=True, blank=True)
    previous_component = models.ForeignKey(
        Component,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaced_by",
    )
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "component_history"
        verbose_name_plural = "Component histories"
        ordering = ["-action_date"]

    def __str__(self):
        return f"{self.component} - {self.action} on {self.action_date.date()}"


class SparePartsInventory(models.Model):
    """Inventory of spare components – auto-populated from Components with status='spare'."""

    component_type = models.ForeignKey(
        ComponentType, on_delete=models.CASCADE, related_name="spare_parts"
    )
    manufacturer = models.CharField(max_length=255, default="", blank=True)
    model = models.CharField(max_length=255, default="", blank=True)
    specifications = models.TextField(null=True, blank=True)
    quantity_available = models.IntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    quantity_minimum = models.IntegerField(
        default=0, validators=[MinValueValidator(0)], help_text="Reorder threshold"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spare_parts",
    )
    last_restocked = models.DateField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "spare_parts_inventory"
        verbose_name_plural = "Spare parts inventory"

    def __str__(self):
        return f"{self.component_type} - {self.manufacturer or 'Generic'} ({self.quantity_available} available)"

    @property
    def needs_restock(self):
        """Check if inventory is below minimum threshold"""
        return self.quantity_available <= self.quantity_minimum

    @property
    def spare_components(self):
        """Return queryset of all Component objects with status='spare' for this entry's component_type."""
        return (
            Component.objects.filter(
                component_type=self.component_type,
                status="spare",
            )
            .select_related("parent_asset", "component_type")
            .order_by("manufacturer", "model")
        )


# ---------------------------------------------------------------------------
# Spare-parts auto-sync utilities
# ---------------------------------------------------------------------------


def sync_spare_parts_for_type(component_type):
    """
    Create or update the SparePartsInventory row for *component_type* so that
    ``quantity_available`` equals the number of Component rows with
    ``status='spare'`` for that type.

    * If spare components exist but no inventory row does, one is created.
    * If the inventory row exists, only ``quantity_available`` is touched.
    * If zero spare components remain, quantity is set to 0 (the row is kept
      so that ``quantity_minimum``, ``notes``, etc. are preserved).
    """
    spare_count = Component.objects.filter(
        component_type=component_type,
        status="spare",
    ).count()

    entry = SparePartsInventory.objects.filter(component_type=component_type).first()

    if spare_count > 0:
        if entry:
            if entry.quantity_available != spare_count:
                entry.quantity_available = spare_count
                entry.save(update_fields=["quantity_available", "updated_at"])
        else:
            SparePartsInventory.objects.create(
                component_type=component_type,
                quantity_available=spare_count,
            )
    else:
        if entry and entry.quantity_available != 0:
            entry.quantity_available = 0
            entry.save(update_fields=["quantity_available", "updated_at"])


def sync_all_spare_parts():
    """
    Bulk-sync every SparePartsInventory row against real Component counts.

    Call this when the spare-parts list page loads to guarantee consistency
    (e.g. after a data import or if signals were bypassed).
    """
    from django.db.models import Count

    spare_counts = dict(
        Component.objects.filter(status="spare")
        .values_list("component_type")
        .annotate(cnt=Count("id"))
        .values_list("component_type", "cnt")
    )

    seen_type_ids = set()

    # Update / create entries for types that have spare components
    for ct_id, count in spare_counts.items():
        seen_type_ids.add(ct_id)
        entry = SparePartsInventory.objects.filter(component_type_id=ct_id).first()
        if entry:
            if entry.quantity_available != count:
                entry.quantity_available = count
                entry.save(update_fields=["quantity_available", "updated_at"])
        else:
            SparePartsInventory.objects.create(
                component_type_id=ct_id,
                quantity_available=count,
            )

    # Zero-out entries whose component types no longer have any spare components
    SparePartsInventory.objects.exclude(component_type_id__in=seen_type_ids).filter(
        quantity_available__gt=0
    ).update(quantity_available=0)


# ============================================================================
# ASSET MANAGEMENT MODELS
# ============================================================================


class AssetAssignment(models.Model):
    """History of asset assignments to users or locations"""

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="assignments"
    )
    user = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_assignments",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_assignments",
    )
    assigned_date = models.DateTimeField(default=timezone.now)
    returned_date = models.DateTimeField(null=True, blank=True)
    condition_on_assignment = models.TextField(null=True, blank=True)
    condition_on_return = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "asset_assignments"
        ordering = ["-assigned_date"]

    def __str__(self):
        if self.user:
            return f"{self.asset.asset_tag} → {self.user.name}"
        elif self.location:
            return f"{self.asset.asset_tag} → {self.location.name}"
        return f"{self.asset.asset_tag} - Assignment {self.id}"

    def clean(self):
        """Ensure either user or location is specified"""
        from django.core.exceptions import ValidationError

        if not self.user and not self.location:
            raise ValidationError("Either user or location must be specified")


class MaintenanceRecord(models.Model):
    """Service and maintenance history for assets"""

    MAINTENANCE_TYPE_CHOICES = [
        ("repair", "Repair"),
        ("upgrade", "Upgrade"),
    ]

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="maintenance_records"
    )
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPE_CHOICES)
    performed_by = models.CharField(max_length=255, default="", blank=True)
    maintenance_date = models.DateField()
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    description = models.TextField(null=True, blank=True)
    next_maintenance_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "maintenance_records"
        ordering = ["-maintenance_date"]

    def __str__(self):
        return f"{self.asset.asset_tag} - {self.maintenance_type} on {self.maintenance_date}"


class Vendor(models.Model):
    """Vendors/suppliers"""

    vendor_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, default="", blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, default="", blank=True)
    address = models.TextField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vendors"
        ordering = ["vendor_name"]

    def __str__(self):
        return str(self.vendor_name)


# ============================================================================
# PROCUREMENT MODELS
# ============================================================================


class Requisition(models.Model):
    """A requisition request header.

    A requisition is simply a request that can be fulfilled by any mix of
    assets and/or components via ``RequisitionItem`` rows.  It is assumed
    that only approved requisitions are entered into the system, so
    ``approved_by`` is a simple optional reference with no workflow logic.
    """

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
    ]

    requisition_number = models.CharField(max_length=100, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="requisitions"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="requisitions"
    )
    requested_by = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="requisitions"
    )
    approved_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_requisitions",
        help_text="Optional – person who approved this requisition.",
    )
    requisition_date = models.DateField(default=timezone.now)
    specifications = models.JSONField(null=True, blank=True)
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="normal"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(null=True, blank=True)

    # Fulfillment
    fulfilled_date = models.DateField(null=True, blank=True)

    # Cancellation
    cancellation_reason = models.TextField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "requisitions"
        ordering = ["-requisition_date"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["company", "department"]),
        ]

    def __str__(self):
        return self.requisition_number

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.status == "fulfilled" and not self.items.exists():
            raise ValidationError(
                {"status": "Cannot mark a requisition as fulfilled without any items."}
            )

    def save(self, *args, **kwargs):
        # Skip full_clean on initial save (items can't exist yet)
        if self.pk:
            self.full_clean()
        super().save(*args, **kwargs)


class RequisitionItem(models.Model):
    """An item that fulfills (part of) a requisition.

    Each item is either an **asset** or a **component** (exactly one must be
    set).
    """

    ITEM_TYPE_CHOICES = [
        ("asset", "Asset"),
        ("component", "Component"),
    ]

    requisition = models.ForeignKey(
        Requisition, on_delete=models.CASCADE, related_name="items"
    )
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="requisition_items",
    )
    component = models.ForeignKey(
        Component,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="requisition_items",
    )
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "requisition_items"
        ordering = ["requisition", "created_at"]
        indexes = [
            models.Index(fields=["requisition", "created_at"]),
        ]

    def __str__(self):
        if self.item_type == "asset" and self.asset:
            return f"{self.requisition.requisition_number} — {self.asset}"
        elif self.item_type == "component" and self.component:
            return f"{self.requisition.requisition_number} — {self.component}"
        return f"{self.requisition.requisition_number} — (unlinked item)"

    # -----------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------
    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}

        if not self.requisition_id:
            return

        # Cannot add items to a cancelled requisition
        if self.requisition.status == "cancelled":
            errors.setdefault("requisition", []).append(
                "Cannot add items to a cancelled requisition."
            )

        # Prevent re-assigning to a different requisition
        if self.pk:
            existing_req_id = (
                RequisitionItem.objects.filter(pk=self.pk)
                .values_list("requisition_id", flat=True)
                .first()
            )
            if existing_req_id and existing_req_id != self.requisition_id:
                errors.setdefault("requisition", []).append(
                    "Item cannot be reassigned to a different requisition."
                )

        # Exactly one of asset / component must be set
        has_asset = bool(self.asset_id)
        has_component = bool(self.component_id)

        if has_asset and has_component:
            errors["asset"] = "An item cannot reference both an asset and a component."
            errors["component"] = (
                "An item cannot reference both an asset and a component."
            )
        elif not has_asset and not has_component:
            errors["asset"] = "An item must reference either an asset or a component."

        # item_type must match the FK that is set
        if has_asset and self.item_type != "asset":
            self.item_type = "asset"
        elif has_component and self.item_type != "component":
            self.item_type = "component"

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class PurchaseInvoice(models.Model):
    """Vendor invoices for purchases"""

    PAYMENT_STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
    ]

    invoice_number = models.CharField(max_length=100, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="purchase_invoices"
    )
    vendor = models.ForeignKey(
        Vendor, on_delete=models.PROTECT, related_name="invoices"
    )
    invoice_date = models.DateField()
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid"
    )
    payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(
        max_length=100, null=True, blank=True, help_text="e.g., Cash, Card, Bank, Bkash"
    )
    payment_reference = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Transaction ID, receipt ID, etc.",
    )
    received_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_invoices",
    )
    received_date = models.DateField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "purchase_invoices"
        ordering = ["-invoice_date"]

    def __str__(self):
        return f"{self.invoice_number} - {self.vendor.vendor_name}"

    @property
    def line_items_total(self):
        """Compute total from line items (quantity * item_cost for each)."""
        from django.db.models import F, Sum

        result = self.line_items.aggregate(total=Sum(F("quantity") * F("item_cost")))[
            "total"
        ]
        return result or 0

    def update_total_from_line_items(self):
        """Re-compute total_amount from line items and save."""
        computed = self.line_items_total
        if computed and computed > 0:
            self.total_amount = computed
            self.save(update_fields=["total_amount", "updated_at"])

    @property
    def items_received(self):
        """True if all receivable line items have had assets/components created."""
        for li in self.line_items.all():
            if li.item_type in ("service", "other"):
                continue
            if li.received_count < li.quantity:
                return False
        return self.line_items.exists()

    @property
    def received_summary(self):
        """Return a dict summarising receive status per line item."""
        summary = []
        for li in self.line_items.all():
            received = li.received_count
            summary.append(
                {
                    "line_item": li,
                    "received": received,
                    "remaining": max(0, li.quantity - received),
                    "complete": received >= li.quantity,
                }
            )
        return summary


class InvoiceLineItem(models.Model):
    """Individual items on purchase invoices"""

    ITEM_TYPE_CHOICES = [
        ("asset", "Asset"),
        ("component", "Component"),
        ("service", "Service"),
        ("other", "Other"),
    ]

    invoice = models.ForeignKey(
        PurchaseInvoice, on_delete=models.CASCADE, related_name="line_items"
    )
    line_number = models.IntegerField()
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="invoice_line_items"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="invoice_line_items"
    )
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    description = models.TextField()
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    item_cost = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    asset_model = models.ForeignKey(
        AssetModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_line_items",
    )
    component_type = models.ForeignKey(
        ComponentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_line_items",
    )
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "invoice_line_items"
        ordering = ["invoice", "line_number"]
        unique_together = [["invoice", "line_number"]]

    def __str__(self):
        return f"{self.invoice.invoice_number} - Line {self.line_number}: {self.description}"

    @property
    def line_total(self):
        """Calculate total for this line item"""
        return self.quantity * self.item_cost

    @property
    def received_count(self):
        """How many assets/components have been created from this line item."""
        if self.item_type == "asset":
            return self.assets.count()
        elif self.item_type == "component":
            return self.components.count()
        return 0

    @property
    def remaining_to_receive(self):
        """How many items still need to be created."""
        return max(0, self.quantity - self.received_count)

    @property
    def is_fully_received(self):
        """True when all items for this line have been created."""
        if self.item_type in ("service", "other"):
            return True
        return self.received_count >= self.quantity

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-update parent invoice total from line items
        if self.invoice_id:
            self.invoice.update_total_from_line_items()


# ============================================================================
# ACTIVITY / AUDIT LOG
# ============================================================================


class ActivityLog(models.Model):
    """
    Persistent audit-trail table that records every meaningful event in the
    system (create / update / delete / status-change / assignment / etc.).

    Uses Django's ContentType framework so a single table can reference any
    model instance via a GenericForeignKey.
    """

    # ------------------------------------------------------------------
    # Event-type choices  (the "category" shown in the activity feed)
    # ------------------------------------------------------------------
    EVENT_TYPE_CHOICES = [
        ("asset", "Asset"),
        ("requisition", "Requisition"),
        ("invoice", "Invoice"),
        ("assignment", "Assignment"),
        ("component", "Component"),
        ("user", "User"),
        ("company", "Company"),
        ("location", "Location"),
        ("department", "Department"),
        ("vendor", "Vendor"),
        ("category", "Category"),
        ("asset_model", "Asset Model"),
        ("component_type", "Component Type"),
        ("spare_part", "Spare Part"),
        ("maintenance", "Maintenance"),
        ("disposal", "Disposal"),
        ("line_item", "Line Item"),
        ("fulfillment", "Fulfillment"),
    ]

    # ------------------------------------------------------------------
    # Action choices  (what happened)
    # ------------------------------------------------------------------
    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("deleted", "Deleted"),
        ("assigned", "Assigned"),
        ("unassigned", "Unassigned"),
        ("status_changed", "Status Changed"),
        ("duplicated", "Duplicated"),
        ("approved", "Approved"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
        ("activated", "Activated"),
        ("deactivated", "Deactivated"),
        ("bulk_deleted", "Bulk Deleted"),
        ("bulk_status", "Bulk Status Change"),
        ("paid", "Marked Paid"),
    ]

    # ------------------------------------------------------------------
    # Icon mapping (for the activity feed badge)
    # ------------------------------------------------------------------
    ICON_MAP = {
        "asset": "A",
        "requisition": "R",
        "invoice": "I",
        "assignment": "X",
        "component": "C",
        "user": "U",
        "company": "O",
        "location": "L",
        "department": "D",
        "vendor": "V",
        "category": "G",
        "asset_model": "M",
        "component_type": "T",
        "spare_part": "S",
        "maintenance": "W",
        "disposal": "Z",
        "line_item": "N",
        "fulfillment": "F",
    }

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES,
        db_index=True,
    )
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        db_index=True,
    )

    message = models.CharField(
        max_length=512,
        help_text="Human-readable summary, e.g. 'Asset LAPTOP-042 created'.",
    )
    detail = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Secondary info, e.g. status display or assignee name.",
    )

    # Who performed the action (nullable — system / anonymous events)
    actor = models.ForeignKey(
        DjangoUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    actor_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Snapshot of actor display name at time of event.",
    )

    # Generic relation to the affected object
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # Snapshot of __str__ at log time (survives deletion of the object)
    object_repr = models.CharField(max_length=512, blank=True, default="")

    # Convenience URL for linking in the activity feed
    url = models.CharField(max_length=512, blank=True, default="")

    # Structured change data  (old → new values)
    changes = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional JSON dict of changed fields, e.g. {'status': ['active', 'retired']}.",
    )

    class Meta:
        db_table = "activity_log"
        ordering = ["-timestamp"]
        verbose_name = "Activity Log Entry"
        verbose_name_plural = "Activity Log"
        indexes = [
            models.Index(fields=["event_type", "-timestamp"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.event_type}/{self.action}: {self.message}"

    @property
    def icon(self):
        return self.ICON_MAP.get(self.event_type, "?")
