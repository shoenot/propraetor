"""Company views."""

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import CompanyForm
from ..models import Company
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# COMPANIES
# ============================================================================


def companies_list(request):
    queryset = Company.objects.annotate(
        total_employees=Count("employees", distinct=True),
        total_assets=Count("assets", distinct=True),
        total_departments=Count("departments", distinct=True),
    )
    columns = [
        TableColumn(
            "name",
            "NAME",
            "name",
            link_pattern=url_pattern("propraetor:company_details", company_id="id"),
            width="name-col",
        ),
        TableColumn("code", "CODE", "code", width="code-col"),
        TableColumn("city", "CITY", "city", width="city-col"),
        TableColumn("country", "COUNTRY", "country", width="country-col"),
        TableColumn("phone", "PHONE", "phone", sortable=False, default_visible=False,
                     width="phone-col"),
        TableColumn(
            "is_active",
            "STATUS",
            "is_active",
            badge=True,
            badge_map={"True": "status-active", "False": "status-inactive"},
            width="status-badge-col",
        ),
        TableColumn("departments", "DEPTS", "total_departments", width="count-col"),
        TableColumn("employees", "EMPLOYEES", "total_employees", width="count-col"),
        TableColumn("assets", "ASSETS", "total_assets", width="count-col"),
    ]

    bulk_actions = [
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:companies_bulk_delete"),
            confirmation="DELETE SELECTED COMPANIES? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=queryset,
        columns=columns,
        table_id="companies-table",
        search_fields=["name", "code", "city", "country"],
        filter_fields={"status": lambda qs, v: qs.filter(is_active=(v == "active"))},
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Companies"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    context.update({"base_template": get_base_template(request)})
    return render(request, "companies/companies_list.html", context)


def company_create(request):
    """Create a new company."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save()
            messages.success(request, f"Company '{company.name}' created successfully.")
            return htmx_redirect(
                request, "propraetor:company_details", company_id=company.id
            )
    else:
        form = CompanyForm()

    context = {"form": form, "base_template": base_template}
    return render(request, "companies/company_create.html", context)


def company_edit(request, company_id):
    """Edit an existing company."""
    base_template = get_base_template(request)
    company = get_object_or_404(Company, pk=company_id)

    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, f"Company '{company.name}' updated successfully.")
            return htmx_redirect(
                request, "propraetor:company_details", company_id=company.id
            )
    else:
        form = CompanyForm(instance=company)

    context = {
        "form": form,
        "object": company,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "companies/company_create.html", context)


def company_details(request, company_id):
    """Company detail page."""
    base_template = get_base_template(request)
    company = get_object_or_404(
        Company.objects.prefetch_related(
            "departments", "employees", "assets", "purchase_invoices", "requisitions"
        ),
        pk=company_id,
    )
    context = {"company": company, "base_template": base_template}
    return render(request, "companies/company_details.html", context)


@require_http_methods(["DELETE"])
def company_delete(request, company_id):
    """Delete a company."""
    company = get_object_or_404(Company, pk=company_id)
    name = company.name
    company.delete()
    messages.success(request, f"Company '{name}' deleted successfully.")
    return htmx_redirect(request, "propraetor:companies_list")


@require_POST
def companies_bulk_delete(request):
    """Bulk delete selected companies."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = Company.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} company(ies) deleted.")
    else:
        messages.warning(request, "No companies selected.")
    return htmx_redirect(request, "propraetor:companies_list")
