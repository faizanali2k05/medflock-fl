"""Candidates are loaded only after integrity and active-contract validation."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from medflock.learning import predict
from medflock.task import CONTRACT_HASH, FEATURES, PatientFeatures, transform


def score_candidate(patient: PatientFeatures, manifest: dict, directory: Path):
    if manifest.get("contract_hash") != CONTRACT_HASH:
        raise ValueError("Model does not match the active task contract")
    filename = manifest.get("file", "")
    if not filename or Path(filename).name != filename or not filename.endswith(".npz"):
        raise ValueError("Invalid artifact filename")
    path = directory / filename
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("Model integrity check failed")
    with np.load(path, allow_pickle=False) as arrays:
        weights = arrays["weights"]
    if weights.shape != (len(FEATURES) + 1,) or not np.isfinite(weights).all():
        raise ValueError("Invalid model tensors")
    score = float(predict(weights, transform(pd.DataFrame([patient.model_dump()])))[0])
    return {
        "score": score,
        "model_id": manifest["id"],
        "clinical_status": "research_only",
        "interpretation": "Uncalibrated research score for the 90-day outcome benchmark",
        "medication_status": "not_assessed",
        "explanation": "This model cannot diagnose heart failure or recommend treatment.",
    }
