"""CLI for ai-eval-kit — evalkit init, run, generate, stats, viewer, dashboard."""

import sys
from pathlib import Path

import click

from evalkit.config import ProductConfig
from evalkit.reporter import print_suite_report, ci_summary


def _load_config(config_path=None):
    try:
        return ProductConfig(config_path)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        click.echo("\nQuick start:")
        click.echo("  evalkit init --name 'My AI Product'")
        sys.exit(1)


@click.group()
def main():
    """ai-eval-kit — Evaluation toolkit for AI products."""
    pass


# ============================================================
# evalkit init
# ============================================================

@main.command()
@click.option("--name", "-n", prompt="Product name", help="Your AI product name")
@click.option("--description", "-d", default="", help="One-line product description")
@click.option("--template", "-t", type=click.Choice(["chatbot", "search_engine", "ai_agent", "blank"]),
              default="blank", help="Start from a template")
@click.option("--dir", "output_dir", default=".", help="Output directory")
def init(name, description, template, output_dir):
    """Initialize a new eval project. Creates product.yaml and scaffolds directories."""
    output = Path(output_dir)

    if template != "blank":
        # Copy template
        template_dir = Path(__file__).parent.parent / "examples" / template
        template_file = template_dir / "product.yaml"
        if template_file.exists():
            import shutil
            dest = output / "product.yaml"
            if not dest.exists():
                shutil.copy(template_file, dest)
                click.echo(f"Copied {template} template to product.yaml")
            else:
                click.echo("product.yaml already exists — skipping template copy")

    from evalkit.scaffold import init_product, scaffold_from_config
    product_yaml = output / "product.yaml"

    if not product_yaml.exists():
        init_product(name, description, output)
        click.echo(f"Created product.yaml for '{name}'")
    else:
        click.echo("product.yaml already exists — scaffolding directories")

    config = ProductConfig(str(product_yaml))
    scaffold_from_config(config)

    click.echo(f"\nScaffolded eval project for: {config.product_name}")
    click.echo(f"  Surfaces: {', '.join(config.surface_names())}")
    click.echo(f"  Evals dir: {config.evals_dir}")
    click.echo(f"  Judges dir: {config.judges_dir}")
    click.echo(f"  Data dir: {config.data_dir}")
    click.echo("\nNext steps:")
    click.echo("  1. Edit product.yaml to define your surfaces and failure modes")
    click.echo("  2. Add test cases to evals/<surface>/")
    click.echo("  3. Run: evalkit run <surface>")
    click.echo("  4. Launch viewer: evalkit viewer")


# ============================================================
# evalkit surfaces
# ============================================================

@main.command()
@click.option("--config", "config_path", default=None, help="Path to product.yaml")
def surfaces(config_path):
    """List all eval surfaces defined in product.yaml."""
    config = _load_config(config_path)
    click.echo(f"\n{config.product_name} — Eval Surfaces\n")
    for name, surface in config.surfaces.items():
        threshold = surface.get("threshold", 0.85)
        owner = surface.get("owner", "unassigned")
        desc = surface.get("description", "")
        dims = ", ".join(surface.get("dimensions", []))
        click.echo(f"  {name}")
        click.echo(f"    threshold: {threshold:.0%} | owner: {owner}")
        click.echo(f"    {desc}")
        if dims:
            click.echo(f"    dimensions: {dims}")
        click.echo()


# ============================================================
# evalkit run
# ============================================================

@main.command()
@click.argument("surface")
@click.option("--feature", "-f", default=None)
@click.option("--trials", "-t", default=None, type=int, help="Override trial count")
@click.option("--save/--no-save", default=True)
@click.option("--ci", is_flag=True, help="Exit code 1 if below threshold")
@click.option("--config", "config_path", default=None)
def run(surface, feature, trials, save, ci, config_path):
    """Run evals for a surface."""
    config = _load_config(config_path)
    if trials:
        config._data.setdefault("runner", {})["trials"] = trials

    from evalkit.runner import EvalRunner
    runner = EvalRunner(config=config)
    result = runner.run_suite(surface, feature)
    print_suite_report(result, config.product_name)

    if save:
        path = runner.save_results(result)
        click.echo(f"\nResults saved to: {path}")

    if ci and not result.meets_threshold:
        summary = ci_summary(result)
        click.echo(f"\nCI FAIL: {summary['surface']} at {summary['pass_rate']:.1%} "
                    f"(threshold: {summary['threshold']:.0%})")
        sys.exit(1)


# ============================================================
# evalkit run-all
# ============================================================

@main.command("run-all")
@click.option("--trials", "-t", default=None, type=int)
@click.option("--ci", is_flag=True)
@click.option("--config", "config_path", default=None)
def run_all(trials, ci, config_path):
    """Run evals for ALL surfaces."""
    config = _load_config(config_path)
    if trials:
        config._data.setdefault("runner", {})["trials"] = trials

    from evalkit.runner import EvalRunner
    from evalkit.loader import list_surfaces as ls
    runner = EvalRunner(config=config)

    all_pass = True
    for surface in ls(config.evals_dir):
        click.echo(f"\n{'='*60}")
        click.echo(f"Running: {surface}")
        click.echo(f"{'='*60}")
        result = runner.run_suite(surface)
        print_suite_report(result, config.product_name)
        runner.save_results(result)
        if not result.meets_threshold:
            all_pass = False

    if ci and not all_pass:
        click.echo("\nCI FAIL: One or more surfaces below threshold")
        sys.exit(1)


# ============================================================
# evalkit stats
# ============================================================

@main.command()
@click.option("--config", "config_path", default=None)
def stats(config_path):
    """Show eval suite statistics."""
    config = _load_config(config_path)
    from evalkit.loader import load_all_suites
    suites = load_all_suites(config.evals_dir)

    click.echo(f"\n{config.product_name} — Eval Stats\n")
    total = 0
    for surface, tasks in suites.items():
        count = len(tasks)
        total += count
        features = set(t.feature for t in tasks)
        threshold = config.surface_threshold(surface)
        click.echo(f"  {surface}: {count} tasks, {len(features)} features, threshold={threshold:.0%}")
    click.echo(f"\n  Total: {total} tasks across {len(suites)} surfaces")


# ============================================================
# evalkit generate
# ============================================================

@main.command()
@click.argument("surface")
@click.argument("feature")
@click.option("--count", "-n", default=20, help="Number of test cases")
@click.option("--config", "config_path", default=None)
def generate(surface, feature, count, config_path):
    """Generate synthetic test cases from seed examples."""
    config = _load_config(config_path)
    from evalkit.synthetic import generate_synthetic, save_generated

    click.echo(f"Generating {count} synthetic cases for {surface}/{feature}...")
    tasks = generate_synthetic(config, surface, feature, count)
    click.echo(f"Generated {len(tasks)} test cases.")

    for t in tasks[:5]:
        click.echo(f"  - {t['input']}")
    if len(tasks) > 5:
        click.echo(f"  ... and {len(tasks) - 5} more")

    path = save_generated(config, surface, feature, tasks)
    click.echo(f"\nSaved to: {path}")


# ============================================================
# evalkit viewer / dashboard
# ============================================================

@main.command()
@click.option("--port", default=8501, type=int)
def viewer(port):
    """Launch the trace viewer + labeling interface."""
    import subprocess
    app_path = Path(__file__).parent.parent / "app" / "trace_viewer.py"
    click.echo(f"Launching trace viewer on port {port}...")
    subprocess.run(["python3", "-m", "streamlit", "run", str(app_path), "--server.port", str(port)])


@main.command()
@click.option("--port", default=8502, type=int)
def dashboard(port):
    """Launch the eval dashboard."""
    import subprocess
    app_path = Path(__file__).parent.parent / "app" / "dashboard.py"
    click.echo(f"Launching dashboard on port {port}...")
    subprocess.run(["python3", "-m", "streamlit", "run", str(app_path), "--server.port", str(port)])


# ============================================================
# evalkit practice
# ============================================================

@main.command()
@click.option("--port", default=8503, type=int)
def practice(port):
    """Launch the eval practice mode — interactive training for PMs."""
    import subprocess
    app_path = Path(__file__).parent.parent / "app" / "practice.py"
    click.echo(f"Launching practice mode on port {port}...")
    click.echo("Four skill tracks: Spot the Failure, Write the Eval, Define the Rubric, Calibration")
    subprocess.run(["python3", "-m", "streamlit", "run", str(app_path), "--server.port", str(port)])


# ============================================================
# evalkit coach
# ============================================================

@main.command()
@click.argument("surface")
@click.argument("feature")
@click.option("--quick", is_flag=True, help="Quick local analysis (no LLM needed)")
@click.option("--config", "config_path", default=None)
def coach(surface, feature, quick, config_path):
    """Review your eval file and get improvement suggestions.

    Example: evalkit coach answer_quality starter
    """
    config = _load_config(config_path)
    yaml_path = config.evals_dir / surface / f"{feature}.yaml"

    if not yaml_path.exists():
        click.echo(f"File not found: {yaml_path}", err=True)
        sys.exit(1)

    import yaml as _yaml
    with open(yaml_path) as f:
        data = _yaml.safe_load(f)
    tasks = data.get("tasks", [])

    from evalkit.coach import quick_check, review_eval_file

    # Always run quick check first
    click.echo(f"\nReviewing: {yaml_path}\n")
    result = quick_check(tasks)

    click.echo(f"Tasks: {result['total_tasks']} | Negative cases: {result['negative_count']} | Grade: {result['grade']}")
    click.echo()

    if result["issues"]:
        for issue in result["issues"]:
            icon = {"high": "!!!", "medium": " ! ", "low": "   "}.get(issue["severity"], "   ")
            click.echo(f"  [{icon}] {issue['message']}")
        click.echo()

    if not quick:
        click.echo("Running LLM coach review...\n")
        product_context = f"{config.product_name}: {config.product_description}"
        review = review_eval_file(yaml_path, product_context)
        click.echo(review)
    else:
        click.echo("(Use without --quick for detailed LLM-powered review)")


# ============================================================
# evalkit learn — the adaptive coaching experience
# ============================================================

@main.command()
@click.option("--port", default=8504, type=int)
def learn(port):
    """Launch the adaptive eval coach — personalized training powered by Claude."""
    import subprocess
    app_path = Path(__file__).parent.parent / "app" / "coach.py"
    click.echo(f"Launching Eval Coach on port {port}...")
    click.echo("Your progress is saved to ~/.evalkit/coach/")
    subprocess.run(["python3", "-m", "streamlit", "run", str(app_path), "--server.port", str(port)])


@main.command()
@click.option("--user", "-u", default="default", help="User profile ID")
def profile(user):
    """Show your coaching profile and skill levels."""
    from evalkit.coach_engine.profile import UserProfile, SKILL_LABELS
    p = UserProfile(user)
    summary = p.summary()

    click.echo(f"\n{summary['display_name']} — {summary['overall_level'].title()}")
    click.echo(f"XP: {summary['overall_xp']} | Sessions: {summary['total_sessions']} | "
               f"Streak: {summary['streak_days']}d | Questions: {summary['total_questions']}")
    click.echo()

    click.echo("Skills:")
    for sk, data in summary["skills"].items():
        bar = "#" * (data["level"] // 5) + "." * (20 - data["level"] // 5)
        click.echo(f"  {SKILL_LABELS[sk]:25s} [{bar}] {data['level']:3d}%  ({data['accuracy']}, {data['attempts']} attempts)")

    if summary["weak_areas"]:
        click.echo(f"\nFocus areas: {', '.join(SKILL_LABELS[sk] for sk in summary['weak_areas'])}")
    if summary["badges"]:
        click.echo(f"Badges: {', '.join(summary['badges'])}")


if __name__ == "__main__":
    main()
