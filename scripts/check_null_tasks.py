"""Check null tasks in agent_actions table."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()

from infra.db.schema import _exec

result = _exec("SELECT COUNT(*) FROM agent_actions WHERE task_name IS NULL").fetchone()
print(f"Null tasks: {result[0]}")
