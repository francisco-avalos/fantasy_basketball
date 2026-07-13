import asyncio
import logging
from datetime import date
import pandas as pd
import pro_sports_transactions as pst
from pro_sports_transactions.handlers import UnflareRequestHandler, UnflareConfig

logger = logging.getLogger(__name__)

# Build the handler ONCE at import time so the Cloudflare clearance cookie is
# cached and reused across every day you query. Creating a new one per call
# would re-solve the challenge each time and throw away the speed benefit.
_handler = UnflareRequestHandler(UnflareConfig(url="http://localhost:5002/scrape"))

# ⚠️ VERIFY these names once:  print(list(pst.TransactionType))
# Adjust any that differ (e.g. if a member is "Injured List" with a space,
# reference it as pst.TransactionType["Injured List"]).
_TXN_TYPES = (
    pst.TransactionType.InjuredList,      # ILChkBx
    pst.TransactionType.Injury,           # InjuriesChkBx
    pst.TransactionType.PersonalReason,   # PersonalChkBx
    pst.TransactionType.Disciplinary,     # DisciplinaryChkBx
    pst.TransactionType.LegalIncident,    # LegalChkBx
)

_COLS = ["date", "team", "acquired", "relinquished", "notes"]

# --- retry tuning -----------------------------------------------------------
_MAX_RETRIES = 4          # attempts per page before giving up
_BASE_DELAY = 2.0         # seconds; grows 2 -> 4 -> 8 -> 16
_MAX_DELAY = 30.0         # cap so backoff never sleeps absurdly long


async def _fetch_page(d: date, starting_row: int) -> pd.DataFrame:
    """Fetch one page (25 rows) with exponential backoff on transient failure."""
    last_err = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return await pst.Search(
                league=pst.League.NBA,
                transaction_types=_TXN_TYPES,
                start_date=d,
                end_date=d,
                starting_row=starting_row,
                request_handler=_handler,
            ).get_dataframe()
        except Exception as e:  # narrow this once you've seen the real error types
            last_err = e
            if attempt == _MAX_RETRIES:
                break
            delay = min(_BASE_DELAY * (2 ** (attempt - 1)), _MAX_DELAY)
            logger.warning(
                "Fetch failed for %s row %d (attempt %d/%d): %s — retrying in %.0fs",
                d, starting_row, attempt, _MAX_RETRIES, e, delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError(
        f"Giving up on {d} row {starting_row} after {_MAX_RETRIES} attempts"
    ) from last_err


def day_injuries_basketball(day) -> pd.DataFrame:
    """All NBA injury/discipline/legal transactions for a single day.

    `day` accepts a 'YYYY-MM-DD' string or a datetime.date.
    Returns columns: date, team, acquired, relinquished, notes.
    """
    d = day if isinstance(day, date) else date.fromisoformat(str(day))

    async def _fetch_all() -> pd.DataFrame:
        frames = []
        starting_row = 0
        while True:
            df = await _fetch_page(d, starting_row)
            if df is None or df.empty:
                break
            frames.append(df)

            total_pages = df.attrs.get("pages", 1)   # site serves 25 rows/page
            current_page = starting_row // 25 + 1
            if current_page >= total_pages:
                break
            starting_row += 25

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_COLS)

    raw = asyncio.run(_fetch_all())
    if raw.empty:
        return pd.DataFrame(columns=_COLS)

    # library returns capitalized columns -> match your old lowercase names
    raw = raw.rename(columns={
        "Date": "date", "Team": "team", "Acquired": "acquired",
        "Relinquished": "relinquished", "Notes": "notes",
    })[_COLS]

    # strip the leading bullet the site puts before player names
    for col in ("acquired", "relinquished"):
        raw[col] = raw[col].astype(str).str.replace("• ", "", regex=False).str.strip()

    return raw