"""Use the already-cached qualified 5j direct runner without network or deployment."""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

from gltest.direct import sdk_loader
from gltest.direct import loader
from gltest.direct.sdk_compat import import_address, import_calldata


LOCAL_CACHE = Path.home() / ".cache" / "gltest-direct" / "extracted" / "local"
RUNNER_HASH = "5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng"


def use_cached_5j_runner() -> None:
    os.environ.setdefault("GENVM_VERSION", "v0.6.0-rc9")
    original = sdk_loader.extract_runner

    def extract_runner(tarball_path, runner_type, runner_hash=None, version=None):
        if runner_hash == RUNNER_HASH:
            path = LOCAL_CACHE / runner_type / RUNNER_HASH
            if path.exists():
                return path
        if runner_type == "py-lib-genlayer-std" and runner_hash:
            path = LOCAL_CACHE / runner_type / runner_hash
            if path.exists():
                return path
        return original(tarball_path, runner_type, runner_hash, version)

    sdk_loader.extract_runner = extract_runner

    # gltest 0.30.0rc2 leaves a duplicated Windows stdin handle open before
    # unlinking its temporary message file. Keep the file until process exit;
    # the contract still receives the exact same deterministic message bytes.
    def inject_message_to_fd0(vm) -> None:
        sender = vm.sender
        if isinstance(sender, bytes):
            sender = import_address()(sender)
        contract_address = vm._contract_address
        if isinstance(contract_address, bytes):
            contract_address = import_address()(contract_address)
        origin = vm.origin
        if isinstance(origin, bytes):
            origin = import_address()(origin)
        message_data = {
            "contract_address": contract_address,
            "sender_address": sender,
            "origin_address": origin,
            "stack": [],
            "value": vm._value,
            "datetime": vm._datetime,
            "is_init": False,
            "chain_id": vm._chain_id,
            "entry_kind": 0,
            "entry_data": b"",
            "entry_stage_data": None,
        }
        encoded = import_calldata().encode(message_data)
        fd, _path = tempfile.mkstemp()
        os.write(fd, encoded)
        os.lseek(fd, 0, os.SEEK_SET)
        vm._original_stdin_fd = os.dup(0)
        os.dup2(fd, 0)
        os.close(fd)

    loader._inject_message_to_fd0 = inject_message_to_fd0
