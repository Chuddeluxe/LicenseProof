# LicenseProof Studio-dev deployment forensics

Status: read-only forensic closure for the failed deployment. No transaction
was submitted during this pass.

## Canonical facts

- Frozen source SHA-256: `77fb66904787baab72210276f29d6c0cc29831e2d243cecad5c2eb249146c0c4`
- Network: `studio-dev`, chain `61997`
- Deployer: `0x33653e6e86807e41682d3346cdf648d6653384b1`
- Recovered known transaction: `0xc1d73935470d50f78338aea2fe4c151f1d4baffd98f60575a5c95fb59c99a799`
- Known transaction nonce: `12`
- Nonce advanced from `11` to `13`; this proves two sender submissions, but the
  nonce-11 hash is not recoverable from the currently exposed RPC methods or
  local journal evidence.

The raw transaction, receipt, lifecycle response, fee configuration, RPC
method probes, and derived comparison are in
`evidence/forensics/studio-dev-forensics.json`.

## Root cause: second broadcast

The former control flow was:

1. `main()` saw no deployment result and no hash in `deployment.jsonl`.
2. `LiveWriter.broadcast_once()` invoked `subprocess.Popen()` for the deploy
   command before writing any durable submission record.
3. The RC CLI printed the transaction label and hash on separate lines. The
   line-by-line parser did not recognize that output, so no hash was written.
4. The process was interrupted after the provider had accepted the first
   submission.
5. A later run took the same “no journal hash” branch and invoked the deploy
   command again, producing nonce 12.

This is a critical release blocker because an uncertain send must never be
treated as permission to submit another deployment.

## Fee root cause

The failed transaction used:

- `executionBudgetPerRound`: `76548000000000`
- `rotations`: `[0]`
- `receiptFeeMaxGasPrice`: `300000000`
- locked `receiptGasPrice`: `250000000`

The finalized receipt accounting measured a deploy receipt charge of
`78628000000000`, exceeding the submitted receipt capacity by
`2080000000000`. The chain surfaced this as `out_of receipt nondet_output`.
The receipt report records zero nondeterministic output bytes; the numeric
budget exhaustion is therefore the stronger classification.

The measured lower bound is `78628000000000`. The chain-provided post-failure
profile applies 20% padding:

```json
{
  "distribution": {
    "leaderTimeunitsAllocation": 100,
    "validatorTimeunitsAllocation": 200,
    "appealRounds": 0,
    "executionBudgetPerRound": 94353600000000,
    "executionConsumed": 0,
    "totalMessageFees": 0,
    "rotations": [0],
    "maxPriceGenPerTimeUnit": 2,
    "storageFeeMaxGasPrice": 300000000,
    "receiptFeeMaxGasPrice": 300000000
  },
  "feeValue": 94353600002588
}
```

The normal and corrected `gen_call` deploy probes both return `00`, even when
the fee profile is supplied. On this RC endpoint, that proves source parsing
and simulation acceptance but not parity with live fee enforcement.

## Corrective control

`LiveWriter.broadcast_once()` now:

- writes and fsyncs a `broadcast_started` journal record before `Popen()`;
- writes a separate durable intent record;
- persists the hash immediately when parsed;
- refuses to broadcast while any attempt or intent is unresolved;
- resumes by reconciling the same hash;
- leaves terminal failures terminal.

The regression tests in
`tests/harness/test_deployment_safety.py` cover normal submission, send-after-
broadcast exceptions, timeout/disconnect uncertainty, process restart,
missing journal with consumed nonce, and `FINISHED_WITH_ERROR`. Each case
asserts zero second broadcasts.

## Decision

`ROOT_CAUSE_VERIFIED = YES`.

`SAFE_REDEPLOYMENT_CANDIDATE = NO` for this workspace until the nonce-11
transaction is independently recovered or conclusively closed and a new
explicit deployment authorization is provided. No redeployment is authorized
by this forensic pass.
