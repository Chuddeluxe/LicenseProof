"""Safe Studio-dev deployment construction and one-shot submission primitives.

This module deliberately separates transaction construction from submission.  It
uses the installed genlayer-py 0.19.0rc2 encoding and fee-resolution helpers,
but does not call the SDK's private ``_send_transaction`` helper: that helper
waits for the EVM receipt before returning the protocol transaction id, which
leaves a gap in which a broadcasted hash cannot be durably recorded.

The sender below closes that gap with the transaction discipline used by the
successful Procura and CharterLock deployments:

    durable intent -> exactly one eth_sendRawTransaction -> durable EVM hash
    -> receipt/event recovery -> protocol finality -> canonical readback

The module has no CLI/stdout parsing and has no automatic deployment retry.
The command-line entry point is dry-run by default; a future broadcast must be
an explicit caller action after a fresh authorization.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from genlayer_py.abi import calldata
from genlayer_py.abi.transactions import serialize
from genlayer_py.chains.studio_devnet import studio_devnet
from genlayer_py import create_client
from genlayer_py.client import GenLayerClient
from genlayer_py.contracts.actions import (
    ADDRESS_ZERO,
    DISCARD,
    _encode_add_transaction_data,
    _prepare_transaction,
    _resolve_transaction_fees,
)
from genlayer_py.contracts.utils import make_calldata_object
from genlayer_py.transactions.actions import is_successful
from web3 import Web3


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "LicenseProof.py"
RPC = "https://studio-dev.genlayer.com/api"
NETWORK = "studio-dev"
CHAIN_ID = 61997
DEPLOYER = "0x33653e6e86807e41682d3346cdf648d6653384b1"
RUNNER = "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng"
EXPECTED_SOURCE_SHA = "354f840a54e57a215790fa70182938ade78f43b505bcf05f8ded37cd4c1135fd"
PROVEN_FEE_VALUE = 100000000000010352

PROVEN_DISTRIBUTION: dict[str, Any] = {
    "leaderTimeunitsAllocation": 100,
    "validatorTimeunitsAllocation": 200,
    "appealRounds": 0,
    "executionBudgetPerRound": 25000000000000000,
    "executionConsumed": 0,
    "totalMessageFees": 0,
    "rotations": [3],
    "maxPriceGenPerTimeUnit": 2,
    "storageFeeMaxGasPrice": 300000000,
    "receiptFeeMaxGasPrice": 300000000,
}


class DeploymentSafetyError(RuntimeError):
    """A deployment must stop instead of guessing or rebroadcasting."""


class Provider(Protocol):
    def make_request(self, method: str, params: list[Any]) -> dict[str, Any]: ...


class AddressOnly:
    """Small account-shaped value sufficient for SDK calldata construction."""

    def __init__(self, address: str) -> None:
        self.address = address


@dataclass(frozen=True)
class ProvenFeeProfile:
    distribution: dict[str, Any]
    fee_value: int

    def sdk_options(self) -> dict[str, Any]:
        return {"distribution": dict(self.distribution), "feeValue": self.fee_value}

    def as_json(self) -> dict[str, Any]:
        return {"distribution": dict(self.distribution), "feeValue": self.fee_value}


def proven_fee_profile() -> ProvenFeeProfile:
    return ProvenFeeProfile(dict(PROVEN_DISTRIBUTION), PROVEN_FEE_VALUE)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_sha(source: bytes | str) -> str:
    raw = source.encode("utf-8") if isinstance(source, str) else source
    return sha256_bytes(raw)


def json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "hex") and not isinstance(value, (str, int, float, bool)):
        try:
            return value.hex()
        except Exception:
            pass
    return value


def fsync_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically write a JSON state file and fsync both file and directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(json_safe(value), handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(json_safe(value), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("ab") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DeploymentSafetyError(f"state file is not an object: {path}")
    return value


def serialized_deploy(source: str) -> tuple[str, str]:
    constructor = calldata.encode(make_calldata_object(method=None, args=None, kwargs=None))
    serialized = serialize([source, constructor, False])
    return serialized, sha256_bytes(bytes.fromhex(serialized[2:]))


def _hex(value: Any) -> str:
    if isinstance(value, str):
        return value if value.startswith("0x") else "0x" + value
    return hex(int(value))


def build_deployment_request(
    client: GenLayerClient,
    source: str,
    sender: str,
    planned_nonce: int,
    fees: ProvenFeeProfile | None = None,
) -> dict[str, Any]:
    """Build the exact unsigned EVM request with genlayer-py's own encoders.

    This performs only reads (consensus ABI initialization, nonce, and gas
    estimation).  It never signs or submits a transaction.
    """
    profile = fees or proven_fee_profile()
    if source_sha(source) != EXPECTED_SOURCE_SHA:
        raise DeploymentSafetyError("frozen LicenseProof source SHA mismatch")
    sender_checksum = Web3.to_checksum_address(sender)
    observed_nonce = client.get_current_nonce(address=sender_checksum)
    if observed_nonce != planned_nonce:
        raise DeploymentSafetyError(f"planned nonce {planned_nonce} differs from remote nonce {observed_nonce}")
    client.initialize_consensus_smart_contract()
    transaction_fees = _resolve_transaction_fees(
        self=client,
        fees=profile.sdk_options(),
        num_of_initial_validators=client.chain.default_number_of_initial_validators,
    )
    serialized_data, calldata_digest = serialized_deploy(source)
    sender_account = AddressOnly(sender_checksum)
    encoded_data = _encode_add_transaction_data(
        self=client,
        sender_account=sender_account,
        recipient=ADDRESS_ZERO,
        consensus_max_rotations=3,
        data=serialized_data,
        valid_until=None,
        user_value=0,
        transaction_fees=transaction_fees,
    )
    # Match _prepare_transaction from the installed SDK while pinning the
    # already checked nonce so the dry-run output is explicit and inspectable.
    transaction = {
        "from": sender_checksum,
        "nonce": hex(planned_nonce),
        "data": encoded_data,
        "to": client.chain.consensus_main_contract["address"],
        "value": hex(transaction_fees["fee_value"] or 0),
        "gasPrice": 0,
        "chainId": client.chain.id,
    }
    transaction["gas"] = client.provider.make_request("eth_estimateGas", params=[transaction])["result"]
    return {
        "network": NETWORK,
        "chainId": CHAIN_ID,
        "rpc": RPC,
        "sender": sender_checksum,
        "nonce": planned_nonce,
        "source_sha256": source_sha(source),
        "runner": RUNNER,
        "serialized_deploy_sha256": calldata_digest,
        "serialized_deploy_bytes": (len(serialized_data) - 2) // 2,
        "consensus_calldata_sha256": sha256_bytes(bytes.fromhex(encoded_data[2:])),
        "fees": profile.as_json(),
        "transaction": json_safe(transaction),
    }


def build_signed_request(
    client: GenLayerClient,
    source: str,
    account: Any,
    fees: ProvenFeeProfile | None = None,
) -> tuple[dict[str, Any], str]:
    """Build/sign without submitting; returns request and raw signed hex."""
    profile = fees or proven_fee_profile()
    if source_sha(source) != EXPECTED_SOURCE_SHA:
        raise DeploymentSafetyError("frozen LicenseProof source SHA mismatch")
    client.initialize_consensus_smart_contract()
    transaction_fees = _resolve_transaction_fees(
        self=client,
        fees=profile.sdk_options(),
        num_of_initial_validators=client.chain.default_number_of_initial_validators,
    )
    serialized_data, calldata_digest = serialized_deploy(source)
    encoded_data = _encode_add_transaction_data(
        self=client,
        sender_account=account,
        recipient=ADDRESS_ZERO,
        consensus_max_rotations=3,
        data=serialized_data,
        valid_until=None,
        user_value=0,
        transaction_fees=transaction_fees,
    )
    transaction = _prepare_transaction(
        self=client,
        sender=account.address,
        recipient=client.chain.consensus_main_contract["address"],
        data=encoded_data,
        value=transaction_fees["fee_value"] or 0,
    )
    signed = account.sign_transaction(transaction)
    raw_hex = client.w3.to_hex(signed.raw_transaction)
    raw_bytes = bytes.fromhex(raw_hex[2:])
    return (
        {
            "network": NETWORK,
            "chainId": CHAIN_ID,
            "rpc": RPC,
            "sender": account.address,
            "nonce": int(transaction["nonce"], 16),
            "source_sha256": source_sha(source),
            "runner": RUNNER,
            "serialized_deploy_sha256": calldata_digest,
            "consensus_calldata_sha256": sha256_bytes(bytes.fromhex(encoded_data[2:])),
            "fees": profile.as_json(),
            "transaction": json_safe(transaction),
            "raw_transaction_sha256": sha256_bytes(raw_bytes),
        },
        raw_hex,
    )


def build_signed_call_request(
    client: GenLayerClient,
    address: str,
    function_name: str,
    args: list[Any],
    account: Any,
    fees: ProvenFeeProfile,
    value: int = 0,
) -> tuple[dict[str, Any], str]:
    """Build/sign a typed contract write without submitting it."""
    client.initialize_consensus_smart_contract()
    transaction_fees = _resolve_transaction_fees(
        self=client,
        fees=fees.sdk_options(),
        num_of_initial_validators=client.chain.default_number_of_initial_validators,
    )
    call_bytes = calldata.encode(make_calldata_object(method=function_name, args=args, kwargs=None))
    serialized_data = serialize([call_bytes, False])
    encoded_data = _encode_add_transaction_data(
        self=client,
        sender_account=account,
        recipient=Web3.to_checksum_address(address),
        consensus_max_rotations=3,
        data=serialized_data,
        valid_until=None,
        user_value=value,
        transaction_fees=transaction_fees,
    )
    transaction = _prepare_transaction(
        self=client,
        sender=account.address,
        recipient=client.chain.consensus_main_contract["address"],
        data=encoded_data,
        value=value + (transaction_fees["fee_value"] or 0),
    )
    signed = account.sign_transaction(transaction)
    raw_hex = client.w3.to_hex(signed.raw_transaction)
    raw_bytes = bytes.fromhex(raw_hex[2:])
    return (
        {
            "network": NETWORK,
            "chainId": CHAIN_ID,
            "rpc": RPC,
            "sender": account.address,
            "nonce": int(transaction["nonce"], 16),
            "to": Web3.to_checksum_address(address),
            "functionName": function_name,
            "args": args,
            "value": value,
            "source_sha256": EXPECTED_SOURCE_SHA,
            "runner": RUNNER,
            "serialized_deploy_sha256": sha256_bytes(bytes.fromhex(serialized_data[2:])),
            "consensus_calldata_sha256": sha256_bytes(bytes.fromhex(encoded_data[2:])),
            "fees": fees.as_json(),
            "transaction": json_safe(transaction),
            "raw_transaction_sha256": sha256_bytes(raw_bytes),
        },
        raw_hex,
    )


def raw_transaction_hash(raw_hex: str) -> str:
    """Return the EVM hash that the provider should return for raw_hex."""
    from eth_utils import keccak

    return "0x" + keccak(bytes.fromhex(raw_hex[2:] if raw_hex.startswith("0x") else raw_hex)).hex()


def nonce_state(client: GenLayerClient, sender: str) -> dict[str, int]:
    """Read both nonce views; a deployment candidate requires equality."""
    checksum = Web3.to_checksum_address(sender)
    latest = client.w3.eth.get_transaction_count(checksum, "latest")
    pending = client.w3.eth.get_transaction_count(checksum, "pending")
    if latest != pending:
        raise DeploymentSafetyError(f"sender has a pending transaction: latest={latest}, pending={pending}")
    return {"latest": latest, "pending": pending}


def _result_hash(response: dict[str, Any]) -> str:
    value = response.get("result")
    if not isinstance(value, str) or not value:
        raise DeploymentSafetyError(f"eth_sendRawTransaction returned no hash: {response}")
    return value


def protocol_hash_from_evm_receipt(client: GenLayerClient, evm_receipt: Any) -> str:
    """Extract the GenLayer protocol id from the SDK consensus event."""
    consensus = client.w3.eth.contract(abi=client.chain.consensus_main_contract["abi"])
    for event_name in ("NewTransaction", "CreatedTransaction"):
        event = consensus.get_event_by_name(event_name)
        events = event.process_receipt(evm_receipt, DISCARD)
        if events:
            return client.w3.to_hex(events[0]["args"]["txId"])
    raise DeploymentSafetyError(
        "EVM deployment submission succeeded but no NewTransaction/CreatedTransaction event was found"
    )


def contract_address_from_receipt(receipt: Any) -> str | None:
    """Read the address from the authoritative protocol receipt shape."""
    if not isinstance(receipt, dict):
        return None
    candidates = [
        receipt.get("contract_address"),
        receipt.get("contractAddress"),
        receipt.get("address"),
    ]
    data = receipt.get("data")
    if isinstance(data, dict):
        candidates.extend([data.get("contract_address"), data.get("contractAddress"), data.get("address")])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


class OneShotDeploymentSender:
    """Durable, one-broadcast sender with same-hash recovery semantics."""

    def __init__(self, provider: Provider, journal_path: Path, intent_path: Path | None = None) -> None:
        self.provider = provider
        self.journal_path = journal_path
        self.intent_path = intent_path or journal_path.with_name(journal_path.name + ".intent.json")

    def _existing_intent(self) -> dict[str, Any] | None:
        value = read_json(self.intent_path)
        if value is None:
            return None
        if value.get("status") in {"evm_hash_persisted", "protocol_hash_persisted", "reconciled"}:
            return value
        raise DeploymentSafetyError(
            "unresolved deployment intent exists; recover sender+nonce/hash before any submission"
        )

    def prepare_intent(self, request: dict[str, Any], raw_hex: str) -> dict[str, Any]:
        if self._existing_intent() is not None:
            raise DeploymentSafetyError("a prior deployment intent already has a hash; reconcile it")
        predicted_hash = raw_transaction_hash(raw_hex)
        intent = {
            "status": "broadcast_intent",
            "broadcast_count": 0,
            "label": request.get("label", "LICENSEPROOF_DEPLOYMENT"),
            "method": request.get("method", request.get("functionName", "deploy")),
            "arguments": request.get("args", []),
            "from": request["sender"],
            "network": request["network"],
            "chainId": request["chainId"],
            "pre_write_nonce": request["nonce"],
            "to": request.get("to"),
            "value": request.get("value", 0),
            "source_sha256": request["source_sha256"],
            "serialized_deploy_sha256": request["serialized_deploy_sha256"],
            "consensus_calldata_sha256": request["consensus_calldata_sha256"],
            "fee_distribution": request["fees"]["distribution"],
            "feeValue": request["fees"]["feeValue"],
            "predicted_evm_tx_hash": predicted_hash,
            "raw_transaction_sha256": request.get("raw_transaction_sha256"),
            "timestamp": utc_now(),
        }
        # Intent is durable before the provider can see a signed payload.
        fsync_json(self.intent_path, intent)
        append_jsonl(self.journal_path, {**intent, "phase": "broadcast_intent_persisted"})
        return intent

    def broadcast_once(self, request: dict[str, Any], raw_hex: str) -> str:
        intent = self.prepare_intent(request, raw_hex)
        # This is the only broadcast call in this module.  Any exception after
        # this line is uncertain and must be recovered, never resent.
        try:
            response = self.provider.make_request("eth_sendRawTransaction", [raw_hex])
        except Exception as exc:
            raise DeploymentSafetyError(
                "submission outcome is uncertain; recover the persisted nonce/hash, do not rebroadcast"
            ) from exc
        evm_hash = _result_hash(response)
        if evm_hash.lower() != intent["predicted_evm_tx_hash"].lower():
            raise DeploymentSafetyError("provider returned a different EVM hash than the signed payload")
        persisted = {**intent, "status": "evm_hash_persisted", "broadcast_count": 1, "evm_tx_hash": evm_hash, "timestamp": utc_now()}
        fsync_json(self.intent_path, persisted)
        append_jsonl(self.journal_path, {**persisted, "phase": "evm_hash_persisted"})
        return evm_hash

    def recover_same_hash(self) -> dict[str, Any]:
        intent = read_json(self.intent_path)
        if intent is None:
            raise DeploymentSafetyError("no deployment intent exists to recover")
        if intent.get("status") == "broadcast_intent":
            predicted = intent.get("predicted_evm_tx_hash")
            if not isinstance(predicted, str) or not predicted:
                raise DeploymentSafetyError("broadcast intent has no recoverable predicted hash")
            observed = self.provider.make_request("eth_getTransactionByHash", [predicted]).get("result")
            if observed is None:
                raise DeploymentSafetyError(
                    "broadcast intent has no observed hash; nonce may be consumed, so stop without rebroadcast"
                )
            intent = {**intent, "status": "evm_hash_persisted", "broadcast_count": 1, "evm_tx_hash": predicted, "recovered_read_only": True, "timestamp": utc_now()}
            fsync_json(self.intent_path, intent)
            append_jsonl(self.journal_path, {**intent, "phase": "evm_hash_recovered"})
        if intent.get("status") not in {"evm_hash_persisted", "protocol_hash_persisted", "reconciled"}:
            raise DeploymentSafetyError("deployment intent is not recoverable")
        return intent

    def reconcile_same_hash(
        self,
        client: GenLayerClient,
        *,
        readback: Callable[[str], Any] | None = None,
        timeout_seconds: int = 1200,
    ) -> dict[str, Any]:
        """Finalize and verify the exact persisted hash; never submit again."""
        intent = self.recover_same_hash()
        evm_hash = intent.get("evm_tx_hash") or intent.get("predicted_evm_tx_hash")
        if not isinstance(evm_hash, str) or not evm_hash:
            raise DeploymentSafetyError("recovery state has no EVM transaction hash")
        try:
            evm_receipt = client.w3.eth.wait_for_transaction_receipt(
                evm_hash, timeout=timeout_seconds, poll_latency=5
            )
        except Exception as exc:
            raise DeploymentSafetyError("EVM receipt recovery failed; do not rebroadcast") from exc
        if int(evm_receipt.get("status", 0)) != 1:
            terminal = {**intent, "status": "reconciled", "finality": "EVM_REVERTED", "execution_result": "EVM_REVERTED", "timestamp": utc_now()}
            fsync_json(self.intent_path, terminal)
            append_jsonl(self.journal_path, {**terminal, "phase": "terminal_execution_error"})
            raise DeploymentSafetyError("deployment EVM transaction reverted; do not rebroadcast")
        protocol_hash = protocol_hash_from_evm_receipt(client, evm_receipt)
        protocol_persisted = {**intent, "status": "protocol_hash_persisted", "broadcast_count": 1, "evm_tx_hash": evm_hash, "protocol_tx_hash": protocol_hash, "timestamp": utc_now()}
        fsync_json(self.intent_path, protocol_persisted)
        append_jsonl(self.journal_path, {**protocol_persisted, "phase": "protocol_hash_persisted"})
        try:
            protocol_receipt = client.wait_for_transaction_receipt(
                protocol_hash,
                wait_until="finalized",
                interval=5000,
                retries=max(1, timeout_seconds // 5),
                full_transaction=True,
            )
        except Exception as exc:
            raise DeploymentSafetyError("protocol finality recovery failed; do not rebroadcast") from exc
        successful = is_successful(protocol_receipt)
        address = contract_address_from_receipt(protocol_receipt)
        result = {
            "evm_tx_hash": evm_hash,
            "protocol_tx_hash": protocol_hash,
            "finality": json_safe(protocol_receipt.get("lifecycle") if isinstance(protocol_receipt, dict) else None),
            "execution_result": json_safe(protocol_receipt.get("tx_execution_result") if isinstance(protocol_receipt, dict) else None),
            "successful": successful,
            "contract_address": address,
        }
        if not successful:
            terminal = {**protocol_persisted, "status": "reconciled", **result, "timestamp": utc_now()}
            fsync_json(self.intent_path, terminal)
            append_jsonl(self.journal_path, {**terminal, "phase": "terminal_execution_error"})
            raise DeploymentSafetyError("deployment finalized without successful execution; do not rebroadcast")
        readback_target = address or intent.get("to")
        canonical = readback(readback_target) if readback is not None and isinstance(readback_target, str) else None
        settled = {**protocol_persisted, "status": "reconciled", **result, "canonical_readback": json_safe(canonical), "timestamp": utc_now()}
        fsync_json(self.intent_path, settled)
        append_jsonl(self.journal_path, {**settled, "phase": "reconciled"})
        return settled


def normalized_proven_profile() -> dict[str, Any]:
    profile = proven_fee_profile()
    return json_safe(profile.as_json())


def dry_run_record(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "DRY_RUN",
        "broadcast_count": 0,
        "transaction_broadcast": False,
        "request": request,
        "timestamp": utc_now(),
    }


def main() -> int:
    """Produce a corrected request; never broadcasts from the CLI default."""
    source = CONTRACT.read_text(encoding="utf-8")
    if source_sha(source) != EXPECTED_SOURCE_SHA:
        raise SystemExit("frozen contract SHA mismatch")
    client = create_client(studio_devnet, endpoint=RPC)
    # The request builder performs read-only SDK initialization and gas
    # estimation.  Nonce is intentionally supplied by a caller after a fresh
    # latest/pending equality check; this command is therefore explicit about
    # using the current pending nonce and cannot silently choose another.
    state = nonce_state(client, DEPLOYER)
    request = build_deployment_request(client, source, DEPLOYER, state["pending"], proven_fee_profile())
    output = ROOT / "evidence" / "predeploy" / "corrected-deployment-request.json"
    fsync_json(output, dry_run_record(request))
    print(json.dumps(json_safe(request), indent=2, sort_keys=True))
    print("TRANSACTION_BROADCAST: NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
