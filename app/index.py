"""
index.py
--------
App entry point.  Run with:
    python index.py

Routing:
    /                        → landing page (page0)
    /apps/fantasy-predictions → page1  (predictive modeling)
    /apps/free-agent-screening→ page2  (free agent screener)
    /apps/team-performance    → page3  (current team performance)
"""

import dash
from dash import dcc, html
from dash.dependencies import Input, Output

from app.dash_create import app_inst, server          # noqa: F401 — server used by gunicorn
from app.landing import page0
from app.layouts import page1, page2, page3, page4
import app.callbacks                             # noqa: F401 — registers all @app.callback decorators


# ---------------------------------------------------------------------------
# Root layout — just a URL listener + a content div
# ---------------------------------------------------------------------------

app_inst.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content"),
])


# ---------------------------------------------------------------------------
# Router callback
# ---------------------------------------------------------------------------

@app_inst.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
)
def display_page(pathname: str):
    """Return the correct page layout based on the URL path."""
    routes = {
        "/apps/fantasy-predictions":  page1,
        "/apps/free-agent-screening": page2,
        "/apps/team-performance":     page3,
        "/apps/ai-assistant":         page4
    }
    # Root path ("/") and anything unrecognised -> landing page
    return routes.get(pathname, page0)


# ---------------------------------------------------------------------------
# Dev server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run_server(debug=True)
