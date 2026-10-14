# Security policy

## What counts as a security issue here

This repository publishes Markdown instruction bundles and one standard-library Python script. There
is no server, no service and no credential handling. Security issues therefore fall into three
groups:

1. **Credential or secret disclosure.** Any committed secret, token, or environment value; and any
   pattern in the published text that would cause a coordinator to print or persist one. The
   packaged skill explicitly forbids workers from reading or echoing credential values, and this
   repository's own disclosure scan rejects credential variable names and token literals.
2. **Unsafe instructions.** A change that would make a coordinator take a destructive or
   unauthorized action: writing on the main working copy instead of an isolated worktree,
   self-answering an escalation-class question (credentials, third parties, payment, manual
   approval, irreversible live-data operations), merging without passing a gate, or discarding an
   unexplained diff without preserving evidence first. Prompt-injection content in a reference file
   — instructions aimed at the agent rather than at the reader — counts here too.
3. **The inbox script.** Anything that loses a message, lets a replayed delivery overwrite saved
   evidence, acknowledges a batch a human still has to read, mistakes a CLI failure for an empty
   queue, or allows two consumers on one Run's queue.

## Reporting

Open a [private security advisory](https://github.com/whutlichao/orchestra-auto/security/advisories/new)
rather than a public issue. If you cannot, open a minimal public issue that says only that you have
a security report and ask for a private channel — do not include the details, the payload or the
value.

Please include:

- which of the three groups above it falls into;
- the file and, where relevant, the line;
- what an attacker or an unwitting coordinator could do with it;
- whether the content is already on a public branch (everything pushed is readable, including
  unmerged branches, so treat a pushed value as disclosed).

## What to expect

- Acknowledgement within a few days; this is a small project maintained by one person, so there is
  no 24-hour promise.
- A fix or a documented decision, plus a note in the change describing the issue at the level of
  detail that is safe to publish — usually the shape of the problem, not a working exploit.
- **You rotate your own credentials.** If the report is about a real leaked value, rotate it
  yourself first; do not rely on this repository's maintainer to do that for you, and do not send
  the value in the report. Say what kind of value it was and where it appeared.

## Handling a leak you find in this repository

1. Stop writing to the repository; do not push, merge or open a PR while it is unresolved.
2. Check whether the value is on any pushed branch. If it is, treat it as disclosed even if it is
   not on the default branch.
3. Report it privately as above, without repeating the value in any public or shared place.
4. Rotate the credential yourself. Removing it from a later commit does not remove it from history —
   the maintainer will decide whether a history rewrite is warranted, and you should not attempt one
   unprompted.
