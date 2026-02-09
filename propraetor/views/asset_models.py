"""Asset model CRUD views."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ..forms import AssetModelForm
from ..models import Asset, AssetModel
from ..table_utils import BulkAction, ReusableTable, TableColumn, url_pattern
from .utils import get_base_template, htmx_redirect


def asset_models_list(request):
    columns = [
        TableColumn(
            "category",
            "CATEGORY",
            "category",
            link_pattern=url_pattern(
                "propraetor:category_details", category_id="category.id"
            ),
            width="category-col",
        ),
        TableColumn(
            "model_name",
            "MODEL",
            "model_name",
            link_pattern=url_pattern(
                "propraetor:asset_model_details", asset_model_id="id"
            ),
            width="name-col",
        ),
        TableColumn("model_number", "MODEL #", "model_number", width="model-num-col"),
        TableColumn("manufacturer", "MFG", "manufacturer", width="manufacturer-col"),
        TableColumn("asset_count", "ASSETS", "asset_count", width="count-col"),
    ]

    bulk_actions = [
        BulkAction(
            "delete",
            "DELETE",
            reverse("propraetor:asset_models_bulk_delete"),
            confirmation="DELETE SELECTED ASSET MODELS? This cannot be undone.",
            variant="danger",
        ),
    ]

    table = ReusableTable(
        request=request,
        queryset=AssetModel.objects.all(),
        columns=columns,
        table_id="assets-models-table",
        search_fields=[
            "model_name",
            "category__name",
            "model_number",
            "manufacturer",
        ],
        filter_fields={"status": "status"},
        bulk_actions=bulk_actions,
    )

    context = table.get_context()
    context["table_title"] = "Asset Models"

    is_table_update = any(
        k in request.GET for k in ["q", "sort", "page", "status", "visible_columns"]
    )

    if request.htmx:
        if request.GET.get("page"):
            return render(request, "partials/reusable_table_rows.html", context)
        if is_table_update:
            return render(request, "partials/reusable_table.html", context)

    context.update(
        {
            "base_template": get_base_template(request),
        }
    )

    return render(request, "asset_models/asset_models_list.html", context)


def asset_model_create(request):
    """Create a new asset model."""
    base_template = get_base_template(request)

    if request.method == "POST":
        form = AssetModelForm(request.POST)
        if form.is_valid():
            asset_model = form.save()
            messages.success(
                request, f"Asset model '{asset_model}' created successfully."
            )
            return htmx_redirect(
                request, "propraetor:asset_model_details", asset_model_id=asset_model.id
            )
    else:
        form = AssetModelForm()

    context = {
        "form": form,
        "base_template": base_template,
    }
    return render(request, "asset_models/asset_model_create.html", context)


def asset_model_edit(request, asset_model_id):
    """Edit an existing asset model."""
    base_template = get_base_template(request)
    asset_model = get_object_or_404(AssetModel, pk=asset_model_id)

    if request.method == "POST":
        form = AssetModelForm(request.POST, instance=asset_model)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Asset model '{asset_model}' updated successfully."
            )
            return htmx_redirect(
                request, "propraetor:asset_model_details", asset_model_id=asset_model.id
            )
    else:
        form = AssetModelForm(instance=asset_model)

    context = {
        "form": form,
        "object": asset_model,
        "editing": True,
        "base_template": base_template,
    }
    return render(request, "asset_models/asset_model_create.html", context)


def asset_model_details(request, asset_model_id):
    """Asset Model Details Page"""
    base_template = get_base_template(request)

    asset_model = get_object_or_404(AssetModel, pk=asset_model_id)
    assets_count = Asset.objects.filter(asset_model=asset_model).count()
    assets_of_model = Asset.objects.filter(asset_model=asset_model)
    context = {
        "asset_model": asset_model,
        "assets_count": assets_count,
        "assets_of_model": assets_of_model,
        "base_template": base_template,
    }

    return render(request, "asset_models/asset_model_details.html", context)


@require_http_methods(["DELETE"])
def asset_model_delete(request, asset_model_id):
    """Delete an asset model."""
    asset_model = get_object_or_404(AssetModel, pk=asset_model_id)
    name = str(asset_model)
    try:
        asset_model.delete()
        messages.success(request, f"Asset model '{name}' deleted successfully.")
    except Exception:
        messages.error(
            request,
            f"Cannot delete asset model '{name}' — it has associated assets.",
        )
        return htmx_redirect(
            request, "propraetor:asset_model_details", asset_model_id=asset_model.id
        )
    return htmx_redirect(request, "propraetor:asset_models_list")


@require_POST
def asset_models_bulk_delete(request):
    """Bulk delete selected asset models."""
    selected_ids = request.POST.getlist("selected_ids")
    if selected_ids:
        count, _ = AssetModel.objects.filter(pk__in=selected_ids).delete()
        messages.success(request, f"{count} asset model(s) deleted.")
    else:
        messages.warning(request, "No asset models selected.")
    return htmx_redirect(request, "propraetor:asset_models_list")


# ============================================================================
