from __future__ import annotations

import hashlib
import json

import pytest

from conftest import fixture_text, mock_license, semantic
from direct.test_lifecycle import commit, prepare


def test_host_and_path_binding(env, policy_args):
    vm, c = prepare(env, policy_args)
    text = fixture_text("permissive.txt")
    with pytest.raises(Exception):
        c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://evil.example/text/x", hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    with pytest.raises(Exception):
        c.commit_license_evidence("e2", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text-evil/x", hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    with pytest.raises(Exception):
        c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "http://licenses.example.org/text/x", hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    module = __import__("sys").modules["_contract_LicenseProof"]
    with pytest.raises(Exception):
        module._canonical_source_url("https://licenses.example.org/text-evil/x", "licenses.example.org", "/text")


def test_evidence_integrity_and_redirect(env, policy_args):
    vm, c = prepare(env, policy_args)
    text = fixture_text("permissive.txt")
    url = "https://licenses.example.org/text/x"
    c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", url, hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    vm.mock_web("^https://licenses\\.example\\.org/text/x$", {"status": 200, "body": text.encode(), "headers": {"x-genlayer-final-url": b"https://evil.example/x"}})
    with pytest.raises(Exception):
        c.adjudicate_component("m1", "c1")
    assert c.get_component_review("c1") == ""


@pytest.mark.parametrize("mode", ["hash", "length"])
def test_evidence_hash_and_length_binding(env, policy_args, mode):
    vm, c = prepare(env, policy_args)
    text = fixture_text("permissive.txt")
    expected_hash = hashlib.sha256(text.encode()).hexdigest()
    evidence_length = len(text.encode()) if mode == "hash" else len(text.encode()) + 1
    c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text/x", expected_hash, evidence_length, "", "", "LICENSE_TEXT")
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    response_body = (b"x" * len(text.encode())) if mode == "hash" else text.encode()
    vm.mock_web("^https://licenses\\.example\\.org/text/x$", {"status": 200, "body": response_body})
    vm.mock_llm("BEGIN_UNTRUSTED_LICENSE_TEXT", json.dumps(json.dumps(semantic())))
    with pytest.raises(Exception):
        c.adjudicate_component("m1", "c1")
    assert c.get_component_review("c1") == ""


def test_policy_and_manifest_freezes(env, policy_args):
    _vm, c = prepare(env, policy_args)
    with pytest.raises(Exception):
        c.freeze_release_policy("p1")
    with pytest.raises(Exception):
        c.freeze_release_policy("p1")
    commit(c)
    c.freeze_manifest("m1")
    with pytest.raises(Exception):
        c.add_component("c2", "m1", "x", "1", "SDK", "x", "b" * 64, "MIT", "e2")
    with pytest.raises(Exception):
        c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text/x", "a" * 64, 1, "", "", "LICENSE_TEXT")


def test_semantic_shape_and_evidence_gate(env, policy_args):
    vm, c = prepare(env, policy_args)
    text = fixture_text("permissive.txt")
    c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text/x", hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    mock_license(vm, "https://licenses.example.org/text/x", text, semantic(evidence_sufficient=False))
    c.adjudicate_component("m1", "c1")
    assert json.loads(c.get_component_review("c1"))["final_result"] == "INSUFFICIENT_EVIDENCE"
    with pytest.raises(Exception):
        c.adjudicate_component("m1", "c1")


def test_semantic_extra_keys_and_string_booleans_fail(env, policy_args):
    vm, c = prepare(env, policy_args)
    text = fixture_text("permissive.txt")
    c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text/x", hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    extra = semantic()
    extra["unexpected"] = True
    mock_license(vm, "https://licenses.example.org/text/x", text, extra)
    with pytest.raises(Exception):
        c.adjudicate_component("m1", "c1")
    assert c.get_component_review("c1") == ""
    vm.clear_mocks()
    stringy = semantic()
    stringy["commercial_use_permitted"] = "true"
    mock_license(vm, "https://licenses.example.org/text/x", text, stringy)
    with pytest.raises(Exception):
        c.adjudicate_component("m1", "c1")


@pytest.mark.parametrize(
    "policy_index,vector_field",
    [
        (2, "commercial_use_permitted"),
        (3, "hosted_service_permitted"),
        (4, "redistribution_permitted"),
        (5, "modification_permitted"),
        (6, "sublicensing_permitted"),
        (7, "derivative_distribution_permitted"),
    ],
)
def test_policy_compatibility_gates(env, policy_args, policy_index, vector_field):
    vm, c = env
    policy = list(policy_args)
    policy[policy_index] = True
    c.create_release_policy(*policy)
    c.freeze_release_policy("p1")
    c.create_manifest("m1", "Release", "1", "p1", "")
    c.add_component("c1", "m1", "lib", "1", "SOURCE_PACKAGE", "pkg", "a" * 64, "MIT", "e1")
    text = fixture_text("permissive.txt")
    c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text/x", hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    mock_license(vm, "https://licenses.example.org/text/x", text, semantic(**{vector_field: False}))
    c.adjudicate_component("m1", "c1")
    assert json.loads(c.get_component_review("c1"))["final_result"] == "INCOMPATIBLE"


def test_proprietary_distribution_gate(env, policy_args):
    vm, c = env
    policy = list(policy_args)
    policy[4] = True
    c.create_release_policy(*policy)
    c.freeze_release_policy("p1")
    c.create_manifest("m1", "Release", "1", "p1", "")
    c.add_component("c1", "m1", "lib", "1", "SOURCE_PACKAGE", "pkg", "a" * 64, "MIT", "e1")
    text = fixture_text("permissive.txt")
    c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text/x", hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    mock_license(vm, "https://licenses.example.org/text/x", text, semantic(proprietary_distribution_permitted=False))
    c.adjudicate_component("m1", "c1")
    assert json.loads(c.get_component_review("c1"))["final_result"] == "INCOMPATIBLE"


def test_network_and_field_of_use_gates(env, policy_args):
    vm, c = env
    c.create_release_policy(*policy_args)
    c.freeze_release_policy("p1")
    c.create_manifest("m1", "Release", "1", "p1", "")
    c.add_component("c1", "m1", "lib", "1", "SOURCE_PACKAGE", "pkg", "a" * 64, "MIT", "e1")
    text = fixture_text("permissive.txt")
    c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text/x", hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    mock_license(vm, "https://licenses.example.org/text/x", text, semantic(network_source_disclosure_required=True))
    c.adjudicate_component("m1", "c1")
    assert json.loads(c.get_component_review("c1"))["final_result"] == "INCOMPATIBLE"

    # The field-of-use rule is independently deterministic in the pure result derivation.
    module = __import__("sys").modules["_contract_LicenseProof"]
    policy = {"commercial_use": True, "hosted_service": False, "redistribution": False, "modification": False, "sublicensing": False, "derivative_distribution": False, "source_model": "OPEN_SOURCE", "distribution_model": "INTERNAL_ONLY"}
    vector = module._semantic_vector(semantic(field_of_use_restriction=True))
    assert module._derive_result(policy, vector) == "INCOMPATIBLE"


def test_short_or_uppercase_hash_fails(env, policy_args):
    _vm, c = prepare(env, policy_args)
    with pytest.raises(Exception):
        c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text/x", "A" * 64, 1, "", "", "LICENSE_TEXT")


def test_technical_failure_is_retryable(env, policy_args):
    vm, c = prepare(env, policy_args)
    text = fixture_text("permissive.txt")
    c.commit_license_evidence("e1", "c1", "a", "licenses.example.org", "/text", "https://licenses.example.org/text/x", hashlib.sha256(text.encode()).hexdigest(), len(text.encode()), "", "", "LICENSE_TEXT")
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    vm.mock_web("^https://licenses\\.example\\.org/text/x$", {"status": 500, "body": b""})
    with pytest.raises(Exception):
        c.adjudicate_component("m1", "c1")
    assert c.get_component_review("c1") == ""
    vm.clear_mocks()
    mock_license(vm, "https://licenses.example.org/text/x", text, semantic())
    assert c.adjudicate_component("m1", "c1")


def test_finalized_manifest_cannot_be_overwritten(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    mock_license(vm, "https://licenses.example.org/text/x", fixture_text("permissive.txt"), semantic())
    # The committed fixture URL is mit.txt; this mock is intentionally replaced below.
    vm.clear_mocks()
    text = fixture_text("permissive.txt")
    vm.mock_web("^https://licenses\\.example\\.org/text/mit\\.txt$", {"status": 200, "body": text.encode()})
    vm.mock_llm("BEGIN_UNTRUSTED_LICENSE_TEXT", json.dumps(json.dumps(semantic())))
    c.adjudicate_component("m1", "c1")
    c.finalize_manifest("m1")
    with pytest.raises(Exception):
        c.finalize_manifest("m1")


def test_incomplete_finalization_and_manifest_immutability(env, policy_args):
    _vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    with pytest.raises(Exception):
        c.finalize_manifest("m1")
    before = c.get_manifest("m1")
    with pytest.raises(Exception):
        c.add_component("c2", "m1", "x", "1", "SDK", "x", "b" * 64, "MIT", "e2")
    assert c.get_manifest("m1") == before
