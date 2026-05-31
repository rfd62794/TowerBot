# Item 3: Consistent Error Shapes

Create BaseTool classes for goals.py and recommendations.py following the games.py pattern exactly. Fix dead code in games.py.

## Confirmed Approach

**tools/games.py analysis:**
- Lines 696-697: Module-level wrapper `get_game_metrics` calls `_games.get_game_metrics(game_name)` (class method with BaseTool)
- Line 137: Old standalone function with raw `{"error": ...}` is DEAD CODE - superseded by GameTools class + wrapper
- Action: Mark line 137 function as dead code with comment, keep GameTools class and wrapper

**tools/goals.py:**
- Create `GoalsTools(BaseTool)` class
- Move 4 functions with raw error returns into class: `get_goal_detail`, `get_current_plan`, `update_task`, `suggest_goal_progress`
- Keep other functions as module-level (they work fine): `get_goals_list`, `get_tasks_today`, `get_upcoming_tasks`, `add_new_task`, `save_commitment`
- Add module-level wrappers for the 4 class methods (registry unchanged)

**tools/recommendations.py:**
- Create `RecommendationsTools(BaseTool)` class
- Move `get_content_recommendations` into class
- Change empty list return to `self.success()` with empty recommendations dict
- Add module-level wrapper (registry unchanged)

## Implementation Steps

1. **tools/goals.py:**
   - Create `GoalsTools(BaseTool)` class at bottom
   - Move 4 functions into class with `self.error()`/`self.success()` pattern
   - Add singleton `_goals = GoalsTools()`
   - Add module-level wrappers for the 4 functions
   - Keep all other module-level functions unchanged

2. **tools/recommendations.py:**
   - Create `RecommendationsTools(BaseTool)` class
   - Move `get_content_recommendations` into class
   - Return `self.success()` for empty recommendations (not error)
   - Add singleton and module-level wrapper

3. **tools/games.py:**
   - Mark line 137 function as dead code with comment
   - Verify wrapper at line 696-697 calls class method (it does)

4. **tests/:**
   - Update assertions if they break (add `ok` checks alongside existing)

5. **Verify:**
   - Run `uv run python scripts/verify.py` - expect 192/192
   - Run spot check script for error shapes
