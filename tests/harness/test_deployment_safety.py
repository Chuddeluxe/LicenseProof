from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.studio_deploy_harness import (
    DeploymentSafetyError,
    OneShotDeploymentSender,
    raw_transaction_hash,
    read_json,
)


RAW = "0x02" + "11" * 32
SENDER = "0x33653e6e86807e41682d3346cdf648d6653384b1"


def request() -> dict[str, object]:
    return {
        "network": "studio-dev",
        "chainId": 61997,
        "sender": SENDER,
        "nonce": 14,
        "source_sha256": "7" * 64,
        "serialized_deploy_sha256": "8" * 64,
        "consensus_calldata_sha256": "9" * 64,
        "fees": {
            "distribution": {
                "leaderTimeunitsAllocation": 100,
                "validatorTimeunitsAllocation": 200,
                "appealRounds": 0,
                "executionBudgetPerRound": 25000000000000000,
                "executionConsumed": 0,
                "totalMessageFees": 0,
                "rotations": [3],
                "maxPriceGenPerTimeUnit": 2,
                "storageFeeMaxGasPrice": 300000000,
                "receiptFeeMaxGasPrice": 300000000,
            },
            "feeValue": 100000000000010352,
        },
    }


class Provider:
    def __init__(self, *, mode: str = "success") -> None:
        self.mode = mode
        self.calls: list[tuple[str, list[object]]] = []

    def make_request(self, method: str, params: list[object]) -> dict[str, object]:
        self.calls.append((method, params))
        if method == "eth_sendRawTransaction":
            if self.mode in {"send_raises", "timeout_after_broadcast", "rpc_disconnect_after_broadcast"}:
                raise TimeoutError(self.mode)
            if self.mode == "wrong_hash":
                return {"result": "0x" + "f" * 64}
            return {"result": raw_transaction_hash(RAW)}
        if method == "eth_getTransactionByHash":
            return {"result": {"hash": params[0], "nonce": hex(14)}}
        raise AssertionError(f"unexpected provider method {method}")


def make_sender(tmp_path: Path, provider: Provider) -> OneShotDeploymentSender:
    return OneShotDeploymentSender(provider, tmp_path / "deployment.jsonl")


def test_normal_broadcast_persists_intent_then_exact_hash(tmp_path: Path) -> None:
    provider = Provider()
    sender = make_sender(tmp_path, provider)

    evm_hash = sender.broadcast_once(request(), RAW)

    assert evm_hash == raw_transaction_hash(RAW)
    assert [method for method, _ in provider.calls] == ["eth_sendRawTransaction"]
    intent = read_json(tmp_path / "deployment.jsonl.intent.json")
    assert intent is not None
    assert intent["status"] == "evm_hash_persisted"
    assert intent["broadcast_count"] == 1
    assert intent["evm_tx_hash"] == evm_hash
    journal_lines = (tmp_path / "deployment.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(journal_lines[0])["phase"] == "broadcast_intent_persisted"
    assert json.loads(journal_lines[1])["phase"] == "evm_hash_persisted"


@pytest.mark.parametrize("failure", ["send_raises", "timeout_after_broadcast", "rpc_disconnect_after_broadcast"])
def test_uncertain_send_is_terminal_and_cannot_broadcast_again(tmp_path: Path, failure: str) -> None:
    provider = Provider(mode=failure)
    sender = make_sender(tmp_path, provider)

    with pytest.raises(DeploymentSafetyError, match="uncertain"):
        sender.broadcast_once(request(), RAW)
    with pytest.raises(DeploymentSafetyError, match="unresolved deployment intent"):
        sender.broadcast_once(request(), RAW)

    assert [method for method, _ in provider.calls] == ["eth_sendRawTransaction"]
    intent = read_json(tmp_path / "deployment.jsonl.intent.json")
    assert intent is not None
    assert intent["status"] == "broadcast_intent"
    assert intent["broadcast_count"] == 0


def test_process_restart_recovers_same_hash_without_new_broadcast(tmp_path: Path) -> None:
    provider = Provider(mode="send_raises")
    first = make_sender(tmp_path, provider)
    with pytest.raises(DeploymentSafetyError, match="uncertain"):
        first.broadcast_once(request(), RAW)

    provider.mode = "success"
    restarted = make_sender(tmp_path, provider)
    recovered = restarted.recover_same_hash()

    assert recovered["recovered_read_only"] is True
    assert recovered["evm_tx_hash"] == raw_transaction_hash(RAW)
    assert [method for method, _ in provider.calls] == [
        "eth_sendRawTransaction",
        "eth_getTransactionByHash",
    ]


def test_missing_journal_but_consumed_nonce_never_rebroadcasts(tmp_path: Path) -> None:
    provider = Provider(mode="success")
    sender = make_sender(tmp_path, provider)
    sender.prepare_intent(request(), RAW)
    (tmp_path / "deployment.jsonl").unlink()

    recovered = sender.recover_same_hash()

    assert recovered["recovered_read_only"] is True
    assert [method for method, _ in provider.calls] == ["eth_getTransactionByHash"]


def test_missing_hash_and_missing_chain_transaction_is_a_stop(tmp_path: Path) -> None:
    class MissingProvider(Provider):
        def make_request(self, method: str, params: list[object]) -> dict[str, object]:
            self.calls.append((method, params))
            return {"result": None}

    provider = MissingProvider()
    sender = make_sender(tmp_path, provider)
    sender.prepare_intent(request(), RAW)

    with pytest.raises(DeploymentSafetyError, match="nonce may be consumed"):
        sender.recover_same_hash()
    assert [method for method, _ in provider.calls] == ["eth_getTransactionByHash"]


def test_wrong_provider_hash_stops_without_second_send(tmp_path: Path) -> None:
    provider = Provider(mode="wrong_hash")
    sender = make_sender(tmp_path, provider)

    with pytest.raises(DeploymentSafetyError, match="different EVM hash"):
        sender.broadcast_once(request(), RAW)
    with pytest.raises(DeploymentSafetyError, match="unresolved deployment intent"):
        sender.broadcast_once(request(), RAW)
    assert len([method for method, _ in provider.calls if method == "eth_sendRawTransaction"]) == 1


def test_terminal_execution_error_does_not_authorize_a_second_send(tmp_path: Path) -> None:
    provider = Provider(mode="success")
    sender = make_sender(tmp_path, provider)
    evm_hash = sender.broadcast_once(request(), RAW)
    intent_path = tmp_path / "deployment.jsonl.intent.json"
    terminal = read_json(intent_path)
    assert terminal is not None
    terminal.update({"status": "reconciled", "execution_result": "FINISHED_WITH_ERROR", "evm_tx_hash": evm_hash})
    from scripts.studio_deploy_harness import fsync_json

    fsync_json(intent_path, terminal)

    with pytest.raises(DeploymentSafetyError, match="prior deployment intent"):
        sender.broadcast_once(request(), RAW)
    assert len([method for method, _ in provider.calls if method == "eth_sendRawTransaction"]) == 1


def test_no_cli_stdout_parser_or_subprocess_broadcast_remains() -> None:
    source = Path("scripts/studio_live_qualification.py").read_text(encoding="utf-8")
    assert ".Popen(" not in source
    assert "Transaction " + "Hash" not in source
    assert "genlayer CLI argument parser" not in source
