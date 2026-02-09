"""
Tests for the Spare Parts Inventory "configuration layer" UX (Option 2).

Covers:
- Template content: info-notice banners, renamed buttons/labels, correct links
- List page: info banner, de-emphasised create button, view_spare_components link
- Detail page: info banner, auto-sync annotations, quick actions, empty-state text
- Create form: info banner, quantity_available hidden, renamed submit button
- Edit form: info banner, quantity_available visible (disabled), renamed title
- Form field help text updates
- Auto-sync integration: Component save/delete keeps SparePartsInventory in sync
- sync_all_spare_parts bulk utility
- Delete only removes config entry, not the actual spare components
"""

from django.contrib.auth.models import User as DjangoUser
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from propraetor.forms import SparePartsInventoryForm
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
    SparePartsInventory,
    sync_all_spare_parts,
    sync_spare_parts_for_type,
)

SIMPLE_STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


# ======================================================================
# Shared base
# ======================================================================


@override_settings(STORAGES=SIMPLE_STORAGES)
class SparePartsUXBase(TestCase):
    """Common fixtures for all spare-parts UX tests."""

    def setUp(self):
        self.client = Client()
        self.user = DjangoUser.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

        self.company = Company.objects.create(name="TestCo", code="TC")
        self.location = Location.objects.create(name="Warehouse A", city="Dhaka")
        self.department = Department.objects.create(
            company=self.company, name="IT"
        )
        self.category = Category.objects.create(name="Server")
        self.component_type = ComponentType.objects.create(type_name="RAM")
        self.component_type2 = ComponentType.objects.create(type_name="SSD")
        self.asset_model = AssetModel.objects.create(
            category=self.category,
            manufacturer="Dell",
            model_name="PowerEdge R740",
        )
        self.asset = Asset.objects.create(
            asset_model=self.asset_model,
            asset_tag="AST-001",
            status="active",
        )

        # Pre-create a spare parts inventory entry with metadata
        self.spare_entry = SparePartsInventory.objects.create(
            component_type=self.component_type,
            manufacturer="Kingston",
            model="DDR5-4800",
            quantity_available=0,
            quantity_minimum=5,
            location=self.location,
            notes="Keep at least 5 sticks on hand.",
        )


# ======================================================================
# List page template tests
# ======================================================================


class SparePartsListTemplateTests(SparePartsUXBase):
    """Verify the list page renders the Option 2 UX elements."""

    def _get_list(self):
        return self.client.get(reverse("propraetor:spare_parts_list"))

    def test_list_returns_200(self):
        resp = self._get_list()
        self.assertEqual(resp.status_code, 200)

    def test_list_contains_info_notice(self):
        resp = self._get_list()
        self.assertContains(resp, "configuration")
        self.assertContains(resp, "metadata layer")

    def test_list_info_notice_links_to_spare_components(self):
        """Info banner should link to components list filtered to spare status."""
        resp = self._get_list()
        components_url = reverse("propraetor:components_list")
        self.assertContains(resp, f'{components_url}?status=spare')

    def test_list_has_view_spare_components_button(self):
        resp = self._get_list()
        self.assertContains(resp, "view_spare_components")

    def test_list_add_button_is_secondary(self):
        """The add button should be btn-secondary, not btn-primary."""
        resp = self._get_list()
        content = resp.content.decode()
        create_url = reverse("propraetor:spare_part_create")
        # Find the link to the create URL and verify it uses btn-secondary
        idx = content.find(create_url)
        self.assertNotEqual(idx, -1, "Create URL not found in list page")
        # Look forward for the class attribute (class comes after href)
        snippet = content[idx:idx + 200]
        self.assertIn("btn-secondary", snippet)
        self.assertNotIn("btn-primary", snippet)

    def test_list_add_button_label_renamed(self):
        """Button should say 'add_inventory_entry', not 'add_spare_part'."""
        resp = self._get_list()
        self.assertContains(resp, "add_inventory_entry")
        self.assertNotContains(resp, "add_spare_part")

    def test_list_stats_cards_render(self):
        resp = self._get_list()
        self.assertContains(resp, "total_parts")
        self.assertContains(resp, "low_stock")

    def test_list_contains_existing_entry(self):
        resp = self._get_list()
        self.assertContains(resp, "RAM")


# ======================================================================
# Detail page template tests
# ======================================================================


class SparePartsDetailTemplateTests(SparePartsUXBase):
    """Verify the detail page renders the Option 2 UX elements."""

    def _get_detail(self):
        return self.client.get(
            reverse(
                "propraetor:spare_part_details",
                kwargs={"spare_part_id": self.spare_entry.pk},
            )
        )

    def test_detail_returns_200(self):
        resp = self._get_detail()
        self.assertEqual(resp.status_code, 200)

    def test_detail_contains_info_notice(self):
        resp = self._get_detail()
        self.assertContains(resp, "inventory configuration entry")

    def test_detail_info_notice_mentions_auto_derived(self):
        resp = self._get_detail()
        self.assertContains(resp, "automatically derived")

    def test_detail_info_notice_links_to_spare_components(self):
        resp = self._get_detail()
        components_url = reverse("propraetor:components_list")
        self.assertContains(resp, f"{components_url}?status=spare")

    def test_detail_edit_button_says_edit_thresholds(self):
        resp = self._get_detail()
        self.assertContains(resp, "edit_thresholds")

    def test_detail_edit_button_is_secondary(self):
        """Header edit button should be btn-secondary, not btn-primary."""
        resp = self._get_detail()
        content = resp.content.decode()
        edit_url = reverse(
            "propraetor:spare_part_edit",
            kwargs={"spare_part_id": self.spare_entry.pk},
        )
        # Find the first occurrence (header button); class comes after href
        idx = content.find(edit_url)
        self.assertNotEqual(idx, -1)
        snippet = content[idx:idx + 200]
        self.assertIn("btn-secondary", snippet)

    def test_detail_delete_confirmation_mentions_components_unaffected(self):
        resp = self._get_detail()
        self.assertContains(
            resp, "actual spare components will not be affected"
        )

    def test_detail_quantity_available_shows_auto_synced(self):
        resp = self._get_detail()
        self.assertContains(resp, "(auto-synced)")

    def test_detail_quantity_available_shows_derived_from_link(self):
        resp = self._get_detail()
        self.assertContains(resp, "derived from")
        self.assertContains(resp, "spare components")

    def test_detail_quantity_minimum_shows_reorder_threshold(self):
        resp = self._get_detail()
        self.assertContains(resp, "(reorder threshold)")

    def test_detail_quick_action_view_spare_components(self):
        resp = self._get_detail()
        self.assertContains(resp, "view_spare_components")

    def test_detail_quick_action_edit_thresholds_metadata(self):
        resp = self._get_detail()
        self.assertContains(resp, "edit_thresholds_&amp;_metadata")

    def test_detail_quick_action_add_spare_component(self):
        """Quick action should link to the component create form."""
        resp = self._get_detail()
        self.assertContains(resp, "add_spare_component")
        component_create_url = reverse("propraetor:component_create")
        self.assertContains(resp, component_create_url)

    def test_detail_empty_state_explains_auto_population(self):
        """When no spare components exist, the message should explain auto-population."""
        resp = self._get_detail()
        self.assertContains(resp, "Stock will appear here automatically")
        self.assertContains(resp, "status=spare")

    def test_detail_with_spare_components_shows_view_all_link(self):
        """When spare components exist, a 'view all in components list' link appears."""
        Component.objects.create(
            component_type=self.component_type,
            parent_asset=self.asset,
            status="spare",
            manufacturer="Kingston",
        )
        resp = self._get_detail()
        self.assertContains(resp, "view_all_in_components_list")

    def test_detail_spare_components_table_renders(self):
        """Spare components table shows component data."""
        comp = Component.objects.create(
            component_type=self.component_type,
            parent_asset=self.asset,
            status="spare",
            manufacturer="Kingston",
            model="DDR5",
        )
        resp = self._get_detail()
        self.assertContains(resp, comp.component_tag)
        self.assertContains(resp, "Kingston")

    def test_detail_404_for_nonexistent(self):
        resp = self.client.get(
            reverse(
                "propraetor:spare_part_details",
                kwargs={"spare_part_id": 99999},
            )
        )
        self.assertEqual(resp.status_code, 404)


# ======================================================================
# Create form template tests
# ======================================================================


class SparePartsCreateTemplateTests(SparePartsUXBase):
    """Verify the create form renders Option 2 UX elements."""

    def _get_create(self):
        return self.client.get(reverse("propraetor:spare_part_create"))

    def test_create_returns_200(self):
        resp = self._get_create()
        self.assertEqual(resp.status_code, 200)

    def test_create_has_info_notice(self):
        resp = self._get_create()
        self.assertContains(resp, "inventory configuration entry")

    def test_create_info_notice_explains_auto_derived(self):
        resp = self._get_create()
        self.assertContains(resp, "automatically derived")

    def test_create_title_says_new_inventory_entry(self):
        resp = self._get_create()
        self.assertContains(resp, "new_inventory_entry")

    def test_create_does_not_show_quantity_available(self):
        """quantity_available should be hidden on the create form."""
        resp = self._get_create()
        content = resp.content.decode()
        # The disabled input for quantity_available should NOT be present
        # Check that the field name attribute for quantity_available is absent
        self.assertNotIn('name="quantity_available"', content)

    def test_create_submit_button_says_create_inventory_entry(self):
        resp = self._get_create()
        self.assertContains(resp, "create_inventory_entry")

    def test_create_section_title_says_inventory_configuration(self):
        resp = self._get_create()
        self.assertContains(resp, "Inventory Configuration")

    def test_create_post_valid(self):
        """Creating an inventory entry should work with minimal valid data."""
        resp = self.client.post(
            reverse("propraetor:spare_part_create"),
            {
                "component_type": self.component_type2.pk,
                "quantity_available": 0,  # disabled field, ignored
                "quantity_minimum": 3,
                "manufacturer": "",
                "model": "",
            },
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertTrue(
            SparePartsInventory.objects.filter(
                component_type=self.component_type2
            ).exists()
        )

    def test_create_post_sets_quantity_minimum(self):
        self.client.post(
            reverse("propraetor:spare_part_create"),
            {
                "component_type": self.component_type2.pk,
                "quantity_available": 0,
                "quantity_minimum": 10,
            },
        )
        entry = SparePartsInventory.objects.get(component_type=self.component_type2)
        self.assertEqual(entry.quantity_minimum, 10)

    def test_create_post_missing_component_type(self):
        """component_type is required — form should re-render with errors."""
        before_count = SparePartsInventory.objects.count()
        resp = self.client.post(
            reverse("propraetor:spare_part_create"),
            {
                "quantity_available": 0,
                "quantity_minimum": 2,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(SparePartsInventory.objects.count(), before_count)


# ======================================================================
# Edit form template tests
# ======================================================================


class SparePartsEditTemplateTests(SparePartsUXBase):
    """Verify the edit form renders Option 2 UX elements."""

    def _get_edit(self):
        return self.client.get(
            reverse(
                "propraetor:spare_part_edit",
                kwargs={"spare_part_id": self.spare_entry.pk},
            )
        )

    def test_edit_returns_200(self):
        resp = self._get_edit()
        self.assertEqual(resp.status_code, 200)

    def test_edit_has_info_notice(self):
        resp = self._get_edit()
        self.assertContains(resp, "inventory configuration entry")

    def test_edit_info_notice_mentions_read_only(self):
        resp = self._get_edit()
        self.assertContains(resp, "read-only")

    def test_edit_title_says_edit_inventory_entry(self):
        resp = self._get_edit()
        self.assertContains(resp, "edit_inventory_entry")

    def test_edit_shows_quantity_available(self):
        """quantity_available SHOULD be visible on the edit form (disabled)."""
        resp = self._get_edit()
        content = resp.content.decode()
        self.assertIn("quantity_available", content)

    def test_edit_section_title_says_inventory_configuration(self):
        resp = self._get_edit()
        self.assertContains(resp, "Inventory Configuration")

    def test_edit_submit_button_says_save_changes(self):
        resp = self._get_edit()
        self.assertContains(resp, "save_changes")

    def test_edit_post_updates_metadata(self):
        """Editing should update metadata like quantity_minimum and notes."""
        resp = self.client.post(
            reverse(
                "propraetor:spare_part_edit",
                kwargs={"spare_part_id": self.spare_entry.pk},
            ),
            {
                "component_type": self.component_type.pk,
                "quantity_available": 0,
                "quantity_minimum": 20,
                "manufacturer": "Corsair",
                "model": "Vengeance",
                "notes": "Updated notes",
            },
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_minimum, 20)
        self.assertEqual(self.spare_entry.manufacturer, "Corsair")
        self.assertEqual(self.spare_entry.notes, "Updated notes")

    def test_edit_404_for_nonexistent(self):
        resp = self.client.get(
            reverse(
                "propraetor:spare_part_edit",
                kwargs={"spare_part_id": 99999},
            )
        )
        self.assertEqual(resp.status_code, 404)


# ======================================================================
# Form field / help-text tests
# ======================================================================


class SparePartsFormFieldTests(SparePartsUXBase):
    """Test form-level changes: help text, disabled state."""

    def test_quantity_available_is_disabled(self):
        form = SparePartsInventoryForm()
        self.assertTrue(form.fields["quantity_available"].disabled)

    def test_quantity_available_help_text_mentions_read_only(self):
        form = SparePartsInventoryForm()
        help_text = form.fields["quantity_available"].help_text
        self.assertIn("Read-only", help_text)

    def test_quantity_available_help_text_mentions_auto_synced(self):
        form = SparePartsInventoryForm()
        help_text = form.fields["quantity_available"].help_text
        self.assertIn("automatically synced", help_text)

    def test_quantity_minimum_help_text_mentions_reorder(self):
        form = SparePartsInventoryForm()
        help_text = form.fields["quantity_minimum"].help_text
        self.assertIn("Reorder threshold", help_text)

    def test_quantity_minimum_help_text_mentions_low_stock(self):
        form = SparePartsInventoryForm()
        help_text = form.fields["quantity_minimum"].help_text
        self.assertIn("low-stock", help_text)


# ======================================================================
# Auto-sync integration tests
# ======================================================================


class SparePartsAutoSyncTests(SparePartsUXBase):
    """
    Test that Component create/update/delete keeps SparePartsInventory
    quantity_available in sync via signals.
    """

    def test_creating_spare_component_updates_quantity(self):
        """When a spare component is created, the inventory count increases."""
        self.assertEqual(self.spare_entry.quantity_available, 0)
        Component.objects.create(
            component_type=self.component_type,
            status="spare",
        )
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 1)

    def test_creating_multiple_spare_components(self):
        for _ in range(3):
            Component.objects.create(
                component_type=self.component_type,
                status="spare",
            )
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 3)

    def test_creating_installed_component_does_not_change_quantity(self):
        """An installed component should not affect the spare count."""
        Component.objects.create(
            component_type=self.component_type,
            parent_asset=self.asset,
            status="installed",
        )
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 0)

    def test_changing_component_to_spare_increases_quantity(self):
        comp = Component.objects.create(
            component_type=self.component_type,
            parent_asset=self.asset,
            status="installed",
        )
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 0)

        comp.status = "spare"
        comp.save()
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 1)

    def test_changing_component_from_spare_to_installed_decreases_quantity(self):
        comp = Component.objects.create(
            component_type=self.component_type,
            status="spare",
        )
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 1)

        comp.status = "installed"
        comp.parent_asset = self.asset
        comp.save()
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 0)

    def test_deleting_spare_component_decreases_quantity(self):
        comp = Component.objects.create(
            component_type=self.component_type,
            status="spare",
        )
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 1)

        comp.delete()
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 0)

    def test_creating_spare_for_new_type_auto_creates_inventory_entry(self):
        """If no SparePartsInventory row exists, one is auto-created."""
        self.assertFalse(
            SparePartsInventory.objects.filter(
                component_type=self.component_type2
            ).exists()
        )
        Component.objects.create(
            component_type=self.component_type2,
            status="spare",
        )
        entry = SparePartsInventory.objects.get(component_type=self.component_type2)
        self.assertEqual(entry.quantity_available, 1)

    def test_inventory_entry_preserved_when_all_spares_removed(self):
        """
        When the last spare component is deleted, the inventory entry
        should be preserved (with quantity=0) so metadata is kept.
        """
        comp = Component.objects.create(
            component_type=self.component_type,
            status="spare",
        )
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 1)

        comp.delete()
        # Entry should still exist
        self.assertTrue(
            SparePartsInventory.objects.filter(pk=self.spare_entry.pk).exists()
        )
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 0)
        # Metadata should be untouched
        self.assertEqual(self.spare_entry.quantity_minimum, 5)
        self.assertEqual(self.spare_entry.notes, "Keep at least 5 sticks on hand.")


# ======================================================================
# sync_spare_parts_for_type unit tests
# ======================================================================


class SyncSparePartsForTypeTests(SparePartsUXBase):
    """Test the sync_spare_parts_for_type utility function directly."""

    def test_sync_updates_existing_entry(self):
        Component.objects.create(
            component_type=self.component_type,
            status="spare",
        )
        Component.objects.create(
            component_type=self.component_type,
            status="spare",
        )
        # Manually desync the entry
        SparePartsInventory.objects.filter(pk=self.spare_entry.pk).update(
            quantity_available=99
        )
        sync_spare_parts_for_type(self.component_type)
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 2)

    def test_sync_creates_entry_if_missing(self):
        Component.objects.create(
            component_type=self.component_type2,
            status="spare",
        )
        # Remove any auto-created entry
        SparePartsInventory.objects.filter(
            component_type=self.component_type2
        ).delete()

        sync_spare_parts_for_type(self.component_type2)
        entry = SparePartsInventory.objects.get(component_type=self.component_type2)
        self.assertEqual(entry.quantity_available, 1)

    def test_sync_zeros_out_when_no_spares(self):
        self.spare_entry.quantity_available = 10
        self.spare_entry.save()
        sync_spare_parts_for_type(self.component_type)
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 0)

    def test_sync_noop_when_already_correct(self):
        """No write should occur if count already matches."""
        Component.objects.create(
            component_type=self.component_type,
            status="spare",
        )
        self.spare_entry.refresh_from_db()
        original_updated_at = self.spare_entry.updated_at

        sync_spare_parts_for_type(self.component_type)
        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.updated_at, original_updated_at)


# ======================================================================
# sync_all_spare_parts bulk utility tests
# ======================================================================


class SyncAllSparePartsTests(SparePartsUXBase):
    """Test the sync_all_spare_parts bulk utility."""

    def test_sync_all_corrects_multiple_types(self):
        # Create spare components for two types
        for _ in range(3):
            Component.objects.create(
                component_type=self.component_type, status="spare"
            )
        for _ in range(2):
            Component.objects.create(
                component_type=self.component_type2, status="spare"
            )

        # Desync all entries
        SparePartsInventory.objects.all().update(quantity_available=99)

        sync_all_spare_parts()

        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 3)

        entry2 = SparePartsInventory.objects.get(component_type=self.component_type2)
        self.assertEqual(entry2.quantity_available, 2)

    def test_sync_all_zeros_out_orphaned_entries(self):
        """Entries with no spare components should be zeroed out."""
        self.spare_entry.quantity_available = 50
        self.spare_entry.save()

        sync_all_spare_parts()

        self.spare_entry.refresh_from_db()
        self.assertEqual(self.spare_entry.quantity_available, 0)

    def test_sync_all_creates_missing_entries(self):
        Component.objects.create(
            component_type=self.component_type2, status="spare"
        )
        # Delete any auto-created entry
        SparePartsInventory.objects.filter(
            component_type=self.component_type2
        ).delete()

        sync_all_spare_parts()

        self.assertTrue(
            SparePartsInventory.objects.filter(
                component_type=self.component_type2
            ).exists()
        )
        entry = SparePartsInventory.objects.get(component_type=self.component_type2)
        self.assertEqual(entry.quantity_available, 1)


# ======================================================================
# Delete view: config entry removal vs component preservation
# ======================================================================


class SparePartsDeletePreservesComponentsTests(SparePartsUXBase):
    """
    Deleting a SparePartsInventory entry should only remove the config row —
    actual Components with status='spare' must remain untouched.
    """

    def test_delete_removes_inventory_entry(self):
        resp = self.client.delete(
            reverse(
                "propraetor:spare_part_delete",
                kwargs={"spare_part_id": self.spare_entry.pk},
            )
        )
        self.assertIn(resp.status_code, [200, 301, 302])
        self.assertFalse(
            SparePartsInventory.objects.filter(pk=self.spare_entry.pk).exists()
        )

    def test_delete_does_not_remove_spare_components(self):
        """Spare components should survive deletion of the inventory entry."""
        comp1 = Component.objects.create(
            component_type=self.component_type,
            status="spare",
        )
        comp2 = Component.objects.create(
            component_type=self.component_type,
            status="spare",
        )
        self.client.delete(
            reverse(
                "propraetor:spare_part_delete",
                kwargs={"spare_part_id": self.spare_entry.pk},
            )
        )
        # Both components should still exist
        self.assertTrue(Component.objects.filter(pk=comp1.pk).exists())
        self.assertTrue(Component.objects.filter(pk=comp2.pk).exists())
        # And they should still be spare
        comp1.refresh_from_db()
        comp2.refresh_from_db()
        self.assertEqual(comp1.status, "spare")
        self.assertEqual(comp2.status, "spare")

    def test_delete_404_for_nonexistent(self):
        resp = self.client.delete(
            reverse(
                "propraetor:spare_part_delete",
                kwargs={"spare_part_id": 99999},
            )
        )
        self.assertEqual(resp.status_code, 404)


# ======================================================================
# needs_restock property
# ======================================================================


class SparePartsNeedsRestockTests(SparePartsUXBase):
    """Test the needs_restock property used in the detail page UI."""

    def test_needs_restock_when_below_minimum(self):
        self.spare_entry.quantity_available = 2
        self.spare_entry.quantity_minimum = 5
        self.spare_entry.save()
        self.assertTrue(self.spare_entry.needs_restock)

    def test_needs_restock_when_equal_to_minimum(self):
        self.spare_entry.quantity_available = 5
        self.spare_entry.quantity_minimum = 5
        self.spare_entry.save()
        self.assertTrue(self.spare_entry.needs_restock)

    def test_adequate_when_above_minimum(self):
        self.spare_entry.quantity_available = 10
        self.spare_entry.quantity_minimum = 5
        self.spare_entry.save()
        self.assertFalse(self.spare_entry.needs_restock)

    def test_adequate_when_minimum_is_zero(self):
        self.spare_entry.quantity_available = 0
        self.spare_entry.quantity_minimum = 0
        self.spare_entry.save()
        self.assertTrue(self.spare_entry.needs_restock)

    def test_detail_page_shows_low_stock_badge_when_needed(self):
        self.spare_entry.quantity_available = 1
        self.spare_entry.quantity_minimum = 5
        self.spare_entry.save()
        resp = self.client.get(
            reverse(
                "propraetor:spare_part_details",
                kwargs={"spare_part_id": self.spare_entry.pk},
            )
        )
        self.assertContains(resp, "low_stock")
        self.assertContains(resp, "needs_restock")

    def test_detail_page_shows_adequate_when_stock_ok(self):
        self.spare_entry.quantity_available = 10
        self.spare_entry.quantity_minimum = 5
        self.spare_entry.save()
        resp = self.client.get(
            reverse(
                "propraetor:spare_part_details",
                kwargs={"spare_part_id": self.spare_entry.pk},
            )
        )
        self.assertContains(resp, "in_stock")
        self.assertContains(resp, "adequate")


# ======================================================================
# CSS class tests
# ======================================================================


class SparePartsInfoNoticeCSS(SparePartsUXBase):
    """Verify that info-notice CSS classes are present in the rendered pages."""

    def test_list_page_has_info_notice_class(self):
        resp = self.client.get(reverse("propraetor:spare_parts_list"))
        self.assertContains(resp, "info-notice")

    def test_detail_page_has_info_notice_class(self):
        resp = self.client.get(
            reverse(
                "propraetor:spare_part_details",
                kwargs={"spare_part_id": self.spare_entry.pk},
            )
        )
        self.assertContains(resp, "info-notice")

    def test_create_page_has_info_notice_class(self):
        resp = self.client.get(reverse("propraetor:spare_part_create"))
        self.assertContains(resp, "info-notice")

    def test_edit_page_has_info_notice_class(self):
        resp = self.client.get(
            reverse(
                "propraetor:spare_part_edit",
                kwargs={"spare_part_id": self.spare_entry.pk},
            )
        )
        self.assertContains(resp, "info-notice")

    def test_info_notice_muted_variant_on_list(self):
        resp = self.client.get(reverse("propraetor:spare_parts_list"))
        self.assertContains(resp, "info-notice-muted")

    def test_info_notice_muted_variant_on_detail(self):
        resp = self.client.get(
            reverse(
                "propraetor:spare_part_details",
                kwargs={"spare_part_id": self.spare_entry.pk},
            )
        )
        self.assertContains(resp, "info-notice-muted")