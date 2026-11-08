import pandas as pd
import pytest

from medflock.local_mapping import LocalMapping, map_local_csv
from medflock.training.data import Feature, TaskContract


def test_local_schema_mapping_converts_units_and_rejects_unknown_codes():
    import io

    contract = TaskContract(
        id="test-task",
        target="outcome",
        group_column="patient",
        features=[Feature(name="measurement", unit="mg/dL")],
    )
    mapping = LocalMapping(
        contract_digest=contract.digest,
        reviewed_by="local-data-steward",
        review_reference="approved-conversion-1",
        columns={
            "measurement": {
                "source": "value",
                "source_unit": "mg/L",
                "target_unit": "mg/dL",
                "scale": 0.1,
            },
            "outcome": {
                "source": "event",
                "source_unit": "category",
                "target_unit": "binary",
                "codes": {"yes": 1, "no": 0},
            },
            "patient": {
                "source": "local_id",
                "source_unit": "identifier",
                "target_unit": "identifier",
            },
        },
    )
    data = b"local_id,value,event,private_note\n001,120,yes,never_export\n002,90,no,never_export\n"
    converted = map_local_csv(data, contract, mapping)
    assert b"never_export" not in converted
    frame = pd.read_csv(io.BytesIO(converted), dtype={"patient": str})
    assert frame["measurement"].tolist() == [12, 9]
    assert frame["patient"].tolist() == ["001", "002"]
    with pytest.raises(ValueError, match="Unmapped category"):
        map_local_csv(data.replace(b"yes", b"unknown"), contract, mapping)
    mapping.columns["measurement"].target_unit = "wrong"
    with pytest.raises(ValueError, match="Target unit"):
        map_local_csv(data, contract, mapping)
