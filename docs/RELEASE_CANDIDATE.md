# LicenseProof release-candidate status

## Frozen artifact

- Contract: `contracts/LicenseProof.py`
- Version: `1.0.0`
- Contract SHA-256: `77fb66904787baab72210276f29d6c0cc29831e2d243cecad5c2eb249146c0c4`
- Runner: `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`
- Semantic schema: `licenseproof.semantic.v1`
- Public methods: 26

The contract source was not modified during the live pass.

## Gates

Local direct, adversarial, property, semantic, and mutation tests passed:
53 tests passed and 24/24 named mutants were killed. Local schema/interface
parity passed. The Studio-dev read-only source-schema probe passed 26/26 and
the read-only deploy simulation returned `00`.

The actual deployment finalized with execution error, so deployed source parity,
deployed contract information, live policy qualification, replay guards, and
public-release readiness are not established.

The RC linter reports E010 at the two bounded `gl.nondet` call sites. This is a
known static call-graph false positive for the qualified GenLayer runtime
boundary; it was recorded and not suppressed by changing the contract.

## Decision

`LIVE_QUALIFICATION = NOT VERIFIED`

`READY_FOR_PUBLIC_RELEASE = NO`

The terminal deployment failure and one unreconciled earlier nonce are blockers.
No automatic retry or redeployment is permitted by the live authorization.
