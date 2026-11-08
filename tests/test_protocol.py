import numpy as np
import pytest

from medflock.protocol import Contribution, tensor_hash
from medflock.task import CONTRACT_HASH


@pytest.mark.parametrize("change", ["round", "contract", "base", "tensor", "count"])
def test_reject_incompatible_or_stale_contribution(change):
    weights = np.array([1.0, 2.0])
    base = tensor_hash(np.zeros(2))
    envelope = Contribution(
        contract_hash=CONTRACT_HASH,
        base_model_hash=base,
        update_hash=tensor_hash(weights),
        round_number=1,
        sample_count=10,
    )
    expected = dict(
        contract_hash=CONTRACT_HASH,
        base_model_hash=base,
        round_number=1,
        expected_shape=(2,),
        expected_count=10,
    )
    envelope.validate_for(weights, **expected)
    if change == "round":
        expected["round_number"] = 2
    elif change == "contract":
        expected["contract_hash"] = "0" * 64
    elif change == "base":
        expected["base_model_hash"] = "0" * 64
    elif change == "tensor":
        weights[0] = 5
    else:
        expected["expected_count"] = 20
    with pytest.raises(ValueError):
        envelope.validate_for(weights, **expected)
