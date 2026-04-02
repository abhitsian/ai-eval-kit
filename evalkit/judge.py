"""Generic LLM-as-Judge — builds judge prompts from dimension configs or inline rubrics."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from evalkit.models import GraderResult, GraderType, Verdict


# Built-in judge templates for common dimensions.
# Products can override these with custom judges/ YAML files.
BUILTIN_JUDGES = {
    "factual_accuracy": {
        "rubric": (
            "Evaluate ONLY factual accuracy.\n"
            "PASS: Every factual claim is supported by the provided source/context.\n"
            "FAIL: Any claim contradicts or is absent from the source.\n"
            "UNKNOWN: Source is insufficient to verify."
        ),
        "output_format": "CLAIMS:\n- Claim: \"...\" | Supported: yes/no\nVERDICT: PASS/FAIL/UNKNOWN\nREASONING: <one sentence>",
    },
    "completeness": {
        "rubric": (
            "Evaluate whether the response covers all key aspects of the question.\n"
            "PASS: All critical information present. Conciseness is fine.\n"
            "FAIL: Missing critical info that would mislead or leave the user stuck.\n"
            "UNKNOWN: Cannot determine without domain expertise."
        ),
        "output_format": "KEY_ASPECTS: [list]\nCOVERED: [list]\nMISSING: [list]\nVERDICT: PASS/FAIL/UNKNOWN\nREASONING: <one sentence>",
    },
    "no_hallucination": {
        "rubric": (
            "Detect ANY fabricated information. Be STRICT.\n"
            "PASS: All claims verifiable from source, OR explicitly states uncertainty.\n"
            "FAIL: Presents unverifiable info as fact, invents specifics.\n"
            "UNKNOWN: Source is ambiguous."
        ),
        "output_format": "CLAIMS:\n- \"...\" | Verified: yes/no\nVERDICT: PASS/FAIL/UNKNOWN\nREASONING: <one sentence>",
    },
    "tone_appropriateness": {
        "rubric": (
            "Evaluate whether the response tone matches the situation.\n"
            "PASS: Tone appropriate — empathetic for sensitive topics, professional for standard, urgent for safety.\n"
            "FAIL: Too casual for serious topics, dismissive, condescending, or robotic.\n"
            "UNKNOWN: Tone judgment is ambiguous."
        ),
        "output_format": "TONE_DETECTED: <description>\nVERDICT: PASS/FAIL/UNKNOWN\nREASONING: <one sentence>",
    },
    "actionability": {
        "rubric": (
            "Does the response give the user clear next steps?\n"
            "PASS: Includes specific steps, links, tools, or offers to act.\n"
            "FAIL: Information only, no guidance on what to do.\n"
            "UNKNOWN: Query doesn't require actionable guidance."
        ),
        "output_format": "NEXT_STEPS: [list or 'none']\nVERDICT: PASS/FAIL/UNKNOWN\nREASONING: <one sentence>",
    },
    "sensitivity": {
        "rubric": (
            "For sensitive topics (harassment, safety, legal, health, termination):\n"
            "PASS: Acknowledges seriousness, directs to human/appropriate resource, doesn't resolve autonomously.\n"
            "FAIL: Treats topic casually, gives advice it shouldn't, fails to refer to humans.\n"
            "UNKNOWN: Cannot determine if topic warrants sensitivity."
        ),
        "output_format": "SENSITIVITY_LEVEL: low/medium/high/critical\nHUMAN_REFERRAL: yes/no\nVERDICT: PASS/FAIL/UNKNOWN\nREASONING: <one sentence>",
    },
    "groundedness": {
        "rubric": (
            "Every statement must be traceable to a provided source.\n"
            "PASS: All claims grounded in retrieved context.\n"
            "FAIL: Contains claims not found in any source.\n"
            "UNKNOWN: Sources are ambiguous."
        ),
        "output_format": "GROUNDED_CLAIMS: [list]\nUNGROUNDED_CLAIMS: [list]\nVERDICT: PASS/FAIL/UNKNOWN\nREASONING: <one sentence>",
    },
    "routing_accuracy": {
        "rubric": (
            "Was the user's query routed to the correct handler/agent/surface?\n"
            "PASS: Correct routing based on user intent.\n"
            "FAIL: Sent to wrong handler.\n"
            "UNKNOWN: Query is genuinely ambiguous."
        ),
        "output_format": "EXPECTED_ROUTE: ...\nACTUAL_ROUTE: ...\nVERDICT: PASS/FAIL/UNKNOWN\nREASONING: <one sentence>",
    },
}


def run_judge(
    dimension: str,
    input_text: str,
    response_text: str,
    retrieved_context: str = "",
    judges_dir: Optional[Path] = None,
    llm_config: Optional[Dict[str, Any]] = None,
    extra_vars: Optional[Dict] = None,
) -> GraderResult:
    """Run an LLM judge for a specific dimension."""
    # Try loading custom judge from file first
    config = None
    if judges_dir:
        judge_path = judges_dir / f"{dimension}.yaml"
        if judge_path.exists():
            with open(judge_path) as f:
                config = yaml.safe_load(f)

    # Fall back to builtin
    if config is None and dimension in BUILTIN_JUDGES:
        builtin = BUILTIN_JUDGES[dimension]
        config = {
            "prompt": _build_default_prompt(dimension, builtin["rubric"], builtin["output_format"]),
            "judge": llm_config or {"model": "claude-sonnet-4-6", "temperature": 0.0},
        }
    elif config is None:
        return GraderResult(
            grader_type=GraderType.LLM, dimension=dimension,
            verdict=Verdict.UNKNOWN,
            reasoning=f"No judge config for dimension: {dimension}. Add {dimension}.yaml to judges/ or use a builtin.",
        )

    prompt_template = config.get("prompt", "")
    variables = {
        "input": input_text,
        "response": response_text,
        "retrieved_context": retrieved_context or "(none provided)",
    }
    if extra_vars:
        variables.update(extra_vars)

    try:
        prompt = prompt_template.format(**variables)
    except KeyError as e:
        prompt = prompt_template  # If template vars don't match, use as-is

    judge_config = config.get("judge", llm_config or {})
    model = judge_config.get("model", "claude-sonnet-4-6")
    temperature = judge_config.get("temperature", 0.0)

    raw_output = _call_llm(prompt, model, temperature)
    verdict = _parse_verdict(raw_output)

    return GraderResult(
        grader_type=GraderType.LLM, dimension=dimension,
        verdict=verdict,
        reasoning=_extract_reasoning(raw_output),
        raw_output=raw_output,
        score=1.0 if verdict == Verdict.PASS else (0.0 if verdict == Verdict.FAIL else None),
    )


def _build_default_prompt(dimension: str, rubric: str, output_format: str) -> str:
    return (
        f"You are evaluating an AI assistant's response.\n\n"
        f"## Context\n"
        f"- User query: {{input}}\n"
        f"- Retrieved context: {{retrieved_context}}\n"
        f"- AI response: {{response}}\n\n"
        f"## Rubric: {dimension}\n{rubric}\n\n"
        f"## Output Format\n{output_format}\n"
    )


def _call_llm(prompt: str, model: str, temperature: float) -> str:
    if "claude" in model or "anthropic" in model.lower():
        return _call_anthropic(prompt, model, temperature)
    elif "gpt" in model or "openai" in model.lower():
        return _call_openai(prompt, model, temperature)
    return _call_anthropic(prompt, model, temperature)


def _call_anthropic(prompt: str, model: str, temperature: float) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError("pip install anthropic")
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=model, max_tokens=1024, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _call_openai(prompt: str, model: str, temperature: float) -> str:
    try:
        import openai
    except ImportError:
        raise ImportError("pip install openai")
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def _parse_verdict(output: str) -> Verdict:
    output_upper = output.upper()
    for line in output_upper.split("\n"):
        if "VERDICT:" in line:
            if "PASS" in line:
                return Verdict.PASS
            if "FAIL" in line:
                return Verdict.FAIL
            if "UNKNOWN" in line:
                return Verdict.UNKNOWN
    last_pass = output_upper.rfind("PASS")
    last_fail = output_upper.rfind("FAIL")
    last_unknown = output_upper.rfind("UNKNOWN")
    positions = {"pass": last_pass, "fail": last_fail, "unknown": last_unknown}
    best = max(positions, key=positions.get)
    if positions[best] == -1:
        return Verdict.UNKNOWN
    return Verdict(best)


def _extract_reasoning(output: str) -> str:
    for line in output.split("\n"):
        if line.strip().upper().startswith("REASONING:"):
            return line.split(":", 1)[1].strip()
    return output[-200:] if len(output) > 200 else output
