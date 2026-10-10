"""V1.1 regression tests for steward-sensitive release and trust boundaries."""
from __future__ import annotations

import hashlib
import json

import pytest

from conftest import fixture_text, mock_license, semantic
from direct.test_lifecycle import commit, prepare


def _finalize_one(vm, c, manifest_id="m1", component_id="c1", url="https://licenses.example.org/text/mit.txt"):
    c.freeze_manifest(manifest_id)
    c.begin_component_review(manifest_id, component_id)
    mock_license(vm, url, fixture_text("permissive.txt"), semantic())
    c.adjudicate_component(manifest_id, component_id)
    c.finalize_manifest(manifest_id)


def test_attacker_cannot_claim_other_creators_manifest(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    _finalize_one(vm, c)
    prior_events = list(c.get_audit_events())
    with vm.prank(b"\x07" * 20):
        with pytest.raises(Exception):
            c.create_manifest("attack", "Claimed successor", "2", "p1", "m1")
    assert c.get_manifest("attack") == ""
    assert c.get_manifest_successor("m1") == ""
    assert c.get_audit_events() == prior_events


def test_only_one_successor_can_be_recorded(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    _finalize_one(vm, c)
    for id in ("m2", "m3"):
        cid = "component-" + id
        eid = "evidence-" + id
        url = "https://licenses.example.org/text/" + id + ".txt"
        c.create_manifest(id, "Replacement", "2", "p1", "m1")
        c.add_component(cid, id, "lib", "2", "SOURCE_PACKAGE", "pkg:lib", "a" * 64, "MIT", eid)
        commit(c, eid, cid, url=url)
        _finalize_one(vm, c, id, cid, url)
    old = c.get_manifest("m1")
    c.supersede_manifest("m1", "m2")
    assert c.get_manifest_successor("m1") == "m2"
    with pytest.raises(Exception):
        c.supersede_manifest("m1", "m3")
    assert c.get_manifest("m1") == old
    assert c.get_manifest_successor("m1") == "m2"


def test_repeated_begin_review_fails_without_append(env, policy_args):
    _vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    count = len(c.get_audit_events())
    with pytest.raises(Exception):
        c.begin_component_review("m1", "c1")
    assert len(c.get_audit_events()) == count


def test_independent_actor_can_assess_and_finalize_frozen_component(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    with vm.prank(b"\x09" * 20):
        c.begin_component_review("m1", "c1")
        mock_license(vm, "https://licenses.example.org/text/mit.txt", fixture_text("permissive.txt"), semantic(commercial_use_permitted=False))
        c.adjudicate_component("m1", "c1")
        assert c.finalize_manifest("m1") == "INCOMPATIBLE"


def test_uncertain_conditions_produce_inconclusive_not_approval(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    mock_license(vm, "https://licenses.example.org/text/mit.txt", fixture_text("permissive.txt"), semantic(applicability_clear=False))
    c.adjudicate_component("m1", "c1")
    assert json.loads(c.get_component_review("c1"))["final_result"] == "INCONCLUSIVE"
    assert c.finalize_manifest("m1") == "INCONCLUSIVE"


def test_inconclusive_requires_sufficient_evidence(env):
    import sys
    mod = sys.modules["_contract_LicenseProof"]
    policy = {"commercial_use": True, "hosted_service": True, "redistribution": False, "modification": False, "sublicensing": False, "derivative_distribution": False, "source_model": "PROPRIETARY", "distribution_model": "HOSTED_ONLY"}
    assert mod._derive_result(policy, semantic(evidence_sufficient=False, applicability_clear=False)) == "INSUFFICIENT_EVIDENCE"


def test_manifest_indexes_and_audit_pagination(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.create_manifest("m2", "Other", "2", "p1", "")
    c.add_component("c2", "m2", "lib2", "2", "SDK", "pkg:other", "b" * 64, "MIT", "e2")
    assert c.get_component_ids("m1") == ["c1"]
    assert c.get_component_ids("m2") == ["c2"]
    events = c.get_audit_events()
    assert c.get_audit_events_page(0, 2) == events[:2]
    assert c.get_audit_events_page(2, 100) == events[2:]
    assert c.get_audit_events_page(len(events), 10) == []
    for start, limit in [(-1, 1), (0, 0), (0, 101)]:
        with pytest.raises(Exception):
            c.get_audit_events_page(start, limit)


def test_attestation_and_cross_component_limitations_public(env):
    _vm, c = env
    info = json.loads(c.contract_info())
    assert info["package_license_authority_verified"] is False
    assert info["cross_component_conflicts_verified"] is False
    assert info["assurance_scope"] == "CLAIMED_LICENSE_TEXT_VS_DECLARED_RELEASE_POLICY"
    assert info["redirect_final_origin_verified_without_metadata"] is False


def test_claimed_evidence_observation_not_trusted(env, policy_args):
    _vm, c = prepare(env, policy_args)
    commit(c)
    evidence = json.loads(c.get_evidence("e1"))
    assert evidence["observed_at_source"] == "CREATOR_ASSERTED"
    assert evidence["committed_at"]
