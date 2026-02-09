"""
Activity / audit-log helpers.

This module provides:

1.  Thread-local storage for the *current request user* so that Django
    signals (which have no access to the request) can stamp the actor
    on every ``ActivityLog`` row.

2.  ``log_activity()`` — the single entry-point for recording an event.

3.  ``post_save`` / ``pre_delete`` signal handlers that automatically
    log create / update / delete for every tracked model.

4.  ``suppress_auto_log()`` — context manager that temporarily disables
    signal-based auto-logging so views can record a more descriptive
    entry without a duplicate generic "updated" row.

Usage from a view (for custom events that signals can't capture):

    from propraetor.activity import log_activity, suppress_auto_log

    with suppress_auto_log():
        asset.status = "retired"
        asset.save(update_fields=["status", "updated_at"])

    log_activity(
        event_type="asset",
        action="status_changed",
        message=f"Asset {asset.asset_tag} status changed to retired",
        detail="Retired",
        instance=asset,
    )
"""

import contextlib
import threading

from django.contrib.auth.models import User as DjangoUser
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save, pre_delete
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

# ---------------------------------------------------------------------------
# Thread-local current user
# ---------------------------------------------------------------------------

_thread_locals = threading.local()


# ---------------------------------------------------------------------------
# Suppress auto-logging  (used by views that log explicitly)
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def suppress_auto_log():
    """
    Context manager that temporarily suppresses signal-based auto-logging.

    Use this around ``.save()`` / ``.delete()`` calls when the view is
    about to call ``log_activity()`` itself with a more descriptive
    action and message.

    Example::

        with suppress_auto_log():
            asset.status = "retired"
            asset.save(update_fields=["status", "updated_at"])

        log_activity(
            event_type="asset",
            action="status_changed",
            message=f"Asset {asset.asset_tag} status changed to retired",
            ...
        )
    """
    _thread_locals.suppress = True
    try:
        yield
    finally:
        _thread_locals.suppress = False


def _is_suppressed():
    """Return True when inside a ``suppress_auto_log()`` block."""
    return getattr(_thread_locals, "suppress", False)


def set_current_user(user):
    """Called by ``ActivityUserMiddleware`` on every request."""
    _thread_locals.user = user


def get_current_user():
    user = getattr(_thread_locals, "user", None)
    if user is not None and user.is_authenticated:
        return user
    return None


# ---------------------------------------------------------------------------
# Model → event_type / URL mapping
# ---------------------------------------------------------------------------

# Lazy import to avoid circular imports at module level.
_MODEL_META = None


def _get_model_meta():
    """
    Return a dict mapping each tracked model class to its
    ``(event_type, url_pattern)`` tuple.

    ``url_pattern`` uses ``{id}`` as a placeholder for the instance PK.
    """
    global _MODEL_META
    if _MODEL_META is not None:
        return _MODEL_META

    from propraetor.models import (
        Asset,
        AssetAssignment,
        AssetModel,
        Category,
        Company,
        Component,
        ComponentHistory,
        ComponentType,
        Department,
        Employee,
        InvoiceLineItem,
        Location,
        MaintenanceRecord,
        PurchaseInvoice,
        Requisition,
        RequisitionItem,
        SparePartsInventory,
        Vendor,
    )

    _MODEL_META = {
        Asset: "asset",
        Requisition: "requisition",
        PurchaseInvoice: "invoice",
        AssetAssignment: "assignment",
        Component: "component",
        ComponentHistory: "component",
        Employee: "user",
        Company: "company",
        Location: "location",
        Department: "department",
        Vendor: "vendor",
        Category: "category",
        AssetModel: "asset_model",
        ComponentType: "component_type",
        SparePartsInventory: "spare_part",
        MaintenanceRecord: "maintenance",
        InvoiceLineItem: "line_item",
        RequisitionItem: "fulfillment"
    }
    return _MODEL_META


def _url_for(instance):
    """Build a detail URL for a model instance using Django's reverse(), or return '' if unknown."""
    from propraetor.models import (
        Asset,
        AssetAssignment,
        AssetModel,
        Category,
        Company,
        Component,
        ComponentHistory,
        ComponentType,
        Department,
        Employee,
        InvoiceLineItem,
        Location,
        MaintenanceRecord,
        PurchaseInvoice,
        Requisition,
        RequisitionItem,
        SparePartsInventory,
        Vendor,
    )

    # Map model class to (url_name, kwarg_key, attribute_name)
    # Using lazy evaluation to avoid accessing FK attrs on unrelated models.
    url_mapping = {
        Asset: ("propraetor:asset_details", "asset_id", "pk"),
        Requisition: ("propraetor:requisition_details", "requisition_id", "pk"),
        PurchaseInvoice: ("propraetor:invoice_details", "invoice_id", "pk"),
        AssetAssignment: ("propraetor:asset_details", "asset_id", "asset_id"),
        Component: ("propraetor:component_details", "component_id", "pk"),
        ComponentHistory: (
            "propraetor:component_details",
            "component_id",
            "component_id",
        ),
        Employee: ("propraetor:user_details", "user_id", "employee_id"),
        Company: ("propraetor:company_details", "company_id", "pk"),
        Location: ("propraetor:location_details", "location_id", "pk"),
        Department: ("propraetor:department_details", "department_id", "pk"),
        Vendor: ("propraetor:vendor_details", "vendor_id", "pk"),
        Category: ("propraetor:category_details", "category_id", "pk"),
        AssetModel: ("propraetor:asset_model_details", "asset_model_id", "pk"),
        ComponentType: ("propraetor:component_type_details", "component_type_id", "pk"),
        SparePartsInventory: ("propraetor:spare_part_details", "spare_part_id", "pk"),
        MaintenanceRecord: ("propraetor:maintenance_details", "record_id", "pk"),
        InvoiceLineItem: ("propraetor:invoice_details", "invoice_id", "invoice_id"),
        RequisitionItem: (
            "propraetor:requisition_details",
            "requisition_id",
            "requisition_id",
        ),
    }

    instance_type = type(instance)
    if instance_type not in url_mapping:
        return ""

    url_name, kwarg_key, attr_name = url_mapping[instance_type]
    kwargs = {kwarg_key: getattr(instance, attr_name, None)}
    try:
        return reverse(url_name, kwargs=kwargs)
    except (NoReverseMatch, AttributeError):
        # If reverse fails (e.g., missing FK), return empty string
        return ""


def _event_type_for(instance):
    """Return the ``event_type`` string for a model instance."""
    meta = _get_model_meta()
    event_type = meta.get(type(instance))
    return event_type if event_type else "asset"


# ---------------------------------------------------------------------------
# Human-readable message helpers
# ---------------------------------------------------------------------------


def _short_repr(instance):
    """
    Return a short, human-friendly label for the instance.
    Falls back to ``str(instance)`` but tries common attributes first.
    """
    for attr in (
        "asset_tag",
        "component_tag",
        "requisition_number",
        "invoice_number",
        "name",
        "vendor_name",
        "type_name",
        "employee_id",
    ):
        val = getattr(instance, attr, None)
        if val:
            return str(val)
    return str(instance)


def _detail_for(instance):
    """
    Return a secondary detail string — typically a status display.
    """
    for method in (
        "get_status_display",
        "get_payment_status_display",
        "get_action_display",
    ):
        fn = getattr(instance, method, None)
        if fn:
            try:
                return str(fn())
            except Exception:
                pass
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def log_activity(
    *,
    event_type,
    action,
    message,
    detail="",
    instance=None,
    url="",
    actor=None,
    actor_name="",
    changes=None,
):
    """
    Create an ``ActivityLog`` row.

    Parameters
    ----------
    event_type
        One of the ``ActivityLog.EVENT_TYPE_CHOICES`` values.
    action
        One of the ``ActivityLog.ACTION_CHOICES`` values.
    message
        Human-readable summary.
    detail, optional
        Secondary information (status, assignee, etc.).
    instance, optional
        The affected model instance (used for GenericForeignKey).
    url, optional
        Link to the affected object.  Auto-derived from *instance* when
        omitted.
    actor, optional
        The Django ``User`` who performed the action.  Falls back to
        the thread-local current user.
    actor_name, optional
        Display name snapshot.  Derived from *actor* when omitted.
    changes, optional
        Structured ``{field: [old, new]}`` change data.
    """
    from propraetor.models import ActivityLog

    if actor is None:
        actor = get_current_user()

    if not actor_name and actor is not None:
        # Prefer the linked Employee name if available
        emp = getattr(actor, "employee", None)
        actor_name = emp.name if emp else (actor.get_full_name() or actor.username)

    ct = None
    obj_id = None
    obj_repr = ""

    if instance is not None:
        ct = ContentType.objects.get_for_model(instance)
        obj_id = instance.pk
        obj_repr = str(instance)[:512]
        if not url:
            url = _url_for(instance)

    ActivityLog.objects.create(
        timestamp=timezone.now(),
        event_type=event_type,
        action=action,
        message=message[:512],
        detail=detail[:512],
        actor=actor,
        actor_name=actor_name[:255],
        content_type=ct,
        object_id=obj_id,
        object_repr=obj_repr,
        url=url[:512],
        changes=changes,
    )


# ---------------------------------------------------------------------------
# Signal-based auto-logging
# ---------------------------------------------------------------------------

# Guard: prevent recursive logging when ActivityLog itself is saved.
_LOGGING = threading.local()


def _is_tracked(instance):
    """Return True if the instance's model class is in our tracking map."""
    return type(instance) in _get_model_meta()


def _on_post_save(sender, instance, created, **kwargs):
    """``post_save`` handler — log *created* or *updated*."""
    if getattr(_LOGGING, "active", False):
        return
    if _is_suppressed():
        return
    if not _is_tracked(instance):
        return

    _LOGGING.active = True
    try:
        event_type = _event_type_for(instance)
        label = _short_repr(instance)
        action = "created" if created else "updated"
        verb = "created" if created else "updated"
        type_label = event_type.replace("_", " ").title()
        message = f"{type_label} {label} {verb}"

        log_activity(
            event_type=event_type,
            action=action,
            message=message,
            detail=_detail_for(instance),
            instance=instance,
        )
    finally:
        _LOGGING.active = False


def _on_pre_delete(sender, instance, **kwargs):
    """``pre_delete`` handler — log *deleted* before the row disappears."""
    if getattr(_LOGGING, "active", False):
        return
    if _is_suppressed():
        return
    if not _is_tracked(instance):
        return

    _LOGGING.active = True
    try:
        event_type = _event_type_for(instance)
        label = _short_repr(instance)
        type_label = event_type.replace("_", " ").title()
        message = f"{type_label} {label} deleted"

        log_activity(
            event_type=event_type,
            action="deleted",
            message=message,
            detail=_detail_for(instance),
            instance=instance,
        )
    finally:
        _LOGGING.active = False


# ---------------------------------------------------------------------------
# Spare-parts inventory auto-sync (Component → SparePartsInventory)
# ---------------------------------------------------------------------------


def _sync_spare_parts_for_component(instance):
    """
    After a Component is saved or deleted, re-sync the SparePartsInventory
    row for its component_type so that ``quantity_available`` always
    reflects the real count of spare components.
    """
    ct = getattr(instance, "component_type", None)
    if ct is None:
        # component_type was already cascade-deleted; nothing to sync
        return
    try:
        from propraetor.models import sync_spare_parts_for_type

        with suppress_auto_log():
            sync_spare_parts_for_type(ct)
    except Exception:
        # Never let a sync failure break the main save/delete operation.
        pass


def _on_component_post_save(sender, instance, **kwargs):
    """Sync spare-parts inventory whenever a Component row is saved."""
    _sync_spare_parts_for_component(instance)


def _on_component_post_delete(sender, instance, **kwargs):
    """Sync spare-parts inventory whenever a Component row is deleted."""
    _sync_spare_parts_for_component(instance)


# ---------------------------------------------------------------------------
# Connect signals — called from AppConfig.ready()
# ---------------------------------------------------------------------------


def connect_signals():
    """
    Connect ``post_save`` and ``pre_delete`` to every tracked model so
    that CRUD operations are automatically logged.

    Also connects spare-parts auto-sync signals for the Component model.
    """
    for model_cls in _get_model_meta():
        post_save.connect(
            _on_post_save,
            sender=model_cls,
            dispatch_uid=f"activity_save_{model_cls.__name__}",
        )
        pre_delete.connect(
            _on_pre_delete,
            sender=model_cls,
            dispatch_uid=f"activity_delete_{model_cls.__name__}",
        )

    # Spare-parts auto-sync: keep SparePartsInventory.quantity_available in
    # lock-step with the actual number of Components whose status is 'spare'.
    from propraetor.models import Component

    post_save.connect(
        _on_component_post_save,
        sender=Component,
        dispatch_uid="spare_sync_component_save",
    )
    post_delete.connect(
        _on_component_post_delete,
        sender=Component,
        dispatch_uid="spare_sync_component_delete",
    )
