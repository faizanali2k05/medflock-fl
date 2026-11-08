"""Exercise the container's actual dataset and configured database without a public port."""

import time
import uuid

from fastapi.testclient import TestClient

from medflock.api import app

with TestClient(app) as client:
    assert client.get("/api/status").json()["dataset_available"]
    key = uuid.uuid4().hex
    response = client.post("/api/runs", json={"rounds": 2}, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in {"completed", "failed"}:
            break
        time.sleep(0.1)
    assert run["status"] == "completed", run
    assert client.get("/api/models").json()
    assert client.get("/").status_code == 200
    print(
        {
            "container_smoke": "passed",
            "eligible": run["result"]["cohort"]["eligible_rows"],
            "clinical_status": run["result"]["clinical_status"],
        }
    )
