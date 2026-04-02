"""Judgment evaluator — uses Claude to evaluate the PM's answers and give structured feedback.

For each answer type:
- failure_spotting: Did they identify the correct failure?
- negative_case_design: Are their negative cases good?
- rubric_definition: Is their rubric specific and complete?
- calibration: Does their verdict match the judge?
- edge_case_thinking: How creative/comprehensive are their edge cases?
- eval_coverage: Did they find the real gaps?
"""

import json
import os
from typing import Any, Dict


def evaluate_answer(
    skill: str,
    simulation: Dict[str, Any],
    user_answer: str,
) -> Dict[str, Any]:
    """Evaluate the PM's answer against the simulation's ideal answer.

    Returns:
        {
            "correct": bool,
            "score": float (0-1),
            "xp_earned": int,
            "feedback": str (detailed, personalized feedback),
            "improvement_tip": str (one actionable suggestion),
            "skill_signal": str (what this reveals about their skill level),
        }
    """
    prompt = _build_evaluation_prompt(skill, simulation, user_answer)
    raw = _call_claude(prompt)
    result = _parse_evaluation(raw)

    # Calculate XP
    base_xp = simulation.get("xp_value", 15)
    result["xp_earned"] = int(base_xp * result.get("score", 0))

    return result


def _build_evaluation_prompt(skill: str, simulation: Dict, user_answer: str) -> str:
    sim_json = json.dumps(simulation, indent=2)

    if skill == "failure_spotting":
        return f"""You are evaluating a PM's ability to spot failures in AI responses.

## The Simulation
{sim_json}

## The PM's Answer
{user_answer}

## Correct Answer
{simulation.get('correct_answer', 'unknown')}

## Your Evaluation
Compare the PM's answer to the correct answer. Consider:
- Did they identify the correct primary failure mode?
- Did they explain WHY it's a failure (not just label it)?
- If they identified a secondary issue that's also valid, give partial credit.

Respond in JSON:
{{
  "correct": true/false,
  "score": 0.0 to 1.0 (1.0 = perfect, 0.5 = partial credit, 0.0 = wrong),
  "feedback": "Specific feedback on their answer — what they got right, what they missed, and why it matters. 2-3 sentences.",
  "improvement_tip": "One specific, actionable thing to do differently next time.",
  "skill_signal": "What this answer reveals about their eval skill — e.g., 'good at catching hallucinations but misses tone issues'"
}}"""

    elif skill == "negative_case_design":
        return f"""You are evaluating a PM's ability to write negative test cases.

## The Simulation
{sim_json}

## The PM's Negative Cases
{user_answer}

## Ideal Negative Cases
{json.dumps(simulation.get('ideal_negative_cases', []), indent=2)}

## Your Evaluation
Compare the PM's cases to the ideal. Consider:
- Did they think about security/adversarial inputs?
- Did they cover out-of-scope requests?
- Did they find boundary conditions?
- Were their cases specific and testable (not vague)?
- Did they cover what the ideal cases cover?

Respond in JSON:
{{
  "correct": true/false (true if they covered at least 50% of key areas),
  "score": 0.0 to 1.0,
  "feedback": "What they covered well, what categories they missed, with specific examples. 2-3 sentences.",
  "improvement_tip": "The most important category of negative case they should always think about.",
  "skill_signal": "Pattern in their thinking — do they lean security? functionality? user behavior?"
}}"""

    elif skill == "rubric_definition":
        return f"""You are evaluating a PM's ability to write scoring rubrics.

## The Simulation
{sim_json}

## The PM's Rubric
{user_answer}

## Reference Rubric
{json.dumps(simulation.get('reference_rubric', {}), indent=2)}

## Your Evaluation
A good rubric has:
1. Specific, observable criteria (not vague)
2. Clear boundary between PASS and FAIL
3. Two independent reviewers would agree
4. Edge cases addressed

Respond in JSON:
{{
  "correct": true/false (true if the rubric is usable),
  "score": 0.0 to 1.0,
  "feedback": "How specific and usable is their rubric? What's strong, what's vague, what's missing? 2-3 sentences.",
  "improvement_tip": "The #1 way to make their rubric more concrete.",
  "skill_signal": "Are they thinking like an evaluator or still thinking like a PM who describes features?"
}}"""

    elif skill == "calibration":
        return f"""You are evaluating a PM's judgment calibration.

## The Simulation
{sim_json}

## The PM's Verdict and Reasoning
{user_answer}

## Correct Verdict
{simulation.get('correct_verdict', 'unknown')}
Reasoning: {simulation.get('judge_reasoning', '')}

## Your Evaluation
Respond in JSON:
{{
  "correct": true/false,
  "score": 1.0 if correct else 0.0,
  "feedback": "Why their verdict was right or wrong. If wrong, explain the reasoning gap. 2-3 sentences.",
  "improvement_tip": "What to look for next time to catch this.",
  "skill_signal": "Are they too strict, too lenient, or well-calibrated?"
}}"""

    elif skill == "edge_case_thinking":
        return f"""You are evaluating a PM's edge case thinking.

## The Simulation
{sim_json}

## The PM's Edge Cases
{user_answer}

## Ideal Edge Cases
{json.dumps(simulation.get('ideal_edge_cases', []), indent=2)}

## Your Evaluation
Good edge case thinking covers multiple categories: input edge cases, timing/state issues, scale, permissions, multi-step interactions.

Respond in JSON:
{{
  "correct": true/false (true if they found at least 3 meaningful edge cases),
  "score": 0.0 to 1.0,
  "feedback": "What categories they covered, what they missed, quality of their thinking. 2-3 sentences.",
  "improvement_tip": "The category of edge case they should always check but missed here.",
  "skill_signal": "Do they think systematically or randomly? Do they favor certain categories?"
}}"""

    elif skill == "eval_coverage":
        return f"""You are evaluating a PM's ability to assess eval coverage.

## The Simulation
{sim_json}

## The PM's Gap Analysis
{user_answer}

## Actual Gaps
{json.dumps(simulation.get('gaps', []), indent=2)}

## Your Evaluation
Respond in JSON:
{{
  "correct": true/false (true if they found at least 2 of the real gaps),
  "score": 0.0 to 1.0,
  "feedback": "Which gaps they found, which they missed, and whether they identified the most critical ones. 2-3 sentences.",
  "improvement_tip": "A systematic checklist for reviewing eval coverage.",
  "skill_signal": "Do they think about coverage holistically or focus on one type of gap?"
}}"""

    return '{"correct": false, "score": 0, "feedback": "Unknown skill type", "improvement_tip": "", "skill_signal": ""}'


def _call_claude(prompt: str) -> str:
    """Call Claude via CLI (uses existing Claude Code auth) or fall back to API."""
    import subprocess
    import shutil

    # Try Claude Code CLI first
    claude_path = shutil.which("claude")
    if not claude_path:
        for path in ["/Users/vaibhav/.local/bin/claude", "/usr/local/bin/claude", "/opt/homebrew/bin/claude"]:
            if os.path.isfile(path):
                claude_path = path
                break

    if claude_path:
        try:
            result = subprocess.run(
                [claude_path, "-p", prompt, "--output-format", "text"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    # Fall back to API
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=1024, temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            raise RuntimeError(f"Both CLI and API failed: {e}")

    raise RuntimeError("No Claude backend. Install Claude Code CLI or set ANTHROPIC_API_KEY.")


def _parse_evaluation(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return {"correct": False, "score": 0.0, "feedback": raw, "improvement_tip": "", "skill_signal": ""}
    try:
        return json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {"correct": False, "score": 0.0, "feedback": raw, "improvement_tip": "", "skill_signal": ""}
