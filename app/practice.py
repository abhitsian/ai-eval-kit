"""
Eval Practice Mode — Interactive training for PMs learning to write evals.

Launch: evalkit practice
   or: streamlit run app/practice.py

Four skill tracks:
1. Spot the Failure — identify what's wrong with AI responses
2. Write the Eval — write test cases for a given scenario
3. Define the Rubric — articulate pass/fail criteria
4. Calibration — compare your judgment against an LLM judge
"""

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from evalkit.challenges import (
    SPOT_THE_FAILURE, WRITE_THE_EVAL, DEFINE_THE_RUBRIC, CALIBRATION_PAIRS,
)


def main():
    st.set_page_config(page_title="Eval Practice", layout="wide", page_icon="🎯")
    st.title("Eval Practice Mode")
    st.markdown("*Build your eval skills through hands-on exercises.*")

    # Track progress in session state
    if "score" not in st.session_state:
        st.session_state.score = {"spot": 0, "write": 0, "rubric": 0, "calibrate": 0, "total_attempted": 0}

    # Sidebar — skill selector + progress
    st.sidebar.header("Your Progress")
    score = st.session_state.score
    total = score["total_attempted"]
    correct = score["spot"] + score["calibrate"]
    if total > 0:
        st.sidebar.metric("Exercises Completed", total)
        st.sidebar.metric("Accuracy (scored)", f"{correct}/{total}" if total else "—")
    st.sidebar.divider()

    skill = st.sidebar.radio(
        "Skill Track",
        ["Spot the Failure", "Write the Eval", "Define the Rubric", "Calibration"],
        captions=[
            "Identify what's wrong with AI responses",
            "Write test cases for a scenario",
            "Define pass/fail criteria for a dimension",
            "Compare your judgment against an LLM judge",
        ],
    )

    st.sidebar.divider()
    st.sidebar.markdown(
        "**Why practice evals?**\n\n"
        "Hamel Husain: *'The people who know what a good answer looks like are domain experts, not ML engineers.'*\n\n"
        "You are the domain expert. This trains your judgment."
    )

    if skill == "Spot the Failure":
        _spot_the_failure()
    elif skill == "Write the Eval":
        _write_the_eval()
    elif skill == "Define the Rubric":
        _define_the_rubric()
    elif skill == "Calibration":
        _calibration()


# ============================================================
# SKILL 1: Spot the Failure
# ============================================================

def _spot_the_failure():
    st.header("Spot the Failure")
    st.markdown(
        "You'll see an AI response to an employee query. "
        "Your job: **identify what's wrong** (or recognize that it's correct)."
    )

    difficulty = st.selectbox("Difficulty", ["all", "easy", "medium", "hard"])
    challenges = SPOT_THE_FAILURE
    if difficulty != "all":
        challenges = [c for c in challenges if c["difficulty"] == difficulty]

    for i, challenge in enumerate(challenges):
        with st.expander(
            f"Challenge {i+1}/{len(challenges)} — {challenge['difficulty'].upper()} — {challenge['scenario']}",
            expanded=(i == 0),
        ):
            # Show the scenario
            st.markdown(f"**Scenario:** {challenge['scenario']}")
            st.markdown(f"**User said:** *\"{challenge['user_input']}\"*")

            if challenge.get("source_context"):
                st.markdown("**Source document:**")
                st.info(challenge["source_context"])

            st.markdown("**AI responded:**")
            st.warning(challenge["ai_response"])

            # PM's answer
            st.markdown("---")
            st.markdown("**What's the issue?**")

            options = [
                "hallucination — AI fabricated information",
                "wrong_routing — sent to wrong handler",
                "incomplete — missing critical info",
                "over_triggered — took action when user just asked a question",
                "tone_mismatch — inappropriate tone for the situation",
                "refused_incorrectly — said it can't when it should",
                "stale_data — outdated information",
                "no_failure — this response is actually good",
            ]

            answer = st.radio(
                "Select the primary failure mode:",
                options,
                key=f"stf_answer_{challenge['id']}",
            )

            if st.button("Check Answer", key=f"stf_check_{challenge['id']}"):
                selected = answer.split(" — ")[0]
                correct = challenge["correct_failure"]

                if selected == correct:
                    st.success(f"Correct! This is a **{correct}** failure.")
                    st.session_state.score["spot"] += 1
                else:
                    st.error(f"Not quite. The primary failure is **{correct}**.")

                st.session_state.score["total_attempted"] += 1

                st.markdown(f"**Explanation:** {challenge['explanation']}")
                st.markdown(f"**Key lesson:** {challenge['teaching_point']}")


# ============================================================
# SKILL 2: Write the Eval
# ============================================================

def _write_the_eval():
    st.header("Write the Eval")
    st.markdown(
        "You'll get a product scenario. Your job: **write test cases** that would catch real failures. "
        "Think about positive cases, negative cases, edge cases, and routing boundaries."
    )

    for i, challenge in enumerate(WRITE_THE_EVAL):
        with st.expander(
            f"Exercise {i+1} — {challenge['difficulty'].upper()} — {challenge['title']}",
            expanded=(i == 0),
        ):
            st.markdown(f"**Scenario:** {challenge['description']}")
            st.markdown(f"**Product context:** {challenge['product_context']}")

            st.markdown("---")
            st.markdown("**Write your test cases below.** Try to cover:")
            st.markdown("- Happy path (things that should work)")
            st.markdown("- Negative cases (things that should NOT work)")
            st.markdown("- Edge cases (unusual but realistic scenarios)")
            st.markdown("- Routing boundaries (when the AI should/shouldn't act)")

            # Input area for the PM to write cases
            user_cases = st.text_area(
                "Your test cases (one per line — describe the input and what you'd check):",
                height=200,
                key=f"wte_input_{challenge['id']}",
                placeholder="Example:\nInput: 'reset my password' → should ask for email verification\nInput: 'what are password rules?' → should answer from KB, NOT trigger reset",
            )

            col_hint, col_show = st.columns(2)
            with col_hint:
                if st.button("Show Hints", key=f"wte_hint_{challenge['id']}"):
                    for hint in challenge["hints"]:
                        st.markdown(f"- {hint}")

            with col_show:
                if st.button("Show Example Answer", key=f"wte_show_{challenge['id']}"):
                    st.markdown("**Example good eval cases:**")
                    for task in challenge["example_good_eval"]["tasks"]:
                        type_badge = {"positive": "green", "negative": "red", "negative_security": "red", "routing": "blue", "filter_accuracy": "blue", "intent_understanding": "blue", "ambiguity": "orange", "workflow": "blue", "guardrail": "red"}.get(task["type"], "gray")
                        st.markdown(f"- **[{task['type']}]** Input: *\"{task['input']}\"* → {task['expected']}")

                    st.markdown("**Common mistakes PMs make:**")
                    for mistake in challenge["common_mistakes"]:
                        st.markdown(f"- {mistake}")

                    st.session_state.score["write"] += 1
                    st.session_state.score["total_attempted"] += 1


# ============================================================
# SKILL 3: Define the Rubric
# ============================================================

def _define_the_rubric():
    st.header("Define the Rubric")
    st.markdown(
        "You'll get an eval dimension. Your job: **define exactly what PASS and FAIL mean.** "
        "A rubric is good when two people reading it would give the same verdict independently."
    )

    for i, challenge in enumerate(DEFINE_THE_RUBRIC):
        with st.expander(
            f"Exercise {i+1} — {challenge['difficulty'].upper()} — {challenge['dimension']}",
            expanded=(i == 0),
        ):
            st.markdown(f"**Dimension:** {challenge['dimension']}")
            st.markdown(f"**Scenario:** {challenge['scenario']}")

            st.markdown("---")
            st.markdown("**Write your rubric:**")

            user_pass = st.text_area(
                "PASS means:",
                key=f"dtr_pass_{challenge['id']}",
                height=100,
                placeholder="Describe specific, observable criteria for a passing response...",
            )
            user_fail = st.text_area(
                "FAIL means:",
                key=f"dtr_fail_{challenge['id']}",
                height=100,
                placeholder="Describe specific, observable criteria for a failing response...",
            )

            if st.button("Show Reference Rubric", key=f"dtr_show_{challenge['id']}"):
                st.markdown("**Reference rubric:**")
                st.success(challenge["good_rubric"])

                st.markdown("**Common mistakes when writing rubrics:**")
                for mistake in challenge["common_mistakes"]:
                    st.markdown(f"- {mistake}")

                st.session_state.score["rubric"] += 1
                st.session_state.score["total_attempted"] += 1


# ============================================================
# SKILL 4: Calibration
# ============================================================

def _calibration():
    st.header("Calibration")
    st.markdown(
        "You'll see an AI response. Give your verdict first, then see how the LLM judge scored it. "
        "**The goal is alignment** — if you and the judge disagree, the discussion of *why* is where learning happens."
    )

    for i, pair in enumerate(CALIBRATION_PAIRS):
        with st.expander(
            f"Case {i+1}/{len(CALIBRATION_PAIRS)} — {pair['dimension']}",
            expanded=(i == 0),
        ):
            st.markdown(f"**Dimension being judged:** `{pair['dimension']}`")
            st.markdown(f"**User asked:** *\"{pair['user_input']}\"*")

            if pair.get("source"):
                st.markdown("**Source:**")
                st.info(pair["source"])

            st.markdown("**AI responded:**")
            st.warning(pair["ai_response"])

            st.markdown("---")
            your_verdict = st.radio(
                "Your verdict:",
                ["pass", "fail", "unknown"],
                key=f"cal_verdict_{pair['id']}",
                horizontal=True,
            )

            your_reasoning = st.text_input(
                "Your reasoning (one sentence):",
                key=f"cal_reason_{pair['id']}",
            )

            if st.button("Compare with LLM Judge", key=f"cal_compare_{pair['id']}"):
                llm_verdict = pair["llm_verdict"]
                agreed = your_verdict == llm_verdict

                if agreed:
                    st.success(f"You agreed with the judge! Both said: **{llm_verdict.upper()}**")
                    st.session_state.score["calibrate"] += 1
                else:
                    st.error(f"Disagreement — You: **{your_verdict.upper()}**, Judge: **{llm_verdict.upper()}**")

                st.session_state.score["total_attempted"] += 1

                st.markdown(f"**Judge's reasoning:** {pair['llm_reasoning']}")
                st.markdown(f"**Why this is tricky:** {pair['tricky_because']}")

                if not agreed:
                    st.markdown(
                        "**Disagreement is normal and valuable.** When you disagree with the judge, it means either:\n"
                        "1. Your rubric needs refinement (most common)\n"
                        "2. The LLM judge needs recalibration\n"
                        "3. The case is genuinely borderline\n\n"
                        "Track these disagreements — they're where your rubrics get better."
                    )


if __name__ == "__main__":
    main()
