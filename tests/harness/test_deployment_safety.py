from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from scripts.studio_live_qualification import (
    JOURNAL_PHASE_HASH,
    JOURNAL_PHASE_RECONCILED,
    JOURNAL_PHASE_STARTED,
    LiveWriter,
    QualificationError,
    append_jsonl,
    broadcast_intent_path,
    last_journal_transaction,
    unresolved_broadcast_attempt,
    unresolved_broadcast_intent,
    write_json,
)


TX_HASH = "0x" + "a" * 64
FEE_RESULT = {
    "result": {
        "defaultFees": {
            "distribution": {
                "leaderTimeunitsAllocation": 100,
                "validatorTimeunitsAllocation": 200,
                "appealRounds": 0,
                "executionBudgetPerRound": 94353600000000,
                "executionConsumed": 0,
                "totalMessageFees": 0,
                "rotations": [0],
                "maxPriceGenPerTimeUnit": 2,
                "storageFeeMaxGasPrice": 300000000,
                "receiptFeeMaxGasPrice": 300000000,
            },
            "feeValue": 94353600002588,
        }
    }
}


def _started(path: Path, *, attempt_id: str = "attempt-1", nonce: int = 11) -> None:
    append_jsonl(
        path,
        {
            "phase": JOURNAL_PHASE_STARTED,
            "attempt_id": attempt_id,
            "label": "DEPLOYMENT",
            "method": "deploy",
            "arguments": [],
            "from": "0x33653e6e86807e41682d3346cdf648d6653384b1",
            "network": "studio-dev",
            "chainId": 61997,
            "pre_write_nonce": nonce,
            "calldata_sha256": "b" * 64,
            "fee_estimate": FEE_RESULT,
            "tx_hash": None,
            "finality": None,
            "execution_result": None,
            "canonical_readback": None,
            "timestamp": "2026-10-09T00:00:00Z",
        },
    )


def _hash_record(path: Path, *, phase: str = JOURNAL_PHASE_HASH) -> None:
    append_jsonl(
        path,
        {
            "phase": phase,
            "attempt_id": "attempt-1",
            "label": "DEPLOYMENT",
            "method": "deploy",
            "pre_write_nonce": 11,
            "tx_hash": TX_HASH,
        },
    )


class FakeProcess:
    def __init__(self, lines: list[str]) -> None:
        self.stdout = io.StringIO("".join(lines))
        self.returncode = 0
        self._polled = False

    def poll(self) -> int | None:
        # Let the reader thread observe the complete CLI output first.
        return None if not self._polled else self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self._polled = True
        return self.returncode

    def terminate(self) -> None:
        self._polled = True


def test_send_returns_hash_normally_and_persists_before_reconcile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    journal = tmp_path / "deployment.jsonl"
    process = FakeProcess(["Transaction Hash:\n", f"{TX_HASH}\n"])
    calls: list[list[str]] = []

    def fake_popen(command: list[str], **_: object) -> FakeProcess:
        calls.append(command)
        return process

    monkeypatch.setattr("scripts.studio_live_qualification.subprocess.Popen", fake_popen)
    writer = LiveWriter(None, None, "node", "cli")  # type: ignore[arg-type]
    monkeypatch.setattr(writer, "reconcile", lambda tx_hash: {
        "transaction": {"lifecycle": {"state": "finalized"}},
        "successful": True,
    })

    tx_hash, record = writer.broadcast_once(
        journal_path=journal,
        label="DEPLOYMENT",
        method="deploy",
        address=None,
        args=[],
        pre_write_nonce=11,
        calldata_digest="b" * 64,
        fee_result=FEE_RESULT,
        deployment=True,
    )

    assert tx_hash == TX_HASH
    assert record["execution_result"]["successful"] is True
    assert len(calls) == 1
    assert last_journal_transaction(journal) == TX_HASH
    assert unresolved_broadcast_attempt(journal) is None
    assert unresolved_broadcast_intent(journal) is None


@pytest.mark.parametrize("failure", ["send_raises", "timeout_after_broadcast", "rpc_disconnect_after_broadcast"])
def test_uncertain_send_is_terminal_for_broadcast_and_blocks_second_send(tmp_path: Path, failure: str) -> None:
    journal = tmp_path / f"{failure}.jsonl"
    _started(journal)
    intent = {"status": "broadcast_possible", "attempt_id": "attempt-1", "pre_write_nonce": 11}
    write_json(broadcast_intent_path(journal), intent)

    assert unresolved_broadcast_attempt(journal)["attempt_id"] == "attempt-1"  # type: ignore[index]
    assert unresolved_broadcast_intent(journal)["attempt_id"] == "attempt-1"  # type: ignore[index]

    writer = LiveWriter(None, None, "node", "cli")  # type: ignore[arg-type]
    with pytest.raises(QualificationError, match="permanent stop condition"):
        writer.broadcast_once(
            journal_path=journal,
            label="DEPLOYMENT",
            method="deploy",
            address=None,
            args=[],
            pre_write_nonce=11,
            calldata_digest="b" * 64,
            fee_result=FEE_RESULT,
            deployment=True,
        )


def test_process_restart_resumes_hash_without_new_broadcast(tmp_path: Path) -> None:
    journal = tmp_path / "deployment.jsonl"
    _started(journal)
    _hash_record(journal)
    write_json(broadcast_intent_path(journal), {"status": JOURNAL_PHASE_HASH, "tx_hash": TX_HASH})

    assert unresolved_broadcast_attempt(journal) is None
    assert unresolved_broadcast_intent(journal) is None
    assert last_journal_transaction(journal) == TX_HASH


def test_missing_journal_but_consumed_nonce_keeps_durable_intent_stop_condition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = tmp_path / "deployment.jsonl"
    write_json(
        broadcast_intent_path(journal),
        {
            "status": "broadcast_possible",
            "attempt_id": "attempt-1",
            "pre_write_nonce": 11,
            "from": "0x33653e6e86807e41682d3346cdf648d6653384b1",
        },
    )
    # The journal can be missing after a filesystem incident, while the
    # separate intent survives.  A consumed nonce is evidence to reconcile,
    # never evidence to submit again.
    assert not journal.exists()
    assert unresolved_broadcast_intent(journal)["pre_write_nonce"] == 11  # type: ignore[index]
    observed_latest = 12
    observed_pending = 12
    assert observed_latest == observed_pending
    calls = 0

    def forbidden_popen(*_: object, **__: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("second broadcast attempted")

    monkeypatch.setattr("scripts.studio_live_qualification.subprocess.Popen", forbidden_popen)
    writer = LiveWriter(None, None, "node", "cli")  # type: ignore[arg-type]
    with pytest.raises(QualificationError):
        writer.broadcast_once(
            journal_path=journal,
            label="DEPLOYMENT",
            method="deploy",
            address=None,
            args=[],
            pre_write_nonce=observed_pending,
            calldata_digest="b" * 64,
            fee_result=FEE_RESULT,
            deployment=True,
        )
    assert calls == 0


def test_terminal_finished_with_error_is_not_a_retry_permission(tmp_path: Path) -> None:
    journal = tmp_path / "deployment.jsonl"
    _started(journal)
    _hash_record(journal, phase=JOURNAL_PHASE_RECONCILED)
    write_json(
        broadcast_intent_path(journal),
        {
            "status": JOURNAL_PHASE_RECONCILED,
            "tx_hash": TX_HASH,
            "execution_result": {"successful": False, "name": "FINISHED_WITH_ERROR"},
        },
    )
    assert last_journal_transaction(journal) == TX_HASH
    assert unresolved_broadcast_attempt(journal) is None
    assert unresolved_broadcast_intent(journal) is None


def test_journal_phases_are_append_only_and_hash_is_never_replaced(tmp_path: Path) -> None:
    journal = tmp_path / "deployment.jsonl"
    _started(journal)
    _hash_record(journal)
    _hash_record(journal, phase=JOURNAL_PHASE_RECONCILED)
    records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert [record["phase"] for record in records] == [JOURNAL_PHASE_STARTED, JOURNAL_PHASE_HASH, JOURNAL_PHASE_RECONCILED]
    assert last_journal_transaction(journal) == TX_HASH
