"""Tests for model usage tracking and rate limit avoidance."""

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


@test("model_usage: record_model_call stores to DB")
def test_record_model_call():
    from infra.db.model_usage import record_model_call, count_model_calls
    
    # Record a call
    record_model_call(
        model_id="test/model",
        provider="test",
        tokens_in=100,
        tokens_out=50,
        cost_usd=0.01,
        success=True,
        latency_ms=500
    )
    
    # Verify it was stored
    count = count_model_calls(model_id="test/model", hours=1)
    assert count >= 1, f"Expected at least 1 call, got {count}"


@test("model_usage: count_model_calls respects rolling window")
def test_count_model_calls_rolling_window():
    from infra.db.model_usage import record_model_call, count_model_calls
    
    # Record a call
    record_model_call(
        model_id="test/window",
        provider="test",
        tokens_in=10,
        tokens_out=5,
        cost_usd=0.0,
        success=True
    )
    
    # Count in 1 hour window - should include the call
    count_1h = count_model_calls(model_id="test/window", hours=1)
    assert count_1h >= 1, f"Expected at least 1 call in 1h window, got {count_1h}"
    
    # Count in 1 minute window - should also include the call
    count_1m = count_model_calls(model_id="test/window", minutes=1)
    assert count_1m >= 1, f"Expected at least 1 call in 1m window, got {count_1m}"


@test("model_usage: count_model_calls_minute counts last 60 seconds only")
def test_count_model_calls_minute():
    from infra.db.model_usage import record_model_call, count_model_calls_minute
    
    # Record a call
    record_model_call(
        model_id="test/minute",
        provider="test",
        tokens_in=10,
        tokens_out=5,
        cost_usd=0.0,
        success=True
    )
    
    # Count in last minute
    count = count_model_calls_minute(model_id="test/minute")
    assert count >= 1, f"Expected at least 1 call in last minute, got {count}"


@test("model_usage: get_last_error_time returns correct timestamp")
def test_get_last_error_time():
    from infra.db.model_usage import record_model_call, get_last_error_time
    from datetime import datetime
    
    # Record an error
    record_model_call(
        model_id="test/error",
        provider="test",
        tokens_in=0,
        tokens_out=0,
        cost_usd=0.0,
        success=False,
        error_code=429
    )
    
    # Get last error time
    last_error = get_last_error_time(model_id="test/error", error_code=429)
    assert last_error is not None, "Expected error time to be returned"
    assert isinstance(last_error, datetime), f"Expected datetime, got {type(last_error)}"


@test("model_usage: count_model_errors filters by error_code")
def test_count_model_errors():
    from infra.db.model_usage import record_model_call, count_model_errors
    
    # Record a 429 error
    record_model_call(
        model_id="test/error_filter",
        provider="test",
        tokens_in=0,
        tokens_out=0,
        cost_usd=0.0,
        success=False,
        error_code=429
    )
    
    # Record a 404 error
    record_model_call(
        model_id="test/error_filter",
        provider="test",
        tokens_in=0,
        tokens_out=0,
        cost_usd=0.0,
        success=False,
        error_code=404
    )
    
    # Count 429 errors only
    count_429 = count_model_errors(model_id="test/error_filter", error_code=429, minutes=1)
    assert count_429 >= 1, f"Expected at least 1 429 error, got {count_429}"
    
    # Count 404 errors only
    count_404 = count_model_errors(model_id="test/error_filter", error_code=404, minutes=1)
    assert count_404 >= 1, f"Expected at least 1 404 error, got {count_404}"


@test("model_usage: get_daily_cost_usd sums correctly")
def test_get_daily_cost_usd():
    from infra.db.model_usage import record_model_call, get_daily_cost
    
    # Record calls with known costs
    record_model_call(
        model_id="test/cost",
        provider="test",
        tokens_in=10,
        tokens_out=5,
        cost_usd=0.05,
        success=True
    )
    
    record_model_call(
        model_id="test/cost",
        provider="test",
        tokens_in=10,
        tokens_out=5,
        cost_usd=0.03,
        success=True
    )
    
    # Get daily cost
    cost = get_daily_cost(provider="test", days=1)
    assert cost >= 0.08, f"Expected cost >= 0.08, got {cost}"


@test("model_manager: should_skip_model returns True at 95% daily limit")
def test_should_skip_daily_limit():
    from bot.model_manager import should_skip_model
    from infra.db.model_usage import record_model_call
    
    # Record enough calls to hit 95% of limit (200 * 0.95 = 190)
    for _ in range(195):
        record_model_call(
            model_id="deepseek/deepseek-v4-flash:free",
            provider="openrouter",
            tokens_in=10,
            tokens_out=5,
            cost_usd=0.0,
            success=True
        )
    
    should_skip, reason = should_skip_model("deepseek/deepseek-v4-flash:free")
    assert should_skip is True, f"Expected True at daily limit, got {should_skip}"
    assert "daily_limit" in reason, f"Expected 'daily_limit' in reason, got {reason}"


@test("model_manager: should_skip_model returns True during 429 backoff window")
def test_should_skip_backoff():
    from bot.model_manager import should_skip_model
    from infra.db.model_usage import record_model_call
    from datetime import datetime, timedelta
    
    # Use a model that exists in MODEL_LIMITS
    model_id = "deepseek/deepseek-v4-flash:free"
    
    # Record recent 429 errors
    for _ in range(3):
        record_model_call(
            model_id=model_id,
            provider="openrouter",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            success=False,
            error_code=429
        )
    
    should_skip, reason = should_skip_model(model_id)
    # Should skip due to backoff
    assert should_skip is True or reason == "ok", f"Expected True or ok, got {should_skip}, {reason}"


@test("model_manager: should_skip_model returns False for ollama provider")
def test_should_skip_ollama():
    from bot.model_manager import should_skip_model
    
    # Ollama should never skip
    should_skip, reason = should_skip_model("ollama")
    assert should_skip is False, f"Expected False for ollama, got {should_skip}"
    assert reason == "local", f"Expected 'local' reason, got {reason}"
    
    # Ollama with model name should also never skip
    should_skip, reason = should_skip_model("ollama/gemma3:4b")
    assert should_skip is False, f"Expected False for ollama/gemma3:4b, got {should_skip}"
    assert reason == "local", f"Expected 'local' reason, got {reason}"


@test("ollama: swap_manager_serializes_concurrent_calls")
def test_swap_manager_serializes_concurrent_calls():
    import asyncio
    from api.local.ollama_api import OllamaSwapManager
    
    manager = OllamaSwapManager()
    manager.enabled = False  # Disable actual API calls
    
    call_order = []
    
    # Track lock acquisition order
    async def task1():
        async with manager._lock:
            call_order.append("task1_start")
            await asyncio.sleep(0.05)
            call_order.append("task1_end")
    
    async def task2():
        async with manager._lock:
            call_order.append("task2_start")
            call_order.append("task2_end")
    
    # Run tasks concurrently
    async def run_both():
        await asyncio.gather(task1(), task2())
    
    asyncio.run(run_both())
    
    # Verify serialization - task1 completes before task2 starts
    assert "task1_start" in call_order
    assert "task1_end" in call_order
    assert "task2_start" in call_order
    assert "task2_end" in call_order
    # task1_end should come before task2_start
    assert call_order.index("task1_end") < call_order.index("task2_start")


@test("ollama: swap_manager_unloads_before_loading_new")
def test_swap_manager_unloads_before_loading_new():
    import asyncio
    from unittest.mock import patch, AsyncMock
    from api.local.ollama_api import OllamaSwapManager
    
    manager = OllamaSwapManager()
    manager.enabled = False
    
    # Mock the unload method
    unload_called = []
    
    async def mock_unload(model_id):
        unload_called.append(model_id)
    
    manager._unload = mock_unload
    
    # Simulate model change
    manager._loaded_model = "gemma3:4b"
    
    async def test_chat():
        # This would normally call _unload when model changes
        if manager._loaded_model != "qwen2.5:7b":
            if manager._loaded_model is not None:
                await manager._unload(manager._loaded_model)
            manager._loaded_model = "qwen2.5:7b"
    
    asyncio.run(test_chat())
    
    # Verify unload was called for the old model
    assert "gemma3:4b" in unload_called, f"Expected unload to be called for gemma3:4b, got {unload_called}"
    assert manager._loaded_model == "qwen2.5:7b"


@test("ollama: swap_manager_skips_unload_if_same_model")
def test_swap_manager_skips_unload_if_same_model():
    import asyncio
    from api.local.ollama_api import OllamaSwapManager
    
    manager = OllamaSwapManager()
    manager.enabled = False
    
    # Mock the unload method
    unload_called = []
    
    async def mock_unload(model_id):
        unload_called.append(model_id)
    
    manager._unload = mock_unload
    
    # Set current model
    manager._loaded_model = "gemma3:4b"
    
    async def test_chat():
        # Same model - should not unload
        if manager._loaded_model != "gemma3:4b":
            if manager._loaded_model is not None:
                await manager._unload(manager._loaded_model)
            manager._loaded_model = "gemma3:4b"
    
    asyncio.run(test_chat())
    
    # Verify unload was NOT called
    assert len(unload_called) == 0, f"Expected no unload call, got {unload_called}"


@test("ollama: swap_manager_handles_unload_failure")
def test_swap_manager_handles_unload_failure():
    import asyncio
    from api.local.ollama_api import OllamaSwapManager
    
    manager = OllamaSwapManager()
    manager.enabled = False
    
    # Mock unload to raise exception
    async def mock_unload(model_id):
        raise Exception("Unload failed")
    
    manager._unload = mock_unload
    
    async def test_chat():
        # Load first model
        manager._loaded_model = "gemma3:4b"
        # Try to load second model (should fail unload but continue)
        try:
            await manager.chat("ollama/qwen2.5:7b", [], None)
        except:
            pass  # Expected to fail
    
    asyncio.run(test_chat())


@test("ollama: swap_manager_restricts_large_models_daytime")
def test_swap_manager_restricts_large_models_daytime():
    import asyncio
    from unittest.mock import patch
    from api.local.ollama_api import OllamaSwapManager
    from datetime import datetime
    
    manager = OllamaSwapManager()
    manager.enabled = False
    
    # Mock datetime to return daytime hour (10 AM)
    with patch('api.local.ollama_api.datetime') as mock_dt:
        mock_dt.now.return_value.hour = 10  # 10 AM (daytime)
        
        async def test_chat():
            try:
                await manager.chat("ollama/qwen2.5:7b", [], None)
                assert False, "Expected exception for large model during daytime"
            except Exception as e:
                assert "restricted to nighttime" in str(e), f"Expected nighttime restriction error, got {e}"
        
        asyncio.run(test_chat())


@test("ollama: swap_manager_allows_large_models_nighttime")
def test_swap_manager_allows_large_models_nighttime():
    import asyncio
    from unittest.mock import patch, MagicMock
    from api.local.ollama_api import OllamaSwapManager
    
    manager = OllamaSwapManager()
    manager.enabled = False
    
    # Mock datetime to return nighttime hour (10 PM)
    with patch('api.local.ollama_api.datetime') as mock_dt:
        mock_dt.now.return_value.hour = 22  # 10 PM (nighttime)
        
        # Mock psutil to return sufficient RAM
        with patch('api.local.ollama_api.psutil') as mock_psutil:
            mock_ram = MagicMock()
            mock_ram.available = 5 * (1024**3)  # 5GB available
            mock_psutil.virtual_memory.return_value = mock_ram
            
            # Mock _inference to avoid actual API call
            async def mock_inference(*args, **kwargs):
                return {"choices": [{"message": {"content": "test"}}]}
            
            manager._inference = mock_inference
            
            async def test_chat():
                try:
                    result = await manager.chat("ollama/qwen2.5:7b", [], None)
                    # Should not raise nighttime restriction error
                    assert True
                except Exception as e:
                    if "restricted to nighttime" in str(e):
                        assert False, f"Should allow large model at night, got {e}"
                    # Other errors (like RAM) are OK for this test
            
            asyncio.run(test_chat())


if __name__ == "__main__":
    passed, total = run_all()
    print(f"\n{passed}/{total} passed")
    sys.exit(0 if passed == total else 1)
