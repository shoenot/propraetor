from django.contrib.auth.models import User as DjangoUser
from django.core.exceptions import ValidationError
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
    InvoiceLineItem,
    PurchaseInvoice,
    Requisition,
    RequisitionItem,
    Vendor,
)


@override_settings(
    STORAGES={
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        }
    }
)
class RequisitionWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)
        self.company = Company.objects.create(name="Acme Corp", code="AC")
        self.department = Department.objects.create(company=self.company, name="IT")
        self.requester = Employee.objects.create(
            name="Requester",
            company=self.company,
            department=self.department,
            status="active",
        )
        self.asset_category = Category.objects.create(name="Laptop")
        self.component_type = ComponentType.objects.create(type_name="RAM Module")
        self.vendor = Vendor.objects.create(vendor_name="BestVendor")
        self.asset_model = AssetModel.objects.create(
            category=self.asset_category,
            manufacturer="",
            model_name="Model A",
        )
        self.invoice = PurchaseInvoice.objects.create(
            invoice_number="INV-001",
            company=self.company,
            vendor=self.vendor,
            invoice_date=timezone.now().date(),
            total_amount=1000,
        )
        self.asset_line_item = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            line_number=1,
            company=self.company,
            department=self.department,
            item_type="asset",
            description="Laptop Line",
            quantity=10,
            item_cost=100,
            asset_model=self.asset_model,
            component_type=None,
        )
        self.component_line_item = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            line_number=2,
            company=self.company,
            department=self.department,
            item_type="component",
            description="RAM Line",
            quantity=20,
            item_cost=50,
            asset_model=None,
            component_type=self.component_type,
        )
        # Create assets and components that can be used for fulfillment
        self.asset1 = Asset.objects.create(
            company=self.company,
            asset_tag="ASSET-001",
            asset_model=self.asset_model,
            invoice=self.invoice,
        )
        self.asset2 = Asset.objects.create(
            company=self.company,
            asset_tag="ASSET-002",
            asset_model=self.asset_model,
            invoice=self.invoice,
        )
        self.component1 = Component.objects.create(
            component_type=self.component_type,
            manufacturer="Kingston",
            status="spare",
            invoice=self.invoice,
        )
        self.component2 = Component.objects.create(
            component_type=self.component_type,
            manufacturer="Corsair",
            status="spare",
            invoice=self.invoice,
        )

    # ------------------------------------------------------------------ #
    # Requisition model basics
    # ------------------------------------------------------------------ #
    def test_requisition_creates_without_type(self):
        """Requisitions no longer require a requisition_type."""
        req = Requisition.objects.create(
            requisition_number="REQ-001",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        self.assertEqual(req.status, "pending")
        self.assertFalse(hasattr(req, "requisition_type"))
        self.assertEqual(str(req), "REQ-001")

    def test_requisition_str(self):
        req = Requisition.objects.create(
            requisition_number="REQ-STR",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        self.assertEqual(str(req), "REQ-STR")

    # ------------------------------------------------------------------ #
    # RequisitionItem validation
    # ------------------------------------------------------------------ #
    def test_item_requires_at_least_one_of_asset_or_component(self):
        req = Requisition.objects.create(
            requisition_number="REQ-002",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        item = RequisitionItem(
            requisition=req,
            item_type="asset",
            asset=None,
            component=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("asset", ctx.exception.error_dict)

    def test_item_cannot_have_both_asset_and_component(self):
        req = Requisition.objects.create(
            requisition_number="REQ-003",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        item = RequisitionItem(
            requisition=req,
            item_type="asset",
            asset=self.asset1,
            component=self.component1,
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("asset", ctx.exception.error_dict)
        self.assertIn("component", ctx.exception.error_dict)

    def test_item_type_auto_corrected_to_match_fk(self):
        """If item_type says 'component' but only asset is set, item_type is corrected."""
        req = Requisition.objects.create(
            requisition_number="REQ-004",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        item = RequisitionItem(
            requisition=req,
            item_type="component",  # mismatch
            asset=self.asset1,
            component=None,
        )
        item.save()
        self.assertEqual(item.item_type, "asset")

    def test_item_cannot_be_added_to_cancelled_requisition(self):
        req = Requisition.objects.create(
            requisition_number="REQ-005",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
            status="cancelled",
        )
        item = RequisitionItem(
            requisition=req,
            item_type="asset",
            asset=self.asset1,
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("requisition", ctx.exception.error_dict)

    def test_item_cannot_be_reassigned_to_different_requisition(self):
        req1 = Requisition.objects.create(
            requisition_number="REQ-006A",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        req2 = Requisition.objects.create(
            requisition_number="REQ-006B",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        item = RequisitionItem.objects.create(
            requisition=req1,
            item_type="asset",
            asset=self.asset1,
        )
        item.requisition = req2
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("requisition", ctx.exception.error_dict)

    # ------------------------------------------------------------------ #
    # Requisition mixed items (assets AND components)
    # ------------------------------------------------------------------ #
    def test_requisition_can_have_mixed_items(self):
        """A single requisition can hold both asset and component items."""
        req = Requisition.objects.create(
            requisition_number="REQ-MIXED",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        RequisitionItem.objects.create(
            requisition=req,
            item_type="asset",
            asset=self.asset1,
        )
        RequisitionItem.objects.create(
            requisition=req,
            item_type="component",
            component=self.component1,
        )
        self.assertEqual(req.items.count(), 2)
        types = set(req.items.values_list("item_type", flat=True))
        self.assertEqual(types, {"asset", "component"})

    # ------------------------------------------------------------------ #
    # RequisitionItem __str__
    # ------------------------------------------------------------------ #
    def test_item_str_asset(self):
        req = Requisition.objects.create(
            requisition_number="REQ-STR-A",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        item = RequisitionItem.objects.create(
            requisition=req,
            item_type="asset",
            asset=self.asset1,
        )
        self.assertIn("REQ-STR-A", str(item))
        self.assertIn(str(self.asset1), str(item))

    def test_item_str_component(self):
        req = Requisition.objects.create(
            requisition_number="REQ-STR-C",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        item = RequisitionItem.objects.create(
            requisition=req,
            item_type="component",
            component=self.component1,
        )
        self.assertIn("REQ-STR-C", str(item))

    def test_item_str_unlinked(self):
        req = Requisition.objects.create(
            requisition_number="REQ-STR-U",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        # Create via auto-populate (will fail validation if no match, so
        # test the __str__ path for completeness by checking the format)
        item = RequisitionItem(
            requisition=req,
            item_type="asset",
        )
        self.assertIn("unlinked", str(item))

    # ------------------------------------------------------------------ #
    # View: requisition_item_create
    # ------------------------------------------------------------------ #
    def test_requisition_item_create_view_creates_asset_record(self):
        req = Requisition.objects.create(
            requisition_number="REQ-VIEW-A",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        url = reverse(
            "propraetor:requisition_item_create",
            kwargs={"requisition_id": req.id},
        )
        response = self.client.post(
            url,
            {
                "requisition": req.id,
                "item_type": "asset",
                "asset": self.asset1.id,
                "notes": "Delivered",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(req.items.count(), 1)
        item = req.items.first()
        self.assertEqual(item.asset, self.asset1)
        self.assertEqual(item.item_type, "asset")

    def test_requisition_item_create_view_creates_component_record(self):
        req = Requisition.objects.create(
            requisition_number="REQ-VIEW-C",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        url = reverse(
            "propraetor:requisition_item_create",
            kwargs={"requisition_id": req.id},
        )
        response = self.client.post(
            url,
            {
                "requisition": req.id,
                "item_type": "component",
                "component": self.component1.id,
                "notes": "RAM module delivered",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(req.items.count(), 1)
        item = req.items.first()
        self.assertEqual(item.component, self.component1)
        self.assertEqual(item.item_type, "component")

    def test_requisition_item_create_view_rejects_get(self):
        req = Requisition.objects.create(
            requisition_number="REQ-VIEW-GET",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        url = reverse(
            "propraetor:requisition_item_create",
            kwargs={"requisition_id": req.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(req.items.count(), 0)

    # ------------------------------------------------------------------ #
    # Fulfill / cancel workflow
    # ------------------------------------------------------------------ #
    def test_fulfill_requires_at_least_one_item(self):
        req = Requisition.objects.create(
            requisition_number="REQ-FULFILL-EMPTY",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        url = reverse(
            "propraetor:requisition_fulfill",
            kwargs={"requisition_id": req.id},
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")

    def test_fulfill_succeeds_with_items(self):
        req = Requisition.objects.create(
            requisition_number="REQ-FULFILL-OK",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        RequisitionItem.objects.create(
            requisition=req,
            item_type="asset",
            asset=self.asset1,
        )
        url = reverse(
            "propraetor:requisition_fulfill",
            kwargs={"requisition_id": req.id},
        )
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, "fulfilled")
        self.assertIsNotNone(req.fulfilled_date)

    def test_cancel_requisition(self):
        req = Requisition.objects.create(
            requisition_number="REQ-CANCEL",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        url = reverse(
            "propraetor:requisition_cancel",
            kwargs={"requisition_id": req.id},
        )
        response = self.client.post(url, {"reason": "No longer needed"}, follow=True)
        self.assertEqual(response.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, "cancelled")
        self.assertEqual(req.cancellation_reason, "No longer needed")

    # ------------------------------------------------------------------ #
    # Bulk operations
    # ------------------------------------------------------------------ #
    def test_bulk_fulfill_only_affects_requisitions_with_items(self):
        req_with_items = Requisition.objects.create(
            requisition_number="REQ-BULK-A",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        RequisitionItem.objects.create(
            requisition=req_with_items,
            item_type="asset",
            asset=self.asset1,
        )
        req_without_items = Requisition.objects.create(
            requisition_number="REQ-BULK-B",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        url = reverse("propraetor:requisitions_bulk_fulfill")
        response = self.client.post(
            url,
            {"selected_ids": [req_with_items.id, req_without_items.id]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        req_with_items.refresh_from_db()
        req_without_items.refresh_from_db()
        self.assertEqual(req_with_items.status, "fulfilled")
        self.assertEqual(req_without_items.status, "pending")

    def test_bulk_cancel(self):
        req = Requisition.objects.create(
            requisition_number="REQ-BCANCEL",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        url = reverse("propraetor:requisitions_bulk_cancel")
        response = self.client.post(
            url,
            {"selected_ids": [req.id]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, "cancelled")

    # ------------------------------------------------------------------ #
    # Item deletion
    # ------------------------------------------------------------------ #
    def test_requisition_item_delete(self):
        req = Requisition.objects.create(
            requisition_number="REQ-DEL",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        item = RequisitionItem.objects.create(
            requisition=req,
            item_type="component",
            component=self.component1,
        )
        url = reverse(
            "propraetor:requisition_item_delete",
            kwargs={"item_id": item.id},
        )
        response = self.client.delete(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(req.items.count(), 0)

    # ------------------------------------------------------------------ #
    # Requisition create / edit views (no type field)
    # ------------------------------------------------------------------ #
    def test_create_requisition_view(self):
        url = reverse("propraetor:requisition_create")
        response = self.client.post(
            url,
            {
                "requisition_number": "REQ-NEW",
                "company": self.company.id,
                "department": self.department.id,
                "requested_by": self.requester.id,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "normal",
                "status": "pending",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Requisition.objects.filter(requisition_number="REQ-NEW").exists()
        )

    def test_edit_requisition_view(self):
        req = Requisition.objects.create(
            requisition_number="REQ-EDIT",
            company=self.company,
            department=self.department,
            requested_by=self.requester,
        )
        url = reverse(
            "propraetor:requisition_edit",
            kwargs={"requisition_id": req.id},
        )
        response = self.client.post(
            url,
            {
                "requisition_number": "REQ-EDIT",
                "company": self.company.id,
                "department": self.department.id,
                "requested_by": self.requester.id,
                "requisition_date": timezone.now().date().isoformat(),
                "priority": "high",
                "status": "pending",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.priority, "high")
