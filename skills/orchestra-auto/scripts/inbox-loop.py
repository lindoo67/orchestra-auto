#!/usr/bin/env python3
"""Orca inbox loop: persist every delivery batch; it never wakes the agent and never
handles business messages on the coordinator's behalf.

The loop is deliberately narrow:

* every batch the CLI returns is written to disk atomically, keyed by a hash of its
  ``deliveryId``, before anything else happens, so a crash can never lose a message;
* an already saved delivery is never overwritten, so a FIFO replay cannot erase the
  evidence of the first read;
* a batch whose every message is a heartbeat is acknowledged automatically, because it
  carries no decision; any other batch is left for the coordinator to handle and
  acknowledge itself;
* a CLI failure, a JSON error or a lost binding is reported as an error and exits
  non-zero. It is never reinterpreted as "the queue was empty".

Only the Python standard library is used (POSIX file locks; macOS, Linux and WSL).
"""

import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

CLI = os.environ.get("ORCA_CLI_COMMAND", "orca")
CHILD = None


def env_number(name, default, cast):
    """Read a numeric environment override, falling back on a bad value.

    A typo in an override must not take the inbox down: an unusable value falls back
    to the documented default and is reported on stderr.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return cast(raw)
    except ValueError:
        print(f"ignoring invalid {name}={raw!r}; using {default}", file=sys.stderr)
        return default


def atomic(path, value):
    """Write ``value`` to ``path`` atomically.

    The temporary file is written and fsynced in the same directory as the target, so
    ``os.replace`` is a same-filesystem rename: a reader either sees the previous
    content or the complete new content, never a half-written file.
    """
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with tmp.open("w") as out:
            out.write(value)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def read_json(path):
    """Read JSON, returning ``{}`` when the file is missing or unreadable."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def log(directory, message):
    with (directory / "watch.log").open("a") as out:
        out.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + message + "\n")


def check(directory, run_id, terminal, args, timeout):
    """Run one ``orchestration check`` and return its parsed envelope.

    Output goes to files rather than pipes so a CLI that keeps the connection alive
    cannot fill a pipe buffer. The complete snapshot is published only after the child
    exits; a partial read is therefore impossible.

    The exit code is examined *before* the output is parsed. A failing CLI often prints
    nothing on stdout, and parsing that empty text first would replace the real reason
    (the exit code and stderr) with a JSON syntax error — exactly the kind of lost
    evidence that makes a hung orchestration hard to diagnose.
    """
    global CHILD
    cmd = [CLI, "orchestration", "check", "--run", run_id,
           "--terminal", terminal, *args, "--json"]
    token = uuid.uuid4().hex
    output = directory / (token + ".stdout.tmp")
    error = directory / (token + ".stderr.tmp")
    try:
        with output.open("w") as out, error.open("w") as err:
            CHILD = subprocess.Popen(cmd, stdout=out, stderr=err)
            atomic(directory / "state.json", json.dumps({
                "run": run_id, "terminal": terminal, "loopPid": os.getpid(),
                "childPid": CHILD.pid, "phase": "waiting" if "--wait" in args else "checking",
                "updatedAt": time.time()}))
            try:
                rc = CHILD.wait(timeout=timeout)
            except subprocess.TimeoutExpired as expired:
                CHILD.kill()
                CHILD.wait()
                raise RuntimeError("CLI timeout") from expired
        raw = output.read_text()
        problem = error.read_text()
        if rc != 0:
            raise RuntimeError(f"CLI exit={rc}: {raw[:1000]} {problem[-1000:]}")
        try:
            data = json.loads(raw)
        except ValueError as invalid:
            raise RuntimeError(f"CLI exit=0 with unparsable JSON: {raw[:1000]} {problem[-1000:]}") from invalid
        if data.get("ok") is not True or not isinstance(data.get("result"), dict):
            raise RuntimeError(f"CLI exit=0 without an ok result: {raw[:1000]} {problem[-1000:]}")
        return data
    finally:
        CHILD = None
        output.unlink(missing_ok=True)
        error.unlink(missing_ok=True)


def locked(directory):
    """Take the exclusive lock for this state directory, or return ``None``.

    The lock is advisory and per-directory: it keeps a second instance from consuming
    the same Run's queue. Orca's own waiter slots remain the cross-directory limit.
    """
    handle = (directory / "inbox.lock").open("a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def stop(signum, frame):
    """Reap the CLI child before exiting so no orphan keeps a waiter slot."""
    if CHILD is not None and CHILD.poll() is None:
        CHILD.terminate()
        try:
            CHILD.wait(timeout=3)
        except subprocess.TimeoutExpired:
            CHILD.kill()
            CHILD.wait()
    raise SystemExit(0)


def status(path):
    """Print this directory's lock and state without consuming the queue."""
    directory = Path(path).resolve()
    if not directory.is_dir():
        print("loop: DEAD (state directory missing)")
        return 1
    handle = locked(directory)
    alive = handle is None
    if handle is not None:
        handle.close()
    print("loop:", "ALIVE" if alive else "DEAD")
    print("state:", json.dumps(read_json(directory / "state.json"), ensure_ascii=False))
    saved = sorted((directory / "deliveries").glob("*.json"))
    print("saved batches:", len(saved), "(durable records; not necessarily unhandled)")
    marker = directory / "NEW-MESSAGE"
    if marker.exists():
        print(marker.read_text())
    print("Run an explicit check --peek to inspect the queue; status never consumes messages.")
    return 0 if alive else 1


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--status":
        return status(sys.argv[2])
    if len(sys.argv) != 4:
        print("usage: inbox-loop.sh RUN STATE_DIR COORDINATOR_HANDLE | --status STATE_DIR",
              file=sys.stderr)
        return 2
    run_id, path, terminal = sys.argv[1:]
    directory = Path(path).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    handle = locked(directory)
    if handle is None:
        print("already running for this state directory", file=sys.stderr)
        return 1
    binding = {"run": run_id, "terminal": terminal, "cli": CLI}
    previous = read_json(directory / "binding.json")
    if previous and previous != binding:
        print("state directory belongs to another Run/terminal/CLI", file=sys.stderr)
        return 2
    atomic(directory / "binding.json", json.dumps(binding))
    atomic(directory / "run-id", run_id + "\n")
    atomic(directory / "inbox-loop.pid", str(os.getpid()) + "\n")
    (directory / "deliveries").mkdir(exist_ok=True)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    wait_ms = env_number("WAIT_TIMEOUT_MS", 30000, int)
    backoff = env_number("BACKOFF_SECONDS", 5.0, float)
    pending_backoff = env_number("PENDING_BACKOFF_SECONDS", 30.0, float)
    pending_delivery = None
    try:
        while True:
            try:
                # Unfiltered first, every cycle, so heartbeats and ordinary messages
                # cannot sit at the head of the queue behind a type filter.
                data = check(directory, run_id, terminal, [], 45)
                messages = data["result"].get("messages")
                if messages == []:
                    data = check(directory, run_id, terminal,
                                 ["--wait", "--types", "worker_done,escalation,question",
                                  "--timeout-ms", str(wait_ms)], wait_ms / 1000 + 15)
                    messages = data["result"].get("messages")
                if not isinstance(messages, list):
                    raise RuntimeError("missing messages array")
                if messages:
                    did = data["result"].get("deliveryId")
                    if not isinstance(did, str) or not did:
                        raise RuntimeError("nonempty batch without deliveryId")
                    file = directory / "deliveries" / (
                        hashlib.sha256(did.encode()).hexdigest() + ".json")
                    # A replay never overwrites evidence, a restart never reuses an
                    # index, and an unhandled file is never rotated away.
                    if not file.exists():
                        atomic(file, json.dumps(data, ensure_ascii=False, indent=2))
                    if all(isinstance(m, dict) and m.get("type") == "heartbeat" for m in messages):
                        check(directory, run_id, terminal, ["--ack", did], 45)
                        log(directory, f"AUTO-ACK heartbeat-only {did}")
                        pending_delivery = None
                    else:
                        if did != pending_delivery:
                            atomic(directory / "NEW-MESSAGE", f"{did}\nfile={file}\n")
                            log(directory, f"PENDING {did} file={file}")
                        pending_delivery = did
                else:
                    pending_delivery = None
                # The marker is not cleared: an empty queue does not prove that the
                # batches already on disk have been handled.
                atomic(directory / "state.json", json.dumps({**binding, "loopPid": os.getpid(),
                    "phase": "backoff", "updatedAt": time.time()}))
            except (OSError, ValueError, RuntimeError) as error:
                # Permission, binding and waiter errors stop explicitly. Retrying
                # forever or borrowing another identity is forbidden.
                log(directory, f"ERROR {error}")
                atomic(directory / "state.json", json.dumps({**binding,
                    "phase": "error", "error": str(error)}))
                return 1
            time.sleep(pending_backoff if pending_delivery else backoff)
    finally:
        (directory / "inbox-loop.pid").unlink(missing_ok=True)
        handle.close()


if __name__ == "__main__":
    sys.exit(main())
