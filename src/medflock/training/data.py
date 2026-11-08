"""Data semantics travel with each model; preprocessing is fitted on training rows only."""

import hashlib
import io
import json
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.model_selection import GroupShuffleSplit, train_test_split

from medflock.task import CONTRACT as LEGACY


class Feature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
    unit: str = Field(min_length=1, max_length=120)
    kind: Literal["continuous", "binary"] = "continuous"
    minimum: float | None = None
    maximum: float | None = None


class TaskContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    version: int = Field(default=1, ge=1)
    features: list[Feature] = Field(min_length=1, max_length=100)
    target: str
    outcome: Literal["binary", "time_horizon"] = "binary"
    followup: str | None = None
    horizon: int = Field(default=90, ge=1, le=3650)
    group_column: str | None = None

    @model_validator(mode="after")
    def semantics(self):
        names = [feature.name for feature in self.features]
        if len(set(names)) != len(names):
            raise ValueError("Feature names must be unique")
        if {self.target, self.followup, self.group_column}.intersection(names):
            raise ValueError("Outcome, follow-up and patient IDs cannot be predictors")
        if self.outcome == "time_horizon" and not self.followup:
            raise ValueError("A time-horizon task requires a follow-up column")
        return self

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()


def default_contract():
    binary = {"anaemia", "diabetes", "high_blood_pressure", "sex", "smoking"}
    return TaskContract(
        id="heart-failure-90d",
        target="DEATH_EVENT",
        outcome="time_horizon",
        followup="time",
        features=[
            Feature(
                name=name,
                unit=LEGACY["feature_units"][name],
                kind="binary" if name in binary else "continuous",
            )
            for name in LEGACY["features"]
        ],
    )


def read_dataset(contents: bytes, contract: TaskContract):
    frame = pd.read_csv(
        io.BytesIO(contents), dtype={contract.group_column: str} if contract.group_column else None
    )
    if not 40 <= len(frame) <= 200000:
        raise ValueError("A dataset must contain 40–200,000 rows")
    required = [f.name for f in contract.features] + [contract.target]
    required += [c for c in [contract.followup, contract.group_column] if c]
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing contract columns: {', '.join(sorted(missing))}")
    original = len(frame)
    frame = frame.drop_duplicates().copy()
    duplicates = original - len(frame)
    for feature in contract.features:
        values = pd.to_numeric(frame[feature.name], errors="raise")
        if np.isinf(values).any() or values.notna().sum() == 0:
            raise ValueError(f"Feature {feature.name} is empty or contains infinity")
        if feature.kind == "binary" and not values.dropna().isin([0, 1]).all():
            raise ValueError(f"Feature {feature.name} must use 0/1 coding")
        if feature.minimum is not None and values.dropna().lt(feature.minimum).any():
            raise ValueError(f"Feature {feature.name} is below its declared minimum")
        if feature.maximum is not None and values.dropna().gt(feature.maximum).any():
            raise ValueError(f"Feature {feature.name} is above its declared maximum")
        frame[feature.name] = values
    if not frame[contract.target].isin([0, 1]).all():
        raise ValueError("Target values must be complete binary 0/1 values")
    excluded = 0
    if contract.outcome == "time_horizon":
        followup = pd.to_numeric(frame[contract.followup], errors="raise")
        if not np.isfinite(followup).all() or followup.lt(0).any():
            raise ValueError("Follow-up must be finite, nonnegative days")
        keep = (followup >= contract.horizon) | (frame[contract.target] == 1)
        excluded = int((~keep).sum())
        frame = frame.loc[keep].copy()
        labels = (
            ((frame[contract.target] == 1) & (followup.loc[keep] <= contract.horizon))
            .astype(int)
            .to_numpy()
        )
    else:
        labels = frame[contract.target].to_numpy(dtype=int)
    if len(np.unique(labels)) != 2 or np.bincount(labels).min() < 10:
        raise ValueError("At least ten eligible examples of each outcome are required")
    names = [feature.name for feature in contract.features]
    values = frame[names].to_numpy(dtype=float)
    groups = None
    if contract.group_column:
        if frame[contract.group_column].isna().any():
            raise ValueError("Patient/group identifiers cannot be missing")
        groups = frame[contract.group_column].astype(str).to_numpy()
    profile = {
        "source_rows": original,
        "eligible_rows": len(labels),
        "duplicate_rows_removed": duplicates,
        "early_censored_excluded": excluded,
        "positive_outcomes": int(labels.sum()),
        "features": len(names),
        "missing_values": int(np.isnan(values).sum()),
        "has_patient_groups": groups is not None,
    }
    return values, labels, groups, profile


def split_indices(labels, groups, seed):
    ids = np.arange(len(labels))
    if groups is None:
        development, test = train_test_split(ids, test_size=0.2, stratify=labels, random_state=seed)
        train, validation = train_test_split(
            development, test_size=0.25, stratify=labels[development], random_state=seed + 1
        )
    else:
        split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        development, test = next(split.split(ids, labels, groups))
        inner = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed + 1)
        a, b = next(inner.split(development, labels[development], groups[development]))
        train, validation = development[a], development[b]
    if any(len(np.unique(labels[part])) != 2 for part in [train, validation, test]):
        raise ValueError("The split lacks both outcomes; change seed or obtain more groups")
    return train, validation, test


def fit_transform(values):
    medians = np.nanmedian(values, axis=0)
    if not np.isfinite(medians).all():
        raise ValueError("A feature has no observed values in the training split")
    filled = np.where(np.isnan(values), medians, values)
    scale = filled.std(axis=0)
    scale[scale < 1e-8] = 1
    return {
        "median": medians.tolist(),
        "mean": filled.mean(axis=0).tolist(),
        "scale": scale.tolist(),
    }


def transform(values, state):
    filled = np.where(np.isnan(values), state["median"], values)
    return np.clip((filled - state["mean"]) / state["scale"], -10, 10)
