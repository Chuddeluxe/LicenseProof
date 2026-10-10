# LicenseProof v1.1 — controlled deployment and qualification handoff

**Status:** PREDEPLOYMENT CANDIDATE. NOT YET DEPLOYED OR SUBMITTED. Historical `v1.0.0` is still deployed at `0x27Ca7E9F92AB0e465420AA9F2583fB25c9355619`, but no v1.1 address or business verdict may be inferred from that release.

## Exact candidate identity

- Branch: `hardening/licenseproof-v1-1`
- Contract file: `contracts/LicenseProof.py`
- Source SHA-256: `354f840a54e57a215790fa70182938ade78f43b505bcf05f8ded37cd4c1135fd`
- Runner: `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`
- Studio-dev: chain 61997, RPC `https://studio-dev.genlayer.com/api`
- Version: `1.1.0`; semantic schema `licenseproof.semantic.v1.1`; 28 methods, 17 strict boolean fields
- Proven deployment envelope: `executionBudgetPerRound=25000000000000000`, `rotations=[3]`, `feeValue=100000000000010352`, **subject to fresh chain fee/balance verification**.

The above SHA must be recalculated and checked against `docs/SOURCE_HASH.txt`, the deploy harness, and CI before any signing. An exact green workflow run is required on the final commit—not merely an earlier candidate.

## Operator actions

The connected GitHub automation cannot access the encrypted local WinCred keystore. **Only an owner-authorized Windows execution may unlock the signer and broadcast transactions.** Do not put a private key in an environment variable, command, repository, ticket, or chat.

From the existing Windows workspace `C:\Users\DELL\LicenseProof`, verify the exact remote and fetch this branch *without overwriting any uncommitted work*. Run the ordinary 5jyc toolchain and tests; remote GitHub CI is necessary but does not prove local wallet readiness.

The v1.1 runner was isolated from historical v1.0 scripts:

```powershell
python -m scripts.live_qualification_v11
```

The default mode is **read-only**. It checks the exact source, chain, 28-method remote schema, and `gen_call type=deploy`; it does not load the wallet.

Only after **new explicit human approval** for a v1.1 Studio-dev deployment and fee expenditure, the authorized owner may run:

```powershell
$env:LICENSEPROOF_V11_DEPLOY_APPROVAL = 'APPROVE LICENSEPROOF V1.1 ONE-SHOT STUDIO-DEV DEPLOYMENT'
python -m scripts.live_qualification_v11 --execute
Remove-Item Env:\LICENSEPROOF_V11_DEPLOY_APPROVAL
```

Do not run these approval commands until fresh nonce, balance, signer, source/hash, remote schema, fee distribution, process exclusivity, and intent journal checks pass. The account is shared with other projects: avoid concurrent signed sends from any of them.

## What the guarded runner does

1. Uses the same-hash direct SDK sender, not CLI stdout parsing; fsyncs each deployment/write intent before broadcast and each returned EVM hash before polling.
2. Stops on a consumed nonce without recoverable hash, on contradictory account state, on a terminal failed execution, or on readback mismatch. **Never rebroadcast just because stdout, RPC, or the process timed out.**
3. Verifies finalized **successful execution**, deployed source SHA, remote 28-method ABI, and `contract_info` version/schema independently.
4. Pins SPDX upstream license *template* bytes to a specific commit with exact SHA-256 and length, never treating them as proof of real package-license grants.
5. Runs controlled MIT, Elastic-2.0, and AGPL-3.0-only policy-relative examples using the new 17-boolean schema, explicitly expecting conservative `INCONCLUSIVE` where license application facts are not established.
6. Preserves every hash, receipt, canonical review, replay/read-only immutability proof, and failed attempt in `evidence/qualification/v1.1/`.
7. Fails qualification rather than proclaiming `VERIFIED` when the sender nonce window contains unexplained transactions.

An unsuccessful semantic transaction with a known hash must be reconciled. The runner will **not** automatically retry it. Diagnose technical consensus/runtime vs business failure before authorizing a single same-identity retry.

## Steward-facing assurance boundaries

The contract assesses **creator-claimed license-text bytes against a creator-declared release policy**. It proves neither legal title nor a package publisher's grant, independent upstream currentness, trusted effective HTTP redirect origin when runtime metadata is absent, nor complete cross-component compatibility. V1.1 positive individual component decisions do not certify full software bundles; multi-component otherwise-positive manifest results fail closed to `INCONCLUSIVE`.

The earlier v1.0.0 results and CI may be cited as **historical**, but never relabeled as v1.1 qualifications.

## Public release and submission gate

Only after successful v1.1 deployment and new live qualification: commit the receipts and truthful readbacks, verify local and GitHub source parity, all CI/tests/mutations/secret scans, exact-HEAD `main` and protected merge, publish `v1.1.0`, then prepare GenLayer Portal fields containing the **new** contract address and actual proof. The Portal submission is not complete until it returns authenticated submission confirmation.

This document is not an approval or submission receipt. **The guarded `--execute` command broadcasts paid chain transactions if its separate authorization condition is satisfied**; never run it merely for testing or inspection.
