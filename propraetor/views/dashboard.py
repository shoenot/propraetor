"""Dashboard view with statistics and summaries."""

from datetime import timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from ..models import (
    Asset,
    AssetModel,
    Component,
    Department,
    Employee,
    Location,
    MaintenanceRecord,
    PurchaseInvoice,
    Requisition,
    SparePartsInventory,
    Vendor,
)
from .utils import get_activity_qs, get_base_template

# DASHBOARD
# ============================================================================


def dashboard(request):
    """Main dashboard with key stats, alerts, breakdowns, and recent activity."""

    now = timezone.now()
    today = now.date()
    thirty_days_ago = today - timedelta(days=30)
    ninety_days_ahead = today + timedelta(days=90)

    # ==================================================================
    # CORE COUNTS
    # ==================================================================
    total_employees = Employee.objects.count()
    active_users = Employee.objects.filter(status="active").count()

    # Optimize asset counts with a single aggregate query
    asset_counts = Asset.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        in_repair=Count("id", filter=Q(status="in_repair")),
        pending=Count("id", filter=Q(status="pending")),
        retired=Count("id", filter=Q(status="retired")),
        disposed=Count("id", filter=Q(status="disposed")),
        inactive=Count("id", filter=Q(status="inactive")),
    )

    total_assets = asset_counts["total"]
    active_assets = asset_counts["active"]
    in_repair = asset_counts["in_repair"]
    pending_assets = asset_counts["pending"]
    retired_assets = asset_counts["retired"]
    disposed_assets = asset_counts["disposed"]
    inactive_assets = asset_counts["inactive"]

    if total_assets > 0:
        active_pct = round(active_assets / total_assets * 100, 1)
        repair_pct = round(in_repair / total_assets * 100, 1)
    else:
        active_pct = 0
        repair_pct = 0

    total_components = Component.objects.count()
    installed_components = Component.objects.filter(status="installed").count()
    spare_components = Component.objects.filter(status="spare").count()
    failed_components = Component.objects.filter(status="failed").count()

    total_locations = Location.objects.count()
    total_departments = Department.objects.count()
    total_vendors = Vendor.objects.count()
    total_models = AssetModel.objects.count()

    # ==================================================================
    # FINANCIAL SNAPSHOT
    # ==================================================================
    unpaid_qs = PurchaseInvoice.objects.filter(
        payment_status__in=["unpaid", "partially_paid"]
    )
    unpaid_invoices = unpaid_qs.count()
    unpaid_amount = unpaid_qs.aggregate(total=Sum("total_amount"))["total"] or 0

    recently_paid_invoices = PurchaseInvoice.objects.filter(
        payment_status="paid", payment_date__gte=thirty_days_ago
    ).count()
    recently_paid_amount = (
        PurchaseInvoice.objects.filter(
            payment_status="paid", payment_date__gte=thirty_days_ago
        ).aggregate(total=Sum("total_amount"))["total"]
        or 0
    )

    total_invoices = PurchaseInvoice.objects.count()
    total_invoice_value = (
        PurchaseInvoice.objects.aggregate(total=Sum("total_amount"))["total"] or 0
    )

    # Total asset value (purchase costs)
    total_asset_value = (
        Asset.objects.filter(purchase_cost__isnull=False).aggregate(
            total=Sum("purchase_cost")
        )["total"]
        or 0
    )

    # ==================================================================
    # ASSET STATUS DISTRIBUTION (for chart / breakdown)
    # ==================================================================
    asset_status_breakdown = [
        {"label": "Active", "value": active_assets, "css_class": "status-active"},
        {"label": "Pending", "value": pending_assets, "css_class": "status-pending"},
        {"label": "In Repair", "value": in_repair, "css_class": "status-in-repair"},
        {"label": "Retired", "value": retired_assets, "css_class": "status-retired"},
        {"label": "Disposed", "value": disposed_assets, "css_class": "status-disposed"},
        {"label": "Inactive", "value": inactive_assets, "css_class": "status-inactive"},
    ]

    # ==================================================================
    # WARRANTY ALERTS (expiring within 90 days)
    # ==================================================================
    warranty_expiring = (
        Asset.objects.filter(
            warranty_expiry_date__gte=today,
            warranty_expiry_date__lte=ninety_days_ahead,
            status="active",
        )
        .select_related("asset_model", "asset_model__category", "assigned_to")
        .order_by("warranty_expiry_date")[:8]
    )

    warranty_expired_count = Asset.objects.filter(
        warranty_expiry_date__lt=today, status="active"
    ).count()

    # ==================================================================
    # LOW STOCK SPARE PARTS
    # ==================================================================
    low_stock_parts = (
        SparePartsInventory.objects.filter(
            quantity_available__lte=F("quantity_minimum")
        )
        .select_related("component_type", "location")
        .order_by("quantity_available")[:6]
    )

    # ==================================================================
    # REQUISITION SUMMARY
    # ==================================================================
    pending_requisitions_count = Requisition.objects.filter(status="pending").count()
    fulfilled_requisitions_30d = Requisition.objects.filter(
        status="fulfilled", fulfilled_date__gte=thirty_days_ago
    ).count()

    pending_requisitions = (
        Requisition.objects.filter(status="pending")
        .select_related("requested_by", "department", "company")
        .order_by("-priority", "-requisition_date")[:6]
    )

    # ==================================================================
    # RECENT MAINTENANCE
    # ==================================================================
    recent_maintenance = (
        MaintenanceRecord.objects.all()
        .select_related("asset", "asset__asset_model")
        .order_by("-maintenance_date")[:5]
    )

    total_maintenance_cost_30d = (
        MaintenanceRecord.objects.filter(
            maintenance_date__gte=thirty_days_ago, cost__isnull=False
        ).aggregate(total=Sum("cost"))["total"]
        or 0
    )

    # ==================================================================
    # TOP DEPARTMENTS BY ASSET COUNT
    # ==================================================================
    top_departments = Department.objects.annotate(
        asset_count=Count("company__assets"),
        employee_count=Count("employees"),
    ).order_by("-asset_count")[:5]

    # ==================================================================
    # RECENT ACTIVITY (from ActivityLog table)
    # ==================================================================
    recent_activity = get_activity_qs()[:10]

    # ==================================================================
    # ASSETS ADDED OVER TIME (last 6 months, by month) - optimized with single query
    # ==================================================================
    six_months_ago = (today.replace(day=1) - timedelta(days=180)).replace(day=1)
    six_months_ago_dt = timezone.make_aware(
        timezone.datetime.combine(six_months_ago, timezone.datetime.min.time())
    )

    # Single query with TruncMonth annotation
    assets_by_month_raw = (
        Asset.objects.filter(created_at__gte=six_months_ago_dt)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    # Create a lookup dict for quick access
    month_counts = {
        item["month"].strftime("%b"): item["count"] for item in assets_by_month_raw
    }

    # Build the final list with all 6 months (including zeros)
    assets_by_month = []
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        month_label = month_start.strftime("%b")
        count = month_counts.get(month_label, 0)
        assets_by_month.append({"month": month_label, "count": count})

    # ==================================================================
    # CONTEXT
    # ==================================================================
    context = {
        # Primary stats
        "active_users": active_users,
        "total_employees": total_employees,
        "total_assets": total_assets,
        "active_assets": active_assets,
        "active_pct": active_pct,
        "in_repair": in_repair,
        "repair_pct": repair_pct,
        "pending_assets": pending_assets,
        "total_components": total_components,
        "installed_components": installed_components,
        "spare_components": spare_components,
        "failed_components": failed_components,
        "total_locations": total_locations,
        "total_departments": total_departments,
        "total_vendors": total_vendors,
        "total_models": total_models,
        # Financial
        "unpaid_invoices": unpaid_invoices,
        "unpaid_amount": unpaid_amount,
        "recently_paid_invoices": recently_paid_invoices,
        "recently_paid_amount": recently_paid_amount,
        "total_invoices": total_invoices,
        "total_invoice_value": total_invoice_value,
        "total_asset_value": total_asset_value,
        "total_maintenance_cost_30d": total_maintenance_cost_30d,
        # Breakdowns
        "asset_status_breakdown": asset_status_breakdown,
        "assets_by_month": assets_by_month,
        # Alerts
        "warranty_expiring": warranty_expiring,
        "warranty_expired_count": warranty_expired_count,
        "low_stock_parts": low_stock_parts,
        # Requisitions
        "pending_requisitions_count": pending_requisitions_count,
        "fulfilled_requisitions_30d": fulfilled_requisitions_30d,
        "pending_requisitions": pending_requisitions,
        # Maintenance
        "recent_maintenance": recent_maintenance,
        # Departments
        "top_departments": top_departments,
        # Activity
        "recent_activity": recent_activity,
        # Misc
        "today": now,
        "base_template": get_base_template(request),
    }

    return render(request, "dashboard.html", context)


# ============================================================================
