# Communication, wakeups and lost-contact recovery

**When to read this**: before the first dispatch of each Run, for identity binding, inbox setup,
wakeups, and lost-contact recovery. Before later dispatches, only verify that the inbox remains
active. Command semantics follow this round's `orca skills get orchestration` and its messaging and worker-contract references. This file
uses `<ORCA>` for the executable chosen this round; the script receives that path through
`ORCA_CLI_COMMAND`.

## 1. Identity and the inbox consumer

After creating a Run, write the returned Run ID, coordinator handle, and each
Task/Dispatch/worker handle into a ledger outside the repository. Handles come from the real
calling identity — never from a terminal title or from "the most recent terminal". A background
process names the coordinator explicitly with `check --terminal <coordinator_handle>`; `check`
does not take `--from`.

Each Run gets its own directory and its own single consumer. Startup example:

```bash
ORCA_CLI_COMMAND=<confirmed executable path> nohup <SKILL_DIR>/scripts/inbox-loop.sh \
  <run_id> /tmp/orch-<repo>-<run_id> <coordinator_handle> \
  > /tmp/orch-<repo>-<run_id>.log 2>&1 &
<SKILL_DIR>/scripts/inbox-loop.sh --status /tmp/orch-<repo>-<run_id>
```

The script needs Python 3's standard library only (POSIX file locks; works on macOS/Linux/WSL). A
file lock at startup excludes a second instance in the same directory, and a directory bound to a
Run/terminal/CLI may not be reused. Orca's waiter slots remain the final cross-directory
constraint. Do not migrate an old script's run directory: confirm and stop the old loop and its
waiter first, keep the old messages, and use a fresh Run-specific directory.

`--status` only inspects that directory's lock and state; it does not scan other Runs' processes
and does not consume the queue. Having no waiter during `phase=backoff` is a normal state and is
not a reason to start another instance. When you see `loop: DEAD`, check `watch.log`'s error and
the current Run binding first; do not auto-restart until the binding/permission/waiter issue is
resolved, and do not kill another Run's process.

Each cycle the script first checks without a filter, then waits at most 30 seconds, so heartbeats
and ordinary messages cannot pile up at the head of the queue. A complete response is written
atomically to `deliveries/*.json`, hashed by deliveryId; files are never rotated away. The same
unacknowledged batch is recorded as PENDING only once and re-checked at a longer interval
afterwards, so FIFO replay cannot cause duplicate log lines and CLI calls. `NEW-MESSAGE` is only
a hint about the most recently saved batch, **not a to-do list**; when a new message arrives or a
session resumes, enumerate every delivery file and reconcile against the ledger.

Errors are written to disk explicitly and end the process; a CLI failure, a JSON error or a lost
binding must never be interpreted as an empty queue.

## 2. Collecting and acknowledging

Maintain a per-message-ID ledger: `received → processing → handled`, recording reply receipts,
acceptance results, and terminal-ownership decisions. Reconcile first on recovery; a duplicate
Delivery is never re-replied, re-merged or re-released.

1. Read the whole Delivery and verify its Run/Task/Dispatch belong to this round's authoritative
   attempt; keep old attempts' messages as evidence and never complete a new attempt from them.
2. Answer questions with `reply --id <message_id>`; record anything awaiting a human decision as
   pending and never self-answer it on timeout. Validate a `worker_done` against the real Dispatch
   and artifacts; a settled lifecycle is not a passed deliverable.
3. Only after handling the whole batch and any needed terminal-ownership decision do you ack the
   `.result.deliveryId` of **that read snapshot** under the current Orca guide. Keep the ack's
   success receipt; on failure keep the ledger entry and re-verify — never assume it was
   acknowledged.
4. When a question waiting on a human blocks the FIFO, run a read-only
   `check --run <run_id> --terminal <handle> --all --json` to see later messages, handle other
   workers' questions and completion reports, and record them; `--all` offers no ackable Delivery
   and you must not fabricate an ID. Consume the original batch afterwards, batch by batch, and
   only reconcile already-handled messages.

The script auto-acks only a non-empty batch that is already on disk and where **every** message is
a heartbeat; mixed batches and unknown types always go to the coordinator. Type filtering only
decides when the waiter wakes, and does not remove the obligation to handle the whole batch. The
script never deletes a local to-do, and an empty queue does not mean the ledger is complete.

## 3. Coordinator liveness and wakeups

A successful `send` is a durable enqueue; wake and nudge are best-effort. `nohup`, a file
appearing, or a live background consumer does **not** mean the agent will produce a new turn, and
you must not claim "it will continue automatically" on that basis.

At dispatch time, choose and record the waiting method that fits the current harness's real tool
contract:

- With a confirmed task-completion notification: use that mechanism to wait for a new local
  delivery or for a check deadline; after each notification returns, handle messages first and
  then install the next wait. The notification mechanism's own completion and re-installation
  must be observable.
- Without a reliable notification: keep the current coordinator turn and wait in bounded tool
  calls, never more than 60 seconds each; after each return, read the inbox and ledger and
  continue other authorized work. Do not emit a final and assume a background script will wake
  you.

- When the environment forces the turn to end: report explicitly which Dispatches are still
  running, the last progress, the ledger directory, and the limitation that you cannot be woken
  automatically; the recovery entry point is that ledger plus the current Orca state. Never write
  this state as completed.

Check messages after every long operation, and no less than once every 60 seconds while idle.
After three rounds with no progress, enumerate this Run's
`worker-list --include-remote --json` (read every page if paginated), inspect `projection.nextAction`
and `liveness.reason`, and read `worker-show` / `worker-read` for the relevant Dispatches. Check
all three of local files, the server-side queue and worker state — do not stare only at
NEW-MESSAGE, and do not wait only for a worker_done.

## 4. The communication contract workers must follow

These requirements must be written into the §4.4 spec; a worker never sees this file automatically:

- Use the live preamble's real executable, handle, Task ID, Dispatch ID and any attached authority
  parameters.
- Check proactively with `check --terminal <own handle>` at every natural checkpoint, including on
  start, after tests, before switching files, and before finishing. The coordinator reaches a
  running worker with `send --to dispatch:<id>`; a send needs read/executed evidence afterwards.
- Resume an `ask` timeout under the same message ID; follow the preamble's heartbeat cadence; never
  open a user-facing question UI directly.
- On success or failure send exactly one `worker_done` from your own terminal, with an explicit
  outcome, a three-sentence summary and real artifact paths; keep the success receipt as evidence,
  then end the turn. A plain final, an already-open PR, a heartbeat, or "I am done" is not a
  lifecycle report.
- When the send result is unknown, inspect the Dispatch/message facts first; a settled dispatch is
  never re-sent. Only when it is confirmed unsettled, the report was not enqueued, and the
  authority is still valid may you retry once; if it still fails, keep the artifacts and report
  the communication blockage. On consumer_fenced, stop immediately.

## 5. Missing completion reports and lost contact

| Observation | Action |
| --- | --- |
| Dispatch settled, no worker_done in the inbox | Reconcile with `check --all`, the real settlement state and the artifacts; record it and continue acceptance. Do not ask for a resend and do not dispatch a duplicate editor |
| Worker turn ended, not settled, and the final turn sent no worker_done | Read the current Orca recovery guide. Once you confirm the terminal still belongs to the original active Dispatch and recovery is allowed, send one explicit finish-the-receipt instruction: check follow-ups, verify artifacts, report worker_done from your own preamble; re-check turnStart/transcript |
| `send` enqueued but unread by the worker | Check whether it is stuck in an `ask`, a permission prompt, or an already-idle turn; for a confirmed idle local terminal you may use the terminal resume mechanism to remind it to read the original Dispatch inbox. Do not re-dispatch the body as a new Task |
| `liveness=unverifiable` / `agentWait=null` / idle title | This is only missing evidence; read the transcript/`worker-show` and `nextAction`. Do not stop, do not release, do not re-dispatch |
| Real exit evidence and recovery impossible | Follow the recovery guide for stop/abandon/retry, keep the artifacts, and only dispatch a recovery worker after the old attempt's authority has ended |
| Wrong identity/Run binding, consumer_fenced | Stop operating on that identity and verify the real caller and the authority relationship; do not impersonate a handle and do not unconditionally create a new Run |

A finish-the-receipt nudge or a wakeup attempt is made at most once, then the evidence is
re-checked; if there is still no progress, preserve the state and report the blockage. Do not loop
injecting Enter, do not repeat the report, and do not re-dispatch on implicit authorization. The
coordinator never sends a worker_done on a worker's behalf and never edits or commits code for it.

## 6. Teardown

Completion reports, acceptance and merges are recorded separately. Release only after a real
settlement and persisted artifacts, per the lifecycle protocol; a settled terminal awaiting
acceptance or merge must not be silently left behind — keep an explicit next step and deadline in
the ledger. Once every expected Dispatch is handled and the ledger has no open items, stop this
Run's consumer (read the loop PID from this directory and confirm the process identity before
SIGTERM); the script reclaims its own CLI child processes. `nohup` does not exit with the session.
Only after the persistent audit report has saved the key receipts and conclusions should you
consider cleaning up temporary message files.
