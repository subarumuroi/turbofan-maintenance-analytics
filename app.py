"""Interactive dashboard.  Run:  streamlit run app.py   (after build_db and model have been run)"""
import warnings
import pandas as pd
import streamlit as st

from src import viz

warnings.filterwarnings("ignore")
st.set_page_config(page_title="Turbofan maintenance analytics", layout="wide")


@st.cache_data(show_spinner="Loading data")
def get():
    return viz.load_data()


try:
    d = get()
except FileNotFoundError as e:
    st.error(f"{e}\n\nRun `python -m src.build_db` and `python -m src.model` first.")
    st.stop()

m = d["metrics"]
st.title("Turbofan maintenance analytics")
st.caption("NASA C-MAPSS FD001 run-to-failure data. SQL for profiling and features, Python for remaining-useful-life intervals and a replacement-cost rule.")

c = st.columns(4)
c[0].metric("Test RMSE", f"{m['test_rmse_vs_true_rul']:.1f} cycles")
c[1].metric("Test MAE", f"{m['test_mae_vs_true_rul']:.1f} cycles")
c[2].metric("80% interval coverage", f"{100*m['test_80pct_interval_coverage_vs_capped']:.0f}%")
c[3].metric("Channels used", f"{m['n_channels_used']} of {len(d['drift'])}")

tab_fleet, tab_engine, tab_sensors, tab_policy, tab_dq = st.tabs(
    ["Fleet status", "Engine drill-down", "Sensor drift", "Maintenance policy", "Data quality"])

ft = viz.fleet_table(d["test_final"])
with tab_fleet:
    status = st.multiselect("Status", ["Schedule now", "Plan", "Monitor"], default=["Schedule now", "Plan"])
    st.caption(f"Bands on the P10 remaining-life bound: at or below {viz.ACT_NOW} cycles = schedule now, at or below {viz.PLAN} = plan. Illustrative.")
    st.dataframe(ft[ft.Status.isin(status)], width="stretch", hide_index=True)

with tab_engine:
    unit = st.selectbox("Test engine", list(ft.Engine), index=0)
    st.plotly_chart(viz.fig_engine_trajectory(d["test_all"], unit), width="stretch")

with tab_sensors:
    sel = list(d["drift"].index[d["drift"].selected])
    st.plotly_chart(viz.fig_drift_heatmap(d["stages"], d["drift"]), width="stretch")
    s = st.selectbox("Channel", sel)
    units = st.multiselect("Training engines", sorted(d["lifetimes"].unit), default=[1, 2, 3, 4, 5])
    st.plotly_chart(viz.fig_sensor_trajectories(d["train_sensor"], s, units), width="stretch")

with tab_policy:
    ratio = st.select_slider("Cost of an in-service failure relative to a planned replacement", options=[3, 5, 10, 20], value=10)
    st.plotly_chart(viz.fig_policy(d["sweep"], d["baselines"], ratio), width="stretch")
    st.caption("Costs are assumptions. The threshold is picked on the same simulation it is scored on, so the improvement is optimistic.")
    st.dataframe(d["sweep"][d["sweep"].cost_ratio == ratio].round(4), width="stretch", hide_index=True)

with tab_dq:
    st.write("Cycle continuity check (SQL):")
    st.dataframe(d["gaps"], hide_index=True)
    st.write("Channel profile and drift score (training split):")
    st.dataframe(d["drift"].round(3), width="stretch")
