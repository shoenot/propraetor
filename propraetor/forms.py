from django import forms

from .models import (
    Asset,
    AssetModel,
    Category,
    Company,
    Component,
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


class BaseForm(forms.ModelForm):
    """Base form that applies consistent styling to all form widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            existing_attrs = widget.attrs or {}

            if isinstance(widget, forms.Select):
                existing_attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                existing_attrs.setdefault("class", "form-textarea")
                existing_attrs.setdefault("rows", 3)
            elif isinstance(widget, forms.CheckboxInput):
                existing_attrs.setdefault("class", "form-checkbox")
            elif isinstance(widget, (forms.DateInput, forms.DateTimeInput)):
                existing_attrs.setdefault("class", "form-input")
            else:
                existing_attrs.setdefault("class", "form-input")

            if field.required:
                existing_attrs["required"] = "required"

            widget.attrs = existing_attrs

    # ------------------------------------------------------------------
    # Searchable-select helper
    # ------------------------------------------------------------------

    def _make_searchable(
        self,
        field_name,
        search_model,
        full_qs,
        placeholder=None,
        fk_attr=None,
        extra_filters=None,
    ):
        """Turn a ModelChoiceField into a searchable AJAX-powered dropdown.

        * On **GET** (unbound form) the queryset is trimmed to only the
          currently-selected value (or empty) so no huge option lists are
          sent to the browser.
        * On **POST** (bound form) the queryset is narrowed to only the
          submitted PK (looked up inside ``full_qs``).  This is enough for
          ``ModelChoiceField.clean()`` to succeed **and** keeps rendering
          fast when the form is re-displayed with validation errors.

        Parameters
        ----------
        field_name : str
            Name of the field in ``self.fields``.
        search_model : str
            Key that the JS widget sends to ``/api/search/?model=…``.
        full_qs : QuerySet
            The complete, filtered queryset for validation.
        placeholder : str | None
            Placeholder text shown in the search input.
        fk_attr : str | None
            The model attribute that stores the FK id (default:
            ``<field_name>_id``).
        extra_filters : dict | None
            Extra ``filter_<key>=<value>`` pairs passed to the search API
            so results are scoped (e.g. ``{"company": 5}``).
        """
        field = self.fields[field_name]
        fk_attr = fk_attr or f"{field_name}_id"

        if self.is_bound:
            # POST – narrow to the submitted PK only.  This is sufficient
            # for ModelChoiceField.clean() (it does qs.get(pk=value)) and
            # keeps rendering lightweight when re-displaying errors.
            submitted = (
                self.data.get(self.add_prefix(field_name))
                or self.data.get(field_name)
            )
            if submitted:
                field.queryset = full_qs.filter(pk=submitted)
            else:
                field.queryset = full_qs.none()
        else:
            # GET – only include the currently selected value (if any)
            current_pk = None
            if self.instance and self.instance.pk:
                current_pk = getattr(self.instance, fk_attr, None)
            if not current_pk:
                init_val = self.initial.get(field_name)
                if init_val is not None:
                    current_pk = init_val.pk if hasattr(init_val, "pk") else init_val

            if current_pk:
                field.queryset = full_qs.filter(pk=current_pk)
            else:
                field.queryset = full_qs.none()

        attrs = {
            "data-searchable": search_model,
            "data-placeholder": placeholder or "type to search\u2026",
        }
        if extra_filters:
            parts = [f"filter_{k}={v}" for k, v in extra_filters.items()]
            attrs["data-filters"] = "&".join(parts)

        field.widget.attrs.update(attrs)


class AssetTransferLocationForm(BaseForm):
    """Lightweight form for transferring an asset to a different location."""

    class Meta:
        model = Asset
        fields = ["location"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._make_searchable(
            "location",
            "location",
            Location.objects.order_by("name"),
            placeholder="search locations\u2026",
        )
        self.fields["location"].required = False


class AssetForm(BaseForm):
    class Meta:
        model = Asset
        fields = [
            "company",
            "asset_tag",
            "asset_model",
            "serial_number",
            "purchase_date",
            "purchase_cost",
            "warranty_expiry_date",
            "status",
            "location",
            "assigned_to",
            "requisition",
            "invoice",
            "attributes",
            "notes",
        ]
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "warranty_expiry_date": forms.DateInput(attrs={"type": "date"}),
            "purchase_cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "attributes": forms.Textarea(attrs={"placeholder": '{"key": "value"}', "rows": 4}),
            "notes": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["asset_tag"].required = False
        self.fields["asset_tag"].help_text = (
            "Leave blank to auto-generate based on tag prefix settings."
        )

        # Searchable FK fields
        self._make_searchable(
            "company",
            "company",
            Company.objects.filter(is_active=True),
            placeholder="search companies\u2026",
        )
        self._make_searchable(
            "asset_model",
            "asset_model",
            AssetModel.objects.select_related("category").order_by(
                "manufacturer", "model_name"
            ),
            placeholder="search asset models\u2026",
        )
        self._make_searchable(
            "assigned_to",
            "employee",
            Employee.objects.filter(status="active").order_by("name"),
            placeholder="search employees\u2026",
        )
        self._make_searchable(
            "location",
            "location",
            Location.objects.order_by("name"),
            placeholder="search locations\u2026",
        )
        self._make_searchable(
            "requisition",
            "requisition",
            Requisition.objects.order_by("-requisition_date"),
            placeholder="search requisitions\u2026",
        )
        self._make_searchable(
            "invoice",
            "invoice",
            PurchaseInvoice.objects.order_by("-invoice_date"),
            placeholder="search invoices\u2026",
        )

        # Make optional fields not required
        self.fields["serial_number"].required = False
        self.fields["purchase_date"].required = False
        self.fields["purchase_cost"].required = False
        self.fields["warranty_expiry_date"].required = False
        self.fields["location"].required = False
        self.fields["assigned_to"].required = False
        self.fields["requisition"].required = False
        self.fields["invoice"].required = False
        self.fields["notes"].required = False
        self.fields["attributes"].required = False


class AssetModelForm(BaseForm):
    class Meta:
        model = AssetModel
        fields = [
            "category",
            "manufacturer",
            "model_name",
            "model_number",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._make_searchable(
            "category",
            "category",
            Category.objects.order_by("name"),
            placeholder="search categories\u2026",
        )

        self.fields["manufacturer"].required = False
        self.fields["model_number"].required = False
        self.fields["notes"].required = False


class ComponentForm(BaseForm):
    class Meta:
        model = Component
        fields = [
            "component_tag",
            "parent_asset",
            "component_type",
            "manufacturer",
            "model",
            "serial_number",
            "specifications",
            "purchase_date",
            "warranty_expiry_date",
            "status",
            "installation_date",
            "removal_date",
            "requisition",
            "invoice",
            "notes",
        ]
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "warranty_expiry_date": forms.DateInput(attrs={"type": "date"}),
            "installation_date": forms.DateInput(attrs={"type": "date"}),
            "removal_date": forms.DateInput(attrs={"type": "date"}),
            "specifications": forms.Textarea(),
            "notes": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._make_searchable(
            "parent_asset",
            "asset",
            Asset.objects.order_by("asset_tag"),
            placeholder="search assets\u2026",
        )
        self._make_searchable(
            "component_type",
            "component_type",
            ComponentType.objects.order_by("type_name"),
            placeholder="search component types\u2026",
        )
        self._make_searchable(
            "requisition",
            "requisition",
            Requisition.objects.order_by("-requisition_date"),
            placeholder="search requisitions\u2026",
        )
        self._make_searchable(
            "invoice",
            "invoice",
            PurchaseInvoice.objects.order_by("-invoice_date"),
            placeholder="search invoices\u2026",
        )

        self.fields["component_tag"].required = False
        self.fields["component_tag"].help_text = (
            "Leave blank to auto-generate based on tag prefix settings."
        )
        self.fields["parent_asset"].required = False
        self.fields["manufacturer"].required = False
        self.fields["model"].required = False
        self.fields["serial_number"].required = False
        self.fields["specifications"].required = False
        self.fields["purchase_date"].required = False
        self.fields["warranty_expiry_date"].required = False
        self.fields["installation_date"].required = False
        self.fields["removal_date"].required = False
        self.fields["requisition"].required = False
        self.fields["invoice"].required = False
        self.fields["notes"].required = False


class RequisitionForm(BaseForm):
    class Meta:
        model = Requisition
        fields = [
            "requisition_number",
            "company",
            "department",
            "requested_by",
            "approved_by",
            "requisition_date",
            "priority",
            "status",
            "specifications",
            "notes",
        ]
        widgets = {
            "requisition_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(),
            "specifications": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._make_searchable(
            "company",
            "company",
            Company.objects.filter(is_active=True),
            placeholder="search companies\u2026",
        )
        self._make_searchable(
            "department",
            "department",
            Department.objects.select_related("company").order_by(
                "company__code", "name"
            ),
            placeholder="search departments\u2026",
        )
        self._make_searchable(
            "requested_by",
            "employee",
            Employee.objects.filter(status="active").order_by("name"),
            placeholder="search employees\u2026",
        )
        self._make_searchable(
            "approved_by",
            "employee",
            Employee.objects.filter(status="active").order_by("name"),
            placeholder="search employees\u2026",
        )

        self.fields["approved_by"].required = False
        self.fields["specifications"].required = False
        self.fields["notes"].required = False


class PurchaseInvoiceForm(BaseForm):
    class Meta:
        model = PurchaseInvoice
        fields = [
            "invoice_number",
            "company",
            "vendor",
            "invoice_date",
            "total_amount",
            "payment_status",
            "payment_date",
            "payment_method",
            "payment_reference",
            "received_by",
            "received_date",
            "notes",
        ]
        widgets = {
            "invoice_date": forms.DateInput(attrs={"type": "date"}),
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "received_date": forms.DateInput(attrs={"type": "date"}),
            "total_amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "notes": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._make_searchable(
            "company",
            "company",
            Company.objects.filter(is_active=True),
            placeholder="search companies\u2026",
        )
        self._make_searchable(
            "vendor",
            "vendor",
            Vendor.objects.order_by("vendor_name"),
            placeholder="search vendors\u2026",
        )
        self._make_searchable(
            "received_by",
            "employee",
            Employee.objects.filter(status="active").order_by("name"),
            placeholder="search employees\u2026",
        )

        self.fields["total_amount"].help_text = (
            "Auto-updated from line items when they are added. "
            "You can also enter a value manually."
        )
        self.fields["payment_date"].required = False
        self.fields["payment_method"].required = False
        self.fields["payment_reference"].required = False
        self.fields["received_by"].required = False
        self.fields["received_date"].required = False
        self.fields["notes"].required = False


class LocationForm(BaseForm):
    class Meta:
        model = Location
        fields = [
            "name",
            "address",
            "city",
            "zipcode",
            "country",
        ]
        widgets = {
            "address": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["address"].required = False
        self.fields["city"].required = False
        self.fields["zipcode"].required = False
        self.fields["country"].required = False


class DepartmentForm(BaseForm):
    class Meta:
        model = Department
        fields = [
            "company",
            "name",
            "default_location",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._make_searchable(
            "company",
            "company",
            Company.objects.filter(is_active=True),
            placeholder="search companies\u2026",
        )
        self._make_searchable(
            "default_location",
            "location",
            Location.objects.order_by("name"),
            placeholder="search locations\u2026",
        )

        self.fields["default_location"].required = False


class ComponentTypeForm(BaseForm):
    class Meta:
        model = ComponentType
        fields = [
            "type_name",
            "attributes",
        ]
        widgets = {
            "attributes": forms.Textarea(attrs={"placeholder": '{"key": "value"}'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attributes"].required = False


class EmployeeForm(BaseForm):
    class Meta:
        model = Employee
        fields = [
            "employee_id",
            "name",
            "email",
            "phone",
            "extension",
            "company",
            "department",
            "location",
            "position",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        active_companies_qs = Company.objects.filter(is_active=True)

        self._make_searchable(
            "company",
            "company",
            active_companies_qs,
            placeholder="search companies\u2026",
        )
        self._make_searchable(
            "department",
            "department",
            Department.objects.select_related("company").order_by(
                "company__code", "name"
            ),
            placeholder="search departments\u2026",
        )
        self._make_searchable(
            "location",
            "location",
            Location.objects.order_by("name"),
            placeholder="search locations\u2026",
        )

        # Auto-select company if only one active company exists
        if not self.instance.pk and not self.initial.get("company"):
            if active_companies_qs.count() == 1:
                self.initial["company"] = active_companies_qs.first().pk
                # Re-run searchable setup so the lone option shows up
                self._make_searchable(
                    "company",
                    "company",
                    active_companies_qs,
                    placeholder="search companies\u2026",
                )

        self.fields["employee_id"].required = False
        self.fields["email"].required = False
        self.fields["phone"].required = False
        self.fields["extension"].required = False
        self.fields["company"].required = False
        self.fields["department"].required = False
        self.fields["location"].required = False
        self.fields["position"].required = False


class VendorForm(BaseForm):
    class Meta:
        model = Vendor
        fields = [
            "vendor_name",
            "contact_person",
            "email",
            "phone",
            "address",
            "website",
            "notes",
        ]
        widgets = {
            "address": forms.Textarea(),
            "notes": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact_person"].required = False
        self.fields["email"].required = False
        self.fields["phone"].required = False
        self.fields["address"].required = False
        self.fields["website"].required = False
        self.fields["notes"].required = False


class CompanyForm(BaseForm):
    class Meta:
        model = Company
        fields = [
            "name",
            "code",
            "address",
            "city",
            "zip",
            "country",
            "phone",
            "notes",
            "is_active",
        ]
        widgets = {
            "address": forms.Textarea(),
            "notes": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False
        self.fields["address"].required = False
        self.fields["city"].required = False
        self.fields["zip"].required = False
        self.fields["country"].required = False
        self.fields["phone"].required = False
        self.fields["notes"].required = False


class CategoryForm(BaseForm):
    class Meta:
        model = Category
        fields = [
            "name",
            "description",
        ]
        widgets = {
            "description": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False


class SparePartsInventoryForm(BaseForm):
    class Meta:
        model = SparePartsInventory
        fields = [
            "component_type",
            "manufacturer",
            "model",
            "specifications",
            "quantity_available",
            "quantity_minimum",
            "location",
            "last_restocked",
            "notes",
        ]
        widgets = {
            "specifications": forms.Textarea(),
            "notes": forms.Textarea(),
            "last_restocked": forms.DateInput(attrs={"type": "date"}),
            "quantity_available": forms.NumberInput(attrs={"min": "0"}),
            "quantity_minimum": forms.NumberInput(attrs={"min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._make_searchable(
            "component_type",
            "component_type",
            ComponentType.objects.order_by("type_name"),
            placeholder="search component types\u2026",
        )
        self._make_searchable(
            "location",
            "location",
            Location.objects.order_by("name"),
            placeholder="search locations\u2026",
        )

        self.fields["manufacturer"].required = False
        self.fields["model"].required = False
        self.fields["specifications"].required = False
        self.fields["location"].required = False
        self.fields["last_restocked"].required = False
        self.fields["notes"].required = False

        # quantity_available is auto-computed from spare Component counts;
        # show the current value but prevent manual edits.
        self.fields["quantity_available"].disabled = True
        self.fields["quantity_available"].help_text = (
            "Read-only — automatically synced from the number of components "
            "with status='spare' for this type. Updated on every component "
            "save/delete."
        )

        self.fields["quantity_minimum"].help_text = (
            "Reorder threshold — a low-stock alert is shown when "
            "quantity_available falls to or below this value."
        )


class MaintenanceRecordForm(BaseForm):
    class Meta:
        model = MaintenanceRecord
        fields = [
            "asset",
            "maintenance_type",
            "performed_by",
            "maintenance_date",
            "cost",
            "description",
            "next_maintenance_date",
        ]
        widgets = {
            "maintenance_date": forms.DateInput(attrs={"type": "date"}),
            "next_maintenance_date": forms.DateInput(attrs={"type": "date"}),
            "cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "description": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._make_searchable(
            "asset",
            "asset",
            Asset.objects.order_by("asset_tag"),
            placeholder="search assets\u2026",
        )

        self.fields["performed_by"].required = False
        self.fields["cost"].required = False
        self.fields["description"].required = False
        self.fields["next_maintenance_date"].required = False




class InvoiceLineItemForm(BaseForm):
    class Meta:
        model = InvoiceLineItem
        fields = [
            "invoice",
            "line_number",
            "company",
            "department",
            "item_type",
            "description",
            "quantity",
            "item_cost",
            "asset_model",
            "component_type",
            "notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(),
            "quantity": forms.NumberInput(attrs={"min": "1"}),
            "item_cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        invoice = kwargs.pop("invoice", None)
        super().__init__(*args, **kwargs)

        # --- Invoice field ---
        base_invoice_qs = PurchaseInvoice.objects.order_by("-invoice_date")
        if invoice:
            self.fields["invoice"].queryset = base_invoice_qs.filter(pk=invoice.pk)
            self.fields["invoice"].initial = invoice
            self.fields["invoice"].widget = forms.HiddenInput()
            # Auto-set line number to next available
            if not self.instance.pk:
                existing_max = (
                    InvoiceLineItem.objects.filter(invoice=invoice)
                    .order_by("-line_number")
                    .values_list("line_number", flat=True)
                    .first()
                )
                self.fields["line_number"].initial = (existing_max or 0) + 1
            # Pre-fill company from invoice
            if not self.instance.pk and invoice.company_id:
                self.fields["company"].initial = invoice.company_id
        else:
            self._make_searchable(
                "invoice",
                "invoice",
                base_invoice_qs,
                placeholder="search invoices\u2026",
            )

        self._make_searchable(
            "company",
            "company",
            Company.objects.filter(is_active=True),
            placeholder="search companies\u2026",
        )
        self._make_searchable(
            "department",
            "department",
            Department.objects.select_related("company").order_by(
                "company__code", "name"
            ),
            placeholder="search departments\u2026",
        )
        self._make_searchable(
            "asset_model",
            "asset_model",
            AssetModel.objects.select_related("category").order_by(
                "manufacturer", "model_name"
            ),
            placeholder="search asset models\u2026",
        )
        self._make_searchable(
            "component_type",
            "component_type",
            ComponentType.objects.order_by("type_name"),
            placeholder="search component types\u2026",
        )

        self.fields["asset_model"].required = False
        self.fields["component_type"].required = False
        self.fields["notes"].required = False


class RequisitionItemForm(BaseForm):
    """Form for adding an item (asset or component) to a requisition."""

    class Meta:
        model = RequisitionItem
        fields = [
            "requisition",
            "item_type",
            "asset",
            "component",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        requisition = kwargs.pop("requisition", None)
        super().__init__(*args, **kwargs)

        # --- Requisition field ---
        base_requisition_qs = Requisition.objects.order_by("-requisition_date")
        if requisition:
            self.fields["requisition"].queryset = base_requisition_qs.filter(pk=requisition.pk)
            self.fields["requisition"].initial = requisition
            self.fields["requisition"].widget = forms.HiddenInput()
        else:
            self._make_searchable(
                "requisition",
                "requisition",
                base_requisition_qs,
                placeholder="search requisitions\u2026",
            )

        # --- Item type field ---
        self.fields["item_type"].required = True

        # --- Asset / Component querysets ---
        asset_qs = Asset.objects.select_related(
            "asset_model", "asset_model__category"
        ).order_by("asset_tag")
        component_qs = Component.objects.select_related(
            "component_type"
        ).order_by("component_type__type_name", "manufacturer")

        extra_asset_filters = {}
        if requisition:
            asset_qs = asset_qs.filter(company=requisition.company)
            extra_asset_filters["company"] = requisition.company_id

        self._make_searchable(
            "asset",
            "asset",
            asset_qs,
            placeholder="search assets\u2026",
            extra_filters=extra_asset_filters or None,
        )
        self._make_searchable(
            "component",
            "component",
            component_qs,
            placeholder="search components\u2026",
        )

        self.fields["asset"].required = False
        self.fields["component"].required = False
        self.fields["notes"].required = False

    def clean(self):
        cleaned_data = super().clean()
        item_type = cleaned_data.get("item_type")
        asset = cleaned_data.get("asset")
        component = cleaned_data.get("component")

        # --- Exactly one of asset / component ---
        if item_type == "asset":
            if not asset:
                self.add_error("asset", "Please select an asset for an asset item.")
            if component:
                self.add_error("component", "Cannot set a component on an asset item.")
        elif item_type == "component":
            if not component:
                self.add_error("component", "Please select a component for a component item.")
            if asset:
                self.add_error("asset", "Cannot set an asset on a component item.")
        else:
            if not item_type:
                self.add_error("item_type", "Item type is required.")

        return cleaned_data