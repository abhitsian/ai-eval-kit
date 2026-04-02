"""
Generic Eval Dashboard
Reads from product.yaml for surfaces, thresholds, owners.

Launch: evalkit dashboard
   or: streamlit run app/dashboard.py
"""

import json
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))

from evalkit.config import ProductConfig


def get_config():
    try:
        return ProductConfig()
    except FileNotFoundError:
        return None


def load_results(data_dir):
    results_dir = data_dir / "results"
    if not results_dir.exists():
        return []
    results = []
    for f in sorted(results_dir.glob("*.json")):
        with open(f) as fh:
            results.append(json.load(fh))
    return results


def load_labels(data_dir):
    labels_dir = data_dir / "labels"
    if not labels_dir.exists():
        return pd.DataFrame()
    files = list(labels_dir.glob("*.csv"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def main():
    st.set_page_config(page_title="Eval Dashboard", layout="wide")

    config = get_config()
    product_name = config.product_name if config else "AI Product"
    st.title(f"{product_name} — Eval Dashboard")

    data_dir = config.data_dir if config else Path.cwd() / "data"
    surfaces_config = config.surfaces if config else {}
    results = load_results(data_dir)
    labels_df = load_labels(data_dir)

    if not results:
        st.info("No eval results yet. Run `evalkit run <surface>` to generate results.")
        if surfaces_config:
            st.header("Configured Surfaces")
            for name, conf in surfaces_config.items():
                st.markdown(f"- **{name}**: threshold={conf.get('threshold', 0.85):.0%}, owner={conf.get('owner', '?')}")
        return

    # --- Readiness Overview ---
    st.header("Launch Readiness")

    latest = {}
    for r in results:
        s = r["surface"]
        if s not in latest or r["timestamp"] > latest[s]["timestamp"]:
            latest[s] = r

    readiness = []
    for name, conf in surfaces_config.items():
        threshold = conf.get("threshold", 0.85)
        owner = conf.get("owner", "?")
        if name in latest:
            lr = latest[name]
            readiness.append({
                "Surface": name, "Owner": owner,
                "Pass Rate": lr["pass_rate"], "Threshold": threshold,
                "pass@k": lr.get("pass_at_k", 0), "pass^k": lr.get("pass_pow_k", 0),
                "Status": "Ready" if lr["pass_rate"] >= threshold else "Not Ready",
            })
        else:
            readiness.append({
                "Surface": name, "Owner": owner,
                "Pass Rate": 0.0, "Threshold": threshold,
                "pass@k": 0.0, "pass^k": 0.0, "Status": "No Data",
            })

    if readiness:
        cols = st.columns(min(len(readiness), 6))
        for i, row in enumerate(readiness):
            with cols[i % len(cols)]:
                color = {"Ready": "green", "Not Ready": "red"}.get(row["Status"], "gray")
                st.markdown(
                    f"<div style='padding:10px;border-radius:8px;border:2px solid {color};text-align:center;margin-bottom:8px'>"
                    f"<b>{row['Surface']}</b><br>"
                    f"<span style='font-size:24px;color:{color}'>{row['Pass Rate']:.0%}</span><br>"
                    f"<small>threshold: {row['Threshold']:.0%} | {row['Owner']}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # --- Trends ---
    st.header("Pass Rate Trends")
    trend_data = [{"surface": r["surface"], "timestamp": r["timestamp"], "pass_rate": r["pass_rate"]} for r in results]
    if trend_data:
        fig = px.line(pd.DataFrame(trend_data), x="timestamp", y="pass_rate", color="surface",
                      title="Pass Rate Over Time")
        st.plotly_chart(fig, use_container_width=True)

    # --- Failure Modes ---
    st.header("Failure Modes")
    if not labels_df.empty and "failure_mode" in labels_df.columns:
        fm = labels_df[labels_df["failure_mode"] != "none"]
        if not fm.empty:
            fig = px.histogram(fm, x="failure_mode", color="failure_mode", title="Failure Distribution (Human Labels)")
            st.plotly_chart(fig, use_container_width=True)
    else:
        fc = {}
        for r in results:
            for task in r.get("tasks", []):
                for trial in task.get("trials", []):
                    for g in trial.get("graders", []):
                        if g["verdict"] == "fail":
                            fc[g["dimension"]] = fc.get(g["dimension"], 0) + 1
        if fc:
            fig = px.bar(x=list(fc.keys()), y=list(fc.values()), title="Grader Failures",
                         labels={"x": "Dimension", "y": "Count"})
            st.plotly_chart(fig, use_container_width=True)

    # --- Capability vs Reliability ---
    st.header("Capability vs Reliability")
    cap = [r for r in readiness if r["pass@k"] > 0]
    if cap:
        fig = go.Figure()
        fig.add_trace(go.Bar(name="pass@k", x=[r["Surface"] for r in cap], y=[r["pass@k"] for r in cap]))
        fig.add_trace(go.Bar(name="pass^k", x=[r["Surface"] for r in cap], y=[r["pass^k"] for r in cap]))
        fig.update_layout(barmode="group")
        st.plotly_chart(fig, use_container_width=True)

    # --- Detail ---
    st.header("Detailed Results")
    selected = st.selectbox("Surface", ["all"] + list(latest.keys()))
    filtered = results if selected == "all" else [r for r in results if r["surface"] == selected]
    for r in filtered[-5:]:
        with st.expander(f"{r['surface']}/{r['feature']} — {r['timestamp']} — {r['pass_rate']:.0%}"):
            rows = []
            for task in r.get("tasks", []):
                fails = [f"{g['dimension']}: {g['reasoning']}" for trial in task["trials"] for g in trial["graders"] if g["verdict"] == "fail"]
                rows.append({
                    "Task": task["task_id"], "Input": task["input"][:60],
                    "Pass Rate": f"{task['pass_rate']:.0%}", "Failures": "; ".join(set(fails))[:100],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # --- Label Stats ---
    if not labels_df.empty:
        st.header("Labeling Progress")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total", len(labels_df))
        c2.metric("Pass", len(labels_df[labels_df["verdict"] == "pass"]))
        c3.metric("Fail", len(labels_df[labels_df["verdict"] == "fail"]))


if __name__ == "__main__":
    main()
