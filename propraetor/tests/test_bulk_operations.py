"""
Tests for bulk operations across all major models.

Covers:
- Bulk delete for: assets, companies, locations, categories, vendors,
  departments, component types, employees, components, asset models,
  spare parts, maintenance records, invoices, requisitions
- Bulk status change for assets
- Bulk unassign for assets and components
- Bulk deactivate for employees/users
- Bulk cancel and bulk fulfill for requisitions
- Bulk mark-paid for invoices
- Empty selection warnings (no IDs selected)
- Partial selection (some IDs valid, some not)
"""

from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from propraetor.models import (
    Asset,
    AssetAssignment,
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
# Shared base
# ======================================================================


class BulkTestBase(TestCase):
    """Shared setUp that creates a logged-in client and common lookup data."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company = Company.objects.create(name="BulkCo", code="BC")
        self.location = Location.objects.create(name="Main Office", city="Dhaka")
        self.department = Department.objects.create(
            company=self.company, name="Engineering"
        )
        self.category = Category.objects.create(name="Laptop")
        self.vendor = Vendor.objects.create(vendor_name="BulkVendor")
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


# ======================================================================
# Bulk delete – Assets
# ======================================================================


class AssetsBulkDeleteTests(BulkTestBase):
    def setUp(self):
        super().setUp()
        self.asset1 = Asset.objects.create(
            company=self.company,
            asset_tag="BD-A1",
            asset_model=self.asset_model,
            status="active",
        )
        self.asset2 = Asset.objects.create(
            company=self.company,
            asset_tag="BD-A2",
            asset_model=self.asset_model,
            status="pending",
        )
        self.asset3 = Asset.objects.create(
            company=self.company,
            asset_tag="BD-A3",
            asset_model=self.asset_model,
            status="retired",
        )

    def test_bulk_delete_selected_assets(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_delete"),
            {"selected_ids": [self.asset1.pk, self.asset2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Asset.objects.filter(pk=self.asset1.pk).exists())
        self.assertFalse(Asset.objects.filter(pk=self.asset2.pk).exists())
        # asset3 should remain
        self.assertTrue(Asset.objects.filter(pk=self.asset3.pk).exists())

    def test_bulk_delete_all_assets(self):
        pks = [self.asset1.pk, self.asset2.pk, self.asset3.pk]
        resp = self.client.post(
            reverse("propraetor:assets_bulk_delete"),
            {"selected_ids": pks},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Asset.objects.filter(pk__in=pks).count(), 0)

    def test_bulk_delete_empty_selection(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        # Nothing should be deleted
        self.assertEqual(Asset.objects.count(), 3)

    def test_bulk_delete_no_selected_ids_param(self):
        resp = self.client.post(reverse("propraetor:assets_bulk_delete"))
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Asset.objects.count(), 3)

    def test_bulk_delete_nonexistent_ids(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_delete"),
            {"selected_ids": [99998, 99999]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Asset.objects.count(), 3)

    def test_bulk_delete_requires_post(self):
        resp = self.client.get(
            reverse("propraetor:assets_bulk_delete"),
        )
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Bulk status change – Assets
# ======================================================================


class AssetsBulkStatusTests(BulkTestBase):
    def setUp(self):
        super().setUp()
        self.asset1 = Asset.objects.create(
            company=self.company,
            asset_tag="BS-A1",
            asset_model=self.asset_model,
            status="active",
        )
        self.asset2 = Asset.objects.create(
            company=self.company,
            asset_tag="BS-A2",
            asset_model=self.asset_model,
            status="pending",
        )
        self.asset3 = Asset.objects.create(
            company=self.company,
            asset_tag="BS-A3",
            asset_model=self.asset_model,
            status="active",
        )

    def test_bulk_status_change_to_retired(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_status"),
            {"selected_ids": [self.asset1.pk, self.asset2.pk], "status": "retired"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset1.refresh_from_db()
        self.asset2.refresh_from_db()
        self.asset3.refresh_from_db()
        self.assertEqual(self.asset1.status, "retired")
        self.assertEqual(self.asset2.status, "retired")
        # asset3 not selected, should be unchanged
        self.assertEqual(self.asset3.status, "active")

    def test_bulk_status_change_to_in_repair(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_status"),
            {"selected_ids": [self.asset1.pk], "status": "in_repair"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.status, "in_repair")

    def test_bulk_status_change_all_valid_statuses(self):
        for status_val, _ in Asset.STATUS_CHOICES:
            resp = self.client.post(
                reverse("propraetor:assets_bulk_status"),
                {"selected_ids": [self.asset1.pk], "status": status_val},
            )
            self.assertIn(resp.status_code, [200, 301, 302])
            self.asset1.refresh_from_db()
            self.assertEqual(self.asset1.status, status_val)

    def test_bulk_status_change_invalid_status(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_status"),
            {"selected_ids": [self.asset1.pk], "status": "bogus"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset1.refresh_from_db()
        # Status should remain unchanged
        self.assertEqual(self.asset1.status, "active")

    def test_bulk_status_change_empty_selection(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_status"),
            {"selected_ids": [], "status": "retired"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.status, "active")

    def test_bulk_status_change_no_status_param(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_status"),
            {"selected_ids": [self.asset1.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.status, "active")

    def test_bulk_status_requires_post(self):
        resp = self.client.get(reverse("propraetor:assets_bulk_status"))
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Bulk unassign – Assets
# ======================================================================


class AssetsBulkUnassignTests(BulkTestBase):
    def setUp(self):
        super().setUp()
        self.emp2 = Employee.objects.create(
            name="John Smith",
            employee_id="EMP-002",
            company=self.company,
            status="active",
        )
        self.asset1 = Asset.objects.create(
            company=self.company,
            asset_tag="BU-A1",
            asset_model=self.asset_model,
            status="active",
            assigned_to=self.employee,
        )
        self.asset2 = Asset.objects.create(
            company=self.company,
            asset_tag="BU-A2",
            asset_model=self.asset_model,
            status="active",
            assigned_to=self.emp2,
        )
        self.asset_unassigned = Asset.objects.create(
            company=self.company,
            asset_tag="BU-A3",
            asset_model=self.asset_model,
            status="active",
            assigned_to=None,
        )

    def test_bulk_unassign_selected_assets(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_unassign"),
            {"selected_ids": [self.asset1.pk, self.asset2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset1.refresh_from_db()
        self.asset2.refresh_from_db()
        self.assertIsNone(self.asset1.assigned_to)
        self.assertIsNone(self.asset2.assigned_to)

    def test_bulk_unassign_already_unassigned(self):
        """Including already-unassigned assets should not cause errors."""
        resp = self.client.post(
            reverse("propraetor:assets_bulk_unassign"),
            {"selected_ids": [self.asset_unassigned.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset_unassigned.refresh_from_db()
        self.assertIsNone(self.asset_unassigned.assigned_to)

    def test_bulk_unassign_mixed_assigned_and_unassigned(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_unassign"),
            {"selected_ids": [self.asset1.pk, self.asset_unassigned.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset1.refresh_from_db()
        self.assertIsNone(self.asset1.assigned_to)

    def test_bulk_unassign_empty_selection(self):
        resp = self.client.post(
            reverse("propraetor:assets_bulk_unassign"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.assigned_to, self.employee)

    def test_bulk_unassign_requires_post(self):
        resp = self.client.get(reverse("propraetor:assets_bulk_unassign"))
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Bulk delete – Companies
# ======================================================================


class CompaniesBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_companies(self):
        c1 = Company.objects.create(name="DelCo1", code="D1")
        c2 = Company.objects.create(name="DelCo2", code="D2")
        resp = self.client.post(
            reverse("propraetor:companies_bulk_delete"),
            {"selected_ids": [c1.pk, c2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Company.objects.filter(pk__in=[c1.pk, c2.pk]).exists())
        # Original company should remain
        self.assertTrue(Company.objects.filter(pk=self.company.pk).exists())

    def test_bulk_delete_companies_empty_selection(self):
        initial_count = Company.objects.count()
        resp = self.client.post(
            reverse("propraetor:companies_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Company.objects.count(), initial_count)

    def test_bulk_delete_companies_requires_post(self):
        resp = self.client.get(reverse("propraetor:companies_bulk_delete"))
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Bulk delete – Locations
# ======================================================================


class LocationsBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_locations(self):
        loc1 = Location.objects.create(name="Del Loc 1")
        loc2 = Location.objects.create(name="Del Loc 2")
        resp = self.client.post(
            reverse("propraetor:locations_bulk_delete"),
            {"selected_ids": [loc1.pk, loc2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Location.objects.filter(pk__in=[loc1.pk, loc2.pk]).exists())

    def test_bulk_delete_locations_empty_selection(self):
        initial_count = Location.objects.count()
        resp = self.client.post(
            reverse("propraetor:locations_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Location.objects.count(), initial_count)


# ======================================================================
# Bulk delete – Categories
# ======================================================================


class CategoriesBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_categories(self):
        cat1 = Category.objects.create(name="Temp Cat 1")
        cat2 = Category.objects.create(name="Temp Cat 2")
        resp = self.client.post(
            reverse("propraetor:categories_bulk_delete"),
            {"selected_ids": [cat1.pk, cat2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Category.objects.filter(pk__in=[cat1.pk, cat2.pk]).exists())

    def test_bulk_delete_categories_empty_selection(self):
        initial_count = Category.objects.count()
        resp = self.client.post(
            reverse("propraetor:categories_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Category.objects.count(), initial_count)


# ======================================================================
# Bulk delete – Vendors
# ======================================================================


class VendorsBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_vendors(self):
        v1 = Vendor.objects.create(vendor_name="Del Vendor 1")
        v2 = Vendor.objects.create(vendor_name="Del Vendor 2")
        resp = self.client.post(
            reverse("propraetor:vendors_bulk_delete"),
            {"selected_ids": [v1.pk, v2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Vendor.objects.filter(pk__in=[v1.pk, v2.pk]).exists())

    def test_bulk_delete_vendors_empty_selection(self):
        initial_count = Vendor.objects.count()
        resp = self.client.post(
            reverse("propraetor:vendors_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Vendor.objects.count(), initial_count)


# ======================================================================
# Bulk delete – Departments
# ======================================================================


class DepartmentsBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_departments(self):
        d1 = Department.objects.create(company=self.company, name="Temp Dept 1")
        d2 = Department.objects.create(company=self.company, name="Temp Dept 2")
        resp = self.client.post(
            reverse("propraetor:departments_bulk_delete"),
            {"selected_ids": [d1.pk, d2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Department.objects.filter(pk__in=[d1.pk, d2.pk]).exists())

    def test_bulk_delete_departments_empty_selection(self):
        initial_count = Department.objects.count()
        resp = self.client.post(
            reverse("propraetor:departments_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Department.objects.count(), initial_count)


# ======================================================================
# Bulk delete – Component Types
# ======================================================================


class ComponentTypesBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_component_types(self):
        ct1 = ComponentType.objects.create(type_name="Temp Type 1")
        ct2 = ComponentType.objects.create(type_name="Temp Type 2")
        resp = self.client.post(
            reverse("propraetor:component_types_bulk_delete"),
            {"selected_ids": [ct1.pk, ct2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(ComponentType.objects.filter(pk__in=[ct1.pk, ct2.pk]).exists())

    def test_bulk_delete_component_types_empty_selection(self):
        initial_count = ComponentType.objects.count()
        resp = self.client.post(
            reverse("propraetor:component_types_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(ComponentType.objects.count(), initial_count)


# ======================================================================
# Bulk delete – Asset Models
# ======================================================================


class AssetModelsBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_asset_models(self):
        cat = Category.objects.create(name="Temp Cat for AM")
        am1 = AssetModel.objects.create(
            category=cat, manufacturer="X", model_name="Model 1"
        )
        am2 = AssetModel.objects.create(
            category=cat, manufacturer="Y", model_name="Model 2"
        )
        resp = self.client.post(
            reverse("propraetor:asset_models_bulk_delete"),
            {"selected_ids": [am1.pk, am2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(AssetModel.objects.filter(pk__in=[am1.pk, am2.pk]).exists())

    def test_bulk_delete_asset_models_empty_selection(self):
        initial_count = AssetModel.objects.count()
        resp = self.client.post(
            reverse("propraetor:asset_models_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(AssetModel.objects.count(), initial_count)


# ======================================================================
# Bulk delete – Components
# ======================================================================


class ComponentsBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_components(self):
        c1 = Component.objects.create(
            component_type=self.component_type,
            manufacturer="A",
            status="spare",
        )
        c2 = Component.objects.create(
            component_type=self.component_type,
            manufacturer="B",
            status="spare",
        )
        resp = self.client.post(
            reverse("propraetor:components_bulk_delete"),
            {"selected_ids": [c1.pk, c2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Component.objects.filter(pk__in=[c1.pk, c2.pk]).exists())

    def test_bulk_delete_components_empty_selection(self):
        initial_count = Component.objects.count()
        resp = self.client.post(
            reverse("propraetor:components_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Component.objects.count(), initial_count)


# ======================================================================
# Bulk unassign – Components
# ======================================================================


class ComponentsBulkUnassignTests(BulkTestBase):
    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            company=self.company,
            asset_tag="CU-PARENT",
            asset_model=self.asset_model,
            status="active",
        )
        self.comp1 = Component.objects.create(
            component_type=self.component_type,
            manufacturer="A",
            parent_asset=self.asset,
            status="installed",
        )
        self.comp2 = Component.objects.create(
            component_type=self.component_type,
            manufacturer="B",
            parent_asset=self.asset,
            status="installed",
        )
        self.comp_spare = Component.objects.create(
            component_type=self.component_type,
            manufacturer="C",
            parent_asset=None,
            status="spare",
        )

    def test_bulk_unassign_components(self):
        resp = self.client.post(
            reverse("propraetor:components_bulk_unassign"),
            {"selected_ids": [self.comp1.pk, self.comp2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.comp1.refresh_from_db()
        self.comp2.refresh_from_db()
        self.assertIsNone(self.comp1.parent_asset)
        self.assertIsNone(self.comp2.parent_asset)

    def test_bulk_unassign_already_unassigned_component(self):
        resp = self.client.post(
            reverse("propraetor:components_bulk_unassign"),
            {"selected_ids": [self.comp_spare.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.comp_spare.refresh_from_db()
        self.assertIsNone(self.comp_spare.parent_asset)

    def test_bulk_unassign_components_empty_selection(self):
        resp = self.client.post(
            reverse("propraetor:components_bulk_unassign"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.comp1.refresh_from_db()
        self.assertEqual(self.comp1.parent_asset, self.asset)


# ======================================================================
# Bulk deactivate – Employees/Users
# ======================================================================


class UsersBulkDeactivateTests(BulkTestBase):
    def setUp(self):
        super().setUp()
        self.emp2 = Employee.objects.create(
            name="Active User 2",
            employee_id="EMP-A2",
            company=self.company,
            status="active",
        )
        self.emp3 = Employee.objects.create(
            name="Active User 3",
            employee_id="EMP-A3",
            company=self.company,
            status="active",
        )

    def test_bulk_deactivate_selected_users(self):
        resp = self.client.post(
            reverse("propraetor:users_bulk_deactivate"),
            {"selected_ids": [self.employee.pk, self.emp2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.employee.refresh_from_db()
        self.emp2.refresh_from_db()
        self.emp3.refresh_from_db()
        self.assertEqual(self.employee.status, "inactive")
        self.assertEqual(self.emp2.status, "inactive")
        # emp3 not selected, should remain active
        self.assertEqual(self.emp3.status, "active")

    def test_bulk_deactivate_empty_selection(self):
        resp = self.client.post(
            reverse("propraetor:users_bulk_deactivate"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, "active")

    def test_bulk_deactivate_already_inactive(self):
        self.employee.status = "inactive"
        self.employee.save()
        resp = self.client.post(
            reverse("propraetor:users_bulk_deactivate"),
            {"selected_ids": [self.employee.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, "inactive")

    def test_bulk_deactivate_requires_post(self):
        resp = self.client.get(reverse("propraetor:users_bulk_deactivate"))
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Bulk delete – Employees/Users
# ======================================================================


class UsersBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_users(self):
        e1 = Employee.objects.create(
            name="Del User 1", employee_id="DEL-001", status="active"
        )
        e2 = Employee.objects.create(
            name="Del User 2", employee_id="DEL-002", status="active"
        )
        resp = self.client.post(
            reverse("propraetor:users_bulk_delete"),
            {"selected_ids": [e1.pk, e2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Employee.objects.filter(pk__in=[e1.pk, e2.pk]).exists())

    def test_bulk_delete_users_empty_selection(self):
        initial_count = Employee.objects.count()
        resp = self.client.post(
            reverse("propraetor:users_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Employee.objects.count(), initial_count)


# ======================================================================
# Bulk delete – Spare Parts
# ======================================================================


class SparePartsBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_spare_parts(self):
        sp1 = SparePartsInventory.objects.create(
            component_type=self.component_type,
            quantity_available=5,
            quantity_minimum=2,
        )
        ct2 = ComponentType.objects.create(type_name="SSD")
        sp2 = SparePartsInventory.objects.create(
            component_type=ct2,
            quantity_available=3,
            quantity_minimum=1,
        )
        resp = self.client.post(
            reverse("propraetor:spare_parts_bulk_delete"),
            {"selected_ids": [sp1.pk, sp2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(
            SparePartsInventory.objects.filter(pk__in=[sp1.pk, sp2.pk]).exists()
        )

    def test_bulk_delete_spare_parts_empty_selection(self):
        initial_count = SparePartsInventory.objects.count()
        resp = self.client.post(
            reverse("propraetor:spare_parts_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(SparePartsInventory.objects.count(), initial_count)


# ======================================================================
# Bulk delete – Maintenance Records
# ======================================================================


class MaintenanceBulkDeleteTests(BulkTestBase):
    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            company=self.company,
            asset_tag="MAINT-BULK",
            asset_model=self.asset_model,
            status="active",
        )

    def test_bulk_delete_maintenance_records(self):
        m1 = MaintenanceRecord.objects.create(
            asset=self.asset,
            maintenance_type="repair",
            maintenance_date=timezone.now().date(),
        )
        m2 = MaintenanceRecord.objects.create(
            asset=self.asset,
            maintenance_type="upgrade",
            maintenance_date=timezone.now().date(),
        )
        resp = self.client.post(
            reverse("propraetor:maintenance_bulk_delete"),
            {"selected_ids": [m1.pk, m2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(
            MaintenanceRecord.objects.filter(pk__in=[m1.pk, m2.pk]).exists()
        )

    def test_bulk_delete_maintenance_empty_selection(self):
        initial_count = MaintenanceRecord.objects.count()
        resp = self.client.post(
            reverse("propraetor:maintenance_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(MaintenanceRecord.objects.count(), initial_count)


# ======================================================================
# Bulk delete – Invoices
# ======================================================================


class InvoicesBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_invoices(self):
        inv1 = PurchaseInvoice.objects.create(
            invoice_number="BD-INV-1",
            company=self.company,
            vendor=self.vendor,
            invoice_date=timezone.now().date(),
            total_amount=Decimal("1000.00"),
        )
        inv2 = PurchaseInvoice.objects.create(
            invoice_number="BD-INV-2",
            company=self.company,
            vendor=self.vendor,
            invoice_date=timezone.now().date(),
            total_amount=Decimal("2000.00"),
        )
        resp = self.client.post(
            reverse("propraetor:invoices_bulk_delete"),
            {"selected_ids": [inv1.pk, inv2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(
            PurchaseInvoice.objects.filter(pk__in=[inv1.pk, inv2.pk]).exists()
        )

    def test_bulk_delete_invoices_empty_selection(self):
        initial_count = PurchaseInvoice.objects.count()
        resp = self.client.post(
            reverse("propraetor:invoices_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(PurchaseInvoice.objects.count(), initial_count)


# ======================================================================
# Bulk mark paid – Invoices
# ======================================================================


class InvoicesBulkMarkPaidTests(BulkTestBase):
    def setUp(self):
        super().setUp()
        self.inv1 = PurchaseInvoice.objects.create(
            invoice_number="PAY-INV-1",
            company=self.company,
            vendor=self.vendor,
            invoice_date=timezone.now().date(),
            total_amount=Decimal("1000.00"),
            payment_status="unpaid",
        )
        self.inv2 = PurchaseInvoice.objects.create(
            invoice_number="PAY-INV-2",
            company=self.company,
            vendor=self.vendor,
            invoice_date=timezone.now().date(),
            total_amount=Decimal("2000.00"),
            payment_status="unpaid",
        )
        self.inv_paid = PurchaseInvoice.objects.create(
            invoice_number="PAY-INV-3",
            company=self.company,
            vendor=self.vendor,
            invoice_date=timezone.now().date(),
            total_amount=Decimal("500.00"),
            payment_status="paid",
        )

    def test_bulk_mark_paid(self):
        resp = self.client.post(
            reverse("propraetor:invoices_bulk_mark_paid"),
            {"selected_ids": [self.inv1.pk, self.inv2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.inv1.refresh_from_db()
        self.inv2.refresh_from_db()
        self.assertEqual(self.inv1.payment_status, "paid")
        self.assertEqual(self.inv2.payment_status, "paid")

    def test_bulk_mark_paid_already_paid(self):
        resp = self.client.post(
            reverse("propraetor:invoices_bulk_mark_paid"),
            {"selected_ids": [self.inv_paid.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.inv_paid.refresh_from_db()
        self.assertEqual(self.inv_paid.payment_status, "paid")

    def test_bulk_mark_paid_empty_selection(self):
        resp = self.client.post(
            reverse("propraetor:invoices_bulk_mark_paid"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.inv1.refresh_from_db()
        self.assertEqual(self.inv1.payment_status, "unpaid")

    def test_bulk_mark_paid_sets_payment_date(self):
        resp = self.client.post(
            reverse("propraetor:invoices_bulk_mark_paid"),
            {"selected_ids": [self.inv1.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.inv1.refresh_from_db()
        self.assertIsNotNone(self.inv1.payment_date)


# ======================================================================
# Bulk delete – Requisitions
# ======================================================================


class RequisitionsBulkDeleteTests(BulkTestBase):
    def test_bulk_delete_requisitions(self):
        r1 = Requisition.objects.create(
            requisition_number="BD-REQ-1",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=timezone.now().date(),
            status="pending",
        )
        r2 = Requisition.objects.create(
            requisition_number="BD-REQ-2",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=timezone.now().date(),
            status="pending",
        )
        resp = self.client.post(
            reverse("propraetor:requisitions_bulk_delete"),
            {"selected_ids": [r1.pk, r2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Requisition.objects.filter(pk__in=[r1.pk, r2.pk]).exists())

    def test_bulk_delete_requisitions_empty_selection(self):
        initial_count = Requisition.objects.count()
        resp = self.client.post(
            reverse("propraetor:requisitions_bulk_delete"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertEqual(Requisition.objects.count(), initial_count)


# ======================================================================
# Bulk cancel – Requisitions
# ======================================================================


class RequisitionsBulkCancelTests(BulkTestBase):
    def setUp(self):
        super().setUp()
        self.req1 = Requisition.objects.create(
            requisition_number="BC-REQ-1",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=timezone.now().date(),
            status="pending",
        )
        self.req2 = Requisition.objects.create(
            requisition_number="BC-REQ-2",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=timezone.now().date(),
            status="pending",
        )
        self.req_fulfilled = Requisition.objects.create(
            requisition_number="BC-REQ-3",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=timezone.now().date(),
            status="fulfilled",
            fulfilled_date=timezone.now().date(),
        )

    def test_bulk_cancel_pending_requisitions(self):
        resp = self.client.post(
            reverse("propraetor:requisitions_bulk_cancel"),
            {"selected_ids": [self.req1.pk, self.req2.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.req1.refresh_from_db()
        self.req2.refresh_from_db()
        self.assertEqual(self.req1.status, "cancelled")
        self.assertEqual(self.req2.status, "cancelled")

    def test_bulk_cancel_empty_selection(self):
        resp = self.client.post(
            reverse("propraetor:requisitions_bulk_cancel"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.req1.refresh_from_db()
        self.assertEqual(self.req1.status, "pending")

    def test_bulk_cancel_requires_post(self):
        resp = self.client.get(reverse("propraetor:requisitions_bulk_cancel"))
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Bulk fulfill – Requisitions
# ======================================================================


class RequisitionsBulkFulfillTests(BulkTestBase):
    def setUp(self):
        super().setUp()
        self.req_with_items = Requisition.objects.create(
            requisition_number="BF-REQ-1",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=timezone.now().date(),
            status="pending",
        )
        self.asset_for_item = Asset.objects.create(
            company=self.company,
            asset_tag="BF-A1",
            asset_model=self.asset_model,
            status="active",
        )
        self.item = RequisitionItem.objects.create(
            requisition=self.req_with_items,
            item_type="asset",
            asset=self.asset_for_item,
        )

        self.req_no_items = Requisition.objects.create(
            requisition_number="BF-REQ-2",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=timezone.now().date(),
            status="pending",
        )

    def test_bulk_fulfill_with_items(self):
        resp = self.client.post(
            reverse("propraetor:requisitions_bulk_fulfill"),
            {"selected_ids": [self.req_with_items.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.req_with_items.refresh_from_db()
        self.assertEqual(self.req_with_items.status, "fulfilled")
        self.assertIsNotNone(self.req_with_items.fulfilled_date)

    def test_bulk_fulfill_without_items_does_not_fulfill(self):
        """Requisitions without items should NOT be fulfilled."""
        resp = self.client.post(
            reverse("propraetor:requisitions_bulk_fulfill"),
            {"selected_ids": [self.req_no_items.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.req_no_items.refresh_from_db()
        # Should remain pending since it has no items
        self.assertEqual(self.req_no_items.status, "pending")

    def test_bulk_fulfill_mixed_with_and_without_items(self):
        resp = self.client.post(
            reverse("propraetor:requisitions_bulk_fulfill"),
            {"selected_ids": [self.req_with_items.pk, self.req_no_items.pk]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.req_with_items.refresh_from_db()
        self.req_no_items.refresh_from_db()
        self.assertEqual(self.req_with_items.status, "fulfilled")
        self.assertEqual(self.req_no_items.status, "pending")

    def test_bulk_fulfill_empty_selection(self):
        resp = self.client.post(
            reverse("propraetor:requisitions_bulk_fulfill"),
            {"selected_ids": []},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.req_with_items.refresh_from_db()
        self.assertEqual(self.req_with_items.status, "pending")

    def test_bulk_fulfill_requires_post(self):
        resp = self.client.get(reverse("propraetor:requisitions_bulk_fulfill"))
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Cross-cutting: authentication required for bulk endpoints
# ======================================================================


class BulkOperationsRequireAuthTests(TestCase):
    """All bulk operations should require authentication."""

    BULK_ENDPOINTS = [
        ("propraetor:assets_bulk_delete", {}),
        ("propraetor:assets_bulk_status", {}),
        ("propraetor:assets_bulk_unassign", {}),
        ("propraetor:companies_bulk_delete", {}),
        ("propraetor:locations_bulk_delete", {}),
        ("propraetor:categories_bulk_delete", {}),
        ("propraetor:vendors_bulk_delete", {}),
        ("propraetor:departments_bulk_delete", {}),
        ("propraetor:component_types_bulk_delete", {}),
        ("propraetor:components_bulk_delete", {}),
        ("propraetor:components_bulk_unassign", {}),
        ("propraetor:users_bulk_deactivate", {}),
        ("propraetor:users_bulk_delete", {}),
        ("propraetor:spare_parts_bulk_delete", {}),
        ("propraetor:maintenance_bulk_delete", {}),
        ("propraetor:invoices_bulk_delete", {}),
        ("propraetor:invoices_bulk_mark_paid", {}),
        ("propraetor:requisitions_bulk_delete", {}),
        ("propraetor:requisitions_bulk_cancel", {}),
        ("propraetor:requisitions_bulk_fulfill", {}),
        ("propraetor:asset_models_bulk_delete", {}),
    ]

    def setUp(self):
        self.client = Client()

    def test_all_bulk_endpoints_redirect_when_unauthenticated(self):
        for url_name, kwargs in self.BULK_ENDPOINTS:
            with self.subTest(endpoint=url_name):
                url = reverse(url_name, kwargs=kwargs)
                resp = self.client.post(url, {"selected_ids": []}, follow=False)
                self.assertEqual(
                    resp.status_code,
                    302,
                    f"{url_name} should redirect to login, got {resp.status_code}",
                )
                self.assertIn("/login/", resp.url)


# ======================================================================
# Bulk operations – partial valid IDs
# ======================================================================


class BulkDeletePartialIDsTests(BulkTestBase):
    """Test that bulk delete works when some IDs are valid and some are not."""

    def test_bulk_delete_with_mix_of_valid_and_invalid_ids(self):
        loc = Location.objects.create(name="Valid Loc")
        resp = self.client.post(
            reverse("propraetor:locations_bulk_delete"),
            {"selected_ids": [loc.pk, 99999]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        # Valid one should be deleted
        self.assertFalse(Location.objects.filter(pk=loc.pk).exists())

    def test_bulk_delete_with_string_ids(self):
        """IDs submitted as strings (from form checkboxes) should still work."""
        loc = Location.objects.create(name="String ID Loc")
        resp = self.client.post(
            reverse("propraetor:locations_bulk_delete"),
            {"selected_ids": [str(loc.pk)]},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Location.objects.filter(pk=loc.pk).exists())

    def test_bulk_status_with_string_ids(self):
        asset = Asset.objects.create(
            company=self.company,
            asset_tag="STR-ID",
            asset_model=self.asset_model,
            status="active",
        )
        resp = self.client.post(
            reverse("propraetor:assets_bulk_status"),
            {"selected_ids": [str(asset.pk)], "status": "retired"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        asset.refresh_from_db()
        self.assertEqual(asset.status, "retired")
