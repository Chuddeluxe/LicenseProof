# LicenseProof live qualification record

Status: **NOT QUALIFIED.**

The qualification run stopped at deployment execution failure. The single
qualification policy was not created, and no live policy, manifest, component,
license evidence, review, or final-result write was broadcast.

The three approved cases therefore remain unqualified:

| Case | Evidence fetched locally | On-chain evidence committed | Result |
| --- | --- | --- | --- |
| A — MIT | Yes | No | NOT RUN |
| B — Elastic-2.0 | Yes | No | NOT RUN |
| C — AGPL-3.0-only | Yes | No | NOT RUN |

Pinned SPDX provenance was resolved at commit
`31ba1a50e5397e00a304dbadc76531740e89ee48` and each license was fetched twice
with identical bytes. The exact URL, SHA-256, and byte length records are in
`evidence/qualification/spdx-provenance.json`.

There are no live replay-guard, policy-immutability, manifest-immutability, or
semantic-result claims because no qualification contract existed to read back.
Technical deployment failure is kept separate from business compatibility
results; no case is reported as compatible or incompatible.
