"""
Deep-learning challengers for the points forecast: Temporal Fusion Transformer (TFT) and DeepAR, one
model of each per position group (PG/SG/SF/PF/C), the same segmentation as XGB. Used by
pipeline/points_forecast.py. Library: pytorch-forecasting 1.4 (torch 2.8, lightning 2.6), installed in
basketball-env-useme-v11052026.

Data
    One series per player, one step per game played (not per calendar day): regular season, 3 seasons
    back, the same games as XGB. A player eligible at several positions is in each of those groups'
    training data, and gets the mean of those models' quantiles.

    known (decoder) inputs  home, rest, b2b, opp_def, opp_pace, min_lag5, tm_out_usg (+ relative time index)
    observed (encoder)      TFT:    points, minutes, fga, fta, fg3a, usage, gap_before, started,
                                    games_on_team
                            DeepAR: points only (its RNN takes the same inputs in encoder and decoder,
                                    so nothing else can be observed-only)
    static                  slug (an embedding; a player the model hasn't seen gets the "unknown" one)

    min_lag5 is the player's minutes EWM through the game 5 games before the target game, so it is
    known at the origin for all 5 horizons and no future minutes leak in (XGB and ARIMAX use the EWM at
    the origin instead). opp_def / opp_pace are as of the day before each game: a few days' look-ahead
    for horizons 2-5, the same as ARIMAX's backtest. tm_out_usg (teammates out, forecast_models) is taken as
    known at the origin and carried to all 5 decoder steps, in the backtest and the forecast. usage is the
    usage share of team possessions; started = top 5 on his team in minutes that game; games_on_team counts
    games since his last team change (capped at 40).

Models
    TFT     QuantileLoss at 10/50/90; point forecast = the median (MAE-optimal, like XGB's absolute loss)
    DeepAR  negative binomial likelihood (points are counts); 200 sample paths -> 10/50/90 quantiles
    Target scaling is per window, from that window's own history (FlooredEncoderNormalizer): TFT
    standardises (mean / std), DeepAR divides by the mean (the negative binomial needs a scale-only
    normaliser). A fixed per-player scale (GroupNormalizer, SPEC 1) froze each player's level at the
    training date, which a backtest model up to a year old, or a role change, made stale. The scale has
    a floor of 1 point, so a scoreless stretch can't divide by zero.

Backtest
    Same rules as XGB: per position, backtest models at the cutoffs from
    forecast_models.backtest_cutoffs (up to 3), each trained only on games on or before its cutoff. Each
    player is scored by the model with the newest cutoff at or before their own safe cutoff. Each origin
    is scored as one window: up to ENC_LEN games of history and the next 5 games. The final model is
    trained on everything and forecasts the schedule.

Training and cache
    Validation = windows whose first forecast game is in the last 10% of dates; early stopping on it.
    Models are cached in mlflow/deep_cache/ (gitignored with mlflow/): {tft,deepar}_<POS>_final and
    _backtest<k>, k = the cutoff's slot. A cached model is reused unless it is RETRAIN_DAYS old, SPEC
    changed, or (backtest) the cutoff it was trained to is later than its slot's cutoff today, which would
    leak scored games. Daily runs then only predict (a few minutes).
"""
import datetime as dt
import json
import logging
import os
import shutil
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from pytorch_forecasting.data import EncoderNormalizer

from pipeline.forecast_models import H, POSITIONS, newest_cutoff

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / 'mlflow' / 'deep_cache'

DEEP_MODELS = {'TFT': ('Temporal Fusion Transformer', 'dl'), 'DEEPAR': ('DeepAR (neg. binomial)', 'dl')}
SPEC = 3                     # bump when inputs or architecture change: forces a retrain of every cached model
                             # 3 (2026-11-20): usage share, DRtg opp_def, tm_out_usg, started, games_on_team,
                             #   team-game backtest windows
ENC_LEN, MIN_ENC = 30, 5     # games of history per window
QUANTILES = [0.1, 0.5, 0.9]
N_SAMPLES = 200              # DeepAR sample paths per forecast
RETRAIN_DAYS = 7
MIN_ROWS = 2000              # a position group with fewer games is skipped (same rule as XGB)
KNOWN = ['home', 'rest', 'b2b', 'opp_def', 'opp_pace', 'min_lag5', 'tm_out_usg']
OBSERVED = {'TFT': ['points', 'minutes', 'fga', 'fta', 'fg3a', 'usage', 'gap_before', 'started', 'games_on_team'],
            'DEEPAR': ['points']}
HPARAMS = {
    'TFT': dict(learning_rate=0.003, hidden_size=32, attention_head_size=2, dropout=0.15,
                hidden_continuous_size=16, reduce_on_plateau_patience=3),
    'DEEPAR': dict(learning_rate=0.003, hidden_size=32, rnn_layers=2, dropout=0.1, reduce_on_plateau_patience=3),
}
TRAIN = dict(max_epochs=30, patience=4, batch_size=128, gradient_clip_val=0.1, seed=42)
INPUT_LABELS = {'points': 'points', 'minutes': 'minutes', 'fga': 'FGA', 'fta': 'FTA', 'fg3a': '3PA',
                'usage': 'usage', 'gap_before': 'days since last game', 'home': 'home', 'rest': 'rest days',
                'b2b': 'back-to-back', 'opp_def': 'opp. defence', 'opp_pace': 'opp. pace',
                'min_lag5': 'minutes (lag 5)', 'tm_out_usg': 'teammates out', 'started': 'started',
                'games_on_team': 'games on team', 'relative_time_idx': 'games ahead', 'slug': 'player',
                'encoder_length': 'history length', 'points_center': 'recent scoring level',
                'points_scale': 'recent scoring spread'}


def _quiet():
    warnings.filterwarnings('ignore')
    os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
    for n in ['lightning', 'lightning.pytorch', 'lightning.fabric', 'pytorch_lightning', 'pytorch_forecasting']:
        logging.getLogger(n).setLevel(logging.ERROR)


class FlooredEncoderNormalizer(EncoderNormalizer):
    """EncoderNormalizer (scale from each window's own history) with the scale floored at `floor` points.
    With center=False the scale is the history's mean, 0 for a scoreless stretch, and pytorch-forecasting
    adds no epsilon there; with center=True a flat history gives a near-zero std. Defined here (not inline)
    so cached checkpoints can unpickle it."""

    def __init__(self, method='standard', center=True, max_length=None, transformation=None, method_kwargs=None,
                 floor=1.0):
        super().__init__(method=method, center=center, max_length=max_length, transformation=transformation,
                         method_kwargs=method_kwargs)
        self.floor = floor

    def _set_parameters(self, y_center, y_scale):
        super()._set_parameters(y_center=y_center, y_scale=y_scale)
        self.scale_ = (self.scale_.clamp(min=self.floor) if isinstance(self.scale_, torch.Tensor)
                       else np.maximum(self.scale_, self.floor))


def _classes():
    from pytorch_forecasting import TemporalFusionTransformer, DeepAR
    return {'TFT': TemporalFusionTransformer, 'DEEPAR': DeepAR}


def _load(kind, path):
    # weights_only=False: torch 2.6+ refuses pickled loss objects otherwise. These checkpoints are only
    # ever written by this pipeline, into the gitignored mlflow/deep_cache/.
    return _classes()[kind].load_from_checkpoint(path, map_location='cpu', weights_only=False)


####################################################################################################
# 001 - DATA
####################################################################################################

def deep_frame(pg):
    """Player-game table (from forecast_models.player_games) -> one row per game with the model inputs."""
    d = pg[['slug', 'date', 'team', 'opponent', 'points', 'minutes', 'fga', 'fta', 'fg3a', 'tov', 'home', 'rest',
            'b2b', 'opp_def', 'opp_pace', 'min_ewm', 'min_lag5', 'usg_share', 'tm_out_usg', 'started',
            'games_on_team']].sort_values(['slug', 'date']).reset_index(drop=True)
    g = d.groupby('slug', sort=False)
    d['usage'] = d.pop('usg_share')              # share of team possessions used (forecast_models.player_games)
    d['gap_before'] = g['date'].diff().dt.days.clip(0, 30).fillna(30)
    d['games_on_team'] = d['games_on_team'].clip(upper=40)
    d['time_idx'] = g.cumcount().astype(int)
    d['series'] = d['slug'].astype(str)
    num = OBSERVED['TFT'] + KNOWN
    d[num] = d[num].astype('float32')
    return d


def _dataset(data, kind):
    from pytorch_forecasting import TimeSeriesDataSet
    from pytorch_forecasting.data import NaNLabelEncoder
    # no softplus: inverse-softplus maps a 0-point game to log(eps) ~ -16, which wrecks a window's mean/std
    norm = FlooredEncoderNormalizer(center=(kind == 'TFT'))
    return TimeSeriesDataSet(
        data, time_idx='time_idx', target='points', group_ids=['slug', 'series'],   # series = slug, or slug|k for a backtest window
        max_encoder_length=ENC_LEN, min_encoder_length=MIN_ENC, max_prediction_length=H, min_prediction_length=1,
        static_categoricals=['slug'], time_varying_known_reals=KNOWN, time_varying_unknown_reals=OBSERVED[kind],
        target_normalizer=norm,
        categorical_encoders={'series': NaNLabelEncoder(add_nan=True), 'slug': NaNLabelEncoder(add_nan=True)},
        add_relative_time_idx=True, add_target_scales=True, add_encoder_length=True)


def _window(enc, dec, sid):
    """One prediction window: history rows + exactly H decoder rows (short ones padded, then ignored)."""
    n_real = len(dec)
    if n_real < H:
        pad = (dec if n_real else enc).iloc[[-1] * (H - n_real)].copy()
        pad['points'] = 0.0
        dec = pd.concat([dec, pad])
    w = pd.concat([enc, dec], ignore_index=True)
    w['series'], w['time_idx'] = sid, np.arange(len(w))
    return w, n_real


def _decoder(enc, games, last):
    """Decoder rows for `games` (team games with the KNOWN inputs, from the grid or the schedule) after the
    player's history `enc`; `last` = index of his latest game in his deep frame. min_lag5 = his minutes EWM
    through game last + h - H, as if he plays every game. Observed-only columns are filled from the last
    history row (the decoder never reads them)."""
    m = enc.attrs['min_ewm']
    dec = pd.DataFrame({'slug': enc['slug'].iloc[0], 'date': games['date'].values, 'team': games['team'].values,
                        'opponent': games['opponent'].values})
    for c in KNOWN:
        if c != 'min_lag5':
            dec[c] = games[c].values
    dec['min_lag5'] = [float(m[max(last + h - H, 0)]) for h in range(1, len(dec) + 1)]
    for c in enc.columns.drop(['series', 'time_idx']):
        if c not in dec:
            dec[c] = 0.0 if c == 'points' else enc[c].iloc[-1]
    return dec[enc.columns.drop(['series', 'time_idx'])].astype(enc.dtypes.drop(['series', 'time_idx']).to_dict())


def backtest_windows(d_s, frame, origins, grid_s):
    """Windows at each backtest origin of one player. `frame` / `origins` are the runner's (the same
    origins as every other model): history through played game o-1, decoder = the team's next H games from
    his grid (forecast_models.player_grid), scored where he played."""
    pos = pd.Series(np.arange(len(d_s)), index=d_s['date'].values)
    wins, actual = [], np.full((len(origins), H), np.nan)
    for k, o in enumerate(origins):
        d = frame['date'].iloc[o - 1]
        j = int(pos[d]) + 1
        enc = d_s.iloc[max(0, j - ENC_LEN):j]
        games = grid_s[grid_s['date'] > d].head(H)
        if len(enc) < MIN_ENC or games.empty:
            continue
        enc.attrs['min_ewm'] = d_s['min_ewm'].values
        games = games.assign(tm_out_usg=float(d_s['tm_out_usg'].iloc[j - 1]))    # teammates out, as known at the origin
        w, n_real = _window(enc, _decoder(enc, games, j - 1), f'{d_s["slug"].iloc[0]}|{k}')
        actual[k, :n_real] = np.where(games['played'].values == 1, games['points'].values, np.nan)
        wins.append(w)
    return wins, actual


def live_window(d_s, fut):
    """History through the latest game + the team's next games from the schedule (runner's future_rows)."""
    enc = d_s.iloc[-ENC_LEN:]
    if len(enc) < MIN_ENC:
        return None
    enc.attrs['min_ewm'] = d_s['min_ewm'].values
    w, _ = _window(enc, _decoder(enc, fut.head(H), len(d_s) - 1), f'{d_s["slug"].iloc[0]}|live')
    return w


####################################################################################################
# 002 - TRAIN / LOAD
####################################################################################################

def train(kind, data, tag, log):
    """Fit one model on `data` (deep_frame rows of one position group). -> (model, info)."""
    import lightning.pytorch as pl
    from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint
    from pytorch_forecasting.metrics import QuantileLoss, NegativeBinomialDistributionLoss
    _quiet()
    pl.seed_everything(TRAIN['seed'], workers=True)
    t0 = time.time()
    ds = _dataset(data, kind)
    di = ds.decoded_index
    date_of = data.set_index(['series', 'time_idx'])['date']
    first = date_of.reindex(pd.MultiIndex.from_arrays([di['series'], di['time_idx_first_prediction']])).values
    last = date_of.reindex(pd.MultiIndex.from_arrays([di['series'], di['time_idx_last']])).values
    cut = data['date'].quantile(0.9)
    tr = ds.filter(lambda _: last < cut)
    va = ds.filter(lambda _: first >= cut)
    tr_dl = tr.to_dataloader(train=True, batch_size=TRAIN['batch_size'], num_workers=0)
    va_dl = va.to_dataloader(train=False, batch_size=512, num_workers=0)

    cls = _classes()[kind]
    loss = (QuantileLoss(QUANTILES) if kind == 'TFT' else NegativeBinomialDistributionLoss(quantiles=QUANTILES))
    model = cls.from_dataset(tr, loss=loss, log_interval=-1, **HPARAMS[kind])
    tmp = CACHE_DIR / 'tmp'
    shutil.rmtree(tmp, ignore_errors=True)
    ck = ModelCheckpoint(dirpath=tmp, filename=tag, monitor='val_loss', mode='min', save_top_k=1)
    es = EarlyStopping(monitor='val_loss', patience=TRAIN['patience'], mode='min')
    trainer = pl.Trainer(max_epochs=TRAIN['max_epochs'], accelerator='cpu', devices=1,   # MPS was >10x slower here
                         gradient_clip_val=TRAIN['gradient_clip_val'], callbacks=[es, ck], logger=False,
                         enable_progress_bar=False, enable_model_summary=False)
    trainer.fit(model, train_dataloaders=tr_dl, val_dataloaders=va_dl)
    best = _load(kind, ck.best_model_path)
    os.replace(ck.best_model_path, CACHE_DIR / f'{tag}.ckpt')
    shutil.rmtree(tmp, ignore_errors=True)

    q, _, _ = _predict(best, kind, va_dl)
    yv, lens = _targets(va_dl)
    mask = np.arange(H)[None, :] < lens[:, None]
    val_mae = float(np.abs(q[:, :, 1] - yv)[mask].mean())
    cov = float(((yv >= q[:, :, 0]) & (yv <= q[:, :, 2]))[mask].mean())
    return best, {'val_loss': float(ck.best_model_score), 'val_mae': val_mae, 'val_cov80': cov,
                  'epochs': int(trainer.current_epoch), 'n_train': len(tr), 'n_val': len(va),
                  'n_players': int(data['slug'].nunique()), 'train_seconds': round(time.time() - t0, 1)}


def _targets(dl):
    ys, lens = [], []
    for x, y in dl:
        ys.append(y[0].numpy())
        lens.append(x['decoder_lengths'].numpy())
    return np.concatenate(ys), np.concatenate(lens)


def get_model(kind, pos, role, data, cutoff, mode, log):
    """Cached model unless stale (see module docstring); otherwise train and cache. -> (model, meta)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tag = f'{kind.lower()}_{pos}_{role}'
    path, meta_path = CACHE_DIR / f'{tag}.ckpt', CACHE_DIR / f'{tag}.json'
    meta = json.loads(meta_path.read_text()) if meta_path.exists() and path.exists() else None
    today = dt.date.today()
    leak = meta is not None and cutoff is not None and pd.Timestamp(meta['cutoff']) > cutoff
    old = meta is not None and (today - dt.date.fromisoformat(meta['trained'])).days >= RETRAIN_DAYS
    if meta is not None and meta.get('spec') == SPEC and not leak and mode != 'retrain' and (mode == 'load' or not old):
        return _load(kind, path), dict(meta, trained_now=False)
    why = ('forced' if mode == 'retrain' else 'no cache' if meta is None else 'spec changed'
           if meta.get('spec') != SPEC else 'cutoff moved earlier' if leak else f'{RETRAIN_DAYS}+ days old')
    log(f'  {kind} {pos} {role}: training ({why}) on {len(data):,} games …')
    model, info = train(kind, data, tag, log)
    meta = {**info, 'spec': SPEC, 'trained': str(today), 'cutoff': str(cutoff.date()) if cutoff is not None else None,
            'last_game': str(data['date'].max().date())}
    meta_path.write_text(json.dumps(meta, indent=1))
    log(f'  {kind} {pos} {role}: val MAE {info["val_mae"]:.2f}, 80% coverage {info["val_cov80"]:.0%}, '
        f'{info["epochs"] + 1} epochs, {info["train_seconds"]:.0f}s')
    return model, dict(meta, trained_now=True)


####################################################################################################
# 003 - PREDICT
####################################################################################################

# passed as a fresh copy every call: predict() setdefault()s its callback into the dict it is given
TRAINER_KW = dict(accelerator='cpu', logger=False, enable_progress_bar=False, enable_model_summary=False)


def _predict(model, kind, dl, interpret=False):
    """-> quantiles (n, H, 3) in points, index DataFrame (series, time_idx), TFT variable weights or None."""
    if kind == 'TFT':
        p = model.predict(dl, mode='raw', return_index=True, trainer_kwargs=dict(TRAINER_KW))
        q = p.output['prediction'].cpu().numpy()
        imp = None
        if interpret:
            it = model.interpret_output(p.output, reduction='none')
            imp = {part: (getattr(model, f'{part}_variables'), it[f'{part}_variables'].cpu().numpy())
                   for part in ['encoder', 'decoder']}
        return q, p.index, imp
    p = model.predict(dl, mode='quantiles', return_index=True, trainer_kwargs=dict(TRAINER_KW), n_samples=N_SAMPLES)
    return p.output.cpu().numpy(), p.index, None


def predict_windows(model, kind, wins, interpret=False):
    """Windows built by backtest_windows / live_window -> {series id: (H, 3) quantiles}, importances."""
    from pytorch_forecasting import TimeSeriesDataSet
    df = pd.concat(wins, ignore_index=True)
    ds = TimeSeriesDataSet.from_parameters(model.dataset_parameters, df, predict=True, stop_randomization=True)
    q, index, imp = _predict(model, kind, ds.to_dataloader(train=False, batch_size=256, num_workers=0), interpret)
    sids = index['series'].values
    out = {sid: np.sort(q[i], axis=1) for i, sid in enumerate(sids)}      # quantiles kept non-crossing
    imps = None
    if imp is not None:
        imps = {sid: {part: dict(zip(names, w[i] / max(w[i].sum(), 1e-9))) for part, (names, w) in imp.items()}
                for i, sid in enumerate(sids)}
    return out, imps


def _top(weights, n=3):
    return ' · '.join(f'{INPUT_LABELS.get(k, k)} {v:.0%}' for k, v in sorted(weights.items(), key=lambda kv: -kv[1])[:n])


####################################################################################################
# 004 - RUN (called by points_forecast)
####################################################################################################

def run(pg, groups, roster_frames, roster_groups, futs, origins_of, needed, cutoffs, mode, log, grids):
    """Backtest + forecast TFT and DeepAR for the rostered players.

    Returns {model: {'errors': {slug: (n_origins, H)}, 'preds': {slug: (n_origins, H)}, 'forecast': {slug: (h,)},
             'band': {slug: (lo, hi)},
             'hits': {slug: (in, n)}, 'params': {slug: dict}}}, and {model: {pos: (fitted model, meta)}}."""
    _quiet()
    torch.set_num_threads(max(1, (os.cpu_count() or 4) - 1))
    data = deep_frame(pg)
    by_slug = {s: g.reset_index(drop=True) for s, g in data[data['slug'].isin(roster_frames)].groupby('slug')}
    bt, actual, live = {}, {}, {}
    for s, frame in roster_frames.items():
        if s not in by_slug:
            continue
        bt[s], actual[s] = backtest_windows(by_slug[s], frame, origins_of[s], grids[s])
        w = live_window(by_slug[s], futs[s])
        if w is not None:
            live[s] = w

    out, fitted = {}, {}
    for kind in DEEP_MODELS:
        bt_q, live_q, imps, metas, bt_cut = {}, {}, {}, {}, {}
        for pos in POSITIONS:
            members = {s for s, g in groups.items() if pos in g}
            dpos = data[data['slug'].isin(members)]
            need = [s for s, g in roster_groups.items() if pos in g and s in by_slug]
            if len(dpos) < MIN_ROWS:
                log(f'  {kind} {pos}: only {len(dpos)} games, skipped')
                continue
            slots = sorted({cutoffs.index(c) for c in (newest_cutoff(needed.get(s), cutoffs) for s in need)
                            if c is not None})
            try:
                bt_models = {}                           # trained-to cutoff -> model
                for k in slots:
                    c = cutoffs[k]
                    m, mt = get_model(kind, pos, f'backtest{k}', dpos[dpos['date'] <= c], c, mode, log)
                    bt_models[pd.Timestamp(mt['cutoff'])] = m
                model, meta = get_model(kind, pos, 'final', dpos, None, mode, log)
            except Exception as e:                       # a failed group must not sink the whole run
                log(f'  {kind} {pos}: FAILED {type(e).__name__}: {e}')
                continue
            fitted.setdefault(kind, {})[pos] = (model, meta)
            metas[pos] = meta
            use = {s: newest_cutoff(needed.get(s), list(bt_models)) for s in need}   # newest safe model
            for c, bt_model in bt_models.items():
                mine = [s for s in need if use[s] == c and bt[s]]
                if not mine:
                    continue
                pred, _ = predict_windows(bt_model, kind, [w for s in mine for w in bt[s]])
                for s in mine:
                    arr = np.full((len(origins_of[s]), H, 3), np.nan)
                    for k in range(len(origins_of[s])):
                        if f'{s}|{k}' in pred:
                            arr[k] = pred[f'{s}|{k}']
                    bt_q.setdefault(s, []).append(arr)
                    bt_cut.setdefault(s, set()).add(str(c.date()))
            lw = [live[s] for s in need if s in live]
            if lw:
                pred, imp = predict_windows(model, kind, lw, interpret=(kind == 'TFT'))
                for s in need:
                    if f'{s}|live' in pred:
                        live_q.setdefault(s, []).append(pred[f'{s}|live'])
                        if imp:
                            imps.setdefault(s, []).append(imp[f'{s}|live'])
        res = {'errors': {}, 'preds': {}, 'forecast': {}, 'band': {}, 'hits': {}, 'params': {}}
        for s in bt_q.keys() | live_q.keys():
            pos_used = [p for p in POSITIONS if p in roster_groups[s] and p in metas]
            prm = {'positions': ','.join(pos_used),
                   **{f'{p}_val_mae': round(metas[p]['val_mae'], 3) for p in pos_used},
                   'trained': max(metas[p]['trained'] for p in pos_used) if pos_used else None,
                   'backtest_cutoff': ','.join(sorted(bt_cut.get(s, ()))) or None}
            if s in bt_q:
                q = np.nanmean(np.stack(bt_q[s]), axis=0)          # several groups: mean of their quantiles
                a = actual[s]
                ok = np.isfinite(a) & np.isfinite(q[:, :, 1])
                res['errors'][s] = np.where(ok, a - q[:, :, 1], np.nan)
                res['preds'][s] = q[:, :, 1]
                res['hits'][s] = (int(((a >= q[:, :, 0]) & (a <= q[:, :, 2]) & ok).sum()), int(ok.sum()))
            if s in live_q:
                n = len(futs[s].head(H))
                q = np.mean(np.stack(live_q[s]), axis=0)[:n]
                res['forecast'][s], res['band'][s] = q[:, 1], (q[:, 0], q[:, 2])
            if s in imps:
                for part in ['encoder', 'decoder']:
                    keys = imps[s][0][part].keys()
                    prm[f'top_{part}'] = _top({k: float(np.mean([i[part][k] for i in imps[s]])) for k in keys})
            res['params'][s] = prm
        out[kind] = res
    return out, fitted


def coverage(hits):
    """Pooled share of backtest actuals inside the model's own 80% range."""
    i, n = map(sum, zip(*hits.values())) if hits else (0, 0)
    return i / n if n else np.nan
