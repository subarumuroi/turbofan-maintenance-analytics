"""Turn RUL predictions into a maintenance rule and compare it with simple baselines.

Rule: replace an engine at the first cycle (after a warm-up) where the lower prediction bound
of its remaining life (the 10th percentile) drops to or below a threshold h cycles.
Cost model (ASSUMED, not from data): a planned replacement costs 1 unit, an in-service failure
costs `cost_ratio` units. Cost is reported per operating cycle, so replacing too early is penalised
through the cycles of life that are thrown away.
"""
import numpy as np
import pandas as pd

WARMUP = 30


def _first_trigger(g, h, col="q10"):
    ok = g[(g.cycle >= WARMUP) & (g[col] <= h)]
    return int(ok.cycle.iloc[0]) if len(ok) else None


def simulate_threshold(oof, thresholds, cost_ratio):
    lifetimes = oof.groupby("unit").cycle.max()
    rows = []
    for h in thresholds:
        trig = oof.groupby("unit").apply(lambda g: _first_trigger(g, h), include_groups=False)
        planned = trig.notna() & (trig < lifetimes)
        operated = trig.where(planned, lifetimes)
        cost = planned.sum() * 1 + (~planned).sum() * cost_ratio
        rows.append({
            "threshold": h, "cost_ratio": cost_ratio,
            "failures": int((~planned).sum()),
            "planned": int(planned.sum()),
            "life_used_pct": float(100 * operated.sum() / lifetimes.sum()),
            "cost_per_cycle": float(cost / operated.sum()),
        })
    return pd.DataFrame(rows)


def baselines(oof, cost_ratio):
    """Run-to-failure and the best fixed-interval replacement age."""
    lifetimes = oof.groupby("unit").cycle.max().to_numpy()
    n = len(lifetimes)
    rtf = cost_ratio * n / lifetimes.sum()
    best = None
    for T in range(100, int(lifetimes.max()) + 1, 2):
        planned = lifetimes > T
        operated = np.where(planned, T, lifetimes)
        c = (planned.sum() + (~planned).sum() * cost_ratio) / operated.sum()
        if best is None or c < best[1]:
            best = (T, c)
    return {"run_to_failure_cost": float(rtf), "fixed_interval_age": best[0], "fixed_interval_cost": float(best[1])}


def sweep(oof, ratios=(3, 5, 10, 20), thresholds=range(0, 81, 5)):
    frames, base = [], []
    for r in ratios:
        frames.append(simulate_threshold(oof, thresholds, r))
        base.append({"cost_ratio": r, **baselines(oof, r)})
    return pd.concat(frames, ignore_index=True), pd.DataFrame(base)
