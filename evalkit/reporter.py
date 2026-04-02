"""Results reporter — rich console output and CI summaries."""

from typing import Dict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from evalkit.models import SuiteResult, Verdict

console = Console()


def print_suite_report(result: SuiteResult, product_name: str = ""):
    """Print a rich console report."""
    status = "[green]PASS[/green]" if result.meets_threshold else "[red]FAIL[/red]"
    title = product_name + " — " if product_name else ""
    header = f"{title}{result.surface}/{result.feature} — {status}"
    header += f"  (pass rate: {result.pass_rate:.1%}, threshold: {result.threshold:.0%})"
    console.print(Panel(header, title="Eval Results"))

    # Metrics
    metrics = Table(title="Metrics")
    metrics.add_column("Metric", style="bold")
    metrics.add_column("Value")
    metrics.add_row("Pass Rate", f"{result.pass_rate:.1%}")
    metrics.add_row("pass@k (capability)", f"{result.pass_at_k_rate:.1%}")
    metrics.add_row("pass^k (reliability)", f"{result.pass_pow_k_rate:.1%}")
    metrics.add_row("Threshold", f"{result.threshold:.0%}")
    metrics.add_row("Tasks", str(len(result.task_results)))
    console.print(metrics)

    # Per-task
    tasks = Table(title="Tasks")
    tasks.add_column("ID")
    tasks.add_column("Input", max_width=50)
    tasks.add_column("Pass Rate")
    tasks.add_column("Status")
    tasks.add_column("Details")

    for tr in result.task_results:
        rate = tr.pass_rate
        st = "[green]PASS[/green]" if rate >= result.threshold else "[red]FAIL[/red]"
        failures = []
        for trial in tr.trials:
            for g in trial.grader_results:
                if g.verdict == Verdict.FAIL:
                    failures.append(f"{g.dimension}: {g.reasoning}")
        details = "; ".join(set(failures))[:80] if failures else ""
        tasks.add_row(tr.task.id, tr.task.input[:50], f"{rate:.0%}", st, details)
    console.print(tasks)

    # Failure modes
    failure_counts = {}
    for tr in result.task_results:
        for trial in tr.trials:
            for g in trial.grader_results:
                if g.verdict == Verdict.FAIL:
                    failure_counts[g.dimension] = failure_counts.get(g.dimension, 0) + 1
    if failure_counts:
        fm = Table(title="Failure Distribution")
        fm.add_column("Dimension")
        fm.add_column("Count", justify="right")
        for dim, count in sorted(failure_counts.items(), key=lambda x: -x[1]):
            fm.add_row(dim, str(count))
        console.print(fm)


def ci_summary(result: SuiteResult) -> Dict:
    return {
        "surface": result.surface,
        "feature": result.feature,
        "pass_rate": result.pass_rate,
        "threshold": result.threshold,
        "meets_threshold": result.meets_threshold,
        "total_tasks": len(result.task_results),
        "passed": sum(1 for t in result.task_results if t.pass_rate >= result.threshold),
        "failed": sum(1 for t in result.task_results if t.pass_rate < result.threshold),
    }
