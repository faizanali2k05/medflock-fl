"""Explicit hospital-local schema mapping; records never leave this process."""

import io
import math

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from medflock.training.data import TaskContract


class ColumnMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1)
    source_unit: str = Field(min_length=1)
    target_unit: str = Field(min_length=1)
    scale: float = 1
    offset: float = 0
    codes: dict[str, int] | None = None

    @model_validator(mode="after")
    def valid_conversion(self):
        if not math.isfinite(self.scale) or self.scale <= 0 or not math.isfinite(self.offset):
            raise ValueError("Conversions require a positive finite scale and finite offset")
        if self.codes and (self.scale != 1 or self.offset != 0):
            raise ValueError("Do not combine category coding with unit conversion")
        if self.codes and not set(self.codes.values()) <= {0, 1}:
            raise ValueError("Category codes must map explicitly to 0 or 1")
        return self


class LocalMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_digest: str
    reviewed_by: str = Field(min_length=1, max_length=120)
    review_reference: str = Field(min_length=1, max_length=240)
    columns: dict[str, ColumnMapping]


def map_local_csv(contents: bytes, contract: TaskContract, mapping: LocalMapping):
    if mapping.contract_digest != contract.digest:
        raise ValueError("Mapping belongs to a different task contract")
    units = {feature.name: feature.unit for feature in contract.features}
    units[contract.target] = "binary"
    if contract.followup:
        units[contract.followup] = "days"
    if contract.group_column:
        units[contract.group_column] = "identifier"
    if set(mapping.columns) != set(units):
        raise ValueError("Mapping must cover exactly the task's required columns")
    sources = [column.source for column in mapping.columns.values()]
    if len(sources) != len(set(sources)):
        raise ValueError("Reusing a source column could leak outcomes into predictors")
    frame = pd.read_csv(io.BytesIO(contents), dtype=str)
    if not set(sources) <= set(frame.columns):
        raise ValueError("Local file is missing a mapped source column")
    result = pd.DataFrame(index=frame.index)
    for target, column in mapping.columns.items():
        if column.target_unit != units[target]:
            raise ValueError(f"Target unit for {target} does not match the model contract")
        values = frame[column.source]
        if target == contract.group_column:
            if column.codes or column.scale != 1 or column.offset != 0:
                raise ValueError("Patient grouping identifiers cannot be transformed")
            result[target] = values
        elif column.codes:
            unknown = values.notna() & ~values.isin(column.codes)
            if unknown.any():
                raise ValueError(f"Unmapped category in {target}; review the local mapping")
            result[target] = values.map(column.codes)
        else:
            result[target] = pd.to_numeric(values, errors="raise") * column.scale + column.offset
    return result.to_csv(index=False).encode("utf-8")
