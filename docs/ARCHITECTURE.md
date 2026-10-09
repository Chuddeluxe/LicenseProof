# Architecture

LicenseProof is a single GenLayer contract with four deterministic layers:

1. Frozen release policy: declared use and source/distribution intent.
2. Frozen manifest: immutable component membership and evidence identity.
3. Consensus-backed component review: authenticated bytes plus a strict
   semantic vector.
4. Deterministic finalization: policy/vector rules and manifest aggregation.

Records are canonical JSON strings in `TreeMap` values. IDs are indexed in
`DynArray` values. This keeps storage layout inspectable and avoids nested
storage objects crossing the nondeterministic boundary.

The leader and validator receive only plain in-memory snapshots. They do not
write storage. Successful review storage happens only after
`run_nondet_default` returns a strictly parsed vector.
