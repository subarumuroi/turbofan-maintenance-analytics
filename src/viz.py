"""Shared data loading and Plotly figures for the static report and the Streamlit app."""
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .config import OUT, RUL_CAP
from .sqlrun import connect, run

NAVY, BLUE, GREY, RED, AMBER, GREEN = "#14284b", "#2f6db5", "#8a94a6", "#c0392b", "#d98e04", "#2e8b57"
LAYOUT = dict(font=dict(family="Arial, sans-serif", size=13), margin=dict(l=50, r=20, t=50, b=45),
              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")

# Illustrative alert bands on the lower (10th percentile) RUL bound, in cycles
ACT_NOW, PLAN = 15, 40


def load_data():
    con = connect()
    drift = pd.read_csv(OUT / "channel_drift.csv", index_col=0)
    keep = ",".join(f"'{c}'" for c in drift.index[drift.selected])
    d = {
        "lifetimes": run("fleet_lifetimes", con),
        "stages": run("drift_by_life_stage", con),
        "profile": run("dq_sensor_profile", con),
        "gaps": run("dq_cycle_gaps", con),
        "drift": drift,
        "oof": pd.read_csv(OUT / "oof_predictions.csv"),
        "test_all": pd.read_csv(OUT / "test_predictions_all_cycles.csv"),
        "test_final": pd.read_csv(OUT / "test_final.csv"),
        "sweep": pd.read_csv(OUT / "policy_sweep.csv"),
        "baselines": pd.read_csv(OUT / "policy_baselines.csv"),
        "metrics": json.loads((OUT / "metrics.json").read_text()),
        "train_sensor": pd.read_sql_query(
            "SELECT r.unit, t.rul, r.sensor, r.value FROM readings r "
            "JOIN train_rul t ON t.unit=r.unit AND t.cycle=r.cycle WHERE r.split='train' "
            f"AND r.sensor IN ({keep})", con),
    }
    con.close()
    return d


def risk_band(q10):
    return np.where(q10 <= ACT_NOW, "Schedule now", np.where(q10 <= PLAN, "Plan", "Monitor"))


def fleet_table(test_final):
    t = test_final.copy()
    t["status"] = risk_band(t.q10)
    t = t.sort_values(["q10", "q50"]).rename(columns={"unit": "Engine", "last_cycle": "Cycles run", "q10": "RUL low (P10)",
                                                      "q50": "RUL median", "q90": "RUL high (P90)", "status": "Status",
                                                      "rul_true": "True RUL (held out)"})
    cols = ["Engine", "Cycles run", "RUL low (P10)", "RUL median", "RUL high (P90)", "Status", "True RUL (held out)"]
    t[["RUL low (P10)", "RUL median", "RUL high (P90)"]] = t[["RUL low (P10)", "RUL median", "RUL high (P90)"]].round(0).astype(int)
    return t[cols].reset_index(drop=True)


def fig_lifetimes(lifetimes):
    f = go.Figure(go.Histogram(x=lifetimes.lifetime, nbinsx=22, marker_color=BLUE))
    f.add_vline(x=lifetimes.lifetime.median(), line_dash="dash", line_color=NAVY,
                annotation_text=f"median {lifetimes.lifetime.median():.0f}", annotation_position="top right")
    f.update_layout(title="Cycles to failure, 100 training engines", xaxis_title="Lifetime (cycles)",
                    yaxis_title="Engines", **LAYOUT)
    return f


def fig_drift_heatmap(stages, drift):
    sel = list(drift.index[drift.selected])
    s = stages[stages.sensor.isin(sel)].copy()
    s = s.join(drift[["early_mean", "early_sd"]], on="sensor")
    s["z"] = (s.mean_value - s.early_mean) / s.early_sd
    order = drift.loc[sel].sort_values("drift_score", ascending=False).index
    z = s.pivot(index="sensor", columns="stage", values="z").loc[order]
    f = go.Figure(go.Heatmap(z=z.values, x=[f"{10*i}-{10*i+10}%" for i in z.columns], y=list(z.index),
                             colorscale="RdBu_r", zmid=0, colorbar=dict(title="SDs vs<br>early life")))
    f.update_layout(title="Channel drift across engine life (SQL-aggregated)", xaxis_title="Share of life elapsed",
                    yaxis_title="Channel", yaxis=dict(autorange="reversed"), **LAYOUT)
    return f


def fig_sensor_trajectories(train_sensor, sensor, units):
    f = go.Figure()
    for u in units:
        g = train_sensor[(train_sensor.sensor == sensor) & (train_sensor.unit == u)].sort_values("rul")
        f.add_trace(go.Scatter(x=g.rul, y=g.value, mode="lines", name=f"Engine {u}", line=dict(width=1.5)))
    f.update_layout(title=f"{sensor} versus cycles remaining until failure", xaxis_title="Cycles remaining",
                    yaxis_title=sensor, xaxis=dict(autorange="reversed"), **LAYOUT)
    return f


def _traj_traces(g, visible=True):
    g = g.sort_values("cycle")
    band = go.Scatter(x=list(g.cycle) + list(g.cycle[::-1]), y=list(g.q90) + list(g.q10[::-1]), fill="toself",
                      fillcolor="rgba(47,109,181,0.18)", line=dict(width=0), name="P10-P90 interval", hoverinfo="skip", visible=visible)
    med = go.Scatter(x=g.cycle, y=g.q50, mode="lines", name="Predicted median", line=dict(color=BLUE, width=2), visible=visible)
    tru = go.Scatter(x=g.cycle, y=g.rul_true_at_cycle.clip(upper=RUL_CAP), mode="lines", name=f"True RUL (capped at {RUL_CAP})",
                     line=dict(color=NAVY, width=2, dash="dot"), visible=visible)
    return [band, med, tru]


def fig_engine_trajectory(test_all, unit):
    f = go.Figure(_traj_traces(test_all[test_all.unit == unit]))
    f.update_layout(title=f"Test engine {unit}: predicted remaining life with uncertainty", xaxis_title="Cycle",
                    yaxis_title="Remaining useful life (cycles)", **LAYOUT)
    return f


def fig_engine_dropdown(test_all, units):
    f = go.Figure()
    for i, u in enumerate(units):
        for tr in _traj_traces(test_all[test_all.unit == u], visible=(i == 0)):
            f.add_trace(tr)
    buttons = [dict(label=f"Engine {u}", method="update",
                    args=[{"visible": [j // 3 == i for j in range(3 * len(units))]},
                          {"title": f"Test engine {u}: predicted remaining life with uncertainty"}])
               for i, u in enumerate(units)]
    f.update_layout(title=f"Test engine {units[0]}: predicted remaining life with uncertainty", xaxis_title="Cycle",
                    yaxis_title="Remaining useful life (cycles)", updatemenus=[dict(buttons=buttons, x=0.0, y=1.18, xanchor="left")], **LAYOUT)
    return f


def fig_policy(sweep, baselines, cost_ratio):
    g = sweep[sweep.cost_ratio == cost_ratio]
    b = baselines[baselines.cost_ratio == cost_ratio].iloc[0]
    best = g.loc[g.cost_per_cycle.idxmin()]
    f = go.Figure()
    f.add_trace(go.Scatter(x=g.threshold, y=g.cost_per_cycle, mode="lines+markers", name="RUL-triggered replacement",
                           line=dict(color=BLUE, width=2)))
    f.add_hline(y=b.fixed_interval_cost, line_dash="dash", line_color=AMBER,
                annotation_text=f"best fixed interval (age {int(b.fixed_interval_age)})", annotation_position="top right")
    f.add_trace(go.Scatter(x=[best.threshold], y=[best.cost_per_cycle], mode="markers", name="lowest cost",
                           marker=dict(color=RED, size=11)))
    f.update_layout(title=f"Replacement threshold vs cost (failure = {cost_ratio}x planned cost; run-to-failure = {b.run_to_failure_cost:.3f})",
                    xaxis_title="Replace when P10 remaining life falls to (cycles)", yaxis_title="Cost per operating cycle",
                    yaxis=dict(rangemode="tozero"), **LAYOUT)
    return f
