"""Select informative channels with SQL-derived drift statistics, then build window features in SQL."""
import numpy as np
import pandas as pd
from .config import BASELINE_CYCLES, DRIFT_THRESHOLD
from .sqlrun import run


def drift_table(con):
    """Per-channel drift score: |late-life mean - early-life mean| / early-life SD.

    Channels with (near) zero variance are excluded outright.
    """
    prof = run("dq_sensor_profile", con).set_index("sensor")
    stages = run("drift_by_life_stage", con)
    early = stages[stages.stage == 0].set_index("sensor")
    late = stages[stages.stage == stages.stage.max()].set_index("sensor")
    out = pd.DataFrame({
        "early_mean": early.mean_value,
        "late_mean": late.mean_value,
        "early_sd": np.sqrt(early.variance.clip(lower=0)),
        "total_variance": prof.variance,
    })
    out["drift_score"] = (out.late_mean - out.early_mean).abs() / out.early_sd.replace(0, np.nan)
    out["selected"] = (out.total_variance > 1e-6) & (out.drift_score >= DRIFT_THRESHOLD)
    return out.sort_values("drift_score", ascending=False)


def build_features_sql(sensors, base=BASELINE_CYCLES):
    """Rolling-window features per engine: 10- and 30-cycle means minus the engine's own baseline."""
    base_cols = ",\n        ".join(f"AVG({s}) AS b_{s}" for s in sensors)
    feat_cols = ",\n    ".join(
        f"AVG(c.{s}) OVER w10 - b.b_{s} AS {s}_d10,\n    AVG(c.{s}) OVER w30 - b.b_{s} AS {s}_d30"
        for s in sensors)
    return f"""WITH base AS (
    SELECT split, unit,
        {base_cols}
    FROM cycles
    WHERE cycle <= {base}
    GROUP BY split, unit
)
SELECT c.split, c.unit, c.cycle,
    {feat_cols}
FROM cycles c
JOIN base b ON b.split = c.split AND b.unit = c.unit
WINDOW
    w10 AS (PARTITION BY c.split, c.unit ORDER BY c.cycle ROWS BETWEEN 9 PRECEDING AND CURRENT ROW),
    w30 AS (PARTITION BY c.split, c.unit ORDER BY c.cycle ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
ORDER BY c.split, c.unit, c.cycle;"""


def load_features(con, sensors):
    sql = build_features_sql(sensors)
    return pd.read_sql_query(sql, con), sql
