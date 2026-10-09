from __future__ import annotations

import json

import pytest

from conftest import fixture_text, mock_license, semantic
from direct.test_lifecycle import commit, prepare


def test_exact_semantic_vector_and_json_mode(env, policy_args):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    vector = semantic(attribution_required=True)
    mock_license(vm, "https://licenses.example.org/text/mit.txt", fixture_text("permissive.txt"), vector)
    c.adjudicate_component("m1", "c1")
    module = __import__("sys").modules["_contract_LicenseProof"]
    assert module.SEMANTIC_FIELDS == tuple(vector)
    assert "json" in module.LicenseProof._semantic_evaluation.__code__.co_consts
    assert set(json.loads(c.get_component_review("c1"))["semantic_vector"]) == set(vector)
    vm.clear_mocks()
    mock_license(vm, "https://licenses.example.org/text/mit.txt", fixture_text("permissive.txt"), semantic(hosted_service_permitted=False))
    assert vm.run_validator() is False
    assert vm.run_validator(leader_result={"commercial_use_permitted": True}) is False


@pytest.mark.parametrize(
    "bad",
    [
        {"extra": True},
        {"commercial_use_permitted": "true"},
        {"commercial_use_permitted": True},
        "not-json-object",
    ],
)
def test_malformed_semantic_output_fails_closed(env, policy_args, bad):
    vm, c = prepare(env, policy_args)
    commit(c)
    c.freeze_manifest("m1")
    c.begin_component_review("m1", "c1")
    url = "https://licenses.example.org/text/mit.txt"
    vm.mock_web("^https://licenses\\.example\\.org/text/mit\\.txt$", {"status": 200, "body": fixture_text("permissive.txt").encode()})
    vm.mock_llm("BEGIN_UNTRUSTED_LICENSE_TEXT", json.dumps(json.dumps(bad)))
    with pytest.raises(Exception):
        c.adjudicate_component("m1", "c1")
    assert c.get_component_review("c1") == ""
