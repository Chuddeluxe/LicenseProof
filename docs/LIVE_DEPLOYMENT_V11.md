# LicenseProof v1.1.0 — Studio-dev deployment record

Status: **FINALIZED / SUCCESS**

This record is the v1.1 deployment provenance. It does not replace or rewrite
the historical v1.0.0 deployment record.

## Artifact and network

| Field | Value |
| --- | --- |
| Network | Studio-dev |
| Chain ID | `61997` |
| RPC | `https://studio-dev.genlayer.com/api` |
| Contract | `0x18A850BB8cA6cb0F75a5A9ab95362c12f1E349e6` |
| Deployment transaction | `0x0d81881d71a362033fa075780d6b6b5ea90c20251fcce952772f863561db5ca1` |
| Source | `contracts/LicenseProof.py` |
| Canonical source SHA-256 | `354f840a54e57a215790fa70182938ade78f43b505bcf05f8ded37cd4c1135fd` |
| Version | `1.1.0` |
| Semantic schema | `licenseproof.semantic.v1.1` |
| Runner | `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` |
| Public methods | `28` |
| Source parity | PASS |
| Schema parity | PASS |

The deployed source was independently read back and hashed from the chain. The
deployed schema contains 28 methods and `contract_info` reports version
`1.1.0`, semantic schema `licenseproof.semantic.v1.1`, and the expected runner.

## Deployment envelope

The proven Studio-dev profile was used in full:

```text
leaderTimeunitsAllocation = 100
validatorTimeunitsAllocation = 200
appealRounds = 0
executionBudgetPerRound = 25000000000000000
executionConsumed = 0
totalMessageFees = 0
rotations = [3]
maxPriceGenPerTimeUnit = 2
storageFeeMaxGasPrice = 300000000
receiptFeeMaxGasPrice = 300000000
feeValue = 100000000000010352
```

The direct SDK sender persisted the deployment intent before broadcast, made one
submission, persisted the returned hash immediately, and reconciled that same
hash through finality and execution. No second deployment was attempted.

## Nonce accounting

The v1.1 deployment and qualification window began at nonce 42 and ended with
latest/pending nonce 67/67. Nonces 42 through 66 are all represented by durable
intent records in `evidence/qualification/v1.1/` and summarized in
`summary.json`:

- 42: deployment;
- 43–44: policy creation and freeze;
- 45–51: Case A manifest, component, evidence, freeze, review start,
  adjudication, and finalization;
- 52–59: Case B lifecycle, one failed technical adjudication at 57, one
  same-identity retry at 58, and finalization;
- 60–66: Case C lifecycle through finalization.

There were 25 chain transactions: 24 successful and one terminal technical
semantic failure. `UNEXPLAINED_TRANSACTIONS=0`, `BLIND_REBROADCASTS=0`, and
`SECOND_DEPLOYMENT=NO`.

## Historical incident boundary

Earlier v1.1 deployment attempts used an underfunded receipt budget and a CLI
stdout/hash-capture pattern that could lose a hash after broadcast. The contract
source was not changed to address those operational defects. The hardened
direct-SDK sender and the proven full fee profile were adopted before this
deployment; the successful v1.1 deployment above was broadcast exactly once.

The prior v1.0.0 deployment and its evidence remain historical and unchanged.

