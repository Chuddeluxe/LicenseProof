"""Run named security mutants against the local mutation test gate.

Every mutant is a concrete source transformation. A mutant is killed only when
the independent mutation suite fails against the transformed contract.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contracts" / "LicenseProof.py"


@dataclass(frozen=True)
class Mutant:
    name: str
    replacements: tuple[tuple[str, str], ...]


MUTANTS = (
    Mutant("remove_host_equality", ((
        '_require(normalized_host == authority_host, "source_url authority host mismatch")',
        '_require(True, "source_url authority host mismatch")',
    ),)),
    Mutant("remove_path_prefix_check", ((
        '_require(_path_inside(path, authority_path_prefix), "source_url path is outside authority prefix")',
        '_require(True, "source_url path is outside authority prefix")',
    ),)),
    Mutant("allow_http", ((
        '_require(parsed.scheme.lower() == "https", "source_url must use HTTPS")',
        '_require(True, "source_url must use HTTPS")',
    ),)),
    Mutant("skip_content_sha_comparison", ((
        '_require(digest == evidence["content_sha256"], "EVIDENCE_MISMATCH")',
        '_require(True, "EVIDENCE_MISMATCH")',
    ),)),
    Mutant("skip_content_length_comparison", ((
        '_require(len(body) == evidence["content_byte_length"], "EVIDENCE_MISMATCH")',
        '_require(True, "EVIDENCE_MISMATCH")',
    ),)),
    Mutant("remove_evidence_sufficient_gate", ((
        'if not vector["evidence_sufficient"]:',
        'if False:',
    ),)),
    Mutant("invert_commercial_compatibility", ((
        'if policy["commercial_use"] and not vector["commercial_use_permitted"]:',
        'if policy["commercial_use"] and vector["commercial_use_permitted"]:',
    ),)),
    Mutant("ignore_hosted_restriction", ((
        'if policy["hosted_service"] and not vector["hosted_service_permitted"]:',
        'if False:',
    ),)),
    Mutant("ignore_redistribution_restriction", ((
        'if policy["redistribution"] and not vector["redistribution_permitted"]:',
        'if False:',
    ),)),
    Mutant("ignore_modification_restriction", ((
        'if policy["modification"] and not vector["modification_permitted"]:',
        'if False:',
    ),)),
    Mutant("ignore_sublicensing_restriction", ((
        'if policy["sublicensing"] and not vector["sublicensing_permitted"]:',
        'if False:',
    ),)),
    Mutant("ignore_proprietary_restriction", ((
        'if policy["source_model"] == "PROPRIETARY" and distribution_relevant and not vector["proprietary_distribution_permitted"]:',
        'if False:',
    ),)),
    Mutant("ignore_network_source_restriction", ((
        'if policy["hosted_service"] and policy["source_model"] == "PROPRIETARY" and vector["network_source_disclosure_required"]:',
        'if False:',
    ),)),
    Mutant("remove_successful_replay_guard", (
        ('_require(component["state"] == "UNREVIEWED", "component review is already finalized")', '_require(True, "component review is already finalized")'),
        ('_require(component_id not in self.review_by_component, "successful review already exists")', '_require(True, "successful review already exists")'),
    )),
    Mutant("write_replay_identity_before_consensus", ((
        '        try:\n            result = gl.vm.run_nondet_default(leader, validator)',
        '        self.review_by_component[component_id] = review_key\n        try:\n            result = gl.vm.run_nondet_default(leader, validator)',
    ),)),
    Mutant("permit_manifest_mutation_after_freeze", ((
        '_require(manifest["state"] == "DRAFT", "manifest is not accepting components")',
        '_require(manifest["state"] in ("DRAFT", "FROZEN"), "manifest is not accepting components")',
    ),)),
    Mutant("permit_policy_mutation_after_freeze", ((
        '_require(policy["state"] == "DRAFT", "policy is not mutable")',
        '_require(policy["state"] in ("DRAFT", "FROZEN"), "policy is not mutable")',
    ),)),
    Mutant("allow_incomplete_manifest_finalization", ((
        '_require(int(manifest["reviewed_component_count"]) == len(components), "manifest has incomplete reviews")',
        '_require(True, "manifest has incomplete reviews")',
    ), (
        '_require(component["state"] == "FINALIZED", "component review is incomplete")',
        '_require(True, "component review is incomplete")',
    ), (
        '_require(review_key is not None and review_key != "", "component review is missing")',
        '_require(True, "component review is missing")',
    ), (
        '            review = self._record(self.review_records, str(review_key), "component review")',
        '            review = {"review_identity": {"manifest_hash": manifest["manifest_hash"]}, "final_result": "COMPATIBLE"}',
    ))),
    Mutant("map_technical_failure_to_compatible", ((
        '            raise gl.vm.UserError("ADJUDICATION_RETRYABLE") from exc',
        '            vector = {field: True for field in SEMANTIC_FIELDS}',
    ),)),
    Mutant("accept_extra_semantic_keys", ((
        '_require(set(value.keys()) == set(SEMANTIC_FIELDS), "semantic keys are not exact")',
        '_require(set(value.keys()) >= set(SEMANTIC_FIELDS), "semantic keys are not exact")',
    ),)),
    Mutant("accept_string_booleans", ((
        '_require(type(value[field]) is bool, f"semantic field {field} must be boolean")',
        '_require(isinstance(value[field], (bool, str)), f"semantic field {field} must be boolean")',
    ),)),
    Mutant("allow_malformed_sha", ((
        're.fullmatch(r"[0-9a-f]{64}", value)',
        're.fullmatch(r"[0-9a-fA-F]{1,64}", value)',
    ),)),
    Mutant("allow_evidence_replacement", (
        ('_require(evidence_id not in self.evidence_records, "duplicate evidence_id")', '_require(True, "duplicate evidence_id")'),
        ('_require(manifest["state"] == "DRAFT", "evidence is immutable after manifest freeze")', '_require(manifest["state"] in ("DRAFT", "FROZEN"), "evidence is immutable after manifest freeze")'),
    )),
    Mutant("allow_cross_issuer_supersession_claim", ((
        '_require(old["creator"] == _actor(), "only predecessor creator may claim supersession")',
        '_require(True, "only predecessor creator may claim supersession")',
    ),)),
    Mutant("allow_repeat_review_start", ((
        '_require(not self.review_started.get(component_id, False), "review already started")',
        '_require(True, "review already started")',
    ),)),
    Mutant("suppress_inconclusive_uncertainty", ((
        'if not vector["applicability_clear"]:',
        'if False:',
    ),)),
    Mutant("certify_unverified_multi_component_bundle", ((
        'if len(components) > 1 and final_result in ("COMPATIBLE", "COMPATIBLE_WITH_OBLIGATIONS"):',
        'if False:',
    ),)),
    Mutant("treat_any_field_use_restriction_as_conflict", ((
        'if vector["field_of_use_restriction"] and vector["field_of_use_conflicts_with_declared_use"]:',
        'if vector["field_of_use_restriction"]:',
    ),)),
    Mutant("allow_finalized_manifest_overwrite", ((
        '_require(manifest["state"] in ("FROZEN", "REVIEWING"), "manifest is not finalizable")',
        '_require(manifest["state"] in ("FROZEN", "REVIEWING", "FINALIZED"), "manifest is not finalizable")',
    ),)),
)


def apply_mutant(source: str, mutant: Mutant) -> str:
    result = source
    for needle, replacement in mutant.replacements:
        if mutant.name == "remove_successful_replay_guard" and "component[\"state\"]" in needle:
            if result.count(needle) != 2:
                raise RuntimeError(f"{mutant.name}: expected two replay-state guards")
            result = result.replace(needle, replacement)
            continue
        if result.count(needle) != 1:
            raise RuntimeError(f"{mutant.name}: expected one occurrence of {needle!r}, found {result.count(needle)}")
        result = result.replace(needle, replacement, 1)
    return result


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    killed = 0
    with tempfile.TemporaryDirectory(prefix="licenseproof-mutants-") as temp:
        mutated_path = Path(temp) / "LicenseProof.py"
        for mutant in MUTANTS:
            mutated_path.write_text(apply_mutant(source, mutant), encoding="utf-8")
            env = os.environ.copy()
            env["LICENSEPROOF_CONTRACT_PATH"] = str(mutated_path)
            run = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "tests/mutations", "--disable-warnings"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            if run.returncode != 0:
                killed += 1
                print(f"KILLED {mutant.name}")
            else:
                print(f"SURVIVED {mutant.name}")
                print(run.stdout[-1000:])
    print(f"MUTANTS_KILLED={killed}/{len(MUTANTS)}")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
