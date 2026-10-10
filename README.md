# LicenseProof

Consensus-backed, policy-relative classification of committed software license text before release.

> **Release status:** v1.0.0 is the historical deployed demonstration. The `hardening/licenseproof-v1-1` branch is an **unreleased candidate**. No v1.1 Studio-dev deployment or live qualification is claimed.

LicenseProof is a standalone GenLayer intelligent contract that evaluates
whether a frozen component manifest is compatible with a frozen release policy
and records the deterministic obligations or incompatibilities that follow.

## The problem

Modern products combine source packages, SDKs, libraries, datasets, model
weights, APIs, templates, and other licensed components. Identifying an SPDX
identifier is deterministic, but the actual terms may require semantic
judgment against a specific release model.

Traditional scanners are useful for identifiers and known license rules, but
they do not reliably resolve custom terms, paid hosted-service restrictions,
attribution and notice obligations, copyleft boundaries, network-source
requirements, proprietary-distribution constraints, or conflicts between a
license and the declared release policy.

LicenseProof answers the narrower question:

> Under the issuer's declared release policy and presented license text, what component-level permissions, conditions, or uncertainties can be classified?

**This is not a verified upstream package-license grant.** The issuer supplies the component identifier, package hash, evidence URL, and policy; their authoritative relationship to a real upstream package is **not independently verified**. This release does **not** certify complete package provenance or cross-component license compatibility. Manifest results aggregate component-level policy outcomes only and MUST NOT be used as a whole-product clearance certificate.

LicenseProof performs policy compatibility adjudication under a declared
release policy. It is not legal advice.

## Architecture

The contract keeps business-critical decisions deterministic:

- release policy identity, version, intent, hash, and freeze state;
- manifest identity, component membership, version, hash, and lifecycle;
- authenticated evidence identity, authority binding, URL path, SHA-256, and
  exact byte length;
- immutable component-review identity and successful-result replay protection;
- independent validator reevaluation of the bounded semantic facts;
- deterministic component and manifest result derivation; and
- append-only audit history without raw model prose.

GenLayer is used only for a bounded semantic vector. The model does not
return a verdict, score, confidence value, explanation, legal advice,
transaction instruction, payment instruction, or address.

The exact semantic fields are:

```text
commercial_use_permitted
hosted_service_permitted
redistribution_permitted
modification_permitted
sublicensing_permitted
derivative_distribution_permitted
proprietary_distribution_permitted
source_disclosure_required
same_license_required
attribution_required
notice_preservation_required
network_source_disclosure_required
field_of_use_restriction
patent_condition_present
evidence_sufficient
```

The deployed v1.0.0 uses exactly these fifteen booleans. The v1.1 candidate adds `applicability_clear`: conditional license facts without established applicability produce `INCONCLUSIVE`. Every field is a strict boolean; the JSON object contains exactly the keys required by the relevant version. License text is treated as untrusted data; prompt,
role, JSON, contract-call, payment, validator, tool, and document-authority
instructions inside it are ignored.

## Evidence authentication

Evidence is HTTPS-only, credential-free, fragment-free, and bound to an exact
normalized authority host and frozen path prefix. Retrieval requires HTTP 2xx,
non-empty byte content, bounded size, valid UTF-8, and exact equality with the
committed SHA-256 and byte length. A changed source at the same URL therefore
fails closed instead of becoming a business result.

The leader and validator independently retrieve and evaluate the same evidence
using JSON mode. A validator that only checks response shape is not sufficient.
Technical failures do not become `COMPATIBLE`, `INCOMPATIBLE`, or any other
business result. Failed semantic attempts remain retryable for the same frozen
identity; a successful identity is immutable and cannot be replayed or shopped.

## Release policy and manifest lifecycle

A policy moves from `DRAFT` to immutable `FROZEN`. A manifest references one
frozen policy. Components and evidence are committed while the manifest is
`DRAFT`; freezing makes membership immutable. Review moves the manifest through
`FROZEN` and `REVIEWING`; every component needs one successful immutable review.
Finalization performs no semantic call and deterministically derives the
manifest result.

The final-result enum is:

```text
COMPATIBLE
COMPATIBLE_WITH_OBLIGATIONS
INCOMPATIBLE
INSUFFICIENT_EVIDENCE
INCONCLUSIVE
```

The deployed v1.0.0 has 26 public methods. The v1.1 candidate has 28 methods, including a successor lineage view and paginated audit events, and extends the semantic vector with `applicability_clear`. The unreleased v1.1 candidate is NOT the deployed contract.

## Verified historical v1.0.0 Studio-dev deployment

The verified deployment is on Studio-dev, chain `61997`:

```text
Contract:        0x27Ca7E9F92AB0e465420AA9F2583fB25c9355619
Deployment tx:   0xa3eeeb8156ee3b6317b77beeb73ba7d3196b0f4d30830ef0de97c82f4407de03
Source SHA-256:  77fb66904787baab72210276f29d6c0cc29831e2d243cecad5c2eb249146c0c4
Version:         1.0.0
Semantic schema: licenseproof.semantic.v1
Runner:          py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng
Methods:         26
Execution:       FINALIZED / SUCCESS
Source parity:   PASS
Schema parity:   PASS
```

## Historical v1.0.0 live qualification (not v1.1 certification)

All three cases used one frozen policy and commit-pinned SPDX evidence from
`spdx/license-list-data` commit
`31ba1a50e5397e00a304dbadc76531740e89ee48`.

| Case | Evidence SHA-256 | Canonical review | Result |
| --- | --- | --- | --- |
| MIT | `b05785f9f18e6716bab63424b11454513b9943a222595b70411009202fc592b5` | `d5ff8b1ac7a97e8771f919c49170efac1be5adab38565c598ec0dcf03e4908de` | `COMPATIBLE_WITH_OBLIGATIONS` |
| Elastic-2.0 | `6448026f2e06ab3da9ed8ddda686694bba37179e88db92dea6d4aab516c957ea` | `40820945d79fbbd79473215da1eaac270dd7832421f5092afd71b764b0e6cb95` | `INCOMPATIBLE` |
| AGPL-3.0-only | `d8a6cc31abc16b6748c7a21f21611f5a1ec33f67d22ca23d7da1c19b95496bee` | `cf10789b6fa19ddf3fe96c6d6d0af548926df2f109b23027822e27509d3a8808` | `INCOMPATIBLE` |

Case A recognized commercial hosted use and modification, with attribution and
notice-preservation obligations. Case B recognized
`hosted_service_permitted=false`. Case C recognized
`network_source_disclosure_required=true` under a proprietary hosted policy.

Case C also preserves the failed technical attempt
`0x0d253e540f555a8282fb857dbc0906f2e5426d45940f493b4536a9211eb44c92`.
It finalized without a canonical review because of consensus disagreement. The
same frozen identity remained unchanged, one retry was performed, and the
successful retry was
`0xe888d147a3b562f64813feb8cf73dbf48d4c5ddfa700eb6d7658b125a883254f`.
No result shopping occurred.

## Incident history

An earlier deployment attempt used an underfunded execution budget whose
receipt requirement exceeded submitted capacity. A CLI stdout/hash-capture
weakness was also identified. The contract source was never changed. The
deployment path was hardened around direct SDK submission, durable intent and
hash persistence, same-hash recovery, and the proven Studio-dev fee profile.
The corrected deployment succeeded exactly once. Detailed evidence remains in
`docs/DEPLOYMENT_FORENSICS.md` and `evidence/qualification/`.

## Verification

The release gates include direct lifecycle tests, URL/evidence and
prompt-injection adversarial tests, Hypothesis property tests, semantic harness
tests, deployment-safety tests, schema/interface parity, source verification,
secret scanning, and a named mutation audit.

Current verified results:

```text
Full tests:       63 passed
Harness tests:    10 passed
Mutation audit:   24/24 killed
ABI parity:       PASS
Secret scan:      PASS
Current audit:    Critical 0 / High 0 / Medium 0
```

Run the local suite with:

```powershell
python -m pytest -q
python scripts/mutation_audit.py
python scripts/verify_schema.py
python scripts/verify_source.py
```

## Assurance and submission boundaries

- **Issuer claim, not independent license authority:** HTTPS hash-verified bytes prove content integrity relative to a creator-supplied commitment. SPDX license templates alone never prove that a software publisher granted that license to a particular package.
- **Policy-relative only:** The manifest result is the deterministic priority of individually reviewed components. Cross-component copyleft, linking, exception, or derivative-work conflicts are outside this version's adjudication.
- **Conditional terms:** Elastic-2.0 hosted restrictions and AGPL network-source duties have conditions; the three live examples demonstrate selected policy-relative interpretations, not universally applicable legal conclusions.
- **Freshness:** `observed_at` and `published_at` are self-asserted. v1.1 additionally records chain commit time but does not prove publisher freshness.
- **Redirects:** Without trusted final-origin metadata, an HTTPS fetch plus SHA256 does not prove a no-redirect authority chain.
- **Review:** v1.1 permits independent review and finalization of already-frozen manifests; draft composition still belongs to the issuer. A still-draft manifest means **unassessed**, never cleared.
- **Historical release:** `v1.0.0` remains frozen at its original tag and deployed address. v1.1 code changes require a separate deployment and new live qualification before the candidate may be called submitted-ready.

## Repository status

This branch is a steward-hardening **candidate**, not a deployed successor. Do not claim a v1.1 Studio-dev contract address or use the historical v1.0.0 proof as evidence of v1.1 execution.

