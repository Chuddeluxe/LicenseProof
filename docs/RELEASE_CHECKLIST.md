# LicenseProof release checklist — verified releases

The v1.0.0 entries below are historical and immutable. The current v1.1.0
entries are recorded separately and do not rewrite v1.0.0.

## v1.0.0 historical release

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

See `docs/LIVE_QUALIFICATION.md`, `docs/DEPLOYMENT_FORENSICS.md`, and
`docs/RELEASE_CANDIDATE.md` for historical live qualification evidence and
exceptions. The v1.0.0 tag remains historical and immutable.

## v1.1.0 current release

- [x] v1.1.0 source, schema, and runner gates passed on the hardening branch.
- [x] v1.1.0 deployed once to Studio-dev chain 61997.
- [x] v1.1.0 deployment finalized successfully with exact source parity.
- [x] MIT, Elastic-2.0, and AGPL-3.0-only v1.1 cases have separate canonical qualification evidence.
- [x] The one technical Case B semantic failure and one same-identity retry are preserved; no result shopping occurred.
- [x] Exact-head v1.1 CI passed after the provenance and secret-scan fixes.

**v1.1.0 contract:** `0x18A850BB8cA6cb0F75a5A9ab95362c12f1E349e6`.

**v1.1.0 deployment:** `0x0d81881d71a362033fa075780d6b6b5ea90c20251fcce952772f863561db5ca1`.

**v1.1.0 source SHA-256:** `354f840a54e57a215790fa70182938ade78f43b505bcf05f8ded37cd4c1135fd`.

See `docs/LIVE_DEPLOYMENT_V11.md`, `docs/LIVE_QUALIFICATION_V11.md`, and
`evidence/qualification/v1.1/`. The Portal package is prepared locally but no
Portal submission is claimed without authenticated confirmation.

