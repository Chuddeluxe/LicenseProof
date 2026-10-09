"""Single-deployment Studio-dev qualification harness for LicenseProof.

This harness intentionally keeps signing inside the already configured GenLayer
CLI account. It never reads, prints, exports, or stores private key material.
All RPC reads are performed directly or through genlayer-py 0.19.0rc2. Every
broadcast is one subprocess invocation, and its protocol hash is journaled and
fsynced before the harness advances to finality or the next write.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genlayer_py.abi import calldata
from genlayer_py.abi.transactions import serialize
from genlayer_py.chains.studio_devnet import studio_devnet
from genlayer_py.client import GenLayerClient
from genlayer_py.contracts.utils import make_calldata_object
from genlayer_py.transactions.actions import is_successful


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "LicenseProof.py"
LOCAL_SCHEMA = ROOT / "contracts" / "schema.json"
LOCAL_INTERFACE = ROOT / "contracts" / "interface.json"
QUALIFICATION_DIR = ROOT / "evidence" / "qualification"

RPC = "https://studio-dev.genlayer.com/api"
NETWORK = "studio-dev"
CHAIN_ID = 61997
DEPLOYER = "0x33653e6e86807e41682d3346cdf648d6653384b1"
EXPECTED_HEAD = "34745d0e9543974754966134e55f761870b33b0a"
EXPECTED_SOURCE_SHA = "77fb66904787baab72210276f29d6c0cc29831e2d243cecad5c2eb249146c0c4"
EXPECTED_RUNNER = "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng"
EXPECTED_VERSION = "1.0.0"
EXPECTED_SEMANTIC_SCHEMA = "licenseproof.semantic.v1"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
SEMANTIC_FIELDS = (
    "commercial_use_permitted",
    "hosted_service_permitted",
    "redistribution_permitted",
    "modification_permitted",
    "sublicensing_permitted",
    "derivative_distribution_permitted",
    "proprietary_distribution_permitted",
    "source_disclosure_required",
    "same_license_required",
    "attribution_required",
    "notice_preservation_required",
    "network_source_disclosure_required",
    "field_of_use_restriction",
    "patent_condition_present",
    "evidence_sufficient",
)
TX_HASH_RE = re.compile(r"(?:Transaction Hash|transaction hash):\s*(0x[0-9a-fA-F]{64})")


class QualificationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(json_safe(record), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("ab") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(json_safe(value), handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


class Rpc:
    def __init__(self, url: str) -> None:
        self.url = url
        self._next_id = 1000

    def call(self, method: str, params: list[Any]) -> tuple[Any, dict[str, Any]]:
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "LicenseProof-live-harness"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = response.read()
                envelope = json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise QualificationError(f"RPC {method} failed: {exc}") from exc
        if "error" in envelope:
            raise QualificationError(f"RPC {method} error: {envelope['error']}")
        return envelope.get("result"), envelope


def source_and_freeze() -> str:
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    if status:
        allowed_prefixes = ("evidence/qualification/", "docs/LIVE_", "scripts/studio_live_qualification.py")
        unexpected: list[str] = []
        for line in status.splitlines():
            path = line[3:] if len(line) >= 4 else line
            if " -> " in path:
                unexpected.append(line)
            elif not path.startswith(allowed_prefixes):
                unexpected.append(line)
        if unexpected:
            raise QualificationError(f"unexplained worktree changes before live run: {' | '.join(unexpected)}")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_HEAD, head],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if ancestry.returncode != 0:
        raise QualificationError(f"HEAD does not descend from the frozen predeploy candidate: {head}")
    source = CONTRACT.read_bytes()
    digest = sha256_bytes(source)
    if digest != EXPECTED_SOURCE_SHA:
        raise QualificationError(f"source SHA mismatch: {digest}")
    text = source.decode("utf-8")
    if EXPECTED_RUNNER not in text.splitlines()[0]:
        raise QualificationError("exact 5jyc dependency header is missing")
    return text


def account_state(rpc: Rpc) -> dict[str, Any]:
    chain_hex, _ = rpc.call("eth_chainId", [])
    chain_id = int(chain_hex, 16) if isinstance(chain_hex, str) else int(chain_hex)
    if chain_id != CHAIN_ID:
        raise QualificationError(f"wrong remote chain: {chain_id}")
    balance_hex, _ = rpc.call("eth_getBalance", [DEPLOYER, "latest"])
    latest_hex, _ = rpc.call("eth_getTransactionCount", [DEPLOYER, "latest"])
    pending_hex, _ = rpc.call("eth_getTransactionCount", [DEPLOYER, "pending"])
    latest = int(latest_hex, 16)
    pending = int(pending_hex, 16)
    return {
        "address": DEPLOYER,
        "chain_id": chain_id,
        "balance_hex": balance_hex,
        "balance_wei": int(balance_hex, 16),
        "latest_nonce": latest,
        "pending_nonce": pending,
    }


def resolve_spdx() -> dict[str, Any]:
    request = urllib.request.Request(
        "https://api.github.com/repos/spdx/license-list-data/commits?per_page=1",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "LicenseProof-live-harness"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            commits = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise QualificationError(f"SPDX commit resolution failed: {exc}") from exc
    if not isinstance(commits, list) or not commits or not isinstance(commits[0], dict):
        raise QualificationError("SPDX commit response was not a non-empty list")
    commit = str(commits[0].get("sha", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise QualificationError(f"invalid SPDX commit: {commit}")
    host = "raw.githubusercontent.com"
    prefix = f"/spdx/license-list-data/{commit}/text/"
    licenses: dict[str, Any] = {}
    for filename in ("MIT.txt", "Elastic-2.0.txt", "AGPL-3.0-only.txt"):
        url = f"https://{host}{prefix}{filename}"
        values: list[bytes] = []
        for _ in range(2):
            request = urllib.request.Request(url, headers={"User-Agent": "LicenseProof-live-harness"})
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    if response.status != 200:
                        raise QualificationError(f"{url} returned HTTP {response.status}")
                    values.append(response.read())
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise QualificationError(f"license fetch failed for {url}: {exc}") from exc
        if not values[0] or values[0] != values[1]:
            raise QualificationError(f"unstable repeated SPDX bytes for {url}")
        try:
            text = values[0].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise QualificationError(f"non-UTF-8 SPDX text for {url}") from exc
        licenses[filename] = {
            "url": url,
            "sha256": sha256_bytes(values[0]),
            "byte_length": len(values[0]),
            "text": text,
        }
    return {
        "commit": commit,
        "authority_id": f"spdx/license-list-data/{commit}",
        "authority_host": host,
        "authority_path_prefix": prefix,
        "licenses": licenses,
        "resolved_at": utc_now(),
    }


def local_schema() -> tuple[dict[str, Any], dict[str, Any]]:
    return json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8")), json.loads(LOCAL_INTERFACE.read_text(encoding="utf-8"))


def normalized_method(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "params": value.get("params", []),
        "kwparams": value.get("kwparams", {}),
        "readonly": value["readonly"],
        "ret": value["ret"],
        "payable": value.get("payable", False),
    }


def schema_from_source(rpc: Rpc, source: str) -> dict[str, Any]:
    code_hex = "0x" + source.encode("utf-8").hex()
    remote, _ = rpc.call("gen_getContractSchemaForCode", [code_hex])
    schema, interface = local_schema()
    if len(remote.get("methods", {})) != 26:
        raise QualificationError("remote source schema did not return 26 methods")
    if remote != schema:
        raise QualificationError("remote source schema differs from contracts/schema.json")
    interface_methods = interface["methods"]
    if {
        key: normalized_method(value) for key, value in remote["methods"].items()
    } != {
        key: normalized_method(value) for key, value in interface_methods.items()
    }:
        raise QualificationError("remote source schema differs from contracts/interface.json")
    return remote


def serialized_call(method: str | None, args: list[Any] | None = None) -> tuple[str, str]:
    encoded = calldata.encode(make_calldata_object(method=method, args=args, kwargs=None))
    serialized = serialize([encoded, False])
    return serialized, sha256_bytes(bytes.fromhex(serialized[2:]))


def serialized_deploy(source: str) -> tuple[str, str]:
    constructor = calldata.encode(make_calldata_object(method=None, args=None, kwargs=None))
    serialized = serialize([source, constructor, False])
    return serialized, sha256_bytes(bytes.fromhex(serialized[2:]))


def successful_gen_call(result: Any) -> bool:
    if isinstance(result, str):
        # Studio-dev returns a raw hex result for some calls. RPC errors are
        # raised by Rpc.call; a non-empty raw result is therefore a successful
        # simulation response, while deploy has its stricter check below.
        return bool(result)
    if not isinstance(result, dict):
        return False
    status = result.get("status")
    if isinstance(status, dict) and status.get("code") not in (None, 0):
        return False
    if result.get("execution_result") not in (None, "SUCCESS", "FINISHED_WITH_RETURN"):
        return False
    return True


def gen_call_deploy_preflight(rpc: Rpc, source: str) -> dict[str, Any]:
    data, digest = serialized_deploy(source)
    result, envelope = rpc.call(
        "gen_call",
        [{"type": "deploy", "data": data, "from": DEPLOYER, "to": ZERO_ADDRESS, "status": "finalized"}],
    )
    if not isinstance(result, str) or not (result.lower() == "00" or result.lower().startswith("00")):
        raise QualificationError(f"deployment gen_call preflight failed: {envelope}")
    return {"result": result, "response": envelope, "calldata_sha256": digest, "payload_hex_bytes": (len(data) - 2) // 2}


def fee_estimate(rpc: Rpc) -> tuple[dict[str, Any], dict[str, Any]]:
    result, envelope = rpc.call("sim_getFeeConfig", [])
    default = result.get("defaultFees") if isinstance(result, dict) else None
    if not isinstance(default, dict) or not isinstance(default.get("distribution"), dict):
        raise QualificationError("Studio-dev fee response has no complete defaultFees profile")
    fees = {
        "distribution": default["distribution"],
        "feeValue": default["feeValue"],
    }
    return {"response": envelope, "result": result}, fees


def extract_hex_data(result: Any) -> str | None:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("data", "result"):
            value = result.get(key)
            if isinstance(value, str):
                return value
    return None


def decode_calldata_value(value: str) -> Any:
    raw = value[2:] if value.startswith("0x") else value
    if not raw:
        return None
    candidates: list[bytes] = []
    try:
        candidates.append(bytes.fromhex(raw))
    except ValueError:
        return value
    if candidates[0].startswith(b"\x00"):
        candidates.append(candidates[0][1:])
    for candidate in candidates:
        try:
            return calldata.decode(candidate)
        except Exception:
            continue
    try:
        return json.loads(candidates[0].decode("utf-8"))
    except Exception:
        return value


def semantic_from_value(value: Any) -> dict[str, bool] | None:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        value = parsed
    if not isinstance(value, dict) or set(value) != set(SEMANTIC_FIELDS):
        return None
    if any(type(value[field]) is not bool for field in SEMANTIC_FIELDS):
        return None
    return {field: value[field] for field in SEMANTIC_FIELDS}


def semantic_candidates(result: Any) -> list[Any]:
    candidates: list[Any] = []
    if isinstance(result, dict):
        for key in ("eqOutputs", "eq_outputs", "equivalence_outputs"):
            values = result.get(key)
            if isinstance(values, list):
                candidates.extend(values)
        for key in ("data", "result"):
            if key in result:
                candidates.append(result[key])
    else:
        candidates.append(result)
    decoded: list[Any] = []
    for candidate in candidates:
        if isinstance(candidate, str) and re.fullmatch(r"(?:0x)?[0-9a-fA-F]+", candidate):
            decoded.append(decode_calldata_value(candidate))
        else:
            decoded.append(candidate)
    return decoded


def gen_call_write_preflight(rpc: Rpc, address: str, method: str, args: list[Any]) -> tuple[dict[str, Any], dict[str, bool] | None]:
    data, digest = serialized_call(method, args)
    result, envelope = rpc.call(
        "gen_call",
        [{"type": "write", "to": address, "from": DEPLOYER, "data": data, "status": "finalized"}],
    )
    if not successful_gen_call(result):
        raise QualificationError(f"write preflight failed for {method}: {envelope}")
    semantic = None
    for candidate in semantic_candidates(result):
        semantic = semantic_from_value(candidate)
        if semantic is not None:
            break
    return {"response": envelope, "result": result, "calldata_sha256": digest}, semantic


def gen_call_read(rpc: Rpc, address: str, method: str, args: list[Any] | None = None) -> Any:
    data, _ = serialized_call(method, args or [])
    result, envelope = rpc.call(
        "gen_call",
        [{"type": "read", "to": address, "from": DEPLOYER, "data": data, "status": "finalized"}],
    )
    if not successful_gen_call(result):
        raise QualificationError(f"read preflight failed for {method}: {envelope}")
    value = extract_hex_data(result)
    if value is None:
        return result
    return decode_calldata_value(value)


def parse_json_string(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise QualificationError(f"expected JSON string readback, got {value!r}")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise QualificationError(f"readback was not JSON: {value!r}") from exc
    if not isinstance(parsed, dict):
        raise QualificationError(f"readback JSON was not an object: {parsed!r}")
    return parsed


def find_node_cli() -> tuple[str, str]:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    node = Path(shutil.which("node") or (appdata / "npm" / "node.exe"))
    cli = appdata / "npm" / "node_modules" / "genlayer" / "dist" / "index.js"
    if not node.exists() or not cli.exists():
        raise QualificationError(f"installed GenLayer CLI runtime not found: {node} / {cli}")
    return str(node), str(cli)


def scalar_arg(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class LiveWriter:
    def __init__(self, rpc: Rpc, client: GenLayerClient, node: str, cli: str) -> None:
        self.rpc = rpc
        self.client = client
        self.node = node
        self.cli = cli

    def reconcile(self, tx_hash: str, timeout_seconds: int = 1200) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last: Any = None
        while time.monotonic() < deadline:
            try:
                tx = self.client.get_transaction(tx_hash)
            except Exception as exc:
                last = {"read_error": str(exc)}
                time.sleep(5)
                continue
            last = json_safe(tx)
            lifecycle = tx.get("lifecycle") if isinstance(tx, dict) else None
            state = lifecycle.get("state") if isinstance(lifecycle, dict) else None
            if state == "finalized":
                return {"transaction": json_safe(tx), "successful": is_successful(tx)}
            if state == "canceled":
                return {"transaction": json_safe(tx), "successful": False}
            if state == "decided" and lifecycle.get("outcome") in {
                "undetermined",
                "validators_timeout",
                "leader_timeout",
            }:
                return {"transaction": json_safe(tx), "successful": False}
            time.sleep(5)
        raise QualificationError(f"timeout reconciling SAME transaction {tx_hash}: {last}")

    def broadcast_once(
        self,
        *,
        journal_path: Path,
        label: str,
        method: str,
        address: str | None,
        args: list[Any],
        pre_write_nonce: int,
        calldata_digest: str,
        fee_result: dict[str, Any],
        deployment: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        fee_json = json.dumps(
            {
                "distribution": fee_result["result"]["defaultFees"]["distribution"],
                "feeValue": fee_result["result"]["defaultFees"]["feeValue"],
            },
            separators=(",", ":"),
        )
        if deployment:
            command = [
                self.node,
                self.cli,
                "deploy",
                "--contract",
                str(CONTRACT),
                "--rpc",
                RPC,
                "--wallet",
                "keystore",
                "--fees",
                fee_json,
            ]
        else:
            if address is None:
                raise QualificationError("write address is required")
            command = [
                self.node,
                self.cli,
                "write",
                address,
                method,
                "--rpc",
                RPC,
                "--wallet",
                "keystore",
                "--fees",
                fee_json,
                "--args",
                *[scalar_arg(value) for value in args],
            ]
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        output: list[str] = []
        hash_holder: dict[str, str] = {}
        hash_event = threading.Event()

        def read_output() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                output.append(line.rstrip())
                match = TX_HASH_RE.search(line)
                if match and "tx_hash" not in hash_holder:
                    hash_holder["tx_hash"] = match.group(1)
                    hash_event.set()

        reader = threading.Thread(target=read_output, name=f"licenseproof-{label}", daemon=True)
        reader.start()
        if not hash_event.wait(timeout=600):
            process.terminate()
            process.wait(timeout=30)
            raise QualificationError(f"{label} produced no transaction hash: {' | '.join(output[-20:])}")
        tx_hash = hash_holder["tx_hash"]
        initial_record = {
            "phase": "tx_hash_persisted",
            "label": label,
            "method": method,
            "arguments": args,
            "from": DEPLOYER,
            "network": NETWORK,
            "chainId": CHAIN_ID,
            "pre_write_nonce": pre_write_nonce,
            "calldata_sha256": calldata_digest,
            "fee_estimate": fee_result,
            "tx_hash": tx_hash,
            "finality": None,
            "execution_result": None,
            "canonical_readback": None,
            "timestamp": utc_now(),
        }
        append_jsonl(journal_path, initial_record)
        reconciled = self.reconcile(tx_hash)
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            # The protocol transaction has already been reconciled. Stop only
            # the CLI's local waiter; never start another broadcast.
            process.terminate()
            process.wait(timeout=30)
        reader.join(timeout=10)
        final_record = {
            **initial_record,
            "phase": "reconciled",
            "finality": reconciled["transaction"].get("lifecycle"),
            "execution_result": {
                "successful": reconciled["successful"],
                "tx_execution_result": reconciled["transaction"].get("tx_execution_result"),
                "tx_execution_result_name": reconciled["transaction"].get("tx_execution_result_name"),
            },
            "cli_exit_code": process.returncode,
            "cli_output_tail": output[-20:],
            "timestamp": utc_now(),
        }
        append_jsonl(journal_path, final_record)
        if not reconciled["successful"]:
            raise QualificationError(f"{label} finalized without successful execution: {final_record}")
        return tx_hash, final_record


def contract_address_from_transaction(rpc: Rpc, tx_hash: str) -> str:
    tx, _ = rpc.call("eth_getTransactionByHash", [tx_hash])
    if not isinstance(tx, dict):
        raise QualificationError(f"deployment transaction {tx_hash} not found")
    candidates = [
        tx.get("contract_address"),
        tx.get("contractAddress"),
        tx.get("data", {}).get("contract_address") if isinstance(tx.get("data"), dict) else None,
        tx.get("data", {}).get("contractAddress") if isinstance(tx.get("data"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and re.fullmatch(r"0x[0-9a-fA-F]{40}", candidate):
            return candidate
    raise QualificationError(f"deployment transaction has no contract address: {tx}")


def deployed_source_sha(rpc: Rpc, address: str) -> str:
    code, _ = rpc.call("gen_getContractCode", [address])
    if not isinstance(code, str):
        raise QualificationError("gen_getContractCode did not return a string")
    try:
        source = base64.b64decode(code, validate=True)
    except Exception as exc:
        raise QualificationError("deployed source was not valid base64") from exc
    digest = sha256_bytes(source)
    if digest != EXPECTED_SOURCE_SHA:
        raise QualificationError(f"deployed source SHA mismatch: {digest}")
    return digest


def expected_semantic(case: str, vector: dict[str, bool]) -> None:
    required: dict[str, bool]
    if case == "A":
        required = {
            "commercial_use_permitted": True,
            "hosted_service_permitted": True,
            "modification_permitted": True,
            "attribution_required": True,
            "notice_preservation_required": True,
            "evidence_sufficient": True,
        }
    elif case == "B":
        required = {"hosted_service_permitted": False, "evidence_sufficient": True}
    else:
        required = {"network_source_disclosure_required": True, "evidence_sufficient": True}
    for field, expected in required.items():
        if vector.get(field) is not expected:
            raise QualificationError(f"case {case} semantic preflight mismatch: {field}={vector.get(field)!r}, expected {expected}")


def read_policy(rpc: Rpc, address: str, policy_id: str) -> dict[str, Any]:
    return parse_json_string(gen_call_read(rpc, address, "get_policy", [policy_id]))


def read_manifest(rpc: Rpc, address: str, manifest_id: str) -> dict[str, Any]:
    return parse_json_string(gen_call_read(rpc, address, "get_manifest", [manifest_id]))


def read_component(rpc: Rpc, address: str, component_id: str) -> dict[str, Any]:
    return parse_json_string(gen_call_read(rpc, address, "get_component", [component_id]))


def read_review(rpc: Rpc, address: str, component_id: str) -> dict[str, Any] | None:
    value = gen_call_read(rpc, address, "get_component_review", [component_id])
    if value in (None, ""):
        return None
    return parse_json_string(value)


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise QualificationError(f"could not read resume record {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QualificationError(f"resume record {path} is not a JSON object")
    return value


def last_journal_transaction(path: Path) -> str | None:
    if not path.exists():
        return None
    latest: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except ValueError as exc:
            raise QualificationError(f"invalid qualification journal line in {path}: {exc}") from exc
        tx_hash = record.get("tx_hash") if isinstance(record, dict) else None
        if isinstance(tx_hash, str) and tx_hash:
            latest = tx_hash
    return latest


def perform_write(
    writer: LiveWriter,
    rpc: Rpc,
    address: str,
    journal_path: Path,
    label: str,
    method: str,
    args: list[Any],
    preflight: dict[str, Any],
    allow_semantic_retry: bool = False,
) -> tuple[str, dict[str, Any]]:
    attempts = 0
    while True:
        state = account_state(rpc)
        if state["latest_nonce"] != state["pending_nonce"]:
            raise QualificationError(f"pending nonce before {label}: {state}")
        fee_result, _fees = fee_estimate(rpc)
        tx_hash, record = writer.broadcast_once(
            journal_path=journal_path,
            label=label,
            method=method,
            address=address,
            args=args,
            pre_write_nonce=state["pending_nonce"],
            calldata_digest=preflight["calldata_sha256"],
            fee_result=fee_result,
        )
        if record["execution_result"]["successful"]:
            return tx_hash, record
        if not allow_semantic_retry or attempts >= 1:
            raise QualificationError(f"non-successful write cannot be retried: {record}")
        attempts += 1
        raise QualificationError("semantic retry requires canonical absence reconciliation before retry; automated path stopped safely")


def immutable_preflight(rpc: Rpc, address: str, method: str, args: list[Any]) -> bool:
    data, _ = serialized_call(method, args)
    try:
        result, envelope = rpc.call(
            "gen_call",
            [{"type": "write", "to": address, "from": DEPLOYER, "data": data, "status": "finalized"}],
        )
    except QualificationError:
        return True
    return not successful_gen_call(result) or "error" in envelope


def main() -> int:
    source = source_and_freeze()
    rpc = Rpc(RPC)
    client = GenLayerClient(studio_devnet)
    node, cli = find_node_cli()
    state_before = account_state(rpc)
    if state_before["latest_nonce"] != state_before["pending_nonce"]:
        raise QualificationError(f"signer has pending transactions: {state_before}")
    if state_before["address"].lower() != DEPLOYER.lower():
        raise QualificationError("configured deployer address mismatch")

    spdx = resolve_spdx()
    QUALIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    write_json(QUALIFICATION_DIR / "spdx-provenance.json", {**spdx, "source_sha256": EXPECTED_SOURCE_SHA})

    # Final, immediately-before-broadcast deployment preflight.
    schema = schema_from_source(rpc, source)
    deploy_preview = gen_call_deploy_preflight(rpc, source)
    deploy_fee_result, _deploy_fees = fee_estimate(rpc)
    write_json(
        QUALIFICATION_DIR / "deployment-preflight.json",
        {
            "timestamp": utc_now(),
            "network": NETWORK,
            "chainId": CHAIN_ID,
            "deployer": DEPLOYER,
            "source_sha256": EXPECTED_SOURCE_SHA,
            "schema_methods": len(schema["methods"]),
            "schema_parity": True,
            "gen_call_deploy": deploy_preview,
            "fee_estimate": deploy_fee_result,
        },
    )

    writer = LiveWriter(rpc, client, node, cli)
    deployment_path = QUALIFICATION_DIR / "deployment.jsonl"
    existing_deployment = load_json(QUALIFICATION_DIR / "deployment-result.json")
    deployment_tx = None
    deployment_record: dict[str, Any] | None = None
    if existing_deployment is not None:
        candidate = existing_deployment.get("deployment_tx")
        if not isinstance(candidate, str) or not candidate:
            raise QualificationError("deployment-result.json has no deployment transaction hash")
        deployment_tx = candidate
        reconciled = writer.reconcile(deployment_tx)
        if not reconciled["successful"]:
            raise QualificationError(f"existing deployment finalized unsuccessfully: {reconciled}")
        deployment_record = existing_deployment.get("deployment_record")
        if not isinstance(deployment_record, dict):
            deployment_record = reconciled
    else:
        journal_tx = last_journal_transaction(deployment_path)
        if journal_tx is not None:
            # A prior process reached the hash-persisted point. Reconcile that
            # exact hash and never invoke the deploy command again.
            deployment_tx = journal_tx
            reconciled = writer.reconcile(deployment_tx)
            if not reconciled["successful"]:
                raise QualificationError(f"existing deployment finalized unsuccessfully: {reconciled}")
            deployment_record = reconciled
        else:
            deployment_args: list[Any] = []
            _deployment_data, deployment_digest = serialized_deploy(source)
            deployment_tx, deployment_record = writer.broadcast_once(
                journal_path=deployment_path,
                label="DEPLOYMENT",
                method="deploy",
                address=None,
                args=deployment_args,
                pre_write_nonce=state_before["pending_nonce"],
                calldata_digest=deployment_digest,
                fee_result=deploy_fee_result,
                deployment=True,
            )
    assert deployment_tx is not None
    contract_address = (
        existing_deployment.get("contract_address")
        if isinstance(existing_deployment, dict)
        else None
    )
    if not isinstance(contract_address, str):
        contract_address = contract_address_from_transaction(rpc, deployment_tx)
    deployment_source_sha = deployed_source_sha(rpc, contract_address)
    deployed_schema, _ = rpc.call("gen_getContractSchema", [contract_address])
    if len(deployed_schema.get("methods", {})) != 26:
        raise QualificationError("deployed schema does not contain 26 methods")
    local_schema_value, local_interface_value = local_schema()
    if deployed_schema != local_schema_value:
        raise QualificationError("deployed schema differs from local schema")
    if {
        key: normalized_method(value) for key, value in deployed_schema["methods"].items()
    } != {
        key: normalized_method(value) for key, value in local_interface_value["methods"].items()
    }:
        raise QualificationError("deployed schema differs from local interface")
    info = parse_json_string(gen_call_read(rpc, contract_address, "contract_info"))
    if info.get("version") != EXPECTED_VERSION or info.get("semantic_schema_version") != EXPECTED_SEMANTIC_SCHEMA:
        raise QualificationError(f"deployed contract_info mismatch: {info}")

    deployment_summary = {
        "deployment_tx": deployment_tx,
        "contract_address": contract_address,
        "deployment_record": deployment_record,
        "deployed_source_sha256": deployment_source_sha,
        "deployed_schema_methods": len(deployed_schema["methods"]),
        "contract_info": info,
    }
    write_json(QUALIFICATION_DIR / "deployment-result.json", deployment_summary)

    state_path = QUALIFICATION_DIR / "qualification-state.json"
    resume_state = load_json(state_path) or {}
    stored_policy = resume_state.get("policy") if isinstance(resume_state, dict) else None
    policy_id = stored_policy.get("id") if isinstance(stored_policy, dict) else None
    if not isinstance(policy_id, str) or not policy_id:
        policy_id = f"LP-LIVE-POLICY-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    policy_args = [
        policy_id,
        "LicenseProof proprietary SaaS qualification",
        True,
        True,
        False,
        True,
        False,
        False,
        "PROPRIETARY",
        "HOSTED_ONLY",
        EXPECTED_VERSION,
    ]
    policy_tx = stored_policy.get("createTx") if isinstance(stored_policy, dict) else None
    freeze_tx = stored_policy.get("freezeTx") if isinstance(stored_policy, dict) else None
    policy = read_policy(rpc, contract_address, policy_id) if isinstance(stored_policy, dict) else None
    if policy is None:
        policy_preflight, _ = gen_call_write_preflight(rpc, contract_address, "create_release_policy", policy_args)
        policy_tx, _ = perform_write(writer, rpc, contract_address, deployment_path, "POLICY_CREATED", "create_release_policy", policy_args, policy_preflight)
        policy = read_policy(rpc, contract_address, policy_id)
        if policy.get("state") != "DRAFT":
            raise QualificationError(f"policy create readback mismatch: {policy}")
        write_json(state_path, {"policy": {"id": policy_id, "createTx": policy_tx}, "cases": {}})
    if policy.get("state") == "DRAFT":
        freeze_preflight, _ = gen_call_write_preflight(rpc, contract_address, "freeze_release_policy", [policy_id])
        freeze_tx, _ = perform_write(writer, rpc, contract_address, deployment_path, "POLICY_FROZEN", "freeze_release_policy", [policy_id], freeze_preflight)
        policy = read_policy(rpc, contract_address, policy_id)
    if policy.get("state") != "FROZEN" or not policy.get("policy_hash"):
        raise QualificationError(f"policy freeze readback mismatch: {policy}")
    policy_hash = policy["policy_hash"]

    cases = {
        "A": {
            "license": "MIT",
            "filename": "MIT.txt",
            "manifest_name": "MIT proprietary SaaS qualification",
            "release_version": "1.0.0-live-a",
            "source_identifier": "spdx:MIT",
            "declared_license_id": "MIT",
            "component": "licenseproof-case-a",
            "literal": "LICENSEPROOF-LIVE-CASE-A-COMPONENT-V1",
            "expected_result": "COMPATIBLE_WITH_OBLIGATIONS",
        },
        "B": {
            "license": "Elastic-2.0",
            "filename": "Elastic-2.0.txt",
            "manifest_name": "Elastic hosted-service restriction qualification",
            "release_version": "1.0.0-live-b",
            "source_identifier": "spdx:Elastic-2.0",
            "declared_license_id": "Elastic-2.0",
            "component": "licenseproof-case-b",
            "literal": "LICENSEPROOF-LIVE-CASE-B-COMPONENT-V1",
            "expected_result": "INCOMPATIBLE",
        },
        "C": {
            "license": "AGPL-3.0-only",
            "filename": "AGPL-3.0-only.txt",
            "manifest_name": "AGPL network-source obligation qualification",
            "release_version": "1.0.0-live-c",
            "source_identifier": "spdx:AGPL-3.0-only",
            "declared_license_id": "AGPL-3.0-only",
            "component": "licenseproof-case-c",
            "literal": "LICENSEPROOF-LIVE-CASE-C-COMPONENT-V1",
            "expected_result": "INCOMPATIBLE",
        },
    }
    qualification: dict[str, Any] = {
        "network": NETWORK,
        "chainId": CHAIN_ID,
        "contract": contract_address,
        "deploymentTx": deployment_tx,
        "contractSha256": EXPECTED_SOURCE_SHA,
        "runner": EXPECTED_RUNNER,
        "deployer": DEPLOYER,
        "spdx": {key: value for key, value in spdx.items() if key != "licenses"},
        "policy": {"id": policy_id, "hash": policy_hash, "state": policy["state"], "createTx": policy_tx, "freezeTx": freeze_tx},
        "cases": {},
    }

    for case_key, spec in cases.items():
        stored_cases = resume_state.get("cases", {}) if isinstance(resume_state, dict) else {}
        stored_case = stored_cases.get(case_key) if isinstance(stored_cases, dict) else None
        if isinstance(stored_case, dict):
            stored_manifest_id = stored_case.get("manifest")
            stored_component_id = stored_case.get("component")
            if not isinstance(stored_manifest_id, str) or not isinstance(stored_component_id, str):
                raise QualificationError(f"resume state for case {case_key} is incomplete")
            manifest = read_manifest(rpc, contract_address, stored_manifest_id)
            review = read_review(rpc, contract_address, stored_component_id)
            if manifest.get("state") != "FINALIZED" or manifest.get("final_result") != spec["expected_result"] or review is None:
                raise QualificationError(f"resume state for case {case_key} is not canonically finalized")
            replay_pass = immutable_preflight(rpc, contract_address, "adjudicate_component", [stored_manifest_id, stored_component_id])
            if not replay_pass:
                raise QualificationError(f"case {case_key} replay guard failed during resume")
            qualification["cases"][case_key] = stored_case
            continue
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        manifest_id = f"LP-LIVE-{case_key}-{suffix}"
        component_id = spec["component"]
        evidence_id = f"LP-LIVE-{case_key}-EVIDENCE-{suffix}"
        evidence = spdx["licenses"][spec["filename"]]
        package_hash = sha256_bytes(spec["literal"].encode("utf-8"))
        manifest_path = QUALIFICATION_DIR / f"case-{case_key.lower()}.jsonl"
        manifest_args = [manifest_id, spec["manifest_name"], spec["release_version"], policy_id, ""]
        preflight, _ = gen_call_write_preflight(rpc, contract_address, "create_manifest", manifest_args)
        create_tx, _ = perform_write(writer, rpc, contract_address, manifest_path, f"CASE_{case_key}_MANIFEST_CREATED", "create_manifest", manifest_args, preflight)
        manifest = read_manifest(rpc, contract_address, manifest_id)
        if manifest.get("state") != "DRAFT" or manifest.get("policy_id") != policy_id:
            raise QualificationError(f"case {case_key} manifest create mismatch: {manifest}")

        component_args = [component_id, manifest_id, spec["component"], "1.0.0", "SOURCE_PACKAGE", spec["source_identifier"], package_hash, spec["declared_license_id"], evidence_id]
        preflight, _ = gen_call_write_preflight(rpc, contract_address, "add_component", component_args)
        component_tx, _ = perform_write(writer, rpc, contract_address, manifest_path, f"CASE_{case_key}_COMPONENT_ADDED", "add_component", component_args, preflight)
        component = read_component(rpc, contract_address, component_id)
        if component.get("manifest_id") != manifest_id or component.get("package_hash") != package_hash:
            raise QualificationError(f"case {case_key} component create mismatch: {component}")

        evidence_args = [evidence_id, component_id, spdx["authority_id"], spdx["authority_host"], spdx["authority_path_prefix"], evidence["url"], evidence["sha256"], evidence["byte_length"], "", utc_now(), "LICENSE_TEXT"]
        preflight, _ = gen_call_write_preflight(rpc, contract_address, "commit_license_evidence", evidence_args)
        evidence_tx, _ = perform_write(writer, rpc, contract_address, manifest_path, f"CASE_{case_key}_EVIDENCE_COMMITTED", "commit_license_evidence", evidence_args, preflight)
        evidence_readback = parse_json_string(gen_call_read(rpc, contract_address, "get_evidence", [evidence_id]))
        if evidence_readback.get("content_sha256") != evidence["sha256"] or int(evidence_readback.get("content_byte_length", -1)) != evidence["byte_length"]:
            raise QualificationError(f"case {case_key} evidence readback mismatch: {evidence_readback}")

        preflight, _ = gen_call_write_preflight(rpc, contract_address, "freeze_manifest", [manifest_id])
        freeze_manifest_tx, _ = perform_write(writer, rpc, contract_address, manifest_path, f"CASE_{case_key}_MANIFEST_FROZEN", "freeze_manifest", [manifest_id], preflight)
        manifest = read_manifest(rpc, contract_address, manifest_id)
        if manifest.get("state") != "FROZEN" or not manifest.get("manifest_hash"):
            raise QualificationError(f"case {case_key} manifest freeze mismatch: {manifest}")

        preflight, _ = gen_call_write_preflight(rpc, contract_address, "begin_component_review", [manifest_id, component_id])
        begin_tx, _ = perform_write(writer, rpc, contract_address, manifest_path, f"CASE_{case_key}_REVIEW_STARTED", "begin_component_review", [manifest_id, component_id], preflight)
        manifest = read_manifest(rpc, contract_address, manifest_id)
        if manifest.get("state") != "REVIEWING":
            raise QualificationError(f"case {case_key} review begin mismatch: {manifest}")

        adjudicate_args = [manifest_id, component_id]
        adjudicate_preflight, semantic_preview = gen_call_write_preflight(rpc, contract_address, "adjudicate_component", adjudicate_args)
        if semantic_preview is None:
            raise QualificationError(f"case {case_key} semantic preview did not expose an exact vector")
        expected_semantic(case_key, semantic_preview)
        adjudication_tx, _ = perform_write(writer, rpc, contract_address, manifest_path, f"CASE_{case_key}_ADJUDICATION", "adjudicate_component", adjudicate_args, adjudicate_preflight, allow_semantic_retry=True)
        review = read_review(rpc, contract_address, component_id)
        if review is None:
            raise QualificationError(f"case {case_key} successful adjudication has no canonical review")
        semantic_vector = review.get("semantic_vector")
        if not isinstance(semantic_vector, dict):
            raise QualificationError(f"case {case_key} review has no semantic vector: {review}")
        expected_semantic(case_key, semantic_vector)
        if review.get("final_result") != spec["expected_result"]:
            raise QualificationError(f"case {case_key} deterministic component result mismatch: {review}")

        replay_pass = immutable_preflight(rpc, contract_address, "adjudicate_component", adjudicate_args)
        if not replay_pass:
            raise QualificationError(f"case {case_key} successful-result replay guard did not reject simulation")

        finalize_preflight, _ = gen_call_write_preflight(rpc, contract_address, "finalize_manifest", [manifest_id])
        finalize_tx, _ = perform_write(writer, rpc, contract_address, manifest_path, f"CASE_{case_key}_MANIFEST_FINALIZED", "finalize_manifest", [manifest_id], finalize_preflight)
        manifest = read_manifest(rpc, contract_address, manifest_id)
        if manifest.get("state") != "FINALIZED" or manifest.get("final_result") != spec["expected_result"]:
            raise QualificationError(f"case {case_key} final manifest mismatch: {manifest}")

        immutability = {
            "policy_freeze": immutable_preflight(rpc, contract_address, "freeze_release_policy", [policy_id]),
            "manifest_component_set": immutable_preflight(rpc, contract_address, "add_component", [f"{component_id}-MUTATION", manifest_id, "mutation", "0", "OTHER", "mutation", "a" * 64, "MIT", evidence_id]),
            "final_manifest_result": immutable_preflight(rpc, contract_address, "finalize_manifest", [manifest_id]),
        }
        if not all(immutability.values()):
            raise QualificationError(f"case {case_key} immutability simulation failed: {immutability}")
        qualification["cases"][case_key] = {
            "license": spec["license"],
            "url": evidence["url"],
            "evidence_sha256": evidence["sha256"],
            "evidence_byte_length": evidence["byte_length"],
            "manifest": manifest_id,
            "component": component_id,
            "evidence_id": evidence_id,
            "review": review.get("review_key"),
            "semantic_vector": semantic_vector,
            "semantic_preview": semantic_preview,
            "result": review["final_result"],
            "final_manifest_result": manifest["final_result"],
            "tx": {
                "manifest_create": create_tx,
                "component_add": component_tx,
                "evidence_commit": evidence_tx,
                "manifest_freeze": freeze_manifest_tx,
                "review_begin": begin_tx,
                "adjudication": adjudication_tx,
                "manifest_finalize": finalize_tx,
            },
            "semantic_retries": 0,
            "replay_guard": replay_pass,
            "immutability": immutability,
        }
        resume_state = {
            "policy": {
                "id": policy_id,
                "hash": policy_hash,
                "createTx": policy_tx,
                "freezeTx": freeze_tx,
            },
            "cases": {
                **(resume_state.get("cases", {}) if isinstance(resume_state.get("cases", {}), dict) else {}),
                case_key: qualification["cases"][case_key],
            },
        }
        write_json(state_path, resume_state)
        write_json(QUALIFICATION_DIR / f"case-{case_key.lower()}-readback.json", {"manifest": manifest, "review": review, "evidence": evidence_readback})

    # Final canonical readback surfaces.
    final_policy = read_policy(rpc, contract_address, policy_id)
    all_policy_ids = gen_call_read(rpc, contract_address, "get_policy_ids")
    all_manifest_ids = gen_call_read(rpc, contract_address, "get_manifest_ids")
    audit_events = gen_call_read(rpc, contract_address, "get_audit_events")
    qualification["canonical_readback"] = {
        "contract_info": info,
        "policy_ids": all_policy_ids,
        "manifest_ids": all_manifest_ids,
        "policy": final_policy,
        "audit_events": audit_events,
        "source_sha256": deployed_source_sha,
        "schema_methods": len(deployed_schema["methods"]),
    }
    write_json(QUALIFICATION_DIR / "summary.json", qualification)
    print(json.dumps({"deployment": deployment_summary, "qualification": qualification}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationError as exc:
        print(f"QUALIFICATION_STOP: {exc}", file=sys.stderr)
        raise SystemExit(2)
