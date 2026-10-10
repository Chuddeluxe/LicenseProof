# LicenseProof Studio-dev deployment record

Status: SUCCESSFUL on Studio-dev chain 61997.

The exact frozen contract source was deployed once with the proven Studio-dev
5jyc fee profile.

- Contract: `0x27Ca7E9F92AB0e465420AA9F2583fB25c9355619`
- Deployment transaction: `0xa3eeeb8156ee3b6317b77beeb73ba7d3196b0f4d30830ef0de97c82f4407de03`
- Deployer nonce: 15
- Finality: FINALIZED / ACCEPTED
- Execution: SUCCESS
- Source SHA-256: `77fb66904787baab72210276f29d6c0cc29831e2d243cecad5c2eb249146c0c4`
- Deployed source SHA-256: exact match
- Deployed schema: 26 methods, exact local schema/interface parity
- Contract info: version `1.0.0`, semantic schema `licenseproof.semantic.v1`

Deployment profile:

```text
leaderTimeunitsAllocation=100
validatorTimeunitsAllocation=200
appealRounds=0
executionBudgetPerRound=25000000000000000
executionConsumed=0
totalMessageFees=0
rotations=[3]
maxPriceGenPerTimeUnit=2
storageFeeMaxGasPrice=300000000
receiptFeeMaxGasPrice=300000000
feeValue=100000000000010352
```

The durable deployment intent was fsynced before the single broadcast, and the
returned hash was persisted before reconciliation. No CLI stdout parsing was
used and no second deployment was attempted.

Historical failed deployment evidence remains preserved in
`evidence/qualification/deployment-failure.json` and the append-only
`evidence/qualification/deployment.jsonl`. Those earlier failures used a
minimal receipt budget and are not part of this successful deployment.
