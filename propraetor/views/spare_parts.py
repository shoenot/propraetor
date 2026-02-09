"""Spare parts views."""

from django.contrib import messages
from django.db.models import F
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..forms import SparePartsInventoryForm
from ..models import SparePartsInventory
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# SPARE PARTS INVENTORY
# ============================================================================


def spare_parts_list(request):
    queryset = SparePartsInventory.objects.select_related("component_type", "location")
    columns = [
        TableColumn(
            "component_type",
            "TYPE",
            "component_type.type_name",
            sort_field="component_type__type_name",
            link_pattern=url_pattern(
                "propraetor:spare_part_details", spare_part_id="id"
            ),
            width="type-col",
        ),
        TableColumn("manufacturer", "MFG", "manufacturer", width="manufacturer-col"),
        TableColumn("model", "MODEL", "model", width="model-col"),
        TableColumn("quantity_available", "QTY AVAIL", "quantity_available", width="qty-col"),
        TableColumn("quantity_minimum", "QTY MIN", "quantity_minimum", width="qty-col"),
        TableColumn(
            "location",
            "LOCATION",
            "location.name",
            sort_field="location__name",
            width="location-col",
        ),
        TableColumn("last_restocked", "RESTOCKED", "last_restocked", width="date-col"),
    ]

    bulk_actions = [
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:spare_parts_bulk_delete"),
            confirmation="DELETE SELECTED SPARE PARTS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=queryset,
        columns=columns,
        table_id="spare-parts-table",
        search_fields=[
            "component_type__type_name",
            "manufacturer",
            "model",
            "specifications",
        ],
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Spare Parts Inventory"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    low_stock_count = SparePartsInventory.objects.filter(
        quantity_available__lte=F("quantity_minimum")
    ).count()

    context.update(
        {
            "base_template": get_base_template(request),
            "low_stock_count": low_stock_count,
            "total_parts": SparePartsInventory.objects.count(),
        }
    )
    return render(request, "spare_parts/spare_parts_list.html", context)


def spare_part_create(request):
    """Create a new spare part inventory entry."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = SparePartsInventoryForm(request.POST)
        if form.is_valid():
            spare = form.save()
            messages.success(request, f"Spare part '{spare}' created successfully.")
            return htmx_redirect(
                request, "propraetor:spare_part_details", spare_part_id=spare.id
            )
    else:
        form = SparePartsInventoryForm()

    context = {"form": form, "base_template": base_template}
    return render(request, "spare_parts/spare_part_create.html", context)


def spare_part_edit(request, spare_part_id):
    """Edit an existing spare part inventory entry."""
    base_template = get_base_template(request)
    spare = get_object_or_404(SparePartsInventory, pk=spare_part_id)

    if request.method == "POST":
        form = SparePartsInventoryForm(request.POST, instance=spare)
        if form.is_valid():
            form.save()
            messages.success(request, f"Spare part '{spare}' updated successfully.")
            return htmx_redirect(
                request, "propraetor:spare_part_details", spare_part_id=spare.id
            )
    else:
        form = SparePartsInventoryForm(instance=spare)

    context = {
        "form": form,
        "object": spare,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "spare_parts/spare_part_create.html", context)


def spare_part_details(request, spare_part_id):
    """Spare part detail page."""
    base_template = get_base_template(request)
    spare = get_object_or_404(
        SparePartsInventory.objects.select_related("component_type", "location"),
        pk=spare_part_id,
    )
    spare_components = spare.spare_components
    context = {
        "spare": spare,
        "spare_components": spare_components,
        "base_template": base_template,
    }
    return render(request, "spare_parts/spare_part_details.html", context)


@require_http_methods(["DELETE"])
def spare_part_delete(request, spare_part_id):
    """Delete a spare part inventory entry."""
    spare = get_object_or_404(SparePartsInventory, pk=spare_part_id)
    spare.delete()
    messages.success(request, "Spare part deleted successfully.")
    return htmx_redirect(request, "propraetor:spare_parts_list")


@require_POST
def spare_parts_bulk_delete(request):
    """Bulk delete selected spare parts."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = SparePartsInventory.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} spare part(s) deleted.")
    else:
        messages.warning(request, "No spare parts selected.")
    return htmx_redirect(request, "propraetor:spare_parts_list")
