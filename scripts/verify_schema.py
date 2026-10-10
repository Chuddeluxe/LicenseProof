"""Fail-closed read-only comparison of generated GenVM schema and committed ABI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from gltest.direct import VMContext, deploy_contract

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from runner_compat import use_cached_5j_runner


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "LicenseProof.py"
SCHEMA = ROOT / "contracts" / "schema.json"
INTERFACE = ROOT / "contracts" / "interface.json"


def compare_artifacts(derived_schema: dict, committed_schema: dict, committed_interface: dict) -> None:
    methods = dict(sorted(derived_schema["methods"].items()))
    expected_schema = {**derived_schema, "methods": methods}
    expected_interface = {
        "contract": "LicenseProof",
        "schema_source": "schema.json",
        "methods": {
            name: {
                "readonly": info["readonly"],
                "params": info["params"],
                "ret": info["ret"],
            }
            for name, info in methods.items()
        },
    }
    if committed_schema != expected_schema:
        raise ValueError("COMMITTED_SCHEMA_MISMATCH")
    if committed_interface != expected_interface:
        raise ValueError("COMMITTED_INTERFACE_MISMATCH")
    if len(methods) != 28:
        raise ValueError(f"unexpected schema method count {len(methods)}")


def main() -> int:
    use_cached_5j_runner()
    vm = VMContext()
    with vm.activate():
        deploy_contract(CONTRACT, vm)
        cls = sys.modules["_contract_LicenseProof"].LicenseProof
        generated = json.loads(cls.__get_schema__())
    try:
        committed_schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        committed_interface = json.loads(INTERFACE.read_text(encoding="utf-8"))
        compare_artifacts(generated, committed_schema, committed_interface)
    except (ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"ABI_PARITY=FAIL: {exc}") from exc
    print("SCHEMA_METHODS=28")
    print("ABI_PARITY=PASS")
    print("READ_ONLY_SCHEMA_VERIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
