from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from gltest.direct import VMContext, deploy_contract

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_compat import use_cached_5j_runner


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path(os.environ.get("LICENSEPROOF_CONTRACT_PATH", str(ROOT / "contracts" / "LicenseProof.py")))
use_cached_5j_runner()


def fixture_text(name: str) -> str:
    return (ROOT / "fixtures" / "licenses" / name).read_text(encoding="utf-8")


def fixture_hash(name: str) -> str:
    return hashlib.sha256(fixture_text(name).encode("utf-8")).hexdigest()


def semantic(**overrides: bool) -> dict[str, bool]:
    fields = {
        "commercial_use_permitted": True,
        "hosted_service_permitted": True,
        "redistribution_permitted": True,
        "modification_permitted": True,
        "sublicensing_permitted": True,
        "derivative_distribution_permitted": True,
        "proprietary_distribution_permitted": True,
        "source_disclosure_required": False,
        "same_license_required": False,
        "attribution_required": False,
        "notice_preservation_required": False,
        "network_source_disclosure_required": False,
        "field_of_use_restriction": False,
        "field_of_use_conflicts_with_declared_use": False,
        "patent_condition_present": False,
        "evidence_sufficient": True,
        "applicability_clear": True,
    }
    fields.update(overrides)
    return fields


def mock_license(vm: VMContext, url: str, text: str, vector: dict[str, bool], *, final_url: str | None = None) -> None:
    response = {"status": 200, "body": text.encode("utf-8")}
    if final_url is not None:
        response = {"response": {"status": 200, "headers": {"x-genlayer-final-url": final_url.encode("utf-8")}, "body": text.encode("utf-8")}}
    vm.mock_web("^" + url.replace(".", r"\.") + "$", response)
    # genlayer-test 0.30's direct shim pre-decodes one JSON layer while the
    # current SDK's JSON decoder expects the response payload as text.
    vm.mock_llm("BEGIN_UNTRUSTED_LICENSE_TEXT", json.dumps(json.dumps(vector, separators=(",", ":"))))


@pytest.fixture
def env():
    vm = VMContext()
    with vm.activate():
        contract = deploy_contract(CONTRACT, vm)
        yield vm, contract


@pytest.fixture
def policy_args():
    return ("p1", "Paid SaaS policy", True, True, False, True, False, False, "PROPRIETARY", "HOSTED_ONLY", "1")
