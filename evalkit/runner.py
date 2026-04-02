"""Generic eval runner — works with any product config."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from evalkit.config import ProductConfig
from evalkit.models import (
    GraderResult, GraderType, SuiteResult, Task, TaskResult, TrialResult, Verdict,
)
from evalkit.graders import grade as code_grade
from evalkit.judge import run_judge
from evalkit.loader import load_suite


class EvalRunner:
    """Runs eval tasks against any AI product target."""

    def __init__(
        self,
        config: ProductConfig,
        target_fn: Optional[Callable] = None,
    ):
        """
        Args:
            config: ProductConfig loaded from product.yaml.
            target_fn: Your AI product function.
                Signature: (input: str, context: dict) -> dict
                The response dict should contain relevant keys like:
                    text, intent, data, citations, actions, tools_called, etc.
                Whatever your graders and judges need to check.
        """
        self.config = config
        self.target_fn = target_fn or self._mock_target
        self.trials = config.runner_config.get("trials", 3)

    def run_suite(self, surface: str, feature: Optional[str] = None) -> SuiteResult:
        """Run all tasks in a surface eval suite."""
        tasks = load_suite(self.config.evals_dir, surface, feature)
        threshold = self.config.surface_threshold(surface)

        task_results = []
        for task in tasks:
            result = self.run_task(task)
            task_results.append(result)

        return SuiteResult(
            surface=surface,
            feature=feature or "all",
            task_results=task_results,
            threshold=threshold,
        )

    def run_task(self, task: Task) -> TaskResult:
        trials = []
        for trial_num in range(self.trials):
            trial = self._run_trial(task, trial_num)
            trials.append(trial)
        return TaskResult(task=task, trials=trials)

    def _run_trial(self, task: Task, trial_number: int) -> TrialResult:
        start = time.monotonic()
        response = self.target_fn(task.input, task.context)
        latency_ms = (time.monotonic() - start) * 1000

        grader_results = []
        for grader_spec in task.graders:
            result = self._run_grader(grader_spec, response, task)
            grader_results.append(result)

        return TrialResult(
            task_id=task.id,
            trial_number=trial_number,
            grader_results=grader_results,
            response=json.dumps(response) if isinstance(response, dict) else str(response),
            latency_ms=latency_ms,
        )

    def _run_grader(self, grader_spec: Dict, response: Dict, task: Task) -> GraderResult:
        grader_type = grader_spec.get("type", "code")

        if grader_type == "code":
            check_name = grader_spec["check"]
            return code_grade(check_name, response, task.expected)

        elif grader_type == "llm":
            dimension = grader_spec["dimension"]
            response_text = response.get("text", json.dumps(response))
            retrieved = response.get("retrieved_context", "")
            return run_judge(
                dimension=dimension,
                input_text=task.input,
                response_text=response_text,
                retrieved_context=retrieved,
                judges_dir=self.config.judges_dir,
                llm_config=self.config.llm_config,
            )

        return GraderResult(
            grader_type=GraderType.CODE, dimension="unknown",
            verdict=Verdict.UNKNOWN, reasoning=f"Unknown grader type: {grader_type}",
        )

    def _mock_target(self, input_text: str, context: Dict) -> Dict:
        """Mock target for testing the eval framework."""
        return {
            "text": f"[MOCK] Response to: {input_text}",
            "intent": "unknown",
            "data": [],
            "citations": [],
            "actions": [],
            "tools_called": [],
        }

    def save_results(self, suite_result: SuiteResult, output_dir: Optional[Path] = None) -> Path:
        output_dir = output_dir or (self.config.data_dir / "results")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{suite_result.surface}_{suite_result.feature}_{timestamp}.json"

        results_data = {
            "product": self.config.product_name,
            "surface": suite_result.surface,
            "feature": suite_result.feature,
            "timestamp": timestamp,
            "threshold": suite_result.threshold,
            "pass_rate": suite_result.pass_rate,
            "pass_at_k": suite_result.pass_at_k_rate,
            "pass_pow_k": suite_result.pass_pow_k_rate,
            "meets_threshold": suite_result.meets_threshold,
            "tasks": [
                {
                    "task_id": tr.task.id,
                    "input": tr.task.input,
                    "severity": tr.task.severity,
                    "pass_rate": tr.pass_rate,
                    "pass_at_k": tr.pass_at_k,
                    "pass_pow_k": tr.pass_pow_k,
                    "trials": [
                        {
                            "trial_number": trial.trial_number,
                            "passed": trial.passed,
                            "latency_ms": trial.latency_ms,
                            "graders": [
                                {"dimension": g.dimension, "verdict": g.verdict.value, "reasoning": g.reasoning}
                                for g in trial.grader_results
                            ],
                        }
                        for trial in tr.trials
                    ],
                }
                for tr in suite_result.task_results
            ],
        }

        path = output_dir / filename
        with open(path, "w") as f:
            json.dump(results_data, f, indent=2)
        return path
