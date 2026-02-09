"""Requisition views."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import RequisitionForm, RequisitionItemForm
from ..models import Requisition, RequisitionItem
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# REQUISITIONS
# ============================================================================


def requisitions_list(request):
    columns = [
        TableColumn(
            "requsition_number",
            "REQ_#",
            "requisition_number",
            link_pattern=url_pattern(
                "propraetor:requisition_details", requisition_id="id"
            ),
            width="req-num-col",
        ),
        TableColumn(
            "company",
            "CMPNY",
            "company.code",
            link_pattern=url_pattern(
                "propraetor:company_details", company_id="company.id"
            ),
            width="company-col",
        ),
        TableColumn(
            "department",
            "DEPT",
            "department.name",
            link_pattern=url_pattern(
                "propraetor:department_details", department_id="department.id"
            ),
            width="department-col",
        ),
        TableColumn(
            "requested_by",
            "REQD_BY",
            "requested_by.name",
            link_pattern=url_pattern(
                "propraetor:user_details", user_id="requested_by.employee_id"
            ),
            width="name-col",
        ),
        TableColumn("priority", "PRIORITY", "priority", width="priority-col"),
        TableColumn("status", "STATUS", "status", width="status-badge-col"),
        TableColumn("requisition_date", "DATE", "requisition_date", width="date-col"),
    ]

    bulk_actions = [
        BulkAction(
            "fulfill",
            "FULFILL",
            reverse("propraetor:requisitions_bulk_fulfill"),
            confirmation="FULFILL SELECTED REQUISITIONS?",
        ),
        BulkAction(
            "cancel",
            "CANCEL",
            reverse("propraetor:requisitions_bulk_cancel"),
            confirmation="CANCEL SELECTED REQUISITIONS?",
        ),
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:requisitions_bulk_delete"),
            confirmation="DELETE SELECTED REQUISITIONS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=Requisition.objects.all().select_related(
            "company",
            "department",
            "requested_by",
        ),
        columns=columns,
        table_id="requisitions-table",
        search_fields=[
            "requisition_number",
            "company__name",
            "department__name",
            "requested_by__name",
            "requested_by__id",
            "specifications",
            "priority",
            "status",
        ],
        filter_fields={"status": "status"},
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Requisitions"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    pending_requests = Requisition.objects.filter(status="pending").count()
    high_priority_requests = Requisition.objects.filter(
        priority__in=["high", "urgent"]
    ).count()
    now = timezone.now()
    fulfilled_this_month = Requisition.objects.filter(
        status="fulfilled", fulfilled_date__year=now.year, fulfilled_date__month=now.month
    ).count()
    fulfilled_this_year = Requisition.objects.filter(
        status="fulfilled", fulfilled_date__year=now.year
    ).count()

    context.update(
        {
            "base_template": get_base_template(request),
            "pending_requests": pending_requests,
            "high_priority_requests": high_priority_requests,
            "fulfilled_this_month": fulfilled_this_month,
            "fulfilled_this_year": fulfilled_this_year,
        }
    )

    return render(request, "requisitions/requisitions_list.html", context)


def requisition_create(request):
    """Create a new requisition."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = RequisitionForm(request.POST)
        if form.is_valid():
            requisition = form.save()
            messages.success(
                request,
                f"Requisition '{requisition.requisition_number}' created successfully.",
            )
            return htmx_redirect(
                request, "propraetor:requisition_details", requisition_id=requisition.id
            )
    else:
        form = RequisitionForm()

    context = {
        "form": form,
        "base_template": base_template,
    }
    return render(request, "requisitions/requisition_create.html", context)


def requisition_edit(request, requisition_id):
    """Edit an existing requisition."""
    base_template = get_base_template(request)
    requisition = get_object_or_404(Requisition, pk=requisition_id)

    if request.method == "POST":
        form = RequisitionForm(request.POST, instance=requisition)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Requisition '{requisition.requisition_number}' updated successfully.",
            )
            return htmx_redirect(
                request,
                "propraetor:requisition_details",
                requisition_id=requisition.id,
            )
    else:
        form = RequisitionForm(instance=requisition)

    context = {
        "form": form,
        "object": requisition,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "requisitions/requisition_create.html", context)


def requisition_details(request, requisition_id):
    """Requisition Details Page"""
    base_template = get_base_template(request)

    requisition = get_object_or_404(
        Requisition.objects.prefetch_related(
            "items__asset__asset_model",
            "items__component__component_type",
        ).select_related(
            "requested_by",
            "approved_by",
            "department",
            "company",
        ),
        pk=requisition_id,
    )

    item_form = RequisitionItemForm(requisition=requisition)

    context = {
        "requisition": requisition,
        "base_template": base_template,
        "item_form": item_form,
    }

    return render(request, "requisitions/requisition_details.html", context)


@require_http_methods(["DELETE"])
def requisition_delete(request, requisition_id):
    """Delete a requisition."""
    requisition = get_object_or_404(Requisition, pk=requisition_id)
    requisition.delete()
    messages.success(request, "Requisition deleted successfully.")
    return htmx_redirect(request, "propraetor:requisition_list")


@require_POST
def requisition_item_create(request, requisition_id):
    """Create a requisition item (asset or component) scoped to a requisition details page."""
    requisition = get_object_or_404(Requisition, pk=requisition_id)

    form = RequisitionItemForm(
        data=request.POST,
        requisition=requisition,
    )

    if form.is_valid():
        item = form.save(commit=False)
        item.requisition = requisition
        item.save()
        messages.success(request, "Item added to requisition.")
        return htmx_redirect(
            request, "propraetor:requisition_details", requisition_id=requisition.id
        )

    messages.error(request, "Please correct the errors in the item form.")
    base_template = get_base_template(request)
    context = {
        "requisition": requisition,
        "item_form": form,
        "base_template": base_template,
    }
    return render(request, "requisitions/requisition_details.html", context)


@require_POST
def requisition_fulfill(request, requisition_id):
    """Mark a requisition as fulfilled."""
    requisition = get_object_or_404(Requisition, pk=requisition_id)

    if not requisition.items.exists():
        messages.error(
            request,
            "You must add at least one item (asset or component) before marking this requisition as fulfilled.",
        )
        return htmx_redirect(
            request, "propraetor:requisition_details", requisition_id=requisition.id
        )

    old_status = requisition.status
    with suppress_auto_log():
        requisition.status = "fulfilled"
        requisition.fulfilled_date = timezone.now().date()
        requisition.save(update_fields=["status", "fulfilled_date", "updated_at"])
    log_activity(
        event_type="requisition",
        action="fulfilled",
        message=f"Requisition {requisition.requisition_number} marked as fulfilled",
        detail="Fulfilled",
        instance=requisition,
        changes={"status": [old_status, "fulfilled"]},
    )
    messages.success(
        request, f"Requisition '{requisition.requisition_number}' marked as fulfilled."
    )
    return htmx_redirect(
        request, "propraetor:requisition_details", requisition_id=requisition.id
    )


@require_POST
def requisition_cancel(request, requisition_id):
    """Cancel a requisition."""
    requisition = get_object_or_404(Requisition, pk=requisition_id)
    old_status = requisition.status
    reason = request.POST.get("reason", "")
    with suppress_auto_log():
        requisition.status = "cancelled"
        if reason:
            requisition.cancellation_reason = reason
            requisition.save(
                update_fields=["status", "cancellation_reason", "updated_at"]
            )
        else:
            requisition.save(update_fields=["status", "updated_at"])
    log_activity(
        event_type="requisition",
        action="cancelled",
        message=f"Requisition {requisition.requisition_number} cancelled",
        detail=reason or "Cancelled",
        instance=requisition,
        changes={"status": [old_status, "cancelled"]},
    )
    messages.success(
        request, f"Requisition '{requisition.requisition_number}' cancelled."
    )
    return htmx_redirect(
        request, "propraetor:requisition_details", requisition_id=requisition.id
    )


@require_POST
def requisitions_bulk_delete(request):
    """Bulk delete selected requisitions."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = Requisition.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} requisition(s) deleted.")
    else:
        messages.warning(request, "No requisitions selected.")
    return htmx_redirect(request, "propraetor:requisition_list")


@require_POST
def requisitions_bulk_cancel(request):
    """Bulk cancel selected requisitions."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count = (
            Requisition.objects.filter(pk__in=selected_ids)
            .exclude(status="cancelled")
            .update(status="cancelled")
        )
        if count:
            log_activity(
                event_type="requisition",
                action="cancelled",
                message=f"{count} requisition(s) bulk cancelled",
                detail="Cancelled",
            )
        messages.success(request, f"{count} requisition(s) cancelled.")
    else:
        messages.warning(request, "No requisitions selected.")
    return htmx_redirect(request, "propraetor:requisition_list")


@require_POST
def requisitions_bulk_fulfill(request):
    """Bulk fulfill selected requisitions that have at least one item."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        today = timezone.now().date()
        # Only fulfil requisitions that have at least one item
        eligible_qs = (
            Requisition.objects.filter(pk__in=selected_ids)
            .exclude(status="fulfilled")
            .filter(items__isnull=False)
            .distinct()
        )
        count = eligible_qs.update(status="fulfilled", fulfilled_date=today)
        skipped = len(selected_ids) - count
        if count:
            log_activity(
                event_type="requisition",
                action="fulfilled",
                message=f"{count} requisition(s) bulk fulfilled",
                detail="Fulfilled",
            )
        if skipped:
            messages.warning(
                request,
                f"{skipped} requisition(s) skipped because they have no items.",
            )
        messages.success(request, f"{count} requisition(s) marked as fulfilled.")
    else:
        messages.warning(request, "No requisitions selected.")
    return htmx_redirect(request, "propraetor:requisition_list")
