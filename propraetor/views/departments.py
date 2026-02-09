"""Department views."""

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import DepartmentForm
from ..models import Department
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# DEPARTMENTS
# ============================================================================


def departments_list(request):
    queryset = Department.objects.annotate(
        total_employees=Count("employees", distinct=True),
        total_assets=Count("employees__assigned_assets", distinct=True),
    ).prefetch_related("company")
    columns = [
        TableColumn(
            "name",
            "NAME",
            "name",
            link_pattern=url_pattern(
                "propraetor:department_details", department_id="id"
            ),
            width="name-col",
        ),
        TableColumn("company", "COMPANY", "company", sortable=False, width="company-col"),
        TableColumn("default_location", "LOCATION", "default_location__name", width="location-col"),
        TableColumn("users", "USERS", "total_employees", width="count-col"),
        TableColumn("assets", "ASSETS", "total_assets", width="count-col"),
    ]

    bulk_actions = [
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:departments_bulk_delete"),
            confirmation="DELETE SELECTED DEPARTMENTS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=queryset,
        columns=columns,
        table_id="departments-table",
        search_fields=["name", "company", "default_location__name"],
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Departments"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    context.update({"base_template": get_base_template(request)})

    return render(request, "departments/departments_list.html", context)


def department_create(request):
    """Create a new department."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            messages.success(
                request, f"Department '{department.name}' created successfully."
            )
            return htmx_redirect(
                request, "propraetor:department_details", department_id=department.id
            )
    else:
        form = DepartmentForm()

    context = {
        "form": form,
        "base_template": base_template,
    }
    return render(request, "departments/department_create.html", context)


def department_edit(request, department_id):
    """Edit an existing department."""
    base_template = get_base_template(request)
    department = get_object_or_404(Department, pk=department_id)

    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Department '{department.name}' updated successfully."
            )
            return htmx_redirect(
                request, "propraetor:department_details", department_id=department.id
            )
    else:
        form = DepartmentForm(instance=department)

    context = {
        "form": form,
        "object": department,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "departments/department_create.html", context)


def department_details(request, department_id):
    """Department detail page."""
    base_template = get_base_template(request)
    department = get_object_or_404(
        Department.objects.select_related(
            "company", "default_location"
        ).prefetch_related("employees"),
        pk=department_id,
    )
    context = {
        "department": department,
        "base_template": base_template,
    }
    return render(request, "departments/department_details.html", context)


@require_http_methods(["DELETE"])
def department_delete(request, department_id):
    """Delete a department."""
    department = get_object_or_404(Department, pk=department_id)
    name = department.name
    department.delete()
    messages.success(request, f"Department '{name}' deleted successfully.")
    return htmx_redirect(request, "propraetor:departments_list")


@require_POST
def departments_bulk_delete(request):
    """Bulk delete selected departments."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = Department.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} department(s) deleted.")
    else:
        messages.warning(request, "No departments selected.")
    return htmx_redirect(request, "propraetor:departments_list")
