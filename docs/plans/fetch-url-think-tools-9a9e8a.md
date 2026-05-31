# fetch_url + think Tools Implementation

Add two new tools: fetch_url (browser tool for reading web pages) and think (scratchpad for reasoning). One session, 165/165 tests expected.

## Implementation Steps

### 1. requirements.txt
- Add `beautifulsoup4` if not present
- Verify `requests` is already present (it is)

### 2. tools/api/fetch_api.py (NEW FILE)
- Create FetchAPIHandler(BaseAPIHandler)
- CACHE_PREFIX = "fetch"
- Use requests (not httpx) for consistency
- fetch_url(url, max_chars=3000) method
- Use BeautifulSoup to extract text, remove noise elements (script, style, nav, header, footer, aside, form)
- Cache key: hash(url, max_chars) - include max_chars
- Return dict with: url, title, content, char_count, truncated, status_code
- Module-level instance and backwards compat function

### 3. core/cache.py
- Add TTL entry: "fetch_page": 3600 (1 hour)
- Add STALE_BUDGET entry: "fetch_page": 3600 (1 hour)
- Note: cache_key() produces "fetch_page" from CACHE_PREFIX="fetch" + suffix="page"

### 4. tools/meta.py (NEW FILE)
- Simple function only, no BaseTool, no BaseAPIHandler
- think(thought: str) -> dict
- Returns: {"ok": True, "thought": thought, "stale_notice": None}
- No side effects, no DB writes, no caching

### 5. tools/search_tools.py
- Add fetch_url method to SearchTools class
- Call fetch_api.fetch_url(), handle errors with self.error()
- Return self.success() with url, title, content, char_count, truncated
- Add module-level function delegating to _search.fetch_url()

### 6. tools/__init__.py
- Add fetch_url to TOOL_REGISTRY with detailed description
- Add think to TOOL_REGISTRY with detailed description
- Import think from tools.meta
- Import fetch_url from tools.search_tools

### 7. core/report.py
- Add "thought" event type to _format()
- Message: "💭 {thought}"
- Silent if thought is empty string

### 8. core/agent.py
- Add think rule to _system_prompt() in thinking process section
- Update _execute() to fire report("thought", thought=...) for think tool instead of generic "tool_called"

### 9. tests/test_fetch_think.py (NEW FILE)
- Test fetch_url returns dict with content key (use Wikipedia Python page)
- Test fetch_url returns error dict for invalid URL
- Test fetch_url content truncated at max_chars
- Test fetch_url cached on second call
- Test think returns ok=True
- Test think returns thought in result
- Test think with empty string returns ok=True
- Test think result has stale_notice=None

### 10. scripts/verify.py
- Add "tests/test_fetch_think.py" to TEST_FILES list

## Success Criteria
- `uv run python scripts/verify.py` passes 165/165 (157 + 8 new)
- Spot check: fetch_url works on Wikipedia page, think returns ok=True
- No changes outside specified files
- think has no side effects (no DB, no cache)
- fetch_url caches per URL+max_chars
- Both tools added to TOOL_REGISTRY with proper descriptions
