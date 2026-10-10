> **VERSIONED RELEASE RECORD.** The v1.1.0 section below is current. The later v1.0.0 section is historical and intentionally preserves its original local-release wording; do not interpret those historical "not deployed" or "not pushed" statements as v1.1 status.

# Current v1.1.0 release status

LicenseProof v1.1.0 is verified on Studio-dev chain `61997`.

- Contract: `0x18A850BB8cA6cb0F75a5A9ab95362c12f1E349e6`
- Deployment transaction: `0x0d81881d71a362033fa075780d6b6b5ea90c20251fcce952772f863561db5ca1`
- Contract source SHA-256: `354f840a54e57a215790fa70182938ade78f43b505bcf05f8ded37cd4c1135fd`
- Version: `1.1.0`
- Semantic schema: `licenseproof.semantic.v1.1` (17 strict booleans)
- Public methods: 28; source/schema parity PASS
- Live qualification: MIT `COMPATIBLE_WITH_OBLIGATIONS`; Elastic-2.0 `INCOMPATIBLE`; AGPL-3.0-only `INCONCLUSIVE`
- Deployment/qualification nonce window: 42–66, 25 transactions, 24 successful and one terminal technical semantic failure; all nonces explained
- Current audit: Critical 0, High 0, Medium 0

The v1.1 Portal submission package is prepared locally, but no Portal
submission is claimed without authenticated Portal confirmation.

# Historical v1.0.0 release-candidate status

## Frozen artifact

- Contract: `contracts/LicenseProof.py`
- Version: `1.0.0`
- Contract SHA-256: `77fb66904787baab72210276f29d6c0cc29831e2d243cecad5c2eb249146c0c4`
- Runner: `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`
- Semantic schema: `licenseproof.semantic.v1`
- Public methods: 26

The contract source remained byte-identical throughout deployment and live
qualification.

## Runtime and deployment

Studio-dev chain identity was verified as 61997. The corrected deployment
used the proven full fee profile from the qualified 5jyc deployments, finalized
successfully, and returned contract address
`0x27Ca7E9F92AB0e465420AA9F2583fB25c9355619`.

The direct SDK harness persists a pre-broadcast intent, signs and broadcasts
once, fsyncs the returned hash immediately, reconciles that same hash, and
stops on terminal failure. It does not parse CLI stdout and has no automatic
deployment retry.

## Qualification

The live MIT, Elastic-2.0, and AGPL-3.0-only cases were finalized with the
expected results. One Case C consensus disagreement was retried once under
the frozen identity and liveness rule. The failed transaction and retry are
both retained in the case journal.

## Gates

- Full local suite: 63 passed
- Harness suite: 10 passed
- Direct: 9 passed
- Adversarial: 16 passed
- Property: 4 passed
- Semantic: 5 passed
- Mutation audit: 24/24 killed
- Schema/interface parity: PASS
- Deployed source parity: PASS
- Secret scan: PASS; no material secret, only the expected WinCred symbol
- Current audit: Critical 0, High 0, Medium 0, Low 0

The installed `genvm-linter` is 0.11.1rc2. Its direct invocation reports the
two known E010 call-graph false positives around the bounded nondeterministic
evaluation boundary; no new linter diagnostic was introduced.

The earlier default-fee preflight failure, HTTP 429 preflight interruption,
and Case C consensus disagreement are preserved as operational history and
are not current release blockers.

## Decision

`LIVE_QUALIFICATION = VERIFIED`

`READY_FOR_PUBLIC_RELEASE = YES`

This is a local provenance checkpoint only. No GitHub repository was created,
no push was performed, and no further deployment is authorized by this record.
