"""Read-only Studio-dev deployment forensics for the frozen LicenseProof source.

This script only performs JSON-RPC reads and writes local evidence files.  It
has no signing, transaction submission, faucet, or retry path.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.studio_live_qualification import (
    CHAIN_ID,
    CONTRACT,
    DEPLOYER,
    EXPECTED_SOURCE_SHA,
    NETWORK,
    RPC,
    ZERO_ADDRESS,
    fee_estimate,
    local_schema,
    serialized_deploy,
    sha256_bytes,
    utc_now,
    write_json,
)


EVIDENCE = ROOT / "evidence" / "forensics"
KNOWN_TX = "0xc1d73935470d50f78338aea2fe4c151f1d4baffd98f60575a5c95fb59c99a799"
PROCURA_TX = "0x5ceef949b50a184d9f5675a174ee6b329acdf61bbb05b853392b5e55b29ba34d"
PROCURA_ADDRESS = "0x88634c7868B0659b46C5bd93E4038222697a0170"


def raw_rpc(method: str, params: list[Any]) -> dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    request = urllib.request.Request(
        RPC,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "LicenseProof-forensics"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            envelope = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {"method": method, "params": params, "transport_error": str(exc)}
    return {"method": method, "params": params, "response": envelope}


def result_of(record: dict[str, Any]) -> Any:
    response = record.get("response")
    return response.get("result") if isinstance(response, dict) else None


def tx_snapshot(tx_hash: str) -> dict[str, Any]:
    return {
        "transaction": raw_rpc("eth_getTransactionByHash", [tx_hash]),
        "receipt": raw_rpc("eth_getTransactionReceipt", [tx_hash]),
        "lifecycle": raw_rpc("gen_getTransactionLifecycle", [{"txId": tx_hash}]),
    }


def main() -> int:
    source = CONTRACT.read_bytes()
    source_sha = hashlib.sha256(source).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f"frozen source SHA mismatch: {source_sha}")

    local_schema_value, local_interface = local_schema()
    deploy_data, deploy_calldata_sha = serialized_deploy(source.decode("utf-8"))
    chain = raw_rpc("eth_chainId", [])
    nonce_latest = raw_rpc("eth_getTransactionCount", [DEPLOYER, "latest"])
    nonce_pending = raw_rpc("eth_getTransactionCount", [DEPLOYER, "pending"])
    balance = raw_rpc("eth_getBalance", [DEPLOYER, "latest"])
    fee_config_record = raw_rpc("sim_getFeeConfig", [])

    # These methods are probed read-only because the RC node does not expose a
    # documented sender+nonce index.  Their exact errors are evidence, not a
    # fabricated nonce-11 hash.
    nonce_11_probes = {
        method: raw_rpc(method, params)
        for method, params in {
            "eth_getTransactionBySenderAndNonce": [DEPLOYER, 11],
            "gen_getTransactionBySenderAndNonce": [DEPLOYER, 11],
            "gen_getTransactionByNonce": [DEPLOYER, 11],
            "eth_getTransactionByNonce": [DEPLOYER, 11],
            "eth_getTransactionsByAddress": [DEPLOYER],
            "gen_getTransactionsByAddress": [DEPLOYER],
        }.items()
    }

    normal_gen_call = raw_rpc(
        "gen_call",
        [{"type": "deploy", "data": deploy_data, "from": DEPLOYER, "to": ZERO_ADDRESS, "status": "finalized"}],
    )
    corrected_distribution = {
        "leaderTimeunitsAllocation": 100,
        "validatorTimeunitsAllocation": 200,
        "appealRounds": 0,
        "executionBudgetPerRound": 94353600000000,
        "executionConsumed": 0,
        "totalMessageFees": 0,
        "rotations": [0],
        "maxPriceGenPerTimeUnit": 2,
        "storageFeeMaxGasPrice": 300000000,
        "receiptFeeMaxGasPrice": 300000000,
    }
    corrected_gen_call = raw_rpc(
        "gen_call",
        [{
            "type": "deploy",
            "data": deploy_data,
            "from": DEPLOYER,
            "to": ZERO_ADDRESS,
            "status": "finalized",
            "fees": {"distribution": corrected_distribution, "feeValue": 94353600002588},
            "feeValue": 94353600002588,
            "feesDistribution": corrected_distribution,
        }],
    )

    known = tx_snapshot(KNOWN_TX)
    procura = tx_snapshot(PROCURA_TX)
    known_tx = result_of(known["transaction"])
    known_fee_accounting = known_tx.get("data", {}).get("fee_accounting", {}) if isinstance(known_tx, dict) else {}
    known_fee_report = known_fee_accounting.get("execution_fee_report", {})
    known_fees = known_tx.get("fees") if isinstance(known_tx, dict) else None
    known_distribution = known_fees.get("distribution") if isinstance(known_fees, dict) else None
    known_code = (
        known_tx.get("contract_code")
        if isinstance(known_tx, dict)
        else None
    )
    if not isinstance(known_code, str) and isinstance(known_tx, dict) and isinstance(known_tx.get("data"), dict):
        known_code = known_tx["data"].get("contract_code")
    known_code_bytes = base64.b64decode(known_code) if isinstance(known_code, str) else b""
    known_consensus = known_tx.get("consensus_data", {}) if isinstance(known_tx, dict) else {}
    known_leader_receipt = known_consensus.get("leader_receipt", []) if isinstance(known_consensus, dict) else []
    if isinstance(known_leader_receipt, list):
        known_leader_receipt = known_leader_receipt[0] if known_leader_receipt else {}
    if not isinstance(known_leader_receipt, dict):
        known_leader_receipt = {}

    procura_tx = result_of(procura["transaction"])
    procura_fee_accounting = procura_tx.get("data", {}).get("fee_accounting", {}) if isinstance(procura_tx, dict) else {}
    procura_fee_report = procura_fee_accounting.get("execution_fee_report", {})
    procura_code = procura_tx.get("contract_code") if isinstance(procura_tx, dict) else None
    if not isinstance(procura_code, str) and isinstance(procura_tx, dict) and isinstance(procura_tx.get("data"), dict):
        procura_code = procura_tx["data"].get("contract_code")
    procura_code_bytes = base64.b64decode(procura_code) if isinstance(procura_code, str) else b""

    fee_result, fee_envelope = fee_estimate(__import__("scripts.studio_live_qualification", fromlist=["Rpc"]).Rpc(RPC))

    evidence = {
        "captured_at": utc_now(),
        "read_only": True,
        "network": NETWORK,
        "rpc": RPC,
        "chain_id_expected": CHAIN_ID,
        "chain_id_rpc": chain,
        "deployer": DEPLOYER,
        "source": {
            "path": str(CONTRACT.relative_to(ROOT)),
            "sha256": source_sha,
            "byte_length": len(source),
            "runner_header_present": source.splitlines()[0].decode("utf-8").strip(),
        },
        "local_schema": {
            "method_count": len(local_schema_value.get("methods", {})),
            "interface_method_count": len(local_interface.get("methods", {})),
        },
        "deployment_payload": {
            "calldata_sha256": deploy_calldata_sha,
            "payload_byte_length": (len(deploy_data) - 2) // 2,
        },
        "account": {"balance": balance, "latest_nonce": nonce_latest, "pending_nonce": nonce_pending},
        "fee_config": fee_config_record,
        "nonce_11_recovery": {
            "status": "NOT_RECOVERED",
            "reason": "No supported sender+nonce/history RPC returned a transaction; no local hash was found.",
            "probes": nonce_11_probes,
        },
        "nonce_12_known_transaction": known,
        "gen_call_fee_parity": {
            "normal_request": normal_gen_call,
            "corrected_full_fee_request": corrected_gen_call,
            "normal_result": result_of(normal_gen_call),
            "corrected_result": result_of(corrected_gen_call),
            "limitation": "gen_call returns source/parse success but does not enforce the live fee envelope on this RC endpoint",
        },
        "failed_deployment_derived": {
            "known_nonce": known_tx.get("nonce") if isinstance(known_tx, dict) else None,
            "source_code_byte_length": len(known_code_bytes),
            "source_code_sha256": sha256_bytes(known_code_bytes),
            "fees_distribution": known_distribution,
            "locked_prices": known_fees.get("locked") if isinstance(known_fees, dict) else None,
            "consumed_fees": known_fees.get("consumed") if isinstance(known_fees, dict) else None,
            "genvm_data_fees": known_leader_receipt.get("genvm_result", {}),
            "execution_fee_report": known_fee_report,
            "required_receipt_budget_lower_bound": 78628000000000,
            "submitted_receipt_capacity": 76548000000000,
            "receipt_budget_deficit": 2080000000000,
        },
        "procura_reference": {
            "address": PROCURA_ADDRESS,
            "transaction": procura,
            "source_code_byte_length": len(procura_code_bytes),
            "execution_fee_report": procura_fee_report,
            "fees_distribution": procura_tx.get("fees", {}).get("distribution") if isinstance(procura_tx, dict) else None,
            "locked_prices": procura_tx.get("fees", {}).get("locked") if isinstance(procura_tx, dict) else None,
            "consumed_fees": procura_tx.get("fees", {}).get("consumed") if isinstance(procura_tx, dict) else None,
        },
        "estimator": {"result": fee_result, "rpc_envelope": fee_envelope},
        "corrected_profile": {
            "distribution": corrected_distribution,
            "feeValue": 94353600002588,
            "basis": "post-failure execution receipt measurement with 20% padding",
        },
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    write_json(EVIDENCE / "studio-dev-forensics.json", evidence)
    write_json(EVIDENCE / "nonce-12-raw-receipt.json", known["receipt"])
    write_json(EVIDENCE / "procura-raw-receipt.json", procura["receipt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
