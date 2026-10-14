# Formatter reflow noise: evidence and recovery

**When to read this**: after a worker finishes you find an abnormally large uncommitted diff, and a
file-by-file check shows large-scale pure formatting change. An abnormal line count is only an
investigation signal — it does not by itself prove the content can be discarded.

## Protect the real work first

Recovery is performed by the worker in its own worktree; the coordinator preserves evidence,
accepts the result, and hands back a concrete list of what is missing. Before any restore or stash,
save the following evidence to a directory outside the repository with restricted permissions, and
confirm the files are readable:

```bash
git status --porcelain=v1 -uall
git diff --binary > <evidence dir>/worktree.patch
git diff --cached --binary > <evidence dir>/index.patch
git ls-files --others --exclude-standard > <evidence dir>/untracked.txt
```

Untracked files must be copied or archived one by one; patches do not contain them. If a patch may
contain credentials, restrict access and avoid pasting it into messages. Compare `HEAD`, the index,
the working tree and the worker's edit record file by file, and mark which changes are real and
which are reflow noise. A non-empty `git diff --cached` only means the index has content — **it does
not prove the rest of the working tree can be discarded**.

## Recovery

Prefer rebuilding the real changes from the worker's edit history or an already committed version.
Only after confirming and backing up every real change in a file may you `git restore` /
`git checkout` that file; re-check the diff and the test results after recovery. When mixed hunks
cannot be split apart reliably, keep the evidence and have the worker redo the work on a clean copy
rather than guessing semantic equivalence from a whitespace-insensitive comparison. If two rounds
still do not converge the diff to the expected range, stop the automatic repair and report to the
coordinator.

## Prevention condition

Only when the current worker actually loads a formatter whose automatic reflow conflicts with the
repository's style should you write a local formatter override into **that worktree**'s root:

```json
{"format":{"enabled":false}}
```

Add that file to the worktree's local exclude (not the tracked one) and do not commit it. Other
workers, or repositories with an existing format convention, follow their own tooling
configuration. This setting is a local repair for a confirmed failure, not a fixed pre-step for
every ticket.
