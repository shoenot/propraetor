"""
Tests for the search API (`api_search`) and the modal inline-create endpoint.

Covers:
- api_search: valid queries, empty queries, unknown models, limit capping,
  default filters, allowed/disallowed client-supplied filters, ordering
- modal_create: GET returns form, POST creates object, POST with invalid
  data returns errors, unknown model_key returns 400
"""

import json

from django.contrib.auth.models import User as DjangoUser
from django.test import Client, TestCase
from django.urls import reverse

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


class ApiSearchTestBase(TestCase):
    """Shared setUp for search API tests."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company_a = Company.objects.create(
            name="Alpha Corp", code="AC", is_active=True
        )
        self.company_b = Company.objects.create(
            name="Beta Inc", code="BI", is_active=True
        )
        self.company_inactive = Company.objects.create(
            name="Inactive Co", code="IC", is_active=False
        )

        self.location1 = Location.objects.create(name="Main Office", city="Dhaka")
        self.location2 = Location.objects.create(
            name="Branch Office", city="Chittagong"
        )

        self.department = Department.objects.create(
            company=self.company_a, name="Engineering"
        )

        self.category = Category.objects.create(name="Laptop")
        self.asset_model = AssetModel.objects.create(
            category=self.category,
            manufacturer="Dell",
            model_name="Latitude 5540",
        )
        self.component_type = ComponentType.objects.create(type_name="RAM Module")

        self.vendor = Vendor.objects.create(
            vendor_name="WidgetSupplier", contact_person="John"
        )

        self.employee_active = Employee.objects.create(
            name="Jane Doe",
            employee_id="EMP-001",
            company=self.company_a,
            department=self.department,
            status="active",
        )
        self.employee_inactive = Employee.objects.create(
            name="John Gone",
            employee_id="EMP-002",
            company=self.company_b,
            status="inactive",
        )

        self.asset1 = Asset.objects.create(
            company=self.company_a,
            asset_tag="ASSET-001",
            asset_model=self.asset_model,
            status="active",
        )
        self.asset2 = Asset.objects.create(
            company=self.company_b,
            asset_tag="ASSET-002",
            asset_model=self.asset_model,
            status="active",
        )

        self.component1 = Component.objects.create(
            component_type=self.component_type,
            manufacturer="Kingston",
            status="spare",
        )

    def _search(self, **params):
        """Helper: GET the search endpoint and return parsed JSON."""
        resp = self.client.get(reverse("propraetor:api_search"), params)
        self.assertEqual(resp.status_code, 200)
        return json.loads(resp.content)


# ======================================================================
# api_search – basic behaviour
# ======================================================================


class ApiSearchBasicTests(ApiSearchTestBase):
    def test_empty_model_param_returns_empty(self):
        data = self._search(model="", q="test")
        self.assertEqual(data["results"], [])
        self.assertEqual(data["total"], 0)

    def test_unknown_model_returns_empty(self):
        data = self._search(model="nonexistent", q="test")
        self.assertEqual(data["results"], [])
        self.assertEqual(data["total"], 0)

    def test_empty_query_returns_empty(self):
        data = self._search(model="company", q="")
        self.assertEqual(data["results"], [])
        self.assertEqual(data["total"], 0)

    def test_whitespace_only_query_returns_empty(self):
        data = self._search(model="company", q="   ")
        self.assertEqual(data["results"], [])
        self.assertEqual(data["total"], 0)

    def test_no_query_param_returns_empty(self):
        data = self._search(model="company")
        self.assertEqual(data["results"], [])

    def test_search_returns_matching_results(self):
        data = self._search(model="company", q="Alpha")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["text"], "Alpha Corp")

    def test_search_is_case_insensitive(self):
        data = self._search(model="company", q="alpha")
        self.assertEqual(data["total"], 1)

    def test_search_partial_match(self):
        """icontains should match partial strings."""
        data = self._search(model="company", q="lph")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["text"], "Alpha Corp")

    def test_result_structure(self):
        data = self._search(model="location", q="Main")
        self.assertEqual(data["total"], 1)
        result = data["results"][0]
        self.assertIn("id", result)
        self.assertIn("text", result)
        self.assertEqual(result["id"], self.location1.pk)

    def test_search_returns_limit_in_response(self):
        data = self._search(model="location", q="Office")
        self.assertIn("limit", data)


# ======================================================================
# api_search – default filters
# ======================================================================


class ApiSearchDefaultFilterTests(ApiSearchTestBase):
    def test_company_search_excludes_inactive_by_default(self):
        """SEARCH_CONFIGS for company has default_filters={'is_active': True}."""
        data = self._search(model="company", q="Inactive")
        self.assertEqual(data["total"], 0)

    def test_company_search_includes_active(self):
        data = self._search(model="company", q="Alpha")
        self.assertEqual(data["total"], 1)

    def test_employee_search_excludes_inactive_by_default(self):
        """SEARCH_CONFIGS for employee has default_filters={'status': 'active'}."""
        data = self._search(model="employee", q="John Gone")
        self.assertEqual(data["total"], 0)

    def test_employee_search_includes_active(self):
        data = self._search(model="employee", q="Jane")
        self.assertEqual(data["total"], 1)


# ======================================================================
# api_search – multiple search fields
# ======================================================================


class ApiSearchMultiFieldTests(ApiSearchTestBase):
    def test_company_search_by_code(self):
        """Company search_fields include 'code'."""
        data = self._search(model="company", q="AC")
        ids = {r["id"] for r in data["results"]}
        self.assertIn(self.company_a.pk, ids)

    def test_location_search_by_city(self):
        """Location search_fields include 'city'."""
        data = self._search(model="location", q="Chittagong")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["id"], self.location2.pk)

    def test_vendor_search_by_contact_person(self):
        data = self._search(model="vendor", q="John")
        self.assertEqual(data["total"], 1)

    def test_employee_search_by_employee_id(self):
        data = self._search(model="employee", q="EMP-001")
        self.assertEqual(data["total"], 1)

    def test_asset_search_by_tag(self):
        data = self._search(model="asset", q="ASSET-001")
        self.assertEqual(data["total"], 1)

    def test_component_type_search_by_type_name(self):
        data = self._search(model="component_type", q="RAM")
        self.assertEqual(data["total"], 1)

    def test_department_search_by_name(self):
        data = self._search(model="department", q="Engineering")
        self.assertEqual(data["total"], 1)

    def test_category_search_by_name(self):
        data = self._search(model="category", q="Laptop")
        self.assertEqual(data["total"], 1)

    def test_asset_model_search_by_manufacturer(self):
        data = self._search(model="asset_model", q="Dell")
        self.assertEqual(data["total"], 1)

    def test_asset_model_search_by_model_name(self):
        data = self._search(model="asset_model", q="Latitude")
        self.assertEqual(data["total"], 1)


# ======================================================================
# api_search – limit parameter
# ======================================================================


class ApiSearchLimitTests(ApiSearchTestBase):
    def test_default_limit(self):
        """Default limit should be 20."""
        data = self._search(model="location", q="Office")
        self.assertEqual(data["limit"], 20)

    def test_custom_limit(self):
        data = self._search(model="location", q="Office", limit="1")
        self.assertEqual(data["limit"], 1)
        self.assertEqual(len(data["results"]), 1)
        # total reflects the full count, not the limit
        self.assertEqual(data["total"], 2)

    def test_limit_capped_at_50(self):
        data = self._search(model="location", q="Office", limit="100")
        self.assertEqual(data["limit"], 50)

    def test_invalid_limit_defaults_to_20(self):
        data = self._search(model="location", q="Office", limit="abc")
        self.assertEqual(data["limit"], 20)

    def test_negative_limit_treated_as_valid_min(self):
        """Negative limit is clamped to 1 by max(1, min(..., 50))."""
        data = self._search(model="location", q="Office", limit="-5")
        # max(1, min(-5, 50)) == 1
        self.assertEqual(data["limit"], 1)


# ======================================================================
# api_search – allowed_filters (client-supplied filters)
# ======================================================================


class ApiSearchClientFilterTests(ApiSearchTestBase):
    def test_asset_filter_by_company(self):
        """Asset SEARCH_CONFIGS has allowed_filters=['company']."""
        data = self._search(
            model="asset",
            q="ASSET",
            **{f"filter_company": str(self.company_a.pk)},
        )
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["id"], self.asset1.pk)

    def test_asset_filter_by_company_other(self):
        data = self._search(
            model="asset",
            q="ASSET",
            **{f"filter_company": str(self.company_b.pk)},
        )
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["id"], self.asset2.pk)

    def test_disallowed_filter_is_ignored(self):
        """Filters not in allowed_filters should be silently ignored."""
        data = self._search(
            model="asset",
            q="ASSET",
            **{f"filter_status": "active"},
        )
        # Should return all assets (filter_status not in allowed_filters for asset)
        self.assertEqual(data["total"], 2)

    def test_company_has_no_allowed_filters(self):
        """Company SEARCH_CONFIGS doesn't define allowed_filters."""
        data = self._search(
            model="company",
            q="Corp",
            **{f"filter_is_active": "True"},
        )
        # Filter should be ignored, only default_filters apply
        self.assertEqual(data["total"], 1)

    def test_empty_filter_value_ignored(self):
        """An empty filter value should not be applied."""
        data = self._search(
            model="asset",
            q="ASSET",
            **{f"filter_company": ""},
        )
        self.assertEqual(data["total"], 2)


# ======================================================================
# api_search – ordering
# ======================================================================


class ApiSearchOrderingTests(ApiSearchTestBase):
    def test_location_results_ordered_by_name(self):
        """Location order_by is ['name']."""
        data = self._search(model="location", q="Office")
        names = [r["text"] for r in data["results"]]
        self.assertEqual(names, ["Branch Office", "Main Office"])

    def test_company_results_ordered_by_name(self):
        data = self._search(model="company", q="Corp")
        # Only active companies matching 'Corp' — just Alpha Corp
        self.assertEqual(data["total"], 1)


# ======================================================================
# api_search – HTTP method restrictions
# ======================================================================


class ApiSearchMethodTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

    def test_post_not_allowed(self):
        resp = self.client.post(
            reverse("propraetor:api_search"), {"model": "company", "q": "test"}
        )
        self.assertEqual(resp.status_code, 405)

    def test_get_allowed(self):
        resp = self.client.get(
            reverse("propraetor:api_search"), {"model": "company", "q": "test"}
        )
        self.assertEqual(resp.status_code, 200)


# ======================================================================
# modal_create – GET (display form)
# ======================================================================


class ModalCreateGetTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

    def test_get_company_form(self):
        resp = self.client.get(
            reverse("propraetor:modal_create", kwargs={"model_key": "company"})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "modal")  # form uses prefix="modal"

    def test_get_location_form(self):
        resp = self.client.get(
            reverse("propraetor:modal_create", kwargs={"model_key": "location"})
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_category_form(self):
        resp = self.client.get(
            reverse("propraetor:modal_create", kwargs={"model_key": "category"})
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_vendor_form(self):
        resp = self.client.get(
            reverse("propraetor:modal_create", kwargs={"model_key": "vendor"})
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_department_form(self):
        resp = self.client.get(
            reverse("propraetor:modal_create", kwargs={"model_key": "department"})
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_component_type_form(self):
        resp = self.client.get(
            reverse("propraetor:modal_create", kwargs={"model_key": "component_type"})
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_employee_form(self):
        resp = self.client.get(
            reverse("propraetor:modal_create", kwargs={"model_key": "employee"})
        )
        self.assertEqual(resp.status_code, 200)

    def test_unknown_model_key_returns_400(self):
        resp = self.client.get(
            reverse("propraetor:modal_create", kwargs={"model_key": "nonexistent"})
        )
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertEqual(data["error"], "Unknown model")


# ======================================================================
# modal_create – POST (create objects)
# ======================================================================


class ModalCreatePostTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

    def test_create_company_success(self):
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "company"}),
            {"modal-name": "NewCo", "modal-is_active": True},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["text"], "NewCo")
        self.assertTrue(Company.objects.filter(name="NewCo").exists())

    def test_create_location_success(self):
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "location"}),
            {"modal-name": "Warehouse"},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.assertTrue(Location.objects.filter(name="Warehouse").exists())

    def test_create_category_success(self):
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "category"}),
            {"modal-name": "Desktop"},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.assertTrue(Category.objects.filter(name="Desktop").exists())

    def test_create_vendor_success(self):
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "vendor"}),
            {"modal-vendor_name": "NewVendor"},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.assertTrue(Vendor.objects.filter(vendor_name="NewVendor").exists())

    def test_create_component_type_success(self):
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "component_type"}),
            {"modal-type_name": "GPU"},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.assertTrue(ComponentType.objects.filter(type_name="GPU").exists())

    def test_create_department_success(self):
        company = Company.objects.create(name="ParentCo", code="PC")
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "department"}),
            {"modal-company": company.pk, "modal-name": "HR"},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.assertTrue(Department.objects.filter(name="HR", company=company).exists())

    def test_create_returns_id_and_text(self):
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "category"}),
            {"modal-name": "Printer"},
        )
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.assertIn("id", data)
        self.assertIn("text", data)
        cat = Category.objects.get(name="Printer")
        self.assertEqual(data["id"], cat.pk)
        self.assertEqual(data["text"], "Printer")


# ======================================================================
# modal_create – POST with invalid data
# ======================================================================


class ModalCreatePostInvalidTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

    def test_create_company_missing_name(self):
        """Company name is required – should return form HTML (not JSON success)."""
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "company"}),
            {"modal-name": ""},
        )
        self.assertEqual(resp.status_code, 200)
        # Should NOT be a JSON success response
        content_type = resp.get("Content-Type", "")
        if "application/json" in content_type:
            data = json.loads(resp.content)
            self.assertFalse(data.get("success", False))
        else:
            # HTML form re-rendered with errors
            self.assertNotIn(b'"success": true', resp.content)
        self.assertEqual(Company.objects.count(), 0)

    def test_create_location_missing_name(self):
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "location"}),
            {"modal-name": ""},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Location.objects.count(), 0)

    def test_create_department_missing_company(self):
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "department"}),
            {"modal-name": "Orphan"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Department.objects.filter(name="Orphan").exists())

    def test_create_component_type_duplicate(self):
        """type_name is unique – second create should fail."""
        ComponentType.objects.create(type_name="CPU")
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "component_type"}),
            {"modal-type_name": "CPU"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ComponentType.objects.filter(type_name="CPU").count(), 1)

    def test_unknown_model_key_post_returns_400(self):
        resp = self.client.post(
            reverse("propraetor:modal_create", kwargs={"model_key": "bogus"}),
            {"modal-name": "whatever"},
        )
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertEqual(data["error"], "Unknown model")


# ======================================================================
# api_search – multiple results / select_related
# ======================================================================


class ApiSearchSelectRelatedTests(ApiSearchTestBase):
    """Verify that select_related models are searchable through relations."""

    def test_asset_model_search_by_category_name(self):
        """asset_model search_fields includes 'category__name'."""
        data = self._search(model="asset_model", q="Laptop")
        self.assertEqual(data["total"], 1)

    def test_department_search_by_company_code(self):
        """department search_fields includes 'company__code'."""
        data = self._search(model="department", q="AC")
        self.assertEqual(data["total"], 1)

    def test_employee_search_by_department_name(self):
        """employee search_fields includes 'department__name'."""
        data = self._search(model="employee", q="Engineering")
        self.assertEqual(data["total"], 1)

    def test_component_search_by_type_name(self):
        """component search_fields includes 'component_type__type_name'."""
        data = self._search(model="component", q="RAM")
        self.assertEqual(data["total"], 1)


# ======================================================================
# api_search – all configured models respond without error
# ======================================================================


class ApiSearchAllModelsTests(ApiSearchTestBase):
    """Smoke test: every key in SEARCH_CONFIGS returns a valid response."""

    SEARCH_MODELS = [
        "company",
        "asset_model",
        "employee",
        "location",
        "requisition",
        "invoice",
        "category",
        "asset",
        "component_type",
        "department",
        "vendor",
        "component",
    ]

    def test_all_search_models_return_valid_json(self):
        for model_key in self.SEARCH_MODELS:
            with self.subTest(model=model_key):
                data = self._search(model=model_key, q="test")
                self.assertIn("results", data)
                self.assertIn("total", data)
                self.assertIsInstance(data["results"], list)


# ======================================================================
# modal_create – all configured models respond without error
# ======================================================================


class ModalCreateAllModelsTests(TestCase):
    """Smoke test: every key in MODAL_CREATE_CONFIGS returns a form on GET."""

    MODAL_MODELS = [
        "company",
        "asset_model",
        "employee",
        "location",
        "category",
        "department",
        "vendor",
        "component_type",
        "requisition",
        "invoice",
        "asset",
        "component",
    ]

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

    def test_all_modal_create_get_returns_200(self):
        for model_key in self.MODAL_MODELS:
            with self.subTest(model=model_key):
                resp = self.client.get(
                    reverse("propraetor:modal_create", kwargs={"model_key": model_key})
                )
                self.assertEqual(resp.status_code, 200)
