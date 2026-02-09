"""Asset views."""

from datetime import date, datetime, timedelta

from django.contrib import messages
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django_htmx.http import HttpResponseClientRedirect

from ..activity import log_activity, suppress_auto_log
from ..forms import AssetForm, AssetTransferLocationForm
from ..models import Asset, AssetAssignment, AssetModel, Location, MaintenanceRecord
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# ASSETS
# ============================================================================


def assets_list(request):
    columns = [
        TableColumn(
            "asset_tag",
            "TAG",
            "asset_tag",
            link_pattern=url_pattern("propraetor:asset_details", asset_id="id"),
            width="tag-col",
        ),
        TableColumn("asset_model", "MODEL", "asset_model", width="model-col"),
        TableColumn(
            "category", "CATEGORY", "asset_model.category.name", default_visible=True,
            width="category-col",
        ),
        TableColumn(
            "assigned_to",
            "ASSIGNED_TO",
            "assigned_to.name",
            sort_field="assigned_to__name",
            link_pattern=url_pattern(
                "propraetor:user_details", user_id="assigned_to.employee_id"
            ),
            width="name-col",
        ),
        TableColumn(
            "company",
            "COMPANY",
            "company.code",
            sort_field="company__code",
            link_pattern=url_pattern(
                "propraetor:company_details", company_id="company.id"
            ),
            width="company-col",
        ),
        TableColumn(
            "department",
            "DEPT",
            "assigned_to.department.name",
            sort_field="assigned_to__department__name",
            link_pattern=url_pattern(
                "propraetor:department_details", department_id="assigned_to.department.id"
            ),
            width="department-col",
        ),
        TableColumn(
            "location",
            "LOCATION",
            "location_resolved",
            sort_field="location__resolved",
            link_pattern=url_pattern("propraetor:location_details", location_id="location.id"),
            width="location-col",
        ),
        TableColumn(
            "status",
            "STATUS",
            "status",
            badge=True,
            badge_map={
                "active": "status-active",
                "pending": "status-pending",
                "inactive": "status-inactive",
                "in_repair": "status-in-repair",
                "retired": "status-retired",
                "disposed": "status-disposed",
            },
            width="status-badge-col",
            align="center"
        ),
        TableColumn(
            "updated_at",
            "LAST UPDATE",
            "updated_at",
            sort_field="updated_at",
            default_visible=False,
            width="datetime-col",
        ),
    ]

    bulk_actions = [
        BulkAction(
            "unassign",
            "UNASSIGN",
            reverse("propraetor:assets_bulk_unassign"),
            confirmation="UNASSIGN SELECTED ASSETS?",
        ),
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:assets_bulk_delete"),
            confirmation="DELETE SELECTED ASSETS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=Asset.objects.select_related("assigned_to", "assigned_to__department", "location", "asset_model", "asset_model__category", "company"),
        columns=columns,
        table_id="assets-table",
        search_fields=[
            "asset_tag",
            "asset_model__category__name",
            "asset_model__model_name",
            "asset_model__manufacturer",
            "asset_model__model_number",
            "assigned_to__name",
            "serial_number",
            "location__name",
            "status",
        ],
        filter_fields={"status": "status"},
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Assets"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    # Standard requests: optimize with single aggregate query
    asset_stats = Asset.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        in_repair=Count("id", filter=Q(status="in_repair")),
        assigned=Count("id", filter=Q(assigned_to_id__isnull=False)),
    )

    total_assets = asset_stats["total"]
    active_assets = asset_stats["active"]
    active_percentage = (
        f"{(active_assets / total_assets * 100):.2f}" if total_assets > 0 else 0
    )

    context.update(
        {
            "total_assets": total_assets,
            "active_assets": active_assets,
            "active_percentage": active_percentage,
            "in_repair": asset_stats["in_repair"],
            "assigned_assets": asset_stats["assigned"],
            "base_template": get_base_template(request),
        }
    )

    return render(request, "assets/assets_list.html", context)


def asset_create(request):
    """Create a new asset."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save()
            messages.success(
                request, f"Asset '{asset.asset_tag}' created successfully."
            )
            return htmx_redirect(request, "propraetor:asset_details", asset_id=asset.id)
    else:
        form = AssetForm()

    context = {
        "form": form,
        "base_template": base_template,
    }
    return render(request, "assets/asset_create.html", context)


def asset_edit(request, asset_id):
    """Edit an existing asset."""
    base_template = get_base_template(request)
    asset = get_object_or_404(Asset, pk=asset_id)

    if request.method == "POST":
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Asset '{asset.asset_tag}' updated successfully."
            )
            return htmx_redirect(request, "propraetor:asset_details", asset_id=asset.id)
    else:
        form = AssetForm(instance=asset)

    context = {
        "form": form,
        "object": asset,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "assets/asset_create.html", context)


def get_asset_context(asset, base_template):
    """Build context dictionary for asset detail views."""
    assignment_history = AssetAssignment.objects.filter(asset_id=asset.id)
    maintenance_records = MaintenanceRecord.objects.filter(asset_id=asset.id)
    installed_components = asset.components.filter(status="installed").select_related(
        "component_type"
    )

    return {
        "asset": asset,
        "assignment_history": assignment_history,
        "maintenance_records": maintenance_records,
        "installed_components": installed_components,
        "base_template": base_template,
    }


def asset_details_ht(request, asset_tag):
    """Asset Page — publicly accessible via /ht/<asset_tag>/"""
    asset = get_object_or_404(Asset, asset_tag=asset_tag)
    base_template = get_base_template(request)
    context = get_asset_context(asset, base_template)
    return render(request, "assets/asset_details.html", context)


def asset_details(request, asset_id):
    """Asset Page"""
    asset = get_object_or_404(Asset, pk=asset_id)
    base_template = get_base_template(request)
    context = get_asset_context(asset, base_template)
    return render(request, "assets/asset_details.html", context)


@require_http_methods(["DELETE"])
def asset_delete(request, asset_id):
    """Delete an asset."""
    asset = get_object_or_404(Asset, pk=asset_id)
    tag = asset.asset_tag
    asset.delete()
    messages.success(request, f"Asset '{tag}' deleted successfully.")
    return htmx_redirect(request, "propraetor:assets_list")


@require_POST
def asset_unassign(request, asset_id):
    """Unassign an asset from its current assignee."""
    asset = get_object_or_404(Asset, pk=asset_id)
    if asset.assigned_to:
        # Record assignment history
        AssetAssignment.objects.filter(
            asset=asset, user=asset.assigned_to, returned_date__isnull=True
        ).update(returned_date=timezone.now())
        assignee_name = str(asset.assigned_to)
        with suppress_auto_log():
            asset.assigned_to = None
            asset.save(update_fields=["assigned_to", "updated_at"])
        log_activity(
            event_type="asset",
            action="unassigned",
            message=f"Asset {asset.asset_tag} unassigned from {assignee_name}",
            detail=assignee_name,
            instance=asset,
        )
        messages.success(
            request, f"Asset '{asset.asset_tag}' unassigned from {assignee_name}."
        )
    else:
        messages.info(request, f"Asset '{asset.asset_tag}' is not currently assigned.")
    return htmx_redirect(request, "propraetor:asset_details", asset_id=asset.id)


@require_POST
def asset_change_status(request, asset_id):
    """Change the status of an asset."""
    asset = get_object_or_404(Asset, pk=asset_id)
    new_status = request.POST.get("status")
    valid_statuses = [s[0] for s in Asset.STATUS_CHOICES]
    if new_status in valid_statuses:
        old_status = asset.status
        with suppress_auto_log():
            asset.status = new_status
            asset.save(update_fields=["status", "updated_at"])
        log_activity(
            event_type="asset",
            action="status_changed",
            message=f"Asset {asset.asset_tag} status changed to {new_status}",
            detail=asset.get_status_display(),
            instance=asset,
            changes={"status": [old_status, new_status]},
        )
        messages.success(
            request, f"Asset '{asset.asset_tag}' status changed to '{new_status}'."
        )
    else:
        messages.error(request, f"Invalid status: '{new_status}'.")
    return htmx_redirect(request, "propraetor:asset_details", asset_id=asset.id)


@require_POST
def asset_duplicate(request, asset_id):
    """Duplicate an asset with a new asset tag."""
    source = get_object_or_404(Asset, pk=asset_id)
    duplicate = Asset(
        company=source.company,
        asset_tag=f"{source.asset_tag}-COPY",
        asset_model=source.asset_model,
        serial_number="",
        attributes=source.attributes,
        purchase_date=source.purchase_date,
        purchase_cost=source.purchase_cost,
        warranty_expiry_date=source.warranty_expiry_date,
        status="pending",
        location=source.location,
        assigned_to=None,
        requisition=source.requisition,
        invoice=source.invoice,
        notes=source.notes,
    )
    with suppress_auto_log():
        duplicate.save()
    log_activity(
        event_type="asset",
        action="duplicated",
        message=f"Asset {duplicate.asset_tag} duplicated from {source.asset_tag}",
        detail=duplicate.get_status_display(),
        instance=duplicate,
    )
    messages.success(request, f"Asset duplicated as '{duplicate.asset_tag}'.")
    return htmx_redirect(request, "propraetor:asset_details", asset_id=duplicate.id)


@require_POST
def assets_bulk_unassign(request):
    """Bulk unassign selected assets."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        assets = Asset.objects.filter(pk__in=selected_ids, assigned_to__isnull=False)
        count = 0
        with suppress_auto_log():
            for asset in assets:
                AssetAssignment.objects.filter(
                    asset=asset, user=asset.assigned_to, returned_date__isnull=True
                ).update(returned_date=timezone.now())
                asset.assigned_to = None
                asset.save(update_fields=["assigned_to", "updated_at"])
                count += 1
        if count:
            log_activity(
                event_type="asset",
                action="unassigned",
                message=f"{count} asset(s) bulk unassigned",
            )
        messages.success(request, f"{count} asset(s) unassigned.")
    else:
        messages.warning(request, "No assets selected.")
    return htmx_redirect(request, "propraetor:assets_list")


@require_POST
def assets_bulk_delete(request):
    """Bulk delete selected assets."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = Asset.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} asset(s) deleted.")
    else:
        messages.warning(request, "No assets selected.")
    return htmx_redirect(request, "propraetor:assets_list")


@require_POST
def assets_bulk_status(request):
    """Bulk change status of selected assets."""
    selected_ids = request.POST.getlist("selected_ids")
    new_status = request.POST.get("status", "")
    valid_statuses = [s[0] for s in Asset.STATUS_CHOICES]
    if selected_ids and new_status in valid_statuses:
        count = Asset.objects.filter(pk__in=selected_ids).update(status=new_status)
        log_activity(
            event_type="asset",
            action="bulk_status",
            message=f"{count} asset(s) bulk status changed to {new_status}",
            detail=new_status,
        )
        messages.success(request, f"{count} asset(s) changed to '{new_status}'.")
    else:
        messages.warning(request, "No assets selected or invalid status.")
    return htmx_redirect(request, "propraetor:assets_list")


@require_http_methods(["GET", "POST"])
def asset_transfer_location(request, asset_id):
    """Transfer an asset to a different location (modal form)."""
    asset = get_object_or_404(Asset, pk=asset_id)

    if request.method == "POST":
        form = AssetTransferLocationForm(request.POST, instance=asset)
        new_location = form.data.get("location") or None

        # Resolve new location object for messaging
        new_loc_obj = None
        if new_location:
            new_loc_obj = Location.objects.filter(pk=new_location).first()

        old_location = asset.location
        old_location_name = str(old_location) if old_location else "none"
        new_location_name = str(new_loc_obj) if new_loc_obj else "none"

        # If the asset is assigned to a user, we must unassign first
        # (model constraint: cannot have both assigned_to and location set)
        unassigned_from = None
        if new_loc_obj and asset.assigned_to:
            unassigned_from = str(asset.assigned_to)
            AssetAssignment.objects.filter(
                asset=asset, user=asset.assigned_to, returned_date__isnull=True
            ).update(returned_date=timezone.now())
            asset.assigned_to = None

        # Apply the location change
        with suppress_auto_log():
            asset.location = new_loc_obj
            asset.save(update_fields=["location", "assigned_to", "updated_at"])

        # Log activity
        detail_parts = [f"{old_location_name} -> {new_location_name}"]
        if unassigned_from:
            detail_parts.append(f"unassigned from {unassigned_from}")
        log_activity(
            event_type="asset",
            action="transferred",
            message=f"Asset {asset.asset_tag} transferred to {new_location_name}",
            detail="; ".join(detail_parts),
            instance=asset,
            changes={"location": [old_location_name, new_location_name]},
        )

        msg = f"Asset '{asset.asset_tag}' transferred to {new_location_name}."
        if unassigned_from:
            msg += f" (unassigned from {unassigned_from})"
        messages.success(request, msg)
        return htmx_redirect(request, "propraetor:asset_details", asset_id=asset.id)

    else:
        form = AssetTransferLocationForm(instance=asset)

    context = {
        "form": form,
        "asset": asset,
    }
    return render(request, "assets/asset_transfer_location.html", context)


# ============================================================================
