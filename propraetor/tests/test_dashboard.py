"""
Tests for the dashboard view.

Covers:
- Dashboard returns 200 for authenticated users
- Dashboard context contains all expected keys
- Dashboard works with an empty database (zero counts)
- Dashboard works with populated data (correct counts, breakdowns)
- Dashboard financial snapshot accuracy
- Dashboard warranty alerts
- Dashboard requisition summary
- Dashboard asset status breakdown
"""

from datetime import timedelta
from decimal import Decimal

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
    MaintenanceRecord,
    PurchaseInvoice,
    Requisition,
    SparePartsInventory,
    Vendor,
)

# Use simple static file storage during tests to avoid manifest errors
SIMPLE_STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# ======================================================================
# Dashboard – empty database
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardEmptyDatabaseTests(TestCase):
    """Dashboard should render without errors even when the DB is empty."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

    def test_dashboard_returns_200(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_context_has_expected_keys(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        expected_keys = [
            # Primary stats
            "active_users",
            "total_employees",
            "total_assets",
            "active_assets",
            "active_pct",
            "in_repair",
            "repair_pct",
            "pending_assets",
            "total_components",
            "installed_components",
            "spare_components",
            "failed_components",
            "total_locations",
            "total_departments",
            "total_vendors",
            "total_models",
            # Financial
            "unpaid_invoices",
            "unpaid_amount",
            "recently_paid_invoices",
            "recently_paid_amount",
            "total_invoices",
            "total_invoice_value",
            "total_asset_value",
            "total_maintenance_cost_30d",
            # Breakdowns
            "asset_status_breakdown",
            "assets_by_month",
            # Alerts
            "warranty_expiring",
            "warranty_expired_count",
            "low_stock_parts",
            # Requisitions
            "pending_requisitions_count",
            "fulfilled_requisitions_30d",
            "pending_requisitions",
            # Maintenance
            "recent_maintenance",
            # Departments
            "top_departments",
            # Activity
            "recent_activity",
            # Misc
            "today",
            "base_template",
        ]

        for key in expected_keys:
            self.assertIn(key, ctx, f"Dashboard context missing key: {key}")

    def test_empty_database_zero_counts(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        self.assertEqual(ctx["total_employees"], 0)
        self.assertEqual(ctx["active_users"], 0)
        self.assertEqual(ctx["total_assets"], 0)
        self.assertEqual(ctx["active_assets"], 0)
        self.assertEqual(ctx["active_pct"], 0)
        self.assertEqual(ctx["in_repair"], 0)
        self.assertEqual(ctx["repair_pct"], 0)
        self.assertEqual(ctx["pending_assets"], 0)
        self.assertEqual(ctx["total_components"], 0)
        self.assertEqual(ctx["installed_components"], 0)
        self.assertEqual(ctx["spare_components"], 0)
        self.assertEqual(ctx["failed_components"], 0)
        self.assertEqual(ctx["total_locations"], 0)
        self.assertEqual(ctx["total_departments"], 0)
        self.assertEqual(ctx["total_vendors"], 0)
        self.assertEqual(ctx["total_models"], 0)

    def test_empty_database_zero_financial(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        self.assertEqual(ctx["unpaid_invoices"], 0)
        self.assertEqual(ctx["unpaid_amount"], 0)
        self.assertEqual(ctx["recently_paid_invoices"], 0)
        self.assertEqual(ctx["recently_paid_amount"], 0)
        self.assertEqual(ctx["total_invoices"], 0)
        self.assertEqual(ctx["total_invoice_value"], 0)
        self.assertEqual(ctx["total_asset_value"], 0)
        self.assertEqual(ctx["total_maintenance_cost_30d"], 0)

    def test_empty_database_zero_requisitions(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        self.assertEqual(ctx["pending_requisitions_count"], 0)
        self.assertEqual(ctx["fulfilled_requisitions_30d"], 0)

    def test_empty_database_empty_querysets(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        self.assertEqual(len(ctx["warranty_expiring"]), 0)
        self.assertEqual(ctx["warranty_expired_count"], 0)
        self.assertEqual(len(ctx["low_stock_parts"]), 0)
        self.assertEqual(len(ctx["pending_requisitions"]), 0)
        self.assertEqual(len(ctx["recent_maintenance"]), 0)
        self.assertEqual(len(ctx["recent_activity"]), 0)

    def test_empty_database_asset_status_breakdown_all_zero(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        for item in ctx["asset_status_breakdown"]:
            self.assertEqual(
                item["value"], 0, f"Status '{item['label']}' should be 0 in empty DB"
            )

    def test_assets_by_month_has_six_entries(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertEqual(len(ctx["assets_by_month"]), 6)
        for entry in ctx["assets_by_month"]:
            self.assertIn("month", entry)
            self.assertIn("count", entry)
            self.assertEqual(entry["count"], 0)


# ======================================================================
# Dashboard – populated database
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardPopulatedTests(TestCase):
    """Dashboard with data should show correct counts and summaries."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        # Core entities
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

        # Employees
        self.emp_active = Employee.objects.create(
            name="Jane Doe",
            employee_id="EMP-001",
            company=self.company,
            department=self.department,
            status="active",
        )
        self.emp_inactive = Employee.objects.create(
            name="John Gone",
            employee_id="EMP-002",
            company=self.company,
            status="inactive",
        )

        # Assets with various statuses
        self.asset_active = Asset.objects.create(
            company=self.company,
            asset_tag="A-ACTIVE",
            asset_model=self.asset_model,
            status="active",
            purchase_cost=Decimal("1000.00"),
        )
        self.asset_pending = Asset.objects.create(
            company=self.company,
            asset_tag="A-PENDING",
            asset_model=self.asset_model,
            status="pending",
            purchase_cost=Decimal("500.00"),
        )
        self.asset_repair = Asset.objects.create(
            company=self.company,
            asset_tag="A-REPAIR",
            asset_model=self.asset_model,
            status="in_repair",
        )
        self.asset_retired = Asset.objects.create(
            company=self.company,
            asset_tag="A-RETIRED",
            asset_model=self.asset_model,
            status="retired",
        )

        # Components
        self.comp_installed = Component.objects.create(
            component_type=self.component_type,
            parent_asset=self.asset_active,
            manufacturer="Kingston",
            status="installed",
        )
        self.comp_spare = Component.objects.create(
            component_type=self.component_type,
            manufacturer="Corsair",
            status="spare",
        )
        self.comp_failed = Component.objects.create(
            component_type=self.component_type,
            manufacturer="Generic",
            status="failed",
        )

    def test_dashboard_returns_200(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_employee_counts(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        self.assertEqual(ctx["total_employees"], 2)
        self.assertEqual(ctx["active_users"], 1)

    def test_asset_counts(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        self.assertEqual(ctx["total_assets"], 4)
        self.assertEqual(ctx["active_assets"], 1)
        self.assertEqual(ctx["in_repair"], 1)
        self.assertEqual(ctx["pending_assets"], 1)

    def test_asset_percentages(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        # 1 active out of 4 = 25.0%
        self.assertAlmostEqual(ctx["active_pct"], 25.0, places=1)
        # 1 in_repair out of 4 = 25.0%
        self.assertAlmostEqual(ctx["repair_pct"], 25.0, places=1)

    def test_component_counts(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        self.assertEqual(ctx["total_components"], 3)
        self.assertEqual(ctx["installed_components"], 1)
        self.assertEqual(ctx["spare_components"], 1)
        self.assertEqual(ctx["failed_components"], 1)

    def test_entity_counts(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        self.assertEqual(ctx["total_locations"], 1)
        self.assertEqual(ctx["total_departments"], 1)
        self.assertEqual(ctx["total_vendors"], 1)
        self.assertEqual(ctx["total_models"], 1)

    def test_asset_status_breakdown_values(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        breakdown = {
            item["label"]: item["value"] for item in ctx["asset_status_breakdown"]
        }
        self.assertEqual(breakdown["Active"], 1)
        self.assertEqual(breakdown["Pending"], 1)
        self.assertEqual(breakdown["In Repair"], 1)
        self.assertEqual(breakdown["Retired"], 1)
        self.assertEqual(breakdown["Disposed"], 0)
        self.assertEqual(breakdown["Inactive"], 0)

    def test_asset_status_breakdown_has_css_classes(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        for item in ctx["asset_status_breakdown"]:
            self.assertIn("css_class", item)
            self.assertTrue(item["css_class"].startswith("status-"))

    def test_total_asset_value(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        # $1000 + $500 = $1500 (only assets with purchase_cost set)
        self.assertEqual(ctx["total_asset_value"], Decimal("1500.00"))


# ======================================================================
# Dashboard – financial snapshot
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardFinancialTests(TestCase):
    """Test the financial snapshot portion of the dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company = Company.objects.create(name="FinCo", code="FC")
        self.vendor = Vendor.objects.create(vendor_name="FinVendor")

        today = timezone.now().date()

        # Unpaid invoice
        self.inv_unpaid = PurchaseInvoice.objects.create(
            invoice_number="INV-UNPAID",
            company=self.company,
            vendor=self.vendor,
            invoice_date=today,
            total_amount=Decimal("5000.00"),
            payment_status="unpaid",
        )

        # Partially paid invoice
        self.inv_partial = PurchaseInvoice.objects.create(
            invoice_number="INV-PARTIAL",
            company=self.company,
            vendor=self.vendor,
            invoice_date=today,
            total_amount=Decimal("3000.00"),
            payment_status="partially_paid",
        )

        # Recently paid invoice (within 30 days)
        self.inv_paid_recent = PurchaseInvoice.objects.create(
            invoice_number="INV-PAID-RECENT",
            company=self.company,
            vendor=self.vendor,
            invoice_date=today - timedelta(days=10),
            total_amount=Decimal("2000.00"),
            payment_status="paid",
            payment_date=today - timedelta(days=5),
        )

        # Old paid invoice (> 30 days ago)
        self.inv_paid_old = PurchaseInvoice.objects.create(
            invoice_number="INV-PAID-OLD",
            company=self.company,
            vendor=self.vendor,
            invoice_date=today - timedelta(days=60),
            total_amount=Decimal("1000.00"),
            payment_status="paid",
            payment_date=today - timedelta(days=45),
        )

    def test_unpaid_invoice_count(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        # unpaid + partially_paid = 2
        self.assertEqual(ctx["unpaid_invoices"], 2)

    def test_unpaid_amount(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        # 5000 + 3000 = 8000
        self.assertEqual(ctx["unpaid_amount"], Decimal("8000.00"))

    def test_recently_paid_invoice_count(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        # Only the invoice paid within the last 30 days
        self.assertEqual(ctx["recently_paid_invoices"], 1)

    def test_recently_paid_amount(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertEqual(ctx["recently_paid_amount"], Decimal("2000.00"))

    def test_total_invoices(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertEqual(ctx["total_invoices"], 4)

    def test_total_invoice_value(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        # 5000 + 3000 + 2000 + 1000 = 11000
        self.assertEqual(ctx["total_invoice_value"], Decimal("11000.00"))


# ======================================================================
# Dashboard – warranty alerts
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardWarrantyAlertTests(TestCase):
    """Test warranty expiration alerts on the dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company = Company.objects.create(name="WarCo", code="WC")
        self.category = Category.objects.create(name="Laptop")
        self.asset_model = AssetModel.objects.create(
            category=self.category,
            manufacturer="Dell",
            model_name="Latitude",
        )

        today = timezone.now().date()

        # Asset with warranty expiring within 90 days (should appear in alerts)
        self.asset_expiring = Asset.objects.create(
            company=self.company,
            asset_tag="W-EXPIRING",
            asset_model=self.asset_model,
            status="active",
            warranty_expiry_date=today + timedelta(days=30),
        )

        # Asset with warranty already expired (should count in expired_count)
        self.asset_expired = Asset.objects.create(
            company=self.company,
            asset_tag="W-EXPIRED",
            asset_model=self.asset_model,
            status="active",
            warranty_expiry_date=today - timedelta(days=10),
        )

        # Asset with warranty far in the future (should NOT appear in alerts)
        self.asset_ok = Asset.objects.create(
            company=self.company,
            asset_tag="W-OK",
            asset_model=self.asset_model,
            status="active",
            warranty_expiry_date=today + timedelta(days=365),
        )

        # Retired asset with warranty expiring (should NOT appear – not active)
        self.asset_retired = Asset.objects.create(
            company=self.company,
            asset_tag="W-RETIRED",
            asset_model=self.asset_model,
            status="retired",
            warranty_expiry_date=today + timedelta(days=30),
        )

    def test_warranty_expiring_includes_soon_to_expire_active_assets(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        expiring_tags = [a.asset_tag for a in ctx["warranty_expiring"]]
        self.assertIn("W-EXPIRING", expiring_tags)

    def test_warranty_expiring_excludes_far_future(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        expiring_tags = [a.asset_tag for a in ctx["warranty_expiring"]]
        self.assertNotIn("W-OK", expiring_tags)

    def test_warranty_expiring_excludes_already_expired(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        expiring_tags = [a.asset_tag for a in ctx["warranty_expiring"]]
        self.assertNotIn("W-EXPIRED", expiring_tags)

    def test_warranty_expiring_excludes_retired_assets(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        expiring_tags = [a.asset_tag for a in ctx["warranty_expiring"]]
        self.assertNotIn("W-RETIRED", expiring_tags)

    def test_warranty_expired_count(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertEqual(ctx["warranty_expired_count"], 1)


# ======================================================================
# Dashboard – requisition summary
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardRequisitionSummaryTests(TestCase):
    """Test the requisition summary section of the dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company = Company.objects.create(name="ReqCo", code="RC")
        self.department = Department.objects.create(
            company=self.company, name="Engineering"
        )
        self.employee = Employee.objects.create(
            name="Requester",
            company=self.company,
            department=self.department,
            status="active",
        )

        today = timezone.now().date()

        self.req_pending1 = Requisition.objects.create(
            requisition_number="REQ-P1",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=today,
            status="pending",
            priority="high",
        )
        self.req_pending2 = Requisition.objects.create(
            requisition_number="REQ-P2",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=today,
            status="pending",
            priority="normal",
        )
        self.req_fulfilled_recent = Requisition.objects.create(
            requisition_number="REQ-F1",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=today - timedelta(days=10),
            status="fulfilled",
            fulfilled_date=today - timedelta(days=5),
        )
        self.req_fulfilled_old = Requisition.objects.create(
            requisition_number="REQ-F2",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=today - timedelta(days=60),
            status="fulfilled",
            fulfilled_date=today - timedelta(days=45),
        )
        self.req_cancelled = Requisition.objects.create(
            requisition_number="REQ-C1",
            company=self.company,
            department=self.department,
            requested_by=self.employee,
            requisition_date=today,
            status="cancelled",
        )

    def test_pending_requisitions_count(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertEqual(ctx["pending_requisitions_count"], 2)

    def test_fulfilled_requisitions_30d(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        # Only 1 was fulfilled within last 30 days
        self.assertEqual(ctx["fulfilled_requisitions_30d"], 1)

    def test_pending_requisitions_queryset(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        req_numbers = [r.requisition_number for r in ctx["pending_requisitions"]]
        self.assertIn("REQ-P1", req_numbers)
        self.assertIn("REQ-P2", req_numbers)
        self.assertNotIn("REQ-F1", req_numbers)
        self.assertNotIn("REQ-C1", req_numbers)

    def test_pending_requisitions_ordered_by_priority_then_date(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        reqs = list(ctx["pending_requisitions"])
        # Dashboard orders by -priority (descending alphabetical on CharField).
        # Alphabetically: "normal" > "high", so REQ-P2 (normal) comes first.
        self.assertEqual(reqs[0].requisition_number, "REQ-P2")
        self.assertEqual(reqs[1].requisition_number, "REQ-P1")


# ======================================================================
# Dashboard – maintenance summary
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardMaintenanceTests(TestCase):
    """Test the maintenance cost and recent maintenance section."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company = Company.objects.create(name="MaintCo", code="MC")
        self.category = Category.objects.create(name="Laptop")
        self.asset_model = AssetModel.objects.create(
            category=self.category,
            manufacturer="Dell",
            model_name="Latitude",
        )
        self.asset = Asset.objects.create(
            company=self.company,
            asset_tag="MAINT-001",
            asset_model=self.asset_model,
            status="active",
        )

        today = timezone.now().date()

        # Recent maintenance record (within 30 days)
        self.maint_recent = MaintenanceRecord.objects.create(
            asset=self.asset,
            maintenance_type="repair",
            maintenance_date=today - timedelta(days=5),
            cost=Decimal("150.00"),
            description="Screen replacement",
        )

        # Another recent maintenance
        self.maint_recent2 = MaintenanceRecord.objects.create(
            asset=self.asset,
            maintenance_type="upgrade",
            maintenance_date=today - timedelta(days=10),
            cost=Decimal("250.00"),
            description="RAM upgrade",
        )

        # Old maintenance (> 30 days)
        self.maint_old = MaintenanceRecord.objects.create(
            asset=self.asset,
            maintenance_type="repair",
            maintenance_date=today - timedelta(days=60),
            cost=Decimal("500.00"),
            description="Old repair",
        )

    def test_total_maintenance_cost_30d(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        # 150 + 250 = 400 (old record is beyond 30 days)
        self.assertEqual(ctx["total_maintenance_cost_30d"], Decimal("400.00"))

    def test_recent_maintenance_queryset(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        # All 3 records should appear in recent_maintenance (no date filter,
        # just the most recent 5 ordered by -maintenance_date)
        descriptions = [m.description for m in ctx["recent_maintenance"]]
        self.assertIn("Screen replacement", descriptions)
        self.assertIn("RAM upgrade", descriptions)
        self.assertIn("Old repair", descriptions)

    def test_recent_maintenance_ordered_by_date_desc(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        dates = [m.maintenance_date for m in ctx["recent_maintenance"]]
        self.assertEqual(dates, sorted(dates, reverse=True))


# ======================================================================
# Dashboard – low stock spare parts
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardLowStockTests(TestCase):
    """Test the low stock spare parts alert section."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.ct_ram = ComponentType.objects.create(type_name="RAM")
        self.ct_ssd = ComponentType.objects.create(type_name="SSD")
        self.ct_gpu = ComponentType.objects.create(type_name="GPU")

        # Low stock: quantity_available <= quantity_minimum
        self.spare_low = SparePartsInventory.objects.create(
            component_type=self.ct_ram,
            quantity_available=2,
            quantity_minimum=5,
        )

        # At minimum (equal) – should also trigger
        self.spare_at_min = SparePartsInventory.objects.create(
            component_type=self.ct_ssd,
            quantity_available=3,
            quantity_minimum=3,
        )

        # Plenty of stock – should NOT appear
        self.spare_ok = SparePartsInventory.objects.create(
            component_type=self.ct_gpu,
            quantity_available=10,
            quantity_minimum=2,
        )

    def test_low_stock_parts_includes_below_minimum(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        low_stock_types = [sp.component_type.type_name for sp in ctx["low_stock_parts"]]
        self.assertIn("RAM", low_stock_types)

    def test_low_stock_parts_includes_at_minimum(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        low_stock_types = [sp.component_type.type_name for sp in ctx["low_stock_parts"]]
        self.assertIn("SSD", low_stock_types)

    def test_low_stock_parts_excludes_well_stocked(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        low_stock_types = [sp.component_type.type_name for sp in ctx["low_stock_parts"]]
        self.assertNotIn("GPU", low_stock_types)

    def test_low_stock_ordered_by_quantity_available(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        quantities = [sp.quantity_available for sp in ctx["low_stock_parts"]]
        self.assertEqual(quantities, sorted(quantities))


# ======================================================================
# Dashboard – top departments
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardTopDepartmentsTests(TestCase):
    """Test the top departments by asset count section."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company = Company.objects.create(name="DeptCo", code="DC")
        self.dept_a = Department.objects.create(company=self.company, name="Dept A")
        self.dept_b = Department.objects.create(company=self.company, name="Dept B")
        self.category = Category.objects.create(name="Laptop")
        self.asset_model = AssetModel.objects.create(
            category=self.category,
            manufacturer="Dell",
            model_name="Latitude",
        )

    def test_top_departments_in_context(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertIn("top_departments", ctx)

    def test_top_departments_limited_to_five(self):
        """Even with many departments, only top 5 should be returned."""
        for i in range(10):
            Department.objects.create(company=self.company, name=f"Extra Dept {i}")

        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertLessEqual(len(ctx["top_departments"]), 5)


# ======================================================================
# Dashboard – assets by month
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardAssetsByMonthTests(TestCase):
    """Test the assets-added-over-time chart data."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company = Company.objects.create(name="ChartCo", code="CC")
        self.category = Category.objects.create(name="Laptop")
        self.asset_model = AssetModel.objects.create(
            category=self.category,
            manufacturer="Dell",
            model_name="Latitude",
        )

    def test_assets_by_month_has_six_months(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertEqual(len(ctx["assets_by_month"]), 6)

    def test_assets_by_month_current_month_has_count(self):
        """Creating an asset now should bump the current month's count."""
        Asset.objects.create(
            company=self.company,
            asset_tag="CHART-001",
            asset_model=self.asset_model,
            status="active",
        )

        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        current_month = timezone.now().strftime("%b")
        current_entry = None
        for entry in ctx["assets_by_month"]:
            if entry["month"] == current_month:
                current_entry = entry
                break

        self.assertIsNotNone(
            current_entry, "Current month should be in assets_by_month"
        )
        self.assertGreaterEqual(current_entry["count"], 1)

    def test_assets_by_month_entries_have_correct_structure(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        for entry in ctx["assets_by_month"]:
            self.assertIn("month", entry)
            self.assertIn("count", entry)
            self.assertIsInstance(entry["month"], str)
            self.assertIsInstance(entry["count"], int)


# ======================================================================
# Dashboard – recent activity
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardRecentActivityTests(TestCase):
    """Test that recent activity shows in the dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

    def test_recent_activity_empty(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertEqual(len(ctx["recent_activity"]), 0)

    def test_recent_activity_after_creating_objects(self):
        """Creating objects should generate activity log entries visible on the dashboard."""
        company = Company.objects.create(name="ActCo", code="AC")
        vendor = Vendor.objects.create(vendor_name="ActVendor")
        location = Location.objects.create(name="ActLoc")

        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context

        # Signal-based auto-logging should have created entries
        self.assertGreater(len(ctx["recent_activity"]), 0)

    def test_recent_activity_limited_to_ten(self):
        """At most 10 entries should be shown on the dashboard."""
        # Create more than 10 objects to generate more than 10 log entries
        for i in range(15):
            Location.objects.create(name=f"Loc-{i}")

        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertLessEqual(len(ctx["recent_activity"]), 10)


# ======================================================================
# Dashboard – base_template context
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class DashboardBaseTemplateTests(TestCase):
    """Test that base_template is correctly set for regular and HTMX requests."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

    def test_regular_request_uses_full_base(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertEqual(ctx["base_template"], "base.html")

    def test_htmx_request_uses_partial_base(self):
        resp = self.client.get(
            reverse("propraetor:dashboard"),
            HTTP_HX_REQUEST="true",
        )
        ctx = resp.context
        self.assertEqual(ctx["base_template"], "partials/partial_base.html")

    def test_today_in_context(self):
        resp = self.client.get(reverse("propraetor:dashboard"))
        ctx = resp.context
        self.assertIsNotNone(ctx["today"])
