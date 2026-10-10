# LicenseProof v1.1.0 — live qualification record

Status: **VERIFIED**

The qualification was performed against the v1.1 contract at
`0x18A850BB8cA6cb0F75a5A9ab95362c12f1E349e6` on Studio-dev chain `61997`.
It is separate from the historical v1.0.0 qualification.

## Frozen policy

| Field | Value |
| --- | --- |
| Policy ID | `LP-V11-POLICY-20261010T104217Z` |
| Policy hash | `78f93851bc2b29d428bb81f69945f6c745a21d6f6101da10b5acbe723a79a134` |
| State | `FROZEN` |
| Commercial use | true |
| Hosted service | true |
| Modification | true |
| Source model | `PROPRIETARY` |
| Distribution model | `HOSTED_ONLY` |

The policy was created at transaction
`0x7aa11fcb736b5f40350861278418a0f04ebfddeb95dcdcae90dd0a0803d29b51` and
frozen at `0x77805526a2d4b07e60e5e19aa5cf478400efcaa237b09d6eaa64b32743e6f612`.

Evidence is pinned to SPDX `license-list-data` commit
`31ba1a50e5397e00a304dbadc76531740e89ee48` at
`raw.githubusercontent.com`, under the frozen commit path prefix. The committed
byte hashes and lengths below were verified by repeated retrieval.

## Canonical cases

### Case A — MIT

- Manifest: `LP-V11-A-20261010T104217Z`
- Component: `licenseproof-case-a`
- Evidence: `LP-V11-EVIDENCE-A`
- Evidence SHA-256: `b05785f9f18e6716bab63424b11454513b9943a222595b70411009202fc592b5`
- Evidence bytes: `1078`
- Review key: `c75a083826ab8d28ac3358ecf7a7e6f4d10b071a8b923baa0ee8c156bc4c3b21`
- Adjudication transaction: `0xe8728fac4c5947ac45e0be2c43265e3c07752b125d584d9e234071bd3082845f`
- Component and manifest result: `COMPATIBLE_WITH_OBLIGATIONS`

The canonical 17-boolean vector included commercial use, hosted service,
modification, attribution, notice preservation, and evidence sufficiency as
true. `applicability_clear=true`.

### Case B — Elastic-2.0

- Manifest: `LP-V11-B-20261010T104217Z`
- Component: `licenseproof-case-b`
- Evidence: `LP-V11-EVIDENCE-B`
- Evidence SHA-256: `6448026f2e06ab3da9ed8ddda686694bba37179e88db92dea6d4aab516c957ea`
- Evidence bytes: `3802`
- Review key: `18548d2f1b3a67fb5857db757337effacdb6307713bf3d8648accf319084b004`
- Successful adjudication transaction: `0x3f209f2369a6dc783ff32d3003742d4fe2e72054cada73a61913a9538b1865e1`
- Component and manifest result: `INCOMPATIBLE`

The canonical vector included `hosted_service_permitted=false`,
`evidence_sufficient=true`, `applicability_clear=true`, and the field-use
conflict fact. The deterministic result followed the hosted-service restriction
under the frozen policy.

The first adjudication transaction,
`0x06395c669605f5140fbb158ec4c05b28ff26a59af38e27906f6500b6c1238efe`, ended
in a terminal technical consensus outcome with no canonical review. The policy,
manifest, component, evidence, and review identity were re-read and unchanged;
the replay guard was unused. Exactly one same-identity retry was then submitted
and succeeded. This was liveness recovery, not result shopping.

### Case C — AGPL-3.0-only

- Manifest: `LP-V11-C-20261010T110102Z`
- Component: `licenseproof-case-c`
- Evidence: `LP-V11-EVIDENCE-C`
- Evidence SHA-256: `d8a6cc31abc16b6748c7a21f21611f5a1ec33f67d22ca23d7da1c19b95496bee`
- Evidence bytes: `34020`
- Review key: `e7cdff6841629a84efac55ea7ee6a1ef45ea375a8637cbd2cca3db2ddefb3e66`
- Adjudication transaction: `0xab2cdf61cfd411086a104fa2c0d56daf736dc07524fdf39714d1e610e6decc59`
- Component and manifest result: `INCONCLUSIVE`

The vector included `network_source_disclosure_required=true` and
`evidence_sufficient=true`, but `applicability_clear=false`. The v1.1
deterministic boundary therefore produced `INCONCLUSIVE`; no network-source
business verdict was forced from a general license clause without established
modified-covered-work and network facts.

## Read-only assurance proofs

- Successful-result replay preflights for all three cases were rejected by the
  canonical replay guard.
- Frozen policy and finalized manifest mutation attempts were simulated
  read-only and rejected.
- The readback proof compares the complete audit event set with the paginated
  audit view: 23 events, page match PASS.
- Failed semantic execution remained retryable only for the same frozen tuple;
  technical failure never became a component or manifest result.
- No duplicate deployment, blind rebroadcast, or result shopping occurred.

The complete per-write journals, failed attempt, retry authorization record,
canonical readback, nonce ledger, and summary are in
`evidence/qualification/v1.1/`.

## Assurance limitations

These cases classify creator-committed license text against a creator-frozen
policy. They do not prove legal title, upstream package provenance, publisher
grant, redirect origin beyond the runtime's available metadata, or complete
cross-component compatibility. Positive component-level results are not a
whole-product clearance certificate.

