"""
Director access tools — full operational access for Claude.
Claude reads and writes everything except templates/canonical/.
All writes to templates go to templates/experimental/ only.
"""
import json
import logging
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent
EXPERIMENTAL_DIR = REPO_ROOT / "templates" / "experimental"
CANONICAL_DIR = REPO_ROOT / "templates" / "canonical"


# ─────────────────────────────────────────────
# CHAIN TOOLS
# ─────────────────────────────────────────────

def get_chains(status: str = None, limit: int = 20) -> dict:
    """
    List chains, optionally filtered by status.
    status: running | waiting_approval | paused | complete | failed | None (all)
    limit: max rows returned (default 20, max 100)

    RETURNS: dict with ok, count, chains (list of chain dicts)
    """
    from infra.db.chains import list_chains
    try:
        limit = min(max(1, limit), 100)
        chains = list_chains(status=status)[:limit]
        return {"ok": True, "count": len(chains), "chains": chains}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_chain(chain_id: str) -> dict:
    """
    Full chain detail including all steps and payload summaries.
    RETURNS: dict with ok, chain, steps, payload_count
    """
    from infra.db.chains import get_chain as _get_chain, get_steps_for_chain
    from infra.db.payloads import list_payloads_for_chain
    try:
        chain = _get_chain(chain_id)
        if not chain:
            return {"ok": False, "error": f"Chain not found: {chain_id}"}
        steps = get_steps_for_chain(chain_id)
        payloads = list_payloads_for_chain(chain_id)
        return {
            "ok": True,
            "chain": chain,
            "steps": steps,
            "payload_count": len(payloads),
            "payload_types": list({p["type"] for p in payloads})
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_chain_payload(payload_id: str) -> dict:
    """
    Full payload contents by ID.
    RETURNS: dict with ok, payload (including deserialized data)
    """
    from infra.db.payloads import get_payload
    try:
        payload = get_payload(payload_id)
        if not payload:
            return {"ok": False, "error": f"Payload not found: {payload_id}"}
        return {"ok": True, "payload": payload}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def start_chain(template_name: str,
                initial_payload: dict = None) -> dict:
    """
    Instantiate and start a chain from a template.
    Loads template from canonical or experimental directory.
    Creates chain record and runs it.

    RETURNS: dict with ok, chain_id, template_name, status
    """
    from infra.chain.template_loader import load_template, TemplateError
    from infra.db.chains import create_chain
    from infra.chain.runner import ChainRunner
    from tools.registry import TOOL_REGISTRY

    try:
        template = load_template(template_name)
    except TemplateError as e:
        return {"ok": False, "error": str(e)}

    try:
        chain = create_chain(
            template_name=template_name,
            payload_ref=None
        )
        chain_id = chain["id"]

        runner = ChainRunner(tool_registry=TOOL_REGISTRY)
        # Run in background — don't block the MCP call
        import threading
        def run():
            try:
                runner.run(chain_id, template["steps"])
            except Exception as e:
                logger.error(f"Chain {chain_id} failed: {e}")
        threading.Thread(target=run, daemon=True).start()

        return {
            "ok": True,
            "chain_id": chain_id,
            "template_name": template_name,
            "status": "started",
            "message": f"Chain {chain_id[:8]} starting in background"
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cancel_chain(chain_id: str) -> dict:
    """
    Halt a running or waiting chain by setting status to failed.
    RETURNS: dict with ok, chain_id, previous_status
    """
    from infra.db.chains import get_chain as _get_chain, update_chain_status
    try:
        chain = _get_chain(chain_id)
        if not chain:
            return {"ok": False, "error": f"Chain not found: {chain_id}"}
        prev = chain["status"]
        if prev in ("complete", "failed"):
            return {
                "ok": False,
                "error": f"Chain already terminal: {prev}"
            }
        update_chain_status(chain_id, "failed")
        return {"ok": True, "chain_id": chain_id, "previous_status": prev}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def resume_chain(chain_id: str) -> dict:
    """
    Resume a chain that is waiting_approval or paused.
    Advances current_step by 1 and restarts execution.
    RETURNS: dict with ok, chain_id, resumed_from_step
    """
    from infra.db.chains import get_chain as _get_chain, update_chain_status
    from infra.chain.template_loader import load_template, TemplateError
    from infra.chain.runner import ChainRunner
    from tools.registry import TOOL_REGISTRY

    try:
        chain = _get_chain(chain_id)
        if not chain:
            return {"ok": False, "error": f"Chain not found: {chain_id}"}
        if chain["status"] not in ("waiting_approval", "paused"):
            return {
                "ok": False,
                "error": f"Chain not resumable — status: {chain['status']}"
            }
        try:
            template = load_template(chain["template_name"])
        except TemplateError as e:
            return {"ok": False, "error": f"Template load failed: {e}"}

        next_step = chain["current_step"] + 1
        update_chain_status(chain_id, "running", current_step=next_step)

        runner = ChainRunner(tool_registry=TOOL_REGISTRY)
        import threading
        def run():
            try:
                runner.run(chain_id, template["steps"])
            except Exception as e:
                logger.error(f"Chain resume {chain_id} failed: {e}")
        threading.Thread(target=run, daemon=True).start()

        return {
            "ok": True,
            "chain_id": chain_id,
            "resumed_from_step": next_step
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────
# TEMPLATE TOOLS
# ─────────────────────────────────────────────

def list_templates(source: str = "all") -> dict:
    """
    List available templates.
    source: 'canonical' | 'experimental' | 'all'
    RETURNS: dict with ok, count, templates (list with name, source, version)
    """
    from infra.chain.template_loader import list_templates as _list
    try:
        templates = _list(source=source)
        return {"ok": True, "count": len(templates), "templates": templates}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_template(name: str) -> dict:
    """
    Get full template content by name.
    RETURNS: dict with ok, name, source, content (full YAML as dict)
    """
    from infra.chain.template_loader import load_template, TemplateError
    try:
        template = load_template(name)
        # Determine source
        canonical_path = CANONICAL_DIR / f"{name}.yaml"
        source = "canonical" if canonical_path.exists() else "experimental"
        return {
            "ok": True,
            "name": name,
            "source": source,
            "content": template
        }
    except TemplateError as e:
        return {"ok": False, "error": str(e)}


def write_template(name: str, yaml_content: str) -> dict:
    """
    Write a template to templates/experimental/.
    NEVER writes to templates/canonical/ — that boundary is absolute.

    name: template name (no .yaml extension)
    yaml_content: valid YAML string conforming to template schema

    RETURNS: dict with ok, path, name, validated
    """
    from infra.chain.template_loader import _load_and_validate, TemplateError
    import tempfile
    import os

    # Check canonical first - absolute boundary
    canonical_path = CANONICAL_DIR / f"{name}.yaml"
    if canonical_path.exists():
        return {
            "ok": False,
            "error": f"'{name}' exists in canonical — cannot overwrite via MCP"
        }

    # Validate YAML parses
    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return {"ok": False, "error": f"Invalid YAML: {e}"}

    # Validate template structure using loader
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name
        from pathlib import Path
        _load_and_validate(Path(tmp_path))
        os.unlink(tmp_path)
    except TemplateError as e:
        return {"ok": False, "error": f"Template validation failed: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"Validation error: {e}"}

    # Write to experimental only
    EXPERIMENTAL_DIR.mkdir(parents=True, exist_ok=True)
    output_path = EXPERIMENTAL_DIR / f"{name}.yaml"
    output_path.write_text(yaml_content, encoding="utf-8")

    logger.info(f"Director wrote experimental template: {name}")
    return {
        "ok": True,
        "name": name,
        "path": str(output_path),
        "validated": True,
        "source": "experimental",
        "message": f"Template '{name}' written to experimental. "
                   f"Runs {3} times successfully to promote to canonical."
    }


def delete_experimental_template(name: str) -> dict:
    """
    Delete a template from experimental only. Cannot delete canonical.
    RETURNS: dict with ok, name, deleted
    """
    path = EXPERIMENTAL_DIR / f"{name}.yaml"
    canonical_path = CANONICAL_DIR / f"{name}.yaml"

    if canonical_path.exists():
        return {
            "ok": False,
            "error": f"'{name}' is canonical — cannot delete via MCP"
        }
    if not path.exists():
        return {"ok": False, "error": f"Template not found: {name}"}

    path.unlink()
    return {"ok": True, "name": name, "deleted": True}


# ─────────────────────────────────────────────
# MEMORY TOOLS (extending existing)
# ─────────────────────────────────────────────

def list_memories(layer: str = None, limit: int = 50) -> dict:
    """
    List memories, optionally filtered by layer.
    layer: technical | project | personal | business | content | None (all)
    RETURNS: dict with ok, count, memories (list with key, layer, content preview)
    """
    from infra.db.schema import _exec
    try:
        limit = min(max(1, limit), 200)
        if layer:
            rows = _exec(
                """SELECT key, layer, content, created_at FROM memories
                   WHERE active=1 AND layer=?
                   ORDER BY created_at DESC LIMIT ?""",
                (layer, limit)
            )
        else:
            rows = _exec(
                """SELECT key, layer, content, created_at FROM memories
                   WHERE active=1
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            )
        memories = [
            {
                "key": r["key"],
                "layer": r["layer"],
                "preview": (r["content"] or "")[:100],
                "created_at": r["created_at"]
            }
            for r in (rows or [])
        ]
        return {"ok": True, "count": len(memories), "memories": memories}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def delete_memory(key: str) -> dict:
    """
    Soft-delete a memory by key (sets active=0).
    RETURNS: dict with ok, key, deleted
    """
    from infra.db.schema import _exec
    try:
        rows = _exec(
            "SELECT id FROM memories WHERE key=? AND active=1",
            (key,)
        )
        if not rows:
            return {"ok": False, "error": f"Memory not found: {key}"}
        _exec(
            "UPDATE memories SET active=0 WHERE key=?",
            (key,), commit=True
        )
        return {"ok": True, "key": key, "deleted": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────
# PATTERN TOOLS
# ─────────────────────────────────────────────

def get_promotion_candidates(status: str = None) -> dict:
    """
    List pattern candidates from observer.
    status: candidate | ready_to_promote | None (all)
    RETURNS: dict with ok, count, candidates
    """
    from infra.db.schema import _exec
    try:
        if status:
            rows = _exec(
                """SELECT * FROM pattern_candidates
                   WHERE promotion_status=?
                   ORDER BY observed_count DESC""",
                (status,)
            )
        else:
            rows = _exec(
                """SELECT * FROM pattern_candidates
                   ORDER BY observed_count DESC"""
            )
        candidates = [dict(r) for r in (rows or [])]
        return {"ok": True, "count": len(candidates), "candidates": candidates}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────
# DB INSPECTION (read-only SQL)
# ─────────────────────────────────────────────

def query_db(sql: str, params: list = None) -> dict:
    """
    Execute a read-only SQL query against Tower's DB.
    SELECT statements only — any other statement is rejected.
    Use for inspection and diagnosis only.

    RETURNS: dict with ok, rows, count
    """
    from infra.db.schema import _exec

    # Enforce read-only
    normalized = sql.strip().upper()
    if not normalized.startswith("SELECT"):
        return {
            "ok": False,
            "error": "Only SELECT statements permitted via query_db"
        }

    # Block dangerous patterns
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT",
                 "ALTER", "CREATE", "TRUNCATE", "REPLACE"]
    for word in forbidden:
        if re.search(r'\b' + re.escape(word) + r'\b', normalized, re.IGNORECASE):
            return {
                "ok": False,
                "error": f"Forbidden keyword in query: {word}"
            }

    try:
        cursor = _exec(sql, tuple(params) if params else ())
        rows = cursor.fetchall()
        result = [dict(r) for r in (rows or [])]
        return {"ok": True, "count": len(result), "rows": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}
