"""Tests for fetch_url and think tools."""

from dotenv import load_dotenv
load_dotenv()

from infra.db import init_db
init_db()


def _reset_fetch_rate_limit():
    """Reset fetch rate limit state for clean test runs."""
    try:
        from infra.db.rate_limits_db import upsert_api_state
        upsert_api_state(
            "fetch",
            calls_this_minute=0,
            last_429_at=None,
            retry_after_seconds=0
        )
    except Exception:
        # Database locked - skip reset, previous teardown should have handled it
        pass


def test_decorator(name):
    def wrapper(fn):
        fn.__name__ = name
        TESTS.append((name, fn))
        return fn
    return wrapper

test = test_decorator

TESTS = []


@test("fetch: fetch_url returns dict with content key")
def test_fetch_url_content():
    from tools.search.search_tools import fetch_url
    result = fetch_url("https://en.wikipedia.org/wiki/Python_(programming_language)")
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "content" in result, "Expected 'content' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"
    assert len(result.get("content", "")) > 0, "Expected non-empty content"


@test("fetch: fetch_url returns error dict for invalid URL")
def test_fetch_url_invalid():
    from tools.search.search_tools import fetch_url
    result = fetch_url("https://this-domain-does-not-exist-xyz.com")
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("ok") == False, "Expected ok=False for invalid URL"
    assert "error" in result, "Expected 'error' key for invalid URL"


@test("fetch: fetch_url content is truncated at max_chars")
def test_fetch_url_truncation():
    from tools.search.search_tools import fetch_url
    result = fetch_url("https://en.wikipedia.org/wiki/Python_(programming_language)", max_chars=100)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    content = result.get("content", "")
    assert len(content) <= 100, f"Expected content <= 100 chars, got {len(content)}"
    # For a long page like Wikipedia, truncation should be True
    assert result.get("truncated") == True, "Expected truncated=True for long page with max_chars=100"


@test("fetch: fetch_url cached on second call")
def test_fetch_url_cache():
    from tools.search.search_tools import fetch_url
    from infra.db.schema import _exec
    # Clear cache for this URL
    _exec("DELETE FROM tool_cache WHERE tool_name LIKE 'fetch%'", commit=True)
    
    result1 = fetch_url("https://en.wikipedia.org/wiki/Python_(programming_language)", max_chars=500)
    content1 = result1.get("content", "")
    
    result2 = fetch_url("https://en.wikipedia.org/wiki/Python_(programming_language)", max_chars=500)
    content2 = result2.get("content", "")
    
    assert content1 == content2, "Expected same content from cache on second call"
    assert result1.get("ok") == True
    assert result2.get("ok") == True


@test("think: think returns ok=True")
def test_think_ok():
    from tools.meta.meta import think
    result = think("Testing the think tool")
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("ok") == True, "Expected ok=True"


@test("think: think returns thought in result")
def test_think_content():
    from tools.meta.meta import think
    test_content = "Testing the think tool"
    result = think(test_content)
    assert result.get("thought") == test_content, f"Expected thought '{test_content}', got {result.get('thought')}"


@test("think: think with empty string returns ok=True")
def test_think_empty():
    from tools.meta.meta import think
    result = think("")
    assert result.get("ok") == True, "Expected ok=True for empty thought"
    assert result.get("thought") == "", "Expected empty thought"


@test("think: think result has stale_notice=None")
def test_think_stale_notice():
    from tools.meta.meta import think
    result = think("Testing stale_notice")
    assert result.get("stale_notice") is None, "Expected stale_notice=None for think tool"


def run_all():
    # Reset rate limit before tests run
    _reset_fetch_rate_limit()
    
    passed = 0
    failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}\n  {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}\n  Unexpected error: {e}")
            failed += 1
    
    return passed, failed


if __name__ == "__main__":
    print(run_all())
