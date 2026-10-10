# LicenseProof v1.1 — Steward Hardening / Predeployment Record

Status: **UNRELEASED, NOT DEPLOYED, NOT SUBMITTED**. The historical v1.0.0 contract, release tag, chain address, and three live examples remain unchanged.

This document distinguishes fixes implemented in the v1.1 candidate from assurance boundaries that the contract deliberately does **not** claim. The source, schema, and CI must pass on an exact candidate commit before any successor deployment.

## Changes implemented in the candidate

| Finding | Disposition |
|---|---|
| H-01: self-declared upstream package authority | **Scope constrained, not a proof of issuer ownership.** The contract exposes `package_license_authority_verified=false`; README forbids claiming a package-license grant from an SPDX template. A real publisher verification service or trusted-issuer registry is an additional product, not silently assumed here. |
| H-02: third-party supersession | Code requires predecessor creator for both initial successor claim and final supersession. A predecessor has at most one canonically recorded successor. Old finalized records remain immutable. Unauthorized and duplicate successor tests added. |
| H-03: no cross-component license conflict proof | **Fail closed:** manifest with two or more components cannot return an otherwise positive aggregate verdict; it returns `INCONCLUSIVE` instead. Contract exposes `cross_component_conflicts_verified=false`. A complete dependency/linking graph is outside this version. |
| H-04: nonasserting source/schema CI | Replaced with read-only verifiers. Source SHA is checked against pinned record and workflow value; committed generated schema and ABI are compared without rewriting files. Added negative tampering tests and dirty-worktree gate. |
| M-01: conditional use and field-of-use | Strict semantic facts include `applicability_clear` and `field_of_use_conflicts_with_declared_use`. A restriction's existence alone no longer implies conflict; conditional legal applicability without concrete facts must produce `INCONCLUSIVE`. |
| M-02: unreachable INCONCLUSIVE | Explicit deterministic branch now returns INCONCLUSIVE when evidence exists but applicability is not established. Schema version changed to v1.1. |
| M-03: creator-asserted evidence timestamps | Evidence distinguishes `observed_at_source=CREATOR_ASSERTED` from canonical `committed_at`; no claim of external publisher freshness is made. |
| M-04: redirect provenance | Contract-info explicitly says final origin is not verified without trusted final-URL metadata. SHA/length authentication proves bytes, not effective-origin lineage. |
| M-05: issuer can suppress adverse review | `begin_component_review`, `adjudicate_component`, and `finalize_manifest` are permissionless after issuer freeze, with independent validator consensus and successful replay guards. |
| M-06: duplicate start / unbounded enumeration | Duplicate review-start is rejected. Components are indexed per manifest and capped to 128. Bounded `get_audit_events_page(start,limit)` provided. Legacy full-history views remain available but should not be used for large histories. |
| L-01: stale release documents | Historical predeployment records are now labelled historical. |
| L-02: narrow secret scan | Added independent, commit-pinned Gitleaks action with full-history checkout; retained original targeted scanner as secondary check. |

## Exact semantics and unassessed boundaries

The candidate's contract is intentionally a **claimed-license-text versus declared-policy assessor**, not an independent package license issuance authority, a legal opinion, or complete dependency-graph compatibility certificate. Package hashes are issuer-declared commitments, not a guarantee that those are upstream artifact hashes. The actor controlling evidence may choose to delay freezing a draft manifest; an incomplete draft must never appear cleared.

Its final result is a **component-policy or fail-closed manifest assessment**. In particular, multiple positive component classifications never constitute automatic whole-bundle clearance. Inconclusive is an explicit valid result, not a technical failure. Consensus/RPC errors never become business verdicts.

## Regression / release gates

The branch includes tests for attacker lineage, one-successor rule, repeat review-start, third-party adverse adjudication, inconclusive condition, multi-component fail-closed aggregation, bounded audit pages, and declared evidence provenance. Source/schema mutation gates include negative checks for tampered committed artifacts and source hashes. The named mutation audit now exercises 29 transformations, including five new steward-sensitive ones.

Before v1.1 deployment:
- Exact source digest, schema and interface match at pinned Git head
- Full remote CI (tests, 29/29 mutants, read-only source/ABI verification, Gitleaks, secret scan) succeeds on candidate HEAD
- No unresolved security HIGH defects **within the expressly limited v1.1 product scope**
- Fresh Studio-dev deploy preflight on the exact 5jyc runner
- Explicit approval for a new contract deployment/signature/fee (old v1.0.0 cannot be upgraded in place)

After deployment:
- Broadcast ONCE using the proven `executionBudgetPerRound=25000000000000000`, `rotations=[3]` profile **only if fresh Studio-dev policy/signer balance still supports it**
- Persist signed transaction/intent before broadcast; same-hash reconcile; verify finalized successful execution, exact source/ABI and contract_info readback
- New live v1.1 qualification, including permissionless outsider negative review, `INCONCLUSIVE` conditional use, and the multi-component fail-closed case
- Preserve historic v1.0.0 contract/tx/results, never relabel old v1.0.0 reviews as v1.1
- Merge into protected main only after qualifications and exact-HEAD CI; publish versioned release with all proof
- Submit only the corresponding verified deployed v1.1 source and links, without claiming package-authority verification or complete license certification.

## Historical reference (not v1.1)

v1.0.0: `0x27Ca7E9F92AB0e465420AA9F2583fB25c9355619`, Studio-dev 61997. Historical v1.0.0 source SHA256 `77fb66904787baab72210276f29d6c0cc29831e2d243cecad5c2eb249146c0c4`; MIT, Elastic-2.0 and AGPL-3.0-only proofs apply **only** to that exact deployed version.
