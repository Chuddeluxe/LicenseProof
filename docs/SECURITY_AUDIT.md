# Independent security audit

This file preserves the original v1.0.0 audit and records the later v1.1.0 steward-hardening audit separately. The v1.1.0 section is the current release assessment.

## v1.1.0 current release audit

The hardening review re-opened assumptions that the original v1.0.0 test suite had not challenged deeply enough. The remediation was implemented on a separate branch, live-deployed as a new contract, qualified independently, merged to protected `main`, and released as `v1.1.0`.

### Steward-sensitive findings and disposition

| Severity | Finding | v1.1.0 disposition |
|---|---|---|
| HIGH | Creator-supplied license source could be mistaken for independently verified upstream package authority | Product scope constrained and exposed explicitly: `package_license_authority_verified=false`; release docs prohibit claiming upstream grant/provenance |
| HIGH | Third party could claim supersession lineage over another creator's finalized manifest | Fixed: predecessor creator binding plus one canonical successor; adversarial tests added |
| HIGH | Positive per-component classifications could be misread as whole-bundle cross-license compatibility | Fixed fail-closed behavior: otherwise-positive multi-component aggregate returns `INCONCLUSIVE`; `cross_component_conflicts_verified=false` |
| HIGH | Source/schema verification could report green without proving committed artifacts | Replaced with fail-closed, read-only SHA/schema/interface checks plus tamper-negative tests |
| MEDIUM | Conditional obligations and field-of-use restrictions could be over-applied | Added `applicability_clear` and `field_of_use_conflicts_with_declared_use`; uncertainty deterministically maps to `INCONCLUSIVE` |
| MEDIUM | `INCONCLUSIVE` was not reachable from normal semantic adjudication | Fixed with explicit deterministic uncertainty branch |
| MEDIUM | Evidence timestamps could be mistaken for externally authenticated freshness | Evidence now marks creator assertion and separately records canonical commit time; no publisher-freshness claim |
| MEDIUM | Redirect/final-origin provenance exceeded runtime guarantees | Explicitly scoped; hash/length prove committed bytes, not hidden redirect lineage |
| MEDIUM | Issuer could suppress adverse assessment after freezing | Frozen-manifest review/adjudication/finalization made permissionless |
| MEDIUM | Duplicate review-start and unbounded read enumeration | Duplicate start rejected; per-manifest component index/cap and paginated audit view added |
| LOW | Historical release documents became stale after deployment | Current/historical records separated and labelled |
| LOW | Original secret scan was narrow | Added commit-pinned Gitleaks in CI; targeted scan retained |

### Current v1.1.0 gates

- Contract: `0x18A850BB8cA6cb0F75a5A9ab95362c12f1E349e6`
- Deployment: `0x0d81881d71a362033fa075780d6b6b5ea90c20251fcce952772f863561db5ca1`
- Source SHA-256: `354f840a54e57a215790fa70182938ade78f43b505bcf05f8ded37cd4c1135fd`
- Public methods: 28
- Semantic schema: `licenseproof.semantic.v1.1` with 17 strict booleans
- Exact-main GitHub CI: `38048824819` — SUCCESS on `dcac65546f9bce41c83a180dd24f324e227cf9d5`
- Full tests: 83 passed
- Focused suites: 60 passed
- Mutation audit: 29/29 killed
- Source verification: PASS
- ABI/schema parity: 28/28 PASS
- Studio-dev remote schema and read-only deployment preflight: PASS
- Commit-pinned Gitleaks: PASS
- Targeted secret scan: PASS
- Live qualification: VERIFIED
- Current unresolved Critical: 0
- Current unresolved High: 0
- Current unresolved Medium: 0

The product deliberately does **not** claim independent publisher/package-license provenance, legal advice, or complete cross-component dependency-graph compatibility. Those are assurance boundaries, not hidden green findings.

The installed `genvm-linter 0.11.1rc2` may still report the known E010 safe-call-table false positives around `run_nondet_default`; runtime execution, validator tests, deployed schema/source parity, and live qualification cover the required call path.

## v1.0.0 historical audit

The original pre-v1.0 audit found one Medium authorization issue and a linter/tooling note. The authorization issue was fixed before v1.0.0 release.

| Severity | Finding | Historical disposition |
|---|---|---|
| MEDIUM | Draft policy/manifest lifecycle methods did not require the recorded creator | Fixed with creator checks |
| LOW / tooling | `genvm-linter 0.11.1rc2` E010 around `run_nondet_default` | Documented tooling false positive |

The v1.0.0 release subsequently passed its then-current direct, adversarial, property, semantic, harness, mutation, source/schema, secret-scan, deployment and live-qualification gates. It remains preserved as historical evidence and must not be used as the v1.1.0 submission artifact.
