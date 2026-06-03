"""
dash_create.py
--------------
Creates the Dash app instance.  Imported by every other module via:
    from dash_create import app, server

Keep this file minimal — only app instantiation lives here.
All layout and callback logic belongs in layouts.py / callbacks.py.
"""

import dash
import dash_bootstrap_components as dbc

# DARKLY is Bootstrap's dark theme.  custom.css (in /assets/) patches it
# further — Dash auto-serves every file in /assets/ with no extra config.
app_inst = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        dbc.themes.DARKLY,
        # Google Fonts — Inter for a clean, modern feel
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
    ],
    # Meaningful title shown in the browser tab
    title="NBA Fantasy Analytics",
    # Prevents the "Dash" favicon; swap in your own by placing a
    # favicon.ico inside /assets/
    update_title=None,
)

server = app_inst.server
