# LicenseProof release-candidate status

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
