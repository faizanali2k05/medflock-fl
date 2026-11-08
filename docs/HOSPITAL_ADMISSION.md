# Hospital admission and training boundary

Hospital participation has distinct states: application pending, manually approved account, transport identity bound, authenticated runner connected, eligible for a training round, and accepted contribution. Neither approval nor a heartbeat proves the later states.

The sign-in page now offers **Request hospital access**. Applications collect institution/contact information, authority acknowledgements and requested account credentials. Passwords are hashed; the account starts disabled. No patient data belongs in an application. Administrators review applications in **Administration → Hospitals**, record their independent verification reference and approve or reject. Approval atomically enables the hospital account and creates a suspended external node. Repeated decisions are rejected. Rejected applications do not enable accounts.

Hospital accounts can access their assigned node and their own synthetic case workspace. They cannot read global datasets, training runs, other users' cases or administration. Institutional approval does not confer the separate clinician evaluation-signoff role. Current clinical service remains an unvalidated synthetic-case pilot.

## Runner enrollment

A hospital needs a compatible local computer, not a VPS. Patient datasets stay on that computer. Training hardware depends on the model: the existing tabular task can run on CPU; full MedGemma training has substantially different requirements. A browser session alone cannot perform the existing Python Flower training workflow.

1. Independently verify institutional authority, data permissions and the intended task.
2. Provision the hospital-controlled runner using `deploy/hospital/compose.yaml`; review `LOCAL_NODE_WORKFLOW.md` for local mapping and validation. Do not upload its patient CSV to the central portal.
3. Register its public key with the pinned Flower 1.39.0 SuperLink using the authenticated registration procedure already exercised by `scripts/flower_spike.py`. The private key remains on the hospital runner. Obtain and independently verify the assigned Flower node ID and public-key fingerprint.
4. In **Administration → Clients → Bind a verified Flower identity**, record the assigned ID, fingerprint and verification reference. This records the administrator's verification; the API itself does not contact SuperLink or attest a live connection. Each hospital and Flower ID can have only one binding through this API. Key rotation/rebinding is not yet supported.
5. Activate the hospital participation policy only after successful enrollment and local dataset validation.
6. Start the ServerApp with `hospital-mode=true`, a reviewed `server-manifest`, and a coordinator-side database connection to the same MedFlock registry. The coordinator needs read access to `node_registry` and `snapshots`; never distribute this database credential to hospital runners. Existing isolated coordinator compose still needs this connection and network provisioning before a real run. Do not treat this as already deployed.

## Enforcement implemented

`HospitalFedAvg` intersects connected Flower identities with registered external nodes that are currently active. Unknown, unbound, paused, restricted, suspended and revoked identities receive no training request. It rechecks policy at aggregation, so a reply arriving after suspension does not enter the global model. Duplicate senders, unexpected records or metrics, invalid sample counts, mismatched array shapes and nonfinite weights cannot satisfy the required contribution count. Insufficient participants or valid replies fail the round without promoting new global weights. Database failures also fail the round.

Only model arrays and the currently approved `num-examples` metric are accepted by this strategy. The local client reads prepared local arrays and returns these records, not patient rows. Model updates can still leak information; this is not a differential-privacy guarantee, poisoning defense or secure aggregation implementation. Training already running on a hospital machine is not remotely killed by a portal pause; the coordinator rejects its subsequent contribution. Changes occurring after the aggregation eligibility snapshot take effect at the next boundary.

The default Flower configuration remains the explicitly synthetic transport spike (`hospital-mode=false`). Production hospital orchestration must enforce hospital mode; it must not launch the synthetic configuration. Current application deployment does not yet launch or supervise hospital rounds. The policy strategy has tests against pinned Flower message objects, but these are not evidence of an independent hospital connection.

## Remaining integration

- Provision and verify the authenticated coordinator endpoint without disturbing existing VPS services.
- Exercise enrollment and a complete training round with a real authorized hospital runner, including pause/revocation during a round.
- Provide local runner installation and dataset mapping UI, versioned dataset approval, and meaningful round progress in the hospital workspace.
- Connect accepted rounds to the model registry, evaluation and release workflow.
- Add credential rotation, connection evidence, recovery and operational monitoring before claiming deployable hospital federation.

Treatment recommendations remain a required product capability. Neither the new hospital role nor teacher prompt enables validated medication recommendations: reliable adopted sources, interaction checks, reviewed evaluation and the runtime treatment flow remain unfinished. See `training/cardiology/CORPUS_GENERATION_PROMPT.md` for the external teacher drafting format and its review requirements.
