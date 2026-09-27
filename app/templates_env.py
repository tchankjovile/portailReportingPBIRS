"""
Shared Jinja2 Templates instance for BICEC PBIRS Portal.

CRITICAL FIX: Starlette 1.6+ + Jinja2 3.1.6 compatibility.
We bypass Starlette's Jinja2Templates entirely and use a simple
wrapper that calls Jinja2 directly then wraps in HTMLResponse.
This avoids the 'unhashable type: dict' and 'dict has no attribute split'
bugs caused by Starlette's internal use of env.get_template(name, globals).
"""
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi.responses import HTMLResponse


# Single Jinja2 Environment instance for the entire application
_jinja_env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"]),
    auto_reload=True,
    cache_size=400,
)

# Register custom filters
_jinja_env.filters["tojson"] = lambda value: json.dumps(value, ensure_ascii=False)


class _Templates:
    """
    Lightweight Starlette Jinja2Templates replacement.
    Uses Jinja2 directly to avoid Starlette 1.6 / Jinja2 3.1.6 compatibility bugs.
    Supports both old-style (name, context) and new-style (request, name, context) calls.
    """

    def __init__(self, env: Environment):
        self.env = env

    def TemplateResponse(self, *args, **kwargs) -> HTMLResponse:
        """
        Supports:
          - Old-style: TemplateResponse("template.html", {"request": req, ...})
          - New-style: TemplateResponse(request, "template.html", {...})
        """
        if args and not hasattr(args[0], 'method'):
            # Old-style: first arg is template name (str)
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.get("context", {})
        else:
            # New-style: first arg is request object
            name = args[1] if len(args) > 1 else kwargs.get("name", "")
            context = args[2] if len(args) > 2 else kwargs.get("context", {})

        status_code = kwargs.get("status_code", 200)
        headers = kwargs.get("headers")

        template = self.env.get_template(name)
        content = template.render(**context)
        return HTMLResponse(content=content, status_code=status_code, headers=headers)


templates = _Templates(env=_jinja_env)
