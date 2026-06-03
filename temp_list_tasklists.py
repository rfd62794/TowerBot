from infra.db import init_db
init_db()
from api.google.tasks_api import _get_tasks_client
client = _get_tasks_client()
result = client.tasklists().list().execute()
print('Task lists:')
for t in result.get('items', []):
    print(f"  {t['id']}: {t['title']}")
