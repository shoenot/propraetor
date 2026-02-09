"""Invoice line items and receiving."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import InvoiceLineItemForm
from ..models import Asset, Component, InvoiceLineItem, PurchaseInvoice, RequisitionItem
from .utils import get_base_template, htmx_redirect

# INVOICE LINE ITEMS  (scoped to an invoice – no standalone list/detail pages)
# ============================================================================


def invoice_line_item_create(request, invoice_id):
    """Create a new line item on a specific invoice."""
    base_template = get_base_template(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=invoice_id)

    if request.method == "POST":
        form = InvoiceLineItemForm(request.POST, invoice=invoice)
        if form.is_valid():
            item = form.save()
            messages.success(
                request, f"Line item #{item.line_number} created successfully."
            )
            return htmx_redirect(
                request, "propraetor:invoice_details", invoice_id=invoice.id
            )
    else:
        form = InvoiceLineItemForm(invoice=invoice)

    context = {
        "form": form,
        "invoice": invoice,
        "base_template": base_template,
    }
    return render(request, "invoices/line_item_form.html", context)


def invoice_line_item_edit(request, invoice_id, line_item_id):
    """Edit a line item that belongs to a specific invoice."""
    base_template = get_base_template(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=invoice_id)
    item = get_object_or_404(InvoiceLineItem, pk=line_item_id, invoice=invoice)

    if request.method == "POST":
        form = InvoiceLineItemForm(request.POST, instance=item, invoice=invoice)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Line item #{item.line_number} updated successfully."
            )
            return htmx_redirect(
                request, "propraetor:invoice_details", invoice_id=invoice.id
            )
    else:
        form = InvoiceLineItemForm(instance=item, invoice=invoice)

    context = {
        "form": form,
        "invoice": invoice,
        "object": item,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "invoices/line_item_form.html", context)


@require_http_methods(["DELETE"])
def invoice_line_item_delete(request, invoice_id, line_item_id):
    """Delete a line item that belongs to a specific invoice."""
    invoice = get_object_or_404(PurchaseInvoice, pk=invoice_id)
    item = get_object_or_404(InvoiceLineItem, pk=line_item_id, invoice=invoice)
    item.delete()
    invoice.update_total_from_line_items()
    messages.success(request, "Line item deleted successfully.")
    return htmx_redirect(request, "propraetor:invoice_details", invoice_id=invoice.id)


# ============================================================================
# RECEIVE ITEMS — Auto-create assets/components from invoice line items
# ============================================================================


@require_POST
def receive_invoice_items(request, invoice_id):
    """Auto-create assets and components from an invoice's line items.

    For each line item with ``item_type`` of *asset* or *component*, creates
    the appropriate records (respecting ``quantity``), linking each back to
    the line item and the invoice.  Line items that are already fully
    received are skipped.
    """
    invoice = get_object_or_404(
        PurchaseInvoice.objects.prefetch_related("line_items"),
        pk=invoice_id,
    )

    created_assets = 0
    created_components = 0
    skipped = 0

    for li in invoice.line_items.all():
        remaining = li.remaining_to_receive

        if remaining <= 0:
            if li.item_type in ("asset", "component"):
                skipped += 1
            continue

        if li.item_type == "asset" and li.asset_model_id:
            for _ in range(remaining):
                with suppress_auto_log():
                    Asset.objects.create(
                        company=invoice.company,
                        asset_model=li.asset_model,
                        purchase_date=invoice.invoice_date,
                        purchase_cost=li.item_cost,
                        status="pending",
                        invoice=invoice,
                        invoice_line_item=li,
                    )
                created_assets += 1
            log_activity(
                event_type="asset",
                action="created",
                message=(
                    f"{remaining} asset(s) auto-created from invoice "
                    f"{invoice.invoice_number} line {li.line_number}"
                ),
                detail="Pending",
                instance=invoice,
            )

        elif li.item_type == "component" and li.component_type_id:
            for _ in range(remaining):
                with suppress_auto_log():
                    Component.objects.create(
                        component_type=li.component_type,
                        manufacturer=li.description[:255] if li.description else "",
                        status="spare",
                        purchase_date=invoice.invoice_date,
                        invoice=invoice,
                        invoice_line_item=li,
                    )
                created_components += 1
            log_activity(
                event_type="component",
                action="created",
                message=(
                    f"{remaining} component(s) auto-created from invoice "
                    f"{invoice.invoice_number} line {li.line_number}"
                ),
                detail="Spare",
                instance=invoice,
            )

    parts = []
    if created_assets:
        parts.append(f"{created_assets} asset(s)")
    if created_components:
        parts.append(f"{created_components} component(s)")
    if skipped:
        parts.append(f"{skipped} line(s) already received")

    if parts:
        messages.success(request, f"Receive complete: {', '.join(parts)}.")
    else:
        messages.info(
            request, "Nothing to receive — no asset/component line items found."
        )

    return htmx_redirect(request, "propraetor:invoice_details", invoice_id=invoice.id)


# ============================================================================
# REQUISITION ITEMS (delete only — managed from requisition details page)
# ============================================================================


@require_http_methods(["DELETE"])
def requisition_item_delete(request, item_id):
    """Delete a requisition item record."""
    item = get_object_or_404(RequisitionItem, pk=item_id)
    req_id = item.requisition_id
    item.delete()
    messages.success(request, "Requisition item deleted successfully.")
    return htmx_redirect(
        request, "propraetor:requisition_details", requisition_id=req_id
    )
