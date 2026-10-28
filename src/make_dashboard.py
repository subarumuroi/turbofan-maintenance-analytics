"""Build a single self-contained HTML report (open in any browser, or host on GitHub Pages).

Usage: python -m src.make_dashboard   ->  outputs/dashboard.html
"""
import html
from .config import OUT
from . import viz

CSS = """
body{font-family:Arial,Helvetica,sans-serif;background:#f4f6fa;color:#14284b;margin:0}
header{background:#14284b;color:#fff;padding:28px 40px}
header h1{margin:0 0 6px;font-size:26px} header p{margin:0;opacity:.85;max-width:900px;line-height:1.45}
main{max-width:1100px;margin:0 auto;padding:24px 20px 60px}
.kpis{display:flex;gap:14px;flex-wrap:wrap;margin:6px 0 22px}
.kpi{background:#fff;border-radius:10px;padding:14px 18px;flex:1;min-width:190px;box-shadow:0 1px 3px rgba(20,40,75,.12)}
.kpi b{display:block;font-size:26px} .kpi span{font-size:12.5px;color:#586274}
section{background:#fff;border-radius:10px;padding:18px 22px;margin-bottom:20px;box-shadow:0 1px 3px rgba(20,40,75,.12)}
section h2{margin:0 0 4px;font-size:19px} section p.note{margin:2px 0 10px;color:#586274;font-size:13.5px;line-height:1.45}
table{border-collapse:collapse;width:100%;font-size:13px} th,td{padding:6px 9px;text-align:right;border-bottom:1px solid #e6e9f0}
th{background:#14284b;color:#fff;position:sticky;top:0} td:first-child,th:first-child,td:nth-child(6),th:nth-child(6){text-align:left}
.tw{max-height:360px;overflow:auto;border:1px solid #e6e9f0;border-radius:6px}
.s-now{color:#c0392b;font-weight:bold}.s-plan{color:#d98e04;font-weight:bold}.s-mon{color:#2e8b57}
footer{font-size:12.5px;color:#586274;line-height:1.5;margin-top:10px}
"""


def table_html(df):
    cls = {"Schedule now": "s-now", "Plan": "s-plan", "Monitor": "s-mon"}
    head = "".join(f"<th>{html.escape(c)}</th>" for c in df.columns)
    rows = []
    for _, r in df.iterrows():
        cells = "".join(f'<td class="{cls.get(v, "")}">{html.escape(str(v))}</td>' for v in r)
        rows.append(f"<tr>{cells}</tr>")
    return f'<div class="tw"><table><tr>{head}</tr>{"".join(rows)}</table></div>'


def main():
    d = viz.load_data()
    m = d["metrics"]
    ft = viz.fleet_table(d["test_final"])
    counts = ft.Status.value_counts()
    ratio = "10"
    pol = m["policy"][ratio]
    units = list(ft.Engine.head(4)) + list(ft.Engine.tail(2))
    sensor = d["drift"].index[d["drift"].selected][0]
    s_units = sorted(d["lifetimes"].sort_values("lifetime").unit.iloc[[0, 25, 50, 75, 99]])

    figs = {
        "life": viz.fig_lifetimes(d["lifetimes"]),
        "drift": viz.fig_drift_heatmap(d["stages"], d["drift"]),
        "sensor": viz.fig_sensor_trajectories(d["train_sensor"], sensor, s_units),
        "traj": viz.fig_engine_dropdown(d["test_all"], units),
        "policy": viz.fig_policy(d["sweep"], d["baselines"], int(ratio)),
    }
    first = True
    def fig(k, h=420):
        nonlocal first
        out = figs[k].update_layout(height=h).to_html(full_html=False, include_plotlyjs="cdn" if first else False)
        first = False
        return out

    gaps = d["gaps"]
    n_flat = int((~d["drift"].selected).sum())
    kpis = [
        (f"{m['test_rmse_vs_true_rul']:.1f} cycles", "Test RMSE (100 held-out engines)"),
        (f"{m['test_mae_vs_true_rul']:.1f} cycles", "Test mean absolute error"),
        (f"{100*m['test_80pct_interval_coverage_vs_capped']:.0f}%", "Coverage of the 80% interval (target 80%)"),
        (f"{counts.get('Schedule now', 0)} / {counts.get('Plan', 0)} / {counts.get('Monitor', 0)}", "Test fleet: schedule now / plan / monitor"),
    ]
    kp = "".join(f'<div class="kpi"><b>{a}</b><span>{b}</span></div>' for a, b in kpis)

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Turbofan maintenance analytics</title><style>{CSS}</style></head><body>
<header><h1>Turbofan maintenance analytics</h1>
<p>NASA C-MAPSS FD001 run-to-failure engine data. SQL (SQLite) for profiling, data quality and window features;
Python for interval-forecast models of remaining useful life and a cost-based replacement rule.</p></header><main>
<div class="kpis">{kp}</div>
<section><h2>1. Data quality and fleet profile</h2>
<p class="note">SQL checks found {int(gaps.units.sum())} engines across both splits, {int(gaps.units_with_gaps.sum())} with cycle gaps, {int(d['profile'].n_null.sum())} null readings, and
{n_flat} of {len(d['drift'])} channels with no usable drift (constant or near-constant), which were dropped. Median lifetime is
{d['lifetimes'].lifetime.median():.0f} cycles, range {d['lifetimes'].lifetime.min()}-{d['lifetimes'].lifetime.max()}.</p>{fig('life', 340)}</section>
<section><h2>2. Which channels degrade</h2>
<p class="note">Mean channel value in ten life-stage bins, standardised by early-life spread. Drift is computed in SQL window and aggregate queries.</p>
{fig('drift', 460)}{fig('sensor', 380)}</section>
<section><h2>3. Fleet status with uncertainty</h2>
<p class="note">Predictions are for the last observed cycle of each held-out engine, sorted by the lower (P10) remaining-life bound. The status bands
(P10 at or below {viz.ACT_NOW} cycles: schedule now; at or below {viz.PLAN}: plan; otherwise monitor) are illustrative. The last column is the true value, shown only to evaluate the model.</p>
{table_html(ft)}{fig('traj', 400)}</section>
<section><h2>4. From forecast to decision</h2>
<p class="note">Replace an engine once its P10 remaining-life bound falls to a threshold. Costs are assumptions: a planned replacement costs 1 unit and an in-service failure costs 10 units
(change the ratio in the Streamlit app). Simulated on out-of-fold predictions for the 100 training engines.
At the cheapest threshold ({pol['best_threshold']} cycles) the rule gives {pol['failures']} failures and uses {pol['life_used_pct']:.0f}% of engine life,
costing {pol['model_cost_per_cycle']:.4f} per cycle against {pol['best_fixed_interval_cost_per_cycle']:.4f} for the best fixed-age replacement and
{pol['run_to_failure_cost_per_cycle']:.4f} for run-to-failure. The threshold was chosen on the same simulation it is scored on, so the gain is optimistic.</p>{fig('policy', 400)}</section>
<footer>Data: NASA Prognostics Center of Excellence, C-MAPSS turbofan degradation simulation (FD001, single operating condition, single fault mode).
Intervals cover {100*m['test_80pct_interval_coverage_vs_capped']:.0f}% of held-out engines against an 80% target, so they are somewhat too narrow.</footer>
</main></body></html>"""
    (OUT / "dashboard.html").write_text(page, encoding="utf-8")
    print("wrote", OUT / "dashboard.html", f"({len(page)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
