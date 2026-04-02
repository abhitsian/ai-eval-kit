"""
Adaptive Eval Coach — Personalized coaching powered by Claude.

Launch: evalkit learn
   or: streamlit run app/coach.py
"""

import sys
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))

from evalkit.coach_engine.profile import UserProfile, SKILLS, SKILL_LABELS, LEVELS
from evalkit.coach_engine.simulator import generate_simulation, PRODUCT_TYPES
from evalkit.coach_engine.evaluator import evaluate_answer
from evalkit.coach_engine.pathway import recommend_next, suggest_session_plan, get_milestone_message

# ─── Skill metadata ───

SKILL_ICONS = {
    "failure_spotting": "01", "negative_case_design": "02",
    "rubric_definition": "03", "edge_case_thinking": "04",
    "calibration": "05", "eval_coverage": "06",
}
SKILL_DESCRIPTIONS = {
    "failure_spotting": "See what's wrong",
    "negative_case_design": "Think adversarially",
    "rubric_definition": "Define pass / fail",
    "edge_case_thinking": "Find the corners",
    "calibration": "Align your judgment",
    "eval_coverage": "Audit completeness",
}
DIFF_LABELS = {"easy": "Warm-up", "medium": "Standard", "hard": "Advanced"}
BADGE_META = {
    "first_blood": ("First Rep", "Completed your first exercise"),
    "getting_started": ("Ten Deep", "Completed 10 exercises"),
    "committed": ("Regular", "5 coaching sessions"),
    "streak_3": ("Streak 3", "3 consecutive days"),
    "streak_7": ("Streak 7", "7 consecutive days"),
    "sharpshooter": ("Sharp", "90%+ accuracy on one skill"),
    "well_rounded": ("Rounded", "All skills above 50"),
    "expert_spotter": ("Expert Eye", "Failure Spotting at 80+"),
    "negative_thinker": ("Devil's Advocate", "Negative Cases at 80+"),
    "rubric_master": ("Rubric Author", "Rubric Definition at 80+"),
    "centurion": ("Centurion", "100 exercises completed"),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Theme injection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _inject_theme():
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=DM+Mono:wght@400;500&display=swap');

    :root {
        --bg: #FAF8F5; --bg-raised: #FFFFFF; --bg-inset: #F2EFEB;
        --ink: #1A1714; --ink-secondary: #6B6560; --ink-tertiary: #9C9590;
        --accent: #C45D3E; --accent-soft: #FCEEE8; --accent-hover: #A94E33;
        --green: #2D8659; --green-soft: #E8F5EE;
        --red: #C44B4B; --red-soft: #FCEAEA;
        --amber: #B8860B; --amber-soft: #FFF8E6;
        --border: #E5E0DB; --border-strong: #D5CFC9;
        --radius: 6px; --radius-lg: 10px;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--bg) !important;
        color: var(--ink) !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    [data-testid="stSidebar"] {
        background-color: var(--ink) !important;
    }
    [data-testid="stSidebar"] * {
        color: #E5E0DB !important;
    }
    [data-testid="stSidebar"] hr { border-color: #3A3530 !important; }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #FAF8F5 !important; font-family: 'DM Mono', monospace !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #9C9590 !important;
    }

    /* Typography */
    h1 { font-weight: 700 !important; letter-spacing: -0.03em !important; font-size: 2rem !important; color: var(--ink) !important; }
    h2 { font-weight: 600 !important; letter-spacing: -0.02em !important; font-size: 1.35rem !important; color: var(--ink) !important; }
    h3 { font-weight: 600 !important; font-size: 1.1rem !important; color: var(--ink) !important; }
    p, li, label, .stMarkdown { font-size: 0.925rem !important; line-height: 1.65 !important; }

    /* Tabs — editorial underline style */
    [data-testid="stTabs"] button {
        font-family: 'DM Sans', sans-serif !important; font-weight: 500 !important;
        font-size: 0.95rem !important; letter-spacing: 0.02em !important;
        color: var(--ink-secondary) !important; border: none !important;
        padding: 12px 0 10px 0 !important; margin-right: 28px !important;
        background: transparent !important; border-radius: 0 !important;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--ink) !important; font-weight: 600 !important;
        border-bottom: 2px solid var(--accent) !important;
    }
    [data-testid="stTabs"] [data-testid="stTabsContent"] { padding-top: 24px !important; }

    /* Buttons */
    .stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {
        background-color: var(--accent) !important; color: #fff !important;
        border: none !important; border-radius: var(--radius) !important;
        font-weight: 600 !important; font-family: 'DM Sans', sans-serif !important;
        padding: 8px 20px !important; transition: background 0.15s !important;
    }
    .stButton > button[kind="primary"]:hover, .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background-color: var(--accent-hover) !important;
    }
    .stButton > button[kind="secondary"], .stButton > button[data-testid="stBaseButton-secondary"] {
        background: transparent !important; color: var(--ink-secondary) !important;
        border: 1px solid var(--border-strong) !important; border-radius: var(--radius) !important;
        font-weight: 500 !important;
    }

    /* Form inputs */
    input, textarea, [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input {
        font-family: 'DM Sans', sans-serif !important; font-size: 0.9rem !important;
        border: 1px solid var(--border-strong) !important; border-radius: var(--radius) !important;
        background-color: var(--bg-raised) !important;
    }
    input:focus, textarea:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent) !important; }

    /* Radio — pill style */
    [data-testid="stRadio"] > div { gap: 6px !important; }
    [data-testid="stRadio"] label {
        background: var(--bg-inset) !important; border: 1px solid var(--border) !important;
        border-radius: 20px !important; padding: 6px 16px !important;
        font-size: 0.85rem !important; transition: all 0.12s !important;
        cursor: pointer !important;
    }
    [data-testid="stRadio"] label:has(input:checked) {
        background: var(--ink) !important; color: var(--bg) !important;
        border-color: var(--ink) !important;
    }
    [data-testid="stRadio"] label input { display: none !important; }

    /* Selectbox */
    [data-testid="stSelectbox"] > div > div {
        border: 1px solid var(--border-strong) !important; border-radius: var(--radius) !important;
    }

    /* Expander */
    [data-testid="stExpander"] {
        border: 1px solid var(--border) !important; border-radius: var(--radius-lg) !important;
        background: var(--bg-raised) !important;
    }
    [data-testid="stExpander"] summary { font-weight: 500 !important; }

    /* Metric override */
    [data-testid="stMetricValue"] { font-family: 'DM Mono', monospace !important; font-weight: 600 !important; }

    /* Progress bar */
    [data-testid="stProgress"] > div > div { background-color: var(--bg-inset) !important; border-radius: 3px !important; }
    [data-testid="stProgress"] > div > div > div { background-color: var(--accent) !important; border-radius: 3px !important; }

    /* Hide Streamlit default */
    #MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
    .block-container { max-width: 960px !important; padding-top: 2rem !important; }
    </style>""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    st.set_page_config(page_title="Eval Coach", layout="wide", page_icon="E")
    _inject_theme()

    if "profile" not in st.session_state:
        st.session_state.profile = UserProfile()
    if "current_sim" not in st.session_state:
        st.session_state.current_sim = None
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "show_result" not in st.session_state:
        st.session_state.show_result = None

    profile = st.session_state.profile

    if profile._data.get("total_sessions", 0) == 0 and not st.session_state.get("onboarded"):
        _onboarding(profile)
        return

    _sidebar(profile)
    tab_train, tab_progress, tab_path = st.tabs(["Train", "Progress", "Path"])

    with tab_train:
        _training_tab(profile)
    with tab_progress:
        _progress_tab(profile)
    with tab_path:
        _pathway_tab(profile)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Onboarding
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _onboarding(profile):
    _inject_theme()

    st.markdown("""
    <div style="max-width:540px; margin:60px auto 0;">
        <p style="font-family:'DM Mono',monospace; font-size:0.8rem; color:#9C9590; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:8px;">Eval Coach</p>
        <h1 style="font-size:2.4rem; line-height:1.15; margin-bottom:12px;">Build the skill that<br>separates shipping from demo.</h1>
        <p style="color:#6B6560; font-size:1rem; line-height:1.7; margin-bottom:36px;">
            Evaluating AI is a learnable craft. This coach generates personalized challenges,
            judges your answers, and adapts to your growth areas — so your product ships with evidence, not vibes.
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        col_pad_l, col_form, col_pad_r = st.columns([1, 3, 1])
        with col_form:
            with st.form("onboarding"):
                name = st.text_input("Your name")
                role = st.selectbox("Role", ["Product Manager", "Senior PM", "Director of PM", "Engineering Manager", "Designer", "QA Lead", "Other"])
                product = st.text_area("What AI product are you building?", placeholder="e.g., An AI-powered employee hub with conversational search")
                product_types = st.multiselect(
                    "Product types you work with",
                    list(PRODUCT_TYPES.keys()),
                    default=["chatbot"],
                    format_func=lambda x: PRODUCT_TYPES[x]["name"],
                )
                submitted = st.form_submit_button("Start coaching", type="primary", use_container_width=True)

            if submitted and name:
                profile.display_name = name
                profile.role = role
                profile.product_context = product
                profile._data["preferred_product_types"] = product_types
                profile.start_session()
                profile.save()
                st.session_state.onboarded = True
                st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Sidebar
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _sidebar(profile):
    sb = st.sidebar

    sb.markdown(f"""
    <div style="padding:4px 0 8px;">
        <p style="font-family:'DM Mono',monospace; font-size:0.7rem; letter-spacing:0.12em; text-transform:uppercase; color:#9C9590; margin:0 0 2px;">Eval Coach</p>
        <p style="font-size:1.2rem; font-weight:600; color:#FAF8F5; margin:0;">{profile.display_name}</p>
    </div>
    """, unsafe_allow_html=True)

    sb.divider()

    level_label = profile.overall_level.title()
    c1, c2 = sb.columns(2)
    c1.metric("Level", level_label)
    c2.metric("XP", f"{profile.overall_xp:,}")

    c3, c4 = sb.columns(2)
    c3.metric("Sessions", profile._data.get("total_sessions", 0))
    c4.metric("Streak", f"{profile._data.get('streak_days', 0)}d")

    # Compact skill bars
    sb.divider()
    sb.markdown("<p style='font-size:0.75rem; text-transform:uppercase; letter-spacing:0.1em; color:#9C9590; margin-bottom:8px;'>Skills</p>", unsafe_allow_html=True)
    for sk in SKILLS:
        lv = profile.skill_level(sk)
        pct = max(lv, 2)
        bar_color = "#C45D3E" if sk in profile.weak_areas else "#2D8659" if lv >= 60 else "#6B6560"
        sb.markdown(f"""
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
            <span style="font-size:0.78rem; color:#9C9590; width:110px; flex-shrink:0;">{SKILL_LABELS[sk]}</span>
            <div style="flex:1; height:4px; background:#3A3530; border-radius:2px; overflow:hidden;">
                <div style="width:{pct}%; height:100%; background:{bar_color}; border-radius:2px;"></div>
            </div>
            <span style="font-family:'DM Mono',monospace; font-size:0.72rem; color:#9C9590; width:28px; text-align:right;">{lv}</span>
        </div>
        """, unsafe_allow_html=True)

    # Badges
    badges = profile._data.get("unlocked_badges", [])
    if badges:
        sb.divider()
        sb.markdown("<p style='font-size:0.75rem; text-transform:uppercase; letter-spacing:0.1em; color:#9C9590; margin-bottom:6px;'>Badges</p>", unsafe_allow_html=True)
        badge_html = ""
        for b in badges:
            label, desc = BADGE_META.get(b, (b, ""))
            badge_html += f'<span title="{desc}" style="display:inline-block; font-size:0.72rem; background:#3A3530; color:#E5E0DB; padding:3px 10px; border-radius:12px; margin:2px 4px 2px 0;">{label}</span>'
        sb.markdown(badge_html, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Train
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _training_tab(profile):
    recs = recommend_next(profile, 3)
    recommended_skill = recs[0]["skill"] if recs else "failure_spotting"

    sim = st.session_state.current_sim

    if sim is None:
        # No active challenge — show launcher
        st.markdown("## Ready to train")

        # Recommendation callout
        if recs:
            r = recs[0]
            st.markdown(f"""
            <div style="background:#FCEEE8; border-left:3px solid #C45D3E; padding:14px 18px; border-radius:0 6px 6px 0; margin-bottom:24px;">
                <p style="margin:0; font-size:0.85rem; color:#1A1714;">
                    <strong>Recommended:</strong> {r['skill_label']} ({r['difficulty']}) — {r['reason']}
                </p>
            </div>
            """, unsafe_allow_html=True)

        # Skill + product selector
        skill_options = list(SKILLS)
        if recommended_skill in skill_options:
            skill_options.remove(recommended_skill)
            skill_options.insert(0, recommended_skill)

        c1, c2 = st.columns([3, 2])
        with c1:
            skill = st.selectbox(
                "Skill",
                skill_options,
                format_func=lambda x: f"{SKILL_LABELS[x]}  —  {SKILL_DESCRIPTIONS[x]}  ({profile.skill_level(x)}%)",
            )
        with c2:
            product_type = st.selectbox(
                "Product context",
                ["auto"] + list(PRODUCT_TYPES.keys()),
                format_func=lambda x: "Varies automatically" if x == "auto" else PRODUCT_TYPES[x]["name"],
            )

        if st.button("Generate challenge", type="primary"):
            with st.spinner("Generating..."):
                pt = None if product_type == "auto" else product_type
                new_sim = generate_simulation(skill, profile, pt)
                st.session_state.current_sim = new_sim
                st.session_state.show_result = None
                if not st.session_state.session_id:
                    st.session_state.session_id = profile.start_session()
            st.rerun()

    else:
        # Active challenge
        _render_challenge(sim, profile)


def _render_challenge(sim, profile):
    skill = sim["skill"]
    diff = sim.get("difficulty", "medium")
    result = st.session_state.show_result

    # Challenge header strip
    diff_color = {"easy": "#2D8659", "medium": "#B8860B", "hard": "#C44B4B"}.get(diff, "#6B6560")
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:16px; padding:10px 0 16px; border-bottom:1px solid #E5E0DB; margin-bottom:20px;">
        <span style="font-family:'DM Mono',monospace; font-size:0.72rem; font-weight:500; color:{diff_color}; text-transform:uppercase; letter-spacing:0.08em; border:1px solid {diff_color}; padding:3px 10px; border-radius:3px;">{DIFF_LABELS.get(diff, diff)}</span>
        <span style="font-size:0.92rem; font-weight:600; color:#1A1714;">{SKILL_LABELS[skill]}</span>
        <span style="font-size:0.82rem; color:#9C9590;">{sim.get('product_name', '')}</span>
        <span style="margin-left:auto; font-family:'DM Mono',monospace; font-size:0.78rem; color:#9C9590;">+{sim.get('xp_value', 15)} xp</span>
    </div>
    """, unsafe_allow_html=True)

    if result:
        _render_result(sim, result, profile)
        return

    # Challenge body by type
    if skill == "failure_spotting":
        _challenge_failure_spotting(sim, profile)
    elif skill == "negative_case_design":
        _challenge_freeform(sim, profile, "Your negative cases (one per line):", "nd")
    elif skill == "rubric_definition":
        _challenge_rubric(sim, profile)
    elif skill == "calibration":
        _challenge_calibration(sim, profile)
    elif skill == "edge_case_thinking":
        _challenge_freeform(sim, profile, "Your edge cases:", "ec")
    elif skill == "eval_coverage":
        _challenge_coverage(sim, profile)


# ── Challenge renderers ──

def _challenge_failure_spotting(sim, profile):
    st.markdown(f"**{sim.get('scenario_description', '')}**")

    # User query block
    st.markdown(f"""
    <div style="background:#F2EFEB; padding:12px 16px; border-radius:6px; margin:12px 0;">
        <p style="font-size:0.78rem; color:#9C9590; margin:0 0 4px; text-transform:uppercase; letter-spacing:0.06em;">User query</p>
        <p style="margin:0; font-style:italic; color:#1A1714;">{sim.get('user_query', '')}</p>
    </div>
    """, unsafe_allow_html=True)

    source = sim.get("source_context", "")
    if source:
        with st.expander("Source / ground truth"):
            st.markdown(f"<p style='font-size:0.88rem; color:#6B6560; line-height:1.7;'>{source}</p>", unsafe_allow_html=True)

    # AI response block
    st.markdown(f"""
    <div style="border:1px solid #E5E0DB; padding:14px 18px; border-radius:6px; margin:8px 0 20px; background:#FFFFFF;">
        <p style="font-size:0.78rem; color:#9C9590; margin:0 0 6px; text-transform:uppercase; letter-spacing:0.06em;">AI response</p>
        <p style="margin:0; color:#1A1714; line-height:1.65;">{sim.get('ai_response', '')}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### What's the primary issue?")
    answer = st.radio(
        "issue",
        ["hallucination", "wrong_routing", "incomplete", "over_triggered",
         "tone_mismatch", "refused_incorrectly", "stale_data", "no_failure"],
        key="fs_answer", horizontal=True, label_visibility="collapsed",
    )
    reasoning = st.text_area("Explain your reasoning", key="fs_reasoning", height=80, placeholder="Why did you pick this failure mode?")
    _submit_row(sim, profile, f"{answer}: {reasoning}")


def _challenge_calibration(sim, profile):
    st.markdown(f"**{sim.get('scenario_description', '')}**")
    st.markdown(f"Judging dimension: `{sim.get('dimension', '')}`")

    st.markdown(f"""
    <div style="background:#F2EFEB; padding:12px 16px; border-radius:6px; margin:12px 0;">
        <p style="font-size:0.78rem; color:#9C9590; margin:0 0 4px; text-transform:uppercase; letter-spacing:0.06em;">User query</p>
        <p style="margin:0; font-style:italic; color:#1A1714;">{sim.get('user_query', '')}</p>
    </div>
    """, unsafe_allow_html=True)

    source = sim.get("source_context", "")
    if source:
        with st.expander("Source / ground truth"):
            st.markdown(f"<p style='font-size:0.88rem; color:#6B6560; line-height:1.7;'>{source}</p>", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="border:1px solid #E5E0DB; padding:14px 18px; border-radius:6px; margin:8px 0 20px; background:#FFFFFF;">
        <p style="font-size:0.78rem; color:#9C9590; margin:0 0 6px; text-transform:uppercase; letter-spacing:0.06em;">AI response</p>
        <p style="margin:0; color:#1A1714; line-height:1.65;">{sim.get('ai_response', '')}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Your verdict")
    verdict = st.radio("verdict", ["pass", "fail"], key="cal_verdict", horizontal=True, label_visibility="collapsed")
    reasoning = st.text_area("Reasoning", key="cal_reasoning", height=80, placeholder="Why pass or fail?")
    _submit_row(sim, profile, f"Verdict: {verdict}. Reasoning: {reasoning}")


def _challenge_rubric(sim, profile):
    st.markdown(f"**Dimension: {sim.get('dimension_name', '')}**")
    st.markdown(sim.get("scenario_description", ""))
    st.markdown(f"*{sim.get('prompt_to_user', '')}*")

    pass_def = st.text_area("PASS means", key="rc_pass", height=90, placeholder="Specific, observable criteria...")
    fail_def = st.text_area("FAIL means", key="rc_fail", height=90, placeholder="Specific, observable criteria...")
    edge = st.text_area("Edge cases", key="rc_edge", height=70, placeholder="Tricky situations and how to handle them...")
    _submit_row(sim, profile, f"PASS: {pass_def}\nFAIL: {fail_def}\nEdge cases: {edge}")


def _challenge_freeform(sim, profile, label, prefix):
    st.markdown(f"**{sim.get('scenario_description', '')}**")

    details = sim.get("feature_details", "")
    if details:
        st.markdown(details)

    existing = sim.get("existing_positive_cases", [])
    if existing:
        st.markdown("**Existing positive cases:**")
        for c in existing:
            st.markdown(f"- {c}")

    prompt = sim.get("prompt_to_user", "")
    if prompt:
        st.markdown(f"*{prompt}*")

    answer = st.text_area(label, key=f"{prefix}_answer", height=180, placeholder="One per line...")
    _submit_row(sim, profile, answer)


def _challenge_coverage(sim, profile):
    st.markdown(f"**{sim.get('scenario_description', '')}**")
    st.markdown("**Existing tests:**")
    for t in sim.get("existing_tests", []):
        st.markdown(f"""
        <div style="display:flex; gap:8px; align-items:baseline; margin-bottom:4px;">
            <code style="font-family:'DM Mono',monospace; font-size:0.78rem; color:#9C9590;">{t.get('id','')}</code>
            <span style="font-size:0.88rem;">&ldquo;{t.get('input','')}&rdquo; &mdash; <span style="color:#6B6560;">{t.get('checks','')}</span></span>
        </div>
        """, unsafe_allow_html=True)

    prompt = sim.get("prompt_to_user", "")
    if prompt:
        st.markdown(f"*{prompt}*")

    answer = st.text_area("Gaps you identified:", key="cov_answer", height=180, placeholder="1. Missing...\n2. No tests for...")
    _submit_row(sim, profile, answer)


# ── Submit row ──

def _submit_row(sim, profile, answer):
    c1, c2 = st.columns([4, 1])
    with c1:
        submitted = st.button("Submit", type="primary", use_container_width=True)
    with c2:
        skipped = st.button("Skip", use_container_width=True)

    if skipped:
        st.session_state.current_sim = None
        st.session_state.show_result = None
        st.rerun()

    if submitted and answer and answer.strip():
        with st.spinner("Evaluating..."):
            result = evaluate_answer(sim["skill"], sim, answer)
            st.session_state.show_result = result
            profile.record_answer(sim["skill"], result.get("correct", False), sim.get("difficulty", "medium"), result.get("xp_earned", 0))
            if st.session_state.session_id:
                profile.record_session_question(st.session_state.session_id, {
                    "skill": sim["skill"], "difficulty": sim.get("difficulty"),
                    "correct": result.get("correct", False), "score": result.get("score", 0), "xp_earned": result.get("xp_earned", 0),
                })
            profile.check_badges()
            profile.save()
        st.rerun()


# ── Result display ──

def _render_result(sim, result, profile):
    correct = result.get("correct", False)
    score = result.get("score", 0)
    xp = result.get("xp_earned", 0)

    bg = "#E8F5EE" if correct else "#FCEAEA"
    border = "#2D8659" if correct else "#C44B4B"
    label = "Correct" if correct else "Not quite"
    label_color = "#2D8659" if correct else "#C44B4B"

    st.markdown(f"""
    <div style="background:{bg}; border-left:3px solid {border}; padding:16px 20px; border-radius:0 8px 8px 0; margin-bottom:20px;">
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">
            <span style="font-size:1.1rem; font-weight:700; color:{label_color};">{label}</span>
            <span style="font-family:'DM Mono',monospace; font-size:0.82rem; color:{label_color};">+{xp} xp</span>
            <span style="font-family:'DM Mono',monospace; font-size:0.82rem; color:#6B6560; margin-left:auto;">Score: {score:.0%}</span>
        </div>
        <p style="margin:0 0 10px; color:#1A1714; line-height:1.65; font-size:0.9rem;">{result.get('feedback', '')}</p>
        <p style="margin:0; color:#6B6560; font-size:0.85rem;"><strong>Tip:</strong> {result.get('improvement_tip', '')}</p>
    </div>
    """, unsafe_allow_html=True)

    signal = result.get("skill_signal", "")
    if signal:
        st.markdown(f"<p style='font-size:0.82rem; color:#9C9590; font-style:italic;'>Signal: {signal}</p>", unsafe_allow_html=True)

    # Reference answer
    skill = sim["skill"]
    if skill == "failure_spotting":
        with st.expander("Reference answer"):
            st.markdown(f"**Failure mode:** {sim.get('correct_answer', '')}")
            st.markdown(sim.get("explanation", ""))
            st.markdown(f"**Lesson:** {sim.get('teaching_point', '')}")
    elif skill == "calibration":
        with st.expander("Judge's verdict"):
            st.markdown(f"**Verdict:** {sim.get('correct_verdict', '')}")
            st.markdown(sim.get("judge_reasoning", ""))
    elif skill == "negative_case_design":
        ideal = sim.get("ideal_negative_cases", [])
        if ideal:
            with st.expander("Reference cases"):
                for case in ideal:
                    st.markdown(f"- **{case.get('input', '')}** — {case.get('why_important', '')}")
    elif skill == "edge_case_thinking":
        ideal = sim.get("ideal_edge_cases", [])
        if ideal:
            with st.expander("Reference edge cases"):
                for case in ideal:
                    st.markdown(f"- **{case.get('case', '')}** — {case.get('why_breaks', '')}")
    elif skill == "rubric_definition":
        ref = sim.get("reference_rubric", {})
        if ref:
            with st.expander("Reference rubric"):
                st.markdown(f"**PASS:** {ref.get('pass', '')}")
                st.markdown(f"**FAIL:** {ref.get('fail', '')}")
    elif skill == "eval_coverage":
        gaps = sim.get("gaps", [])
        if gaps:
            with st.expander("Reference gaps"):
                for g in gaps:
                    st.markdown(f"- **{g.get('gap', '')}** — {g.get('why_matters', '')}")

    # Milestone check
    milestone = get_milestone_message(profile)
    if milestone:
        st.markdown(f"""
        <div style="background:#FFF8E6; border-left:3px solid #B8860B; padding:12px 16px; border-radius:0 6px 6px 0; margin:16px 0;">
            <p style="margin:0; font-size:0.88rem; color:#1A1714;">{milestone}</p>
        </div>
        """, unsafe_allow_html=True)

    if st.button("Next challenge", type="primary"):
        st.session_state.current_sim = None
        st.session_state.show_result = None
        st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Progress
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _progress_tab(profile):
    st.markdown("## Your progress")

    # Skill radar chart
    labels = [SKILL_LABELS[sk] for sk in SKILLS]
    values = [profile.skill_level(sk) for sk in SKILLS]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=labels + [labels[0]],
        fill="toself",
        fillcolor="rgba(196,93,62,0.12)",
        line=dict(color="#C45D3E", width=2),
        marker=dict(size=6, color="#C45D3E"),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="#FAF8F5",
            radialaxis=dict(visible=True, range=[0, 100], showticklabels=True, tickfont=dict(size=10, color="#9C9590"), gridcolor="#E5E0DB"),
            angularaxis=dict(tickfont=dict(size=12, family="DM Sans", color="#1A1714"), gridcolor="#E5E0DB"),
        ),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=60, t=20, b=20),
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Skill breakdown
    st.markdown("### Breakdown")
    for sk in SKILLS:
        data = profile._data["skills"].get(sk, {})
        level = profile.skill_level(sk)
        total = data.get("total", 0)
        correct = data.get("correct", 0)
        accuracy = f"{correct}/{total} ({correct/total:.0%})" if total > 0 else "No attempts"

        bar_color = "#C45D3E" if sk in profile.weak_areas else "#2D8659" if level >= 60 else "#6B6560"
        pct = max(level, 1)

        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:14px; padding:10px 0; border-bottom:1px solid #F2EFEB;">
            <span style="font-family:'DM Mono',monospace; font-size:0.72rem; color:#9C9590; width:20px;">{SKILL_ICONS[sk]}</span>
            <span style="font-weight:500; width:160px; flex-shrink:0;">{SKILL_LABELS[sk]}</span>
            <div style="flex:1; height:6px; background:#F2EFEB; border-radius:3px; overflow:hidden;">
                <div style="width:{pct}%; height:100%; background:{bar_color}; border-radius:3px; transition:width 0.4s;"></div>
            </div>
            <span style="font-family:'DM Mono',monospace; font-size:0.82rem; color:#1A1714; width:35px; text-align:right;">{level}%</span>
            <span style="font-size:0.8rem; color:#9C9590; width:90px; text-align:right;">{accuracy}</span>
        </div>
        """, unsafe_allow_html=True)

    # Session history
    sessions = profile._data.get("sessions", [])
    completed = [s for s in sessions if s.get("total", 0) > 0]
    if completed:
        st.markdown("### Recent sessions")
        for session in reversed(completed[-8:]):
            total = session.get("total", 0)
            correct = session.get("correct", 0)
            skills_practiced = ", ".join(SKILL_LABELS.get(s, s) for s in session.get("skills_practiced", []) if s)
            date = session.get("started_at", "")[:10]
            pct_correct = correct / total if total else 0
            bar_w = max(int(pct_correct * 100), 2)

            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:12px; padding:8px 0; border-bottom:1px solid #F2EFEB;">
                <span style="font-family:'DM Mono',monospace; font-size:0.78rem; color:#9C9590; width:80px;">{date}</span>
                <div style="flex:1; height:4px; background:#F2EFEB; border-radius:2px; overflow:hidden;">
                    <div style="width:{bar_w}%; height:100%; background:#2D8659; border-radius:2px;"></div>
                </div>
                <span style="font-family:'DM Mono',monospace; font-size:0.78rem; color:#1A1714; width:40px; text-align:right;">{correct}/{total}</span>
                <span style="font-size:0.78rem; color:#9C9590; flex-shrink:0;">{skills_practiced}</span>
            </div>
            """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Path
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _pathway_tab(profile):
    plan = suggest_session_plan(profile)

    st.markdown(f"## {plan['title']}")
    st.markdown(plan["description"])

    # Session plan as structured blocks
    st.markdown(f"""
    <div style="background:#F2EFEB; padding:16px 20px; border-radius:8px; margin:16px 0 24px;">
        <p style="font-size:0.78rem; color:#9C9590; text-transform:uppercase; letter-spacing:0.08em; margin:0 0 10px;">Today's plan &mdash; {plan['estimated_minutes']} min</p>
        <p style="font-size:0.9rem; color:#1A1714; margin:0 0 12px;">{plan['goal']}</p>
    """, unsafe_allow_html=True)

    plan_items = ""
    for ex in plan["exercises"]:
        diff_color = {"easy": "#2D8659", "medium": "#B8860B", "hard": "#C44B4B"}.get(ex["difficulty"], "#6B6560")
        plan_items += f"""
        <div style="display:flex; align-items:center; gap:10px; padding:6px 0;">
            <span style="font-size:0.78rem; color:{diff_color}; font-family:'DM Mono',monospace; border:1px solid {diff_color}; padding:1px 8px; border-radius:3px;">{ex['difficulty'][:3]}</span>
            <span style="font-size:0.88rem; color:#1A1714;">{SKILL_LABELS.get(ex['skill'], ex['skill'])}</span>
            <span style="font-family:'DM Mono',monospace; font-size:0.78rem; color:#9C9590;">&times;{ex['count']}</span>
        </div>"""
    st.markdown(plan_items + "</div>", unsafe_allow_html=True)

    # Recommendations
    st.markdown("### Up next")
    recs = recommend_next(profile, 5)
    for rec in recs:
        priority_bg = {"high": "#FCEEE8", "medium": "#FFF8E6", "low": "#F2EFEB"}.get(rec["priority"], "#F2EFEB")
        priority_border = {"high": "#C45D3E", "medium": "#B8860B", "low": "#D5CFC9"}.get(rec["priority"], "#D5CFC9")
        st.markdown(f"""
        <div style="border-left:3px solid {priority_border}; background:{priority_bg}; padding:10px 16px; border-radius:0 6px 6px 0; margin-bottom:8px;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="font-weight:600; font-size:0.88rem;">{rec['skill_label']}</span>
                <span style="font-family:'DM Mono',monospace; font-size:0.72rem; color:#9C9590;">{rec['difficulty']}</span>
            </div>
            <p style="margin:4px 0 0; font-size:0.82rem; color:#6B6560;">{rec['reason']}</p>
        </div>
        """, unsafe_allow_html=True)

    # Milestones
    st.markdown("### Milestones")
    total = profile._data.get("total_questions", 0)
    milestones = [5, 10, 25, 50, 100]
    cols = st.columns(len(milestones))
    for i, m in enumerate(milestones):
        done = total >= m
        with cols[i]:
            bg = "#E8F5EE" if done else "#F2EFEB"
            border_c = "#2D8659" if done else "#E5E0DB"
            num_c = "#2D8659" if done else "#9C9590"
            check = "Done" if done else f"{m - total} to go"
            st.markdown(f"""
            <div style="text-align:center; padding:14px 8px; border:1px solid {border_c}; border-radius:8px; background:{bg};">
                <p style="font-family:'DM Mono',monospace; font-size:1.4rem; font-weight:700; color:{num_c}; margin:0;">{m}</p>
                <p style="font-size:0.72rem; color:#9C9590; margin:4px 0 0;">{check}</p>
            </div>
            """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
