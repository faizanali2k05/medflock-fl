from types import SimpleNamespace

import numpy as np
import pytest
from flwr.app import ArrayRecord, ConfigRecord, Message, MetricRecord, RecordDict

from medflock.federation_policy import HospitalFedAvg


@pytest.fixture(autouse=True)
def task_identity(monkeypatch):
    from flwr.supercore.task_identity import TaskIdentity

    for name in ("_run_id", "_node_id", "_task_id"):
        monkeypatch.setattr(TaskIdentity, name, 1)


def setup_round(active):
    strategy = HospitalFedAvg(lambda: set(active), minimum=2)
    messages = list(
        strategy.configure_train(
            1,
            ArrayRecord([np.zeros(3)]),
            ConfigRecord(),
            SimpleNamespace(get_node_ids=lambda: [11, 12, 99]),
        )
    )
    return strategy, messages


def reply(message, values=None, count=4):
    return Message(
        RecordDict(
            {
                "arrays": ArrayRecord([np.ones(3) if values is None else values]),
                "metrics": MetricRecord({"num-examples": count}),
            }
        ),
        reply_to=message,
    )


def test_dispatch_only_admitted_transport_identities():
    strategy, messages = setup_round({11, 12})
    assert {m.metadata.dst_node_id for m in messages} == {11, 12}
    arrays, metrics = strategy.aggregate_train(1, [reply(m) for m in messages])
    assert np.array_equal(arrays.to_numpy_ndarrays()[0], np.ones(3))
    assert dict(metrics) == {}


def test_pause_between_dispatch_and_aggregation_prevents_update():
    active = {11, 12}
    strategy, messages = setup_round(active)
    active.remove(12)
    with pytest.raises(RuntimeError, match="global weights not changed"):
        strategy.aggregate_train(1, [reply(m) for m in messages])


@pytest.mark.parametrize(
    "values,count", [(np.ones(4), 4), (np.array([np.nan] * 3), 4), (np.ones(3), 0)]
)
def test_invalid_updates_cannot_meet_quorum(values, count):
    strategy, messages = setup_round({11, 12})
    with pytest.raises(RuntimeError, match="global weights not changed"):
        strategy.aggregate_train(1, [reply(messages[0]), reply(messages[1], values, count)])


def test_duplicates_and_unconfigured_round_fail_closed():
    strategy, messages = setup_round({11, 12})
    with pytest.raises(RuntimeError):
        strategy.aggregate_train(1, [reply(messages[0]), reply(messages[0])])
    with pytest.raises(RuntimeError):
        strategy.aggregate_train(2, [reply(m) for m in messages])


def test_insufficient_active_nodes_do_not_dispatch():
    with pytest.raises(RuntimeError, match="not dispatched"):
        setup_round({11})
