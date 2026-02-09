"""Category views."""

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..activity import log_activity, suppress_auto_log
from ..forms import CategoryForm
from ..models import Category
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect

# CATEGORIES
# ============================================================================


def categories_list(request):
    queryset = Category.objects.annotate(
        total_models=Count("models", distinct=True),
    )
    columns = [
        TableColumn(
            "name",
            "NAME",
            "name",
            link_pattern=url_pattern("propraetor:category_details", category_id="id"),
            width="name-col",
        ),
        TableColumn("description", "DESCRIPTION", "description", sortable=False, width="description-col"),
        TableColumn("models", "MODELS", "total_models", width="count-col"),
    ]

    bulk_actions = [
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:categories_bulk_delete"),
            confirmation="DELETE SELECTED CATEGORIES? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=queryset,
        columns=columns,
        table_id="categories-table",
        search_fields=["name", "description"],
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Categories"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    context.update({"base_template": get_base_template(request)})
    return render(request, "categories/categories_list.html", context)


def category_create(request):
    """Create a new category."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(
                request, f"Category '{category.name}' created successfully."
            )
            return htmx_redirect(
                request, "propraetor:category_details", category_id=category.id
            )
    else:
        form = CategoryForm()

    context = {"form": form, "base_template": base_template}
    return render(request, "categories/category_create.html", context)


def category_edit(request, category_id):
    """Edit an existing category."""
    base_template = get_base_template(request)
    category = get_object_or_404(Category, pk=category_id)

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Category '{category.name}' updated successfully."
            )
            return htmx_redirect(
                request, "propraetor:category_details", category_id=category.id
            )
    else:
        form = CategoryForm(instance=category)

    context = {
        "form": form,
        "object": category,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "categories/category_create.html", context)


def category_details(request, category_id):
    """Category detail page."""
    base_template = get_base_template(request)
    category = get_object_or_404(
        Category.objects.prefetch_related("models"),
        pk=category_id,
    )
    context = {"category": category, "base_template": base_template}
    return render(request, "categories/category_details.html", context)


@require_http_methods(["DELETE"])
def category_delete(request, category_id):
    """Delete a category."""
    category = get_object_or_404(Category, pk=category_id)
    name = category.name
    category.delete()
    messages.success(request, f"Category '{name}' deleted successfully.")
    return htmx_redirect(request, "propraetor:categories_list")


@require_POST
def categories_bulk_delete(request):
    """Bulk delete selected categories."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = Category.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} category(ies) deleted.")
    else:
        messages.warning(request, "No categories selected.")
    return htmx_redirect(request, "propraetor:categories_list")
