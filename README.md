# ai-eval-kit

Evaluation toolkit for PMs building AI products. Define your product's AI surfaces in a YAML file, and get a complete eval system: test runner, LLM judges, trace viewer, human labeling, and a launch-readiness dashboard.

Built on eval frameworks from [Hamel Husain](https://hamel.dev/blog/posts/evals/) and [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).

## 30-Second Start

```bash
pip install -e .

# Initialize a new eval project (interactive)
evalkit init --name "My AI Product"

# Or start from a template
evalkit init --template chatbot
evalkit init --template search_engine
evalkit init --template ai_agent

# See your surfaces
evalkit surfaces

# Run evals
evalkit run answer_quality
evalkit run-all --ci

# View stats
evalkit stats

# Launch trace viewer (for labeling)
evalkit viewer

# Launch dashboard
evalkit dashboard

# Generate synthetic test cases
evalkit generate answer_quality starter --count 20
```

## How It Works

### 1. Define Your Product (`product.yaml`)

```yaml
product:
  name: "My AI Product"
  description: "What it does"

surfaces:
  answer_quality:
    description: "Accuracy of AI responses"
    threshold: 0.90
    owner: "pm_name"
    dimensions: [factual_accuracy, completeness, no_hallucination]

  tone:
    description: "Communication style"
    threshold: 0.85
    owner: "pm_name"
    dimensions: [tone_appropriateness]

failure_modes:
  - id: hallucination
    label: "Hallucination"
    severity: critical
  - id: incomplete
    label: "Incomplete"
    severity: medium
```

A **surface** is any distinct AI capability. A chatbot might have: answer quality, intent detection, tone, escalation. A search product might have: retrieval, answer generation, citation accuracy.

### 2. Write Test Cases (`evals/<surface>/*.yaml`)

```yaml
metadata:
  surface: answer_quality
  feature: product_questions

tasks:
  - id: aq-001
    input: "How do I reset my password?"
    expected:
      routes_to: knowledge
      contains_keywords: [reset, password, settings]
    graders:
      - type: code
        check: contains_keywords
      - type: llm
        dimension: factual_accuracy

  - id: aq-002
    input: "What's the weather on Mars?"
    expected:
      behavior: should_decline
    graders:
      - type: llm
        dimension: no_hallucination
    notes: "Negative case — should not fabricate an answer"
```

### 3. Connect Your AI

```python
from evalkit.config import ProductConfig
from evalkit.runner import EvalRunner

def my_ai(input_text: str, context: dict) -> dict:
    # Call your AI here
    response = your_api.chat(input_text)
    return {
        "text": response.text,
        "intent": response.intent,
        "citations": response.sources,
        "data": response.data,
    }

config = ProductConfig()
runner = EvalRunner(config, target_fn=my_ai)
result = runner.run_suite("answer_quality")
```

### 4. Run and Iterate

```bash
evalkit run answer_quality          # Run evals, see results
evalkit viewer                      # Review traces, label pass/fail
evalkit dashboard                   # Track progress toward launch
```

## What's Included

| Component | What It Does |
|-----------|-------------|
| **`evalkit init`** | Scaffolds everything from a product.yaml |
| **`evalkit run`** | Runs test cases, applies graders, reports results |
| **`evalkit viewer`** | Streamlit app to browse traces and label pass/fail |
| **`evalkit dashboard`** | Launch-readiness dashboard with pass rates and trends |
| **`evalkit generate`** | LLM-powered synthetic test case expansion |
| **16 built-in graders** | Route checking, keyword matching, PII detection, tool verification, etc. |
| **8 built-in LLM judges** | Factual accuracy, hallucination, tone, completeness, etc. |
| **3 product templates** | Chatbot, search engine, AI agent — ready to customize |

## Built-in Graders (Code-Based)

These run instantly, no LLM calls needed:

| Grader | What It Checks |
|--------|----------------|
| `exact_match` | Field matches expected value exactly |
| `contains_keywords` | Response contains all specified keywords |
| `excludes_keywords` | Response does NOT contain banned keywords |
| `routes_to` | Intent/routing is correct |
| `has_citations` / `no_citations` | Source citations present or absent |
| `response_is_list` / `response_is_single` | Data shape check |
| `has_actions` | Actionable buttons/options present |
| `field_equals` | Specific field matches expected value |
| `response_length_between` | Response length within range |
| `regex_match` | Response matches regex pattern |
| `no_pii_leaked` | No SSN, credit card patterns |
| `latency_under` | Response time within threshold |
| `tool_called` / `tool_not_called` | Correct tools used/avoided |

### Adding Custom Graders

```python
from evalkit.graders import register_grader
from evalkit.models import GraderResult, GraderType, Verdict

def my_custom_check(response, expected):
    passed = response.get("confidence", 0) > 0.8
    return GraderResult(
        grader_type=GraderType.CODE,
        dimension="confidence_check",
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        reasoning=f"Confidence: {response.get('confidence', 0)}",
    )

register_grader("confidence_check", my_custom_check)
```

## Built-in LLM Judges

These use Claude/GPT to evaluate qualitative dimensions:

| Judge | What It Evaluates |
|-------|-------------------|
| `factual_accuracy` | Every claim supported by source |
| `completeness` | Key aspects covered |
| `no_hallucination` | No fabricated information |
| `tone_appropriateness` | Tone matches situation |
| `actionability` | Clear next steps provided |
| `sensitivity` | Sensitive topics handled with care |
| `groundedness` | All statements traceable to source |
| `routing_accuracy` | Correct handler selected |

Override any judge by placing a `<dimension>.yaml` file in your `judges/` directory.

## Key Concepts

| Concept | Meaning |
|---------|---------|
| **Surface** | A distinct AI capability (answer quality, intent detection, etc.) |
| **Task** | One test case with input, expected output, and graders |
| **Trial** | A single attempt at a task (run multiple for stochastic outputs) |
| **Grader** | Scoring logic — code-based or LLM-based |
| **pass@k** | At least 1 of k trials passes — measures **capability** |
| **pass^k** | All k trials pass — measures **reliability** |
| **Threshold** | Pass rate needed for launch readiness |

## Templates

### Chatbot (`--template chatbot`)
Surfaces: answer quality, intent detection, tone, escalation, tool use

### Search Engine (`--template search_engine`)
Surfaces: retrieval, answer generation, citation, query understanding, access control

### AI Agent (`--template ai_agent`)
Surfaces: task completion, planning, tool use, guardrails, communication, recovery

## Philosophy

1. **Look at your data.** The trace viewer exists so your team sees what the AI actually does.
2. **Domain experts define quality.** PMs write rubrics. Engineers build infrastructure.
3. **Start simple.** Binary pass/fail. 20 test cases. A spreadsheet works for week one.
4. **Grade outcomes, not paths.** The AI may take unexpected routes to correct answers.
5. **Balance your eval sets.** Always include negative cases.
6. **Evals inform every decision.** New model? Run evals. New prompt? Run evals.

## Project Structure

```
your-project/
├── product.yaml          # Your product definition (surfaces, thresholds, failure modes)
├── evals/                # Test cases per surface
│   ├── answer_quality/
│   │   └── starter.yaml
│   └── tone/
│       └── starter.yaml
├── judges/               # Custom LLM judge overrides (optional)
├── data/
│   ├── traces/           # Logged AI interactions (JSONL)
│   ├── labels/           # Human labels (CSV)
│   ├── golden/           # Promoted golden test cases
│   └── results/          # Eval run results (JSON)
└── docs/                 # Your team's documentation
```
