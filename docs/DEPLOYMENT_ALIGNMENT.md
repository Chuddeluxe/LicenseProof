# LicenseProof deployment alignment

Status: corrected deployment candidate prepared locally; no transaction was
broadcast in this pass.

## Frozen source

- Contract: `contracts/LicenseProof.py`
- SHA-256: `77fb66904787baab72210276f29d6c0cc29831e2d243cecad5c2eb249146c0c4`
- Runner: `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`

The contract, schema, ABI, semantic prompt, and runtime code were not changed.

## Reference implementations inspected

The alignment was based on implementation and provenance files, not only on
their documentation:

- Procura direct SDK qualification: `C:\Users\DELL\Procura\scripts\qualification\studio_live_qualification.py`
- Procura Deployment #6: `C:\Users\DELL\Procura\evidence\qualification\current\_deployment6.jsonl`
- CharterLock one-shot/recovery: `C:\Users\DELL\CHARTERLOCK\scripts\live_write_once.mjs` and `reconcile_live_tx.mjs`
- DriftProof fee/deployment provenance: `C:\Users\DELL\DriftProof\docs\provenance\STUDIO_DEV_DEPLOYMENT.md`
- ClearLC Deployment #4 fee evidence: `C:\Users\DELL\ClearLC\artifacts\studio-dev-qualification-deployment4.json`

The corrected LicenseProof sender uses genlayer-py’s installed calldata,
fee-normalization, ABI encoding, gas-estimation, and signing primitives. It
does not use the CLI or parse human-readable stdout.

## Proven Studio-dev deployment profile

| Field | Proven value |
| --- | ---: |
| leaderTimeunitsAllocation | 100 |
| validatorTimeunitsAllocation | 200 |
| appealRounds | 0 |
| executionBudgetPerRound | 25000000000000000 |
| executionConsumed | 0 |
| totalMessageFees | 0 |
| rotations | `[3]` |
| maxPriceGenPerTimeUnit | 2 |
| storageFeeMaxGasPrice | 300000000 |
| receiptFeeMaxGasPrice | 300000000 |
| feeValue | 100000000000010352 |

The failed LicenseProof attempt used `executionBudgetPerRound=76548000000000`;
the measured receipt requirement was `78628000000000`, leaving a deficit of
`2080000000000`. The corrected request never uses either that value or the
narrowly padded `94353600000000` value.

## Transaction safety

The corrected sender persists a complete deployment intent before the provider
can see the signed raw transaction. The intent includes the sender, reserved
nonce, frozen source hash, serialized deployment hash, encoded calldata hash,
complete fee distribution, and fee value. The provider is called exactly once.
The returned EVM hash is fsynced immediately and is the only hash used for
subsequent receipt/event recovery. An exception, timeout, disconnect, missing
local journal, or terminal execution error is a stop condition; it cannot
trigger a second deployment.

The prior CLI stdout parser and its `Popen` broadcast path were removed from
`scripts/studio_live_qualification.py`. That compatibility module now refuses
legacy live writes and directs callers to the direct sender in
`scripts/studio_deploy_harness.py`.

## Read-only Studio-dev evidence

- `evidence/predeploy/corrected-deployment-request.json` contains the exact
  unsigned EVM request built for the current sender and nonce using the proven
  profile.
- `evidence/predeploy/corrected-gen-call-deploy.json` records a read-only
  `gen_call` with the complete corrected fee object and result `00`.

The remote chain check returned `61997`, source schema returned 26 methods,
and the corrected full-fee deploy simulation returned `00`. No signer was
loaded, no transaction was signed for submission, and no broadcast occurred.
