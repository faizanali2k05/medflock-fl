import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile

parser = argparse.ArgumentParser(description="Acquire the public UCI 519 research CSV locally")
parser.add_argument("--source", type=Path)
args = parser.parse_args()
destination = Path("data/heart_failure.csv")
destination.parent.mkdir(exist_ok=True)
if args.source:
    contents = args.source.read_bytes()
else:
    archive = Path("data/uci519.zip")
    urlretrieve(
        "https://archive.ics.uci.edu/static/public/519/heart+failure+clinical+records.zip",
        archive,
    )
    with ZipFile(archive) as bundle:
        contents = bundle.read("heart_failure_clinical_records_dataset.csv")
digest = hashlib.sha256(contents).hexdigest()
expected = "9c73cea7468ff5d517801ec050fe9993da5912fce4b56f296f8df3b38dd75912"
if digest != expected:
    raise ValueError("Source differs from the pinned UCI snapshot; review provenance before intake")
pending = destination.with_suffix(".pending.csv")
pending.write_bytes(contents)
pending.replace(destination)
manifest = {
    "source": "https://archive.ics.uci.edu/dataset/519/heart+failure+clinical+records",
    "license": "CC BY 4.0",
    "doi": "10.24432/C5Z89R",
    "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    "use": "Research only; no prescription labels or verified hospital IDs",
}
Path("data/source.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
