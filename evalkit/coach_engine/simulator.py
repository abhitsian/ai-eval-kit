"""Simulation generator — creates adaptive eval challenges using Claude.

Generates five types of simulations:
1. spot_failure: Here's an AI response — what's wrong?
2. write_cases: Here's a feature — write test cases
3. rubric_craft: Here's a dimension — define pass/fail
4. calibrate: Grade this response — compare with judge
5. coverage_audit: Here's an eval file — what's missing?

Adapts to user's skill level, weak areas, and product context.
"""

import json
import os
from typing import Any, Dict, List, Optional

from evalkit.coach_engine.profile import UserProfile, SKILL_LABELS


# Product scenario templates for variety
PRODUCT_TYPES = {
    "chatbot": {
        "name": "Customer Support Chatbot",
        "features": ["password reset", "order tracking", "refund processing", "FAQ answers", "complaint handling", "live agent handoff"],
        "failure_risks": ["hallucination about policies", "premature escalation", "missing empathy", "wrong order lookup", "promising refunds it can't give"],
    },
    "search": {
        "name": "Enterprise AI Search",
        "features": ["document retrieval", "answer synthesis", "citation", "permission filtering", "query rewriting", "multi-source aggregation"],
        "failure_risks": ["hallucinated sources", "permission leak", "stale results", "wrong document", "over-confident answers"],
    },
    "agent": {
        "name": "Autonomous Work Agent",
        "features": ["meeting scheduling", "email drafting", "expense submission", "data lookup", "report generation", "workflow automation"],
        "failure_risks": ["unauthorized actions", "wrong parameters", "hallucinated completion", "stuck loops", "missing confirmation"],
    },
    "copilot": {
        "name": "Code Copilot",
        "features": ["code generation", "bug detection", "refactoring suggestions", "documentation", "test writing", "code review"],
        "failure_risks": ["insecure code", "wrong language/framework", "over-engineering", "breaking existing tests", "hallucinated APIs"],
    },
    "hr_assistant": {
        "name": "HR/Employee Assistant",
        "features": ["policy Q&A", "benefits enrollment", "PTO requests", "org chart", "onboarding guidance", "performance review info"],
        "failure_risks": ["hallucinated policies", "wrong compliance info", "privacy violations", "tone mismatch on sensitive topics", "stale org data"],
    },
}


def generate_simulation(
    skill: str,
    profile: UserProfile,
    product_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a single simulation challenge adapted to the user's level."""

    # Pick product type
    if not product_type:
        prefs = profile._data.get("preferred_product_types", [])
        if prefs:
            import random
            product_type = random.choice(prefs)
        else:
            import random
            product_type = random.choice(list(PRODUCT_TYPES.keys()))

    product = PRODUCT_TYPES.get(product_type, PRODUCT_TYPES["chatbot"])

    # Determine difficulty based on skill level
    level = profile.skill_level(skill)
    if level >= 70:
        difficulty = "hard"
    elif level >= 40:
        difficulty = "medium"
    else:
        difficulty = "easy"

    # Get user context for personalization
    user_context = ""
    if profile.product_context:
        user_context = f"\nThe user is building: {profile.product_context}"
    if profile.role:
        user_context += f"\nTheir role: {profile.role}"

    # Build the generation prompt based on skill type
    prompt = _build_generation_prompt(skill, difficulty, product, user_context, profile)

    # Call Claude to generate the simulation
    raw = _call_claude(prompt)
    simulation = _parse_simulation(raw, skill)
    simulation["skill"] = skill
    simulation["difficulty"] = difficulty
    simulation["product_type"] = product_type
    simulation["product_name"] = product["name"]

    return simulation


def _build_generation_prompt(skill: str, difficulty: str, product: Dict, user_context: str, profile: UserProfile) -> str:
    """Build the prompt for generating a simulation."""

    weak_areas = profile.weak_areas
    weak_context = f"\nThe user struggles with: {', '.join(weak_areas)}. Make challenges that exercise these areas." if weak_areas else ""

    import random
    feature = random.choice(product["features"])
    risk = random.choice(product["failure_risks"])

    if skill == "failure_spotting":
        return f"""Generate an eval training exercise for a PM.

Product: {product['name']}
Feature: {feature}
Difficulty: {difficulty}
{user_context}{weak_context}

Create a scenario where an AI assistant responds to a user query. The response should contain a {'subtle and nuanced' if difficulty == 'hard' else 'clear' if difficulty == 'easy' else 'moderate'} failure.

{'For hard difficulty, make the failure subtle — the response should look mostly correct with a hidden issue. About 20% of the time, make it actually correct (no failure) to test if the user can recognize good responses too.' if difficulty == 'hard' else ''}
{'For easy difficulty, make the failure obvious and use a common failure pattern.' if difficulty == 'easy' else ''}

Respond in this exact JSON format:
{{
  "scenario_description": "One sentence setting the scene",
  "user_query": "What the user asked the AI",
  "source_context": "The source/ground truth the AI should have used (or empty if none)",
  "ai_response": "What the AI actually responded",
  "correct_answer": "hallucination|wrong_routing|incomplete|over_triggered|tone_mismatch|refused_incorrectly|stale_data|no_failure",
  "explanation": "Why this is the correct answer — be specific about what's wrong (or right)",
  "teaching_point": "The generalizable lesson from this case",
  "xp_value": {{"easy": 10, "medium": 20, "hard": 35}}["{difficulty}"]
}}

Return ONLY the JSON object."""

    elif skill == "negative_case_design":
        return f"""Generate an eval training exercise for a PM learning to write negative test cases.

Product: {product['name']}
Feature: {feature}
Difficulty: {difficulty}
{user_context}{weak_context}

Present a feature and some existing POSITIVE test cases. Ask the user to write NEGATIVE cases (things that should NOT work, should be rejected, or should trigger guardrails).

Respond in this exact JSON format:
{{
  "scenario_description": "Description of the feature being tested",
  "existing_positive_cases": [
    "Positive test case 1",
    "Positive test case 2",
    "Positive test case 3"
  ],
  "prompt_to_user": "What negative test cases should we add? Think about: security, edge cases, out-of-scope requests, adversarial inputs, and boundary conditions.",
  "ideal_negative_cases": [
    {{"input": "The negative test case", "why_important": "Why this matters"}},
    {{"input": "Another negative case", "why_important": "Why this matters"}},
    {{"input": "Another negative case", "why_important": "Why this matters"}},
    {{"input": "Another negative case", "why_important": "Why this matters"}}
  ],
  "common_misses": ["What most PMs forget to test"],
  "xp_value": {{"easy": 10, "medium": 20, "hard": 35}}["{difficulty}"]
}}

Return ONLY the JSON object."""

    elif skill == "rubric_definition":
        return f"""Generate an eval training exercise for a PM learning to write scoring rubrics.

Product: {product['name']}
Difficulty: {difficulty}
Relevant risk: {risk}
{user_context}{weak_context}

Present a quality dimension that needs a rubric. Ask the user to define PASS, FAIL, and edge cases.

Respond in this exact JSON format:
{{
  "dimension_name": "Name of the quality dimension to define",
  "scenario_description": "Context for why this dimension matters for this product",
  "prompt_to_user": "Define what PASS and FAIL mean for this dimension. Be specific enough that two reviewers would agree independently.",
  "reference_rubric": {{
    "pass": "Specific, observable criteria for PASS",
    "fail": "Specific, observable criteria for FAIL",
    "edge_cases": ["Tricky case 1 and how to handle it", "Tricky case 2"]
  }},
  "common_rubric_mistakes": ["Mistake PMs make when defining this rubric"],
  "xp_value": {{"easy": 10, "medium": 20, "hard": 35}}["{difficulty}"]
}}

Return ONLY the JSON object."""

    elif skill == "calibration":
        return f"""Generate a calibration exercise for a PM practicing eval judgment.

Product: {product['name']}
Feature: {feature}
Difficulty: {difficulty}
{user_context}{weak_context}

Create an AI response that the user must judge. {'Make it genuinely borderline — reasonable people could disagree.' if difficulty == 'hard' else 'Make the verdict clear.' if difficulty == 'easy' else 'Make it require careful reading.'}

Respond in this exact JSON format:
{{
  "scenario_description": "Context",
  "user_query": "What the user asked",
  "source_context": "Ground truth source (if applicable)",
  "ai_response": "The AI's response to judge",
  "dimension": "factual_accuracy|completeness|tone|hallucination|actionability",
  "correct_verdict": "pass|fail",
  "judge_reasoning": "Detailed reasoning for the verdict",
  "why_tricky": "Why this case tests calibration skill",
  "xp_value": {{"easy": 10, "medium": 20, "hard": 35}}["{difficulty}"]
}}

Return ONLY the JSON object."""

    elif skill == "edge_case_thinking":
        return f"""Generate an exercise for a PM learning to think about edge cases.

Product: {product['name']}
Feature: {feature}
Difficulty: {difficulty}
{user_context}{weak_context}

Present a feature and ask the user to brainstorm edge cases that could break it.

Respond in this exact JSON format:
{{
  "scenario_description": "The feature being stress-tested",
  "feature_details": "How the feature works normally",
  "prompt_to_user": "What edge cases could break this? Think about: unusual inputs, timing issues, state conflicts, scale, permissions, and multi-step interactions.",
  "ideal_edge_cases": [
    {{"case": "Description of edge case", "why_breaks": "Why this is problematic", "category": "input|timing|state|scale|permission|multi-step"}},
    {{"case": "Another edge case", "why_breaks": "Why", "category": "category"}},
    {{"case": "Another", "why_breaks": "Why", "category": "category"}},
    {{"case": "Another", "why_breaks": "Why", "category": "category"}},
    {{"case": "Another", "why_breaks": "Why", "category": "category"}}
  ],
  "xp_value": {{"easy": 10, "medium": 20, "hard": 35}}["{difficulty}"]
}}

Return ONLY the JSON object."""

    elif skill == "eval_coverage":
        return f"""Generate an exercise for a PM learning to assess eval coverage.

Product: {product['name']}
Difficulty: {difficulty}
{user_context}{weak_context}

Present an existing set of eval test cases with deliberate gaps. Ask the user to identify what's missing.

Respond in this exact JSON format:
{{
  "scenario_description": "You're reviewing an eval suite for {feature}",
  "existing_tests": [
    {{"id": "t-001", "input": "test query 1", "checks": "what it tests"}},
    {{"id": "t-002", "input": "test query 2", "checks": "what it tests"}},
    {{"id": "t-003", "input": "test query 3", "checks": "what it tests"}},
    {{"id": "t-004", "input": "test query 4", "checks": "what it tests"}},
    {{"id": "t-005", "input": "test query 5", "checks": "what it tests"}}
  ],
  "prompt_to_user": "This eval suite has gaps. What's missing? Think about: negative cases, edge cases, different user personas, different failure modes, and coverage balance.",
  "gaps": [
    {{"gap": "What's missing", "why_matters": "Risk if not tested", "example_test": "A specific test to add"}},
    {{"gap": "Another gap", "why_matters": "Why", "example_test": "Test to add"}},
    {{"gap": "Another gap", "why_matters": "Why", "example_test": "Test to add"}}
  ],
  "coverage_score": "What percentage of real-world scenarios are covered by these 5 tests?",
  "xp_value": {{"easy": 10, "medium": 20, "hard": 35}}["{difficulty}"]
}}

Return ONLY the JSON object."""

    return "{}"


def _call_claude(prompt: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            temperature=0.9,  # High temp for variety
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        raise RuntimeError(f"Claude API error: {e}. Set ANTHROPIC_API_KEY in your environment.")


def _parse_simulation(raw: str, skill: str) -> Dict[str, Any]:
    """Parse the JSON simulation from Claude's response."""
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON found in simulation response: {raw[:200]}")
    return json.loads(raw[start:end])
