> **HISTORICAL CHECKPOINT — NOT CURRENT RELEASE STATUS.** This record predates the successful v1.0.0 public deployment and the current unreleased v1.1 hardening branch. Current canonical v1.0.0 facts are in `docs/LIVE_DEPLOYMENT.md`, `docs/LIVE_QUALIFICATION.md`, and the `v1.0.0` release. Do not treat historical "not deployed" or "not pushed" statements below as current.

# Release checklist

- [x] Contract source uses the qualified 5j runner.
- [x] Policy, manifest, evidence, review, finalization, and audit controls are
  deterministic.
- [x] Semantic vector is exact and JSON-only.
- [x] Validator independently reruns retrieval and semantic evaluation.
- [x] Direct, adversarial, property, semantic, and mutation gates pass.
- [x] Schema/interface method parity passes.
- [x] Critical/High/Medium audit findings are zero.
- [x] Worktree is clean after local commits.
- [ ] Deployment: intentionally not performed in this phase.
