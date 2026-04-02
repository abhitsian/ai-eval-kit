# Getting Started with ai-eval-kit

## Step 1: Install

```bash
git clone https://github.com/abhitsian/ai-eval-kit.git
cd ai-eval-kit
pip install -e .
```

## Step 2: Initialize Your Project

```bash
mkdir my-product-evals && cd my-product-evals

# Interactive setup
evalkit init --name "My AI Product"

# Or use a template
evalkit init --template chatbot --name "Support Bot"
```

This creates:
- `product.yaml` — your product definition
- `evals/` — directories for each surface with starter test cases
- `data/` — directories for traces, labels, and results
- `judges/` — where you can add custom LLM judge configs

## Step 3: Edit product.yaml

Define your AI surfaces. Each surface is a distinct capability:

```yaml
surfaces:
  my_surface:
    description: "What this AI capability does"
    threshold: 0.90          # Launch readiness bar
    owner: "who_owns_this"   # PM responsible for eval quality
    dimensions:              # What qualitative dimensions to judge
      - factual_accuracy
      - completeness
```

## Step 4: Write Test Cases

Add YAML files to `evals/<surface>/`:

```yaml
metadata:
  surface: my_surface
  feature: core_queries

tasks:
  - id: core-001
    input: "A real user query"
    expected:
      contains_keywords: [expected, words]
    graders:
      - type: code
        check: contains_keywords
      - type: llm
        dimension: factual_accuracy
```

**Tips:**
- Start with 20-50 test cases from real user queries
- Include 30% negative cases (things that should NOT work)
- Add edge cases: typos, ambiguous queries, adversarial inputs

## Step 5: Run Evals

```bash
# Run one surface
evalkit run my_surface

# Run all surfaces
evalkit run-all

# CI mode (exit 1 if below threshold)
evalkit run-all --ci
```

## Step 6: Connect Your AI

By default, evals run against a mock target. To connect your real AI:

```python
from evalkit.config import ProductConfig
from evalkit.runner import EvalRunner

def my_ai(input_text, context):
    result = your_api.call(input_text)
    return {"text": result.text, "intent": result.intent, "citations": result.sources}

runner = EvalRunner(ProductConfig(), target_fn=my_ai)
result = runner.run_suite("my_surface")
```

## Step 7: Start Labeling

```bash
evalkit viewer
```

Open the trace viewer, review AI interactions, label pass/fail, tag failure modes.

## Step 8: Track Progress

```bash
evalkit dashboard
```

See pass rates, trends, failure mode distribution, and launch readiness.

## Weekly Workflow

1. **Monday**: Review traces in the viewer. Label 50+.
2. **Wednesday**: Run eval suite. Check dashboard for regressions.
3. **Friday**: Review failure mode distribution. Pick top 3 to fix next week.
