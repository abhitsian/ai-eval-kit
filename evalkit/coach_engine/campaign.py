"""Campaign mode — story-driven eval training.

You're a PM at a fictional company. Your AI product launches in 6 weeks.
Each week, the AI gets better but new failure modes appear.
Your job: catch them before users do.

Week 1: Obvious failures. Easy.
Week 2: Hallucinations get sneakier.
Week 3: Edge cases start hitting. Intent routing breaks.
Week 4: Tone and sensitivity issues surface.
Week 5: Everything at once. Gauntlet.
Week 6: Launch week. Boss rounds. High stakes.
"""

from typing import Any, Dict, List

CAMPAIGN_WEEKS = [
    {
        "week": 1,
        "title": "First Look",
        "company": "NovaCare Health",
        "product": "AI patient support assistant for a healthcare company",
        "narrative": (
            "You just joined NovaCare as the PM for their AI patient support assistant. "
            "The CEO demoed it at a board meeting and now wants to launch in 6 weeks. "
            "You open the logs and start reviewing. The first batch looks... rough."
        ),
        "challenges": [
            {"skill": "failure_spotting", "difficulty": "easy", "context": "Patient asks about medication dosage and the AI invents a number"},
            {"skill": "failure_spotting", "difficulty": "easy", "context": "Patient asks about appointment scheduling and gets routed to billing"},
            {"skill": "calibration", "difficulty": "easy", "context": "AI answers a simple insurance question — is this actually correct?"},
        ],
        "unlock_xp": 0,
        "pass_requirement": 2,  # need 2/3 correct to advance
    },
    {
        "week": 2,
        "title": "The Sneaky Ones",
        "company": "NovaCare Health",
        "product": "AI patient support assistant",
        "narrative": (
            "The engineering team fixed the obvious failures. But QA is flagging responses that "
            "*look* correct at first glance. The hallucinations are getting subtle — "
            "correct first paragraph, invented details buried in the middle."
        ),
        "challenges": [
            {"skill": "failure_spotting", "difficulty": "medium", "context": "Answer is 90% correct but invents one specific detail about coverage limits"},
            {"skill": "failure_spotting", "difficulty": "medium", "context": "AI answers about a policy that was updated last month — cites the old version"},
            {"skill": "negative_case_design", "difficulty": "easy", "context": "Write cases for the medication FAQ feature — what should the AI refuse to answer?"},
            {"skill": "calibration", "difficulty": "medium", "context": "Borderline response about treatment options — pass or fail?"},
        ],
        "unlock_xp": 30,
        "pass_requirement": 3,
    },
    {
        "week": 3,
        "title": "Edge Cases Hit",
        "company": "NovaCare Health",
        "product": "AI patient support assistant",
        "narrative": (
            "Design partner Mercy Hospital started testing with real patients. "
            "The feedback is coming in: 'It works for simple questions but falls apart "
            "when patients ask anything unusual.' Time to stress-test."
        ),
        "challenges": [
            {"skill": "edge_case_thinking", "difficulty": "medium", "context": "The appointment booking agent — what edge cases could break it?"},
            {"skill": "failure_spotting", "difficulty": "hard", "context": "Patient asks about a drug interaction — AI gives a confident but slightly wrong answer"},
            {"skill": "negative_case_design", "difficulty": "medium", "context": "A patient types in Spanish — what should happen?"},
            {"skill": "eval_coverage", "difficulty": "easy", "context": "Review the existing test suite for medication Q&A — what's missing?"},
        ],
        "unlock_xp": 80,
        "pass_requirement": 3,
    },
    {
        "week": 4,
        "title": "The Human Side",
        "company": "NovaCare Health",
        "product": "AI patient support assistant",
        "narrative": (
            "A patient wrote to the CEO: 'Your AI told me to just take Tylenol when I described "
            "chest pain symptoms.' The tone and safety failures are the ones that make the news. "
            "You need to lock down sensitivity handling."
        ),
        "challenges": [
            {"skill": "failure_spotting", "difficulty": "hard", "context": "Patient describes anxiety symptoms — AI responds cheerfully with generic advice"},
            {"skill": "rubric_definition", "difficulty": "medium", "context": "Define pass/fail for 'medical safety' — when must the AI escalate to a human?"},
            {"skill": "calibration", "difficulty": "hard", "context": "AI declines to answer a simple diet question citing 'medical advice' — over-refusal or appropriate caution?"},
            {"skill": "negative_case_design", "difficulty": "hard", "context": "Write cases that test the boundary between 'helpful info' and 'medical advice the AI shouldn't give'"},
        ],
        "unlock_xp": 150,
        "pass_requirement": 3,
    },
    {
        "week": 5,
        "title": "Full Audit",
        "company": "NovaCare Health",
        "product": "AI patient support assistant",
        "narrative": (
            "Two weeks to launch. The compliance team wants a full quality audit. "
            "Every surface, every failure mode. You need to prove the system is ready."
        ),
        "challenges": [
            {"skill": "eval_coverage", "difficulty": "hard", "context": "The full eval suite — audit it for gaps across all surfaces"},
            {"skill": "rubric_definition", "difficulty": "hard", "context": "Define the rubric for 'appointment booking correctness' — the highest-traffic feature"},
            {"skill": "edge_case_thinking", "difficulty": "hard", "context": "The AI handles prescription refills — what could go wrong?"},
            {"skill": "failure_spotting", "difficulty": "hard", "context": "Subtle data staleness — patient's insurance changed but AI uses old data"},
            {"skill": "calibration", "difficulty": "hard", "context": "AI provides a perfect answer but takes 12 seconds — pass or fail?"},
        ],
        "unlock_xp": 250,
        "pass_requirement": 4,
    },
    {
        "week": 6,
        "title": "Launch Week",
        "company": "NovaCare Health",
        "product": "AI patient support assistant",
        "narrative": (
            "It's launch day. The CEO is on stage. Mercy Hospital goes live with 50,000 patients. "
            "One last round of checks. These are the hardest cases — the ones that would "
            "make the front page if they slip through."
        ),
        "challenges": [
            {"skill": "failure_spotting", "difficulty": "expert", "context": "The AI seems perfect — but there's a subtle issue that could affect thousands of patients"},
            {"skill": "calibration", "difficulty": "expert", "context": "Response is technically correct but could be misinterpreted in a dangerous way"},
            {"skill": "negative_case_design", "difficulty": "expert", "context": "An adversarial user tries to get the AI to provide a diagnosis — does it hold?"},
        ],
        "unlock_xp": 400,
        "pass_requirement": 2,
    },
]


def get_campaign_state(profile_data: dict) -> dict:
    """Get current campaign progress from profile data."""
    campaign = profile_data.get("campaign", {
        "current_week": 1,
        "week_scores": {},  # {week: {correct: n, total: n}}
        "completed": False,
        "started": False,
    })
    return campaign


def get_current_week(campaign_state: dict) -> dict:
    """Get the current week's campaign data."""
    week_num = campaign_state.get("current_week", 1)
    if week_num < 1 or week_num > len(CAMPAIGN_WEEKS):
        return CAMPAIGN_WEEKS[-1]
    return CAMPAIGN_WEEKS[week_num - 1]


def can_advance(campaign_state: dict) -> bool:
    """Check if the user can advance to the next week."""
    week_num = campaign_state.get("current_week", 1)
    week_data = CAMPAIGN_WEEKS[week_num - 1]
    scores = campaign_state.get("week_scores", {}).get(str(week_num), {"correct": 0, "total": 0})
    return scores.get("correct", 0) >= week_data["pass_requirement"]


def advance_week(campaign_state: dict) -> dict:
    """Advance to the next week."""
    week_num = campaign_state.get("current_week", 1)
    if week_num < len(CAMPAIGN_WEEKS):
        campaign_state["current_week"] = week_num + 1
    else:
        campaign_state["completed"] = True
    return campaign_state


def record_campaign_answer(campaign_state: dict, week: int, correct: bool) -> dict:
    """Record a campaign challenge result."""
    key = str(week)
    if key not in campaign_state.get("week_scores", {}):
        campaign_state.setdefault("week_scores", {})[key] = {"correct": 0, "total": 0}
    campaign_state["week_scores"][key]["total"] += 1
    if correct:
        campaign_state["week_scores"][key]["correct"] += 1
    return campaign_state
