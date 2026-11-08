"""Deployment-engine spike uses synthetic local data and the pinned Flower Message API."""

import json
from pathlib import Path

import numpy as np
from flwr.app import ArrayRecord, ConfigRecord, Context, Message, MetricRecord, RecordDict
from flwr.clientapp import ClientApp
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import FedAvg

from medflock.learning import train
from medflock.node_data import load_node
from medflock.training.models import BinaryModel

client_app = ClientApp()
server_app = ServerApp()


@client_app.train()
def train_node(message: Message, context: Context):
    config = message.content["config"]
    if "adapter-contract" in config:
        from medflock.adapter_federation import train_adapter_message

        return train_adapter_message(message, context)
    if "contract-digest" in config:
        values, labels = load_node(context.node_config["data-dir"], config["contract-digest"])
        model = BinaryModel(values.shape[1])
        initial = message.content["arrays"].to_numpy_ndarrays()[0]
        if initial.shape != (model.size,) or not np.isfinite(initial).all():
            raise ValueError("Coordinator model shape or values are invalid")
        weights = model.train(
            initial,
            values,
            labels,
            int(config["local-epochs"]),
            float(config["learning-rate"]),
            float(config["l2"]),
        )
        return Message(
            RecordDict(
                {
                    "arrays": ArrayRecord([weights]),
                    "metrics": MetricRecord({"num-examples": len(labels)}),
                }
            ),
            reply_to=message,
        )
    partition_id = int(context.node_config["partition-id"])
    rng = np.random.default_rng(100 + partition_id)
    features = np.column_stack([rng.normal(size=(24, 2)), np.ones(24)])
    labels = (features[:, 0] + features[:, 1] > 0).astype(int)
    config = message.content["config"]
    weights = train(
        message.content["arrays"].to_numpy_ndarrays()[0],
        features,
        labels,
        int(config["local-epochs"]),
        float(config["learning-rate"]),
    )
    return Message(
        RecordDict(
            {
                "arrays": ArrayRecord([weights]),
                "metrics": MetricRecord({"num-examples": len(labels)}),
            }
        ),
        reply_to=message,
    )


@server_app.main()
def main(grid: Grid, context: Context):
    count = int(context.run_config["num-clients"])
    specification_path = str(context.run_config.get("server-manifest", ""))
    specification = json.loads(Path(specification_path).read_text()) if specification_path else None
    adapter = bool(specification and specification.get("family") == "causal-lora")
    if adapter:
        with np.load(
            Path(specification_path).parent / "initial-adapter.npz", allow_pickle=False
        ) as data:
            initial_arrays = [data[name].copy() for name in sorted(data.files)]
        if [list(value.shape) for value in initial_arrays] != [
            shape for _, shape in specification["layout"]
        ]:
            raise ValueError("Initial adapter layout mismatch")
    else:
        initial = np.zeros(int(specification["features"]) + 1) if specification else np.zeros(3)
        initial_arrays = [initial]
    if not all(np.isfinite(value).all() for value in initial_arrays):
        raise ValueError("Initial model contains invalid weights")
    training_config = {
        "local-epochs": context.run_config["local-epochs"],
        "learning-rate": context.run_config["learning-rate"],
    }
    if adapter:
        training_config.update({"adapter-contract": specification["digest"]})
    elif specification:
        training_config.update({"contract-digest": specification["digest"], "l2": 0.01})
    strategy = FedAvg(min_train_nodes=count, min_available_nodes=count, fraction_evaluate=0.0)
    if context.run_config.get("hospital-mode", False):
        from sqlalchemy import create_engine

        from medflock.config import Settings
        from medflock.federation_policy import HospitalFedAvg, eligible_identities

        if not specification:
            raise ValueError("Hospital rounds require a reviewed task manifest")
        engine = create_engine(Settings.load().database_url)
        strategy = HospitalFedAvg(lambda: eligible_identities(engine), minimum=count)
    result = strategy.start(
        grid=grid,
        initial_arrays=ArrayRecord(initial_arrays),
        num_rounds=int(context.run_config["num-server-rounds"]),
        timeout=60,
        train_config=ConfigRecord(training_config),
    )
    updated = result.arrays.to_numpy_ndarrays()
    if adapter:
        if not all(np.isfinite(value).all() for value in updated):
            raise RuntimeError("Invalid aggregated adapter")
        np.savez(
            Path(specification_path).parent / "global-adapter.npz",
            **{f"tensor-{i:04d}": value for i, value in enumerate(updated)},
        )
        print(f"MEDFLOCK_ADAPTER_OK clients={count} tensors={len(updated)}", flush=True)
        return
    weights = updated[0]
    if not np.isfinite(weights).all() or np.linalg.norm(weights) == 0:
        raise RuntimeError("Transport spike did not produce a valid trained model")
    if specification:
        np.savez(Path(specification_path).parent / "global-weights.npz", weights=weights)
    print(f"MEDFLOCK_SPIKE_OK clients={count} norm={np.linalg.norm(weights):.8f}", flush=True)
