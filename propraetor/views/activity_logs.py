"""Activity log views."""

from django.shortcuts import render

from ..models import ActivityLog
from ..table_utils import ReusableTable, TableColumn
from .utils import get_activity_qs, get_base_template

# ACTIVITY
# ============================================================================


def activity_list(request):
    """Full activity feed page with filtering and pagination."""

    EVENT_TYPES = [
        ("", "all types"),
    ] + list(ActivityLog.EVENT_TYPE_CHOICES)

    # Read filter from query string  (named "status" to match reusable table hx-include)
    type_filter = request.GET.get("status", "").strip() or None

    qs = get_activity_qs(event_type_filter=type_filter)

    # Define columns for the reusable table
    columns = [
        TableColumn(
            "type",
            "type",
            "event_type",
            sortable=False,
            template="partials/cells/event_type_cell.html",
            width="event-type-col",
            align="center",
        ),
        TableColumn(
            "event",
            "event",
            "message",
            sortable=False,
            # Uses the 'url' field from ActivityLog, which is generated via reverse() in activity.py
            link_pattern="{url}",
            width="event-col",
        ),
        TableColumn(
            "detail",
            "detail",
            "detail",
            sortable=False,
            width="detail-col",
        ),
        TableColumn(
            "actor",
            "actor",
            lambda item: item.actor_name or "system",
            sortable=False,
            width="actor-col",
        ),
        TableColumn(
            "time",
            "time",
            lambda item: (
                item.timestamp.strftime("%b %d, %Y  %H:%M") if item.timestamp else "-"
            ),
            sortable=False,
            width="datetime-col",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=qs,
        columns=columns,
        table_id="activity-table",
        page_size=25,
        search_fields=["message", "detail", "actor_name"],
        show_column_toggle=False,
        show_bulk_select=False,
        lazy_load=True,
    )

    context = table.get_context()
    context.update(
        {
            "table_title": "Activity",
            "event_types": EVENT_TYPES,
            "current_type": type_filter or "",
            "base_template": get_base_template(request),
        }
    )

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    return render(request, "activity/activity_list.html", context)
