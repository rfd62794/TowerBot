from infra.db import init_db
init_db()
from api.google.youtube_api import _get_credentials
import requests

creds = _get_credentials()
token = creds.token
task_id = "ZHUxZXVPQnpVcThKSUJSZQ"
tasklist_id = "MDQ2NjEyMzYzOTg4MjI0MTE4OTM6MDow"

response = requests.get(
    f"https://tasks.googleapis.com/tasks/v1/lists/{tasklist_id}/tasks/{task_id}",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"Status code: {response.status_code}")
print(f"Response: {response.text}")
