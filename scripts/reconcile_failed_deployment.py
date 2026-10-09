"""Read-only reconciliation of the historical failed deployment hash."""

from __future__ import annotations

import json
from pathlib import Path

from genlayer_py import create_client
from genlayer_py.chains.studio_devnet import studio_devnet

from studio_live_qualification import (
    CHAIN_ID,
    DEPLOYER,
    NETWORK,
    QUALIFICATION_DIR,
    RPC,
    LiveWriter,
    Rpc,
    append_jsonl,
    json_safe,
    serialized_deploy,
    utc_now,
)


TX_HASH = "0xc1d73935470d50f78338aea2fe4c151f1d4baffd98f60575a5c95fb59c99a799"
ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "LicenseProof.py"


def main() -> int:
    preflight = json.loads((QUALIFICATION_DIR / "deployment-preflight.json").read_text(encoding="utf-8"))
    _data, calldata_digest = serialized_deploy(CONTRACT.read_text(encoding="utf-8"))
    if calldata_digest != preflight["gen_call_deploy"]["calldata_sha256"]:
        raise RuntimeError("deployment calldata digest does not match the persisted preflight")
    rpc = Rpc(RPC)
    chain_hex, _ = rpc.call("eth_chainId", [])
    if int(chain_hex, 16) != CHAIN_ID:
        raise RuntimeError(f"unexpected chain id while reconciling: {chain_hex}")
    client = create_client(studio_devnet, endpoint=RPC)
    writer = LiveWriter(rpc, client)
    initial = {
        "phase": "tx_hash_persisted_recovery",
        "label": "DEPLOYMENT",
        "method": "deploy",
        "arguments": [],
        "from": DEPLOYER,
        "network": NETWORK,
        "chainId": CHAIN_ID,
        "pre_write_nonce": None,
        "calldata_sha256": calldata_digest,
        "fee_estimate": preflight["fee_estimate"],
        "tx_hash": TX_HASH,
        "finality": None,
        "execution_result": None,
        "canonical_readback": None,
        "timestamp": utc_now(),
        "recovery_reason": "CLI printed the label and hash on separate lines; hash was recovered from captured output before any retry.",
    }
    journal = QUALIFICATION_DIR / "deployment.jsonl"
    append_jsonl(journal, initial)
    reconciled = writer.reconcile(TX_HASH)
    final = {
        **initial,
        "phase": "reconciled",
        "finality": reconciled["transaction"].get("lifecycle"),
        "execution_result": {
            "successful": reconciled["successful"],
            "tx_execution_result": reconciled["transaction"].get("tx_execution_result"),
            "tx_execution_result_name": reconciled["transaction"].get("tx_execution_result_name"),
        },
        "canonical_readback": None,
        "transaction": json_safe(reconciled["transaction"]),
        "timestamp": utc_now(),
    }
    append_jsonl(journal, final)
    (QUALIFICATION_DIR / "deployment-failure.json").write_text(json.dumps(json_safe(final), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(json_safe(final), sort_keys=True))
    return 0 if reconciled["successful"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
