"""Location views."""

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import LocationForm
from ..models import Location
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# LOCATIONS
# ============================================================================


def locations_list(request):
    queryset = (
        Location.objects.all()
        .annotate(
            total_employees=Count("employees", distinct=True),
            total_assets=Count("assets", distinct=True),
        )
        .prefetch_related("employees", "assets")
    )
    columns = [
        TableColumn(
            "name",
            "NAME",
            "name",
            link_pattern=url_pattern("propraetor:location_details", location_id="id"),
            width="name-col",
        ),
        TableColumn("address", "ADDRESS", "address", sortable=False, width="address-col"),
        TableColumn("city", "CITY", "city", width="city-col"),
        TableColumn("zipcode", "ZIP", "zipcode", sortable=False, width="zipcode-col"),
        TableColumn("users", "USERS", "total_employees", width="count-col"),
        TableColumn("assets", "ASSETS", "total_assets", width="count-col"),
    ]

    bulk_actions = [
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:locations_bulk_delete"),
            confirmation="DELETE SELECTED LOCATIONS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=queryset,
        columns=columns,
        table_id="locations-table",
        search_fields=["name", "address", "city"],
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Locations"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    context.update({"base_template": get_base_template(request)})

    return render(request, "locations/locations_list.html", context)


def location_create(request):
    """Create a new location."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save()
            messages.success(
                request, f"Location '{location.name}' created successfully."
            )
            return htmx_redirect(request, "propraetor:location_details", location_id=location.id)
    else:
        form = LocationForm()

    context = {
        "form": form,
        "base_template": base_template,
    }
    return render(request, "locations/location_create.html", context)


def location_edit(request, location_id):
    """Edit an existing location."""
    base_template = get_base_template(request)
    location = get_object_or_404(Location, pk=location_id)

    if request.method == "POST":
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Location '{location.name}' updated successfully."
            )
            return htmx_redirect(request, "propraetor:location_details", location_id=location.id)
    else:
        form = LocationForm(instance=location)

    context = {
        "form": form,
        "object": location,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "locations/location_create.html", context)


def location_details(request, location_id):
    """Location detail page"""
    base_template = get_base_template(request)
    location = get_object_or_404(
        Location.objects.prefetch_related(
            "assets", "employees", "default_for_departments", "spare_parts"
        ),
        pk=location_id,
    )

    context = {"location": location, "base_template": base_template}

    return render(request, "locations/location_details.html", context)


@require_http_methods(["DELETE"])
def location_delete(request, location_id):
    """Delete a location."""
    location = get_object_or_404(Location, pk=location_id)
    name = location.name
    location.delete()
    messages.success(request, f"Location '{name}' deleted successfully.")
    return htmx_redirect(request, "propraetor:locations_list")


@require_POST
def locations_bulk_delete(request):
    """Bulk delete selected locations."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = Location.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} location(s) deleted.")
    else:
        messages.warning(request, "No locations selected.")
    return htmx_redirect(request, "propraetor:locations_list")
