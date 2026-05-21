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

from dash_create import app, server          # noqa: F401 — server used by gunicorn
from landing import page0
from layouts import page1, page2, page3
import callbacks                             # noqa: F401 — registers all @app.callback decorators


# ---------------------------------------------------------------------------
# Root layout — just a URL listener + a content div
# ---------------------------------------------------------------------------

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content"),
])


# ---------------------------------------------------------------------------
# Router callback
# ---------------------------------------------------------------------------

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
)
def display_page(pathname: str):
    """Return the correct page layout based on the URL path."""
    routes = {
        "/apps/fantasy-predictions":  page1,
        "/apps/free-agent-screening": page2,
        "/apps/team-performance":     page3,
    }
    # Root path ("/") and anything unrecognised -> landing page
    return routes.get(pathname, page0)


# ---------------------------------------------------------------------------
# Dev server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run_server(debug=True)
