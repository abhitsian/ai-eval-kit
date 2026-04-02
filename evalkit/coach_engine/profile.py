"""User profile and performance tracking — the memory of the coaching system.

Stores:
- User identity and preferences
- Skill levels across 6 dimensions
- Session history with per-question results
- Weak areas for adaptive difficulty
- Streak and engagement metrics
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


COACH_DIR = Path.home() / ".evalkit" / "coach"

# The 6 eval skills we train
SKILLS = [
    "failure_spotting",      # Can you see what's wrong?
    "negative_case_design",  # Can you think about what shouldn't work?
    "rubric_definition",     # Can you articulate pass/fail?
    "edge_case_thinking",    # Can you find the weird corners?
    "calibration",           # Does your judgment align with others?
    "eval_coverage",         # Can you think holistically about test coverage?
]

SKILL_LABELS = {
    "failure_spotting": "Failure Spotting",
    "negative_case_design": "Negative Case Design",
    "rubric_definition": "Rubric Definition",
    "edge_case_thinking": "Edge Case Thinking",
    "calibration": "Calibration",
    "eval_coverage": "Eval Coverage",
}

# Difficulty tiers
LEVELS = ["beginner", "intermediate", "advanced", "expert"]


class UserProfile:
    """Persistent user profile with skill tracking and session history."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._path = COACH_DIR / f"{user_id}.json"
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self._path.exists():
            with open(self._path) as f:
                return json.load(f)
        return self._create_default()

    def _create_default(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "display_name": self.user_id,
            "product_context": "",  # What AI product they're building
            "role": "",  # PM, engineer, etc.
            "skills": {skill: {"level": 0, "xp": 0, "correct": 0, "total": 0} for skill in SKILLS},
            "overall_level": "beginner",
            "overall_xp": 0,
            "streak_days": 0,
            "last_session_date": None,
            "total_sessions": 0,
            "total_questions": 0,
            "sessions": [],  # Last 50 sessions
            "weak_areas": [],  # Skills needing work
            "strong_areas": [],  # Skills they're good at
            "unlocked_badges": [],
            "preferred_difficulty": "adaptive",  # adaptive, easy, medium, hard
            "preferred_product_types": [],  # chatbot, search, agent, etc.
            "combo": 0,  # consecutive correct answers
            "best_combo": 0,
            "session_correct": 0,  # current session running total
            "session_total": 0,
        }

    def save(self):
        COACH_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)

    # --- Identity ---

    @property
    def display_name(self) -> str:
        return self._data.get("display_name", self.user_id)

    @display_name.setter
    def display_name(self, value: str):
        self._data["display_name"] = value

    @property
    def product_context(self) -> str:
        return self._data.get("product_context", "")

    @product_context.setter
    def product_context(self, value: str):
        self._data["product_context"] = value

    @property
    def role(self) -> str:
        return self._data.get("role", "")

    @role.setter
    def role(self, value: str):
        self._data["role"] = value

    # --- Skills ---

    def skill_level(self, skill: str) -> int:
        """0-100 score for a skill."""
        return self._data["skills"].get(skill, {}).get("level", 0)

    def skill_xp(self, skill: str) -> int:
        return self._data["skills"].get(skill, {}).get("xp", 0)

    def skill_accuracy(self, skill: str) -> float:
        s = self._data["skills"].get(skill, {})
        if s.get("total", 0) == 0:
            return 0.0
        return s["correct"] / s["total"]

    def all_skill_levels(self) -> Dict[str, int]:
        return {skill: self.skill_level(skill) for skill in SKILLS}

    @property
    def overall_level(self) -> str:
        return self._data.get("overall_level", "beginner")

    @property
    def overall_xp(self) -> int:
        return self._data.get("overall_xp", 0)

    @property
    def weak_areas(self) -> List[str]:
        return self._data.get("weak_areas", [])

    @property
    def strong_areas(self) -> List[str]:
        return self._data.get("strong_areas", [])

    # --- Recording Results ---

    @property
    def combo(self) -> int:
        return self._data.get("combo", 0)

    @property
    def best_combo(self) -> int:
        return self._data.get("best_combo", 0)

    def record_answer(self, skill: str, correct: bool, difficulty: str, xp_earned: int, details: Dict = None):
        """Record a single answer result and update skill levels."""
        s = self._data["skills"].setdefault(skill, {"level": 0, "xp": 0, "correct": 0, "total": 0})
        s["total"] += 1

        # Combo tracking
        if correct:
            s["correct"] += 1
            self._data["combo"] = self._data.get("combo", 0) + 1
            self._data["best_combo"] = max(self._data.get("best_combo", 0), self._data["combo"])
            self._data["session_correct"] = self._data.get("session_correct", 0) + 1
        else:
            self._data["combo"] = 0
        self._data["session_total"] = self._data.get("session_total", 0) + 1

        # XP multiplier from combo
        combo = self._data.get("combo", 0)
        if combo >= 5:
            xp_earned = int(xp_earned * 2.0)
        elif combo >= 3:
            xp_earned = int(xp_earned * 1.5)

        s["xp"] += xp_earned

        # Update skill level (0-100 based on accuracy with minimum attempts)
        if s["total"] >= 3:
            accuracy = s["correct"] / s["total"]
            # Weight recent performance more (simple exponential moving average)
            s["level"] = min(100, int(accuracy * 100))

        self._data["overall_xp"] = self._data.get("overall_xp", 0) + xp_earned
        self._data["total_questions"] = self._data.get("total_questions", 0) + 1

        # Recalculate weak/strong areas
        self._recalculate_areas()

        # Recalculate overall level
        avg = sum(self.skill_level(sk) for sk in SKILLS) / len(SKILLS)
        if avg >= 80:
            self._data["overall_level"] = "expert"
        elif avg >= 60:
            self._data["overall_level"] = "advanced"
        elif avg >= 30:
            self._data["overall_level"] = "intermediate"
        else:
            self._data["overall_level"] = "beginner"

    def _recalculate_areas(self):
        levels = {sk: self.skill_level(sk) for sk in SKILLS if self._data["skills"][sk]["total"] >= 2}
        if not levels:
            return
        avg = sum(levels.values()) / len(levels)
        self._data["weak_areas"] = [sk for sk, lv in levels.items() if lv < avg - 10]
        self._data["strong_areas"] = [sk for sk, lv in levels.items() if lv > avg + 10]

    def start_session(self) -> str:
        """Start a new coaching session. Returns session ID."""
        session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last = self._data.get("last_session_date")

        # Streak tracking
        if last == today:
            pass  # Same day
        elif last and (datetime.fromisoformat(last.replace("Z", "+00:00")).date() -
                       datetime.now(timezone.utc).date()).days == -1:
            self._data["streak_days"] = self._data.get("streak_days", 0) + 1
        else:
            self._data["streak_days"] = 1

        self._data["last_session_date"] = today
        self._data["total_sessions"] = self._data.get("total_sessions", 0) + 1

        session = {
            "id": session_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "questions": [],
            "skills_practiced": [],
        }
        self._data["sessions"].append(session)
        # Keep last 50 sessions
        self._data["sessions"] = self._data["sessions"][-50:]
        self.save()
        return session_id

    def record_session_question(self, session_id: str, question_data: Dict):
        """Add a question result to the current session."""
        for session in reversed(self._data["sessions"]):
            if session["id"] == session_id:
                session["questions"].append(question_data)
                if question_data.get("skill") not in session["skills_practiced"]:
                    session["skills_practiced"].append(question_data.get("skill", ""))
                break
        self.save()

    def end_session(self, session_id: str):
        """Finalize a session."""
        for session in reversed(self._data["sessions"]):
            if session["id"] == session_id:
                session["ended_at"] = datetime.now(timezone.utc).isoformat()
                questions = session["questions"]
                session["total"] = len(questions)
                session["correct"] = sum(1 for q in questions if q.get("correct"))
                break
        self.save()

    # --- Badges ---

    def check_badges(self) -> List[str]:
        """Check for newly earned badges and return them."""
        new_badges = []
        existing = set(self._data.get("unlocked_badges", []))

        badge_checks = {
            "first_blood": self._data.get("total_questions", 0) >= 1,
            "getting_started": self._data.get("total_questions", 0) >= 10,
            "committed": self._data.get("total_sessions", 0) >= 5,
            "streak_3": self._data.get("streak_days", 0) >= 3,
            "streak_7": self._data.get("streak_days", 0) >= 7,
            "sharpshooter": any(self.skill_accuracy(sk) >= 0.9 and self._data["skills"][sk]["total"] >= 10 for sk in SKILLS),
            "well_rounded": all(self.skill_level(sk) >= 50 for sk in SKILLS),
            "expert_spotter": self.skill_level("failure_spotting") >= 80,
            "negative_thinker": self.skill_level("negative_case_design") >= 80,
            "rubric_master": self.skill_level("rubric_definition") >= 80,
            "centurion": self._data.get("total_questions", 0) >= 100,
        }

        for badge_id, earned in badge_checks.items():
            if earned and badge_id not in existing:
                new_badges.append(badge_id)
                self._data.setdefault("unlocked_badges", []).append(badge_id)

        if new_badges:
            self.save()
        return new_badges

    # --- Summary ---

    def summary(self) -> Dict[str, Any]:
        return {
            "display_name": self.display_name,
            "overall_level": self.overall_level,
            "overall_xp": self.overall_xp,
            "total_sessions": self._data.get("total_sessions", 0),
            "total_questions": self._data.get("total_questions", 0),
            "streak_days": self._data.get("streak_days", 0),
            "skills": {sk: {"level": self.skill_level(sk), "accuracy": f"{self.skill_accuracy(sk):.0%}",
                            "attempts": self._data["skills"][sk]["total"]} for sk in SKILLS},
            "weak_areas": self.weak_areas,
            "strong_areas": self.strong_areas,
            "badges": self._data.get("unlocked_badges", []),
        }

    def raw(self) -> Dict[str, Any]:
        return self._data
