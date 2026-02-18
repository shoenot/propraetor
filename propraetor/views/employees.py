"""Employee/User views."""

from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import EmployeeForm
from ..models import Asset, Employee
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# USERS
# ============================================================================


def users_list(request):
    columns = [
        TableColumn(
            "name",
            "NAME",
            "name",
            link_pattern=url_pattern("propraetor:user_details", user_id="pk"),
            width="name-col",
        ),
        TableColumn("employee_id", "EMP_ID", "employee_id", width="id-col"),
        TableColumn("phone", "PHONE", "phone", sortable=False, width="phone-col", default_visible=False),
        TableColumn("company", "CMPNY", "company.code", 
                    sort_field="company__code", width="company-col",
                    link_pattern=url_pattern("propraetor:company_details", company_id="company.id")),
        TableColumn("department", "DEPT", "department.name", 
                    sort_field="department__name", width="department-col",
                    link_pattern=url_pattern("propraetor:department_details", department_id="department.id")),
        TableColumn("location", "LOCATION", "location.name", 
                    sort_field="location__name", width="location-col",
                    link_pattern=url_pattern("propraetor:location_details", location_id="location.id")),
        TableColumn("position", "POS", "position", width="position-col"),
        TableColumn(
            "assets_count",
            "ASSETS",
            lambda item: item.assigned_assets.filter(status="active").count(),
            width="count-col",
            align="center"
        ),
        TableColumn(
            "status",
            "STATUS",
            "status",
            badge=True,
            badge_map={"active": "status-active", "inactive": "status-inactive"},
            width="status-badge-col",
            align="center"
        ),
        TableColumn("email", "EMAIL", "email", default_visible=False, width="email-col"),
        TableColumn(
            "updated_at",
            "LAST UPDATE",
            "updated_at",
            sort_field="updated_at",
            default_visible=True,
            width="datetime-col",
        ),
    ]

    bulk_actions = [
        BulkAction(
            "deactivate",
            "DEACTIVATE",
            reverse("propraetor:users_bulk_deactivate"),
            confirmation="DEACTIVATE SELECTED USERS?",
        ),
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:users_bulk_delete"),
            confirmation="DELETE SELECTED USERS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=Employee.objects.select_related("company", "department", "location"),
        columns=columns,
        table_id="users-table",
        search_fields=[
            "name",
            "employee_id",
            "phone",
            "company__name",
            "department__name",
        ],
        filter_fields={"status": "status"},
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Users"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    context.update(
        {
            "total_users": Employee.objects.count(),
            "active_users": Employee.objects.filter(status="active").count(),
            "users_with_assets": Employee.objects.filter(assigned_assets__isnull=False)
            .distinct()
            .count(),
            "base_template": get_base_template(request),
        }
    )

    return render(request, "users/users_list.html", context)


def user_create(request):
    """Create a new employee/user."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f"User '{employee.name}' created successfully.")
            return htmx_redirect(
                request, "propraetor:user_details", user_id=employee.id
            )
    else:
        form = EmployeeForm()

    context = {
        "form": form,
        "base_template": base_template,
    }
    return render(request, "users/user_create.html", context)


def user_edit(request, user_id):
    """Edit an existing employee/user."""
    base_template = get_base_template(request)
    employee = get_object_or_404(Employee, pk=user_id)

    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, f"User '{employee.name}' updated successfully.")
            return htmx_redirect(
                request, "propraetor:user_details", user_id=employee.id
            )
    else:
        form = EmployeeForm(instance=employee)

    context = {
        "form": form,
        "object": employee,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "users/user_create.html", context)


def user_details(request, user_id):
    """Employee detail page."""
    base_template = get_base_template(request)
    user = get_object_or_404(
        Employee.objects.select_related(
            "company", "department", "location"
        ).prefetch_related("assigned_assets", "asset_assignments", "requisitions"),
        pk=user_id,
    )

    context = {"user": user, "today": date.today(), "base_template": base_template}

    return render(request, "users/user_details.html", context)


@require_http_methods(["DELETE"])
def user_delete(request, user_id):
    """Delete a user/employee."""
    user = get_object_or_404(Employee, pk=user_id)
    name = user.name
    user.delete()
    messages.success(request, f"User '{name}' deleted successfully.")
    return htmx_redirect(request, "propraetor:users_list")


@require_POST
def user_activate(request, user_id):
    """Activate a user."""
    user = get_object_or_404(Employee, pk=user_id)
    with suppress_auto_log():
        user.status = "active"
        user.save(update_fields=["status", "updated_at"])
    log_activity(
        event_type="user",
        action="activated",
        message=f"User {user.name} activated",
        detail="Active",
        instance=user,
    )
    messages.success(request, f"User '{user.name}' activated.")
    return htmx_redirect(request, "propraetor:user_details", user_id=user.id)


@require_POST
def user_deactivate(request, user_id):
    """Deactivate a user."""
    user = get_object_or_404(Employee, pk=user_id)
    with suppress_auto_log():
        user.status = "inactive"
        user.save(update_fields=["status", "updated_at"])
    log_activity(
        event_type="user",
        action="deactivated",
        message=f"User {user.name} deactivated",
        detail="Inactive",
        instance=user,
    )
    messages.success(request, f"User '{user.name}' deactivated.")
    return htmx_redirect(request, "propraetor:user_details", user_id=user.id)


@require_POST
def users_bulk_deactivate(request):
    """Bulk deactivate selected users."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count = Employee.objects.filter(pk__in=selected_ids).update(status="inactive")
        log_activity(
            event_type="user",
            action="bulk_status",
            message=f"{count} user(s) bulk deactivated",
            detail="Inactive",
        )
        messages.success(request, f"{count} user(s) deactivated.")
    else:
        messages.warning(request, "No users selected.")
    return htmx_redirect(request, "propraetor:users_list")


@require_POST
def users_bulk_delete(request):
    """Bulk delete selected users."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = Employee.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} user(s) deleted.")
    else:
        messages.warning(request, "No users selected.")
    return htmx_redirect(request, "propraetor:users_list")
