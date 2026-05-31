# Phase B: Tools Category Restructure

Restructure tools/ directory into category-based packages (content, games, search, productivity, communication, meta) for better organization.

## Steps

1. **Create category directories** - tools/content, tools/games, tools/search, tools/productivity, tools/communication, tools/meta with empty __init__.py files

2. **Move files to new locations:**
   - tools/youtube/channel.py → tools/content/channel.py
   - tools/youtube/videos.py → tools/content/videos.py
   - tools/youtube/discovery.py → tools/content/discovery.py
   - tools/games.py → tools/games/metrics.py
   - tools/recommendations.py → tools/games/recommendations.py
   - tools/search_tools.py → tools/search/search_tools.py
   - tools/goals.py → tools/productivity/goals.py
   - tools/personal.py → tools/productivity/personal.py
   - tools/calendar.py → tools/productivity/calendar.py
   - tools/sync_tasks.py → tools/productivity/sync.py
   - tools/gmail.py → tools/communication/gmail.py
   - tools/meta.py → tools/meta/meta.py

3. **Create package __init__.py files** - Each category package re-exports its public functions

4. **Update imports in moved files** - Fix cross-references (e.g., tools/games/recommendations.py imports from tools.games.metrics)

5. **Update tools/registry.py** - Change all import paths to new category structure

6. **Update bot/scheduler.py** - Update tool import paths

7. **Update test files** - Update all test imports to new paths

8. **Verify 193/193** - Run tests with old files still present

9. **Delete old files** - Remove old tool files and youtube/ directory

10. **Final verify** - 193/193 tests pass, bot starts cleanly

## Critical Constraints

- DO NOT modify tools/registry.py content (only import paths)
- DO NOT modify tools/__init__.py or tools/_tool.py
- DO NOT touch tools/api/ (Phase C)
- No tool function logic changes
- No test assertion changes
