# VPS deployment verification

Verified on 21 October 2026 (Asia/Karachi), with application image commit
`b7f7b817c4ee6b36c61abf34d15bd7f583d36d9e`.

Endpoint: https://31.97.50.29:18443. Administrator: `dustyShards`.
Use the separately supplied password, then change it through Account.

The IP certificate is self-signed. Its SHA-256 fingerprint is:

```
7A:20:19:F9:70:27:01:91:21:12:97:41:8B:9D:06:53:31:AF:F1:D6:7A:1B:AC:84:17:D3:E9:14:22:F0:E7:FC
```

## Checks performed

- Public HTTPS returned the frontend successfully using certificate verification
  against the certificate obtained over the established SSH connection.
- Anonymous administrator access returned 401. Authenticated mutation without
  CSRF returned 403. Login and logout returned 200.
- `/.env` and `/.git/config` returned 403. Deployment environment permissions
  are 0600; temporary registry credentials were removed after image acquisition.
- The bundled corpus imported 300 unreviewed synthetic drafts: 160 training,
  65 validation and 75 test examples. Import does not authorize training.
- The private quantized MedGemma runtime was healthy. A synthetic missing-data
  prompt returned a complete 12-token answer through the authenticated public
  API in 8.91 seconds. This single smoke test is not a latency benchmark or
  clinical evaluation. An earlier 64-token request produced truncated analysis;
  broader response-quality testing remains necessary.
- A two-round, three-client tabular experiment completed through the deployed
  queue and worker, reporting centralized, local-only and simulated FedAvg
  results. Run ID: `e38815df3e204705897d314bb85833bf`.
- All pre-existing container IDs remained present and running, with uptime
  continuing from the deployment snapshot. No unrelated service was restarted
  or configured. This is container continuity evidence, not an application-level
  test of the other clients' services.
- MedFlock has five isolated Compose services with aggregate limits of two CPU
  cores and 6016 MiB RAM. API diagnostics bind loopback; database and inference
  have no published host ports.

The release passed 43 backend and two frontend tests, frontend compilation,
linting, and GitHub/GitLab CI before deployment. Browser automation encountered
a Firefox navigation error; visual verification of the public deployment is
not claimed. HTTP, authentication, corpus and inference checks used the public
HTTPS endpoint with certificate verification enabled.

## Remaining boundaries

The dashboard manages node registration and account permissions; it does not
install a remote Flower process. Corpus upload is versioned storage, not a
training trigger. Full-weight MedGemma distillation still requires suitable
compute and reviewed examples. Clinical validation, validated prescribing,
actual hospital pilots, automated host deployment and a backup restore drill
remain unfinished. The deployed model supports research text inference only.
