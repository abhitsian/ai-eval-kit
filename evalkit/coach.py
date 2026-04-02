"""Eval Coach — LLM-powered review of your eval YAML files.

Analyzes your test cases and suggests:
- Missing negative cases
- Missing edge cases
- Rubric gaps
- One-directional bias
- Severity mismatches
"""

import os
from pathlib import Path
from typing import Dict, List

import yaml


def review_eval_file(yaml_path: Path, product_context: str = "") -> str:
    """Review an eval YAML file and return suggestions."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    metadata = data.get("metadata", {})
    tasks = data.get("tasks", [])

    # Build the prompt
    task_summary = "\n".join(
        f"- id={t['id']} | input=\"{t['input']}\" | graders={[g.get('check', g.get('dimension', '?')) for g in t.get('graders', [])]} | notes={t.get('notes', '')}"
        for t in tasks
    )

    prompt = f"""You are an eval quality coach for a PM building an AI product.

Review this eval file and provide specific, actionable feedback.

## Product Context
{product_context or '(not provided)'}

## Eval File: {yaml_path.name}
Surface: {metadata.get('surface', '?')}
Feature: {metadata.get('feature', '?')}
Severity: {metadata.get('severity', '?')}
Number of tasks: {len(tasks)}

## Tasks
{task_summary}

## Your Review

Evaluate across these dimensions and provide specific feedback:

### 1. Coverage
- Are there enough test cases? (minimum 10-15 for a feature)
- Is there a mix of easy/medium/hard queries?
- Are different user personas represented? (new user, power user, manager, etc.)

### 2. Negative Cases
- What percentage are negative cases (things that should NOT work)?
- Target: 30% negative cases. Flag if below 20%.
- What specific negative cases are missing?

### 3. Edge Cases
- Are there typo/informal variants?
- Ambiguous queries that could go either way?
- Multi-intent queries?
- Queries in unexpected formats?

### 4. Grader Coverage
- Are critical dimensions covered? (accuracy, hallucination, completeness)
- Are there code-based graders for fast CI checks?
- Are LLM judges used for qualitative dimensions?

### 5. One-Directional Bias
- Do all tests push in the same direction? (e.g., all test that something SHOULD trigger, none test that it SHOULDN'T)
- Flag if the eval only measures one direction.

### 6. Severity Alignment
- Is the severity rating appropriate for this feature?
- Are critical tasks (compliance, safety) marked as such?

## Format
Give 3-5 specific, actionable suggestions. For each:
- What's missing or wrong
- A concrete example of what to add
- Why it matters

End with a quality score: A (production-ready), B (good start, needs gaps filled), C (needs significant work), D (missing fundamentals).
"""

    return _call_llm(prompt)


def quick_check(tasks: List[Dict]) -> Dict:
    """Fast local analysis without LLM — checks basic quality signals."""
    issues = []
    total = len(tasks)

    # Check count
    if total < 5:
        issues.append({"type": "low_count", "message": f"Only {total} tasks. Aim for 15-20 per feature.", "severity": "high"})
    elif total < 10:
        issues.append({"type": "low_count", "message": f"{total} tasks is a start. Aim for 15-20.", "severity": "medium"})

    # Check negative cases
    negative_signals = ["should not", "should_not", "negative", "shouldn't", "must not", "banned", "wrong"]
    negative_count = sum(
        1 for t in tasks
        if any(sig in str(t.get("notes", "")).lower() or sig in str(t.get("expected", "")).lower() for sig in negative_signals)
    )
    neg_pct = negative_count / total if total > 0 else 0
    if neg_pct < 0.15:
        issues.append({
            "type": "few_negatives",
            "message": f"Only {negative_count}/{total} ({neg_pct:.0%}) negative cases. Target: 30%. You're testing what should work but not what shouldn't.",
            "severity": "high",
        })

    # Check grader types
    has_code = any("code" in str(t.get("graders", [])) for t in tasks)
    has_llm = any("llm" in str(t.get("graders", [])) for t in tasks)
    if not has_code:
        issues.append({"type": "no_code_graders", "message": "No code-based graders. Add deterministic checks for fast CI feedback.", "severity": "medium"})
    if not has_llm:
        issues.append({"type": "no_llm_graders", "message": "No LLM judges. Add them for qualitative dimensions (accuracy, tone, completeness).", "severity": "low"})

    # Check for variety in inputs
    inputs = [t.get("input", "") for t in tasks]
    avg_len = sum(len(i) for i in inputs) / len(inputs) if inputs else 0
    all_similar_length = all(abs(len(i) - avg_len) < 10 for i in inputs)
    if all_similar_length and total > 3:
        issues.append({
            "type": "low_variety",
            "message": "All inputs are similar length. Add: short queries, typos, long/detailed queries, informal language.",
            "severity": "medium",
        })

    # Check for notes/documentation
    undocumented = sum(1 for t in tasks if not t.get("notes"))
    if undocumented > total * 0.7:
        issues.append({
            "type": "undocumented",
            "message": f"{undocumented}/{total} tasks have no notes. Add notes explaining why each case is interesting — it helps future reviewers.",
            "severity": "low",
        })

    # Overall score
    high_issues = sum(1 for i in issues if i["severity"] == "high")
    if high_issues == 0 and total >= 10:
        grade = "B"
    elif high_issues == 0:
        grade = "C"
    elif high_issues >= 2:
        grade = "D"
    else:
        grade = "C"

    return {"issues": issues, "grade": grade, "total_tasks": total, "negative_count": negative_count}


def _call_llm(prompt: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=2048, temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except (ImportError, Exception) as e:
        return f"LLM coach unavailable ({e}). Use 'evalkit coach --quick' for local analysis."
