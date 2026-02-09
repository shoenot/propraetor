"""Vendor views."""

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import VendorForm
from ..models import Vendor
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# VENDORS
# ============================================================================


def vendors_list(request):
    queryset = Vendor.objects.annotate(
        total_invoices=Count("invoices", distinct=True),
    )
    columns = [
        TableColumn(
            "vendor_name",
            "NAME",
            "vendor_name",
            link_pattern=url_pattern("propraetor:vendor_details", vendor_id="id"),
            width="name-col",
        ),
        TableColumn("contact_person", "CONTACT", "contact_person", width="contact-col"),
        TableColumn("email", "EMAIL", "email", width="email-col"),
        TableColumn("phone", "PHONE", "phone", sortable=False, width="phone-col"),
        TableColumn(
            "website", "WEBSITE", "website", sortable=False, default_visible=False,
            width="website-col",
        ),
        TableColumn("invoices", "INVOICES", "total_invoices", width="count-col"),
    ]

    bulk_actions = [
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:vendors_bulk_delete"),
            confirmation="DELETE SELECTED VENDORS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=queryset,
        columns=columns,
        table_id="vendors-table",
        search_fields=["vendor_name", "contact_person", "email", "phone"],
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Vendors"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    context.update({"base_template": get_base_template(request)})
    return render(request, "vendors/vendors_list.html", context)


def vendor_create(request):
    """Create a new vendor."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save()
            messages.success(
                request, f"Vendor '{vendor.vendor_name}' created successfully."
            )
            return htmx_redirect(
                request, "propraetor:vendor_details", vendor_id=vendor.id
            )
    else:
        form = VendorForm()

    context = {"form": form, "base_template": base_template}
    return render(request, "vendors/vendor_create.html", context)


def vendor_edit(request, vendor_id):
    """Edit an existing vendor."""
    base_template = get_base_template(request)
    vendor = get_object_or_404(Vendor, pk=vendor_id)

    if request.method == "POST":
        form = VendorForm(request.POST, instance=vendor)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Vendor '{vendor.vendor_name}' updated successfully."
            )
            return htmx_redirect(
                request, "propraetor:vendor_details", vendor_id=vendor.id
            )
    else:
        form = VendorForm(instance=vendor)

    context = {
        "form": form,
        "object": vendor,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "vendors/vendor_create.html", context)


def vendor_details(request, vendor_id):
    """Vendor detail page."""
    base_template = get_base_template(request)
    vendor = get_object_or_404(
        Vendor.objects.prefetch_related("invoices"),
        pk=vendor_id,
    )
    context = {"vendor": vendor, "base_template": base_template}
    return render(request, "vendors/vendor_details.html", context)


@require_http_methods(["DELETE"])
def vendor_delete(request, vendor_id):
    """Delete a vendor."""
    vendor = get_object_or_404(Vendor, pk=vendor_id)
    name = vendor.vendor_name
    vendor.delete()
    messages.success(request, f"Vendor '{name}' deleted successfully.")
    return htmx_redirect(request, "propraetor:vendors_list")


@require_POST
def vendors_bulk_delete(request):
    """Bulk delete selected vendors."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = Vendor.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} vendor(s) deleted.")
    else:
        messages.warning(request, "No vendors selected.")
    return htmx_redirect(request, "propraetor:vendors_list")
