from django.db import migrations, models


def generate_component_tags(apps, schema_editor):
    """Backfill component_tag for every existing Component row."""
    Component = apps.get_model("propraetor", "Component")

    # Build a map of component_type_id → type_name so we can derive prefixes
    ComponentType = apps.get_model("propraetor", "ComponentType")
    type_names = dict(ComponentType.objects.values_list("id", "type_name"))

    # Track the running sequence per prefix so we don't re-scan on every row
    prefix_seq = {}  # prefix → current max sequence number

    for component in Component.objects.select_related("component_type").order_by("pk"):
        ct_name = type_names.get(component.component_type_id, "COMP") or "COMP"
        prefix = ct_name[:4].upper().replace(" ", "")

        if prefix not in prefix_seq:
            # Seed from any tags that may already exist (e.g. partial migration)
            max_seq = 0
            existing = (
                Component.objects.filter(component_tag__startswith=f"{prefix}-")
                .exclude(component_tag__isnull=True)
                .exclude(component_tag="")
                .values_list("component_tag", flat=True)
            )
            for tag in existing:
                suffix = tag[len(prefix) + 1 :]
                try:
                    max_seq = max(max_seq, int(suffix))
                except (ValueError, IndexError):
                    continue
            prefix_seq[prefix] = max_seq

        prefix_seq[prefix] += 1
        component.component_tag = f"{prefix}-{prefix_seq[prefix]:04d}"
        component.save(update_fields=["component_tag"])


class Migration(migrations.Migration):

    dependencies = [
        ("propraetor", "0013_add_line_item_fks_and_requisition_invoice"),
    ]

    operations = [
        # Step 1: Add the field as nullable so existing rows aren't blocked.
        migrations.AddField(
            model_name="component",
            name="component_tag",
            field=models.CharField(
                blank=True,
                help_text="Unique identifier for this component (auto-generated if left blank).",
                max_length=100,
                null=True,
            ),
        ),
        # Step 2: Backfill every existing row with a generated tag.
        migrations.RunPython(
            generate_component_tags,
            migrations.RunPython.noop,
            elidable=True,
        ),
        # Step 3: Make the field non-nullable and unique; update ordering and indexes.
        migrations.AlterField(
            model_name="component",
            name="component_tag",
            field=models.CharField(
                blank=True,
                help_text="Unique identifier for this component (auto-generated if left blank).",
                max_length=100,
                unique=True,
            ),
        ),
        migrations.AlterModelOptions(
            name="component",
            options={"ordering": ["component_tag"]},
        ),
    ]