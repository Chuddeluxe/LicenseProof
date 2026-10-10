"""Perform the one authorized retry for the failed Case C adjudication.

This script is deliberately narrow: it cannot create a policy, manifest,
component, evidence record, or deployment.  It only retries the same frozen
Case C semantic identity after canonical proof that nonce 39 ended in
consensus disagreement without creating a successful review.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.continue_live_qualification import safe_semantic_preview, expected_vector
from scripts.live_qualification_direct import (
    LiveRun,
    QUALIFICATION_DIR,
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
    account_state,
    append_jsonl,
    gen_call_read,
    local_schema,
    parse_json_string,
)


ADDRESS = "0x27Ca7E9F92AB0e465420AA9F2583fB25c9355619"
POLICY_ID = "LP-LIVE-POLICY-20261009T235554Z"
MANIFEST_ID = "LP-LIVE-C-20261009T235554Z"
COMPONENT_ID = "licenseproof-case-c"
EVIDENCE_ID = "LP-LIVE-EVIDENCE-C"
FAILED_INTENT = QUALIFICATION_DIR / "case-c.case_c_adjudication.intent.json"
FAILED_TX = "0x0d253e540f555a8282fb857dbc0906f2e5426d45940f493b4536a9211eb44c92"
JOURNAL = "case-c.jsonl"


def main() -> int:
    runner = LiveRun()
    runner.acquire_lock()
    try:
        source = runner.root.joinpath("contracts", "LicenseProof.py").read_bytes()
        if hashlib.sha256(source).hexdigest() != EXPECTED_SOURCE_SHA:
            raise RuntimeError("frozen source precondition failed")
        if EXPECTED_RUNNER.encode("utf-8") not in source.splitlines()[0]:
            raise RuntimeError("exact runner header is missing")
        if runner.account.address.lower() != DEPLOYER.lower():
            raise RuntimeError("retry account does not match authorized deployer")
        runner.contract_address = ADDRESS
        if not FAILED_INTENT.exists():
            raise RuntimeError("the first failed Case C intent is missing")
        failed = json.loads(FAILED_INTENT.read_text(encoding="utf-8"))
        if (
            failed.get("protocol_tx_hash") != FAILED_TX
            or failed.get("pre_write_nonce") != 39
            or failed.get("broadcast_count") != 1
            or failed.get("successful") is not False
            or failed.get("finality", {}).get("state") != "finalized"
        ):
            raise RuntimeError("first failed Case C intent does not match the authorized retry condition")

        funds = account_state(runner.rpc)
        if funds["latest_nonce"] != funds["pending_nonce"]:
            raise RuntimeError(f"retry nonce precondition failed: {funds}")
        if runner.account.address.lower() != funds["address"].lower():
            raise RuntimeError("RPC account differs from configured signer")

        policy = read_policy(runner.rpc, ADDRESS, POLICY_ID)
        manifest = read_manifest(runner.rpc, ADDRESS, MANIFEST_ID)
        component = read_component(runner.rpc, ADDRESS, COMPONENT_ID)
        evidence = read_evidence(runner.rpc, ADDRESS, EVIDENCE_ID)
        if policy.get("state") != "FROZEN" or manifest.get("state") != "REVIEWING":
            raise RuntimeError("retry identity is not legally retryable")
        if component.get("state") != "UNREVIEWED":
            raise RuntimeError("Case C component is no longer unreviewed")
        if evidence.get("content_sha256") != "d8a6cc31abc16b6748c7a21f21611f5a1ec33f67d22ca23d7da1c19b95496bee":
            raise RuntimeError("Case C evidence hash changed")
        try:
            existing_review = read_review(runner.rpc, ADDRESS, COMPONENT_ID)
        except Exception:
            existing_review = None
        if existing_review not in (None, ""):
            raise RuntimeError("successful Case C review exists; retry would be result shopping")

        profile = proven_fee_profile()
        preview, vector = semantic_preflight(runner.rpc, ADDRESS, [MANIFEST_ID, COMPONENT_ID], profile)
        if vector is None:
            raise RuntimeError("retry semantic preflight returned no strict vector")
        expected_vector("C", vector)
        if preview.get("calldata_sha256") != failed.get("serialized_deploy_sha256"):
            raise RuntimeError("retry calldata does not match the failed frozen tuple")

        append_jsonl(QUALIFICATION_DIR / JOURNAL, {
            "phase": "semantic_retry_authorized",
            "case": "C",
            "reason": "MAJORITY_DISAGREE / UNDETERMINED consensus outcome; no successful review",
            "first_failed_tx": FAILED_TX,
            "canonical_record_absent": True,
            "identity_unchanged": True,
            "policy_hash": policy.get("policy_hash"),
            "manifest_hash": manifest.get("manifest_hash"),
            "component_package_hash": component.get("package_hash"),
            "evidence_sha256": evidence.get("content_sha256"),
            "semantic_schema_version": "licenseproof.semantic.v1",
            "preview": safe_semantic_preview(preview, vector),
            "timestamp": utc_now(),
        })

        result = runner.send_write(
            "CASE_C_ADJUDICATION_RETRY_1",
            "adjudicate_component",
            [MANIFEST_ID, COMPONENT_ID],
            profile,
            lambda: read_review(runner.rpc, ADDRESS, COMPONENT_ID),
            JOURNAL,
        )
        review = read_review(runner.rpc, ADDRESS, COMPONENT_ID)
        if review.get("final_result") != "INCOMPATIBLE":
            raise RuntimeError(f"Case C retry produced unexpected result: {review}")

        try:
            semantic_preflight(runner.rpc, ADDRESS, [MANIFEST_ID, COMPONENT_ID], profile)
        except Exception:
            replay_guard = "PASS"
        else:
            raise RuntimeError("Case C successful review replay guard was not rejected")

        finalized = runner.send_write(
            "CASE_C_MANIFEST_FINALIZED",
            "finalize_manifest",
            [MANIFEST_ID],
            profile,
            lambda: read_manifest(runner.rpc, ADDRESS, MANIFEST_ID),
            JOURNAL,
        )
        final_manifest = read_manifest(runner.rpc, ADDRESS, MANIFEST_ID)
        if final_manifest.get("state") != "FINALIZED" or final_manifest.get("final_result") != "INCOMPATIBLE":
            raise RuntimeError(f"Case C final manifest mismatch: {final_manifest}")
        output = {
            "case": "C",
            "first_failed_tx": FAILED_TX,
            "retry_tx": result.get("protocol_tx_hash"),
            "retry_nonce": result.get("pre_write_nonce"),
            "review": review,
            "manifest": final_manifest,
            "replay_guard": replay_guard,
            "finalize_tx": finalized.get("protocol_tx_hash"),
            "semantic_retries": 1,
            "timestamp": utc_now(),
        }
        (QUALIFICATION_DIR / "case-c-retry.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    finally:
        runner.release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
