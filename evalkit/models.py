"""Data models for eval tasks, trials, and results."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Verdict(Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class GraderType(Enum):
    CODE = "code"
    LLM = "llm"
    HUMAN = "human"


@dataclass
class Task:
    id: str
    input: str
    surface: str
    feature: str
    expected: Dict[str, Any]
    graders: List[Dict[str, Any]]
    context: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    severity: str = "medium"
    tags: List[str] = field(default_factory=list)


@dataclass
class GraderResult:
    grader_type: GraderType
    dimension: str
    verdict: Verdict
    reasoning: str
    raw_output: str = ""
    score: Optional[float] = None


@dataclass
class TrialResult:
    task_id: str
    trial_number: int
    grader_results: List[GraderResult]
    response: str
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    token_count: int = 0

    @property
    def passed(self) -> bool:
        scorable = [g for g in self.grader_results if g.verdict != Verdict.UNKNOWN]
        if not scorable:
            return True
        return all(g.verdict == Verdict.PASS for g in scorable)


@dataclass
class TaskResult:
    task: Task
    trials: List[TrialResult]

    @property
    def pass_at_k(self) -> float:
        """At least one trial passed (capability)."""
        return 1.0 if any(t.passed for t in self.trials) else 0.0

    @property
    def pass_pow_k(self) -> float:
        """All trials passed (reliability)."""
        return 1.0 if all(t.passed for t in self.trials) else 0.0

    @property
    def pass_rate(self) -> float:
        if not self.trials:
            return 0.0
        return sum(1 for t in self.trials if t.passed) / len(self.trials)


@dataclass
class SuiteResult:
    surface: str
    feature: str
    task_results: List[TaskResult]
    threshold: float

    @property
    def pass_rate(self) -> float:
        if not self.task_results:
            return 0.0
        return sum(r.pass_rate for r in self.task_results) / len(self.task_results)

    @property
    def meets_threshold(self) -> bool:
        return self.pass_rate >= self.threshold

    @property
    def pass_at_k_rate(self) -> float:
        if not self.task_results:
            return 0.0
        return sum(r.pass_at_k for r in self.task_results) / len(self.task_results)

    @property
    def pass_pow_k_rate(self) -> float:
        if not self.task_results:
            return 0.0
        return sum(r.pass_pow_k for r in self.task_results) / len(self.task_results)
