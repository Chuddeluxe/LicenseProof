# Trust model

Trusted by the contract: caller identity, canonical IDs, frozen policy and
manifest hashes, evidence identity, SHA-256, byte length, URL authority/path,
state transitions, replay guards, and result derivation.

Not trusted: declared SPDX-looking labels, fetched text, redirects, LLM prose,
LLM confidence, model-selected verdicts, and infrastructure success.

The model may classify only the fifteen semantic booleans. A compatible result
is a contract calculation, never an LLM response.
