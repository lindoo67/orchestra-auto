#!/usr/bin/env python3
"""Behaviour tests for ``inbox-loop.py``, driven through a fake Orca CLI.

The loop's job is small but safety-critical: never lose a message, never let a FIFO
replay overwrite the first read, never acknowledge anything a human still has to look
at, and never mistake a CLI failure for an empty queue. These tests exercise exactly
those behaviours end to end by running the real script as a subprocess against a stub
``orca`` executable, so the assertions are about what the script actually writes to
disk rather than about its internals.

Nothing here reaches the network, reads credentials, or depends on this machine's Orca
profile: the CLI is a shim generated per-test in a temporary directory.
"""

import contextlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRS = (
    REPO_ROOT / "skills" / "orchestra-auto",
    REPO_ROOT / "skills" / "orchestra-auto-zh",
)
SCRIPT_RELATIVE = Path("scripts") / "inbox-loop.py"

ORCHESTRATION_CHECK_PREFIX = '["orchestration", "check", "--run"]'


def load_inbox_module(skill_dir):
    """Import a skill's inbox-loop.py by path, without touching sys.path."""
    path = skill_dir / SCRIPT_RELATIVE
    spec = importlib.util.spec_from_file_location(
        "inbox_loop_" + skill_dir.name.replace("-", "_"), path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot build an import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeOrca:
    """A stub ``orca`` that answers ``orchestration check`` from a scripted list.

    Each entry in ``responses`` is one complete check response envelope, exactly as the
    real CLI would print it. An entry may instead be ``{"fail": "reason"}`` to make the
    stub exit non-zero, which is how the "a CLI failure must be reported, not mistaken
    for an empty queue" behaviour is exercised. Only a plain (non ``--wait``) check
    advances the script; the last response repeats forever, so the loop under test
    always has something to read. ``--ack`` calls are recorded and answered without
    advancing.
    """

    def __init__(self, directory, responses, ack_log=None):
        self.directory = Path(directory)
        self.responses = responses
        self.ack_log = Path(ack_log) if ack_log else self.directory / "acks.txt"
        self.calls_log = self.directory / "calls.txt"
        self.counter_file = self.directory / "counter.txt"
        self.path = self.directory / "orca"

    def write(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        responses_file = self.directory / "responses.json"
        responses_file.write_text(json.dumps(self.responses))
        shim = f'''#!{sys.executable}
import json, sys

RESPONSES = json.loads(open({str(responses_file)!r}).read())
CALLS = {str(self.calls_log)!r}
ACKS = {str(self.ack_log)!r}
COUNTER = {str(self.counter_file)!r}

argv = sys.argv[1:]
with open(CALLS, "a") as out:
    out.write(" ".join(argv) + "\\n")

if argv[:3] != {ORCHESTRATION_CHECK_PREFIX}:
    sys.stderr.write("unexpected command: " + " ".join(argv))
    sys.exit(2)

if "--ack" in argv:
    did = argv[argv.index("--ack") + 1]
    with open(ACKS, "a") as out:
        out.write(did + "\\n")
    sys.stdout.write(json.dumps({{"ok": True, "result": {{"acknowledged": did}}}}))
    sys.exit(0)

if "--wait" not in argv:
    try:
        index = int(open(COUNTER).read())
    except (OSError, ValueError):
        index = 0
    with open(COUNTER, "w") as out:
        out.write(str(index + 1))
else:
    try:
        index = max(int(open(COUNTER).read()) - 1, 0)
    except (OSError, ValueError):
        index = 0
index = min(index, len(RESPONSES) - 1)
response = RESPONSES[index]

if "fail" in response:
    sys.stderr.write(response["fail"])
    sys.exit(1)

sys.stdout.write(json.dumps(response))
sys.exit(0)
'''
        self.path.write_text(shim)
        self.path.chmod(self.path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return self

    def calls(self):
        if not self.calls_log.exists():
            return []
        return [line for line in self.calls_log.read_text().splitlines() if line]

    def acks(self):
        if not self.ack_log.exists():
            return []
        return [line for line in self.ack_log.read_text().splitlines() if line]


def batch(delivery_id, messages):
    return {"ok": True, "result": {"deliveryId": delivery_id, "messages": messages}}


def heartbeat():
    return {"id": "msg_hb", "type": "heartbeat", "body": "alive"}


def normal(message_type="worker_done", message_id="msg_done"):
    return {"id": message_id, "type": message_type, "body": "finished"}


class InboxLoopCase(unittest.TestCase):
    """Shared harness: a temporary state dir plus a scripted fake CLI."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="inbox-loop-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = self.tmp / "state"
        self.state.mkdir()
        self.script = SCRIPT_RELATIVE
        self.skill_dir = SKILL_DIRS[0]

    def start(self, responses, skill_dir=None, env_extra=None, wait_ms=200):
        skill_dir = skill_dir or self.skill_dir
        fake = FakeOrca(self.tmp / ("fake-" + skill_dir.name), responses).write()
        env = dict(os.environ)
        env["ORCA_CLI_COMMAND"] = str(fake.path)
        env["WAIT_TIMEOUT_MS"] = str(wait_ms)
        env["BACKOFF_SECONDS"] = "0.15"
        env["PENDING_BACKOFF_SECONDS"] = "0.15"
        env.update(env_extra or {})
        process = subprocess.Popen(
            [sys.executable, str(skill_dir / self.script),
             "run_test", str(self.state), "term_coordinator"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        return process, fake

    def wait_for(self, predicate, timeout=15.0, what="condition"):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        self.fail(f"timed out waiting for {what}")

    def stop(self, process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        # Drain the pipes so a killed child cannot leave a zombie writer behind.
        with contextlib.suppress(subprocess.TimeoutExpired, ValueError):
            process.communicate(timeout=5)
        return process

    def deliveries(self):
        directory = self.state / "deliveries"
        if not directory.exists():
            return []
        return sorted(directory.glob("*.json"))


class AtomicPersistenceTests(InboxLoopCase):
    def test_delivery_is_saved_atomically_and_completely(self):
        """A delivered batch must appear on disk as one complete, valid JSON file."""
        process, _ = self.start([batch("delivery_atomic", [normal()])])
        try:
            self.wait_for(lambda: len(self.deliveries()) == 1, what="one saved delivery")
            saved = json.loads(self.deliveries()[0].read_text())
            self.assertEqual(saved["result"]["deliveryId"], "delivery_atomic")
            self.assertEqual(saved["result"]["messages"][0]["id"], "msg_done")
            # atomic() writes to a sibling temp file and renames it; no temp file may
            # survive a completed write.
            leftovers = list((self.state / "deliveries").glob("*.tmp"))
            self.assertEqual(leftovers, [], f"temp files left behind: {leftovers}")
        finally:
            self.stop(process)

    def test_write_is_durable_against_a_reread(self):
        """The saved file must always be one complete document, never a prefix."""
        process, _ = self.start([batch("delivery_reread", [normal()])])
        try:
            self.wait_for(lambda: len(self.deliveries()) == 1, what="one saved delivery")
            path = self.deliveries()[0]
            for _ in range(20):
                payload = json.loads(path.read_text())
                self.assertIn("result", payload, "file was observed half-written")
            self.assertFalse(path.with_name(path.name + ".tmp").exists())
        finally:
            self.stop(process)


class ReplayTests(InboxLoopCase):
    def test_replayed_delivery_does_not_overwrite_the_first_read(self):
        """A FIFO replay of the same deliveryId must not clobber saved evidence."""
        first = batch("delivery_replay", [normal(message_id="first_read")])
        replay = batch("delivery_replay", [normal(message_id="second_read")])
        process, _ = self.start([first, replay])
        try:
            self.wait_for(lambda: len(self.deliveries()) == 1, what="saved delivery")
            path = self.deliveries()[0]
            self.wait_for(lambda: path.stat().st_size > 0, what="file content")
            time.sleep(0.8)  # let the loop consume the replay
            saved = json.loads(path.read_text())
            self.assertEqual(saved["result"]["messages"][0]["id"], "first_read")
            self.assertEqual(len(self.deliveries()), 1, "replay created a second file")
        finally:
            self.stop(process)


class AcknowledgementTests(InboxLoopCase):
    def test_heartbeat_only_batch_is_auto_acknowledged(self):
        """A batch whose every message is a heartbeat carries no decision: ack it.

        The wait is on the log line, not on the ack call: the loop acks and then logs, so waiting on
        the ack alone would race the write and read a file that does not exist yet.
        """
        process, fake = self.start([batch("delivery_hb", [heartbeat(), heartbeat()])])
        try:
            log_path = self.state / "watch.log"
            self.wait_for(
                lambda: log_path.exists()
                and "AUTO-ACK heartbeat-only delivery_hb" in log_path.read_text(),
                what="the auto-ack log line",
            )
            self.assertIn("delivery_hb", fake.acks())
        finally:
            self.stop(process)

    def test_normal_message_is_not_auto_acknowledged(self):
        """A batch containing anything a human must read is left for the coordinator."""
        process, fake = self.start([batch("delivery_done", [normal()])])
        try:
            self.wait_for(lambda: self.deliveries(), what="saved delivery")
            time.sleep(0.8)
            self.assertEqual(fake.acks(), [], "a worker_done batch must not be auto-acked")
            marker = self.state / "NEW-MESSAGE"
            self.wait_for(marker.exists, what="PENDING marker")
            self.assertIn("delivery_done", marker.read_text())
        finally:
            self.stop(process)

    def test_mixed_batch_is_not_auto_acknowledged(self):
        """One heartbeat plus one real message is still a batch a human must handle."""
        process, fake = self.start([batch("delivery_mixed", [heartbeat(), normal()])])
        try:
            self.wait_for(lambda: self.deliveries(), what="saved delivery")
            time.sleep(0.8)
            self.assertEqual(fake.acks(), [], "a mixed batch must not be auto-acked")
            saved = json.loads(self.deliveries()[0].read_text())
            self.assertEqual(len(saved["result"]["messages"]), 2)
        finally:
            self.stop(process)

    def test_pending_marker_is_not_cleared_by_an_empty_queue(self):
        """An empty queue does not prove the saved batches were handled."""
        process, _ = self.start([
            batch("delivery_pending", [normal()]),
            batch("delivery_empty", []),
        ])
        try:
            marker = self.state / "NEW-MESSAGE"
            self.wait_for(marker.exists, what="PENDING marker")
            first = marker.read_text()
            time.sleep(1.0)
            self.assertTrue(marker.exists(), "the PENDING marker was cleared automatically")
            self.assertEqual(marker.read_text(), first)
        finally:
            self.stop(process)


class FailureReportingTests(InboxLoopCase):
    def test_cli_error_is_reported_and_exits_nonzero(self):
        """A CLI failure must never be reinterpreted as an empty queue."""
        process, _ = self.start([{"fail": "simulated CLI failure"}])
        try:
            process.communicate(timeout=30)
            self.assertNotEqual(process.returncode, 0, "loop exited 0 on a CLI failure")
            state = json.loads((self.state / "state.json").read_text())
            self.assertEqual(state["phase"], "error")
            self.assertIn("CLI exit=1", state["error"])
            log = (self.state / "watch.log").read_text()
            self.assertIn("ERROR", log)
            self.assertIn("simulated CLI failure", log)
        finally:
            self.stop(process)

    def test_nonempty_batch_without_delivery_id_is_an_error(self):
        """A batch with messages but no deliveryId cannot be acknowledged safely."""
        process, _ = self.start([
            {"ok": True, "result": {"messages": [normal()]}},
        ])
        try:
            process.communicate(timeout=30)
            self.assertNotEqual(process.returncode, 0)
            state = json.loads((self.state / "state.json").read_text())
            self.assertEqual(state["phase"], "error")
            self.assertIn("deliveryId", state["error"])
        finally:
            self.stop(process)


class BindingTests(InboxLoopCase):
    def test_state_directory_cannot_be_rebound_to_another_run(self):
        """A directory bound to one Run/terminal/CLI must refuse a different binding."""
        process, _ = self.start([batch("delivery_bind", [heartbeat()])])
        try:
            binding_file = self.state / "binding.json"
            self.wait_for(binding_file.exists, what="binding file")
            self.wait_for(lambda: binding_file.read_text() != "", what="binding content")
        finally:
            self.stop(process)
        # A second invocation for a different Run must refuse to take over.
        env = dict(os.environ)
        env["ORCA_CLI_COMMAND"] = str(FakeOrca(self.tmp / "fake-rebind", []).path)
        result = subprocess.run(
            [sys.executable, str(self.skill_dir / self.script),
             "another_run", str(self.state), "term_other"],
            env=env, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("another Run", result.stderr)
        binding = json.loads((self.state / "binding.json").read_text())
        self.assertEqual(binding["run"], "run_test")

    def test_status_reports_dead_for_a_missing_directory(self):
        """--status must not consume the queue and must report a missing dir as DEAD."""
        missing = self.tmp / "does-not-exist"
        result = subprocess.run(
            [sys.executable, str(self.skill_dir / self.script), "--status", str(missing)],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("loop: DEAD", result.stdout)

    def test_status_reports_alive_for_a_running_loop(self):
        process, _ = self.start([batch("delivery_alive", [heartbeat()])])
        try:
            self.wait_for(lambda: (self.state / "inbox-loop.pid").exists(), what="pid file")
            result = subprocess.run(
                [sys.executable, str(self.skill_dir / self.script), "--status", str(self.state)],
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("loop: ALIVE", result.stdout)
        finally:
            self.stop(process)


class SingleInstanceTests(InboxLoopCase):
    def test_second_instance_for_the_same_directory_is_refused(self):
        """The directory lock keeps two consumers off one Run's queue."""
        process, fake = self.start([batch("delivery_lock", [heartbeat()])])
        try:
            self.wait_for(lambda: (self.state / "inbox-loop.pid").exists(), what="pid file")
            env = dict(os.environ)
            env["ORCA_CLI_COMMAND"] = str(fake.path)
            result = subprocess.run(
                [sys.executable, str(self.skill_dir / self.script),
                 "run_test", str(self.state), "term_coordinator"],
                env=env, capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("already running", result.stderr)
        finally:
            self.stop(process)


class BothLanguageVariantsTests(unittest.TestCase):
    """The two language variants must ship the same script, byte for byte."""

    def test_scripts_are_identical_across_language_variants(self):
        english = (SKILL_DIRS[0] / SCRIPT_RELATIVE).read_bytes()
        chinese = (SKILL_DIRS[1] / SCRIPT_RELATIVE).read_bytes()
        self.assertEqual(english, chinese)

    def test_modules_expose_the_same_public_functions(self):
        english = load_inbox_module(SKILL_DIRS[0])
        chinese = load_inbox_module(SKILL_DIRS[1])
        for name in ("atomic", "check", "locked", "main", "status", "env_number"):
            self.assertTrue(hasattr(english, name), f"missing {name}")
            self.assertTrue(hasattr(chinese, name), f"missing {name}")


class EnvironmentOverrideTests(unittest.TestCase):
    def test_invalid_numeric_override_falls_back_to_the_default(self):
        module = load_inbox_module(SKILL_DIRS[0])
        previous = os.environ.get("WAIT_TIMEOUT_MS")
        os.environ["WAIT_TIMEOUT_MS"] = "not-a-number"
        try:
            self.assertEqual(module.env_number("WAIT_TIMEOUT_MS", 30000, int), 30000)
        finally:
            if previous is None:
                os.environ.pop("WAIT_TIMEOUT_MS", None)
            else:
                os.environ["WAIT_TIMEOUT_MS"] = previous

    def test_valid_numeric_override_is_used(self):
        module = load_inbox_module(SKILL_DIRS[0])
        previous = os.environ.get("BACKOFF_SECONDS")
        os.environ["BACKOFF_SECONDS"] = "0.25"
        try:
            self.assertEqual(module.env_number("BACKOFF_SECONDS", 5.0, float), 0.25)
        finally:
            if previous is None:
                os.environ.pop("BACKOFF_SECONDS", None)
            else:
                os.environ["BACKOFF_SECONDS"] = previous


if __name__ == "__main__":
    unittest.main()
