import numpy as np
import pandas as pd
import pytest

from medflock.task import FEATURES


@pytest.fixture
def dataset(tmp_path):
    rng = np.random.default_rng(17)
    records = []
    for index in range(80):
        values = [
            40 + index / 2,
            index % 2,
            100 + index,
            (index // 2) % 2,
            20 + index % 30,
            index % 2,
            200000 + index,
            0.8 + rng.random(),
            130 + index % 10,
            index % 2,
            (index // 3) % 2,
        ]
        records.append(
            dict(
                zip(FEATURES, values),
                time=60 if index % 3 == 0 else 120,
                DEATH_EVENT=int(index % 3 == 0),
            )
        )
    path = tmp_path / "synthetic.csv"
    pd.DataFrame(records).to_csv(path, index=False)
    return path
