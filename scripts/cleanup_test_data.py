"""One-time cleanup of test records that polluted the live privy.db."""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
from infra.db.schema import _exec
init_db()

test_hashes = ("abc1234", "def5678", "ghi9012", "jkl3456")
placeholders = ",".join("?" * len(test_hashes))
_exec(f"DELETE FROM deploy_history WHERE commit_hash IN ({placeholders})", test_hashes)
print("Removed test deploy records.")

from infra.db import get_last_deploy, get_last_stable_commit
print(f"last_deploy: {get_last_deploy()}")
print(f"last_stable: {get_last_stable_commit()}")
