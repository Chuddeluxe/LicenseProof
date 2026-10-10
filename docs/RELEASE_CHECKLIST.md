# LicenseProof release checklist — current verified v1.0.0

- [x] Contract source uses qualified pinned 5j runner.
- [x] Policy, manifest, evidence, review, finalization, and audit controls are deterministic.
- [x] Semantic vector is exact, boolean, and JSON-only.
- [x] Validator independently reruns evidence retrieval and semantic evaluation.
- [x] Direct, adversarial, property, semantic, harness, and mutation gates passed in release CI.
- [x] Schema/interface method parity and frozen source parity passed.
- [x] Qualified contract deployed to Studio-dev chain 61997.
- [x] Canonical deployment execution finalized successfully and deployed source matched the frozen SHA-256.
- [x] MIT, Elastic-2.0, and AGPL-3.0-only cases reached successful canonical results; failed Case C consensus attempt and authorized retry are preserved.
- [x] Main commit `1abde6b6e2d1396c96942767a04a4154f6b0103d` passed exact-head GitHub CI run `38033403915`.
- [x] v1.0.0 annotated release tag points to that commit.

**Canonical deployment:** `0x27Ca7E9F92AB0e465420AA9F2583fB25c9355619`.

**Deployment transaction:** `0xa3eeeb8156ee3b6317b77beeb73ba7d3196b0f4d30830ef0de97c82f4407de03`.

**Contract source SHA-256:** `77fb66904787baab72210276f29d6c0cc29831e2d243cecad5c2eb249146c0c4`.

See `docs/LIVE_QUALIFICATION.md`, `docs/DEPLOYMENT_FORENSICS.md`, and `docs/RELEASE_CANDIDATE.md` for live qualification evidence and historical exceptions.

This checklist corrects the superseded pre-deployment note that said no deployment was performed. The v1.0.0 tag remains historical and immutable. Any newer main commit requires its own CI check before claiming exact-head parity.
