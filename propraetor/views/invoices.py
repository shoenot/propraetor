"""Invoice views."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import PurchaseInvoiceForm
from ..models import Asset, Component, InvoiceLineItem, PurchaseInvoice
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# INVOICES
# ============================================================================


def invoices_list(request):
    columns = [
        TableColumn(
            "invoice_number",
            "INV_#",
            "invoice_number",
            link_pattern=url_pattern("propraetor:invoice_details", invoice_id="id"),
            width="invoice-num-col",
        ),
        TableColumn(
            "vendor",
            "VENDOR",
            "vendor.vendor_name",
            sort_field="vendor__vendor_name",
            width="name-col",
        ),
        TableColumn(
            "company",
            "CMPNY",
            "company.code",
            sort_field="company__code",
            width="company-col",
        ),
        TableColumn("invoice_date", "INV_DATE", "invoice_date", width="date-col"),
        TableColumn("total_amount", "TOTAL", "total_amount", width="money-col"),
        TableColumn(
            "payment_status",
            "PAYMENT",
            "payment_status",
            badge=True,
            badge_map={
                "unpaid": "status-pending",
                "partially_paid": "status-active",
                "paid": "status-active",
            },
            width="payment-col",
        ),
        TableColumn("payment_date", "PAID_DATE", "payment_date", width="date-col"),
    ]

    bulk_actions = [
        BulkAction(
            "mark_paid",
            "MARK PAID",
            reverse("propraetor:invoices_bulk_mark_paid"),
            confirmation="MARK SELECTED INVOICES AS PAID?",
        ),
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:invoices_bulk_delete"),
            confirmation="DELETE SELECTED INVOICES? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=PurchaseInvoice.objects.select_related("company", "vendor"),
        columns=columns,
        table_id="invoices-table",
        search_fields=[
            "invoice_number",
            "company__name",
            "company__code",
            "vendor__vendor_name",
            "payment_status",
        ],
        filter_fields={"payment_status": "payment_status"},
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Invoices"

    is_table_update = any(
        k in request.GET
        for k in ["q", "sort", "page", "payment_status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    total_invoices = PurchaseInvoice.objects.count()
    paid_invoices = PurchaseInvoice.objects.filter(payment_status="paid").count()
    partially_paid_invoices = PurchaseInvoice.objects.filter(
        payment_status="partially_paid"
    ).count()
    unpaid_invoices = PurchaseInvoice.objects.filter(payment_status="unpaid").count()

    context.update(
        {
            "base_template": get_base_template(request),
            "total_invoices": total_invoices,
            "paid_invoices": paid_invoices,
            "partially_paid_invoices": partially_paid_invoices,
            "unpaid_invoices": unpaid_invoices,
        }
    )

    return render(request, "invoices/invoices_list.html", context)


def invoice_create(request):
    """Create a new purchase invoice."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = PurchaseInvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save()
            messages.success(
                request,
                f"Invoice '{invoice.invoice_number}' created successfully.",
            )
            return htmx_redirect(
                request, "propraetor:invoice_details", invoice_id=invoice.id
            )
    else:
        form = PurchaseInvoiceForm()

    context = {
        "form": form,
        "base_template": base_template,
    }
    return render(request, "invoices/invoice_create.html", context)


def invoice_edit(request, invoice_id):
    """Edit an existing purchase invoice."""
    base_template = get_base_template(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=invoice_id)

    if request.method == "POST":
        form = PurchaseInvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Invoice '{invoice.invoice_number}' updated successfully.",
            )
            return htmx_redirect(
                request, "propraetor:invoice_details", invoice_id=invoice.id
            )
    else:
        form = PurchaseInvoiceForm(instance=invoice)

    context = {
        "form": form,
        "object": invoice,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "invoices/invoice_create.html", context)


def invoice_details(request, invoice_id):
    """Invoice Details Page."""
    base_template = get_base_template(request)

    invoice = get_object_or_404(
        PurchaseInvoice.objects.select_related("company", "vendor").prefetch_related(
            "line_items",
            "line_items__asset_model",
            "line_items__component_type",
        ),
        pk=invoice_id,
    )

    # Assets and components that were received (created) from this invoice
    received_assets = Asset.objects.filter(
        invoice=invoice,
        invoice_line_item__isnull=False,
    ).select_related("asset_model", "invoice_line_item")

    received_components = Component.objects.filter(
        invoice=invoice,
        invoice_line_item__isnull=False,
    ).select_related("component_type", "invoice_line_item")

    context = {
        "invoice": invoice,
        "base_template": base_template,
        "received_assets": received_assets,
        "received_components": received_components,
    }

    return render(request, "invoices/invoice_details.html", context)


@require_http_methods(["DELETE"])
def invoice_delete(request, invoice_id):
    """Delete an invoice."""
    invoice = get_object_or_404(PurchaseInvoice, pk=invoice_id)
    number = invoice.invoice_number
    invoice.delete()
    messages.success(request, f"Invoice '{number}' deleted successfully.")
    return htmx_redirect(request, "propraetor:invoices_list")


@require_POST
def invoices_bulk_delete(request):
    """Bulk delete selected invoices."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = PurchaseInvoice.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} invoice(s) deleted.")
    else:
        messages.warning(request, "No invoices selected.")
    return htmx_redirect(request, "propraetor:invoices_list")


@require_POST
def invoices_bulk_mark_paid(request):
    """Bulk mark selected invoices as paid."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        today = timezone.now().date()
        count = (
            PurchaseInvoice.objects.filter(pk__in=selected_ids)
            .exclude(payment_status="paid")
            .update(payment_status="paid", payment_date=today)
        )
        if count:
            log_activity(
                event_type="invoice",
                action="paid",
                message=f"{count} invoice(s) bulk marked as paid",
                detail="Paid",
            )
        messages.success(request, f"{count} invoice(s) marked as paid.")
    else:
        messages.warning(request, "No invoices selected.")
    return htmx_redirect(request, "propraetor:invoices_list")


def invoice_mark_paid(request, invoice_id):
    """Mark a purchase invoice as paid.

    Intended to be called via HTMX from the invoice details page.
    """
    invoice = get_object_or_404(PurchaseInvoice, pk=invoice_id)

    if request.method == "POST":
        old_status = invoice.payment_status
        with suppress_auto_log():
            invoice.payment_status = "paid"
            if not invoice.payment_date:
                invoice.payment_date = timezone.now().date()
            invoice.save(update_fields=["payment_status", "payment_date", "updated_at"])
        log_activity(
            event_type="invoice",
            action="paid",
            message=f"Invoice {invoice.invoice_number} marked as paid",
            detail="Paid",
            instance=invoice,
            changes={"payment_status": [old_status, "paid"]},
        )

    return htmx_redirect(request, "propraetor:invoice_details", invoice_id=invoice.id)


def invoice_duplicate(request, invoice_id):
    """Create a duplicate of a purchase invoice (without reusing the same invoice_number).

    Intended to be called via HTMX from the invoice details page.
    """
    source = get_object_or_404(
        PurchaseInvoice.objects.prefetch_related("line_items"), pk=invoice_id
    )

    # Create a copy of the invoice (without primary key and invoice_number)
    duplicate = PurchaseInvoice(
        company=source.company,
        vendor=source.vendor,
        invoice_date=source.invoice_date,
        total_amount=source.total_amount,
        payment_status="unpaid",
        payment_date=None,
        payment_method=source.payment_method,
        payment_reference="",
        received_by=source.received_by,
        received_date=source.received_date,
        notes=source.notes,
    )
    duplicate.invoice_number = f"{source.invoice_number}-COPY"
    with suppress_auto_log():
        duplicate.save()

    # Duplicate line items
    with suppress_auto_log():
        for item in source.line_items.all():
            InvoiceLineItem.objects.create(
                invoice=duplicate,
                line_number=item.line_number,
                company=item.company,
                department=item.department,
                item_type=item.item_type,
                description=item.description,
                quantity=item.quantity,
                item_cost=item.item_cost,
                asset_model=item.asset_model,
                component_type=item.component_type,
                notes=item.notes,
            )

    log_activity(
        event_type="invoice",
        action="duplicated",
        message=f"Invoice {duplicate.invoice_number} duplicated from {source.invoice_number}",
        detail=duplicate.get_payment_status_display(),
        instance=duplicate,
    )

    return htmx_redirect(request, "propraetor:invoice_details", invoice_id=duplicate.id)
