"""Component views."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import ComponentForm
from ..models import Asset, Component
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# COMPONENTS
# ============================================================================


def components_list(request):
    columns = [
        TableColumn(
            "component_tag",
            "TAG",
            "component_tag",
            sort_field="component_tag",
            link_pattern=url_pattern("propraetor:component_details", component_id="id"),
            width="tag-col",
        ),
        TableColumn("component_type", "TYPE", "component_type", width="type-col"),
        TableColumn("manufacturer", "MFG", "manufacturer", width="manufacturer-col"),
        TableColumn("model", "MODEL", "model", width="model-col"),
        TableColumn("serial_number", "SERIAL", "serial_number", width="serial-col"),
        TableColumn(
            "parent_asset__asset_tag",
            "PARENT",
            "parent_asset.asset_tag",
            sort_field="parent_asset__asset_tag",
            width="tag-col",
        ),
        TableColumn(
            "parent_asset__assigned_to",
            "ASSIGNED_TO",
            "parent_asset.assigned_to",
            sort_field="parent_asset__assigned_to__name",
            width="name-col",
        ),
        TableColumn(
            "status",
            "Status",
            "status",
            badge=True,
            badge_map={
                "installed": "status-active",
                "spare": "status-pending",
                "failed": "status-in-repair",
                "removed": "status-inactive",
                "disposed": "status-disposed",
            },
            width="status-badge-col",
        ),
        TableColumn("invoice__id", "Invoice", "invoice__id", width="id-col", default_visible=False),
        TableColumn("requisition__id", "Requisition", "requisition__id", width="id-col", default_visible=False),
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
            reverse("propraetor:components_bulk_unassign"),
            confirmation="UNASSIGN SELECTED COMPONENTS?",
        ),
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:components_bulk_delete"),
            confirmation="DELETE SELECTED COMPONENTS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=Component.objects.select_related("component_type", "parent_asset", "parent_asset__assigned_to"),
        columns=columns,
        table_id="components-table",
        search_fields=[
            "component_tag",
            "component_type__type_name",
            "serial_number",
            "manufacturer",
            "model",
            "parent_asset__asset_tag",
            "parent_asset__assigned_to__name",
            "parent_asset__assigned_to__employee_id",
            "status",
            "requisition__id",
            "invoice__invoice_number",
        ],
        filter_fields={"status": "status"},
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Components"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    total_components = Component.objects.count()
    spare_components = Component.objects.filter(status="spare").count()
    failed_components = Component.objects.filter(status="failed").count()

    context.update(
        {
            "total_components": total_components,
            "spare_components": spare_components,
            "failed_components": failed_components,
            "base_template": get_base_template(request),
        }
    )

    return render(request, "components/components_list.html", context)


def component_create(request):
    """Create a new component."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = ComponentForm(request.POST)
        if form.is_valid():
            component = form.save()
            messages.success(request, f"Component '{component}' created successfully.")
            return htmx_redirect(
                request, "propraetor:component_details", component_id=component.id
            )
    else:
        form = ComponentForm()

    context = {
        "form": form,
        "base_template": base_template,
    }
    return render(request, "components/component_create.html", context)


def component_edit(request, component_id):
    """Edit an existing component."""
    base_template = get_base_template(request)
    component = get_object_or_404(Component, pk=component_id)

    if request.method == "POST":
        form = ComponentForm(request.POST, instance=component)
        if form.is_valid():
            form.save()
            messages.success(request, f"Component '{component}' updated successfully.")
            return htmx_redirect(
                request, "propraetor:component_details", component_id=component.id
            )
    else:
        form = ComponentForm(instance=component)

    context = {
        "form": form,
        "object": component,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "components/component_create.html", context)


def component_details(request, component_id):
    """Component detail page."""
    base_template = get_base_template(request)
    component = get_object_or_404(
        Component.objects.select_related(
            "parent_asset", "component_type", "requisition", "invoice"
        ),
        pk=component_id,
    )
    available_assets = Asset.objects.select_related(
        "asset_model", "asset_model__category", "company", "location", "assigned_to"
    ).order_by("asset_tag")

    # Build asset data for the searchable dropdown (json_script will serialize it)
    assets_json = [
        {
            "id": asset.id,
            "asset_tag": asset.asset_tag,
            "model": str(asset.asset_model) if asset.asset_model else "",
            "serial_number": asset.serial_number or "",
            "company": str(asset.company) if asset.company else "",
            "category": (
                str(asset.asset_model.category)
                if asset.asset_model and asset.asset_model.category
                else ""
            ),
            "location": str(asset.location) if asset.location else "",
            "assigned_to": str(asset.assigned_to) if asset.assigned_to else "",
            "status": asset.get_status_display(),
        }
        for asset in available_assets
    ]

    context = {
        "component": component,
        "available_assets": available_assets,
        "assets_json": assets_json,
        "base_template": base_template,
    }
    return render(request, "components/component_details.html", context)


@require_http_methods(["DELETE"])
def component_delete(request, component_id):
    """Delete a component."""
    component = get_object_or_404(Component, pk=component_id)
    component.delete()
    messages.success(request, "Component deleted successfully.")
    return htmx_redirect(request, "propraetor:components_list")


@require_POST
def component_unassign(request, component_id):
    """Unassign a component from its parent asset."""
    component = get_object_or_404(Component, pk=component_id)
    if component.parent_asset:
        parent_tag = component.parent_asset.asset_tag
        with suppress_auto_log():
            component.parent_asset = None
            component.status = "spare"
            component.removal_date = timezone.now().date()
            component.save(
                update_fields=[
                    "parent_asset",
                    "status",
                    "removal_date",
                    "updated_at",
                ]
            )
        log_activity(
            event_type="component",
            action="unassigned",
            message=f"Component {component.component_tag} unassigned from asset {parent_tag}",
            detail=parent_tag,
            instance=component,
        )
        messages.success(request, f"Component unassigned from asset '{parent_tag}'.")
    else:
        messages.info(request, "Component is not assigned to any asset.")
    return htmx_redirect(
        request, "propraetor:component_details", component_id=component.id
    )


@require_POST
def component_change_status(request, component_id):
    """Change the status of a component."""
    component = get_object_or_404(Component, pk=component_id)
    new_status = request.POST.get("status")
    valid_statuses = [s[0] for s in Component.STATUS_CHOICES]
    if new_status in valid_statuses:
        if new_status == "installed":
            parent_asset_id = request.POST.get("parent_asset")
            if not parent_asset_id:
                messages.error(
                    request,
                    "A component cannot be marked as installed without being assigned to a parent asset.",
                )
                return htmx_redirect(
                    request,
                    "propraetor:component_details",
                    component_id=component.id,
                )
            try:
                parent_asset = Asset.objects.get(pk=parent_asset_id)
            except Asset.DoesNotExist:
                messages.error(request, "The selected asset does not exist.")
                return htmx_redirect(
                    request,
                    "propraetor:component_details",
                    component_id=component.id,
                )
            old_status = component.status
            with suppress_auto_log():
                component.parent_asset = parent_asset
                component.status = "installed"
                component.installation_date = timezone.now().date()
                component.removal_date = None
                component.save(
                    update_fields=[
                        "parent_asset",
                        "status",
                        "installation_date",
                        "removal_date",
                        "updated_at",
                    ]
                )
            log_activity(
                event_type="component",
                action="assigned",
                message=f"Component {component.component_tag} installed in asset {parent_asset.asset_tag}",
                detail=parent_asset.asset_tag,
                instance=component,
                changes={
                    "status": [old_status, "installed"],
                    "parent_asset": [None, str(parent_asset)],
                },
            )
            messages.success(
                request,
                f"Component marked as installed in asset '{parent_asset.asset_tag}'.",
            )
        else:
            old_status = component.status
            with suppress_auto_log():
                component.status = new_status
                component.save(update_fields=["status", "updated_at"])
            log_activity(
                event_type="component",
                action="status_changed",
                message=f"Component {component.component_tag} status changed to {new_status}",
                detail=component.get_status_display(),
                instance=component,
                changes={"status": [old_status, new_status]},
            )
            messages.success(request, f"Component status changed to '{new_status}'.")
    else:
        messages.error(request, f"Invalid status: '{new_status}'.")
    return htmx_redirect(
        request, "propraetor:component_details", component_id=component.id
    )


@require_POST
def components_bulk_unassign(request):
    """Bulk unassign selected components from parent assets."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        today = timezone.now().date()
        count = Component.objects.filter(
            pk__in=selected_ids, parent_asset__isnull=False
        ).update(parent_asset=None, status="spare", removal_date=today)
        if count:
            log_activity(
                event_type="component",
                action="unassigned",
                message=f"{count} component(s) bulk unassigned",
            )
        messages.success(request, f"{count} component(s) unassigned.")
    else:
        messages.warning(request, "No components selected.")
    return htmx_redirect(request, "propraetor:components_list")


@require_POST
def components_bulk_delete(request):
    """Bulk delete selected components."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = Component.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} component(s) deleted.")
    else:
        messages.warning(request, "No components selected.")
    return htmx_redirect(request, "propraetor:components_list")
