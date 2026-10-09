# Security controls

- Authorization: creator/actor is recorded; mutation is controlled by state,
  IDs, freeze gates, and immutable records.
- Identity: policy, manifest, package, evidence, and semantic schema hashes are
  bound into the review tuple.
- Evidence: exact host/path, content hash, byte length, UTF-8, size, timestamp,
  and optional final URL checks.
- Semantic boundary: untrusted-data prompt, JSON mode, exact key/type parser,
  independent validator evaluation.
- Replay/liveness: successful review guard is written after consensus; failed
  attempts write no review identity and stay retryable.
- Finality: final result is derived by deterministic priority and finalized
  manifests are not overwritten.
- History: audit events are append-only and contain no raw LLM prose.

The independent audit classified no Critical, High, or Medium findings after
the final test pass. The only Low/tooling note is the installed linter’s stale
E010 recognition of `run_nondet_default`, documented in the semantic boundary
and recurrence audit.
