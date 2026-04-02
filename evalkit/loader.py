"""Load eval tasks from YAML files — works with any product config."""

from pathlib import Path
from typing import Dict, List, Optional

import yaml

from evalkit.models import Task


def load_suite(evals_dir: Path, surface: str, feature: Optional[str] = None) -> List[Task]:
    """Load all tasks for a surface, optionally filtered by feature."""
    surface_dir = evals_dir / surface
    if not surface_dir.exists():
        raise FileNotFoundError(
            f"No eval suite for surface: {surface}\n"
            f"Expected directory: {surface_dir}\n"
            "Run 'evalkit init' to scaffold eval directories."
        )

    tasks = []
    for yaml_file in sorted(surface_dir.glob("*.yaml")):
        if feature and yaml_file.stem != feature:
            continue
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        if not data:
            continue

        metadata = data.get("metadata", {})
        for task_data in data.get("tasks", []):
            tasks.append(Task(
                id=task_data["id"],
                input=task_data["input"],
                surface=metadata.get("surface", surface),
                feature=metadata.get("feature", yaml_file.stem),
                expected=task_data.get("expected", {}),
                graders=task_data.get("graders", []),
                context=task_data.get("context", {}),
                notes=task_data.get("notes", ""),
                severity=metadata.get("severity", "medium"),
                tags=task_data.get("tags", []),
            ))
    return tasks


def load_all_suites(evals_dir: Path) -> Dict[str, List[Task]]:
    """Load all tasks grouped by surface."""
    suites = {}
    if not evals_dir.exists():
        return suites
    for surface_dir in sorted(evals_dir.iterdir()):
        if surface_dir.is_dir():
            tasks = load_suite(evals_dir, surface_dir.name)
            if tasks:
                suites[surface_dir.name] = tasks
    return suites


def list_surfaces(evals_dir: Path) -> List[str]:
    """List all available eval surfaces."""
    if not evals_dir.exists():
        return []
    return [d.name for d in sorted(evals_dir.iterdir()) if d.is_dir()]
