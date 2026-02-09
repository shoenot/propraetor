from django import template
import re

register = template.Library()

@register.simple_tag(takes_context=True)
def active_path(context, base):
    """
    Return "active" when the current request path matches `base`.

    Supported forms for `base`:
      - Single path: "/users/"
      - Comma-separated list: "/users/,/assets/"
      - Regex: "r/REGEX" (e.g. r/^/assets/.*$/)

    Matching behaviour:
      - If a path ends with a slash ("/foo/") it matches any path that starts with that prefix.
      - If a path does not end with a slash ("foo") it matches either exact equality or a prefix followed by "/" (to avoid false positives like "/foo-old/").
      - Regex is applied via re.search against request.path.
    """
    request = context.get('request')
    if not request:
        return ""

    path = request.path or ""

    # Regex mode: base starts with "r/"
    if isinstance(base, str) and base.startswith('r/'):
        pattern = base[2:]
        try:
            if re.search(pattern, path):
                return "active"
        except re.error:
            # If the regex is invalid, treat as no match
            return ""
        return ""

    # Treat comma-separated values
    for part in (p.strip() for p in str(base).split(',')):
        if not part:
            continue

        # If the part ends with a slash, match by prefix
        if part.endswith('/'):
            if path.startswith(part):
                return "active"
        else:
            # Match exact path or as a path segment prefix (avoid matching "/assets-old/")
            if path == part or path.startswith(part + '/'):
                return "active"

    return ""
