"""Read-only Studio-dev source schema and deploy simulation for v1.1.

Never signs, never sends a transaction, never asks for a private key.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from studio_live_qualification import Rpc, gen_call_deploy_preflight, QualificationError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contracts" / "LicenseProof.py"
SCHEMA = ROOT / "contracts" / "schema.json"
HASH = ROOT / "docs" / "SOURCE_HASH.txt"
RPC = "https://studio-dev.genlayer.com/api"
CHAIN_ID = 61997


def main() -> int:
    source_bytes = SOURCE.read_bytes()
    source = source_bytes.decode("utf-8")
    record = dict(line.strip().split("=", 1) for line in HASH.read_text(encoding="utf-8-sig").splitlines() if "=" in line)
    expected = record["SHA256"]
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != expected:
        raise RuntimeError("remote preflight source hash mismatch")
    rpc = Rpc(RPC)
    chain, _ = rpc.call("eth_chainId", [])
    if int(chain, 16) != CHAIN_ID:
        raise RuntimeError("wrong Studio-dev chain")
    remote_schema, _ = rpc.call("gen_getContractSchemaForCode", ["0x" + source_bytes.hex()])
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
    print("REMOTE_PREFLIGHT_SOURCE_SHA=" + digest)
    print("TRANSACTION_BROADCAST=NO")
    print("NOTE=gen_call validates source execution but does not prove live receipt budget sufficiency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
