"""Explicitly guarded one-shot v1.1 Studio-dev deployment and qualification runner.

This runner is intentionally direct-SDK only.  It performs the final read-only
gates, sends exactly one corrected deployment, then executes the three approved
qualification cases with the same durable intent/hash/finality boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from eth_account import Account
from genlayer_py import create_client
from genlayer_py.chains.studio_devnet import studio_devnet

from scripts.studio_deploy_harness import (
    CONTRACT,
    DEPLOYER,
    EXPECTED_SOURCE_SHA,
    NETWORK,
    RPC,
    RUNNER,
    CHAIN_ID,
    DeploymentSafetyError,
    OneShotDeploymentSender,
    ProvenFeeProfile,
    append_jsonl,
    build_signed_call_request,
    build_signed_request,
    contract_address_from_receipt,
    fsync_json,
    nonce_state,
    proven_fee_profile,
    source_sha,
)
from scripts.studio_live_qualification import (
    Rpc,
    account_state,
    decode_calldata_value,
    deployed_source_sha,
    gen_call_read,
    local_schema,
    parse_json_string,
    semantic_candidates,
    serialized_call,
    serialized_deploy,
    successful_gen_call,
)


QUALIFICATION_DIR = Path(__file__).resolve().parents[1] / "evidence" / "qualification" / "v1.1"
SPDX_COMMIT = "31ba1a50e5397e00a304dbadc76531740e89ee48"
SPDX_HOST = "raw.githubusercontent.com"
SPDX_PREFIX = f"/spdx/license-list-data/{SPDX_COMMIT}/text/"
EXPECTED_LICENSES = {
    "MIT.txt": ("b05785f9f18e6716bab63424b11454513b9943a222595b70411009202fc592b5", 1078),
    "Elastic-2.0.txt": ("6448026f2e06ab3da9ed8ddda686694bba37179e88db92dea6d4aab516c957ea", 3802),
    "AGPL-3.0-only.txt": ("d8a6cc31abc16b6748c7a21f21611f5a1ec33f67d22ca23d7da1c19b95496bee", 34020),
}
V11_SEMANTIC_FIELDS = (
    "commercial_use_permitted", "hosted_service_permitted", "redistribution_permitted",
    "modification_permitted", "sublicensing_permitted", "derivative_distribution_permitted",
    "proprietary_distribution_permitted", "source_disclosure_required", "same_license_required",
    "attribution_required", "notice_preservation_required", "network_source_disclosure_required",
    "field_of_use_restriction", "field_of_use_conflicts_with_declared_use",
    "patent_condition_present", "evidence_sufficient", "applicability_clear",
)


def semantic_from_value(value: Any) -> dict[str, bool] | None:
    """Reject v1.0 15-key and any malformed v1.1 semantic previews."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if type(value) is not dict or set(value) != set(V11_SEMANTIC_FIELDS):
        return None
    if any(type(value[key]) is not bool for key in V11_SEMANTIC_FIELDS):
        return None
    return {key: value[key] for key in V11_SEMANTIC_FIELDS}


METHOD_PARAMS = {
    "create_release_policy": [
        "policy_id", "name", "commercial_use", "hosted_service", "redistribution",
        "modification", "sublicensing", "derivative_distribution", "source_model",
        "distribution_model", "policy_version",
    ],
    "create_manifest": ["manifest_id", "name", "release_version", "policy_id", "supersedes_manifest_id"],
    "add_component": [
        "component_id", "manifest_id", "name", "version", "component_type", "source_identifier",
        "package_hash", "declared_license_id", "license_evidence_id",
    ],
    "commit_license_evidence": [
        "evidence_id", "component_id", "authority_id", "authority_host", "authority_path_prefix",
        "source_url", "content_sha256", "content_byte_length", "published_at", "observed_at", "evidence_type",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return json_safe(value.value)
    return value


def load_firewall_account() -> Any:
    import win32cred  # Windows-only; loaded only after an explicitly approved --execute
    target = "genlayer-cli/account:firewall-only"
    credential = win32cred.CredRead(target, win32cred.CRED_TYPE_GENERIC)
    blob = credential.get("CredentialBlob")
    if not blob:
        raise RuntimeError("authorized firewall-only account is unavailable")
    private_key = blob.decode("utf-8") if isinstance(blob, bytes) else str(blob)
    try:
        account = Account.from_key(private_key)
    finally:
        private_key = ""
        blob = None
    if account.address.lower() != DEPLOYER.lower():
        raise RuntimeError("configured firewall-only account does not match authorized deployer")
    return account


def profile_from_rpc(value: dict[str, Any]) -> ProvenFeeProfile:
    distribution = value.get("distribution")
    if not isinstance(distribution, dict):
        raise RuntimeError("fee profile has no distribution")
    normalized: dict[str, Any] = {}
    for key, item in distribution.items():
        if key == "rotations":
            normalized[key] = [int(x) for x in item]
        else:
            normalized[key] = int(item)
    return ProvenFeeProfile(normalized, int(value["feeValue"]))


def fee_profile(rpc: Rpc) -> tuple[ProvenFeeProfile, dict[str, Any]]:
    result, envelope = rpc.call("sim_getFeeConfig", [])
    default = result.get("defaultFees") if isinstance(result, dict) else None
    if not isinstance(default, dict):
        raise RuntimeError("Studio-dev fee config has no defaultFees")
    return profile_from_rpc(default), {"response": envelope, "result": result}


def deploy_gen_call(rpc: Rpc, source: str, profile: ProvenFeeProfile) -> dict[str, Any]:
    data, digest = serialized_deploy(source)
    result, envelope = rpc.call(
        "gen_call",
        [{
            "type": "deploy", "data": data, "from": DEPLOYER,
            "to": "0x0000000000000000000000000000000000000000", "status": "finalized",
            "fees": profile.as_json(),
        }],
    )
    if not isinstance(result, str) or result.lower() != "00":
        raise RuntimeError(f"corrected deploy gen_call failed: {envelope}")
    return {"result": result, "response": envelope, "serialized_deploy_sha256": digest, "fees": profile.as_json()}


def write_gen_call(
    rpc: Rpc,
    address: str,
    method: str,
    args: list[Any],
    profile: ProvenFeeProfile,
) -> tuple[dict[str, Any], dict[str, bool] | None]:
    data, digest = serialized_call(method, args)
    result, envelope = rpc.call(
        "gen_call",
        [{
            "type": "write", "to": address, "from": DEPLOYER, "data": data,
            "status": "finalized", "fees": profile.as_json(),
        }],
    )
    semantic: dict[str, bool] | None = None
    for candidate in semantic_candidates(result):
        semantic = semantic_from_value(candidate)
        if semantic is not None:
            break
    return {"response": envelope, "result": result, "calldata_sha256": digest, "fees": profile.as_json()}, semantic


def semantic_preflight(
    rpc: Rpc,
    address: str,
    args: list[Any],
    profile: ProvenFeeProfile,
) -> tuple[dict[str, Any], dict[str, bool] | None]:
    """Run the Studio read-only simulation that exposes equivalence outputs."""
    data, digest = serialized_call("adjudicate_component", args)
    result, envelope = rpc.call(
        "sim_call",
        [{
            "type": "write", "to": address, "from": DEPLOYER, "data": data,
            "transaction_hash_variant": "latest-final", "fees": profile.as_json(),
        }],
    )
    if not isinstance(result, dict) or result.get("execution_result") != "SUCCESS":
        raise RuntimeError(
            "semantic simulation did not succeed: "
            f"execution_result={result.get('execution_result') if isinstance(result, dict) else None}, "
            f"result_keys={sorted(result.keys()) if isinstance(result, dict) else None}"
        )
    semantic = None
    for candidate in semantic_candidates(result):
        semantic = semantic_from_value(candidate)
        if semantic is not None:
            break
    return {"response": envelope, "result": result, "calldata_sha256": digest, "fees": profile.as_json()}, semantic


def assert_rejected_write(rpc: Rpc, address: str, method: str, args: list[Any], profile: ProvenFeeProfile) -> None:
    try:
        result, _ = write_gen_call(rpc, address, method, args, profile)
    except Exception:
        return
    if successful_gen_call(result["result"]):
        raise RuntimeError(f"read-only invalid-write simulation unexpectedly succeeded: {method}")


def fetch_pinned_spdx() -> dict[str, Any]:
    licenses: dict[str, Any] = {}
    for filename, (expected_sha, expected_length) in EXPECTED_LICENSES.items():
        url = f"https://{SPDX_HOST}{SPDX_PREFIX}{filename}"
        values: list[bytes] = []
        for _ in range(2):
            request = urllib.request.Request(url, headers={"User-Agent": "LicenseProof-live-harness"})
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    if response.status != 200:
                        raise RuntimeError(f"{url} returned HTTP {response.status}")
                    body = response.read()
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise RuntimeError(f"pinned SPDX fetch failed: {url}: {exc}") from exc
            if not body:
                raise RuntimeError(f"pinned SPDX evidence is empty: {url}")
            body.decode("utf-8")
            values.append(body)
        digest = hashlib.sha256(values[0]).hexdigest()
        if values[0] != values[1] or digest != expected_sha or len(values[0]) != expected_length:
            raise RuntimeError(f"pinned SPDX bytes changed or mismatched: {filename}")
        licenses[filename] = {"url": url, "sha256": digest, "bytes": len(values[0])}
    return {
        "commit": SPDX_COMMIT,
        "authority_id": f"spdx/license-list-data/{SPDX_COMMIT}",
        "authority_host": SPDX_HOST,
        "authority_path_prefix": SPDX_PREFIX,
        "licenses": licenses,
        "verified_at": utc_now(),
    }


def read_policy(rpc: Rpc, address: str, policy_id: str) -> dict[str, Any]:
    value = gen_call_read(rpc, address, "get_policy", [policy_id])
    return parse_json_string(value)


def read_manifest(rpc: Rpc, address: str, manifest_id: str) -> dict[str, Any]:
    return parse_json_string(gen_call_read(rpc, address, "get_manifest", [manifest_id]))


def read_component(rpc: Rpc, address: str, component_id: str) -> dict[str, Any]:
    return parse_json_string(gen_call_read(rpc, address, "get_component", [component_id]))


def read_evidence(rpc: Rpc, address: str, evidence_id: str) -> dict[str, Any]:
    return parse_json_string(gen_call_read(rpc, address, "get_evidence", [evidence_id]))


def read_review(rpc: Rpc, address: str, component_id: str) -> dict[str, Any]:
    return parse_json_string(gen_call_read(rpc, address, "get_component_review", [component_id]))


def read_result(rpc: Rpc, address: str, manifest_id: str) -> str:
    return str(gen_call_read(rpc, address, "get_manifest_result", [manifest_id]))


def resolve_contract_address(rpc: Rpc, protocol_hash: str, reconciliation: dict[str, Any]) -> str:
    address = reconciliation.get("contract_address")
    if isinstance(address, str) and address:
        return address
    transaction, _ = rpc.call("eth_getTransactionByHash", [protocol_hash])
    if isinstance(transaction, dict):
        for key in ("contract_address", "contractAddress", "address"):
            if isinstance(transaction.get(key), str) and transaction[key]:
                return transaction[key]
        data = transaction.get("data")
        if isinstance(data, dict):
            for key in ("contract_address", "contractAddress", "address"):
                if isinstance(data.get(key), str) and data[key]:
                    return data[key]
    raise RuntimeError("successful deployment has no recoverable contract address")


class LiveRun:
    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.lock = self.root / "evidence" / "qualification" / "v1.1" / ".live-run.lock"
        self.account = load_firewall_account()
        self.rpc = Rpc(RPC)
        self.client = create_client(studio_devnet, endpoint=RPC, account=self.account)
        self.contract_address: str | None = None
        self.write_count = 0
        self.successful_write_count = 0
        self.failed_semantic_attempts = 0
        self.semantic_retries = 0
        self.case_outputs: dict[str, Any] = {}
        self.journal_paths: dict[str, Path] = {}

    def acquire_lock(self) -> None:
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError("an active or unresolved LicenseProof qualification process exists") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "started": utc_now()}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def release_lock(self) -> None:
        try:
            self.lock.unlink()
        except FileNotFoundError:
            pass

    def preflight_schema(self, source: str) -> dict[str, Any]:
        code_hex = "0x" + source.encode("utf-8").hex()
        remote, envelope = self.rpc.call("gen_getContractSchemaForCode", [code_hex])
        schema, interface = local_schema()
        if remote != schema or set(remote.get("methods", {})) != set(interface.get("methods", {})):
            raise RuntimeError("remote source schema/interface parity failed")
        if len(remote.get("methods", {})) != 28:
            raise RuntimeError("remote source schema is not 28 methods")
        for method, names in METHOD_PARAMS.items():
            actual = [item[0] for item in remote["methods"][method]["params"]]
            if actual != names:
                raise RuntimeError(f"deployed/source parameter order mismatch for {method}: {actual}")
        return {"schema": remote, "response": envelope, "methods": 28, "parity": "PASS"}

    def send_write(
        self,
        label: str,
        method: str,
        args: list[Any],
        profile: ProvenFeeProfile,
        readback: Callable[[], Any] | None = None,
        journal_name: str = "deployment.jsonl",
    ) -> dict[str, Any]:
        if self.contract_address is None:
            raise RuntimeError("contract address is not set")
        state = nonce_state(self.client, self.account.address)
        funds = account_state(self.rpc)
        if funds["balance_wei"] <= profile.fee_value * 11 // 10:
            raise RuntimeError(f"insufficient balance for {label} fee envelope: {funds}")
        preview, semantic = write_gen_call(self.rpc, self.contract_address, method, args, profile)
        journal = QUALIFICATION_DIR / journal_name
        intent = journal.with_name(f"{journal.stem}.{label.lower()}.intent.json")
        append_jsonl(journal, {
            "phase": "preflight",
            "label": label,
            "method": method,
            "arguments": args,
            "from": self.account.address,
            "network": NETWORK,
            "chainId": CHAIN_ID,
            "pre_write_nonce": state["pending"],
            "fee_estimate": profile.as_json(),
            "semantic_preview": semantic,
            "preflight": preview,
            "timestamp": utc_now(),
        })
        request, raw_hex = build_signed_call_request(
            self.client, self.contract_address, method, args, self.account, profile,
        )
        request.update({"label": label, "method": method})
        if request["nonce"] != state["pending"]:
            raise RuntimeError(f"nonce changed while constructing {label}: {request['nonce']} != {state['pending']}")
        sender = OneShotDeploymentSender(self.client.provider, journal, intent)
        evm_hash = sender.broadcast_once(request, raw_hex)
        reconciliation = sender.reconcile_same_hash(
            self.client,
            readback=(lambda _target: readback()) if readback is not None else None,
        )
        if not reconciliation.get("successful"):
            raise RuntimeError(f"{label} did not finalize successfully")
        self.write_count += 1
        self.successful_write_count += 1
        return {"label": label, "method": method, "evm_tx_hash": evm_hash, **reconciliation, "semantic_preview": semantic}

    def run(self) -> dict[str, Any]:
        source = CONTRACT.read_text(encoding="utf-8")
        if source_sha(source) != EXPECTED_SOURCE_SHA or RUNNER not in source.splitlines()[0]:
            raise RuntimeError("frozen source precondition failed")
        self.acquire_lock()
        try:
            before = account_state(self.rpc)
            if before["address"].lower() != DEPLOYER.lower() or before["latest_nonce"] != before["pending_nonce"]:
                raise RuntimeError(f"deployer precondition failed: {before}")
            schema_preflight = self.preflight_schema(source)
            deployment_profile = proven_fee_profile()
            deployment_preview = deploy_gen_call(self.rpc, source, deployment_profile)
            # The Studio default profile is a known minimal simulation preset
            # (rotations=[0], 76.548e12 execution budget).  It is below the
            # measured 78.852e12 receipt envelope for these writes.  Use the
            # already proven full Studio-dev profile for every qualification
            # write and retain the current fee config as provenance.
            _, fee_config = fee_profile(self.rpc)
            regular_profile = deployment_profile
            # Each write is serialized and finalized before the next one, so
            # the protocol refund makes the required liquid balance the
            # largest single fee envelope plus margin, not the sum of all
            # sequential deposits.
            required_balance = max(deployment_profile.fee_value, regular_profile.fee_value) * 11 // 10
            if before["balance_wei"] <= required_balance * 11 // 10:
                raise RuntimeError("deployer balance lacks required qualification fee margin")
            current = account_state(self.rpc)
            if current["latest_nonce"] != current["pending_nonce"]:
                raise RuntimeError(f"deployer became non-quiescent before broadcast: {current}")
            deployment_journal = QUALIFICATION_DIR / "deployment.jsonl"
            deployment_intent = QUALIFICATION_DIR / "deployment.corrected.intent.json"
            existing_deployment = None
            if deployment_intent.exists():
                existing_deployment = json.loads(deployment_intent.read_text(encoding="utf-8"))
                if not isinstance(existing_deployment, dict):
                    raise RuntimeError("deployment intent is not an object")
                if existing_deployment.get("status") != "reconciled" or existing_deployment.get("broadcast_count") != 1:
                    raise RuntimeError("deployment intent is unresolved; recover the same hash and do not broadcast")
                if existing_deployment.get("source_sha256") != EXPECTED_SOURCE_SHA:
                    raise RuntimeError("existing deployment source SHA does not match the frozen source")
                if str(existing_deployment.get("from", "")).lower() != self.account.address.lower():
                    raise RuntimeError("existing deployment sender does not match the authorized account")
                deployment_evm_hash = str(existing_deployment.get("evm_tx_hash", ""))
                if not deployment_evm_hash:
                    raise RuntimeError("reconciled deployment intent has no EVM hash")
                deployment_reconciliation = existing_deployment
            else:
                request, raw_hex = build_signed_request(self.client, source, self.account, deployment_profile)
                request.update({"label": "DEPLOYMENT", "method": "deploy", "args": []})
                append_jsonl(deployment_journal, {
                    "event": "deployment_intent",
                    "phase": "preflight_ready",
                    "network": NETWORK,
                    "chainId": CHAIN_ID,
                    "sender": self.account.address,
                    "reserved_nonce": request["nonce"],
                    "source_path": str(CONTRACT),
                    "source_sha256": EXPECTED_SOURCE_SHA,
                    "runner": RUNNER,
                    "source_byte_length": len(source.encode("utf-8")),
                    "serialized_deploy_sha256": request["serialized_deploy_sha256"],
                    "consensus_calldata_sha256": request["consensus_calldata_sha256"],
                    "fee_distribution": deployment_profile.distribution,
                    "feeValue": deployment_profile.fee_value,
                    "timestamp": utc_now(),
                    "preflight": {"schema": schema_preflight, "gen_call_deploy": deployment_preview, "fee_config": fee_config},
                })
                deployment_sender = OneShotDeploymentSender(self.client.provider, deployment_journal, deployment_intent)
                deployment_evm_hash = deployment_sender.broadcast_once(request, raw_hex)
                deployment_reconciliation = deployment_sender.reconcile_same_hash(self.client)
            if not deployment_reconciliation.get("successful"):
                raise RuntimeError(f"deployment execution failed: {deployment_reconciliation}")
            address = resolve_contract_address(self.rpc, deployment_reconciliation["protocol_tx_hash"], deployment_reconciliation)
            self.contract_address = address
            source_match = deployed_source_sha(self.rpc, address)
            deployed_schema, _ = self.rpc.call("gen_getContractSchema", [address])
            local_schema_value, local_interface_value = local_schema()
            if deployed_schema != local_schema_value or len(deployed_schema.get("methods", {})) != 28:
                raise RuntimeError("deployed schema parity failed")
            info = parse_json_string(gen_call_read(self.rpc, address, "contract_info"))
            if info.get("contract_version") != "1.1.0" or info.get("semantic_schema_version") != "licenseproof.semantic.v1.1":
                raise RuntimeError(f"contract_info mismatch: {info}")
            deployment_record = {
                "event": "deployment_verified",
                "deployment_evm_tx_hash": deployment_evm_hash,
                "deployment_tx": deployment_reconciliation["protocol_tx_hash"],
                "contract_address": address,
                "finality": deployment_reconciliation.get("finality"),
                "execution_result": deployment_reconciliation.get("execution_result"),
                "source_sha256": source_match,
                "schema_methods": len(deployed_schema["methods"]),
                "contract_info": info,
                "timestamp": utc_now(),
            }
            append_jsonl(deployment_journal, deployment_record)
            spdx = fetch_pinned_spdx()
            fsync_json(QUALIFICATION_DIR / "spdx-provenance.json", spdx)

            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            policy_id = f"LP-V11-POLICY-{stamp}"
            policy_args = [policy_id, "LicenseProof declared proprietary SaaS policy", True, True, False, True, False, False, "PROPRIETARY", "HOSTED_ONLY", "1.1.0"]
            policy_create = self.send_write("POLICY_CREATED", "create_release_policy", policy_args, regular_profile, lambda: read_policy(self.rpc, address, policy_id))
            policy = read_policy(self.rpc, address, policy_id)
            if policy.get("state") != "DRAFT":
                raise RuntimeError(f"policy creation readback mismatch: {policy}")
            policy_freeze = self.send_write("POLICY_FROZEN", "freeze_release_policy", [policy_id], regular_profile, lambda: read_policy(self.rpc, address, policy_id))
            policy = read_policy(self.rpc, address, policy_id)
            if policy.get("state") != "FROZEN" or not policy.get("policy_hash"):
                raise RuntimeError(f"policy freeze readback mismatch: {policy}")

            cases = {
                "A": {"license": "MIT", "file": "MIT.txt", "manifest": f"LP-V11-A-{stamp}", "name": "MIT proprietary SaaS qualification", "release": "1.1.0-live-a", "source": "spdx:MIT", "declared": "MIT", "component": "licenseproof-case-a", "literal": "LICENSEPROOF-LIVE-CASE-A-COMPONENT-V11", "evidence": "LP-V11-EVIDENCE-A", "expected": "COMPATIBLE_WITH_OBLIGATIONS", "semantic": {"commercial_use_permitted": True, "hosted_service_permitted": True, "modification_permitted": True, "attribution_required": True, "notice_preservation_required": True, "evidence_sufficient": True, "applicability_clear": True}},
                "B": {"license": "Elastic-2.0", "file": "Elastic-2.0.txt", "manifest": f"LP-V11-B-{stamp}", "name": "Elastic hosted-service restriction qualification", "release": "1.1.0-live-b", "source": "spdx:Elastic-2.0", "declared": "Elastic-2.0", "component": "licenseproof-case-b", "literal": "LICENSEPROOF-LIVE-CASE-B-COMPONENT-V11", "evidence": "LP-V11-EVIDENCE-B", "expected": "INCONCLUSIVE", "semantic": {"applicability_clear": False, "evidence_sufficient": True}},
                "C": {"license": "AGPL-3.0-only", "file": "AGPL-3.0-only.txt", "manifest": f"LP-V11-C-{stamp}", "name": "AGPL network-source obligation qualification", "release": "1.1.0-live-c", "source": "spdx:AGPL-3.0-only", "declared": "AGPL-3.0-only", "component": "licenseproof-case-c", "literal": "LICENSEPROOF-LIVE-CASE-C-COMPONENT-V11", "evidence": "LP-V11-EVIDENCE-C", "expected": "INCONCLUSIVE", "semantic": {"applicability_clear": False, "evidence_sufficient": True}},
            }
            for key, case in cases.items():
                journal_name = f"case-{key.lower()}.jsonl"
                manifest_args = [case["manifest"], case["name"], case["release"], policy_id, ""]
                component_hash = hashlib.sha256(case["literal"].encode("utf-8")).hexdigest()
                evidence = spdx["licenses"][case["file"]]
                component_args = [case["component"], case["manifest"], case["component"], "1.1.0", "SOURCE_PACKAGE", case["source"], component_hash, case["declared"], case["evidence"]]
                evidence_args = [case["evidence"], case["component"], spdx["authority_id"], spdx["authority_host"], spdx["authority_path_prefix"], evidence["url"], evidence["sha256"], evidence["bytes"], "", "", "LICENSE_TEXT"]
                created = self.send_write(f"CASE_{key}_MANIFEST_CREATED", "create_manifest", manifest_args, regular_profile, lambda mid=case["manifest"]: read_manifest(self.rpc, address, mid), journal_name)
                added = self.send_write(f"CASE_{key}_COMPONENT_ADDED", "add_component", component_args, regular_profile, lambda cid=case["component"]: read_component(self.rpc, address, cid), journal_name)
                evidenced = self.send_write(f"CASE_{key}_EVIDENCE_COMMITTED", "commit_license_evidence", evidence_args, regular_profile, lambda eid=case["evidence"]: read_evidence(self.rpc, address, eid), journal_name)
                frozen = self.send_write(f"CASE_{key}_MANIFEST_FROZEN", "freeze_manifest", [case["manifest"]], regular_profile, lambda mid=case["manifest"]: read_manifest(self.rpc, address, mid), journal_name)
                started = self.send_write(f"CASE_{key}_REVIEW_STARTED", "begin_component_review", [case["manifest"], case["component"]], regular_profile, lambda cid=case["component"]: read_component(self.rpc, address, cid), journal_name)
                adjudication_args = [case["manifest"], case["component"]]
                semantic_preview_record, semantic_vector = semantic_preflight(self.rpc, address, adjudication_args, deployment_profile)
                if semantic_vector is None or any(semantic_vector.get(field) is not expected for field, expected in case["semantic"].items()):
                    raise RuntimeError(f"case {key} semantic preflight mismatch: {semantic_vector}")
                append_jsonl(QUALIFICATION_DIR / journal_name, {"phase": "semantic_preflight", "case": key, "preview": semantic_preview_record, "semantic_vector": semantic_vector, "timestamp": utc_now()})
                adjudicated = self.send_write(f"CASE_{key}_ADJUDICATION", "adjudicate_component", adjudication_args, deployment_profile, lambda cid=case["component"]: read_review(self.rpc, address, cid), journal_name)
                review = read_review(self.rpc, address, case["component"])
                result = review.get("final_result")
                if result != case["expected"]:
                    raise RuntimeError(f"case {key} component result mismatch: {result}")
                replay_pass = False
                try:
                    replay_preview, _ = semantic_preflight(self.rpc, address, adjudication_args, deployment_profile)
                    replay_pass = not successful_gen_call(replay_preview["result"])
                except Exception:
                    replay_pass = True
                if not replay_pass:
                    raise RuntimeError(f"case {key} successful review replay guard was not rejected")
                finalized = self.send_write(f"CASE_{key}_MANIFEST_FINALIZED", "finalize_manifest", [case["manifest"]], regular_profile, lambda mid=case["manifest"]: read_manifest(self.rpc, address, mid), journal_name)
                manifest = read_manifest(self.rpc, address, case["manifest"])
                if manifest.get("final_result") != case["expected"] or manifest.get("state") != "FINALIZED":
                    raise RuntimeError(f"case {key} manifest result mismatch: {manifest}")
                self.case_outputs[key] = {
                    "license": case["license"], "manifest": case["manifest"], "component": case["component"], "evidence": evidence,
                    "review": review, "semantic_vector": review.get("semantic_vector"), "component_result": result,
                    "manifest_result": manifest.get("final_result"), "adjudication_tx": adjudicated["protocol_tx_hash"],
                    "semantic_retries": 0, "replay_guard": "PASS",
                    "writes": [created, added, evidenced, frozen, started, adjudicated, finalized],
                }

            # Read-only immutability simulations after all successful results.
            assert_rejected_write(self.rpc, address, "freeze_release_policy", [policy_id], regular_profile)
            assert_rejected_write(self.rpc, address, "add_component", ["LP-LIVE-IMMUTABILITY", cases["A"]["manifest"], "x", "1", "OTHER", "x", "a" * 64, "MIT", cases["A"]["evidence"]], regular_profile)
            assert_rejected_write(self.rpc, address, "finalize_manifest", [cases["A"]["manifest"]], regular_profile)
            final_policy = read_policy(self.rpc, address, policy_id)
            final_manifests = {key: read_manifest(self.rpc, address, item["manifest"]) for key, item in cases.items()}
            all_ids = gen_call_read(self.rpc, address, "get_manifest_ids")
            audits = gen_call_read(self.rpc, address, "get_audit_events")
            after = account_state(self.rpc)
            summary = {
                "network": NETWORK, "chainId": CHAIN_ID, "rpc": RPC, "contract": address, "contractSha256": EXPECTED_SOURCE_SHA, "runner": RUNNER,
                "deployer": self.account.address, "balanceBefore": before["balance_wei"], "balanceAfter": after["balance_wei"],
                "nonceBefore": {"latest": before["latest_nonce"], "pending": before["pending_nonce"]},
                "nonceAfter": {"latest": after["latest_nonce"], "pending": after["pending_nonce"]},
                "deployment": {"evmTx": deployment_evm_hash, "tx": deployment_reconciliation["protocol_tx_hash"], "contractAddress": address, "finality": deployment_reconciliation.get("finality"), "execution": deployment_reconciliation.get("execution_result"), "profile": deployment_profile.as_json()},
                "spdx": spdx, "policy": {"id": policy_id, "hash": final_policy.get("policy_hash"), "state": final_policy.get("state")},
                "cases": self.case_outputs, "manifestIds": all_ids, "auditEvents": audits,
                "totalWrites": self.write_count + (0 if existing_deployment else 1), "successfulWrites": self.successful_write_count + (0 if existing_deployment else 1), "failedSemanticAttempts": self.failed_semantic_attempts, "semanticRetries": self.semantic_retries,
                "unexplainedWrites": 0 if after["latest_nonce"] == before["latest_nonce"] + self.write_count + (0 if existing_deployment else 1) and after["pending_nonce"] == after["latest_nonce"] else 1,
                "sourceParity": "PASS", "schemaParity": "PASS", "contractInfo": info, "finalManifests": final_manifests,
                "liveQualification": "VERIFIED", "readyForPublicRelease": "YES", "deploymentPerformed": "YES", "transactionBroadcast": "YES",
                "faucetUsed": "NO", "githubCreated": "NO", "pushPerformed": "NO", "verifiedAt": utc_now(),
            }
            fsync_json(QUALIFICATION_DIR / "summary.json", summary)
            return summary
        finally:
            self.release_lock()


def main() -> int:
    parser = argparse.ArgumentParser(description="LicenseProof v1.1 read-only or one-shot live qualification")
    parser.add_argument("--execute", action="store_true", help="requires independent deployment approval and may spend GEN")
    args = parser.parse_args()
    if not args.execute:
        # Default path loads no signer and makes no on-chain writes.
        from scripts.verify_studio_v11 import main as preflight
        return preflight()
    if os.environ.get("LICENSEPROOF_V11_DEPLOY_APPROVAL") != "APPROVE LICENSEPROOF V1.1 ONE-SHOT STUDIO-DEV DEPLOYMENT":
        raise SystemExit("Missing explicit v1.1 approval; no signer loaded and no transaction sent")
    result = LiveRun().run()
    print(json.dumps(json_safe(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
