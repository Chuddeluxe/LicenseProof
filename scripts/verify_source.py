"""Fail-closed, read-only verification of the exact candidate source and runner."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from gltest.direct import VMContext, deploy_contract

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from runner_compat import use_cached_5j_runner


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "LicenseProof.py"
HASH_RECORD = ROOT / "docs" / "SOURCE_HASH.txt"
EXPECTED_RUNNER = "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng"


def pinned_sha() -> str:
    record = dict(
        item.split("=", 1)
        for line in HASH_RECORD.read_text(encoding="utf-8-sig").splitlines()
        if (item := line.strip()) and "=" in item
    )
    if record.get("CONTRACT") != "contracts/LicenseProof.py":
        raise RuntimeError("incorrect contract path in pinned source record")
    if record.get("RUNNER") != EXPECTED_RUNNER:
        raise RuntimeError("runner mismatch in pinned source record")
    digest = record.get("SHA256", "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise RuntimeError("invalid pinned SHA256")
    external = os.getenv("EXPECTED_CONTRACT_SHA256")
    if external and external != digest:
        raise RuntimeError("CI expected SHA does not match source record")
    return digest


def main() -> int:
    use_cached_5j_runner()
    digest = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    expected = pinned_sha()
    if digest != expected:
        raise SystemExit(f"SOURCE_SHA_MISMATCH actual={digest} expected={expected}")
    vm = VMContext()
    with vm.activate():
        contract = deploy_contract(CONTRACT, vm)
        cls = sys.modules["_contract_LicenseProof"].LicenseProof
        schema = json.loads(cls.__get_schema__())
    if len(schema["methods"]) != 28:
        raise SystemExit(f"unexpected schema method count {len(schema['methods'])}")
    print(f"CONTRACT_SHA256={digest}")
    print(f"SCHEMA_METHOD_COUNT={len(schema['methods'])}")
    print("SOURCE_SHA_VERIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
