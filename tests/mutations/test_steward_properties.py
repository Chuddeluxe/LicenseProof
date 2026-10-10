"""Mutation-enforced steward remediation properties for LicenseProof 1.1."""
from __future__ import annotations

import hashlib
import json
import sys

import pytest

from conftest import fixture_text, mock_license, semantic
from direct.test_lifecycle import prepare, commit


def test_no_third_party_lineage_claim_mutant(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    mock_license(vm, "https://licenses.example.org/text/mit.txt", fixture_text("permissive.txt"), semantic())
    c.adjudicate_component("m1", "c1")
    c.finalize_manifest("m1")
    with vm.prank(b"\x15" * 20):
        with pytest.raises(Exception):
            c.create_manifest("attacker-successor", "forged", "2", "p1", "m1")
    assert c.get_manifest("attacker-successor") == ""


def test_review_start_once_mutant(env, policy_args):
    _vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    with pytest.raises(Exception):
        c.begin_component_review("m1", "c1")


def test_applicability_uncertainty_mutant(env):
    mod = sys.modules["_contract_LicenseProof"]
    policy = {
        "commercial_use": True,
        "hosted_service": True,
        "redistribution": False,
        "modification": False,
        "sublicensing": False,
        "derivative_distribution": False,
        "source_model": "PROPRIETARY",
        "distribution_model": "HOSTED_ONLY",
    }
    assert mod._derive_result(policy, semantic(applicability_clear=False)) == "INCONCLUSIVE"
    assert mod._derive_result(policy, semantic(field_of_use_restriction=True)) == "COMPATIBLE"


def test_multiple_positive_reviews_do_not_certify_bundle_mutant(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    txt = fixture_text("permissive.txt")
    url = "https://licenses.example.org/text/second.txt"
    c.add_component("c2", "m1", "pkg2", "1", "SDK", "pkg:second", "b" * 64, "MIT", "e2")
    c.commit_license_evidence(
        "e2", "c2", "issuer", "licenses.example.org", "/text", url,
        hashlib.sha256(txt.encode()).hexdigest(), len(txt.encode()), "", "", "LICENSE_TEXT",
    )
    c.freeze_manifest("m1")
    for cid, address in [("c1", "https://licenses.example.org/text/mit.txt"), ("c2", url)]:
        c.begin_component_review("m1", cid)
        mock_license(vm, address, txt, semantic())
        c.adjudicate_component("m1", cid)
    assert c.finalize_manifest("m1") == "INCONCLUSIVE"
