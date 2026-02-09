"""
Tests for view CRUD operations (create, read/detail, update/edit, delete).

Covers list, create, edit, detail, and delete views for:
- Locations
- Companies
- Categories
- Vendors
- Departments
- Assets
- Employees (Users)
- Component Types
"""

from django.contrib.auth.models import User as DjangoUser
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from propraetor.models import (
    Asset,
    AssetModel,
    Category,
    Company,
    Component,
    ComponentType,
    Department,
    Employee,
    Location,
    Vendor,
)

# Use simple static file storage during tests to avoid manifest errors
SIMPLE_STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# ======================================================================
# Shared setUp mixin
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class ViewTestBase(TestCase):
    """Shared setUp that creates a logged-in client and basic lookup data."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company = Company.objects.create(name="TestCo", code="TC")
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


# ======================================================================
# Location CRUD
# ======================================================================


class LocationCRUDTests(ViewTestBase):
    # -- List --
    def test_locations_list_returns_200(self):
        resp = self.client.get(reverse("propraetor:locations_list"))
        self.assertEqual(resp.status_code, 200)

    def test_locations_list_contains_location(self):
        resp = self.client.get(reverse("propraetor:locations_list"))
        self.assertContains(resp, "HQ")

    # -- Create GET --
    def test_location_create_get_returns_200(self):
        resp = self.client.get(reverse("propraetor:location_create"))
        self.assertEqual(resp.status_code, 200)

    # -- Create POST --
    def test_location_create_post_valid(self):
        resp = self.client.post(
            reverse("propraetor:location_create"),
            {"name": "Branch Office", "city": "Chittagong"},
        )
        # Should redirect on success (302 or HTMX redirect)
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(Location.objects.filter(name="Branch Office").exists())

    def test_location_create_post_missing_name(self):
        """Name is required – form should re-render with errors."""
        resp = self.client.post(
            reverse("propraetor:location_create"),
            {"name": "", "city": "Chittagong"},
        )
        self.assertEqual(resp.status_code, 200)
        # Object should NOT be created
        self.assertFalse(
            Location.objects.filter(city="Chittagong")
            .exclude(pk=self.location.pk)
            .exists()
        )

    # -- Detail --
    def test_location_details_returns_200(self):
        resp = self.client.get(
            reverse("propraetor:location_details", kwargs={"location_id": self.location.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "HQ")

    def test_location_details_404_for_nonexistent(self):
        resp = self.client.get(
            reverse("propraetor:location_details", kwargs={"location_id": 99999})
        )
        self.assertEqual(resp.status_code, 404)

    # -- Edit GET --
    def test_location_edit_get_returns_200(self):
        resp = self.client.get(
            reverse("propraetor:location_edit", kwargs={"location_id": self.location.pk})
        )
        self.assertEqual(resp.status_code, 200)

    # -- Edit POST --
    def test_location_edit_post_valid(self):
        resp = self.client.post(
            reverse("propraetor:location_edit", kwargs={"location_id": self.location.pk}),
            {"name": "HQ Updated", "city": "Dhaka"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "HQ Updated")

    # -- Delete --
    def test_location_delete(self):
        resp = self.client.delete(
            reverse("propraetor:location_delete", kwargs={"location_id": self.location.pk})
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Location.objects.filter(pk=self.location.pk).exists())

    def test_location_delete_404_for_nonexistent(self):
        resp = self.client.delete(
            reverse("propraetor:location_delete", kwargs={"location_id": 99999})
        )
        self.assertEqual(resp.status_code, 404)

    def test_location_delete_rejects_get(self):
        """Delete endpoint requires DELETE method."""
        resp = self.client.get(
            reverse("propraetor:location_delete", kwargs={"location_id": self.location.pk})
        )
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Company CRUD
# ======================================================================


class CompanyCRUDTests(ViewTestBase):
    def test_companies_list_returns_200(self):
        resp = self.client.get(reverse("propraetor:companies_list"))
        self.assertEqual(resp.status_code, 200)

    def test_companies_list_contains_company(self):
        resp = self.client.get(reverse("propraetor:companies_list"))
        self.assertContains(resp, "TestCo")

    def test_company_create_get(self):
        resp = self.client.get(reverse("propraetor:company_create"))
        self.assertEqual(resp.status_code, 200)

    def test_company_create_post_valid(self):
        resp = self.client.post(
            reverse("propraetor:company_create"),
            {"name": "NewCo", "code": "NC", "is_active": True},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(Company.objects.filter(name="NewCo").exists())

    def test_company_create_post_duplicate_name(self):
        """Company name is unique – form should fail."""
        resp = self.client.post(
            reverse("propraetor:company_create"),
            {"name": "TestCo", "code": "XX", "is_active": True},
        )
        self.assertEqual(resp.status_code, 200)  # form re-rendered with errors
        self.assertEqual(Company.objects.filter(name="TestCo").count(), 1)

    def test_company_details_returns_200(self):
        resp = self.client.get(
            reverse(
                "propraetor:company_details",
                kwargs={"company_id": self.company.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "TestCo")

    def test_company_edit_get(self):
        resp = self.client.get(
            reverse(
                "propraetor:company_edit",
                kwargs={"company_id": self.company.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_company_edit_post_valid(self):
        resp = self.client.post(
            reverse(
                "propraetor:company_edit",
                kwargs={"company_id": self.company.pk},
            ),
            {"name": "TestCo Renamed", "code": "TC", "is_active": True},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "TestCo Renamed")

    def test_company_delete(self):
        # Create a standalone company with no FK dependencies
        co = Company.objects.create(name="DeleteMe", code="DM")
        resp = self.client.delete(
            reverse("propraetor:company_delete", kwargs={"company_id": co.pk})
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Company.objects.filter(pk=co.pk).exists())

    def test_company_delete_rejects_get(self):
        resp = self.client.get(
            reverse(
                "propraetor:company_delete",
                kwargs={"company_id": self.company.pk},
            )
        )
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Category CRUD
# ======================================================================


class CategoryCRUDTests(ViewTestBase):
    def test_categories_list_returns_200(self):
        resp = self.client.get(reverse("propraetor:categories_list"))
        self.assertEqual(resp.status_code, 200)

    def test_category_create_get(self):
        resp = self.client.get(reverse("propraetor:category_create"))
        self.assertEqual(resp.status_code, 200)

    def test_category_create_post_valid(self):
        resp = self.client.post(
            reverse("propraetor:category_create"),
            {"name": "Desktop", "description": "Desktop PCs"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(Category.objects.filter(name="Desktop").exists())

    def test_category_create_post_empty_name(self):
        resp = self.client.post(
            reverse("propraetor:category_create"),
            {"name": ""},
        )
        self.assertEqual(resp.status_code, 200)
        # Only the original category should exist
        self.assertEqual(Category.objects.count(), 1)

    def test_category_details(self):
        resp = self.client.get(
            reverse(
                "propraetor:category_details",
                kwargs={"category_id": self.category.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Laptop")

    def test_category_edit_get(self):
        resp = self.client.get(
            reverse(
                "propraetor:category_edit",
                kwargs={"category_id": self.category.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_category_edit_post(self):
        resp = self.client.post(
            reverse(
                "propraetor:category_edit",
                kwargs={"category_id": self.category.pk},
            ),
            {"name": "Notebook"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Notebook")

    def test_category_delete(self):
        # Use a standalone category without FK references via PROTECT
        cat = Category.objects.create(name="Temporary")
        resp = self.client.delete(
            reverse("propraetor:category_delete", kwargs={"category_id": cat.pk})
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())


# ======================================================================
# Vendor CRUD
# ======================================================================


class VendorCRUDTests(ViewTestBase):
    def test_vendors_list_returns_200(self):
        resp = self.client.get(reverse("propraetor:vendors_list"))
        self.assertEqual(resp.status_code, 200)

    def test_vendor_create_get(self):
        resp = self.client.get(reverse("propraetor:vendor_create"))
        self.assertEqual(resp.status_code, 200)

    def test_vendor_create_post_valid(self):
        resp = self.client.post(
            reverse("propraetor:vendor_create"),
            {"vendor_name": "NewVendor"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(Vendor.objects.filter(vendor_name="NewVendor").exists())

    def test_vendor_create_post_empty_name(self):
        resp = self.client.post(
            reverse("propraetor:vendor_create"),
            {"vendor_name": ""},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Vendor.objects.count(), 1)

    def test_vendor_details(self):
        resp = self.client.get(
            reverse(
                "propraetor:vendor_details",
                kwargs={"vendor_id": self.vendor.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "WidgetVendor")

    def test_vendor_edit_get(self):
        resp = self.client.get(
            reverse(
                "propraetor:vendor_edit",
                kwargs={"vendor_id": self.vendor.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_vendor_edit_post(self):
        resp = self.client.post(
            reverse(
                "propraetor:vendor_edit",
                kwargs={"vendor_id": self.vendor.pk},
            ),
            {"vendor_name": "Renamed Vendor"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.vendor_name, "Renamed Vendor")

    def test_vendor_delete(self):
        v = Vendor.objects.create(vendor_name="DeleteVendor")
        resp = self.client.delete(
            reverse("propraetor:vendor_delete", kwargs={"vendor_id": v.pk})
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Vendor.objects.filter(pk=v.pk).exists())

    def test_vendor_delete_rejects_post(self):
        """Delete requires DELETE method, not POST."""
        resp = self.client.post(
            reverse(
                "propraetor:vendor_delete",
                kwargs={"vendor_id": self.vendor.pk},
            ),
        )
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# Department CRUD
# ======================================================================


class DepartmentCRUDTests(ViewTestBase):
    def test_departments_list_returns_200(self):
        resp = self.client.get(reverse("propraetor:departments_list"))
        self.assertEqual(resp.status_code, 200)

    def test_department_create_get(self):
        resp = self.client.get(reverse("propraetor:department_create"))
        self.assertEqual(resp.status_code, 200)

    def test_department_create_post_valid(self):
        resp = self.client.post(
            reverse("propraetor:department_create"),
            {"company": self.company.pk, "name": "Sales"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(
            Department.objects.filter(company=self.company, name="Sales").exists()
        )

    def test_department_create_post_missing_company(self):
        """Company is required for department."""
        resp = self.client.post(
            reverse("propraetor:department_create"),
            {"name": "Orphan Dept"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Department.objects.filter(name="Orphan Dept").exists())

    def test_department_create_post_missing_name(self):
        resp = self.client.post(
            reverse("propraetor:department_create"),
            {"company": self.company.pk, "name": ""},
        )
        self.assertEqual(resp.status_code, 200)
        # Only the original department exists
        self.assertEqual(Department.objects.filter(company=self.company).count(), 1)

    def test_department_details(self):
        resp = self.client.get(
            reverse(
                "propraetor:department_details",
                kwargs={"department_id": self.department.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_department_edit_get(self):
        resp = self.client.get(
            reverse(
                "propraetor:department_edit",
                kwargs={"department_id": self.department.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_department_edit_post(self):
        resp = self.client.post(
            reverse(
                "propraetor:department_edit",
                kwargs={"department_id": self.department.pk},
            ),
            {"company": self.company.pk, "name": "Eng Renamed"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.department.refresh_from_db()
        self.assertEqual(self.department.name, "Eng Renamed")

    def test_department_delete(self):
        # Create a standalone department that has no FK dependents
        dept = Department.objects.create(company=self.company, name="Temp Dept")
        resp = self.client.delete(
            reverse(
                "propraetor:department_delete",
                kwargs={"department_id": dept.pk},
            )
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Department.objects.filter(pk=dept.pk).exists())


# ======================================================================
# Component Type CRUD
# ======================================================================


class ComponentTypeCRUDTests(ViewTestBase):
    def test_component_types_list_returns_200(self):
        resp = self.client.get(reverse("propraetor:component_types_list"))
        self.assertEqual(resp.status_code, 200)

    def test_component_type_create_get(self):
        resp = self.client.get(reverse("propraetor:component_type_create"))
        self.assertEqual(resp.status_code, 200)

    def test_component_type_create_post_valid(self):
        resp = self.client.post(
            reverse("propraetor:component_type_create"),
            {"type_name": "SSD"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(ComponentType.objects.filter(type_name="SSD").exists())

    def test_component_type_create_post_duplicate(self):
        """type_name is unique."""
        resp = self.client.post(
            reverse("propraetor:component_type_create"),
            {"type_name": "RAM"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ComponentType.objects.filter(type_name="RAM").count(), 1)

    def test_component_type_details(self):
        resp = self.client.get(
            reverse(
                "propraetor:component_type_details",
                kwargs={"component_type_id": self.component_type.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_component_type_edit_post(self):
        resp = self.client.post(
            reverse(
                "propraetor:component_type_edit",
                kwargs={"component_type_id": self.component_type.pk},
            ),
            {"type_name": "DDR5 RAM"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.component_type.refresh_from_db()
        self.assertEqual(self.component_type.type_name, "DDR5 RAM")

    def test_component_type_delete(self):
        ct = ComponentType.objects.create(type_name="Temp Type")
        resp = self.client.delete(
            reverse(
                "propraetor:component_type_delete",
                kwargs={"component_type_id": ct.pk},
            )
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(ComponentType.objects.filter(pk=ct.pk).exists())


# ======================================================================
# Employee/User CRUD
# ======================================================================


class EmployeeCRUDTests(ViewTestBase):
    def test_users_list_returns_200(self):
        resp = self.client.get(reverse("propraetor:users_list"))
        self.assertEqual(resp.status_code, 200)

    def test_user_create_get(self):
        resp = self.client.get(reverse("propraetor:user_create"))
        self.assertEqual(resp.status_code, 200)

    def test_user_create_post_valid(self):
        resp = self.client.post(
            reverse("propraetor:user_create"),
            {
                "name": "New Employee",
                "employee_id": "EMP-NEW",
                "status": "active",
            },
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(Employee.objects.filter(name="New Employee").exists())

    def test_user_create_post_missing_name(self):
        resp = self.client.post(
            reverse("propraetor:user_create"),
            {"name": "", "status": "active"},
        )
        self.assertEqual(resp.status_code, 200)
        # Only the original employee exists
        self.assertEqual(Employee.objects.count(), 1)

    def test_user_details(self):
        resp = self.client.get(
            reverse(
                "propraetor:user_details",
                kwargs={"user_id": self.employee.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Jane Doe")

    def test_user_edit_get(self):
        resp = self.client.get(
            reverse(
                "propraetor:user_edit",
                kwargs={"user_id": self.employee.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_user_edit_post(self):
        resp = self.client.post(
            reverse(
                "propraetor:user_edit",
                kwargs={"user_id": self.employee.pk},
            ),
            {
                "name": "Jane Updated",
                "employee_id": "EMP-001",
                "status": "active",
            },
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.name, "Jane Updated")

    def test_user_delete(self):
        emp = Employee.objects.create(name="ToDelete", status="active")
        resp = self.client.delete(
            reverse("propraetor:user_delete", kwargs={"user_id": emp.pk})
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Employee.objects.filter(pk=emp.pk).exists())

    def test_user_activate(self):
        self.employee.status = "inactive"
        self.employee.save()
        resp = self.client.post(
            reverse("propraetor:user_activate", kwargs={"user_id": self.employee.pk})
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, "active")

    def test_user_deactivate(self):
        resp = self.client.post(
            reverse(
                "propraetor:user_deactivate",
                kwargs={"user_id": self.employee.pk},
            )
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, "inactive")


# ======================================================================
# Asset CRUD
# ======================================================================


class AssetCRUDTests(ViewTestBase):
    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            company=self.company,
            asset_tag="ASSET-001",
            asset_model=self.asset_model,
            status="active",
        )

    def test_assets_list_returns_200(self):
        resp = self.client.get(reverse("propraetor:assets_list"))
        self.assertEqual(resp.status_code, 200)

    def test_asset_create_get(self):
        resp = self.client.get(reverse("propraetor:asset_create"))
        self.assertEqual(resp.status_code, 200)

    def test_asset_create_post_valid(self):
        resp = self.client.post(
            reverse("propraetor:asset_create"),
            {
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "ASSET-NEW",
                "status": "pending",
            },
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(Asset.objects.filter(asset_tag="ASSET-NEW").exists())

    def test_asset_create_post_auto_tag(self):
        """Asset tag is auto-generated when left blank."""
        resp = self.client.post(
            reverse("propraetor:asset_create"),
            {
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "",
                "status": "pending",
            },
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        # A new asset should have been created with an auto-generated tag
        new_assets = Asset.objects.exclude(pk=self.asset.pk)
        self.assertEqual(new_assets.count(), 1)
        self.assertTrue(len(new_assets.first().asset_tag) > 0)

    def test_asset_create_post_missing_model(self):
        """asset_model is required."""
        resp = self.client.post(
            reverse("propraetor:asset_create"),
            {"asset_tag": "FAIL-001", "status": "pending"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Asset.objects.filter(asset_tag="FAIL-001").exists())

    def test_asset_details(self):
        resp = self.client.get(
            reverse(
                "propraetor:asset_details",
                kwargs={"asset_id": self.asset.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ASSET-001")

    def test_asset_details_by_tag(self):
        """The /ht/<asset_tag>/ route also works."""
        resp = self.client.get(
            reverse(
                "propraetor:asset_details_ht",
                kwargs={"asset_tag": "ASSET-001"},
            )
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ASSET-001")

    def test_asset_details_ht_404_bad_tag(self):
        resp = self.client.get(
            reverse(
                "propraetor:asset_details_ht",
                kwargs={"asset_tag": "NONEXISTENT"},
            )
        )
        self.assertEqual(resp.status_code, 404)

    def test_asset_edit_get(self):
        resp = self.client.get(
            reverse(
                "propraetor:asset_edit",
                kwargs={"asset_id": self.asset.pk},
            )
        )
        self.assertEqual(resp.status_code, 200)

    def test_asset_edit_post(self):
        resp = self.client.post(
            reverse(
                "propraetor:asset_edit",
                kwargs={"asset_id": self.asset.pk},
            ),
            {
                "company": self.company.pk,
                "asset_model": self.asset_model.pk,
                "asset_tag": "ASSET-001",
                "status": "in_repair",
            },
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, "in_repair")

    def test_asset_delete(self):
        resp = self.client.delete(
            reverse(
                "propraetor:asset_delete",
                kwargs={"asset_id": self.asset.pk},
            )
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(Asset.objects.filter(pk=self.asset.pk).exists())

    def test_asset_change_status(self):
        resp = self.client.post(
            reverse(
                "propraetor:asset_change_status",
                kwargs={"asset_id": self.asset.pk},
            ),
            {"status": "retired"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, "retired")

    def test_asset_change_status_invalid(self):
        resp = self.client.post(
            reverse(
                "propraetor:asset_change_status",
                kwargs={"asset_id": self.asset.pk},
            ),
            {"status": "bogus"},
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, "active")  # unchanged

    def test_asset_unassign(self):
        self.asset.assigned_to = self.employee
        self.asset.location = None
        self.asset.save()
        resp = self.client.post(
            reverse(
                "propraetor:asset_unassign",
                kwargs={"asset_id": self.asset.pk},
            )
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.assigned_to)

    def test_asset_unassign_when_not_assigned(self):
        """Unassigning an unassigned asset should just return info message."""
        resp = self.client.post(
            reverse(
                "propraetor:asset_unassign",
                kwargs={"asset_id": self.asset.pk},
            )
        )
        self.assertIn(resp.status_code, [200, 301, 302])

    def test_asset_duplicate(self):
        resp = self.client.post(
            reverse(
                "propraetor:asset_duplicate",
                kwargs={"asset_id": self.asset.pk},
            )
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        # There should now be 2 assets
        self.assertEqual(Asset.objects.count(), 2)
        dup = Asset.objects.exclude(pk=self.asset.pk).first()
        self.assertIn("COPY", dup.asset_tag)
        self.assertEqual(dup.status, "pending")
        self.assertIsNone(dup.assigned_to)
