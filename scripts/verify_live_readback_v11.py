"""Read-only canonical v1.1 deployment and qualification readback."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from scripts.live_qualification_v11 import QUALIFICATION_DIR
from scripts.studio_live_qualification import (
    RPC,
    Rpc,
    account_state,
    gen_call_read,
    parse_json_string,
)
from scripts.studio_deploy_harness import fsync_json


CONTRACT = "0x18A850BB8cA6cb0F75a5A9ab95362c12f1E349e6"


def main() -> int:
    summary = json.loads((QUALIFICATION_DIR / "summary.json").read_text(encoding="utf-8"))
    rpc = Rpc(RPC)
    info = parse_json_string(gen_call_read(rpc, CONTRACT, "contract_info"))
    policy_id = summary["policy"]["id"]
    cases = {
        key: {"manifest": value["manifest"], "component": value["component"]}
        for key, value in summary["cases"].items()
    }
    result: dict[str, object] = {
        "network": summary["network"],
        "chainId": summary["chainId"],
        "contract": CONTRACT,
        "contract_info": {
            "contract_version": info["contract_version"],
            "semantic_schema_version": info["semantic_schema_version"],
            "runner": info["runner"],
        },
        "policy": parse_json_string(gen_call_read(rpc, CONTRACT, "get_policy", [policy_id])),
        "policy_ids": gen_call_read(rpc, CONTRACT, "get_policy_ids"),
        "manifest_ids": gen_call_read(rpc, CONTRACT, "get_manifest_ids"),
        "cases": {},
    }
    for key, identifiers in cases.items():
        manifest = parse_json_string(gen_call_read(rpc, CONTRACT, "get_manifest", [identifiers["manifest"]]))
        component = parse_json_string(gen_call_read(rpc, CONTRACT, "get_component", [identifiers["component"]]))
        evidence = parse_json_string(gen_call_read(rpc, CONTRACT, "get_evidence", [component["license_evidence_id"]]))
        review = parse_json_string(gen_call_read(rpc, CONTRACT, "get_component_review", [identifiers["component"]]))
        result["cases"][key] = {
            "manifest": manifest,
            "component": component,
            "evidence": {
                "evidence_id": evidence["evidence_id"],
                "content_sha256": evidence["content_sha256"],
                "content_byte_length": evidence["content_byte_length"],
            },
            "review": review,
            "successor": gen_call_read(rpc, CONTRACT, "get_manifest_successor", [identifiers["manifest"]]),
        }
    events = gen_call_read(rpc, CONTRACT, "get_audit_events")
    page = gen_call_read(rpc, CONTRACT, "get_audit_events_page", [0, 100])
    result["audit"] = {"full_count": len(events), "page_count": len(page), "page_matches_full": page == events}
    code, _ = rpc.call("gen_getContractCode", [CONTRACT])
    result["deployed_source_sha256"] = hashlib.sha256(base64.b64decode(code, validate=True)).hexdigest()
    schema, _ = rpc.call("gen_getContractSchema", [CONTRACT])
    result["deployed_schema_methods"] = len(schema["methods"])
    result["account_after"] = account_state(rpc)
    fsync_json(QUALIFICATION_DIR / "readback-proof.json", result)
    print(json.dumps({
        "contract": CONTRACT,
        "contract_version": info["contract_version"],
        "semantic_schema_version": info["semantic_schema_version"],
        "deployed_source_sha256": result["deployed_source_sha256"],
        "deployed_schema_methods": result["deployed_schema_methods"],
        "policy_state": result["policy"]["state"],
        "case_results": {key: value["manifest"]["final_result"] for key, value in result["cases"].items()},
        "audit": result["audit"],
        "account_after": result["account_after"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
