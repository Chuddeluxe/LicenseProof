"""Tamper tests for read-only GitHub release verification helpers."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.verify_schema import compare_artifacts
import scripts.verify_source as verify_source


def test_exact_committed_schema_required():
    base = json.loads((verify_source.ROOT / "contracts/schema.json").read_text(encoding="utf-8"))
    interface = json.loads((verify_source.ROOT / "contracts/interface.json").read_text(encoding="utf-8"))
    compare_artifacts(base, base, interface)
    altered = copy.deepcopy(base)
    altered["methods"]["get_manifest"]["readonly"] = False
    with pytest.raises(ValueError, match="COMMITTED_SCHEMA_MISMATCH"):
        compare_artifacts(base, altered, interface)
    altered_interface = copy.deepcopy(interface)
    altered_interface["methods"]["get_manifest"]["readonly"] = False
    with pytest.raises(ValueError, match="COMMITTED_INTERFACE_MISMATCH"):
        compare_artifacts(base, base, altered_interface)


def test_pinned_hash_mismatch_detected(monkeypatch, tmp_path):
    wrong = tmp_path / "SOURCE_HASH.txt"
    wrong.write_text(
        "CONTRACT=contracts/LicenseProof.py\n"
        "SHA256=" + "0" * 64 + "\n"
        "RUNNER=" + verify_source.EXPECTED_RUNNER + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(verify_source, "HASH_RECORD", wrong)
    monkeypatch.setenv("EXPECTED_CONTRACT_SHA256", "f" * 64)
    with pytest.raises(RuntimeError, match="CI expected SHA"):
        verify_source.pinned_sha()


def test_pinned_runner_mismatch_detected(monkeypatch, tmp_path):
    wrong = tmp_path / "SOURCE_HASH.txt"
    wrong.write_text(
        "CONTRACT=contracts/LicenseProof.py\n"
        "SHA256=" + "a" * 64 + "\n"
        "RUNNER=py-genlayer:wrong\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(verify_source, "HASH_RECORD", wrong)
    with pytest.raises(RuntimeError, match="runner mismatch"):
        verify_source.pinned_sha()
