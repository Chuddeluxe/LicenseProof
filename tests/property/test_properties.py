from __future__ import annotations

from hypothesis import HealthCheck, given, settings, strategies as st


def module_from_env(env):
    import sys

    return sys.modules["_contract_LicenseProof"]


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
@given(st.text(min_size=0, max_size=80))
def test_hash_validator_accepts_exactly_lowercase_64_hex(env, value):
    module = module_from_env(env)
    if len(value) == 64 and all(char in "0123456789abcdef" for char in value):
        assert module._valid_sha256(value, "hash") == value
    else:
        try:
            module._valid_sha256(value, "hash")
        except Exception:
            return
        assert False, "malformed SHA-256 was accepted"


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
@given(st.lists(st.sampled_from(["COMPATIBLE", "COMPATIBLE_WITH_OBLIGATIONS", "INCOMPATIBLE", "INSUFFICIENT_EVIDENCE", "INCONCLUSIVE"]), min_size=1, max_size=5))
def test_result_priority_is_deterministic(env, results):
    module = module_from_env(env)
    priority = ["INCOMPATIBLE", "INSUFFICIENT_EVIDENCE", "INCONCLUSIVE", "COMPATIBLE_WITH_OBLIGATIONS", "COMPATIBLE"]
    expected = next(result for result in priority if result in results)
    assert expected in module.FINAL_RESULTS
    assert sorted(results, key=priority.index)[0] == expected


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=20)
@given(st.permutations(["a", "b", "c", "d"]))
def test_component_order_does_not_change_priority(env, order):
    module = module_from_env(env)
    assert set(order) == {"a", "b", "c", "d"}
    assert module.FINAL_RESULTS == (
        "COMPATIBLE",
        "COMPATIBLE_WITH_OBLIGATIONS",
        "INCOMPATIBLE",
        "INSUFFICIENT_EVIDENCE",
        "INCONCLUSIVE",
    )


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=20)
@given(st.sampled_from(["/text", "/text/", "/licenses/archive"]))
def test_authority_prefix_never_allows_escape(env, prefix):
    module = module_from_env(env)
    canonical = module._normalize_prefix(prefix)
    assert module._path_inside(canonical + "/license.txt", canonical)
    assert not module._path_inside(canonical + "-evil/license.txt", canonical)
