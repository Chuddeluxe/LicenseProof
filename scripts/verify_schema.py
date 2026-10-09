"""Generate and verify the exact local GenVM schema/interface pair."""

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


def main() -> int:
    use_cached_5j_runner()
    vm = VMContext()
    with vm.activate():
        deploy_contract(CONTRACT, vm)
        cls = sys.modules["_contract_LicenseProof"].LicenseProof
        schema = json.loads(cls.__get_schema__())
    schema["methods"] = dict(sorted(schema["methods"].items()))
    interface = {
        "contract": "LicenseProof",
        "schema_source": "schema.json",
        "methods": {
            name: {
                "readonly": info["readonly"],
                "params": info["params"],
                "ret": info["ret"],
            }
            for name, info in schema["methods"].items()
        },
    }
    SCHEMA.write_text(json.dumps(schema, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    INTERFACE.write_text(json.dumps(interface, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    schema_methods = set(schema["methods"])
    interface_methods = set(interface["methods"])
    if schema_methods != interface_methods:
        raise SystemExit("schema/interface method parity failed")
    print(f"SCHEMA_METHODS={len(schema_methods)}")
    print("ABI_PARITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
