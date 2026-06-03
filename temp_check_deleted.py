from infra.db import init_db
init_db()
from api.google.tasks_api import tasks_api
result = tasks_api.pull_tasks('MDQ2NjEyMzYzOTg4MjI0MTE4OTM6MDow', show_completed=False)
tasks = result.get('tasks', [])
deleted_tasks = [t for t in tasks if t.get('deleted')]
print(f'Total tasks: {len(tasks)}')
print(f'Deleted tasks: {len(deleted_tasks)}')
target_deleted = any(t.get('id') == 'ZHUxZXVPQnpVcThKSUJSZQ' and t.get('deleted') for t in tasks)
print(f'ZHUxZXVPQnpVcThKSUJSZQ deleted: {target_deleted}')
