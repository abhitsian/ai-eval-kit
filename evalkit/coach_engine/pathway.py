"""Adaptive learning pathway — recommends what to practice next.

Uses the user's profile to:
1. Identify weakest skill areas
2. Adjust difficulty to the zone of proximal development
3. Vary product types for breadth
4. Balance skill practice across dimensions
5. Suggest focus sessions for specific weaknesses
"""

from typing import Dict, List, Optional, Tuple

from evalkit.coach_engine.profile import UserProfile, SKILLS, SKILL_LABELS


def recommend_next(profile: UserProfile, count: int = 5) -> List[Dict]:
    """Recommend the next exercises based on the user's profile.

    Returns a list of recommended exercises with skill, difficulty, and reason.
    """
    recommendations = []
    skills_data = profile._data.get("skills", {})

    # Priority 1: Skills never attempted (onboarding)
    unattempted = [sk for sk in SKILLS if skills_data.get(sk, {}).get("total", 0) == 0]
    if unattempted:
        # Start with the most foundational skills
        priority_order = ["failure_spotting", "calibration", "negative_case_design",
                         "rubric_definition", "edge_case_thinking", "eval_coverage"]
        for sk in priority_order:
            if sk in unattempted and len(recommendations) < count:
                recommendations.append({
                    "skill": sk,
                    "skill_label": SKILL_LABELS[sk],
                    "difficulty": "easy",
                    "reason": f"You haven't tried {SKILL_LABELS[sk]} yet — let's start here.",
                    "priority": "high",
                })

    # Priority 2: Weak areas (below average)
    weak = profile.weak_areas
    for sk in weak:
        if len(recommendations) < count:
            level = profile.skill_level(sk)
            diff = "easy" if level < 30 else "medium"
            recommendations.append({
                "skill": sk,
                "skill_label": SKILL_LABELS[sk],
                "difficulty": diff,
                "reason": f"{SKILL_LABELS[sk]} is at {level}% — focused practice will help.",
                "priority": "high",
            })

    # Priority 3: Skills with low accuracy but enough attempts
    for sk in SKILLS:
        if len(recommendations) >= count:
            break
        data = skills_data.get(sk, {})
        if data.get("total", 0) >= 5 and (data.get("correct", 0) / max(data["total"], 1)) < 0.6:
            if not any(r["skill"] == sk for r in recommendations):
                recommendations.append({
                    "skill": sk,
                    "skill_label": SKILL_LABELS[sk],
                    "difficulty": "medium",
                    "reason": f"Accuracy on {SKILL_LABELS[sk]} is {data['correct']}/{data['total']} — let's improve.",
                    "priority": "medium",
                })

    # Priority 4: Level up strong areas
    for sk in SKILLS:
        if len(recommendations) >= count:
            break
        level = profile.skill_level(sk)
        if level >= 60 and level < 80:
            if not any(r["skill"] == sk for r in recommendations):
                recommendations.append({
                    "skill": sk,
                    "skill_label": SKILL_LABELS[sk],
                    "difficulty": "hard",
                    "reason": f"{SKILL_LABELS[sk]} is at {level}% — hard challenges will push you to expert.",
                    "priority": "medium",
                })

    # Fill remaining with variety
    import random
    remaining_skills = [sk for sk in SKILLS if not any(r["skill"] == sk for r in recommendations)]
    random.shuffle(remaining_skills)
    for sk in remaining_skills:
        if len(recommendations) >= count:
            break
        level = profile.skill_level(sk)
        diff = _adaptive_difficulty(level)
        recommendations.append({
            "skill": sk,
            "skill_label": SKILL_LABELS[sk],
            "difficulty": diff,
            "reason": f"Keeping {SKILL_LABELS[sk]} sharp.",
            "priority": "low",
        })

    return recommendations[:count]


def suggest_session_plan(profile: UserProfile) -> Dict:
    """Suggest a structured coaching session plan."""
    total_q = profile._data.get("total_questions", 0)

    if total_q == 0:
        return {
            "title": "Welcome Session",
            "description": "Let's discover your baseline across all eval skills.",
            "exercises": [
                {"skill": "failure_spotting", "count": 3, "difficulty": "easy"},
                {"skill": "calibration", "count": 2, "difficulty": "easy"},
            ],
            "estimated_minutes": 10,
            "goal": "Complete your first 5 exercises and establish your skill baseline.",
        }
    elif total_q < 20:
        weak = profile.weak_areas or ["failure_spotting", "negative_case_design"]
        return {
            "title": "Foundation Building",
            "description": "Strengthening your weakest areas while maintaining breadth.",
            "exercises": [
                {"skill": weak[0] if weak else "failure_spotting", "count": 3, "difficulty": "easy"},
                {"skill": weak[1] if len(weak) > 1 else "rubric_definition", "count": 2, "difficulty": "medium"},
                {"skill": "edge_case_thinking", "count": 2, "difficulty": "easy"},
            ],
            "estimated_minutes": 15,
            "goal": f"Get {weak[0] if weak else 'core skills'} above 40%.",
        }
    else:
        recs = recommend_next(profile, 3)
        return {
            "title": "Targeted Improvement",
            "description": "Focused practice on your growth areas.",
            "exercises": [
                {"skill": r["skill"], "count": 2, "difficulty": r["difficulty"]}
                for r in recs
            ],
            "estimated_minutes": 20,
            "goal": f"Push your weakest skill ({profile.weak_areas[0] if profile.weak_areas else 'all areas'}) up by 10%.",
        }


def _adaptive_difficulty(skill_level: int) -> str:
    """Pick difficulty in the zone of proximal development."""
    if skill_level < 25:
        return "easy"
    elif skill_level < 50:
        return "medium"
    elif skill_level < 75:
        # Mix of medium and hard
        import random
        return random.choice(["medium", "hard"])
    else:
        return "hard"


def get_milestone_message(profile: UserProfile) -> Optional[str]:
    """Check if user hit a milestone and return a message."""
    total = profile._data.get("total_questions", 0)

    milestones = {
        5: "5 exercises done — you're building eval instincts.",
        10: "10 exercises — you can now spot common AI failures faster than most PMs.",
        25: "25 exercises — you're developing real eval judgment.",
        50: "50 exercises — you're in the top tier of PM eval skills.",
        100: "100 exercises — eval master. You can design eval systems from scratch.",
    }

    return milestones.get(total)
