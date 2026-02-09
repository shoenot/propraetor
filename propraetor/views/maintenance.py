"""Maintenance views."""

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import MaintenanceRecordForm
from ..models import MaintenanceRecord
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# MAINTENANCE RECORDS
# ============================================================================


def maintenance_list(request):
    queryset = MaintenanceRecord.objects.select_related("asset")
    columns = [
        TableColumn(
            "asset",
            "ASSET",
            "asset.asset_tag",
            sort_field="asset__asset_tag",
            link_pattern=url_pattern("propraetor:maintenance_details", record_id="id"),
            width="tag-col",
        ),
        TableColumn(
            "maintenance_type",
            "TYPE",
            "maintenance_type",
            badge=True,
            badge_map={"repair": "status-in_repair", "upgrade": "status-active"},
            width="type-col",
        ),
        TableColumn("performed_by", "PERFORMED BY", "performed_by", width="name-col"),
        TableColumn("maintenance_date", "DATE", "maintenance_date", width="date-col"),
        TableColumn("cost", "COST", "cost", width="money-col"),
        TableColumn(
            "next_maintenance_date",
            "NEXT DATE",
            "next_maintenance_date",
            default_visible=False,
            width="date-col",
        ),
    ]

    bulk_actions = [
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:maintenance_bulk_delete"),
            confirmation="DELETE SELECTED MAINTENANCE RECORDS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=queryset,
        columns=columns,
        table_id="maintenance-table",
        search_fields=[
            "asset__asset_tag",
            "performed_by",
            "description",
            "maintenance_type",
        ],
        filter_fields={"type": "maintenance_type"},
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Maintenance Records"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "type", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    context.update({"base_template": get_base_template(request)})
    return render(request, "maintenance/maintenance_list.html", context)


def maintenance_create(request):
    """Create a new maintenance record."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST)
        if form.is_valid():
            record = form.save()
            messages.success(
                request,
                f"Maintenance record for '{record.asset.asset_tag}' created successfully.",
            )
            return htmx_redirect(
                request, "propraetor:maintenance_details", record_id=record.id
            )
    else:
        form = MaintenanceRecordForm()

    context = {"form": form, "base_template": base_template}
    return render(request, "maintenance/maintenance_create.html", context)


def maintenance_edit(request, record_id):
    """Edit an existing maintenance record."""
    base_template = get_base_template(request)
    record = get_object_or_404(MaintenanceRecord, pk=record_id)

    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, "Maintenance record updated successfully.")
            return htmx_redirect(
                request, "propraetor:maintenance_details", record_id=record.id
            )
    else:
        form = MaintenanceRecordForm(instance=record)

    context = {
        "form": form,
        "object": record,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "maintenance/maintenance_create.html", context)


def maintenance_details(request, record_id):
    """Maintenance record detail page."""
    base_template = get_base_template(request)
    record = get_object_or_404(
        MaintenanceRecord.objects.select_related("asset"),
        pk=record_id,
    )
    context = {"record": record, "base_template": base_template}
    return render(request, "maintenance/maintenance_details.html", context)


@require_http_methods(["DELETE"])
def maintenance_delete(request, record_id):
    """Delete a maintenance record."""
    record = get_object_or_404(MaintenanceRecord, pk=record_id)
    record.delete()
    messages.success(request, "Maintenance record deleted successfully.")
    return htmx_redirect(request, "propraetor:maintenance_list")


@require_POST
def maintenance_bulk_delete(request):
    """Bulk delete selected maintenance records."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = MaintenanceRecord.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} maintenance record(s) deleted.")
    else:
        messages.warning(request, "No maintenance records selected.")
    return htmx_redirect(request, "propraetor:maintenance_list")
