# State machine

Policy: `DRAFT -> FROZEN`.

Manifest: `DRAFT -> FROZEN -> REVIEWING -> FINALIZED`. `SUPERSEDED` is part of
the public state vocabulary for replacement workflows, but historical
finalized records are never overwritten; supersession is an append-only
relation and audit event.

Component review: `UNREVIEWED -> FINALIZED` only after successful consensus.
Failed retrieval, malformed JSON, disagreement, VM errors, and reverted calls
do not consume the review identity and remain retryable.
