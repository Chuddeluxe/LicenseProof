# LicenseProof live qualification record

Status: VERIFIED on Studio-dev.

One frozen policy was used for all three approved cases:

- Policy ID: `LP-LIVE-POLICY-20261009T235554Z`
- Policy hash: `5186010712e61154134377dc0b566b529cfea5c1a0152c974f8fc2e0fe43a8b0`
- State: FROZEN
- Intent: commercial hosted proprietary SaaS with modification enabled

Pinned SPDX evidence used commit
`31ba1a50e5397e00a304dbadc76531740e89ee48`. Each source was fetched twice,
decoded as UTF-8, and matched its committed SHA-256 and byte length.

| Case | Manifest | Semantic result | Manifest result |
| --- | --- | --- | --- |
| A - MIT | `LP-LIVE-A-20261009T235554Z` | COMPATIBLE_WITH_OBLIGATIONS | COMPATIBLE_WITH_OBLIGATIONS |
| B - Elastic-2.0 | `LP-LIVE-B-20261009T235554Z` | INCOMPATIBLE | INCOMPATIBLE |
| C - AGPL-3.0-only | `LP-LIVE-C-20261009T235554Z` | INCOMPATIBLE | INCOMPATIBLE |

Case A recognized commercial use, hosted service, and modification as
permitted, with attribution and notice preservation obligations.

Case B recognized `hosted_service_permitted=false`; the deterministic policy
rule derived INCOMPATIBLE.

Case C recognized `network_source_disclosure_required=true`; the frozen
proprietary hosted-only policy therefore derived INCOMPATIBLE.

Case C had one finalized but undetermined consensus attempt at nonce 39 due to
validator disagreement. The canonical review was absent, the frozen identity
was unchanged, and the single authorized semantic retry at nonce 40 succeeded.
The failed attempt remains preserved and was never treated as a business
verdict.

Read-only replay simulations rejected duplicate adjudication for all three
cases. Read-only mutation simulations rejected frozen-policy mutation,
adding to a finalized manifest, and repeat finalization. No duplicate
qualification writes were broadcast.

Full provenance is in `evidence/qualification/summary.json`, the three case
JSONL journals, and `evidence/qualification/readonly-proofs.json`.

## Final nonce reconciliation

The deployer account advanced from nonce 14 to nonce 42, so the inclusive
window contains 28 recovered chain transactions (14 through 41). The ledger
contains 25 LicenseProof transactions and 24 qualification transactions after
excluding the deployment. Three additional finalized transactions belong to
other projects using the same account: the RightsRail deployment at nonce 14
and `policy-lumen-finch-001` policy operations at nonces 23 and 24. One
LicenseProof transaction, Case C adjudication at nonce 39, finalized without a
successful review because of consensus disagreement; it was followed by the
single authorized retry at nonce 40. Thus 27 transactions succeeded and one
was a technical/consensus failure, with all 28 nonces accounted for.

The canonical Case C review key is
`cf10789b6fa19ddf3fe96c6d6d0af548926df2f109b23027822e27509d3a8808`.
