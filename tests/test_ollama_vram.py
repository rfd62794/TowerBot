"""Tests for OllamaSwapManager._check_vram() — VRAM check via /api/ps."""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from api.local.ollama_api import OllamaSwapManager, TOTAL_VRAM_GB


def _make_manager(loaded_model=None):
    """Create a bare OllamaSwapManager without triggering health checks."""
    m = OllamaSwapManager.__new__(OllamaSwapManager)
    m._loaded_model = loaded_model
    m._lock = asyncio.Lock()
    m.host = "http://localhost:11434"
    m.model = "gemma4:e4b"
    m.enabled = True
    m._starting = False
    m._process = None
    return m


def _mock_httpx_client(json_payload):
    """Return a context manager mock that yields a client returning json_payload."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_payload

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_ctx


def _mock_httpx_client_raises(exc):
    """Return a context manager mock whose .get() raises exc."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=exc)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_ctx


# ── tests ──────────────────────────────────────────────────────────────────

def test_vram_check_allows_model_within_total_vram():
    """Empty /api/ps — nothing loaded. qwen2.5:7b (4.0GB) <= 4.0GB total → True."""
    manager = _make_manager()
    mock_ctx = _mock_httpx_client({"models": []})

    async def _run():
        with patch("api.local.ollama_api.httpx.AsyncClient", return_value=mock_ctx):
            return await manager._check_vram("qwen2.5:7b")

    result = asyncio.run(_run())
    assert result is True, f"Expected True (0GB used, 4.0GB available), got {result}"


def test_vram_check_blocks_when_other_processes_use_vram():
    """Non-Ollama model using 2GB VRAM. 4.0 - 2.0 = 2.0GB available. qwen2.5:7b needs 4.0GB → False."""
    manager = _make_manager()
    mock_ctx = _mock_httpx_client({
        "models": [{"name": "some-other-model", "size_vram": int(2.0 * 1024 ** 3)}]
    })

    async def _run():
        with patch("api.local.ollama_api.httpx.AsyncClient", return_value=mock_ctx):
            with patch("api.local.ollama_api.TOTAL_VRAM_GB", 4.0):
                return await manager._check_vram("qwen2.5:7b")

    result = asyncio.run(_run())
    assert result is False, f"Expected False (2.0GB available < 4.0GB required), got {result}"


def test_vram_check_excludes_current_loaded_model():
    """gemma4:e4b loaded (9.6GB VRAM). Checking qwen2.5:3b — gemma4 excluded → 32.0GB available → True."""
    manager = _make_manager(loaded_model="gemma4:e4b")
    mock_ctx = _mock_httpx_client({
        "models": [{"name": "gemma4:e4b", "size_vram": int(9.6 * 1024 ** 3)}]
    })

    async def _run():
        with patch("api.local.ollama_api.httpx.AsyncClient", return_value=mock_ctx):
            return await manager._check_vram("qwen2.5:3b")

    result = asyncio.run(_run())
    assert result is True, f"Expected True (gemma4:e4b excluded from used VRAM), got {result}"


def test_vram_check_falls_back_to_psutil_on_api_failure():
    """/api/ps raises ConnectionError — fallback to psutil. 8GB available → True for qwen2.5:7b."""
    manager = _make_manager()
    mock_ctx = _mock_httpx_client_raises(ConnectionError("connection refused"))

    mock_vmem = MagicMock()
    mock_vmem.available = int(8.0 * 1024 ** 3)

    async def _run():
        with patch("api.local.ollama_api.httpx.AsyncClient", return_value=mock_ctx):
            with patch("api.local.ollama_api.psutil.virtual_memory", return_value=mock_vmem):
                return await manager._check_vram("qwen2.5:7b")

    result = asyncio.run(_run())
    assert result is True, f"Expected True (psutil fallback: 8GB available), got {result}"


def test_vram_already_loaded_returns_true():
    """Model already present in /api/ps — return True immediately without VRAM math."""
    manager = _make_manager()
    mock_ctx = _mock_httpx_client({
        "models": [{"name": "gemma4:e4b", "size_vram": int(9.6 * 1024 ** 3)}]
    })

    async def _run():
        with patch("api.local.ollama_api.httpx.AsyncClient", return_value=mock_ctx):
            return await manager._check_vram("gemma4:e4b")

    result = asyncio.run(_run())
    assert result is True, f"Expected True when model already in VRAM, got {result}"


# ── harness ────────────────────────────────────────────────────────────────

TESTS = [
    test_vram_check_allows_model_within_total_vram,
    test_vram_check_blocks_when_other_processes_use_vram,
    test_vram_check_excludes_current_loaded_model,
    test_vram_check_falls_back_to_psutil_on_api_failure,
    test_vram_already_loaded_returns_true,
]


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  \u2713 ollama_vram: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 ollama_vram: {t.__name__}: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    p, f = run_all()
    print(f"\n{p}/{p+f} passed")
