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
    canonical_templates = load_canonical_templates()

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

    # Inject canonical templates based on task type
    injected_context = _inject_canonical_templates(type_name, canonical_templates)
    if injected_context:
        prompt = f"{injected_context}\n\n{prompt}"

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


def _inject_canonical_templates(task_type: str, canonical_templates: dict) -> str:
    """
    Inject relevant canonical templates based on task type.

    Returns concatenated context string, or empty string if no templates apply.
    """
    # Always inject system_base
    injected = []
    if "system_base" in canonical_templates:
        injected.append(canonical_templates["system_base"]["content"])

    # Task-type-specific injections
    if task_type in ["planner", "reporter"]:
        # Morning briefing and planning: signal_over_noise + one_thing_decision
        if "signal_over_noise" in canonical_templates:
            injected.append(canonical_templates["signal_over_noise"]["content"])
        if "one_thing_decision" in canonical_templates:
            injected.append(canonical_templates["one_thing_decision"]["content"])

    if task_type == "creator":
        # Content tasks: rfd_content_frame
        if "rfd_content_frame" in canonical_templates:
            injected.append(canonical_templates["rfd_content_frame"]["content"])

    if task_type == "planner":
        # Research/planning: tool_priority + research_synthesis
        if "tool_priority" in canonical_templates:
            injected.append(canonical_templates["tool_priority"]["content"])
        if "research_synthesis" in canonical_templates:
            injected.append(canonical_templates["research_synthesis"]["content"])

    if task_type in ["creator", "planner"]:
        # Action tasks: approval_gate
        if "approval_gate" in canonical_templates:
            injected.append(canonical_templates["approval_gate"]["content"])

    return "\n\n".join(injected)


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


def get_task_model_role(task_name: str) -> str | None:
    """
    Extract model_role from task type configuration.
    
    Args:
        task_name: Name of the task from config/tasks.yaml
    
    Returns:
        model_role string if defined, None otherwise
    """
    tasks = load_tasks()
    templates = load_templates()
    task_types = load_task_types()

    if task_name not in tasks:
        return None

    task_config = tasks[task_name]
    template_name = task_config.get("template")
    if not template_name or template_name not in templates:
        return None

    template = templates[template_name]
    type_name = template.get("type")
    if not type_name or type_name not in task_types:
        return None

    task_type = task_types[type_name]
    return task_type.get("model_role")
