"""Base prompt system — context injection for autonomous tasks."""
import logging
from pathlib import Path
import yaml

logger = logging.getLogger("privy.prompts")

PROMPTS_PATH = Path("templates/canonical/base_prompts.yaml")

TASK_PROMPT_MAP = {
    "default":           ["base_identity"],
    "briefing":          ["base_identity", "signal_over_noise", "one_thing"],
    "research":          ["base_identity", "tool_priority", "research_synthesis"],
    "content":           ["base_identity", "rfd_content_frame", "signal_over_noise"],
    "action":            ["base_identity", "approval_gate"],
    "planning":          ["base_identity", "one_thing", "signal_over_noise"],
    "monitoring":        ["base_identity", "signal_over_noise"],
    "skill_review":      ["base_identity", "signal_over_noise"],
}

_cache: dict | None = None


def _load_prompts() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(PROMPTS_PATH, encoding="utf-8") as f:
            _cache = yaml.safe_load(f)
        return _cache
    except Exception as e:
        logger.warning(f"[prompts] failed to load base_prompts.yaml: {e}")
        return {}


def get_prompts_for_task(task_type: str) -> str:
    """
    Return concatenated prompt blocks for a given task type.
    Falls back to 'default' if task_type not in map.
    Returns empty string if prompts file not found.
    """
    prompts = _load_prompts()
    if not prompts:
        return ""

    keys = TASK_PROMPT_MAP.get(task_type, TASK_PROMPT_MAP["default"])
    blocks = []
    for key in keys:
        block = prompts.get(key, "")
        if block:
            blocks.append(block.strip())

    return "\n\n".join(blocks) if blocks else ""


def get_all_prompt_keys() -> list[str]:
    """Return list of all available prompt block keys."""
    return list(_load_prompts().keys())
