# Turbofan maintenance analytics

A small end-to-end analytics project on run-to-failure engine data: SQL for data quality and feature
engineering, Python for remaining-useful-life (RUL) forecasts with uncertainty intervals, and a
cost-based replacement rule built on those forecasts, delivered as a dashboard.

Maintenance analytics from sensor history:

Data: NASA C-MAPSS turbofan degradation simulation, subset FD001 (100 training engines run to failure,
100 test engines cut off before failure, single operating condition, single fault mode). See `data/DATA_SOURCE.md`.

## Process

1. **Load** the raw text files into SQLite (`src/build_db.py`, schema in `sql/01_schema.sql`).
2. **Profile in SQL** (`sql/02_queries.sql`): cycle continuity, nulls, per-channel variance, fleet lifetimes
   with `NTILE`, and channel means by life stage. Channels with no usable drift are dropped (10 of 24 here,
   chosen by a drift score computed from the SQL output, not by hand).
3. **Build features in SQL** (`src/features.py` generates `outputs/features.sql`): 10- and 30-cycle rolling means
   per channel, each minus that engine's own first-20-cycle baseline, using window functions.
4. **Model** (`src/model.py`): gradient-boosted quantile regressors for the 10th, 50th and 90th percentile of RUL,
   RUL capped at 125 cycles for training. Out-of-fold predictions use `GroupKFold` by engine so no engine
   appears in both training and validation.
5. **Decide** (`src/decision.py`): replace an engine when its P10 remaining-life bound falls to a threshold.
   Compared with run-to-failure and the best fixed replacement age under an assumed cost model.
6. **Report**: `app.py` (Streamlit, interactive) and `src/make_dashboard.py` (single static HTML page).

## Start Here

```bash
pip install -r requirements.txt
python -m src.build_db        # builds data/turbofan.db from data/raw
python -m src.model           # trains, evaluates, writes outputs/
python -m src.make_dashboard  # writes outputs/dashboard.html
streamlit run app.py          # interactive version
```

Requires Python 3.9+ and SQLite 3.25+ (window functions), which ships with current Python.

## Results from one run (FD001)

| Measure | Value |
|---|---|
| Test RMSE vs true RUL, 100 held-out engines | 13.4 cycles |
| Test MAE | 10.4 cycles |
| Test RMSE for the 25 engines within 30 cycles of failure | 9.4 cycles |
| NASA asymmetric score (lower is better) | 271.6 |
| Coverage of the 80% (P10 to P90) interval | 73% |

The intervals are too narrow: they contain the true value for 73% of held-out engines against an 80% target.
A calibration step (for example conformal adjustment of the quantiles) is the obvious next improvement.

Maintenance rule, assuming a failure costs 10 times a planned replacement (all four ratios tested are in
`outputs/policy_sweep.csv`): the cheapest threshold on the out-of-fold simulation was a P10 bound of 15 cycles,
with 0 failures, 88% of engine life used, and a cost of 0.0055 per operating cycle against 0.0079 for the best
fixed replacement age (126 cycles) and 0.0485 for run-to-failure.

## Limitations

- The cost figures are assumptions, not data. The threshold is selected on the same simulation it is scored on,
  so the improvement over fixed-age replacement is optimistic. A fair estimate needs a separate set of engines.
- FD001 has one operating condition and one fault mode. The other C-MAPSS subsets (FD002 to FD004) add both,
  and this feature set would need operating-condition normalisation to handle them.
- Simulated engines with clean sensor channels are far tidier than real maintenance records, which are
  dominated by work-order history, free-text notifications and missing data. This project covers the
  sensor-degradation side only.
- No code here has been tuned beyond a first reasonable configuration.

## Layout

```
app.py                  Streamlit dashboard
sql/01_schema.sql       tables and views
sql/02_queries.sql      named analysis queries
src/build_db.py         load raw files into SQLite
src/features.py         channel selection and SQL window features
src/model.py            quantile models, evaluation, outputs
src/decision.py         replacement-rule simulation
src/viz.py              figures shared by both dashboards
src/make_dashboard.py   static HTML report
outputs/                metrics, predictions, dashboard.html
```
