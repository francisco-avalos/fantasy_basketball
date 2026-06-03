"""
ai_chatbox.py
─────────────
AI assistant module for the Fantasy Basketball Analytics dashboard.

Builds a context string from live DataFrames already loaded in callbacks.py
and sends it + the user's question to the Anthropic API.

Usage
-----
1.  pip install anthropic
2.  Set the environment variable:
        export ANTHROPIC_API_KEY="sk-ant-..."
    (On Heroku: heroku config:set ANTHROPIC_API_KEY=sk-ant-...)
3.  Import and wire up the layout / callback (see ai_layout_snippet.py and
    ai_callback_snippet.py in this same PR).
"""

import os
import datetime as dt
import anthropic
import pandas as pd


# ── Anthropic client (key read from env) ──────────────────────────────────────

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL  = "claude-haiku-4-5-20251001"       # alternative - claude-opus-4-20250514


# ── Context builders ──────────────────────────────────────────────────────────

def _fmt_df(df: pd.DataFrame, max_rows: int = 20) -> str:
    """Return a compact string representation of a DataFrame."""
    return df.head(max_rows).to_string(index=False)


def build_context(
    fa_espn_df:           pd.DataFrame,
    fa_yahoo_df:          pd.DataFrame,
    myteam_df:            pd.DataFrame,
    my_live_espn_df:      pd.DataFrame,
    my_live_yahoo_df:     pd.DataFrame,
    model_eval_pred_df:   pd.DataFrame,
    injury_probabilities_df: pd.DataFrame,
    days_back: int = 14,
) -> str:
    """
    Assemble a concise but information-dense context block that the LLM
    can reason over.  Keep it under ~3 000 tokens so the prompt stays cheap.
    """
    today      = dt.date.today()
    cutoff     = today - dt.timedelta(days=days_back)

    # ── Free agents (ESPN) – last N days, weighted avg key stats ──────────────
    stat_cols = [
        "name", "made_field_goals", "made_three_point_field_goals",
        "made_free_throws", "total_rebounds", "assists",
        "steals", "blocks", "turnovers", "points_scored", "minutes_played",
    ]
    imps = [c for c in stat_cols if c not in ("name",)]

    def weighted_avg(df: pd.DataFrame) -> pd.DataFrame:
        recent = df[df["date"] >= cutoff].copy() if "date" in df.columns else df.copy()
        if recent.empty:
            return pd.DataFrame()
        grouped = (
            recent.groupby("name")
            .apply(
                lambda x: pd.Series(
                    {
                        v: (
                            (x[v] * x["minutes_played"]).sum() / x["minutes_played"].sum()
                            if x["minutes_played"].sum() > 0
                            else 0
                        )
                        for v in imps
                        if v in x.columns
                    }
                )
            )
            .reset_index()
        )
        return grouped.sort_values("points_scored", ascending=False).head(20)

    espn_top = weighted_avg(fa_espn_df)  if not fa_espn_df.empty  else pd.DataFrame()
    yahoo_top = weighted_avg(fa_yahoo_df) if not fa_yahoo_df.empty else pd.DataFrame()

    # ── My roster ─────────────────────────────────────────────────────────────
    roster_espn  = my_live_espn_df[["name"]].drop_duplicates() if not my_live_espn_df.empty  else pd.DataFrame()
    roster_yahoo = my_live_yahoo_df[["name"]].drop_duplicates() if not my_live_yahoo_df.empty else pd.DataFrame()

    # ── My team stats (season) – weighted avg ─────────────────────────────────
    myteam_stat_cols = [
        "name", "points", "assists", "total_rebounds", "steals",
        "blocks", "turnovers", "made_three_point_field_goals", "minutes_played",
    ]
    myteam_imps = [c for c in myteam_stat_cols if c not in ("name",) and c in myteam_df.columns]

    if not myteam_df.empty and myteam_imps:
        myteam_agg = (
            myteam_df.groupby("name")
            .apply(
                lambda x: pd.Series(
                    {
                        v: (
                            (x[v] * x["minutes_played"]).sum() / x["minutes_played"].sum()
                            if "minutes_played" in x.columns and x["minutes_played"].sum() > 0
                            else 0
                        )
                        for v in myteam_imps
                    }
                )
            )
            .reset_index()
        )
        myteam_agg = myteam_agg.sort_values("points", ascending=False) if "points" in myteam_agg.columns else myteam_agg
    else:
        myteam_agg = pd.DataFrame()

    # ── Predictions (champion model, next 5 days) ─────────────────────────────
    if not model_eval_pred_df.empty and "champion_model" in model_eval_pred_df.columns:
        preds_top = model_eval_pred_df[model_eval_pred_df["champion_model"] == 1][
            ["slug", "day", "predictions", "league"]
        ].head(30)
    else:
        preds_top = model_eval_pred_df.head(30) if not model_eval_pred_df.empty else pd.DataFrame()

    # ── Injury probabilities ──────────────────────────────────────────────────
    inj_sample = injury_probabilities_df.head(15) if not injury_probabilities_df.empty else pd.DataFrame()

    # ── Assemble ──────────────────────────────────────────────────────────────
    sections = [
        f"Today's date: {today}",
        f"Stats window: last {days_back} days",
        "",
        "=== MY ESPN ROSTER ===",
        _fmt_df(roster_espn)  if not roster_espn.empty  else "(no data)",
        "",
        "=== MY YAHOO ROSTER ===",
        _fmt_df(roster_yahoo) if not roster_yahoo.empty else "(no data)",
        "",
        "=== MY TEAM — SEASON WEIGHTED AVERAGES (ESPN) ===",
        _fmt_df(myteam_agg)   if not myteam_agg.empty   else "(no data)",
        "",
        f"=== TOP FREE AGENTS — ESPN (last {days_back} days, min-weighted avg) ===",
        _fmt_df(espn_top)     if not espn_top.empty      else "(no data)",
        "",
        f"=== TOP FREE AGENTS — YAHOO (last {days_back} days, min-weighted avg) ===",
        _fmt_df(yahoo_top)    if not yahoo_top.empty     else "(no data)",
        "",
        "=== MODEL PREDICTIONS (next 5 games, champion model) ===",
        _fmt_df(preds_top)    if not preds_top.empty     else "(no data)",
        "",
        "=== INJURY PROBABILITY SAMPLES ===",
        _fmt_df(inj_sample)   if not inj_sample.empty    else "(no data)",
    ]

    return "\n".join(sections)


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert fantasy basketball analyst assistant embedded inside a
Fantasy Basketball Analytics dashboard. The dashboard owner gives you live
statistical context (free agents, roster stats, model predictions, injury
probabilities) and asks questions about their teams and decisions.

Guidelines:
- Be concise, direct, and data-driven.
- Reference specific player names and numbers from the context when relevant.
- If the data doesn't cover something, say so rather than guess.
- Use fantasy basketball scoring conventions (points, rebounds, assists, steals,
  blocks, 3-pointers, FG%, FT%, turnovers) when making recommendations.
- Format lists with bullet points for easy scanning.
"""


# ── Main call ─────────────────────────────────────────────────────────────────

def ask_ai(
    user_message:  str,
    context:       str,
    chat_history:  list[dict] | None = None,
) -> str:
    """
    Send a question + live dashboard context to Claude and return the reply.

    Parameters
    ----------
    user_message  : The user's latest question.
    context       : Output of build_context() — injected as a system-level data block.
    chat_history  : List of prior turns: [{"role": "user"|"assistant", "content": "..."}]
                    Pass None or [] for a fresh conversation.

    Returns
    -------
    The assistant's text reply.
    """
    chat_history = chat_history or []

    # Inject live data into the system prompt
    full_system = (
        SYSTEM_PROMPT
        + "\n\n=== LIVE DASHBOARD DATA ===\n"
        + context
    )

    # Build messages list: history + new user turn
    messages = chat_history + [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=full_system,
        messages=messages,
    )

    return response.content[0].text
