"""Task runner — loads YAML configs, builds resolved tasks for autonomous execution."""

import sys
from pathlib import Path
from typing import Any

import yaml

# Add project root to path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

_task_types: dict = {}
_templates: dict = {}
_tasks: dict = {}


def load_task_types() -> dict:
    """Load task types from config/task_types.yaml."""
    global _task_types
    if _task_types:
        return _task_types

    path = _root / "config" / "task_types.yaml"
    with open(path, "r") as f:
        _task_types = yaml.safe_load(f)
    return _task_types


def load_templates() -> dict:
    """Load task templates from config/task_templates.yaml."""
    global _templates
    if _templates:
        return _templates

    path = _root / "config" / "task_templates.yaml"
    with open(path, "r") as f:
        _templates = yaml.safe_load(f)
    return _templates


def load_tasks() -> dict:
    """Load task instances from config/tasks.yaml."""
    global _tasks
    if _tasks:
        return _tasks

    path = _root / "config" / "tasks.yaml"
    with open(path, "r") as f:
        _tasks = yaml.safe_load(f)
    return _tasks


def resolve_task(task_name: str) -> dict:
    """
    Returns fully resolved task with prompt, persona, max_iterations, etc.

    Raises ValueError if template or type not found.
    """
    tasks = load_tasks()
    templates = load_templates()
    task_types = load_task_types()

    if task_name not in tasks:
        raise ValueError(f"Task not found: {task_name}")

    task_config = tasks[task_name]
    template_name = task_config.get("template")
    if not template_name:
        raise ValueError(f"Task {task_name} has no template")

    if template_name not in templates:
        raise ValueError(f"Template not found: {template_name}")

    template = templates[template_name]
    type_name = template.get("type")
    if not type_name:
        raise ValueError(f"Template {template_name} has no type")

    if type_name not in task_types:
        raise ValueError(f"TaskType not found: {type_name}")

    task_type = task_types[type_name]

    # Resolve prompt with params
    params = task_config.get("params", {})
    prompt = template["prompt"]
    try:
        prompt = prompt.format(**params)
    except KeyError as e:
        raise ValueError(f"Missing param for template {template_name}: {e}")

    return {
        "name": task_name,
        "schedule": task_config["schedule"],
        "enabled": task_config.get("enabled", True),
        "params": params,
        "prompt": prompt,
        "persona": task_type.get("persona", ""),
        "max_iterations": task_type.get("max_iterations", 10),
        "emit_signals": task_type.get("emit_signals", False),
        "fallback_on_empty": task_type.get("fallback_on_empty", False),
        "urgent_on": task_type.get("urgent_on", []),
        "save_to_memory": task_type.get("save_to_memory", False),
    }


def get_all_resolved_tasks() -> list[dict]:
    """Returns all enabled tasks, fully resolved."""
    tasks = load_tasks()
    resolved = []
    for task_name in tasks:
        try:
            task = resolve_task(task_name)
            if task.get("enabled"):
                resolved.append(task)
        except ValueError as e:
            # Skip tasks with missing templates/types
            print(f"Warning: Skipping {task_name}: {e}")
    return resolved
