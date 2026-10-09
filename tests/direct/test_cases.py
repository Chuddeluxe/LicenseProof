from __future__ import annotations

import hashlib
import json

from conftest import fixture_text, mock_license, semantic


def run_case(env, policy, license_name, vector, expected, *, component_type="SOURCE_PACKAGE"):
    vm, c = env
    text = fixture_text(license_name)
    digest = hashlib.sha256(text.encode()).hexdigest()
    c.create_release_policy(*policy)
    c.freeze_release_policy(policy[0])
    c.create_manifest("m", "Release", "1", policy[0], "")
    c.add_component("c", "m", "fixture", "1", component_type, "fixture", "b" * 64, "CUSTOM", "e")
    c.commit_license_evidence("e", "c", "fixture-authority", "licenses.example.org", "/case", "https://licenses.example.org/case/license.txt", digest, len(text.encode()), "", "", "LICENSE_TEXT")
    c.freeze_manifest("m")
    c.begin_component_review("m", "c")
    mock_license(vm, "https://licenses.example.org/case/license.txt", text, vector)
    c.adjudicate_component("m", "c")
    assert c.finalize_manifest("m") == expected
    return json.loads(c.get_component_review("c"))


def test_case_a_permissive_combination(env):
    policy = ("a", "Commercial SaaS", True, True, False, True, False, False, "PROPRIETARY", "HOSTED_ONLY", "1")
    review = run_case(env, policy, "permissive.txt", semantic(attribution_required=True, notice_preservation_required=True), "COMPATIBLE_WITH_OBLIGATIONS")
    assert review["semantic_vector"]["commercial_use_permitted"] is True


def test_case_b_hosted_restriction(env):
    policy = ("b", "Paid hosted", True, True, False, True, False, True, "PROPRIETARY", "HOSTED_ONLY", "1")
    review = run_case(env, policy, "hosted-restricted.txt", semantic(hosted_service_permitted=False, attribution_required=True, notice_preservation_required=True), "INCOMPATIBLE")
    assert review["semantic_vector"]["hosted_service_permitted"] is False


def test_case_c_network_source_obligation(env):
    policy = ("c", "Hosted proprietary", True, True, False, False, False, False, "PROPRIETARY", "HOSTED_ONLY", "1")
    review = run_case(env, policy, "network-copyleft.txt", semantic(network_source_disclosure_required=True, attribution_required=True, notice_preservation_required=True), "INCOMPATIBLE")
    assert review["semantic_vector"]["network_source_disclosure_required"] is True
