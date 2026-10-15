# `worker-start` returning `state: failed`: evidence and re-dispatch

**When to read this**: only when an `orchestration worker-start` receipt shows `state: failed`. The
normal path does not read it — reading it must not become a fixed cost on every dispatch.

**Why it is its own file**: it has six steps and costs roughly 700 tokens, while `state: failed` is
a low-frequency event. Keeping it in SKILL.md would mean paying that context cost every session for
something that rarely happens.

**The one sentence to remember**: "no relaunch" means **no unconditional retry**, not no retry per
the `recovery` field. `terminal_handle_stale` reads like "re-dispatching is impossible", but the
positive guidance is right there on disk — read it before concluding anything.

---

## The case this procedure comes from (the reason for each step below)

A `worker-start` receipt of this shape is the reason the steps below are ordered as they are:

```text
failedStage: agent_readiness
lastError:   terminal_handle_stale
```

It reads like "the terminal is gone, so re-dispatching is pointless". The evidence showed **both
terminals still present and the worktree already created**, with only the setup terminal
`status: exited` and `tail: []` (zero output) — **the readiness check judged before setup finished**.
The fault was neither in the ticket nor in the configuration.

---

## Procedure (six steps, order matters)

### 1. Read the receipt's four fields

```text
failedStage         Which stage failed
lastError           Error code
recovery            ← the most important: it directly gives the next command
residualResources   Leftover resources; this decides whether cleanup comes first
```

The `recovery` field usually already contains the command to run. **Read it before thinking**;
do not start by designing a retry scheme.

### 2. Take evidence, do not guess

Three read-only commands, each answering one question:

```bash
<ORCA> terminal show --terminal <setup handle> --json   # are both terminals still there (check `orphaned`)
git worktree list                                       # was the worktree really created
<ORCA> terminal read --terminal <setup handle> --json    # the setup terminal's status and tail
```

**Criterion**: terminals present + worktree present + setup exited with zero output ⇒ **the failure
is in the readiness check, not in your ticket**. Once that combination holds, do not investigate the
configuration direction — that path costs you two rounds before it dead-ends.

### 3. Verify the hook itself is good

**Manually run the command the repository's setup hook actually executes** in the worktree, after
confirming that command from the receipt or the repository configuration.

```bash
cd <worktree> && <this repository's setup command>
```

It passes ⇒ **transient**, not a configuration problem, and re-dispatching is safe.
It fails ⇒ handle the real setup error; do not re-dispatch blindly.

### 4. Read the recovery reference

```bash
<ORCA> skills get orchestration --reference references/recovery-and-cleanup.md
```

Its state table says:

> `failed` or `stopped` → Start a replacement with `--retry-of`; repeat placement explicitly

So **re-dispatching is not forbidden; the posture matters**:

```bash
<ORCA> orchestration worker-start --task <task_id> \
  --retry-of <failed_dispatch_id> \
  --worktree <explicit selector> --agent <§0's worker> --json
```

Two constraints to respect:

- **`--retry-of` must be paired with `--task`.** Pairing it with `--spec` creates another Task,
  which is a different ticket.
- **Placement is not silently inherited.** Give `--worktree` explicitly (with `--repo` or
  `id:<repo-id>::<absolute worktree path>`); do not expect it to carry over from the failed
  Dispatch.

### 5. Release the failed Dispatch first

```bash
<ORCA> orchestration worker-release --dispatch <failed_dispatch_id> --json
```

It never ran the Task, yet its terminals still occupy quota. **Release before re-dispatching**,
otherwise the new worker may fail to start on quota or waiter slots. The order cannot be reversed.

### 6. After re-dispatching, confirm the turn really started per §4.3.1

A `ready` receipt still proves nothing — that holds for a first dispatch and for a re-dispatch
alike. Read the title per §4.3.1, judge the idle banner, and send **one** bare Enter if needed.

---

## When to stop

- Step 3's manual setup run **fails** ⇒ not transient; investigate the real error, do not
  re-dispatch.
- The same ticket keeps returning `failed` ⇒ the per-ticket breaker of §6's send-back protocol is
  reached (two consecutive failures of the same gate), or it is time for §9's "report and stop". Do
  not loop on re-dispatching.
- The evidence shows **real uncommitted changes** in the worktree ⇒ that is not "failed", that is
  "half done". Confirm whether the deliverable is already persisted per §6 G-impl item 5, then
  decide between accepting and sending back.

## Related

- SKILL.md §4.3.1 — confirm the turn started after dispatch (applies to a re-dispatch too)
- SKILL.md §6 send-back protocol — per-ticket and run-level breakers
- SKILL.md §2 — no write ever lands on main; every evidence command here is read-only
