from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.urls import NoReverseMatch, reverse


def url_pattern(url_name, **kwargs_mapping):
    """
    Create a link pattern function that uses Django's reverse() for URL generation.

    This helper ensures URLs are always generated consistently with your URL config
    instead of hardcoding URL strings.

    Args:
        url_name: The URL name to reverse (e.g., 'propraetor:asset_details')
        **kwargs_mapping: Mapping of URL parameter names to attribute paths
                         (e.g., asset_id='id', user_id='assigned_to.id')

    Returns:
        A function that takes an item and returns the reversed URL or None

    Example:
        TableColumn(
            "asset_tag",
            "TAG",
            "asset_tag",
            link_pattern=url_pattern('propraetor:asset_details', asset_id='id')
        )
    """

    def generate_url(item):
        kwargs = {}
        for param_name, attr_path in kwargs_mapping.items():
            # Navigate through dotted notation
            value = item
            for attr in attr_path.split("."):
                if value is None:
                    return None
                value = getattr(value, attr, None)

            if value is None:
                return None
            kwargs[param_name] = value

        try:
            return reverse(url_name, kwargs=kwargs)
        except (NoReverseMatch, AttributeError):
            return None

    return generate_url


class DictObj:
    """
    Wraps a dict so its keys are accessible as attributes.
    This allows plain dicts (e.g. from _build_activity_feed) to work
    with TableColumn.get_value / get_link which use getattr().
    """

    def __init__(self, d, pk=None):
        self.__dict__.update(d)
        self.pk = pk if pk is not None else id(self)

    def __repr__(self):
        return f"DictObj({self.__dict__})"


class TableColumn:
    """
    Represents a single column in the table.

    Args:
        key: Unique identifier for the column (used in database queries and column visibility)
        label: Display label for the column header
        accessor: How to access the data (field name, dotted path, or callable)
        sortable: Whether this column can be sorted
        sort_field: Database field to use for sorting (defaults to accessor if sortable)
        link_pattern: URL pattern for linking. Can be:
                     - A string with placeholders like {id}, {asset_tag} (legacy, not recommended)
                     - A callable that takes an item and returns a URL
                     - Result of url_pattern() helper (recommended)
        template: Custom template snippet for rendering the cell
        default_visible: Whether column is visible by default
        width: CSS width class (e.g., 'w-32', 'w-full')
        align: Text alignment ('left', 'center', 'right')
        badge: Whether to render as a badge (useful for status fields)
        badge_map: Mapping of values to badge CSS classes
    """

    def __init__(
        self,
        key,
        label,
        accessor,
        sortable=True,
        sort_field=None,
        link_pattern=None,
        template=None,
        default_visible=True,
        width=None,
        align="left",
        badge=False,
        badge_map=None,
    ):
        self.key = key
        self.label = label
        self.accessor = accessor
        self.sortable = sortable
        self.sort_field = sort_field or (
            accessor if isinstance(accessor, str) else None
        )
        self.link_pattern = link_pattern
        self.template = template
        self.default_visible = default_visible
        self.width = width
        self.align = align
        self.badge = badge
        self.badge_map = badge_map or {}

    def get_value(self, item):
        """Extract value from item using the accessor"""
        if callable(self.accessor):
            return self.accessor(item)

        # Handle dotted notation (e.g., 'assigned_to.name')
        value = item
        for attr in self.accessor.split("."):
            if value is None:
                return None
            value = getattr(value, attr, None)
        return value

    def get_link(self, item):
        """Generate link URL if link_pattern is defined"""
        if not self.link_pattern:
            return None

        # If link_pattern is callable (e.g., from url_pattern() helper), call it
        if callable(self.link_pattern):
            return self.link_pattern(item)

        # Otherwise treat as string pattern (legacy support)
        # Replace placeholders in link_pattern
        # Supports {id}, {pk}, {field_name}, {related.id}, etc.
        import re

        pattern = self.link_pattern
        placeholders = re.findall(r"\{([\w\.]+)\}", pattern)

        # Track whether any placeholder resolved to a non-null value
        has_value = False

        for placeholder in placeholders:
            # Support dotted notation similar to get_value (e.g. 'company.id')
            value = item
            for attr in placeholder.split("."):
                if value is None:
                    break
                value = getattr(value, attr, None)

            if value is not None:
                has_value = True
                pattern = pattern.replace(f"{{{placeholder}}}", str(value))

        # If all placeholders resolved to None, don't generate a link
        if not has_value:
            return None

        return pattern

    def to_dict(self):
        """Convert to dictionary for template context"""
        return {
            "key": self.key,
            "label": self.label,
            "sortable": self.sortable,
            "sort_field": self.sort_field,
            "default_visible": self.default_visible,
            "width": self.width,
            "align": self.align,
            "badge": self.badge,
        }


class BulkAction:
    """
    Represents a bulk action that can be performed on selected items.

    Args:
        key: Unique identifier for the action
        label: Display label for the action
        handler: View function or URL name to handle the action
        confirmation: Confirmation message to show before executing
        icon: Icon class or SVG
        variant: Button variant ('danger', 'primary', 'secondary')
    """

    def __init__(
        self,
        key,
        label,
        handler,
        confirmation=None,
        icon=None,
        variant="secondary",
    ):
        self.key = key
        self.label = label
        self.handler = handler
        self.confirmation = confirmation
        self.icon = icon
        self.variant = variant

    def to_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "handler": self.handler,
            "confirmation": self.confirmation,
            "icon": self.icon,
            "variant": self.variant,
        }


class ReusableTable:
    """
    A comprehensive reusable table class with support for:
    - Search, filter, sort, pagination
    - Column visibility toggling
    - Bulk actions with row selection
    - Lazy loading (infinite scroll)
    - Custom cell rendering
    """

    def __init__(
        self,
        request,
        queryset,
        columns,
        table_id="data-table",
        default_sort=None,
        page_size=20,
        search_fields=None,
        filter_fields=None,
        bulk_actions=None,
        show_column_toggle=True,
        show_bulk_select=True,
        lazy_load=True,
    ):
        self.request = request
        self.queryset = queryset
        self.columns = columns
        self.table_id = table_id
        self.default_sort = default_sort or self._get_first_sortable_field()
        self.page_size = page_size
        self.search_fields = search_fields or []
        self.filter_fields = filter_fields or {}
        self.bulk_actions = bulk_actions or []
        self.show_column_toggle = show_column_toggle
        self.show_bulk_select = show_bulk_select
        self.lazy_load = lazy_load

        # Get current parameters from request
        self.current_sort = request.GET.get("sort", self.default_sort)
        self.query = request.GET.get("q", "").strip()
        self.visible_columns = self._get_visible_columns()

    def _get_first_sortable_field(self):
        """Get the first sortable column's sort field"""
        for col in self.columns:
            if col.sortable and col.sort_field:
                return col.sort_field
        return "id"

    def _get_visible_columns(self):
        """Get list of visible column keys from request or defaults"""
        # Check if user has specified visible columns
        visible = self.request.GET.getlist("visible_columns")
        if visible:
            return visible

        # Use cookies/session for persistence (optional)
        session_key = f"table_{self.table_id}_visible_columns"
        if session_key in self.request.session:
            return self.request.session[session_key]

        # Default to columns marked as default_visible
        return [col.key for col in self.columns if col.default_visible]

    def _is_queryset(self):
        """Check whether the underlying data is a Django QuerySet."""
        return isinstance(self.queryset, QuerySet)

    def apply_search(self):
        """Apply search across specified fields (QuerySet only)."""
        if not self._is_queryset():
            return
        if self.query and self.search_fields:
            search_filter = Q()
            for field in self.search_fields:
                search_filter |= Q(**{f"{field}__icontains": self.query})
            self.queryset = self.queryset.filter(search_filter).distinct()

    def apply_filters(self):
        """Apply filters from request parameters (QuerySet only)."""
        if not self._is_queryset():
            return
        for param, field in self.filter_fields.items():
            value = self.request.GET.get(param)
            if value:
                if isinstance(field, str):
                    # Simple field filter
                    self.queryset = self.queryset.filter(**{field: value})
                elif callable(field):
                    # Custom filter function
                    self.queryset = field(self.queryset, value)

    def apply_sorting(self):
        """Apply sorting (QuerySet only; lists must be pre-sorted)."""
        if not self._is_queryset():
            return
        if self.current_sort:
            self.queryset = self.queryset.order_by(self.current_sort)

    def paginate(self):
        """Apply pagination"""
        paginator = Paginator(self.queryset, self.page_size)
        page_number = self.request.GET.get("page", 1)
        return paginator.get_page(page_number)

    def toggle_sort(self, field):
        """Generate the next sort state for a field"""
        if not field:
            return None
        return f"-{field}" if self.current_sort == field else field

    def get_header_context(self):
        """Build context for table headers"""
        headers = []

        # Add bulk select column if enabled
        if self.show_bulk_select:
            headers.append(
                {
                    "key": "_select",
                    "label": "select_all",
                    "type": "checkbox",
                    "sortable": False,
                    "width": "checkbox-col",
                    "align": "center",
                }
            )

        # Add data columns
        for col in self.columns:
            if col.key in self.visible_columns:
                header = col.to_dict()
                header["is_current"] = (
                    self.current_sort.strip("-") == col.sort_field
                    if col.sort_field
                    else False
                )
                header["direction"] = (
                    "desc" if self.current_sort.startswith("-") else "asc"
                )
                header["next_sort"] = (
                    self.toggle_sort(col.sort_field) if col.sortable else None
                )
                headers.append(header)

        return headers

    def get_row_context(self, items):
        """Build context for table rows"""
        rows = []

        for item in items:
            cells = []

            # Add bulk select cell if enabled
            if self.show_bulk_select:
                cells.append(
                    {
                        "type": "checkbox",
                        "value": item.pk,
                    }
                )

            # Add data cells
            for col in self.columns:
                if col.key in self.visible_columns:
                    value = col.get_value(item)
                    link = col.get_link(item)

                    cell = {
                        "key": col.key,
                        "value": value,
                        "link": link,
                        "align": col.align,
                        "badge": col.badge,
                        "badge_class": col.badge_map.get(value, ""),
                        "template": col.template,
                    }
                    cells.append(cell)

            rows.append(
                {
                    "pk": item.pk,
                    "item": item,
                    "cells": cells,
                }
            )

        return rows

    def get_context(self):
        """
        Build complete context for the table.
        Call this from your view and pass to template.
        """
        # Apply filters and sorting
        self.apply_search()
        self.apply_filters()
        self.apply_sorting()

        # Paginate
        page_obj = self.paginate()

        # Build context
        context = {
            # Table configuration
            "table_id": self.table_id,
            "show_column_toggle": self.show_column_toggle,
            "show_bulk_select": self.show_bulk_select,
            "lazy_load": self.lazy_load,
            # Data
            "items": page_obj,
            "headers": self.get_header_context(),
            "rows": self.get_row_context(page_obj),
            # Metadata
            "total_count": page_obj.paginator.count,
            "current_sort": self.current_sort,
            "query": self.query,
            "visible_columns": self.visible_columns,
            # Column management
            "all_columns": [col.to_dict() for col in self.columns],
            # Bulk actions
            "bulk_actions": [action.to_dict() for action in self.bulk_actions],
            # URLs
            "rows_url": self.request.path,
        }

        return context


# Helper function for views
def create_table(request, queryset, columns, **kwargs):
    """
    Convenience function to create a table.

    Usage:
        table = create_table(
            request,
            Asset.objects.all(),
            columns=[
                TableColumn('asset_tag', 'Tag', 'asset_tag', link_pattern='/assets/{id}/'),
                TableColumn('status', 'Status', 'status', badge=True),
            ],
            search_fields=['asset_tag', 'model'],
        )
        context = table.get_context()
    """
    return ReusableTable(request, queryset, columns, **kwargs)
