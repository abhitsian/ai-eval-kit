"""
Adaptive Eval Coach — Personalized coaching powered by Claude.

Launch: evalkit learn
   or: streamlit run app/coach.py

Features:
- Onboarding: captures who you are and what you're building
- Adaptive simulations: generates challenges matched to your level
- Real-time evaluation: judges your answers and gives feedback
- Progress tracking: skill radar, XP, streaks, badges
- Learning pathway: recommends what to practice next
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from evalkit.coach_engine.profile import UserProfile, SKILLS, SKILL_LABELS, LEVELS
from evalkit.coach_engine.simulator import generate_simulation, PRODUCT_TYPES
from evalkit.coach_engine.evaluator import evaluate_answer
from evalkit.coach_engine.pathway import recommend_next, suggest_session_plan, get_milestone_message


def main():
    st.set_page_config(page_title="Eval Coach", layout="wide")

    # Initialize session state
    if "profile" not in st.session_state:
        st.session_state.profile = UserProfile()
    if "current_sim" not in st.session_state:
        st.session_state.current_sim = None
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "show_result" not in st.session_state:
        st.session_state.show_result = None

    profile = st.session_state.profile

    # Check if first time
    if profile._data.get("total_sessions", 0) == 0 and not st.session_state.get("onboarded"):
        _onboarding(profile)
        return

    # Main layout
    _sidebar(profile)

    tab_train, tab_progress, tab_path = st.tabs(["Train", "Progress", "Learning Path"])

    with tab_train:
        _training_tab(profile)
    with tab_progress:
        _progress_tab(profile)
    with tab_path:
        _pathway_tab(profile)


# ============================================================
# Onboarding
# ============================================================

def _onboarding(profile: UserProfile):
    st.title("Welcome to Eval Coach")
    st.markdown(
        "I'll help you build the skill of evaluating AI products — "
        "the single most important capability for PMs shipping AI.\n\n"
        "First, let me learn about you."
    )

    with st.form("onboarding"):
        name = st.text_input("Your name", value="")
        role = st.selectbox("Your role", ["Product Manager", "Senior PM", "Director of PM", "Engineering Manager", "Designer", "QA Lead", "Other"])
        product = st.text_area("What AI product are you building? (one sentence)", placeholder="e.g., An AI-powered employee hub with conversational search and agentic workflows")
        product_types = st.multiselect(
            "Which types of AI products interest you?",
            list(PRODUCT_TYPES.keys()),
            default=["chatbot"],
            format_func=lambda x: PRODUCT_TYPES[x]["name"],
        )
        submitted = st.form_submit_button("Start Coaching")

    if submitted and name:
        profile.display_name = name
        profile.role = role
        profile.product_context = product
        profile._data["preferred_product_types"] = product_types
        profile.start_session()
        profile.save()
        st.session_state.onboarded = True
        st.rerun()


# ============================================================
# Sidebar
# ============================================================

def _sidebar(profile: UserProfile):
    st.sidebar.title(f"Hi, {profile.display_name}")

    # Quick stats
    st.sidebar.metric("Level", profile.overall_level.title())
    st.sidebar.metric("XP", profile.overall_xp)

    col1, col2 = st.sidebar.columns(2)
    col1.metric("Sessions", profile._data.get("total_sessions", 0))
    col2.metric("Streak", f"{profile._data.get('streak_days', 0)}d")

    # Badges
    badges = profile._data.get("unlocked_badges", [])
    if badges:
        st.sidebar.divider()
        st.sidebar.markdown("**Badges**")
        badge_labels = {
            "first_blood": "First Exercise", "getting_started": "10 Exercises",
            "committed": "5 Sessions", "streak_3": "3-Day Streak",
            "streak_7": "7-Day Streak", "sharpshooter": "90% Accuracy",
            "well_rounded": "All Skills 50+", "expert_spotter": "Expert Spotter",
            "negative_thinker": "Negative Thinker", "rubric_master": "Rubric Master",
            "centurion": "100 Exercises",
        }
        st.sidebar.markdown(" ".join(f"`{badge_labels.get(b, b)}`" for b in badges))

    # Weak areas
    if profile.weak_areas:
        st.sidebar.divider()
        st.sidebar.markdown("**Focus Areas**")
        for sk in profile.weak_areas:
            st.sidebar.markdown(f"- {SKILL_LABELS[sk]} ({profile.skill_level(sk)}%)")


# ============================================================
# Training Tab
# ============================================================

def _training_tab(profile: UserProfile):
    st.header("Train")

    # Skill selector
    col_skill, col_product, col_go = st.columns([2, 2, 1])

    with col_skill:
        recs = recommend_next(profile, 3)
        recommended_skill = recs[0]["skill"] if recs else "failure_spotting"

        skill_options = list(SKILLS)
        # Put recommended first
        if recommended_skill in skill_options:
            skill_options.remove(recommended_skill)
            skill_options.insert(0, recommended_skill)

        skill = st.selectbox(
            "Skill",
            skill_options,
            format_func=lambda x: f"{'-> ' if x == recommended_skill else ''}{SKILL_LABELS[x]} ({profile.skill_level(x)}%)",
        )

    with col_product:
        product_type = st.selectbox(
            "Product type",
            ["auto"] + list(PRODUCT_TYPES.keys()),
            format_func=lambda x: "Auto (varies)" if x == "auto" else PRODUCT_TYPES[x]["name"],
        )

    with col_go:
        st.markdown("<br>", unsafe_allow_html=True)
        generate = st.button("Generate Challenge", type="primary", use_container_width=True)

    if recs and not st.session_state.current_sim:
        st.info(f"Recommended: **{recs[0]['skill_label']}** ({recs[0]['difficulty']}) — {recs[0]['reason']}")

    # Generate new simulation
    if generate:
        with st.spinner("Generating challenge..."):
            pt = None if product_type == "auto" else product_type
            sim = generate_simulation(skill, profile, pt)
            st.session_state.current_sim = sim
            st.session_state.show_result = None
            if not st.session_state.session_id:
                st.session_state.session_id = profile.start_session()
        st.rerun()

    # Display current simulation
    sim = st.session_state.current_sim
    if sim:
        _render_simulation(sim, profile)


def _render_simulation(sim: dict, profile: UserProfile):
    skill = sim["skill"]
    st.divider()

    # Header
    diff_colors = {"easy": "green", "medium": "orange", "hard": "red"}
    diff = sim.get("difficulty", "medium")
    st.markdown(
        f"**{SKILL_LABELS[skill]}** | "
        f":{diff_colors.get(diff, 'gray')}[{diff.upper()}] | "
        f"{sim.get('product_name', '')} | "
        f"+{sim.get('xp_value', 15)} XP"
    )

    # Render based on skill type
    if skill == "failure_spotting":
        _render_failure_spotting(sim, profile)
    elif skill == "negative_case_design":
        _render_negative_design(sim, profile)
    elif skill == "rubric_definition":
        _render_rubric_craft(sim, profile)
    elif skill == "calibration":
        _render_calibration(sim, profile)
    elif skill == "edge_case_thinking":
        _render_edge_cases(sim, profile)
    elif skill == "eval_coverage":
        _render_coverage(sim, profile)


def _render_failure_spotting(sim: dict, profile: UserProfile):
    st.markdown(f"**Scenario:** {sim.get('scenario_description', '')}")
    st.markdown(f"**User asked:** *\"{sim.get('user_query', '')}\"*")

    source = sim.get("source_context", "")
    if source:
        with st.expander("Source / Ground Truth"):
            st.info(source)

    st.markdown("**AI responded:**")
    st.warning(sim.get("ai_response", ""))

    st.markdown("---")

    answer = st.radio(
        "What's the primary issue?",
        ["hallucination", "wrong_routing", "incomplete", "over_triggered",
         "tone_mismatch", "refused_incorrectly", "stale_data", "no_failure"],
        key="fs_answer",
    )
    reasoning = st.text_area("Why? (explain your reasoning)", key="fs_reasoning", height=80)

    _submit_and_evaluate(sim, profile, f"{answer}: {reasoning}")


def _render_negative_design(sim: dict, profile: UserProfile):
    st.markdown(f"**Feature:** {sim.get('scenario_description', '')}")
    st.markdown("**Existing positive test cases:**")
    for case in sim.get("existing_positive_cases", []):
        st.markdown(f"- {case}")

    st.markdown("---")
    st.markdown(f"**{sim.get('prompt_to_user', 'Write negative test cases:')}**")

    answer = st.text_area(
        "Your negative cases (one per line):",
        key="nd_answer", height=200,
        placeholder="1. Input that should be rejected because...\n2. Edge case where...\n3. Security test:...",
    )
    _submit_and_evaluate(sim, profile, answer)


def _render_rubric_craft(sim: dict, profile: UserProfile):
    st.markdown(f"**Dimension:** {sim.get('dimension_name', '')}")
    st.markdown(f"**Context:** {sim.get('scenario_description', '')}")
    st.markdown("---")
    st.markdown(f"**{sim.get('prompt_to_user', 'Define your rubric:')}**")

    pass_def = st.text_area("PASS means:", key="rc_pass", height=100)
    fail_def = st.text_area("FAIL means:", key="rc_fail", height=100)
    edge = st.text_area("Edge cases to consider:", key="rc_edge", height=80)

    answer = f"PASS: {pass_def}\nFAIL: {fail_def}\nEdge cases: {edge}"
    _submit_and_evaluate(sim, profile, answer)


def _render_calibration(sim: dict, profile: UserProfile):
    st.markdown(f"**Scenario:** {sim.get('scenario_description', '')}")
    st.markdown(f"**Dimension:** `{sim.get('dimension', '')}`")
    st.markdown(f"**User asked:** *\"{sim.get('user_query', '')}\"*")

    source = sim.get("source_context", "")
    if source:
        with st.expander("Source / Ground Truth"):
            st.info(source)

    st.markdown("**AI responded:**")
    st.warning(sim.get("ai_response", ""))

    st.markdown("---")
    verdict = st.radio("Your verdict:", ["pass", "fail"], key="cal_verdict", horizontal=True)
    reasoning = st.text_area("Reasoning:", key="cal_reasoning", height=80)

    answer = f"Verdict: {verdict}. Reasoning: {reasoning}"
    _submit_and_evaluate(sim, profile, answer)


def _render_edge_cases(sim: dict, profile: UserProfile):
    st.markdown(f"**Feature:** {sim.get('scenario_description', '')}")
    st.markdown(f"**How it works:** {sim.get('feature_details', '')}")
    st.markdown("---")
    st.markdown(f"**{sim.get('prompt_to_user', 'What edge cases could break this?')}**")

    answer = st.text_area(
        "Your edge cases:",
        key="ec_answer", height=200,
        placeholder="1. What if the user...\n2. What happens when...\n3. Edge case:...",
    )
    _submit_and_evaluate(sim, profile, answer)


def _render_coverage(sim: dict, profile: UserProfile):
    st.markdown(f"**{sim.get('scenario_description', '')}**")
    st.markdown("**Existing tests:**")
    for test in sim.get("existing_tests", []):
        st.markdown(f"- `{test.get('id', '')}`: *\"{test.get('input', '')}\"* — checks: {test.get('checks', '')}")

    st.markdown("---")
    st.markdown(f"**{sim.get('prompt_to_user', 'What gaps do you see?')}**")

    answer = st.text_area(
        "Gaps you identified:",
        key="cov_answer", height=200,
        placeholder="1. Missing: ... (because...)\n2. No tests for...\n3. Gap:...",
    )
    _submit_and_evaluate(sim, profile, answer)


def _submit_and_evaluate(sim: dict, profile: UserProfile, answer: str):
    """Common submit + evaluate + feedback flow."""
    col_submit, col_skip = st.columns([3, 1])

    with col_submit:
        submitted = st.button("Submit Answer", type="primary", use_container_width=True)
    with col_skip:
        skipped = st.button("Skip", use_container_width=True)

    if skipped:
        st.session_state.current_sim = None
        st.session_state.show_result = None
        st.rerun()

    if submitted and answer.strip():
        with st.spinner("Evaluating your answer..."):
            result = evaluate_answer(sim["skill"], sim, answer)
            st.session_state.show_result = result

            # Record in profile
            profile.record_answer(
                skill=sim["skill"],
                correct=result.get("correct", False),
                difficulty=sim.get("difficulty", "medium"),
                xp_earned=result.get("xp_earned", 0),
            )

            # Record in session
            if st.session_state.session_id:
                profile.record_session_question(st.session_state.session_id, {
                    "skill": sim["skill"],
                    "difficulty": sim.get("difficulty"),
                    "correct": result.get("correct", False),
                    "score": result.get("score", 0),
                    "xp_earned": result.get("xp_earned", 0),
                })

            # Check badges
            new_badges = profile.check_badges()

            # Check milestones
            milestone = get_milestone_message(profile)

            profile.save()

        st.rerun()

    # Show result if available
    result = st.session_state.show_result
    if result:
        st.divider()

        if result.get("correct"):
            st.success(f"Correct! +{result.get('xp_earned', 0)} XP")
        else:
            st.error(f"Not quite. +{result.get('xp_earned', 0)} XP")

        st.markdown(f"**Score:** {result.get('score', 0):.0%}")
        st.markdown(f"**Feedback:** {result.get('feedback', '')}")
        st.markdown(f"**Tip:** {result.get('improvement_tip', '')}")

        if result.get("skill_signal"):
            st.markdown(f"*Signal: {result['skill_signal']}*")

        # Show correct answer for learning
        if sim["skill"] == "failure_spotting":
            with st.expander("Correct answer"):
                st.markdown(f"**Failure:** {sim.get('correct_answer', '')}")
                st.markdown(f"**Why:** {sim.get('explanation', '')}")
                st.markdown(f"**Lesson:** {sim.get('teaching_point', '')}")
        elif sim["skill"] == "calibration":
            with st.expander("Judge's answer"):
                st.markdown(f"**Verdict:** {sim.get('correct_verdict', '')}")
                st.markdown(f"**Reasoning:** {sim.get('judge_reasoning', '')}")

        if st.button("Next Challenge", type="primary"):
            st.session_state.current_sim = None
            st.session_state.show_result = None
            st.rerun()


# ============================================================
# Progress Tab
# ============================================================

def _progress_tab(profile: UserProfile):
    st.header("Your Progress")

    import plotly.graph_objects as go

    # Skill radar
    skills = list(SKILL_LABELS.values())
    levels = [profile.skill_level(sk) for sk in SKILLS]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=levels + [levels[0]],  # Close the polygon
        theta=skills + [skills[0]],
        fill="toself",
        name="Your Skills",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Skill Radar",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Per-skill detail
    st.subheader("Skill Breakdown")
    for sk in SKILLS:
        data = profile._data["skills"].get(sk, {})
        level = profile.skill_level(sk)
        total = data.get("total", 0)
        correct = data.get("correct", 0)
        accuracy = f"{correct}/{total} ({correct/total:.0%})" if total > 0 else "No attempts"

        col_name, col_bar, col_stats = st.columns([2, 4, 2])
        with col_name:
            st.markdown(f"**{SKILL_LABELS[sk]}**")
        with col_bar:
            st.progress(level / 100, text=f"{level}%")
        with col_stats:
            st.markdown(f"{accuracy}")

    # Session history
    sessions = profile._data.get("sessions", [])
    if sessions:
        st.subheader("Recent Sessions")
        for session in reversed(sessions[-10:]):
            total = session.get("total", 0)
            correct = session.get("correct", 0)
            skills_practiced = ", ".join(SKILL_LABELS.get(s, s) for s in session.get("skills_practiced", []))
            date = session.get("started_at", "")[:10]
            if total > 0:
                st.markdown(f"- **{date}**: {correct}/{total} correct | {skills_practiced}")


# ============================================================
# Pathway Tab
# ============================================================

def _pathway_tab(profile: UserProfile):
    st.header("Learning Path")

    # Session plan
    plan = suggest_session_plan(profile)
    st.subheader(plan["title"])
    st.markdown(plan["description"])
    st.markdown(f"**Goal:** {plan['goal']}")
    st.markdown(f"**Estimated time:** {plan['estimated_minutes']} minutes")

    st.markdown("**Today's exercises:**")
    for ex in plan["exercises"]:
        st.markdown(f"- {SKILL_LABELS.get(ex['skill'], ex['skill'])} x{ex['count']} ({ex['difficulty']})")

    st.divider()

    # Recommendations
    st.subheader("Recommended Next")
    recs = recommend_next(profile, 5)
    for rec in recs:
        priority_colors = {"high": "red", "medium": "orange", "low": "gray"}
        st.markdown(
            f"- **{rec['skill_label']}** ({rec['difficulty']}) — {rec['reason']} "
            f"[:{priority_colors.get(rec['priority'], 'gray')}[{rec['priority']}]]"
        )

    # Milestones
    st.divider()
    st.subheader("Milestones")
    total = profile._data.get("total_questions", 0)
    milestones = [5, 10, 25, 50, 100]
    for m in milestones:
        if total >= m:
            st.markdown(f"- [x] {m} exercises")
        else:
            st.markdown(f"- [ ] {m} exercises ({m - total} to go)")


if __name__ == "__main__":
    main()
