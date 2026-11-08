import numpy as np
import pytest


def test_one_batch_gemma_adapter_round_exchanges_no_record_payload(tmp_path, monkeypatch):
    from flwr.supercore.task_identity import TaskIdentity

    for name in ("_run_id", "_node_id", "_task_id"):
        monkeypatch.setattr(TaskIdentity, name, 1)
    pytest.importorskip("torch")
    pytest.importorskip("peft")
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "adapter_check", Path(__file__).parents[1] / "scripts/check_adapter_federation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.check(tmp_path)


def test_adapter_shapes_and_nonfinite_updates_rejected():
    pytest.importorskip("torch")
    pytest.importorskip("peft")
    from medflock.adapter_federation import apply_adapter_arrays

    with pytest.raises(ValueError, match="count"):
        apply_adapter_arrays(None, [], [("x", [2])])
    with pytest.raises(ValueError, match="Invalid"):
        apply_adapter_arrays(None, [np.array([np.nan, 1], dtype=np.float32)], [("x", [2])])
