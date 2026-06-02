"""
Template loader — reads YAML from templates/ directories.
Validates required fields. Returns structured template dict.
"""
import os
import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CANONICAL_DIR = Path(__file__).parent.parent.parent / "templates" / "canonical"
EXPERIMENTAL_DIR = Path(__file__).parent.parent.parent / "templates" / "experimental"

REQUIRED_FIELDS = {"name", "steps"}
VALID_STEP_TYPES = {
    "tool_call", "llm_call", "condition_check",
    "transform", "spawn_chain", "approval_wait"
}


class TemplateError(Exception):
    """Raised when a template is invalid or not found."""
    pass


def load_template(name: str) -> dict:
    """
    Load a template by name. Searches canonical first, then experimental.
    Raises TemplateError if not found or invalid.
    """
    for directory in (CANONICAL_DIR, EXPERIMENTAL_DIR):
        path = directory / f"{name}.yaml"
        if path.exists():
            return _load_and_validate(path)
    raise TemplateError(f"Template not found: {name}")


def list_templates(source: str = "all") -> list[dict]:
    """
    List available templates.
    source: 'canonical' | 'experimental' | 'all'
    Returns list of dicts with name, source, version.
    """
    results = []
    dirs = []
    if source in ("canonical", "all"):
        dirs.append((CANONICAL_DIR, "canonical"))
    if source in ("experimental", "all"):
        dirs.append((EXPERIMENTAL_DIR, "experimental"))

    for directory, label in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            try:
                t = _load_and_validate(path)
                results.append({
                    "name": t["name"],
                    "source": label,
                    "version": t.get("version", "unknown"),
                    "description": t.get("description", "")
                })
            except TemplateError as e:
                logger.warning(f"Skipping invalid template {path}: {e}")

    return results


def _load_and_validate(path: Path) -> dict:
    """Load YAML and validate required fields."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise TemplateError(f"Failed to load {path}: {e}") from e

    if not isinstance(data, dict):
        raise TemplateError(f"Template must be a dict: {path}")

    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise TemplateError(f"Template {path} missing fields: {missing}")

    if not isinstance(data["steps"], list) or len(data["steps"]) == 0:
        raise TemplateError(f"Template {path} must have at least one step")

    for i, step in enumerate(data["steps"]):
        step_type = step.get("type")
        if step_type not in VALID_STEP_TYPES:
            raise TemplateError(
                f"Template {path} step {i} has invalid type: {step_type}"
            )

    return data
