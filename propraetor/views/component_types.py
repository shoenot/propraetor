"""Component type views."""

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import ComponentTypeForm
from ..models import ComponentType
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# COMPONENT TYPES
# ============================================================================


def component_types_list(request):
    queryset = ComponentType.objects.annotate(
        total_components=Count("components", distinct=True),
    )
    columns = [
        TableColumn(
            "type_name",
            "NAME",
            "type_name",
            link_pattern=url_pattern(
                "propraetor:component_type_details", component_type_id="id"
            ),
            width="name-col",
        ),
        TableColumn("total_components", "COMPONENTS", "total_components", width="count-col"),
        TableColumn("created_at", "CREATED", "created_at", sort_field="created_at", width="datetime-col"),
    ]

    bulk_actions = [
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:component_types_bulk_delete"),
            confirmation="DELETE SELECTED COMPONENT TYPES? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=queryset,
        columns=columns,
        table_id="component-types-table",
        search_fields=["type_name"],
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Component Types"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    context.update({"base_template": get_base_template(request)})

    return render(request, "component_types/component_types_list.html", context)


def component_type_create(request):
    """Create a new component type."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = ComponentTypeForm(request.POST)
        if form.is_valid():
            component_type = form.save()
            messages.success(
                request,
                f"Component type '{component_type.type_name}' created successfully.",
            )
            return htmx_redirect(
                request,
                "propraetor:component_type_details",
                component_type_id=component_type.id,
            )
    else:
        form = ComponentTypeForm()

    context = {
        "form": form,
        "base_template": base_template,
    }
    return render(request, "component_types/component_type_create.html", context)


def component_type_edit(request, component_type_id):
    """Edit an existing component type."""
    base_template = get_base_template(request)
    component_type = get_object_or_404(ComponentType, pk=component_type_id)

    if request.method == "POST":
        form = ComponentTypeForm(request.POST, instance=component_type)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Component type '{component_type.type_name}' updated successfully.",
            )
            return htmx_redirect(
                request,
                "propraetor:component_type_details",
                component_type_id=component_type.id,
            )
    else:
        form = ComponentTypeForm(instance=component_type)

    context = {
        "form": form,
        "object": component_type,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "component_types/component_type_create.html", context)


def component_type_details(request, component_type_id):
    """Component type detail page."""
    base_template = get_base_template(request)
    component_type = get_object_or_404(
        ComponentType.objects.prefetch_related("components"),
        pk=component_type_id,
    )
    components_of_type = component_type.components.select_related(
        "parent_asset"
    ).order_by("-created_at")[:10]
    components_count = component_type.components.count()
    context = {
        "component_type": component_type,
        "components_of_type": components_of_type,
        "components_count": components_count,
        "base_template": base_template,
    }
    return render(request, "component_types/component_type_details.html", context)


@require_http_methods(["DELETE"])
def component_type_delete(request, component_type_id):
    """Delete a component type."""
    component_type = get_object_or_404(ComponentType, pk=component_type_id)
    name = component_type.type_name
    component_type.delete()
    messages.success(request, f"Component type '{name}' deleted successfully.")
    return htmx_redirect(request, "propraetor:component_types_list")


@require_POST
def component_types_bulk_delete(request):
    """Bulk delete selected component types."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = ComponentType.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} component type(s) deleted.")
    else:
        messages.warning(request, "No component types selected.")
    return htmx_redirect(request, "propraetor:component_types_list")
