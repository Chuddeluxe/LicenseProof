# Evidence model

An evidence record freezes authority ID, normalized host, path prefix, source
URL, content SHA-256, byte length, publication/observation timestamps, and
evidence type. The component binds exactly one evidence ID before manifest
freeze.

URLs require HTTPS, no credentials, no fragment, no non-default explicit port,
exact normalized host, and a path inside the prefix with dot-segments and
encoded separator escapes rejected. Retrieval requires 2xx bytes, bounded
non-empty body, UTF-8 decoding, exact hash, and exact length. The current web
Response ABI has no final-URL field; when the optional
`x-genlayer-final-url` field is present it is authenticated against the same
host/prefix. Redirect-related behavior is therefore fail-closed when exposed
by the current response surface and is covered by the adversarial harness.
