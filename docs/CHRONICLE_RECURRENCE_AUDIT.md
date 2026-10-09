# Chronicle recurrence audit

| Failure class | Risk | Control | Test | Result |
|---|---|---|---|---|
| FINALITY != EXECUTION SUCCESS | Reverted/undetermined review treated as final | Write review only after successful strict result | retry and technical-failure tests | PASS |
| RUNTIME FAMILY MISMATCH | API works locally but not on qualified runner | 5j header, cached runner, exact versions recorded | direct load and source verification | PASS |
| TEXT MODE VS JSON MODE | Text parser accepts prose or fences | `response_format="json"`, exact object parser | semantic malformed-output tests | PASS |
| STORAGE API FAMILY | Nested or stale storage behavior corrupts state | v0.6 annotation TreeMap/DynArray and JSON records | direct lifecycle/schema load | PASS |
| ADDRESS/SERIALIZATION BOUNDARIES | Non-plain values cross nondet boundary | plain dict snapshots and strings in leader/validator | direct pickling/load path | PASS |
| TIMESTAMP COMPARISON | Publication appears after observation | timezone-aware parsing and ordering check | evidence timestamp tests | PASS |
| WEB AUTHORITY SPOOFING | Credentials, subdomains, ports, escapes | normalized exact host and safe path prefix | adversarial URL tests | PASS |
| WEB SOURCE CHANGED BY SAME URL | Same URL returns different bytes | frozen SHA and exact length | hash/length mismatch tests | PASS |
| INFRASTRUCTURE FAILURE AS BUSINESS VERDICT | 500/empty/UTF-8 error becomes compatible | retryable UserError; no review write | technical failure tests | PASS |
| PROMPT INJECTION | License text changes control instructions | untrusted-data prompt boundary | injected-license test | PASS |
| WEAK VALIDATOR THAT ONLY CHECKS SHAPE | Leader can shop a valid shape | validator independently retrieves and evaluates | captured validator and disagreement tests | PASS |
| RESULT SHOPPING | Caller retries with changed tuple | manifest/policy/evidence hashes in review identity | identity/replay tests | PASS |
| SUCCESSFUL RESULT REPLAY | Same result stored multiple times | component guard and review index | duplicate review mutation | PASS |
| FAILED ATTEMPT LIVENESS | Failed attempt permanently blocks retry | replay identity written after consensus only | retry test and mutant | PASS |
| SOURCE / SCHEMA PARITY | ABI drifts from public source | schema generated locally and interface parity gate | verify_schema.py | PASS |
| STALE DOCUMENTATION / DEPLOYMENT CLAIMS | Local artifact claims production status | README and plan state local predeploy only | source/docs review | PASS |

Tooling note: `genvm-linter 0.11.1rc2` reports E010 for the required
`run_nondet_default` because its safe-call table omits that current API. No
contract control is disabled; the diagnostic is retained and documented as a
tooling false positive.
