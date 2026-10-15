# Failure and reporting discipline

**When to read this**: when the CLI will not start, a `worker-start` receipt says `state: failed`,
a circuit breaker trips, or the Orca app restarts mid-run.

## 9. Failure and reporting discipline

- If the CLI will not start or the orchestration guide cannot be fetched: report the exact error
  and stop. **Do not swap the executable and do not guess commands.**
- **When a `worker-start` receipt says `state: failed`, gather evidence before deciding; do not
  relaunch blindly.** One observed case had `failedStage: agent_readiness` /
  `lastError: terminal_handle_stale`: it read like the terminal was gone, but the evidence showed
  **both terminals still present and the worktree already created** — the setup terminal was
  `status: exited` with `tail: []` (zero output), because the readiness check judged before setup
  finished. The full 6-step evidence and re-dispatch procedure is in
  `references/failed-dispatch-recovery.md` (read it only when you get `state: failed`). Skeleton:
  1. **Read the receipt's four fields** (`failedStage` / `lastError` / `recovery` /
     `residualResources`), then check whether the terminals and the worktree are in fact still
     there — criteria and commands are in that file.
  2. **Verify the hook itself**: run the setup command manually in the worktree; if it passes,
     the failure was transient.
  3. **Re-dispatch per `recovery`**: `--retry-of` together with `--task`, releasing the failed
     Dispatch first, then confirm the turn started per §4.3.1.
  **Why this is separate**: `terminal_handle_stale` reads like "cannot re-dispatch", while the
  positive guidance is sitting on disk. **"No relaunch" means no unconditional retry, not no retry
  per the recovery instructions.**
- When anything trips a breaker (per ticket: two consecutive failures of the same gate; run level:
  §6's cumulative send-back threshold) or an escalation-class issue (freeze that ticket, keep the
  rest going, §5.1) → stop and ask the human immediately, stating which stage you are stuck in,
  the evidence you have, and what the human needs to decide.
- **If the Orca app dies or restarts mid-run**: the symptoms are a failing foreground `check` and
  a background inbox process that exited. Recover in three steps: ① `orca status --json` to
  confirm the app is up; ② `orchestration worker-list --include-remote --json` to inventory each
  Dispatch's liveness and attention (Run / Task / terminal state is persisted by Orca and
  survives a restart); ③ restart the inbox per §4.5 item 1 and re-confirm each running worker's
  title per §4.3.1. Do not re-send any orchestration command before the app is confirmed up, and
  do not conclude from this that a worker is dead — §4.5 item 6: without evidence you are never
  authorized to stop it.
- **Run binding lost or consumer_fenced**: stop consuming and stop lifecycle operations on that
  identity, read the current version's recovery reference, and verify the real session/terminal
  against the original Run. `check` uses `--terminal` and does not accept `--from`; do not guess
  handles from titles, impersonate a worker, or unconditionally create a new Run. Do not create a
  duplicate editor before the old Dispatch is inventoried and its ownership is clear; if recovery
  is impossible, preserve the artifacts and report the binding blockage.
- Authorized implementation work is not skipped because the task is small or the repo lacks a
  `WORK_SCOPE` section; pure Q&A, reports and stages beyond this round's delivery endpoint are not
  dispatched. When the scope is unclear, explore read-only first and re-judge per §1.
- Advance later stages directly when they are inside this round's scope; when they are not, state
  their status and the next entry point in the report.
- Follow the repository's language for design terminology; use deep-module vocabulary when
  architectural analysis needs it.
