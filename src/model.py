"""Train RUL models with prediction intervals, evaluate, and write outputs.

Usage: python -m src.model
"""
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

from .config import OUT, RUL_CAP
from .features import drift_table, load_features
from .sqlrun import connect, run
from . import decision

QUANTILES = {"q10": 0.1, "q50": 0.5, "q90": 0.9}


def make_model(q):
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=300, learning_rate=0.05,
                                         max_leaf_nodes=15, min_samples_leaf=40, random_state=0)


def fit_predict(Xtr, ytr, Xte_list):
    outs = [dict() for _ in Xte_list]
    for name, q in QUANTILES.items():
        m = make_model(q).fit(Xtr, ytr)
        for o, X in zip(outs, Xte_list):
            o[name] = m.predict(X)
    result = []
    for o in outs:  # enforce non-crossing quantiles and valid range
        arr = np.sort(np.vstack([o["q10"], o["q50"], o["q90"]]), axis=0).clip(0, RUL_CAP)
        result.append(pd.DataFrame(arr.T, columns=["q10", "q50", "q90"]))
    return result


def nasa_score(pred, true):
    d = pred - true
    return float(np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1)))


def main():
    OUT.mkdir(exist_ok=True)
    con = connect()

    drift = drift_table(con)
    sensors = list(drift.index[drift.selected])
    drift.to_csv(OUT / "channel_drift.csv")
    print(f"{len(sensors)} informative channels: {sensors}")

    feats, feat_sql = load_features(con, sensors)
    (OUT / "features.sql").write_text(feat_sql)
    labels = run("train_labels", con)
    truth = run("test_fleet_truth", con)

    tr = feats[feats.split == "train"].merge(labels, on=["unit", "cycle"])
    te = feats[feats.split == "test"].reset_index(drop=True)
    fcols = [c for c in feats.columns if c not in ("split", "unit", "cycle")] + ["cycle"]
    Xtr, ytr = tr[fcols].to_numpy(), tr.rul.clip(upper=RUL_CAP).to_numpy()

    # Out-of-fold predictions grouped by engine (no engine appears in both train and validation folds)
    oof = np.zeros((len(tr), 3))
    for fold, (a, b) in enumerate(GroupKFold(n_splits=5).split(Xtr, ytr, groups=tr.unit)):
        (p,) = fit_predict(Xtr[a], ytr[a], [Xtr[b]])
        oof[b] = p.to_numpy()
    oof_df = tr[["unit", "cycle", "lifetime", "rul"]].copy()
    oof_df[["q10", "q50", "q90"]] = oof
    oof_df["rul_capped"] = ytr
    oof_df.to_csv(OUT / "oof_predictions.csv", index=False)

    # Final model on all training engines, scored on held-out test engines
    (pte,) = fit_predict(Xtr, ytr, [te[fcols].to_numpy()])
    te_pred = pd.concat([te[["unit", "cycle"]], pte], axis=1)
    te_pred = te_pred.merge(truth, on="unit")
    te_pred["rul_true_at_cycle"] = te_pred.rul_true + (te_pred.last_cycle - te_pred.cycle)
    te_pred.to_csv(OUT / "test_predictions_all_cycles.csv", index=False)

    last = te_pred[te_pred.cycle == te_pred.last_cycle].copy()
    last["true_capped"] = last.rul_true.clip(upper=RUL_CAP)
    last.to_csv(OUT / "test_final.csv", index=False)

    err_raw = last.q50 - last.rul_true
    err_cap = last.q50 - last.true_capped
    late = last.rul_true <= 30
    metrics = {
        "n_train_engines": int(tr.unit.nunique()), "n_test_engines": int(last.unit.nunique()),
        "n_channels_used": len(sensors), "rul_cap": RUL_CAP,
        "oof_rmse_all_cycles_vs_capped": float(np.sqrt(np.mean((oof_df.q50 - oof_df.rul_capped) ** 2))),
        "test_rmse_vs_true_rul": float(np.sqrt(np.mean(err_raw ** 2))),
        "test_rmse_vs_capped_true_rul": float(np.sqrt(np.mean(err_cap ** 2))),
        "test_mae_vs_true_rul": float(np.mean(np.abs(err_raw))),
        "test_nasa_score": nasa_score(last.q50.to_numpy(), last.rul_true.to_numpy()),
        "test_80pct_interval_coverage_vs_capped": float(((last.true_capped >= last.q10) & (last.true_capped <= last.q90)).mean()),
        "test_rmse_engines_within_30_cycles_of_failure": float(np.sqrt(np.mean(err_raw[late] ** 2))) if late.any() else None,
        "n_test_engines_within_30_cycles_of_failure": int(late.sum()),
    }

    sweep_df, base_df = decision.sweep(oof_df)
    sweep_df.to_csv(OUT / "policy_sweep.csv", index=False)
    base_df.to_csv(OUT / "policy_baselines.csv", index=False)
    metrics["policy"] = {}
    for r, g in sweep_df.groupby("cost_ratio"):
        best = g.loc[g.cost_per_cycle.idxmin()]
        b = base_df[base_df.cost_ratio == r].iloc[0]
        metrics["policy"][str(r)] = {
            "best_threshold": int(best.threshold), "model_cost_per_cycle": float(best.cost_per_cycle),
            "failures": int(best.failures), "life_used_pct": float(best.life_used_pct),
            "run_to_failure_cost_per_cycle": float(b.run_to_failure_cost),
            "best_fixed_interval_age": int(b.fixed_interval_age), "best_fixed_interval_cost_per_cycle": float(b.fixed_interval_cost),
        }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
