# LicenseProof Studio-dev deployment record

Status: **BLOCKED — deployment execution failed.**

The frozen source was preflighted successfully against Studio-dev (chain 61997):
remote source schema 26/26, local schema/interface parity, and read-only
`gen_call` deploy simulation `00`. The actual deployment did not satisfy the
success criteria.

Captured transaction:

- Hash: `0xc1d73935470d50f78338aea2fe4c151f1d4baffd98f60575a5c95fb59c99a799`
- Nonce: 12
- Finality: `FINALIZED`, outcome `accepted`
- Execution: `ERROR` / CLI `FINISHED_WITH_ERROR`
- Node detail: `out_of receipt nondet_output`; validator quorum was reached
- Observed transaction data contract address: `0x665F21cD9c8e0d12aAa2773840293152CBEC7C54`

The observed address is not treated as a deployed LicenseProof contract because
execution failed. No contract readback, policy write, manifest write, evidence
commit, semantic adjudication, or qualification write was attempted.

The first corrected CLI invocation exited after emitting a deployment result but
before the harness captured its multiline hash. The account nonce moved from the
preflight value 11 to 13, while the captured transaction is nonce 12. Therefore
one earlier deployment transaction (inferred nonce 11) is unexplained and its
hash could not be recovered from the exposed RPC history. This is recorded as a
release blocker; no further reconciliation or deployment was attempted.

Raw transaction and reconciliation evidence is preserved in
`evidence/qualification/deployment.jsonl` and
`evidence/qualification/deployment-failure.json`.

No redeployment is authorized or performed after the terminal failure.
