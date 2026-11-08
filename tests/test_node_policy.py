from datetime import datetime, timedelta, timezone

import pytest

from medflock.node_policy import effective_status, training_allowed
from medflock.service import Workbench
from medflock.store import Store, fleet


def test_policy_blocks_training_and_expiry_restores_previous_policy(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'nodes.db'}")
    service = Workbench(store, tmp_path / "unused.csv", tmp_path / "artifacts")
    service.register_node("hospital-one", "Hospital one")
    for policy in ["paused", "restricted", "suspended"]:
        node = service.set_node_status("hospital-one", policy)
        assert not training_allowed(node)
    service.set_node_status("hospital-one", "restricted")
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    node = service.set_node_status("hospital-one", "suspended", expiry.isoformat(), "admin")
    assert effective_status(node, expiry - timedelta(seconds=1)) == "suspended"
    assert effective_status(node, expiry) == "restricted"
    node = service.set_node_status("hospital-one", "active")
    assert training_allowed(node)
    assert "suspended_until" not in node["details"]
    with store.engine.begin() as conn:
        conn.execute(fleet.update().where(fleet.c.id == "hospital-one").values(status="removed"))
    with pytest.raises(ValueError, match="Revoked"):
        service.set_node_status("hospital-one", "active")
