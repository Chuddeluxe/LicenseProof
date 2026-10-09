# LicenseProof

Consensus-backed software license compatibility before release.

LicenseProof is a standalone GenLayer intelligent contract for answering a
bounded release question: can a frozen component manifest be used under a
frozen release policy, and which deterministic obligations follow?

## Problem

Modern releases combine source packages, SDKs, datasets, model weights, APIs,
templates, and other assets. SPDX identification is deterministic, but the
actual compatibility of terms with a declared commercial, hosted, proprietary,
or distributed release model can require semantic judgment. A component may
allow commercial use while forbidding paid hosted service, require derivative
source disclosure, preserve notices, or contain custom non-SPDX terms.

Normal license scanners are excellent at identifiers and known rules. They are
not enough for authenticated custom text, network copyleft, hosted-service
restrictions, or release-policy-specific semantic facts.

## Product boundary

GenLayer decides only the following strict semantic vector after independently
retrieving the committed evidence:

`commercial_use_permitted`, `hosted_service_permitted`,
`redistribution_permitted`, `modification_permitted`, `sublicensing_permitted`,
`derivative_distribution_permitted`, `proprietary_distribution_permitted`,
`source_disclosure_required`, `same_license_required`, `attribution_required`,
`notice_preservation_required`, `network_source_disclosure_required`,
`field_of_use_restriction`, `patent_condition_present`, and
`evidence_sufficient`.

The model does not return a verdict, score, confidence, prose, legal advice,
or transaction instruction. The contract deterministically controls identity,
versioning, policy, manifest membership, evidence hashes, authority binding,
state transitions, replay protection, final result derivation, and audit history.

## Release policy and manifest lifecycle

A release policy records commercial use, hosted service, redistribution,
modification, sublicensing, derivative distribution, source model, and
distribution model. It moves from `DRAFT` to immutable `FROZEN`.

A manifest references exactly one frozen policy. Components and authenticated
evidence are committed while the manifest is `DRAFT`; freezing computes the
manifest hash and makes membership immutable. Review moves the manifest through
`FROZEN` → `REVIEWING`; each component must have one successful immutable
review. Finalization derives the manifest result by deterministic priority:

`INCOMPATIBLE` → `INSUFFICIENT_EVIDENCE` → `INCONCLUSIVE` →
`COMPATIBLE_WITH_OBLIGATIONS` → `COMPATIBLE`.

## Demonstrations

- Case A: MIT-like permissive text under commercial hosted proprietary use
  produces `COMPATIBLE_WITH_OBLIGATIONS` because attribution and notice
  preservation are required.
- Case B: custom text forbidding paid hosted derivatives produces
  `INCOMPATIBLE` because `hosted_service_permitted=false`.
- Case C: network-copyleft-style text with a hosted proprietary policy produces
  `INCOMPATIBLE` because `network_source_disclosure_required=true`.

The fixtures are ordinary local evidence inputs; verdicts are not keyed to
fixture names.

## Security model

Evidence is HTTPS-only, credential-free, fragment-free, restricted to the
exact normalized authority host and frozen path prefix, bounded in bytes, and
bound to a lowercase SHA-256 and exact byte length. Retrieval requires HTTP
2xx, byte body, non-empty bounded content, UTF-8 decoding, and exact committed
hash/length equality. Technical failures revert/retry and never become a
business verdict.

The semantic prompt treats license text as untrusted data and explicitly
ignores prompt, role, JSON, contract-call, payment, validator, tool, and
document-authority instructions. Validators independently retrieve the same
evidence and independently execute the same JSON semantic evaluation; they do
not merely validate shape.

## Architecture

The contract uses annotation-driven `TreeMap` and `DynArray` storage, with
canonical JSON strings for records. The current qualified runtime family is
the cached `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`
runner with `genlayer-py 0.19.0rc2` and `genlayer-test 0.30.0rc2`.

## Test matrix

The repository contains direct lifecycle tests, URL/evidence/prompt-injection
adversarial tests, Hypothesis properties, semantic harness tests, and a real
named mutation audit. The mutation gate requires 24/24 killed. Schema and
interface parity are generated from the local GenVM contract schema.

## Current status

**LOCAL PREDEPLOY ONLY.** No deployment, faucet use, Studio-dev write, live
blockchain write, GitHub repository, or push was performed.
