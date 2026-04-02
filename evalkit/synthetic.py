"""Synthetic test case generator — works with any product config."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from evalkit.config import ProductConfig


def generate_synthetic(
    config: ProductConfig,
    surface: str,
    feature: str,
    count: int = 20,
) -> List[Dict]:
    """Generate synthetic test cases from seed examples using LLM."""
    # Load seed examples
    feature_path = config.evals_dir / surface / f"{feature}.yaml"
    if not feature_path.exists():
        raise FileNotFoundError(f"No eval file: {feature_path}")

    with open(feature_path) as f:
        data = yaml.safe_load(f)
    seeds = data.get("tasks", [])
    seed_examples = "\n".join(f"- {t['input']}" for t in seeds[:10])

    surface_desc = config.surfaces.get(surface, {}).get("description", surface)

    prompt = f"""You are generating test queries for an AI product evaluation.

Product: {config.product_name}
Description: {config.product_description}
Surface being tested: {surface} — {surface_desc}
Feature: {feature}

Here are {min(len(seeds), 10)} seed examples:
{seed_examples}

Generate {count} NEW, diverse variations. Include:
- Different phrasings (formal, casual, typos, abbreviations)
- Different user contexts and personas
- Edge cases and ambiguous queries
- Queries that SHOULD succeed and queries that SHOULD fail (negative cases)
- Different levels of specificity

Return a JSON array of objects:
[{{"input": "...", "notes": "why interesting", "is_negative_case": false}}]

Return ONLY the JSON array."""

    llm_config = config.llm_config
    raw_output = _call_llm(prompt, llm_config.get("model", "claude-sonnet-4-6"))
    return _parse_json_array(raw_output)


def save_generated(config: ProductConfig, surface: str, feature: str, tasks: List[Dict]) -> Path:
    """Save generated tasks as a new YAML eval file."""
    output_path = config.evals_dir / surface / f"{feature}_synthetic.yaml"

    data = {
        "metadata": {
            "surface": surface,
            "feature": f"{feature}_synthetic",
            "severity": "medium",
            "generated": True,
        },
        "tasks": [
            {
                "id": f"syn-{surface[:3]}-{i:03d}",
                "input": t["input"],
                "notes": t.get("notes", ""),
                "expected": {"routes_to": surface},
                "graders": [{"type": "llm", "dimension": "factual_accuracy"}],
                "tags": ["synthetic", "negative" if t.get("is_negative_case") else "positive"],
            }
            for i, t in enumerate(tasks)
        ],
    }

    with open(output_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return output_path


def _call_llm(prompt: str, model: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=model, max_tokens=4096, temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except ImportError:
        raise ImportError("pip install anthropic")


def _parse_json_array(text: str) -> List[Dict]:
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array in output: {text[:100]}")
    return json.loads(text[start:end])
