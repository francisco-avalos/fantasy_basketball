"""
landing.py
----------
The landing page (page0).

Import in index.py:
    from landing import page0
"""

from dash import dcc, html


# ---------------------------------------------------------------------------
# Helper — reusable feature card
# ---------------------------------------------------------------------------

def _feature_card(icon: str, icon_class: str, title: str, description: str) -> html.Div:
    return html.Div(
        className="feature-card",
        children=[
            html.Div(icon, className=f"feature-icon {icon_class}"),
            html.Div(title, className="feature-title"),
            html.Div(description, className="feature-desc"),
        ],
    )


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

page0 = html.Div(
    style={"padding": "0 24px 48px"},
    children=[

        # ── Hero ──────────────────────────────────────────────────────────
        html.Div(
            className="landing-hero",
            children=[
                html.H1(
                    "NBA Fantasy Analytics",
                    className="landing-title",
                ),
                html.P(
                    "Time-series forecasting, injury survival analysis, and "
                    "minutes-weighted production metrics — built on "
                    "Basketball-Reference, ESPN, and Yahoo data.",
                    className="landing-subtitle",
                ),

                # Tech pills
                html.Div(
                    className="landing-pills",
                    children=[
                        html.Span("ARIMA · SARIMAX · LSTM · Neural Network", className="pill-accent"),
                        html.Span("Kaplan-Meier injury modeling",             className="pill"),
                        html.Span("Minutes-weighted ranking tool",            className="pill"),
                        html.Span("ESPN + Yahoo league integration",          className="pill"),
                        html.Span("MariaDB · Python · Plotly Dash",           className="pill"),
                    ],
                ),

                # CTA buttons
                html.Div(
                    className="landing-cta-row",
                    children=[
                        dcc.Link(
                            html.Button("Free Agent Screener →", className="btn-primary"),
                            href="/apps/free-agent-screening",
                        ),
                        dcc.Link(
                            html.Button("View Player Predictions", className="btn-secondary"),
                            href="/apps/fantasy-predictions",
                        ),
                        dcc.Link(
                            html.Button("My Team Performance", className="btn-secondary"),
                            href="/apps/team-performance",
                        ),
                        dcc.Link(
                            html.Button("AI Assistant", className="btn-secondary"),
                            href="/apps/ai-assistant",
                        ),
                    ],
                ),
            ],
        ),

        # ── Feature cards ─────────────────────────────────────────────────
        html.Div(
            className="feature-grid",
            children=[
                _feature_card(
                    icon="📈",
                    icon_class="fi-amber",
                    title="Predictive modeling",
                    description=(
                        "Per-player point forecasts using ARIMA, SARIMAX, "
                        "double/single exponential smoothing, and LSTM neural "
                        "networks. Champion model selected automatically by "
                        "lowest MAE on a held-out test set."
                    ),
                ),
                _feature_card(
                    icon="🔍",
                    icon_class="fi-blue",
                    title="Free agent screener",
                    description=(
                        "Rank waiver wire pickups by minutes-weighted category "
                        "production — a view unavailable natively in ESPN or Yahoo. "
                        "Filter by league, date range, calculation type, and "
                        "individual stat categories."
                    ),
                ),
                _feature_card(
                    icon="🏥",
                    icon_class="fi-green",
                    title="Injury survival analysis",
                    description=(
                        "Kaplan-Meier survival curves estimate the probability a "
                        "player returns within N days, broken down by injury type. "
                        "Data sourced from Pro Sports Transactions."
                    ),
                ),
                _feature_card(
                    icon="📊",
                    icon_class="fi-amber",
                    title="Team performance dashboard",
                    description=(
                        "Minutes-weighted production heatmaps, weekly contribution "
                        "trend lines, per-player box plots, and weekday vs. weekend "
                        "performance splits for my current roster."
                    ),
                ),
                _feature_card(
                    icon="🤖",
                    icon_class="fi-blue",
                    title="Multi-model comparison",
                    description=(
                        "Every player gets evaluated across 8 model types. Results "
                        "are stored in the DB and surfaced in the predictions table "
                        "so you can see exactly why the champion was chosen."
                    ),
                ),
                _feature_card(
                    icon="🗄️",
                    icon_class="fi-green",
                    title="Live data pipeline",
                    description=(
                        "Daily player game logs scraped from Basketball-Reference, "
                        "merged with ESPN and Yahoo league rosters, and stored in "
                        "MariaDB. Models retrain on fresh data automatically."
                    ),
                ),
            ],
        ),

        # ── Methodology note ──────────────────────────────────────────────
        html.Div(
            style={
                "maxWidth": "900px",
                "margin": "40px auto 0",
                "background": "var(--bg-card)",
                "border": "0.5px solid var(--border)",
                "borderRadius": "var(--radius-lg)",
                "padding": "20px 24px",
            },
            children=[
                html.Div("Methodology", style={
                    "fontSize": "13px",
                    "fontWeight": "500",
                    "color": "var(--text-primary)",
                    "marginBottom": "10px",
                }),
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"},
                    children=[
                        html.Div([
                            html.Div("Forecasting approach", style={"fontSize": "11px", "color": "var(--accent)", "marginBottom": "4px", "textTransform": "uppercase", "letterSpacing": "0.07em"}),
                            html.Div(
                                "Player game-log time series are modeled individually. "
                                "A rolling walk-forward validation scheme is used — "
                                "models are never evaluated on data they were trained on. "
                                "The champion model per player is updated each run.",
                                style={"fontSize": "12px", "color": "var(--text-muted)", "lineHeight": "1.6"},
                            ),
                        ]),
                        html.Div([
                            html.Div("Minutes-weighted ranking", style={"fontSize": "11px", "color": "var(--info)", "marginBottom": "4px", "textTransform": "uppercase", "letterSpacing": "0.07em"}),
                            html.Div(
                                "Standard fantasy rankings treat a player who scored 20 pts "
                                "in 38 minutes the same as one who scored 20 pts in 22 minutes. "
                                "The screener weights each stat by minutes played, then "
                                "sorts by the selected category — surfacing efficient players.",
                                style={"fontSize": "12px", "color": "var(--text-muted)", "lineHeight": "1.6"},
                            ),
                        ]),
                    ],
                ),
            ],
        ),

    ],
)
