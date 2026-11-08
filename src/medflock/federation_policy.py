"""Recheck admission at dispatch and aggregation using transport-assigned Flower identities."""

import numpy as np
from flwr.app import MessageType, RecordDict
from flwr.serverapp.strategy import FedAvg
from sqlalchemy import select

from medflock.node_policy import effective_status
from medflock.store import fleet, snapshots


def eligible_identities(engine):
    with engine.connect() as conn:
        nodes = {row["id"]: row for row in conn.execute(select(fleet)).mappings()}
        bindings = (
            conn.execute(select(snapshots).where(snapshots.c.id.startswith("flower_identity_")))
            .mappings()
            .all()
        )
    return {
        int(row["id"].removeprefix("flower_identity_"))
        for row in bindings
        if (node := nodes.get(row["details"]["node_id"]))
        and effective_status(node) == "active"
        and node["kind"] == "registered_external"
    }


class HospitalFedAvg(FedAvg):
    def __init__(self, eligible, minimum, **kwargs):
        super().__init__(
            min_train_nodes=minimum, min_available_nodes=minimum, fraction_evaluate=0.0, **kwargs
        )
        self.eligible = eligible
        self.minimum = minimum
        self.dispatched = {}
        self.shapes = {}

    def configure_train(self, server_round, arrays, config, grid):
        selected = sorted(set(grid.get_node_ids()) & self.eligible())
        if len(selected) < self.minimum:
            raise RuntimeError(
                "Insufficient admitted, active hospital runners; round not dispatched"
            )
        self.dispatched[server_round] = set(selected)
        self.shapes[server_round] = [value.shape for value in arrays.to_numpy_ndarrays()]
        config["server-round"] = server_round
        return self._construct_messages(
            RecordDict(
                {
                    self.arrayrecord_key: arrays,
                    self.configrecord_key: config,
                }
            ),
            selected,
            MessageType.TRAIN,
        )

    def aggregate_train(self, server_round, replies):
        allowed = self.dispatched.pop(server_round, set()) & self.eligible()
        shapes = self.shapes.pop(server_round, [])
        accepted, seen = [], set()
        for reply in replies:
            identity = reply.metadata.src_node_id
            if identity not in allowed or identity in seen or reply.has_error():
                continue
            seen.add(identity)
            try:
                if set(reply.content.keys()) != {self.arrayrecord_key, "metrics"}:
                    continue
                if set(reply.content["metrics"].keys()) != {self.weighted_by_key}:
                    continue
                arrays = reply.content[self.arrayrecord_key].to_numpy_ndarrays()
                count = reply.content["metrics"][self.weighted_by_key]
                if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                    continue
                if [value.shape for value in arrays] != shapes:
                    continue
                if not all(np.isfinite(value).all() for value in arrays):
                    continue
            except (KeyError, TypeError, AttributeError, ValueError):
                continue
            accepted.append(reply)
        if len(accepted) < self.minimum:
            raise RuntimeError("Insufficient eligible valid updates; global weights not changed")
        return super().aggregate_train(server_round, accepted)
