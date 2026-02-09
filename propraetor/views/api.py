"""API views for AJAX search and modal inline creation."""

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .configs import MODAL_CREATE_CONFIGS, SEARCH_CONFIGS


@csrf_protect
@require_http_methods(["GET", "POST"])
def modal_create(request, model_key):
    """Return an inline creation form (GET) or process it (POST).

    On **GET** the view returns an HTML fragment containing the rendered form
    fields (no base-template chrome).

    On **POST**:
    * If valid  → ``JsonResponse`` with ``{success, id, text}`` so the JS
      widget can inject the new ``<option>`` and select it.
    * If invalid → re-rendered HTML fragment with validation errors so the
      modal can show them without a full page reload.
    """
    config = MODAL_CREATE_CONFIGS.get(model_key)
    if config is None:
        return JsonResponse({"error": "Unknown model"}, status=400)

    FormClass = config["form_class"]
    title = config["title"]

    if request.method == "POST":
        form = FormClass(request.POST, prefix="modal")
        if form.is_valid():
            obj = form.save()
            # Activity logging is handled automatically by the post_save signal
            return JsonResponse(
                {
                    "success": True,
                    "id": obj.pk,
                    "text": str(obj),
                }
            )
        # Validation failed – return the form with errors so the modal can
        # re-render in-place.
        return render(
            request,
            "partials/modal_create_form.html",
            {
                "form": form,
                "model_key": model_key,
                "title": title,
            },
        )

    # GET – blank form
    form = FormClass(prefix="modal")
    return render(
        request,
        "partials/modal_create_form.html",
        {
            "form": form,
            "model_key": model_key,
            "title": title,
        },
    )


@require_GET
def api_search(request):
    """Generic AJAX search used by the searchable-select JS widget.

    Query parameters
    ----------------
    model : str   – key into ``SEARCH_CONFIGS``
    q     : str   – search term (required, >= 1 char)
    limit : int   – max results (capped at 50, default 20)
    filter_<field> : str – extra ORM filters (must be whitelisted)
    """
    model_name = request.GET.get("model", "")
    query = request.GET.get("q", "").strip()
    try:
        limit = max(1, min(int(request.GET.get("limit", 20)), 50))
    except (ValueError, TypeError):
        limit = 20

    config = SEARCH_CONFIGS.get(model_name)
    if config is None:
        return JsonResponse({"results": [], "total": 0})

    qs = config["model"].objects.all()

    # Default filters (e.g. is_active=True)
    default_filters = config.get("default_filters")
    if default_filters:
        qs = qs.filter(**default_filters)

    # select_related
    sr = config.get("select_related")
    if sr:
        qs = qs.select_related(*sr)

    # Extra client-supplied filters (only whitelisted fields)
    allowed = set(config.get("allowed_filters", []))
    for key, value in request.GET.items():
        if key.startswith("filter_"):
            field = key[7:]
            if field in allowed and value:
                qs = qs.filter(**{field: value})

    # Text search – require at least one character
    if query:
        q_obj = Q()
        for sf in config["search_fields"]:
            q_obj |= Q(**{f"{sf}__icontains": query})
        qs = qs.filter(q_obj)
    else:
        return JsonResponse({"results": [], "total": 0})

    # Ordering
    order = config.get("order_by")
    if order:
        qs = qs.order_by(*order)

    total = qs.count()
    results = [{"id": obj.pk, "text": str(obj)} for obj in qs[:limit]]

    return JsonResponse({"results": results, "total": total, "limit": limit})
