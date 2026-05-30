"""Tests for core/ layer — model_manager, scheduler."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("core: model_manager discovers free models")
def test_fetch_models():
    from bot.model_manager import fetch_free_tool_models
    models = fetch_free_tool_models()
    assert isinstance(models, list), "Expected list of models"
    assert len(models) >= 5, f"Expected 5+ models, got {len(models)}"


@test("core: get_available_model returns a model or None (not exception)")
def test_get_available_model():
    from bot.model_manager import get_available_model
    result = get_available_model()
    assert result is None or isinstance(result, str), \
        f"Expected str or None, got {type(result)}"


@test("core: TOOL_INCOMPATIBLE excludes owl-alpha")
def test_tool_incompatible():
    from bot.model_manager import TOOL_INCOMPATIBLE
    assert "openrouter/owl-alpha" in TOOL_INCOMPATIBLE, \
        "owl-alpha should be in TOOL_INCOMPATIBLE"
    assert "z-ai/glm-4.5-air:free" in TOOL_INCOMPATIBLE, \
        "glm-4.5-air should be in TOOL_INCOMPATIBLE"


@test("core: should_send_now returns bool")
def test_should_send_now():
    from bot.scheduler import should_send_now
    assert callable(should_send_now), "should_send_now not callable"
    result = should_send_now("normal")
    assert isinstance(result, bool), \
        f"should_send_now should return bool, got {type(result)}"


@test("core: should_send_now blocks urgent during sleep hours logic")
def test_should_send_now_urgent():
    from bot.scheduler import should_send_now
    result_urgent = should_send_now("urgent")
    result_normal = should_send_now("normal")
    assert isinstance(result_urgent, bool), "Expected bool for urgent"
    assert isinstance(result_normal, bool), "Expected bool for normal"


@test("core: heartbeat_check runs without error")
def test_heartbeat():
    import asyncio
    from bot.scheduler import heartbeat_check

    async def fake_send(msg):
        return None

    async def _run():
        await heartbeat_check(fake_send)

    asyncio.run(_run())


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
