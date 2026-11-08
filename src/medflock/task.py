"""The active contract uses fixed transforms so no test or peer statistics leak into training."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

RESOURCES = Path(__file__).resolve().parent / "resources"
CONTRACT = json.loads((RESOURCES / "heart-failure-90d.v1.json").read_text())
CONTRACT_HASH = hashlib.sha256(json.dumps(CONTRACT, sort_keys=True).encode()).hexdigest()
FEATURES = CONTRACT["features"]
SCALES = np.array(CONTRACT["feature_scales"])


class PatientFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    age: float = Field(ge=18, le=120)
    anaemia: int = Field(ge=0, le=1)
    creatinine_phosphokinase: float = Field(ge=0, le=100000)
    diabetes: int = Field(ge=0, le=1)
    ejection_fraction: float = Field(gt=0, le=100)
    high_blood_pressure: int = Field(ge=0, le=1)
    platelets: float = Field(gt=0, le=2000000)
    serum_creatinine: float = Field(gt=0, le=30)
    serum_sodium: float = Field(gt=0, le=200)
    sex: int = Field(ge=0, le=1)
    smoking: int = Field(ge=0, le=1)


def transform(frame: pd.DataFrame) -> np.ndarray:
    values = frame[FEATURES].to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Features must be finite and complete")
    return np.column_stack([np.clip(values / SCALES, -10, 10), np.ones(len(values))])


def load_cohort(path: Path) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_csv(path)
    expected = set(FEATURES + ["time", "DEATH_EVENT"])
    if set(frame.columns) != expected:
        raise ValueError("Dataset columns do not match the active contract")
    for row in frame[FEATURES].to_dict("records"):
        PatientFeatures.model_validate(row)
    if not frame.DEATH_EVENT.isin([0, 1]).all() or not frame.time.ge(0).all():
        raise ValueError("Invalid event or follow-up coding")
    if not np.isfinite(frame.time).all():
        raise ValueError("Non-finite follow-up")
    original = len(frame)
    frame = frame.drop_duplicates().copy()
    distinct = len(frame)
    eligible = (frame.time >= 90) | (frame.DEATH_EVENT == 1)
    frame = frame.loc[eligible].copy()
    frame["target"] = ((frame.DEATH_EVENT == 1) & (frame.time <= 90)).astype(int)
    frame["row_id"] = frame.index.astype(int)
    if len(frame) < 30 or frame.target.nunique() != 2 or frame.target.value_counts().min() < 5:
        raise ValueError("Insufficient eligible observations or outcome classes")
    return frame, {
        "source_rows": original,
        "duplicate_rows_removed": original - distinct,
        "early_censored_excluded": distinct - len(frame),
        "eligible_rows": len(frame),
        "events_90d": int(frame.target.sum()),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
