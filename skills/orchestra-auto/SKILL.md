---
name: orchestra-auto
description: >-
  Coordinate supervised Orca workers and drive authorized development or planning work all the
  way to acceptance and auto-merge. Use whenever the user asks you to hand out work, supervise
  multi-ticket efforts, or run Orca workers: the coordinator plans, communicates and accepts,
  workers edit, commit and open PRs, and the coordinator merges automatically once the gates
  pass without asking the user ticket by ticket. Also use it when the user mentions Orca
  orchestration, worker dispatch, worktree isolation, acceptance gates, or PR auto-merge in an
  Orca session. Plain question answering, reading, and reviewing or editing this skill do not
  start an orchestration run.
---

# Orchestra Auto — the fully automatic dispatch loop

You are the coordinator. Start by pinning down the scope the user asked for. Any change that
lands in a project repository this round is by default committed by a worker, pushed on a
branch, and opened as a PR; once the gates pass, the coordinator merges it automatically and
syncs the main branch. The user has already authorized this default, so do not ask again
before merging. If the user explicitly asks to stop at an open PR, if repository rules block
the merge, or if a gate has not passed, keep the PR and report the real state. Pure Q&A and
reports that write no repository files create no PR.

A human appears at three moments: they said one sentence when the task started; a worker asks
a decision-class question and the human is invited to settle it (§5); or something genuinely
requires a human (credentials, third party, approval). **What auto automates is the process
(dispatch / gates / sending back), not the decisions** — a worker's recommended answer is
reference input only. For anything §5 classifies as decision-class, attach your own leaning,
ask the human, and only then reply to the worker.

This skill supplies the orchestration procedure; the user's request, the repository's
conventions and the current tool contract decide this round's scope and execution. Channel
selection is §1, role boundaries are §2, and dispatch parameters are §4. It does **not**
depend on the target repo's `AGENTS.md` having a `WORK_SCOPE` section — **a missing section is
never a reason to stop**.

```text
user input → §1 pin the delivery endpoint and channel → §2 hard-rule self-check → §4 dispatch a worker if edits are needed
              → §4.5 collect messages in the background, make progress in the foreground (never idle-wait)
              ⇄ §5 answer (decisions go to the human) → §6 gate acceptance
              → send back or advance → after the project PR passes G-merge, §6.5 auto-merge → teardown
              (worker-release, reclaimable drained) → §7 closing report; stop at the agreed delivery endpoint
```

Files under `references/` are read conditionally; SKILL.md keeps the routing and the core
constraints. Each reference states its own trigger in its opening lines:

| File | When to read it |
| --- | --- |
| `references/dispatch-preflight.md` | Before every dispatch (tick every line), and at teardown when checking for formatter noise |
| `references/spec-contract.md` | When writing a worker's spec, on any channel and for any ticket type |
| `references/gate-acceptance.md` | When a ticket closes and you pick a gate; when merging a project PR or settling a worker |
| `references/inbox-and-waiting.md` | Before dispatching (identity binding, inbox, wakeups, lost-contact recovery) |
| `references/worker-start-and-recovery.md` | `turnStart` unconfirmed, a permission prompt, or a worker gone silent |
| `references/gates-docs-planning.md` | This ticket is a design / spec / ticket-splitting ticket heading for G-docs / G-wayfinder / G-spec / G-tickets |
| `references/reformat-noise-recovery.md` | §4.0.1 finds tens of thousands of lines of uncommitted change (formatter reflow noise) |
| `references/failed-dispatch-recovery.md` | `worker-start` returns `state: failed` |
| `references/failure-and-reporting.md` | The CLI will not start, a breaker trips, or the Orca app restarts mid-run |

## 0. Initialize only when executing orchestration; editing this skill does not start a run

Enter the flow below only when the current task actually asks for Orca orchestration. When the
user asks to modify or review this skill, it is material to be edited: create no Run, dispatch
no worker, and do not switch roles just because you read the body text.

First use §1 to decide whether this round really needs a worker. Read the live worker settings
only when you are about to dispatch; pure Q&A or a pure report does not depend on them. A
user-named agent outranks the default, and the disabled list must still be checked.

Read the live Orca settings for this profile and record exactly two fields: the current default
TUI agent and the current list of disabled TUI agents. **This read is the only source of truth
for this machine's worker preference.**

- Locate the profile directory from the live CLI (for example the settings path reported by
  `orca agent hooks status --json`), then read the settings document Orca stores for that
  profile and take the default TUI agent and disabled TUI agents from it.
- The exact file, table and field names are **Orca-version specific**. Resolve them from the
  current CLI help and the current Orca skill guides rather than hardcoding what an older
  version wrote. When the command you were going to use does not match the current public
  documentation, do not guess: raise an `ask` with the evidence.
- Do not infer the current values from stale exports, old snapshots, cached backup files, the
  specific agent names mentioned in this skill's body, eval fixtures, or old logs. The
  dated observations in this skill describe behaviour at that time; they are not current
  settings.

When the user names no worker, fill the worker slot with the current default you just read.
When the user names one, use that one. In both cases check the current disabled list: if the
chosen agent is disabled, stop and report rather than silently substituting a guess. If the
read fails, if there is no settings row, or if these fields are empty, stop and report that
the settings are unreadable.

```text
mode orchestra-auto | channel <A|B|C> | intent <task type> | pre-skill <actual path / none> | worker <actual agent / none> | delivery endpoint <answer / report / merged project change / other endpoint the user named>
```

All six columns need **concrete values**; "TBD" is not allowed. When not dispatching, write
"none" for worker. When dispatching, the pre-skill column must be that skill's real absolute
path — writing "TBD" pushes the single most important decision of this round onto your future
self, and in practice that push never gets picked back up (channel B is `implement`, channel C
is `grill-with-docs`; §1's table settles it right now). The worktree name is a slug you take
at dispatch time; it is not part of the delivery endpoint.

**How to fill the worker column**: if the user named an agent, use the named one ("run it with
pi" → `pi`). **Being named outranks the default setting** — what the user explicitly asked for
always beats a machine preference. If they named none, read the live settings as above and use
what you read. Both paths are still bounded by the live disabled-agent check.

Why follow Orca's setting instead of hardcoding: the worker's harness is a machine preference.
Hardcode it and the day the user changes their default agent, the skill keeps dispatching the
old one — and that drift only becomes visible when "the worker behaves wrong", by which point
a whole dispatch round is already burned. There is a more direct reason too: `worker-start` does
not consult that setting on the local path, and it raises `agent_unconfigured` when the agent is
missing or unrecognized rather than falling back to a default. The only way to obtain the value
is to read it and pass it explicitly. That value feeds both `--agent` and the idle-banner string
you watch in §4.3.1, and both are needed the moment you dispatch (the agent table is §4.3).

If the settings are unreadable, or neither `worker-start --help` nor the Orca command registry
can confirm the agent, report per §9 and stop. **Do not guess, and do not casually dispatch an
unverified harness**: without a usable start criterion, §4.3.1 degrades into "eyeball the
title". If Orca recognizes an agent but you have no table entry for it yet, do the evidence
steps above, dispatch, and then add the entry.

**Deciding whether you may dispatch requires the live settings**: the chosen agent must be
recognized by `worker-start --help` and must not appear in the disabled list you just read.
The §4.3 table records each agent's start and title criteria; it is not the source of default
values or of disabled state. If the chosen agent has no entry yet, check `worker-start --help`,
the working / permission / idle labels Orca's agent registry reports, and the live disabled
list. Once you have confirmed Orca supports it and it is not disabled, dispatch normally.
Prefer the receipt's `turnStart: observed` as the start criterion; otherwise observe the live
title per §4.3.1 and add the verified shape to the table.

## 1. Channel and delivery endpoint

Record what the user asked for and where they want it to stop. Project changes become an
automatically created and merged PR by default. Exploration may change the implementation path;
it may not widen the work.

| Request | Channel | Handling |
| --- | --- | --- |
| Explanation, status, discussion, or a verbal research conclusion | A | Answer directly; no worker, no writes |
| A clearly bounded small change, a bug fix, an existing spec or ticket | B | Read-only exploration, then dispatch an implementation worker; for bugs start with `diagnosing-bugs` |
| Research, design, spec or tickets that must land on disk | B/C | Use the matching `research`, `grill-with-docs`, `to-spec`, `to-tickets`; stop at the named artifact |
| A multi-ticket or not-yet-settled full implementation request | C | Converge on requirements and dependencies first, then dispatch along the DAG |
| External issues/PRs, conflicts, or terminology governance | B/C | Use the repository's triage, conflict-handling or domain-modeling flow |

When the fog is heavy and no stable requirement can be formed yet, `wayfinder` can produce a
map and decision tickets; read the target repository's wayfinding conventions first and do not
invent labels when they are missing. If the change would overturn an existing ADR or a planned
decision, settle that decision first. A full implementation request normally runs
`grill-with-docs → to-spec → to-tickets → implement`, but when a valid spec or ticket already
exists you enter at the matching stage. If only design was asked for, stop once the design
artifact's PR is merged; do not automatically continue into implementation. If the user
explicitly asked for an open PR only, stop at that exception.

If §4.1's read-only exploration turns up multiple tickets, forked approaches or a cross-module
seam, re-judge the channel and restate the mode declaration. If the scope itself is unclear,
raise it for a human decision per §5; never convert a discussion request into implementation
authorization.

## 2. Role boundary: the coordinator plans and accepts, workers edit and commit

- The coordinator does read-only exploration, task splitting, dispatch, message handling,
  answering questions, running acceptance, and executing authorized PR merges.
- Every addition, edit, format, restore, conflict resolution, stage, commit, push, and PR body
  for a project file is done by a worker inside that ticket's worktree; this includes
  governance documents, ticket status and Answer text, and one-line fixes.
  **The coordinator must never edit or commit inside a worker's worktree, and must never
  bypass this boundary with a script or another agent.**
- The coordinator may write task specs, communication ledgers, evidence and reports outside the
  repository; `/tmp` is for process artifacts and a persistent audit directory under the user's
  home is for durable audit. Landing files inside the project is the worker's job.
- Check who is writing and where before every write. If project files, the index, or branch
  content would change ⇒ dispatch a worker. Acceptance caches and artifacts go in a temporary
  acceptance directory and never update the user's main working copy.
- The coordinator may create an isolated acceptance worktree, fetch, run checks and merge PRs,
  and after each merge **pull the merged main branch** per §6.5.1. That is syncing accepted
  work, not implementing it or creating commits. Only a clean main working copy may run
  `git pull --ff-only`; do not reset, do not auto-stash, and do not switch the user's current
  branch. Post-merge verification may check out the corresponding remote main commit in a
  temporary worktree to isolate caches and test artifacts.
- On a missed change, formatter noise, a missing commit/PR, or a merge conflict: list the
  evidence and send it back to the worker. If a worker is unreachable, confirm its state and
  resume or replace it per the communication recovery protocol; the coordinator does not take
  over the implementation.

## 3. Lightweight implementation

A single ticket whose approach is settled and whose blast radius can be bounded goes down
channel B: one isolated worktree, a short spec, and verification proportionate to the risk. Bug
fixes need regression evidence that reproduces on the old code and passes on the new. Pure copy,
style or configuration changes are accepted with an applicable check and an observable result;
do not manufacture red-green tests for them. Project file changes are committed to a PR and
auto-merged by default.

A two-axis review may be omitted for a small change with a bounded radius if the reason is
recorded in both the spec and the Answer. When the change spans tickets, touches a shared
interface, or has an unclear blast radius, G-impl selects the wider verification instead.
Documentation and planning tickets run their own gates and are not wrapped in source-test
gates. Small size does not change the role boundary: authorized implementation work is still
edited by a worker in an isolated worktree.

## 4. Dispatch (channels B / C)

### 4.0 Pre-dispatch preflight

Run the preflight checklist in [dispatch preflight](references/dispatch-preflight.md) and tick every line
before dispatching. Its two mechanical criteria — the `code-review` mention in an implementation
spec, and the base-commit check on every baseline number — are the ones that actually catch a real
mistake.

### 4.0.1 Formatter noise at teardown

After a worker reports `worker_done` and before declaring a gate passed, run the teardown check in
[dispatch preflight](references/dispatch-preflight.md).

### 4.1 Read-only exploration

Gather the facts needed to write the spec on main first (three parallel reads at most).

**Exploration's endpoint is the spec, not the edit.** The moment "I could just change this line
myself" appears — that is the signal to dispatch, not a licence to skip it.

### 4.2 Fetch the orchestration guide (once, to disk)

```bash
<ORCA> skills get orchestration > /tmp/orchestration-guide-<repo>.md
```

Grep the on-disk file afterwards. Do not repeatedly `head -120` / `sed -n '250,420p'` the same
output — that burns dozens of tool calls for nothing (one session spent several dozen on it). It
lives in `/tmp` only (§2). Pull `--reference references/<file>.md` when you hit a
specific action gate.

### 4.3 ★ Overriding Orca's default placement (the single most important rule here)

**Orca's default puts a worker in the current (= main) workspace** — "a fresh worker means a
fresh agent terminal, **not** a new Git worktree". That directly contradicts §2's hard rule, and
**orchestra-auto explicitly overrides Orca's default here.**

**Project binding comes from the calling Orca context, not the shell's cwd.** The coordinator is
normally standing in the target repo, but if the session cwd differs from the target repo
(working against a fixture, or dispatching into another repository) you must add an explicit
`--repo <selector>`, otherwise the worktree is created inside whatever project the cwd belongs
to. This one was learned the hard way.

Every task worker, without exception:

```bash
<ORCA> orchestration worker-start --spec "<spec>" \
  --worktree new-top-level --name <ticket slug> --setup run --agent <§0's worker> --json
```

- `--worktree new-top-level`: an isolated top-level worktree, cut from the default base ref.
  **Never `current`, never `new-child`** — the first is main, the second may land inside a
  subdirectory of main.
- `--name`: the ticket slug, so the worktree is recognizable later and locatable on a send-back.
- `--agent <§0's worker>`: **must be explicit; there is no "use the default" form** —
  `worker-start` raises `agent_unconfigured` when `--agent` is missing or unrecognized, because
  it does not read the default TUI agent (that default only serves the GUI composer path). So
  this column cannot be omitted, and its **value** comes from §0's worker column.

  Per-agent titles, permission prompts and TUI resume criteria are in the
  [start and recovery reference](references/worker-start-and-recovery.md); read it only when the
  receipt does not confirm the turn started or you hit an interactive prompt.

- Judge whether an agent is usable from the live **disabled list** read in §0, not from `which`;
  Orca may recognize an agent that the current profile still disables. The live settings read is
  the only configuration criterion; the dated observations in this table only explain verified
  start behaviour and must not be used to infer current defaults or availability.
- `--spec` in one shot (`worker-start --spec` creates the Task and the attempt together). Reach
  for `task-create` + `worker-start --task <id>` only when several tickets have dependencies,
  when you need a planned fan-out, or when retrying a known Task.
- Immediately after the receipt, confirm the turn really started per §4.3.1, and verify §4.5's
  inbox consumer and waiting method.

### 4.3.1 Confirming the turn started after dispatch

`state: ready` only means the Dispatch is ready. Prefer the receipt's `turnStart: observed`; if
it is `unsupported`, `unobserved`, or absent, read the
[start and recovery reference](references/worker-start-and-recovery.md) and confirm the start
with evidence that agent actually supports. Orca allows workers without a terminal: check
`worker-show` for the handle first, and never force `terminal show` onto a worker that has no
terminal. If you cannot prove it, gather evidence per §9 rather than entering a blind wait.

### 4.4 The spec contract

Write the spec from the template in [the spec contract](references/spec-contract.md); every element there
is required, including the behaviour rules, the pre-skill's absolute path, the ticket-type and gate
line, and the `Not run this ticket` line. A worker sees only the spec, so anything you leave out is
something it will not do.

### 4.5 Communication loop: enqueue, collect, handle and wake are verified separately

Read the [communication and recovery protocol](references/inbox-and-waiting.md) before
dispatching. Keep one ledger per Run outside the repository: Run/coordinator handle,
Task/Dispatch/worker handle/worktree, last progress, message IDs, handling state, completion
receipt, PR, next check time. After context compaction or recovery, read the ledger and the
real Orca state first; never guess identity from an old conversation.

- Prepare a single inbox consumer and a waiting method before the first worker starts; after
  every dispatch confirm the turn started and check the consumer.
- One background consumer per Run, bound to the real coordinator handle; messages are saved
  atomically by deliveryId, a restart never overwrites, and unhandled evidence is never rotated
  away. The script provides no agent-wakeup ability.
- Deduplicate every message by message ID and verify its Run/Task/Dispatch. Acknowledge only
  after the whole batch and any needed terminal-ownership decisions are handled. When the
  current batch is blocked on a human decision, use a read-only `check --all` to inspect
  following messages and keep handling other workers promptly; an ack is not a reply, and you
  must not ack with an unreviewed deliveryId lifted from a different check.
- Collect messages after long operations and while idle. A single foreground wait never exceeds
  60 seconds; after three rounds with no progress, inspect worker-list / worker-show /
  worker-read, the queue and the local ledger, and recover from evidence rather than waiting
  blindly.
- Unless the environment forces the turn to end, ending a coordinator turn with work still in
  flight requires a **confirmed** notification mechanism for the next turn. An unverified
  background process, a message file, or a successful `send` does not count. With no automatic
  wakeup, keep the current turn in bounded polling; when the environment must take control back,
  state explicitly what is still running, that you cannot be woken automatically, and where the
  recovery entry point is — never claim you will continue automatically, and never leave the
  user to prod you on a schedule.
- Recovery for a missing worker_done or an already-idle worker, plus error and stop conditions,
  follow the reference.

## 5. Reply protocol: decisions go to the human, details are answered for them

For every worker question (from grill / wayfinder / prototype and so on), classify first, then
decide who answers. The core of this skill still stands — the flow must not stall on a question
— but "never ask the human" is no longer the default.
Merging an already-authorized project change is an execution step of §6, not a product decision
that needs re-approval; escalate per this section only when the merge would change the scope the
user set or needs extra external authorization.
The `➡️ <recommended>` line in a grilling format is reference information from the worker:
**no question may go straight from recommendation to answer without classification.**

### 5.1 Classification criteria (go through them one by one; any hit makes it decision-class)

1. **It affects the deliverable's shape or user-observable behaviour**: product direction,
   requirement trade-offs, visible UI / copy / interaction choices.
2. **Approach fork**: several viable implementation paths where the choice affects architecture,
   dependencies, seams, or the split of later tickets.
3. **Scope boundary**: whether a feature is in, what goes in Out of Scope, how strict acceptance
   is.
4. **The escalation five**: credentials, third-party accounts, payment, manual approval,
   irreversible live-data operations. These skip the other criteria, stop immediately, and the
   question is forwarded to the human verbatim, waiting for a human answer before anything
   continues. Stopping more often is preferred to answering for them.
   **What stops is this worker, not the whole run**: with several tickets in flight, an
   escalation freezes the ticket in trouble while the others keep advancing through their gates
   — one ticket's credential problem must not freeze the whole pipeline. A global freeze happens
   only when §6's send-back protocol trips the run-level breaker.

A question that touches none of the four — naming, directory placement, implementation
technique, test style, in-library API usage — is **detail-class**, and you answer it (§5.3).
Self-check as in §3: if you cannot write down why it touches none of the four, treat it as
decision-class. If the reason cannot be written, the classification does not hold.

Note that this is the opposite of the older direction: the old version listed "the requirement is
unclear / I am not sure which option the user wants" as never-ask, must-decide-alone. **Now that
is exactly what criteria 1 and 2 cover, so it must go to the human.** The user explicitly asked
that decisions not be answered straight from the recommendation — decision-class questions going
to the human are the target behaviour, not an interruption.

### 5.2 Decision-class: attach your leaning and ask the human

Pause the reply to the worker and put three things in front of the human:

- the worker's original question (including its recommendation and reasoning, if any);
- your own leaning and a one-line reason (grounded in the project context, an ADR, the spec, or
  the user's own words);
- a one-line cost for each remaining option.

Only after the human confirms or changes it do you reply to the worker with
`reply --id <original message_id>`. When the human's choice differs from yours, theirs wins; do
not relitigate. If you have a genuinely strong technical objection, say it once, and if the human
does not change their mind, follow theirs. A worker's `ask` blocks — it waits for your answer —
so make the question complete in one pass to reduce round trips.

### 5.3 Detail-class: the coordinator answers

Use the project context, an ADR, the spec, or the user's own words as the basis, and pick the
option closest to the intent the user already expressed and to the existing architecture. When
the worker's recommendation does not conflict with its reasoning, answer as recommended; when it
does, explain in the reply why you are dropping the recommendation. Write the reason into the
reply.

### 5.4 Record (both classes)

Append `Q → A (human-decided / answered-for-them) → one-line reason` to the task thread (or the
Answer's Decisions section); for human-decided ones also record the key points of the human's
choice. §7's report summarizes this audit list, and the human may overturn any answered-for-them
entry afterwards.

### 5.5 Reply channel

Replies go back over the same orchestration channel (`reply`); introduce no other tool to answer
a worker. Asking the human uses this session's question channel — that is the only place the
coordinator is allowed and required to ask; the worker-side ban in §4.4 BEHAVIOR RULE 1 is
unchanged.

## 6. Gate acceptance

Verify observable results and evidence yourself, and on failure list what is missing and send it back.
Choose the gate by ticket type and follow [gate acceptance](references/gate-acceptance.md). That file
also covers G-impl item by item, the G-merge composition rules, §6.5 merge execution and §6.5.1's local
main sync, plus the worker lifecycle and send-back protocol.

## 7. Landing work, implementation, and closing

Each round is bounded by the scope declared in §0. A full implementation request with unclear
requirements runs `grill-with-docs → to-spec → to-tickets → implement` in order; with a clear spec
or existing tickets you enter at the matching stage. A design-only, spec-only or tickets-only
request closes once that stage's artifact PR is merged, and you do not drift into implementation
on your own. When the user explicitly asked to keep an open PR, close at that exception.

- Design tickets are accepted under G-docs or G-wayfinder. If this round also includes to-spec /
  to-tickets, keep landing and reconcile the tracker: the requirement anchor labels and states
  follow the repository's conventions, implementation tickets exist, and dependencies are
  queryable. If this round excludes those stages, the report records the follow-up entry point
  explicitly and does not mark the unauthorized stages as defects.
- Dispatch along the DAG frontier; a downstream ticket with dependencies waits until the upstream
  result is in the agreed base. The default maximum of concurrent workers is 3; if resources,
  quota or task independence differ, record the reason for adjusting it in the ledger.
- Each implementation ticket completes the applicable tests and review on its own diff;
  cross-ticket integration is handled by §6's pre-merge gates. When the same field or interface
  changes across call sites, the Answer enumerates every relevant location and its disposition.
- Terminology and ticket style follow the repository's existing conventions. Ticket-splitting
  options state the ticket count, each ticket's deliverable and their dependencies, and avoid
  undefined abbreviations.

The closing report goes in a durable directory outside the repository and must be readable on its
own, without depending on `/tmp` persisting. Record: this round's request and delivery endpoint;
the actual artifacts with their commit/PR/merge state; the key acceptance results and evidence
locations; the decisions the human made and the ones answered for them; unfinished items; and the
worker lifecycle count. For project changes, list each PR's merge SHA, the local sync result and
the final main-branch HEAD; when a merge could not happen, state why. An open PR is this round's
endpoint only when the user explicitly asked to stop there, or when repository rules or a gate
blocked the merge.

## 8. Planning dependency initialization (on demand)

Only when this round really uses `grill-with-docs`, `to-spec`, `to-tickets` or `triage`, and the
configuration they need is missing, check what the repository's planning setup requires. Reuse the
repository's existing issue tracker and domain docs configuration first. If initialization would
add governance files, labels or PRs, confirm those belong to the user's requested planning scope;
do not change unrelated configuration just because the skill ran. When initialization is really
needed, a worker lands it in an isolated worktree and the coordinator accepts it.

## 9. Failure and reporting discipline

When the CLI will not start, a `worker-start` receipt is `state: failed`, a breaker trips, or the Orca
app restarts, follow [failure and reporting](references/failure-and-reporting.md) instead of
improvising. The recurring shape of every rule there: gather evidence before deciding, report the exact
error, and never relaunch unconditionally.
