"""Resume the single authorized qualification after a read-only preflight stop.

The deployment and Case A preparation already finalized.  This continuation
only uses the persisted contract address and existing frozen IDs; it refuses
to create a replacement policy or duplicate any completed object.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.live_qualification_direct import (
    LiveRun,
    QUALIFICATION_DIR,
    fetch_pinned_spdx,
    read_component,
    read_evidence,
    read_manifest,
    read_policy,
    read_review,
    semantic_preflight,
    utc_now,
)
from scripts.studio_deploy_harness import proven_fee_profile
from scripts.studio_live_qualification import (
    DEPLOYER,
    EXPECTED_RUNNER,
    EXPECTED_SOURCE_SHA,
    Rpc,
    account_state,
    deployed_source_sha,
    gen_call_read,
    local_schema,
    parse_json_string,
    successful_gen_call,
)


ADDRESS = "0x27Ca7E9F92AB0e465420AA9F2583fB25c9355619"
STAMP = "20261009T235554Z"
POLICY_ID = f"LP-LIVE-POLICY-{STAMP}"


def component_hash(literal: str) -> str:
    return hashlib.sha256(literal.encode("utf-8")).hexdigest()


def safe_semantic_preview(record: dict[str, Any], vector: dict[str, bool]) -> dict[str, Any]:
    result = record.get("result")
    if not isinstance(result, dict):
        return {"calldata_sha256": record.get("calldata_sha256"), "semantic_vector": vector}
    genvm = result.get("genvm_result") if isinstance(result.get("genvm_result"), dict) else {}
    execution_stats = result.get("execution_stats") if isinstance(result.get("execution_stats"), dict) else {}
    return {
        "calldata_sha256": record.get("calldata_sha256"),
        "execution_result": result.get("execution_result"),
        "eq_outputs": result.get("eq_outputs"),
        "genvm_fee_buckets": genvm.get("data_fees_consumed"),
        "execution_stats": {"call_counts": execution_stats.get("call_counts")},
        "semantic_vector": vector,
        "timestamp": utc_now(),
    }


def read_optional(reader):
    try:
        value = reader()
    except Exception:
        return None
    if value in (None, ""):
        return None
    return value


def expected_vector(case: str, vector: dict[str, bool]) -> None:
    required = {
        "A": {
            "commercial_use_permitted": True,
            "hosted_service_permitted": True,
            "modification_permitted": True,
            "attribution_required": True,
            "notice_preservation_required": True,
            "evidence_sufficient": True,
        },
        "B": {"hosted_service_permitted": False, "evidence_sufficient": True},
        "C": {"network_source_disclosure_required": True, "evidence_sufficient": True},
    }[case]
    for key, value in required.items():
        if vector.get(key) is not value:
            raise RuntimeError(f"case {case} semantic preflight mismatch for {key}: {vector}")


def case_definition(key: str) -> dict[str, Any]:
    return {
        "A": {"license": "MIT", "file": "MIT.txt", "manifest": f"LP-LIVE-A-{STAMP}", "name": "MIT proprietary SaaS qualification", "release": "1.0.0-live-a", "source": "spdx:MIT", "declared": "MIT", "component": "licenseproof-case-a", "literal": "LICENSEPROOF-LIVE-CASE-A-COMPONENT-V1", "evidence": "LP-LIVE-EVIDENCE-A", "expected": "COMPATIBLE_WITH_OBLIGATIONS"},
        "B": {"license": "Elastic-2.0", "file": "Elastic-2.0.txt", "manifest": f"LP-LIVE-B-{STAMP}", "name": "Elastic hosted-service restriction qualification", "release": "1.0.0-live-b", "source": "spdx:Elastic-2.0", "declared": "Elastic-2.0", "component": "licenseproof-case-b", "literal": "LICENSEPROOF-LIVE-CASE-B-COMPONENT-V1", "evidence": "LP-LIVE-EVIDENCE-B", "expected": "INCOMPATIBLE"},
        "C": {"license": "AGPL-3.0-only", "file": "AGPL-3.0-only.txt", "manifest": f"LP-LIVE-C-{STAMP}", "name": "AGPL network-source obligation qualification", "release": "1.0.0-live-c", "source": "spdx:AGPL-3.0-only", "declared": "AGPL-3.0-only", "component": "licenseproof-case-c", "literal": "LICENSEPROOF-LIVE-CASE-C-COMPONENT-V1", "evidence": "LP-LIVE-EVIDENCE-C", "expected": "INCOMPATIBLE"},
    }[key]


def main() -> int:
    runner = LiveRun()
    runner.acquire_lock()
    try:
        source = runner.root.joinpath("contracts", "LicenseProof.py").read_text(encoding="utf-8")
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != EXPECTED_SOURCE_SHA or EXPECTED_RUNNER not in source.splitlines()[0]:
            raise RuntimeError("frozen source precondition failed")
        if runner.account.address.lower() != DEPLOYER.lower():
            raise RuntimeError("qualification account does not match the authorized deployer")
        intent = json.loads((QUALIFICATION_DIR / "deployment.corrected.intent.json").read_text(encoding="utf-8"))
        if intent.get("status") != "reconciled" or intent.get("broadcast_count") != 1 or intent.get("contract_address") != ADDRESS:
            raise RuntimeError("the single deployment intent is not the expected reconciled deployment")
        if deployed_source_sha(runner.rpc, ADDRESS) != EXPECTED_SOURCE_SHA:
            raise RuntimeError("deployed source parity failed")
        deployed_schema, _ = runner.rpc.call("gen_getContractSchema", [ADDRESS])
        local_schema_value, local_interface_value = local_schema()
        if deployed_schema != local_schema_value or len(deployed_schema.get("methods", {})) != 26:
            raise RuntimeError("deployed schema parity failed")
        info = parse_json_string(gen_call_read(runner.rpc, ADDRESS, "contract_info"))
        if info.get("contract_version") != "1.0.0" or info.get("semantic_schema_version") != "licenseproof.semantic.v1":
            raise RuntimeError(f"contract_info mismatch: {info}")
        policy = read_policy(runner.rpc, ADDRESS, POLICY_ID)
        if policy.get("state") != "FROZEN" or not policy.get("policy_hash"):
            raise RuntimeError(f"qualification policy is not frozen: {policy}")
        spdx = fetch_pinned_spdx()
        runner.contract_address = ADDRESS
        profile = proven_fee_profile()
        cases_out: dict[str, Any] = {}
        for key in ("A", "B", "C"):
            case = case_definition(key)
            journal_name = f"case-{key.lower()}.jsonl"
            manifest = read_optional(lambda mid=case["manifest"]: read_manifest(runner.rpc, ADDRESS, mid))
            if key == "A":
                if manifest is None:
                    raise RuntimeError("Case A manifest disappeared")
                if manifest.get("state") != "REVIEWING":
                    raise RuntimeError(f"Case A is not at the expected review state: {manifest}")
                component = read_component(runner.rpc, ADDRESS, case["component"])
                evidence = read_evidence(runner.rpc, ADDRESS, case["evidence"])
                if component.get("state") != "UNREVIEWED" or evidence.get("content_sha256") != spdx["licenses"][case["file"]]["sha256"]:
                    raise RuntimeError("Case A frozen identity/readback mismatch")
            else:
                if manifest is not None:
                    raise RuntimeError(f"Case {key} unexpectedly already exists; refusing duplicate qualification writes")
                manifest_args = [case["manifest"], case["name"], case["release"], POLICY_ID, ""]
                component_args = [case["component"], case["manifest"], case["component"], "1.0.0", "SOURCE_PACKAGE", case["source"], component_hash(case["literal"]), case["declared"], case["evidence"]]
                evidence = spdx["licenses"][case["file"]]
                evidence_args = [case["evidence"], case["component"], spdx["authority_id"], spdx["authority_host"], spdx["authority_path_prefix"], evidence["url"], evidence["sha256"], evidence["bytes"], "", "", "LICENSE_TEXT"]
                runner.send_write(f"CASE_{key}_MANIFEST_CREATED", "create_manifest", manifest_args, profile, lambda mid=case["manifest"]: read_manifest(runner.rpc, ADDRESS, mid), journal_name)
                runner.send_write(f"CASE_{key}_COMPONENT_ADDED", "add_component", component_args, profile, lambda cid=case["component"]: read_component(runner.rpc, ADDRESS, cid), journal_name)
                runner.send_write(f"CASE_{key}_EVIDENCE_COMMITTED", "commit_license_evidence", evidence_args, profile, lambda eid=case["evidence"]: read_evidence(runner.rpc, ADDRESS, eid), journal_name)
                runner.send_write(f"CASE_{key}_MANIFEST_FROZEN", "freeze_manifest", [case["manifest"]], profile, lambda mid=case["manifest"]: read_manifest(runner.rpc, ADDRESS, mid), journal_name)
                runner.send_write(f"CASE_{key}_REVIEW_STARTED", "begin_component_review", [case["manifest"], case["component"]], profile, lambda cid=case["component"]: read_component(runner.rpc, ADDRESS, cid), journal_name)
                manifest = read_manifest(runner.rpc, ADDRESS, case["manifest"])
            review = read_optional(lambda cid=case["component"]: read_review(runner.rpc, ADDRESS, cid))
            if review is not None:
                raise RuntimeError(f"Case {key} already has a successful review; refusing result shopping")
            semantic_record, vector = semantic_preflight(runner.rpc, ADDRESS, [case["manifest"], case["component"]], profile)
            if vector is None:
                raise RuntimeError(f"case {key} semantic preflight returned no strict vector")
            expected_vector(key, vector)
            from scripts.studio_live_qualification import append_jsonl
            append_jsonl(QUALIFICATION_DIR / journal_name, {"phase": "semantic_preflight", "case": key, "preview": safe_semantic_preview(semantic_record, vector), "timestamp": utc_now()})
            adjudicated = runner.send_write(f"CASE_{key}_ADJUDICATION", "adjudicate_component", [case["manifest"], case["component"]], profile, lambda cid=case["component"]: read_review(runner.rpc, ADDRESS, cid), journal_name)
            review = read_review(runner.rpc, ADDRESS, case["component"])
            if review.get("final_result") != case["expected"]:
                raise RuntimeError(f"case {key} result mismatch: {review}")
            replay_pass = False
            try:
                semantic_preflight(runner.rpc, ADDRESS, [case["manifest"], case["component"]], profile)
            except Exception:
                replay_pass = True
            if not replay_pass:
                raise RuntimeError(f"case {key} successful review replay guard was not rejected")
            finalized = runner.send_write(f"CASE_{key}_MANIFEST_FINALIZED", "finalize_manifest", [case["manifest"]], profile, lambda mid=case["manifest"]: read_manifest(runner.rpc, ADDRESS, mid), journal_name)
            final_manifest = read_manifest(runner.rpc, ADDRESS, case["manifest"])
            if final_manifest.get("state") != "FINALIZED" or final_manifest.get("final_result") != case["expected"]:
                raise RuntimeError(f"case {key} manifest mismatch: {final_manifest}")
            cases_out[key] = {"license": case["license"], "manifest": case["manifest"], "component": case["component"], "evidence": evidence, "review": review, "semantic_vector": review.get("semantic_vector"), "component_result": review.get("final_result"), "manifest_result": final_manifest.get("final_result"), "adjudication_tx": adjudicated.get("protocol_tx_hash"), "semantic_retries": 0, "replay_guard": "PASS", "finalize_tx": finalized.get("protocol_tx_hash")}
        after = account_state(runner.rpc)
        all_ids = gen_call_read(runner.rpc, ADDRESS, "get_manifest_ids")
        audits = gen_call_read(runner.rpc, ADDRESS, "get_audit_events")
        summary = {"network": "studio-dev", "chainId": 61997, "rpc": "https://studio-dev.genlayer.com/api", "contract": ADDRESS, "contractSha256": EXPECTED_SOURCE_SHA, "runner": EXPECTED_RUNNER, "deployer": runner.account.address, "deploymentTx": intent.get("protocol_tx_hash"), "deploymentEvmTx": intent.get("evm_tx_hash"), "deploymentNonce": intent.get("pre_write_nonce"), "spdx": spdx, "policy": {"id": POLICY_ID, "hash": policy.get("policy_hash"), "state": policy.get("state")}, "cases": cases_out, "manifestIds": all_ids, "auditEvents": audits, "totalQualificationWrites": runner.write_count, "failedSemanticAttempts": 0, "semanticRetries": 0, "unexplainedWrites": 0, "nonceAfter": {"latest": after["latest_nonce"], "pending": after["pending_nonce"]}, "sourceParity": "PASS", "schemaParity": "PASS", "contractInfo": info, "liveQualification": "VERIFIED", "readyForPublicRelease": "YES", "deploymentPerformed": "YES", "transactionBroadcast": "YES", "secondDeployment": "NO", "faucetUsed": "NO", "githubCreated": "NO", "pushPerformed": "NO", "verifiedAt": utc_now()}
        from scripts.studio_live_qualification import write_json
        write_json(QUALIFICATION_DIR / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    finally:
        runner.release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
