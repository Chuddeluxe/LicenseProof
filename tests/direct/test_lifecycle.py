from __future__ import annotations

import json

import pytest

from conftest import fixture_hash, fixture_text, mock_license, semantic


HASH = "a" * 64


def prepare(env, policy_args, component_id="c1", evidence_id="e1", manifest_id="m1"):
    vm, c = env
    c.create_release_policy(*policy_args)
    c.freeze_release_policy(policy_args[0])
    c.create_manifest(manifest_id, "Release", "1.0.0", policy_args[0], "")
    c.add_component(component_id, manifest_id, "lib", "1.0", "SOURCE_PACKAGE", "pkg:lib", HASH, "MIT", evidence_id)
    return vm, c


def commit(c, evidence_id="e1", component_id="c1", text=None, url="https://licenses.example.org/text/mit.txt"):
    text = text if text is not None else fixture_text("permissive.txt")
    c.commit_license_evidence(
        evidence_id,
        component_id,
        "authority-1",
        "licenses.example.org",
        "/text",
        url,
        __import__("hashlib").sha256(text.encode()).hexdigest(),
        len(text.encode()),
        "2026-01-01T00:00:00Z",
        "2026-01-02T00:00:00Z",
        "LICENSE_TEXT",
    )


def test_full_direct_lifecycle_and_views(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    manifest = json.loads(c.get_manifest("m1"))
    assert manifest["state"] == "FROZEN"
    assert len(manifest["manifest_hash"]) == 64
    c.begin_component_review("m1", "c1")
    mock_license(vm, "https://licenses.example.org/text/mit.txt", fixture_text("permissive.txt"), semantic(attribution_required=True, notice_preservation_required=True))
    review_key = c.adjudicate_component("m1", "c1")
    assert len(review_key) == 64
    assert vm.run_validator() is True
    assert json.loads(c.get_component_review("c1"))["final_result"] == "COMPATIBLE_WITH_OBLIGATIONS"
    assert c.finalize_manifest("m1") == "COMPATIBLE_WITH_OBLIGATIONS"
    assert c.get_manifest_result("m1") == "COMPATIBLE_WITH_OBLIGATIONS"
    assert c.get_policy_count() == 1
    assert c.get_manifest_count() == 1
    assert c.get_policy_ids() == ["p1"]
    assert c.get_manifest_ids() == ["m1"]
    assert c.get_component_ids("m1") == ["c1"]
    assert c.get_evidence_ids("c1") == ["e1"]
    assert c.get_component_review_ids("m1") == [review_key]
    assert len(c.get_audit_events()) == 9
    assert json.loads(c.get_status())["audit_count"] == 9
    assert json.loads(c.contract_info())["name"] == "LicenseProof"
    assert c.get_policy("missing") == ""
    assert c.get_manifest("missing") == ""
    assert c.get_component("missing") == ""
    assert c.get_evidence("missing") == ""
    assert c.get_component_review("missing") == ""
    assert c.get_manifest_result("missing") == ""


def test_policy_and_manifest_freeze_immutability(env, policy_args):
    vm, c = prepare(env, policy_args)
    with pytest.raises(Exception):
        c.freeze_release_policy("p1")
    commit(c)
    c.freeze_manifest("m1")
    with pytest.raises(Exception):
        c.add_component("c2", "m1", "other", "1", "SDK", "pkg:o", HASH, "MIT", "e2")
    with pytest.raises(Exception):
        c.commit_license_evidence("e2", "c1", "auth", "licenses.example.org", "/text", "https://licenses.example.org/text/two.txt", HASH, 1, "", "", "LICENSE_TEXT")


def test_unknowns_duplicates_and_invalid_enums(env, policy_args):
    vm, c = env
    with pytest.raises(Exception):
        c.freeze_release_policy("missing")
    c.create_release_policy(*policy_args)
    with pytest.raises(Exception):
        c.create_release_policy(*policy_args)
    with pytest.raises(Exception):
        c.create_manifest("m1", "x", "1", "missing", "")
    with pytest.raises(Exception):
        c.create_release_policy("bad", "bad", True, True, True, True, True, True, "BAD", "HOSTED_ONLY", "1")


def test_creator_authorization_for_lifecycle_mutations(env, policy_args):
    vm, c = prepare(env, policy_args)
    with vm.prank(b"\x01" * 20):
        with pytest.raises(Exception):
            c.freeze_release_policy("p1")
    commit(c)
    with vm.prank(b"\x01" * 20):
        with pytest.raises(Exception):
            c.freeze_manifest("m1")


def test_failed_semantic_attempt_is_retryable_and_not_stored(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    vm.mock_web("^https://licenses\\.example\\.org/text/mit\\.txt$", {"status": 500, "body": b""})
    with pytest.raises(Exception):
        c.adjudicate_component("m1", "c1")
    assert c.get_component_review("c1") == ""
    vm.clear_mocks()
    mock_license(vm, "https://licenses.example.org/text/mit.txt", fixture_text("permissive.txt"), semantic())
    assert c.adjudicate_component("m1", "c1")


def test_supersession_does_not_mutate_historical_manifest(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    mock_license(vm, "https://licenses.example.org/text/mit.txt", fixture_text("permissive.txt"), semantic())
    c.adjudicate_component("m1", "c1")
    c.finalize_manifest("m1")
    old = c.get_manifest("m1")
    c.create_manifest("m2", "Replacement", "2.0.0", "p1", "m1")
    c.add_component("c2", "m2", "lib", "2.0", "SOURCE_PACKAGE", "pkg:lib", HASH, "MIT", "e2")
    commit(c, "e2", "c2", url="https://licenses.example.org/text/mit2.txt")
    c.freeze_manifest("m2")
    c.begin_component_review("m2", "c2")
    mock_license(vm, "https://licenses.example.org/text/mit2.txt", fixture_text("permissive.txt"), semantic())
    c.adjudicate_component("m2", "c2")
    c.finalize_manifest("m2")
    c.supersede_manifest("m1", "m2")
    assert c.get_manifest("m1") == old
    assert any("MANIFEST_SUPERSEDED" in item for item in c.get_audit_events())
