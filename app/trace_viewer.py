"""
Generic Trace Viewer + Labeling Interface
Reads surfaces and failure modes from product.yaml.

Launch: evalkit viewer
   or: streamlit run app/trace_viewer.py
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import pandas as pd

# Add parent to path so evalkit is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from evalkit.config import ProductConfig


def get_config():
    """Load product config, searching up from cwd."""
    try:
        return ProductConfig()
    except FileNotFoundError:
        return None


def load_traces(data_dir):
    traces = []
    traces_dir = data_dir / "traces"
    if not traces_dir.exists():
        return traces
    for f in sorted(traces_dir.glob("*.jsonl"), reverse=True):
        with open(f) as fh:
            for line in fh:
                if line.strip():
                    traces.append(json.loads(line))
    for f in sorted(traces_dir.glob("*.json"), reverse=True):
        with open(f) as fh:
            data = json.load(fh)
            if isinstance(data, list):
                traces.extend(data)
            else:
                traces.append(data)
    return traces


def load_labels(data_dir):
    labels_dir = data_dir / "labels"
    if not labels_dir.exists():
        return pd.DataFrame(columns=["trace_id", "verdict", "failure_mode", "notes", "reviewer", "timestamp"])
    files = list(labels_dir.glob("*.csv"))
    if not files:
        return pd.DataFrame(columns=["trace_id", "verdict", "failure_mode", "notes", "reviewer", "timestamp"])
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def save_label(data_dir, trace_id, verdict, failure_mode, notes, reviewer):
    labels_dir = data_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = labels_dir / f"labels_{today}.csv"
    exists = path.exists()
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["trace_id", "verdict", "failure_mode", "notes", "reviewer", "timestamp"])
        w.writerow([trace_id, verdict, failure_mode, notes, reviewer, datetime.now(timezone.utc).isoformat()])


def promote_to_golden(data_dir, trace):
    golden_dir = data_dir / "golden"
    golden_dir.mkdir(parents=True, exist_ok=True)
    with open(golden_dir / "golden_set.jsonl", "a") as f:
        f.write(json.dumps(trace) + "\n")


def main():
    st.set_page_config(page_title="Trace Viewer", layout="wide")

    config = get_config()
    if config:
        st.title(f"{config.product_name} — Trace Viewer")
        surface_names = ["all"] + config.surface_names()
        failure_modes = ["none"] + config.failure_mode_ids()
        data_dir = config.data_dir
    else:
        st.title("AI Eval Kit — Trace Viewer")
        st.warning("No product.yaml found. Run `evalkit init` to set up your project.")
        surface_names = ["all"]
        failure_modes = ["none", "hallucination", "wrong_routing", "incomplete", "tone_mismatch", "wrong_action", "other"]
        data_dir = Path.cwd() / "data"

    # Sidebar
    st.sidebar.header("Filters")
    surface_filter = st.sidebar.selectbox("Surface", surface_names)
    reviewer = st.sidebar.text_input("Your Name", value="reviewer")
    show_labeled = st.sidebar.checkbox("Show labeled", value=False)

    # Load data
    traces = load_traces(data_dir)
    labels_df = load_labels(data_dir)
    labeled_ids = set(labels_df["trace_id"].tolist()) if not labels_df.empty else set()

    if not traces:
        st.info(
            "No traces found. Add trace files to `data/traces/` as JSONL or JSON.\n\n"
            "**Trace format:**\n"
            "```json\n"
            '{"id": "t-001", "input": "user query", "surface": "your_surface", '
            '"response": {"text": "AI response"}, "timestamp": "2026-01-01T00:00:00Z"}\n'
            "```"
        )
        if st.button("Generate sample traces"):
            _create_samples(data_dir, config)
            st.rerun()
        return

    # Filter
    if surface_filter != "all":
        traces = [t for t in traces if t.get("surface", "") == surface_filter]
    if not show_labeled:
        traces = [t for t in traces if t.get("id", "") not in labeled_ids]

    # Stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Traces", len(traces))
    c2.metric("Labeled", len(labeled_ids))
    c3.metric("Unlabeled", len(traces))
    c4.metric("Surfaces", len(set(t.get("surface", "?") for t in traces)))

    if not traces:
        st.success("All traces labeled!")
        return

    st.divider()

    for idx, trace in enumerate(traces[:50]):
        tid = trace.get("id", f"t-{idx}")
        inp = trace.get("input", "")
        surface = trace.get("surface", "?")
        response = trace.get("response", {})
        resp_text = response.get("text", str(response)) if isinstance(response, dict) else str(response)
        retrieved = trace.get("retrieved_context", "")
        ts = trace.get("timestamp", "")

        with st.expander(f"**{tid}** | {surface} | {inp[:60]}", expanded=(idx == 0)):
            left, right = st.columns([3, 2])

            with left:
                st.markdown(f"**Input:** {inp}")
                st.markdown(f"**Surface:** `{surface}` | **Time:** {ts}")
                st.markdown("---")
                st.markdown("**Response:**")
                st.markdown(resp_text)
                if retrieved:
                    st.markdown("---")
                    st.markdown("**Retrieved Context:**")
                    st.text_area("Source", retrieved, height=120, key=f"src_{tid}", disabled=True)

            with right:
                st.markdown("### Label")
                verdict = st.radio("Verdict", ["pass", "fail"], key=f"v_{tid}", horizontal=True)
                fm = st.selectbox("Failure Mode", failure_modes, key=f"fm_{tid}")
                notes = st.text_area("Notes", key=f"n_{tid}", height=60)

                c_save, c_gold = st.columns(2)
                with c_save:
                    if st.button("Save", key=f"s_{tid}"):
                        save_label(data_dir, tid, verdict, fm, notes, reviewer)
                        st.success("Saved!")
                        st.rerun()
                with c_gold:
                    if st.button("→ Eval Set", key=f"g_{tid}"):
                        promote_to_golden(data_dir, trace)
                        st.success("Added!")


def _create_samples(data_dir, config):
    traces_dir = data_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    surface = config.surface_names()[0] if config else "general"
    samples = [
        {"id": "sample-001", "input": "How does this feature work?", "surface": surface,
         "response": {"text": "This feature allows you to..."}, "timestamp": "2026-01-01T10:00:00Z"},
        {"id": "sample-002", "input": "I need help with something", "surface": surface,
         "response": {"text": "I can help you with that..."}, "timestamp": "2026-01-01T11:00:00Z"},
        {"id": "sample-003", "input": "What is your return policy on Jupiter?", "surface": surface,
         "response": {"text": "Our return policy on Jupiter is 30 days..."}, "timestamp": "2026-01-01T12:00:00Z"},
    ]
    with open(traces_dir / "samples.jsonl", "w") as f:
        for s in samples:
            f.write(json.dumps(s) + "\n")


if __name__ == "__main__":
    main()
