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


def _method_entry(title: str, color: str, text: str) -> html.Div:
    return html.Div([
        html.Div(title, style={"fontSize": "11px", "color": color, "marginBottom": "4px",
                               "textTransform": "uppercase", "letterSpacing": "0.07em"}),
        html.Div(text, style={"fontSize": "12px", "color": "var(--text-muted)", "lineHeight": "1.6"}),
    ])


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
                    "Points forecasts that account for whether a player will "
                    "suit up, injury return odds fitted to each absence, and a "
                    "minute-weighted free-agent screener, refreshed daily from "
                    "Basketball-Reference, ESPN and Yahoo data.",
                    className="landing-subtitle",
                ),

                # Tech pills
                html.Div(
                    className="landing-pills",
                    children=[
                        html.Span("XGBoost · Temporal Fusion Transformer (TFT) · DeepAR · ARIMA",
                                  className="pill-accent"),
                        html.Span("Survival models fitted per injury",    className="pill"),
                        html.Span("Minute-weighted free-agent screener",  className="pill"),
                        html.Span("ESPN + Yahoo leagues",                 className="pill"),
                        html.Span("Python · Dash · MySQL · MLflow · AWS", className="pill"),
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
                            html.Button("Points Forecasts", className="btn-secondary"),
                            href="/apps/fantasy-predictions",
                        ),
                        dcc.Link(
                            html.Button("My Team", className="btn-secondary"),
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
                    title="Points forecasting",
                    description=(
                        "Points for each rostered player's next five team games, "
                        "from a field of competing models: simple baselines, ARIMA "
                        "and other time-series models, XGBoost, and the TFT and "
                        "DeepAR deep-learning models. A separate model estimates "
                        "whether he plays each game, so the page shows points if "
                        "he plays and expected points."
                    ),
                ),
                _feature_card(
                    icon="🔍",
                    icon_class="fi-blue",
                    title="Free agent screener",
                    description=(
                        "Rank the waiver wire on minute-weighted production, a view "
                        "ESPN and Yahoo do not offer. Every stat is colored by how "
                        "the player ranks among free agents. A \"My needs\" view "
                        "re-ranks on the categories your roster is weakest in. "
                        "Click a player to compare him with your weakest rostered "
                        "player at his position."
                    ),
                ),
                _feature_card(
                    icon="🏥",
                    icon_class="fi-green",
                    title="Injury survival analysis",
                    description=(
                        "How many more days will he be out? Several survival models "
                        "compete on recent seasons, and the winner draws a return "
                        "curve for each type of injury. Each injured player also "
                        "gets a curve fitted to his own absence: surgery, stated "
                        "timeline, age, injury history and minutes. Data from Pro "
                        "Sports Transactions."
                    ),
                ),
                _feature_card(
                    icon="📊",
                    icon_class="fi-amber",
                    title="Team performance dashboard",
                    description=(
                        "My roster across all 12 fantasy categories, colored against "
                        "league rotation players, plus how many players can fill "
                        "each lineup slot. Weekly trends, game-by-game form, a hot / "
                        "cold table, and an Injuries tab with each injured player's "
                        "return curve."
                    ),
                ),
                _feature_card(
                    icon="🤖",
                    icon_class="fi-blue",
                    title="Model scoreboard and monitoring",
                    description=(
                        "Every model is scored on each player's recent games before "
                        "it can win. The champion is the best model across the "
                        "roster; a player switches only when a statistical test "
                        "shows his own best is really better. Live accuracy is "
                        "checked against that score every week, with a badge on "
                        "the page."
                    ),
                ),
                _feature_card(
                    icon="🗄️",
                    icon_class="fi-green",
                    title="Nightly data pipeline",
                    description=(
                        "Every morning an automated run loads last night's box "
                        "scores from Basketball-Reference, ESPN rosters, positions "
                        "and injury statuses, and new injury transactions, then "
                        "refits the models. Data lives in MySQL on AWS; models are "
                        "versioned in MLflow and backed up to S3."
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
                        _method_entry(
                            "Forecasting approach", "var(--accent)",
                            "Every model is refit at each of a player's recent games "
                            "and forecasts his team's next five, so it is only ever "
                            "scored on games it hadn't seen. Machine-learning models "
                            "train only on games before each cutoff. A "
                            "chance-of-playing model, capped by today's ESPN injury "
                            "status, turns points if he plays into expected points.",
                        ),
                        _method_entry(
                            "Minute-weighted ranking", "var(--info)",
                            "A 6-minute garbage-time game shouldn't count as much as "
                            "a 34-minute start. The screener averages each stat per "
                            "game with every game weighted by minutes played, so the "
                            "numbers reflect what a player does when he gets real "
                            "minutes. Each column is ranked against other free "
                            "agents, and shooting percentages are ranked by volume, "
                            "so 1-for-1 doesn't top the list.",
                        ),
                        _method_entry(
                            "Injury modeling", "var(--accent)",
                            "Absences are rebuilt from the injury transaction log: an "
                            "absence opens when a player is ruled out and closes at "
                            "his next game. Notes are sorted into body region and "
                            "injury type by rules, with Claude for the few the rules "
                            "miss. Models train on older seasons, are scored on "
                            "recent ones, and count in-season days only.",
                        ),
                        _method_entry(
                            "Monitoring", "var(--info)",
                            "Every logged forecast is scored once its game is played "
                            "and compared with the accuracy its backtest promised, "
                            "measured against a naive forecast so a hard week for "
                            "everyone doesn't look like drift. Injury curves are "
                            "checked weekly against recent returns. An alert in "
                            "either flips the page badge to drifting.",
                        ),
                    ],
                ),
            ],
        ),

    ],
)
