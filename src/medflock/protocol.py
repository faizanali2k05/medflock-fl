"""Contribution metadata binds weights to one task, base model and aggregation round."""

import hashlib

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


def tensor_hash(weights: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(weights, dtype="<f8").tobytes()).hexdigest()


class Contribution(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contract_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    base_model_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    update_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    round_number: int = Field(ge=1)
    sample_count: int = Field(ge=1)

    def validate_for(
        self,
        weights,
        *,
        contract_hash,
        base_model_hash,
        round_number,
        expected_shape,
        expected_count,
    ):
        if self.contract_hash != contract_hash:
            raise ValueError("Contribution task contract mismatch")
        if self.base_model_hash != base_model_hash or self.round_number != round_number:
            raise ValueError("Stale or unexpected contribution")
        if weights.shape != expected_shape or not np.isfinite(weights).all():
            raise ValueError("Invalid contribution tensors")
        if self.update_hash != tensor_hash(weights) or self.sample_count != expected_count:
            raise ValueError("Contribution integrity or sample count mismatch")
