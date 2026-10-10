"""Read-only Studio-dev source schema and deploy simulation for v1.1.

Never signs, never sends a transaction, never asks for a private key.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.studio_live_qualification import Rpc, gen_call_deploy_preflight, QualificationError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contracts" / "LicenseProof.py"
SCHEMA = ROOT / "contracts" / "schema.json"
HASH = ROOT / "docs" / "SOURCE_HASH.txt"
RPC = "https://studio-dev.genlayer.com/api"
CHAIN_ID = 61997


def main() -> int:
    # Text mode canonicalizes Windows CRLF checkouts to the LF source bytes that
    # the v1.1 deploy runner actually submits. The raw worktree digest is
    # diagnostic only; canonical deployment bytes must match SOURCE_HASH.txt.
    raw_worktree_bytes = SOURCE.read_bytes()
    source = SOURCE.read_text(encoding="utf-8")
    canonical_bytes = source.encode("utf-8")
    record = dict(line.strip().split("=", 1) for line in HASH.read_text(encoding="utf-8-sig").splitlines() if "=" in line)
    expected = record["SHA256"]
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    raw_digest = hashlib.sha256(raw_worktree_bytes).hexdigest()
    if digest != expected:
        raise RuntimeError(f"remote preflight canonical source hash mismatch: {digest} != {expected}")
    rpc = Rpc(RPC)
    chain, _ = rpc.call("eth_chainId", [])
    if int(chain, 16) != CHAIN_ID:
        raise RuntimeError("wrong Studio-dev chain")
    remote_schema, _ = rpc.call("gen_getContractSchemaForCode", ["0x" + canonical_bytes.hex()])
    local_schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if not isinstance(remote_schema, dict) or remote_schema != local_schema:
        raise RuntimeError("remote schema/source mismatch")
    if len(remote_schema["methods"]) != 28:
        raise RuntimeError("wrong remote method count")
    deploy = gen_call_deploy_preflight(rpc, source)
    if not deploy["result"].lower().startswith("00"):
        raise RuntimeError("remote deploy simulation did not succeed")
    print("STUDIO_DEV_CHAIN=61997")
    print("REMOTE_SCHEMA_METHODS=28")
    print("REMOTE_SCHEMA_PARITY=PASS")
    print("REMOTE_GEN_CALL_DEPLOY=PASS")
    print("REMOTE_PREFLIGHT_SOURCE_SHA=" + digest)\n    print("RAW_WORKTREE_SOURCE_SHA=" + raw_digest)\n    print("WORKTREE_LINE_ENDING_NORMALIZED=" + ("YES" if raw_digest != digest else "NO"))
    print("TRANSACTION_BROADCAST=NO")
    print("NOTE=gen_call validates source execution but does not prove live receipt budget sufficiency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
