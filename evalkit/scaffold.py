"""Scaffold generator — creates eval directories, starter test cases, and judge configs from product.yaml."""

from pathlib import Path
from typing import Dict, List

import yaml

from evalkit.config import ProductConfig


STARTER_PRODUCT_YAML = """\
# {product_name} — Eval Configuration
# Edit this file to define your AI product's eval surfaces.

product:
  name: "{product_name}"
  description: "{product_description}"
  version: "1.0"

# Each surface is a distinct AI capability to evaluate.
# Add your own surfaces below.
surfaces:
  answer_quality:
    description: "Accuracy and helpfulness of AI responses"
    threshold: 0.90
    owner: "your_name"
    dimensions:
      - factual_accuracy
      - completeness
      - no_hallucination

  tone:
    description: "Appropriate communication style"
    threshold: 0.85
    owner: "your_name"
    dimensions:
      - tone_appropriateness

# Failure modes — what can go wrong?
failure_modes:
  - id: hallucination
    label: "Hallucination"
    severity: critical
    description: "AI fabricates information not in any source"
  - id: incomplete
    label: "Incomplete"
    severity: medium
    description: "Correct direction but missing key info"
  - id: tone_mismatch
    label: "Tone Mismatch"
    severity: medium
    description: "Inappropriate tone for the situation"
  - id: wrong_action
    label: "Wrong Action"
    severity: high
    description: "AI takes incorrect action or gives wrong advice"

llm:
  provider: anthropic
  model: claude-sonnet-4-6
  temperature: 0.0

runner:
  trials: 3
  timeout_seconds: 30
  parallel_workers: 4
"""


STARTER_EVAL_YAML = """\
# {surface} — Starter Eval Tasks
# Add your test cases below. Each task needs:
#   - id: unique identifier
#   - input: what the user says/asks
#   - expected: what you expect (used by graders)
#   - graders: list of checks to run

metadata:
  surface: {surface}
  feature: starter
  severity: medium

tasks:
  - id: {prefix}-001
    input: "Replace this with a real user query"
    expected:
      routes_to: {surface}
    graders:
      - type: code
        check: routes_to
    notes: "Starter task — replace with real examples"

  - id: {prefix}-002
    input: "Replace with a query that should NOT succeed"
    expected:
      behavior: should_fail_gracefully
    graders:
      - type: llm
        dimension: no_hallucination
    notes: "Negative case — always include these"
"""


def init_product(name: str, description: str, output_dir: Path):
    """Create a new product.yaml and scaffold directories."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write product.yaml
    product_yaml = output_dir / "product.yaml"
    if not product_yaml.exists():
        content = STARTER_PRODUCT_YAML.format(
            product_name=name,
            product_description=description,
        )
        with open(product_yaml, "w") as f:
            f.write(content)

    # Scaffold from config
    scaffold_from_config(ProductConfig(str(product_yaml)))
    return product_yaml


def scaffold_from_config(config: ProductConfig):
    """Create eval directories, starter tasks, and data dirs from product config."""
    project_dir = config.project_dir

    # Create directory structure
    dirs = [
        config.evals_dir,
        config.judges_dir,
        config.data_dir / "traces",
        config.data_dir / "labels",
        config.data_dir / "golden",
        config.data_dir / "results",
        project_dir / "docs",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        gitkeep = d / ".gitkeep"
        if not any(d.iterdir()):
            gitkeep.touch()

    # Create eval directories and starter tasks for each surface
    for surface_name in config.surface_names():
        surface_dir = config.evals_dir / surface_name
        surface_dir.mkdir(exist_ok=True)

        starter_file = surface_dir / "starter.yaml"
        if not starter_file.exists():
            prefix = surface_name[:3]
            content = STARTER_EVAL_YAML.format(
                surface=surface_name,
                prefix=prefix,
            )
            with open(starter_file, "w") as f:
                f.write(content)

    # Create .env.example
    env_example = project_dir / ".env.example"
    if not env_example.exists():
        with open(env_example, "w") as f:
            f.write("ANTHROPIC_API_KEY=sk-ant-xxxxx\nOPENAI_API_KEY=sk-xxxxx\n")
