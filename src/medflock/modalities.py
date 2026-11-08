"""Local modality adapters produce versioned features without inventing paired patient data."""

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field
from scipy.signal import resample_poly

from medflock.training.data import Feature, TaskContract


class ModalitySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    modality: str
    privacy_review_reference: str = Field(min_length=8)
    source: str = Field(min_length=3)
    permission: str = Field(min_length=3)
    leads: list[str] = Field(default_factory=list)
    sampling_hz: int = Field(default=250, ge=50, le=4000)
    units: str = "mV"
    image_size: int = Field(default=32, ge=16, le=128)


def image_features(contents, size):
    with Image.open(io.BytesIO(contents)) as image:
        if image.format not in {"PNG", "JPEG"} or image.width * image.height > 20_000_000:
            raise ValueError(
                "Only bounded PNG/JPEG images are supported; DICOM needs a separate adapter"
            )
        image = ImageOps.exif_transpose(image).convert("L")
        pixels = np.asarray(image.resize((size, size)), dtype=float) / 255
    grid = np.array(
        [block.mean() for row in np.array_split(pixels, 4) for block in np.array_split(row, 4)]
    )
    return np.r_[
        grid,
        pixels.std(),
        np.abs(np.diff(pixels, axis=0)).mean(),
        np.abs(np.diff(pixels, axis=1)).mean(),
    ]


def ecg_features(contents, sampling_hz, target_hz, leads, units):
    if units != "mV" or not leads or len(set(leads)) != len(leads):
        raise ValueError("ECG requires unique ordered leads and physical mV units")
    signal = np.load(io.BytesIO(contents), allow_pickle=False)
    if signal.ndim != 2 or signal.shape[1] != len(leads) or not np.isfinite(signal).all():
        raise ValueError("ECG must be a finite [samples, ordered leads] NPY array")
    if not 50 <= sampling_hz <= 4000 or not 2 <= len(signal) / sampling_hz <= 120:
        raise ValueError("ECG duration must be 2–120 seconds with a supported sampling rate")
    from math import gcd

    divisor = gcd(sampling_hz, target_hz)
    signal = resample_poly(signal, target_hz // divisor, sampling_hz // divisor, axis=0)
    result = []
    for channel in signal.T:
        centered = channel - np.median(channel)
        result.extend(
            [
                np.std(centered),
                np.sqrt(np.mean(centered**2)),
                np.quantile(centered, 0.95) - np.quantile(centered, 0.05),
                np.mean(np.abs(np.diff(centered))),
                np.mean(np.abs(centered)),
            ]
        )
    return np.asarray(result)


def adapt(manifest_contents, root, spec):
    spec = ModalitySpec.model_validate(spec)
    if spec.modality not in {"image", "ecg_waveform"}:
        raise ValueError(
            "Supported modalities: image, ecg_waveform; report images are not waveforms"
        )
    records = json.loads(manifest_contents)
    if not isinstance(records, list) or not 40 <= len(records) <= 200000:
        raise ValueError("Manifest requires 40–200000 records")
    root = Path(root).resolve()
    rows, seen, exclusions = [], {}, 0
    for record in records:
        path = (root / record["path"]).resolve()
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or path.stat().st_size > 25 * 1024**2
        ):
            raise ValueError("Input must be a bounded file within the declared dataset root")
        if record.get("privacy_review") != "cleared" or not record.get("patient_group"):
            raise ValueError(
                "Every record needs privacy clearance and a pseudonymous patient group"
            )
        if record.get("label") not in [0, 1]:
            raise ValueError("This adapter currently supports binary tasks only")
        contents = path.read_bytes()
        fingerprint = hashlib.sha256(contents).hexdigest()
        identity = (record["label"], record["patient_group"])
        if fingerprint in seen:
            if seen[fingerprint] != identity:
                raise ValueError("Duplicate content has conflicting labels or patient assignments")
            exclusions += 1
            continue
        seen[fingerprint] = identity
        if spec.modality == "image":
            values = image_features(contents, spec.image_size)
        else:
            if record.get("leads") != spec.leads or record.get("units") != spec.units:
                raise ValueError("ECG lead order/units differ from the task specification")
            values = ecg_features(
                contents, int(record["sampling_hz"]), spec.sampling_hz, spec.leads, spec.units
            )
        row = {f"f{index:03d}": float(value) for index, value in enumerate(values)}
        row.update(patient_group=str(record["patient_group"]), label=record["label"])
        rows.append(row)
    if not rows:
        raise ValueError("No eligible modality records")
    feature_names = [name for name in rows[0] if name.startswith("f")]
    semantics = {
        key: value
        for key, value in spec.model_dump().items()
        if key not in {"privacy_review_reference", "source", "permission"}
    }
    semantic_hash = hashlib.sha256(json.dumps(semantics, sort_keys=True).encode()).hexdigest()
    contract = TaskContract(
        id=spec.task_id,
        target="label",
        group_column="patient_group",
        features=[Feature(name=name, unit="adapter-v1:" + semantic_hash) for name in feature_names],
    )
    provenance = {
        "source": spec.source,
        "permission": spec.permission,
        "adapter": spec.modality + "-features-v1",
        "specification": spec.model_dump(),
        "specification_hash": hashlib.sha256(spec.model_dump_json().encode()).hexdigest(),
        "duplicates_removed": exclusions,
        "clinical_status": "research_only",
    }
    return pd.DataFrame(rows).to_csv(index=False).encode(), contract, provenance
