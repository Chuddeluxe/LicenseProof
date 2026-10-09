# Testing

Run `python -m pytest -q` for direct, adversarial, property, semantic, and
mutation test modules. Run `python scripts/verify_schema.py` to regenerate the
exact schema/interface pair. Run `python scripts/mutation_audit.py` for the
24-mutant security gate.

Direct tests cover all writes, views, counts, IDs, audit history, freeze and
supersession behavior. Adversarial tests cover URL spoofing, redirects,
changed bytes, malformed responses, prompt injection, and malformed semantic
payloads. Hypothesis tests cover lowercase SHA validation, deterministic
priority, order independence, and path boundaries.
