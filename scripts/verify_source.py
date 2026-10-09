"""Load LicenseProof with the installed direct runner and print source facts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from gltest.direct import VMContext, deploy_contract

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from runner_compat import use_cached_5j_runner


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "LicenseProof.py"


def main() -> int:
    use_cached_5j_runner()
    digest = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    vm = VMContext()
    with vm.activate():
        contract = deploy_contract(CONTRACT, vm)
        contract_class = sys.modules["_contract_LicenseProof"].LicenseProof
        schema = json.loads(contract_class.__get_schema__())
        print("CONTRACT_SHA256=" + digest)
        print("SCHEMA_METHOD_COUNT=" + str(len(schema["methods"])))
        print(json.dumps(schema, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
