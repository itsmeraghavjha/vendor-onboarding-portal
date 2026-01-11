import requests
import time
from flask import current_app

BASE_URL = "https://eve.idfy.com/v3"


def run_task(task_type, payload):
    res = requests.post(
        f"{BASE_URL}/tasks/async/verify_with_source/{task_type}",
        headers={
            "Content-Type": "application/json",
            "api-key": current_app.config["IDFY_API_KEY"],
            "account-id": current_app.config["IDFY_ACCOUNT_ID"],
        },
        json={
            "task_id": payload.get("task_id"),
            "group_id": payload.get("group_id"),
            "data": payload["data"],
        },
        timeout=15,
    )
    res.raise_for_status()
    return res.json()["request_id"]


def poll_task(request_id, retries=10, delay=2):
    for _ in range(retries):
        r = requests.get(
            f"{BASE_URL}/tasks",
            headers={
                "api-key": current_app.config["IDFY_API_KEY"],
                "account-id": current_app.config["IDFY_ACCOUNT_ID"],
            },
            params={"request_id": request_id},
            timeout=5,
        )
        r.raise_for_status()
        task = r.json()[0]
        if task["status"] in ("completed", "failed"):
            return task
        time.sleep(delay)
    raise TimeoutError("IDFY polling timeout")
