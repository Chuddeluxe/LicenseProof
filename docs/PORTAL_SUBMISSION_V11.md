# GenLayer Portal submission package — LicenseProof v1.1.0

Status: **PREPARED LOCALLY — NOT SUBMITTED**

This package contains the values to submit after an authenticated Portal
session. It is not a Portal receipt and does not claim submission.

## Contract submission fields

```text
Project: LicenseProof
Version: 1.1.0
Network: Studio-dev
Chain ID: 61997
Contract address: 0x18A850BB8cA6cb0F75a5A9ab95362c12f1E349e6
Deployment transaction: 0x0d81881d71a362033fa075780d6b6b5ea90c20251fcce952772f863561db5ca1
Contract source SHA-256: 354f840a54e57a215790fa70182938ade78f43b505bcf05f8ded37cd4c1135fd
Runner: py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng
Public methods: 28
Semantic schema: licenseproof.semantic.v1.1
```

## Proof package

- Deployment/source/schema proof: `docs/LIVE_DEPLOYMENT_V11.md`.
- Live qualification proof: `docs/LIVE_QUALIFICATION_V11.md`.
- Machine-readable journals and canonical readback: `evidence/qualification/v1.1/`.
- MIT: `COMPATIBLE_WITH_OBLIGATIONS`; review key
  `c75a083826ab8d28ac3358ecf7a7e6f4d10b071a8b923baa0ee8c156bc4c3b21`.
- Elastic-2.0: `INCOMPATIBLE`; review key
  `18548d2f1b3a67fb5857db757337effacdb6307713bf3d8648accf319084b004`.
- AGPL-3.0-only: `INCONCLUSIVE`; review key
  `e7cdff6841629a84efac55ea7ee6a1ef45ea375a8637cbd2cca3db2ddefb3e66`.
- SPDX commit: `31ba1a50e5397e00a304dbadc76531740e89ee48`.

## Submission control

```text
PORTAL_SUBMISSION_ATTEMPTED = NO
PORTAL_SUBMISSION_CONFIRMED = NO
PORTAL_CONFIRMATION_ID = NONE
```

Do not change these fields without an authenticated Portal response. A public
GitHub release or an on-chain deployment is not itself Portal confirmation.

