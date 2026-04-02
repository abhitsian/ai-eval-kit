"""Product configuration loader — reads product.yaml and drives everything."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ProductConfig:
    """Loads and provides access to product.yaml configuration."""

    def __init__(self, config_path: Optional[str] = None):
        self.path = Path(config_path) if config_path else self._find_config()
        if not self.path.exists():
            raise FileNotFoundError(
                f"No product.yaml found at {self.path}.\n"
                "Run 'evalkit init' to create one, or copy an example from examples/."
            )
        with open(self.path) as f:
            self._data = yaml.safe_load(f)

    @staticmethod
    def _find_config() -> Path:
        """Walk up from cwd to find product.yaml."""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            candidate = parent / "product.yaml"
            if candidate.exists():
                return candidate
        return Path.cwd() / "product.yaml"

    @property
    def product_name(self) -> str:
        return self._data.get("product", {}).get("name", "My AI Product")

    @property
    def product_description(self) -> str:
        return self._data.get("product", {}).get("description", "")

    @property
    def surfaces(self) -> Dict[str, Dict[str, Any]]:
        return self._data.get("surfaces", {})

    def surface_names(self) -> List[str]:
        return list(self.surfaces.keys())

    def surface_threshold(self, surface: str) -> float:
        return self.surfaces.get(surface, {}).get("threshold", 0.85)

    def surface_owner(self, surface: str) -> str:
        return self.surfaces.get(surface, {}).get("owner", "unassigned")

    def surface_dimensions(self, surface: str) -> List[str]:
        return self.surfaces.get(surface, {}).get("dimensions", [])

    @property
    def failure_modes(self) -> List[Dict[str, str]]:
        return self._data.get("failure_modes", [])

    def failure_mode_labels(self) -> List[str]:
        return [fm["label"] for fm in self.failure_modes]

    def failure_mode_ids(self) -> List[str]:
        return [fm["id"] for fm in self.failure_modes]

    @property
    def llm_config(self) -> Dict[str, Any]:
        return self._data.get("llm", {"provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.0})

    @property
    def runner_config(self) -> Dict[str, Any]:
        return self._data.get("runner", {"trials": 3, "timeout_seconds": 30, "parallel_workers": 4})

    @property
    def team(self) -> List[Dict[str, Any]]:
        return self._data.get("team", [])

    @property
    def project_dir(self) -> Path:
        return self.path.parent

    @property
    def evals_dir(self) -> Path:
        return self.project_dir / "evals"

    @property
    def judges_dir(self) -> Path:
        return self.project_dir / "judges"

    @property
    def data_dir(self) -> Path:
        return self.project_dir / "data"

    def raw(self) -> Dict[str, Any]:
        return self._data
