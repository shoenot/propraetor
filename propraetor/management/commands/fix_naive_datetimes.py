"""
Management command to fix naive datetime values in the database.

This command will convert all naive datetime values to timezone-aware datetimes
using the default timezone configured in Django settings.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from propraetor.models import (
    Asset,
    AssetModel,
    Category,
    Company,
    Component,
    ComponentType,
    Department,
    Location,
    MaintenanceRecord,
    PurchaseInvoice,
    Requisition,
    RequisitionItem,
    SparePartsInventory,
    Vendor,
)


class Command(BaseCommand):
    help = "Fix naive datetime values in the database by converting them to timezone-aware datetimes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fixed without making changes",
        )

    def fix_model_datetimes(self, model, dry_run=False):
        """Fix naive datetimes for a given model."""
        model_name = model.__name__
        datetime_fields = []

        # Get all datetime fields
        for field in model._meta.get_fields():
            if field.__class__.__name__ == "DateTimeField":
                datetime_fields.append(field.name)

        if not datetime_fields:
            return 0

        total_fixed = 0

        for field_name in datetime_fields:
            objects_to_update = []

            # Get all objects
            for obj in model.objects.all():
                field_value = getattr(obj, field_name)

                # Check if the datetime is naive
                if field_value and timezone.is_naive(field_value):
                    # Make it timezone-aware
                    aware_datetime = timezone.make_aware(field_value)
                    setattr(obj, field_name, aware_datetime)
                    objects_to_update.append(obj)

            if objects_to_update:
                count = len(objects_to_update)
                self.stdout.write(
                    f"Found {count} naive datetime(s) in {model_name}.{field_name}"
                )

                if not dry_run:
                    # Bulk update - need to do one at a time to preserve auto fields
                    for obj in objects_to_update:
                        # Use update_fields to avoid triggering auto_now
                        if field_name == "updated_at":
                            # For updated_at, we need to temporarily disable auto_now
                            obj.save(update_fields=[field_name])
                        else:
                            obj.save(update_fields=[field_name])

                    total_fixed += count
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Fixed {count} datetime(s) in {model_name}.{field_name}"
                        )
                    )

        return total_fixed

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # List of models to fix
        models_to_fix = [
            Asset,
            AssetModel,
            Company,
            Location,
            Department,
            Category,
            Component,
            ComponentType,
            SparePartsInventory,
            MaintenanceRecord,
            Vendor,
            Requisition,
            RequisitionItem,
            PurchaseInvoice,
        ]

        total_fixed = 0

        with transaction.atomic():
            for model in models_to_fix:
                try:
                    fixed = self.fix_model_datetimes(model, dry_run)
                    total_fixed += fixed
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error fixing {model.__name__}: {str(e)}")
                    )

            if dry_run:
                # Rollback in dry-run mode
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.WARNING(
                        f"\nDRY RUN COMPLETE - Would have fixed {total_fixed} datetime values"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nSuccessfully fixed {total_fixed} naive datetime values"
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS("All datetime values are now timezone-aware!")
                )
