# Hospital-local preparation and participation

The client portal shows only the signed-in account's assigned node. Administrator
policies allow participation, pause training, restrict participation, suspend
indefinitely, suspend for one hour, or revoke access. Timed suspension restores
the prior policy; it does not automatically activate a previously restricted node.
Revocation disables assigned accounts and sessions and cannot be undone through
the policy selector. Register a new identity to re-enroll a revoked node.

The simulation worker checks eligibility before local training. These controls do
not stop a remote process or secure an independently launched Flower deployment.
Hospital transport enrollment and policy enforcement at that boundary remain
unfinished. The portal states this explicitly; registration and heartbeat are
not evidence that a hospital is connected.

## Different local dataset structures

`scripts/prepare_hospital_node.py` accepts `--mapping local-mapping.json` in addition
to the dataset, coordinator specification, output directory and permission reference.
Run it on the hospital machine. It performs no network requests. The mapping binds
to the exact task-contract digest and contains a reviewer and review reference.
Each required target column specifies its source column, source unit, target unit,
and either an explicit numerical scale/offset or categorical 0/1 codes. Patient
group identifiers are retained as strings. Unmapped categories, missing columns,
wrong target units and reuse of a source column are rejected. Extra source columns
are excluded. The normal task checks then validate labels, ranges and splitting.

Example column entry:

```json
{"source": "local_measurement", "source_unit": "mg/L", "target_unit": "mg/dL", "scale": 0.1}
```

Conversions must be reviewed locally. The software does not infer semantic
equivalence from matching names or guess diagnoses from free text. The mapping and
source provenance remain in the local output directory, alongside local partitions.
Protect that directory as hospital data; it is not an upload bundle.

The intended exchange is coordinator model/configuration to node, local training
and evaluation, model updates and approved aggregate metrics to coordinator, then
an evaluated global model back to nodes. Raw records are not required by this
exchange. Model updates can still leak information; weights-only exchange alone is
not a privacy guarantee. Different tasks or incompatible model structures require
different contracts and cannot be averaged together.

The current local preparation runner supports the logistic task specification.
It is not a generic image, ECG or MedGemma federated trainer. An authenticated
hospital pilot and end-to-end transport testing remain required.
