"""
Tests for form validation across all major form classes.

Covers:
- Required field validation
- Unique constraint validation
- Cross-field validation (e.g., RequisitionItemForm clean)
- Optional fields accepted as blank
- Valid data acceptance
- Widget attribute assignment (BaseForm styling)
"""

from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone

from propraetor.forms import (
    AssetForm,
    AssetModelForm,
    CategoryForm,
    CompanyForm,
    ComponentForm,
    ComponentTypeForm,
    DepartmentForm,
    EmployeeForm,
    InvoiceLineItemForm,
    LocationForm,
    MaintenanceRecordForm,
    PurchaseInvoiceForm,
    RequisitionForm,
    RequisitionItemForm,
    SparePartsInventoryForm,
    VendorForm,
)
from propraetor.models import (
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

# ======================================================================
# Shared setUp mixin
# ======================================================================


class FormTestBase(TestCase):
    """Shared setUp that creates basic lookup data for form tests."""

    def setUp(self):
        self.company = Company.objects.create(name="TestCo", code="TC", is_active=True)
        self.company_b = Company.objects.create(
            name="OtherCo", code="OC", is_active=True
        )
        self.location = Location.objects.create(name="HQ", city="Dhaka")
        self.department = Department.objects.create(
            company=self.company, name="Engineering"
        )
        self.category = Category.objects.create(name="Laptop")
        self.vendor = Vendor.objects.create(vendor_name="WidgetVendor")
        self.component_type = ComponentType.objects.create(type_name="RAM")
        self.asset_model = AssetModel.objects.create(
            category=self.category,
            manufacturer="Dell",
            model_name="Latitude 5540",
        )
        self.employee = Employee.objects.create(
            name="Jane Doe",
            employee_id="EMP-001",
            company=self.company,
            department=self.department,
            status="active",
        )
        self.asset = Asset.objects.create(
            company=self.company,
            asset_tag="ASSET-001",
            asset_model=self.asset_model,
            status="active",
        )
        self.component = Component.objects.create(
            component_type=self.component_type,
            manufacturer="Kingston",
            status="spare",
        )
        self.invoice = PurchaseInvoice.objects.create(
            invoice_number="INV-001",
            company=self.company,
            vendor=self.vendor,
            invoice_date=timezone.now().date(),
            total_amount=Decimal("1000.00"),
        )
        self.requisition = Requisition.objects.create(
            requisition_number="REQ-001",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=timezone.now().date(),
            status="pending",
        )


# ======================================================================
# CategoryForm
# ======================================================================


class CategoryFormTests(FormTestBase):
    def test_valid_data(self):
        form = CategoryForm(data={"name": "Desktop"})
        self.assertTrue(form.is_valid())

    def test_valid_with_description(self):
        form = CategoryForm(data={"name": "Printer", "description": "All printers"})
        self.assertTrue(form.is_valid())

    def test_name_required(self):
        form = CategoryForm(data={"name": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_description_optional(self):
        form = CategoryForm(data={"name": "Monitor"})
        self.assertTrue(form.is_valid())

    def test_save_creates_object(self):
        form = CategoryForm(data={"name": "Tablet"})
        self.assertTrue(form.is_valid())
        obj = form.save()
        self.assertEqual(obj.name, "Tablet")
        self.assertTrue(Category.objects.filter(name="Tablet").exists())


# ======================================================================
# CompanyForm
# ======================================================================


class CompanyFormTests(FormTestBase):
    def test_valid_minimal_data(self):
        form = CompanyForm(data={"name": "NewCo", "is_active": True})
        self.assertTrue(form.is_valid())

    def test_valid_full_data(self):
        form = CompanyForm(
            data={
                "name": "FullCo",
                "code": "FC",
                "address": "123 Street",
                "city": "Dhaka",
                "zip": "12345",
                "country": "Bangladesh",
                "phone": "+88012345",
                "notes": "Some notes",
                "is_active": True,
            }
        )
        self.assertTrue(form.is_valid())

    def test_name_required(self):
        form = CompanyForm(data={"name": "", "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_duplicate_name_rejected(self):
        form = CompanyForm(data={"name": "TestCo", "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_duplicate_code_rejected(self):
        form = CompanyForm(data={"name": "UniqueName", "code": "TC", "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("code", form.errors)

    def test_code_optional(self):
        form = CompanyForm(data={"name": "NoCodeCo", "is_active": True})
        self.assertTrue(form.is_valid())

    def test_optional_fields_can_be_blank(self):
        form = CompanyForm(
            data={
                "name": "BlankFieldsCo",
                "code": "",
                "address": "",
                "city": "",
                "zip": "",
                "country": "",
                "phone": "",
                "notes": "",
                "is_active": True,
            }
        )
        self.assertTrue(form.is_valid())

    def test_edit_existing_company(self):
        form = CompanyForm(
            data={"name": "TestCo Renamed", "code": "TC", "is_active": True},
            instance=self.company,
        )
        self.assertTrue(form.is_valid())
        obj = form.save()
        self.assertEqual(obj.name, "TestCo Renamed")

    def test_edit_same_name_and_code_on_same_instance(self):
        """Editing a company without changing unique fields should succeed."""
        form = CompanyForm(
            data={"name": "TestCo", "code": "TC", "is_active": True},
            instance=self.company,
        )
        self.assertTrue(form.is_valid())


# ======================================================================
# LocationForm
# ======================================================================


class LocationFormTests(FormTestBase):
    def test_valid_data(self):
        form = LocationForm(data={"name": "Branch"})
        self.assertTrue(form.is_valid())

    def test_name_required(self):
        form = LocationForm(data={"name": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_optional_fields_accepted(self):
        form = LocationForm(
            data={
                "name": "Warehouse",
                "address": "456 Road",
                "city": "Chittagong",
                "zipcode": "11111",
                "country": "Bangladesh",
            }
        )
        self.assertTrue(form.is_valid())

    def test_all_optional_fields_blank(self):
        form = LocationForm(
            data={
                "name": "MinimalLoc",
                "address": "",
                "city": "",
                "zipcode": "",
                "country": "",
            }
        )
        self.assertTrue(form.is_valid())


# ======================================================================
# VendorForm
# ======================================================================


class VendorFormTests(FormTestBase):
    def test_valid_data(self):
        form = VendorForm(data={"vendor_name": "NewVendor"})
        self.assertTrue(form.is_valid())

    def test_vendor_name_required(self):
        form = VendorForm(data={"vendor_name": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("vendor_name", form.errors)

    def test_all_optional_fields(self):
        form = VendorForm(
            data={
                "vendor_name": "FullVendor",
                "contact_person": "Alice",
                "email": "alice@example.com",
                "phone": "+88012345",
                "address": "789 Lane",
                "website": "https://example.com",
                "notes": "Good vendor",
            }
        )
        self.assertTrue(form.is_valid())

    def test_invalid_email_rejected(self):
        form = VendorForm(data={"vendor_name": "BadEmail", "email": "not-an-email"})
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_invalid_website_rejected(self):
        form = VendorForm(data={"vendor_name": "BadWeb", "website": "not-a-url"})
        self.assertFalse(form.is_valid())
        self.assertIn("website", form.errors)

    def test_optional_fields_blank(self):
        form = VendorForm(
            data={
                "vendor_name": "MinimalVendor",
                "contact_person": "",
                "email": "",
                "phone": "",
                "address": "",
                "website": "",
                "notes": "",
            }
        )
        self.assertTrue(form.is_valid())


# ======================================================================
# DepartmentForm
# ======================================================================


class DepartmentFormTests(FormTestBase):
    def test_valid_data(self):
        form = DepartmentForm(data={"company": self.company.pk, "name": "Sales"})
        self.assertTrue(form.is_valid())

    def test_name_required(self):
        form = DepartmentForm(data={"company": self.company.pk, "name": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_company_required(self):
        form = DepartmentForm(data={"name": "Orphan Dept"})
        self.assertFalse(form.is_valid())
        self.assertIn("company", form.errors)

    def test_default_location_optional(self):
        form = DepartmentForm(data={"company": self.company.pk, "name": "HR"})
        self.assertTrue(form.is_valid())

    def test_with_default_location(self):
        form = DepartmentForm(
            data={
                "company": self.company.pk,
                "name": "Ops",
                "default_location": self.location.pk,
            }
        )
        self.assertTrue(form.is_valid())

    def test_duplicate_company_name_rejected(self):
        """Department name must be unique within a company."""
        form = DepartmentForm(data={"company": self.company.pk, "name": "Engineering"})
        self.assertFalse(form.is_valid())

    def test_same_name_different_company_allowed(self):
        form = DepartmentForm(
            data={"company": self.company_b.pk, "name": "Engineering"}
        )
        self.assertTrue(form.is_valid())


# ======================================================================
# ComponentTypeForm
# ======================================================================


class ComponentTypeFormTests(FormTestBase):
    def test_valid_data(self):
        form = ComponentTypeForm(data={"type_name": "SSD"})
        self.assertTrue(form.is_valid())

    def test_type_name_required(self):
        form = ComponentTypeForm(data={"type_name": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("type_name", form.errors)

    def test_duplicate_type_name_rejected(self):
        form = ComponentTypeForm(data={"type_name": "RAM"})
        self.assertFalse(form.is_valid())
        self.assertIn("type_name", form.errors)

    def test_attributes_optional(self):
        form = ComponentTypeForm(data={"type_name": "GPU"})
        self.assertTrue(form.is_valid())

    def test_attributes_with_json(self):
        form = ComponentTypeForm(
            data={"type_name": "CPU", "attributes": '{"cores": 8}'}
        )
        self.assertTrue(form.is_valid())

    def test_edit_preserves_unique(self):
        """Editing a component type without changing type_name should work."""
        form = ComponentTypeForm(
            data={"type_name": "RAM"},
            instance=self.component_type,
        )
        self.assertTrue(form.is_valid())


# ======================================================================
# EmployeeForm
# ======================================================================


class EmployeeFormTests(FormTestBase):
    def test_valid_minimal_data(self):
        form = EmployeeForm(data={"name": "New Employee", "status": "active"})
        self.assertTrue(form.is_valid())

    def test_name_required(self):
        form = EmployeeForm(data={"name": "", "status": "active"})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_status_required(self):
        form = EmployeeForm(data={"name": "No Status"})
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_invalid_status_rejected(self):
        form = EmployeeForm(data={"name": "Bad Status", "status": "unknown"})
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_valid_full_data(self):
        form = EmployeeForm(
            data={
                "name": "Full Employee",
                "employee_id": "EMP-FULL",
                "email": "full@example.com",
                "phone": "+88012345",
                "extension": "123",
                "company": self.company.pk,
                "department": self.department.pk,
                "location": self.location.pk,
                "position": "Engineer",
                "status": "active",
            }
        )
        self.assertTrue(form.is_valid())

    def test_duplicate_employee_id_rejected(self):
        form = EmployeeForm(
            data={"name": "Dup ID", "employee_id": "EMP-001", "status": "active"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("employee_id", form.errors)

    def test_blank_employee_id_allowed(self):
        """employee_id can be blank (auto-generated or optional)."""
        form = EmployeeForm(
            data={"name": "No ID Employee", "employee_id": "", "status": "active"}
        )
        self.assertTrue(form.is_valid())

    def test_invalid_email_rejected(self):
        form = EmployeeForm(
            data={"name": "Bad Email", "email": "not-an-email", "status": "active"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_optional_fields_blank(self):
        form = EmployeeForm(
            data={
                "name": "Minimal Employee",
                "employee_id": "",
                "email": "",
                "phone": "",
                "extension": "",
                "position": "",
                "status": "active",
            }
        )
        self.assertTrue(form.is_valid())


# ======================================================================
# AssetModelForm
# ======================================================================


class AssetModelFormTests(FormTestBase):
    def test_valid_data(self):
        form = AssetModelForm(
            data={
                "category": self.category.pk,
                "manufacturer": "HP",
                "model_name": "EliteBook 840",
            }
        )
        self.assertTrue(form.is_valid())

    def test_category_required(self):
        form = AssetModelForm(data={"manufacturer": "HP", "model_name": "EliteBook"})
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_model_name_required(self):
        form = AssetModelForm(
            data={"category": self.category.pk, "manufacturer": "HP", "model_name": ""}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("model_name", form.errors)

    def test_manufacturer_optional(self):
        form = AssetModelForm(
            data={
                "category": self.category.pk,
                "manufacturer": "",
                "model_name": "Custom Build",
            }
        )
        self.assertTrue(form.is_valid())

    def test_duplicate_category_manufacturer_model_name_rejected(self):
        """UniqueConstraint on (category, manufacturer, model_name)."""
        form = AssetModelForm(
            data={
                "category": self.category.pk,
                "manufacturer": "Dell",
                "model_name": "Latitude 5540",
            }
        )
        self.assertFalse(form.is_valid())

    def test_same_model_name_different_manufacturer_allowed(self):
        form = AssetModelForm(
            data={
                "category": self.category.pk,
                "manufacturer": "Lenovo",
                "model_name": "Latitude 5540",
            }
        )
        self.assertTrue(form.is_valid())

    def test_model_number_optional(self):
        form = AssetModelForm(
            data={
                "category": self.category.pk,
                "model_name": "ThinkPad",
                "model_number": "TP-123",
            }
        )
        self.assertTrue(form.is_valid())

    def test_notes_optional(self):
        form = AssetModelForm(
            data={
                "category": self.category.pk,
                "model_name": "WithNotes",
                "notes": "End of life 2025",
            }
        )
        self.assertTrue(form.is_valid())


# ======================================================================
# AssetForm
# ======================================================================


class AssetFormTests(FormTestBase):
    def test_valid_minimal_data(self):
        form = AssetForm(
            data={
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "A-NEW",
                "status": "pending",
            }
        )
        self.assertTrue(form.is_valid())

    def test_asset_model_required(self):
        form = AssetForm(
            data={"company": self.company.pk, "asset_tag": "FAIL", "status": "pending"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("asset_model", form.errors)

    def test_asset_tag_optional(self):
        """Asset tag can be blank – it gets auto-generated on save."""
        form = AssetForm(
            data={
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "",
                "status": "pending",
            }
        )
        self.assertTrue(form.is_valid())

    def test_duplicate_asset_tag_rejected(self):
        form = AssetForm(
            data={
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "ASSET-001",
                "status": "pending",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("asset_tag", form.errors)

    def test_invalid_status_rejected(self):
        form = AssetForm(
            data={
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "A-BAD",
                "status": "bogus_status",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_valid_status_choices(self):
        for status_val, _ in Asset.STATUS_CHOICES:
            form = AssetForm(
                data={
                    "company": self.company.pk,
                    "asset_model": self.asset_model.pk,
                    "asset_tag": f"A-{status_val.upper()}",
                    "status": status_val,
                }
            )
            self.assertTrue(
                form.is_valid(),
                f"Status '{status_val}' should be valid, errors: {form.errors}",
            )

    def test_purchase_cost_negative_rejected(self):
        form = AssetForm(
            data={
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "A-NEG",
                "status": "pending",
                "purchase_cost": "-100",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("purchase_cost", form.errors)

    def test_purchase_cost_zero_accepted(self):
        form = AssetForm(
            data={
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "A-ZERO",
                "status": "pending",
                "purchase_cost": "0.00",
            }
        )
        self.assertTrue(form.is_valid())

    def test_all_optional_fields_blank(self):
        form = AssetForm(
            data={
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "",
                "status": "pending",
                "serial_number": "",
                "purchase_date": "",
                "purchase_cost": "",
                "warranty_expiry_date": "",
                "notes": "",
            }
        )
        self.assertTrue(form.is_valid())

    def test_edit_existing_asset(self):
        form = AssetForm(
            data={
                "asset_model": self.asset_model.pk,
                "asset_tag": "ASSET-001",
                "status": "in_repair",
                "company": self.company.pk,
            },
            instance=self.asset,
        )
        self.assertTrue(form.is_valid())
        obj = form.save()
        self.assertEqual(obj.status, "in_repair")


# ======================================================================
# ComponentForm
# ======================================================================


class ComponentFormTests(FormTestBase):
    def test_valid_minimal_data(self):
        form = ComponentForm(
            data={
                "component_type": self.component_type.pk,
                "status": "spare",
            }
        )
        self.assertTrue(form.is_valid())

    def test_component_type_required(self):
        form = ComponentForm(data={"status": "spare"})
        self.assertFalse(form.is_valid())
        self.assertIn("component_type", form.errors)

    def test_component_tag_optional(self):
        form = ComponentForm(
            data={
                "component_type": self.component_type.pk,
                "component_tag": "",
                "status": "spare",
            }
        )
        self.assertTrue(form.is_valid())

    def test_invalid_status_rejected(self):
        form = ComponentForm(
            data={
                "component_type": self.component_type.pk,
                "status": "invalid_status",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_valid_status_choices(self):
        for status_val, _ in Component.STATUS_CHOICES:
            tag = f"COMP-{status_val.upper()}"
            form = ComponentForm(
                data={
                    "component_type": self.component_type.pk,
                    "component_tag": tag,
                    "status": status_val,
                    # installed requires parent_asset
                    **(
                        {"parent_asset": self.asset.pk}
                        if status_val == "installed"
                        else {}
                    ),
                }
            )
            self.assertTrue(
                form.is_valid(),
                f"Status '{status_val}' should be valid, errors: {form.errors}",
            )

    def test_all_optional_fields_blank(self):
        form = ComponentForm(
            data={
                "component_type": self.component_type.pk,
                "component_tag": "",
                "manufacturer": "",
                "model": "",
                "serial_number": "",
                "specifications": "",
                "purchase_date": "",
                "warranty_expiry_date": "",
                "status": "spare",
                "installation_date": "",
                "removal_date": "",
                "notes": "",
            }
        )
        self.assertTrue(form.is_valid())


# ======================================================================
# RequisitionForm
# ======================================================================


class RequisitionFormTests(FormTestBase):
    def test_valid_data(self):
        form = RequisitionForm(
            data={
                "requisition_number": "REQ-NEW",
                "company": self.company.pk,
                "department": self.department.pk,
                "requested_by": self.employee.pk,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "normal",
                "status": "pending",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_requisition_number_required(self):
        form = RequisitionForm(
            data={
                "requisition_number": "",
                "company": self.company.pk,
                "department": self.department.pk,
                "requested_by": self.employee.pk,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "normal",
                "status": "pending",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("requisition_number", form.errors)

    def test_company_required(self):
        form = RequisitionForm(
            data={
                "requisition_number": "REQ-NOCOMP",
                "department": self.department.pk,
                "requested_by": self.employee.pk,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "normal",
                "status": "pending",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("company", form.errors)

    def test_department_required(self):
        form = RequisitionForm(
            data={
                "requisition_number": "REQ-NODEPT",
                "company": self.company.pk,
                "requested_by": self.employee.pk,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "normal",
                "status": "pending",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("department", form.errors)

    def test_requested_by_required(self):
        form = RequisitionForm(
            data={
                "requisition_number": "REQ-NOREQ",
                "company": self.company.pk,
                "department": self.department.pk,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "normal",
                "status": "pending",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("requested_by", form.errors)

    def test_duplicate_requisition_number_rejected(self):
        form = RequisitionForm(
            data={
                "requisition_number": "REQ-001",
                "company": self.company.pk,
                "department": self.department.pk,
                "requested_by": self.employee.pk,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "normal",
                "status": "pending",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("requisition_number", form.errors)

    def test_invalid_priority_rejected(self):
        form = RequisitionForm(
            data={
                "requisition_number": "REQ-BADP",
                "company": self.company.pk,
                "department": self.department.pk,
                "requested_by": self.employee.pk,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "critical",
                "status": "pending",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("priority", form.errors)

    def test_valid_priority_choices(self):
        for priority_val, _ in Requisition.PRIORITY_CHOICES:
            form = RequisitionForm(
                data={
                    "requisition_number": f"REQ-{priority_val.upper()}",
                    "company": self.company.pk,
                    "department": self.department.pk,
                    "requested_by": self.employee.pk,
                    "requisition_date": timezone.now().date().isoformat(),
                    "priority": priority_val,
                    "status": "pending",
                }
            )
            self.assertTrue(
                form.is_valid(),
                f"Priority '{priority_val}' should be valid, errors: {form.errors}",
            )

    def test_approved_by_optional(self):
        form = RequisitionForm(
            data={
                "requisition_number": "REQ-NOAPP",
                "company": self.company.pk,
                "department": self.department.pk,
                "requested_by": self.employee.pk,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "normal",
                "status": "pending",
            }
        )
        self.assertTrue(form.is_valid())


# ======================================================================
# PurchaseInvoiceForm
# ======================================================================


class PurchaseInvoiceFormTests(FormTestBase):
    def test_valid_data(self):
        form = PurchaseInvoiceForm(
            data={
                "invoice_number": "INV-NEW",
                "company": self.company.pk,
                "vendor": self.vendor.pk,
                "invoice_date": timezone.now().date().isoformat(),
                "total_amount": "5000.00",
                "payment_status": "unpaid",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_invoice_number_required(self):
        form = PurchaseInvoiceForm(
            data={
                "invoice_number": "",
                "company": self.company.pk,
                "vendor": self.vendor.pk,
                "invoice_date": timezone.now().date().isoformat(),
                "total_amount": "1000",
                "payment_status": "unpaid",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("invoice_number", form.errors)

    def test_duplicate_invoice_number_rejected(self):
        form = PurchaseInvoiceForm(
            data={
                "invoice_number": "INV-001",
                "company": self.company.pk,
                "vendor": self.vendor.pk,
                "invoice_date": timezone.now().date().isoformat(),
                "total_amount": "1000",
                "payment_status": "unpaid",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("invoice_number", form.errors)

    def test_company_required(self):
        form = PurchaseInvoiceForm(
            data={
                "invoice_number": "INV-NOCOMP",
                "vendor": self.vendor.pk,
                "invoice_date": timezone.now().date().isoformat(),
                "total_amount": "1000",
                "payment_status": "unpaid",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("company", form.errors)

    def test_vendor_required(self):
        form = PurchaseInvoiceForm(
            data={
                "invoice_number": "INV-NOVEND",
                "company": self.company.pk,
                "invoice_date": timezone.now().date().isoformat(),
                "total_amount": "1000",
                "payment_status": "unpaid",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("vendor", form.errors)

    def test_total_amount_required(self):
        form = PurchaseInvoiceForm(
            data={
                "invoice_number": "INV-NOAMT",
                "company": self.company.pk,
                "vendor": self.vendor.pk,
                "invoice_date": timezone.now().date().isoformat(),
                "total_amount": "",
                "payment_status": "unpaid",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("total_amount", form.errors)

    def test_negative_total_amount_rejected(self):
        form = PurchaseInvoiceForm(
            data={
                "invoice_number": "INV-NEG",
                "company": self.company.pk,
                "vendor": self.vendor.pk,
                "invoice_date": timezone.now().date().isoformat(),
                "total_amount": "-500",
                "payment_status": "unpaid",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("total_amount", form.errors)

    def test_payment_optional_fields(self):
        form = PurchaseInvoiceForm(
            data={
                "invoice_number": "INV-OPT",
                "company": self.company.pk,
                "vendor": self.vendor.pk,
                "invoice_date": timezone.now().date().isoformat(),
                "total_amount": "500",
                "payment_status": "unpaid",
                "payment_date": "",
                "payment_method": "",
                "payment_reference": "",
                "received_date": "",
                "notes": "",
            }
        )
        self.assertTrue(form.is_valid())

    def test_invalid_payment_status_rejected(self):
        form = PurchaseInvoiceForm(
            data={
                "invoice_number": "INV-BADPS",
                "company": self.company.pk,
                "vendor": self.vendor.pk,
                "invoice_date": timezone.now().date().isoformat(),
                "total_amount": "1000",
                "payment_status": "overdue",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("payment_status", form.errors)


# ======================================================================
# InvoiceLineItemForm
# ======================================================================


class InvoiceLineItemFormTests(FormTestBase):
    def test_valid_asset_line_item(self):
        form = InvoiceLineItemForm(
            data={
                "invoice": self.invoice.pk,
                "line_number": 1,
                "company": self.company.pk,
                "department": self.department.pk,
                "item_type": "asset",
                "description": "Laptop order",
                "quantity": 5,
                "item_cost": "100.00",
                "asset_model": self.asset_model.pk,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_component_line_item(self):
        form = InvoiceLineItemForm(
            data={
                "invoice": self.invoice.pk,
                "line_number": 2,
                "company": self.company.pk,
                "department": self.department.pk,
                "item_type": "component",
                "description": "RAM order",
                "quantity": 10,
                "item_cost": "50.00",
                "component_type": self.component_type.pk,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_service_line_item(self):
        form = InvoiceLineItemForm(
            data={
                "invoice": self.invoice.pk,
                "line_number": 3,
                "company": self.company.pk,
                "department": self.department.pk,
                "item_type": "service",
                "description": "Installation service",
                "quantity": 1,
                "item_cost": "200.00",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_invoice_required(self):
        form = InvoiceLineItemForm(
            data={
                "line_number": 1,
                "company": self.company.pk,
                "department": self.department.pk,
                "item_type": "asset",
                "description": "Missing invoice",
                "quantity": 1,
                "item_cost": "100.00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("invoice", form.errors)

    def test_quantity_minimum_one(self):
        form = InvoiceLineItemForm(
            data={
                "invoice": self.invoice.pk,
                "line_number": 1,
                "company": self.company.pk,
                "department": self.department.pk,
                "item_type": "asset",
                "description": "Zero qty",
                "quantity": 0,
                "item_cost": "100.00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_negative_item_cost_rejected(self):
        form = InvoiceLineItemForm(
            data={
                "invoice": self.invoice.pk,
                "line_number": 1,
                "company": self.company.pk,
                "department": self.department.pk,
                "item_type": "asset",
                "description": "Negative cost",
                "quantity": 1,
                "item_cost": "-50.00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("item_cost", form.errors)

    def test_with_invoice_kwarg_hides_invoice_field(self):
        """When invoice kwarg is provided, invoice field becomes hidden."""
        form = InvoiceLineItemForm(
            data={
                "invoice": self.invoice.pk,
                "line_number": 1,
                "company": self.company.pk,
                "department": self.department.pk,
                "item_type": "service",
                "description": "Test",
                "quantity": 1,
                "item_cost": "100.00",
            },
            invoice=self.invoice,
        )
        from django.forms import HiddenInput

        self.assertIsInstance(form.fields["invoice"].widget, HiddenInput)

    def test_with_invoice_kwarg_auto_sets_line_number(self):
        """When invoice kwarg is provided and no instance, line_number auto-increments."""
        # Create a line item first
        InvoiceLineItem.objects.create(
            invoice=self.invoice,
            line_number=1,
            company=self.company,
            department=self.department,
            item_type="asset",
            description="First line",
            quantity=1,
            item_cost=Decimal("100.00"),
            asset_model=self.asset_model,
        )
        form = InvoiceLineItemForm(invoice=self.invoice)
        self.assertEqual(form.fields["line_number"].initial, 2)


# ======================================================================
# RequisitionItemForm
# ======================================================================


class RequisitionItemFormTests(FormTestBase):
    def test_valid_asset_item(self):
        form = RequisitionItemForm(
            data={
                "requisition": self.requisition.pk,
                "item_type": "asset",
                "asset": self.asset.pk,
            },
            requisition=self.requisition,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_component_item(self):
        form = RequisitionItemForm(
            data={
                "requisition": self.requisition.pk,
                "item_type": "component",
                "component": self.component.pk,
            },
            requisition=self.requisition,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_item_type_required(self):
        form = RequisitionItemForm(
            data={
                "requisition": self.requisition.pk,
                "asset": self.asset.pk,
            },
            requisition=self.requisition,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("item_type", form.errors)

    def test_asset_required_for_asset_type(self):
        form = RequisitionItemForm(
            data={
                "requisition": self.requisition.pk,
                "item_type": "asset",
            },
            requisition=self.requisition,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("asset", form.errors)

    def test_component_required_for_component_type(self):
        form = RequisitionItemForm(
            data={
                "requisition": self.requisition.pk,
                "item_type": "component",
            },
            requisition=self.requisition,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("component", form.errors)

    def test_asset_item_rejects_component(self):
        """Setting both asset and component on an asset item should fail."""
        form = RequisitionItemForm(
            data={
                "requisition": self.requisition.pk,
                "item_type": "asset",
                "asset": self.asset.pk,
                "component": self.component.pk,
            },
            requisition=self.requisition,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("component", form.errors)

    def test_component_item_rejects_asset(self):
        """Setting both asset and component on a component item should fail."""
        form = RequisitionItemForm(
            data={
                "requisition": self.requisition.pk,
                "item_type": "component",
                "asset": self.asset.pk,
                "component": self.component.pk,
            },
            requisition=self.requisition,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("asset", form.errors)

    def test_notes_optional(self):
        form = RequisitionItemForm(
            data={
                "requisition": self.requisition.pk,
                "item_type": "asset",
                "asset": self.asset.pk,
                "notes": "",
            },
            requisition=self.requisition,
        )
        self.assertTrue(form.is_valid())

    def test_with_requisition_kwarg_hides_field(self):
        from django.forms import HiddenInput

        form = RequisitionItemForm(
            data={
                "requisition": self.requisition.pk,
                "item_type": "asset",
                "asset": self.asset.pk,
            },
            requisition=self.requisition,
        )
        self.assertIsInstance(form.fields["requisition"].widget, HiddenInput)


# ======================================================================
# MaintenanceRecordForm
# ======================================================================


class MaintenanceRecordFormTests(FormTestBase):
    def test_valid_data(self):
        form = MaintenanceRecordForm(
            data={
                "asset": self.asset.pk,
                "maintenance_type": "repair",
                "maintenance_date": timezone.now().date().isoformat(),
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_asset_required(self):
        form = MaintenanceRecordForm(
            data={
                "maintenance_type": "repair",
                "maintenance_date": timezone.now().date().isoformat(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("asset", form.errors)

    def test_maintenance_type_required(self):
        form = MaintenanceRecordForm(
            data={
                "asset": self.asset.pk,
                "maintenance_date": timezone.now().date().isoformat(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("maintenance_type", form.errors)

    def test_maintenance_date_required(self):
        form = MaintenanceRecordForm(
            data={
                "asset": self.asset.pk,
                "maintenance_type": "repair",
                "maintenance_date": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("maintenance_date", form.errors)

    def test_invalid_maintenance_type_rejected(self):
        form = MaintenanceRecordForm(
            data={
                "asset": self.asset.pk,
                "maintenance_type": "inspection",
                "maintenance_date": timezone.now().date().isoformat(),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("maintenance_type", form.errors)

    def test_cost_optional(self):
        form = MaintenanceRecordForm(
            data={
                "asset": self.asset.pk,
                "maintenance_type": "upgrade",
                "maintenance_date": timezone.now().date().isoformat(),
                "cost": "",
            }
        )
        self.assertTrue(form.is_valid())

    def test_negative_cost_rejected(self):
        form = MaintenanceRecordForm(
            data={
                "asset": self.asset.pk,
                "maintenance_type": "repair",
                "maintenance_date": timezone.now().date().isoformat(),
                "cost": "-100",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("cost", form.errors)

    def test_valid_full_data(self):
        form = MaintenanceRecordForm(
            data={
                "asset": self.asset.pk,
                "maintenance_type": "repair",
                "performed_by": "Tech Guy",
                "maintenance_date": timezone.now().date().isoformat(),
                "cost": "250.00",
                "description": "Replaced screen",
                "next_maintenance_date": (
                    timezone.now().date() + timezone.timedelta(days=90)
                ).isoformat(),
            }
        )
        self.assertTrue(form.is_valid(), form.errors)


# ======================================================================
# SparePartsInventoryForm
# ======================================================================


class SparePartsInventoryFormTests(FormTestBase):
    def test_valid_data(self):
        form = SparePartsInventoryForm(
            data={
                "component_type": self.component_type.pk,
                "quantity_available": 5,
                "quantity_minimum": 2,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_component_type_required(self):
        form = SparePartsInventoryForm(
            data={
                "quantity_available": 5,
                "quantity_minimum": 2,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("component_type", form.errors)

    def test_quantity_available_disabled(self):
        """quantity_available is auto-computed and should be disabled."""
        form = SparePartsInventoryForm()
        self.assertTrue(form.fields["quantity_available"].disabled)

    def test_optional_fields(self):
        form = SparePartsInventoryForm(
            data={
                "component_type": self.component_type.pk,
                "quantity_available": 0,
                "quantity_minimum": 0,
                "manufacturer": "",
                "model": "",
                "specifications": "",
                "last_restocked": "",
                "notes": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)


# ======================================================================
# BaseForm widget styling
# ======================================================================


class BaseFormWidgetStylingTests(FormTestBase):
    """Test that BaseForm applies CSS classes to all widget types."""

    def test_select_fields_get_form_select_class(self):
        form = AssetForm()
        status_widget = form.fields["status"].widget
        self.assertIn("form-select", status_widget.attrs.get("class", ""))

    def test_textarea_fields_get_form_textarea_class(self):
        form = CompanyForm()
        notes_widget = form.fields["notes"].widget
        self.assertIn("form-textarea", notes_widget.attrs.get("class", ""))

    def test_text_input_fields_get_form_input_class(self):
        form = LocationForm()
        name_widget = form.fields["name"].widget
        self.assertIn("form-input", name_widget.attrs.get("class", ""))

    def test_date_input_fields_get_form_input_class(self):
        form = AssetForm()
        date_widget = form.fields["purchase_date"].widget
        self.assertIn("form-input", date_widget.attrs.get("class", ""))

    def test_required_fields_have_required_attr(self):
        form = CategoryForm()
        name_widget = form.fields["name"].widget
        self.assertEqual(name_widget.attrs.get("required"), "required")

    def test_non_required_fields_lack_required_attr(self):
        form = CategoryForm()
        desc_widget = form.fields["description"].widget
        self.assertNotIn("required", desc_widget.attrs)

    def test_searchable_select_has_data_attribute(self):
        form = AssetForm()
        company_widget = form.fields["company"].widget
        self.assertIn("data-searchable", company_widget.attrs)
        self.assertEqual(company_widget.attrs["data-searchable"], "company")

    def test_searchable_select_has_placeholder(self):
        form = AssetForm()
        company_widget = form.fields["company"].widget
        self.assertIn("data-placeholder", company_widget.attrs)

    def test_number_input_has_min_attr(self):
        form = PurchaseInvoiceForm()
        amount_widget = form.fields["total_amount"].widget
        self.assertEqual(amount_widget.attrs.get("min"), "0")

    def test_number_input_has_step_attr(self):
        form = PurchaseInvoiceForm()
        amount_widget = form.fields["total_amount"].widget
        self.assertEqual(amount_widget.attrs.get("step"), "0.01")
