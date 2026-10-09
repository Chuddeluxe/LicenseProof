# Semantic boundary

`gl.nondet.exec_prompt(prompt, response_format="json")` is called only inside
the leader/validator functions passed to `gl.vm.run_nondet_default`.

The prompt declares the document untrusted and requires exactly fifteen keys,
all strict booleans, with no extra keys. Markdown stripping, fuzzy aliases,
trailing-comma repair, and prose extraction are intentionally absent.

The installed `genvm-linter 0.11.1rc2` emits E010 for the current
`run_nondet_default` call graph because its safe-call table recognizes
`run_nondet` but not the required `run_nondet_default`. This is recorded as a
tooling false positive; the source uses the requested current API and direct
tests execute the captured validator independently.
