# Documenting Changes

When and how to document a change to this codebase. The rule of thumb: the
commit says *what changed and why*, the docs say *how the thing works now*.
A reader should never have to reconstruct current behaviour from a commit log.

## The commit is the first document

Format and attribution are covered in
[Git Rules and Procedures](git-rules-and-procedures.md). What belongs in the
body:

- **Why**, not what. The diff shows what changed. Explain the reason it needed
  to change, and what you rejected — a future reader mostly wants to know
  whether they can undo it.
- **Evidence** for anything you claim works. "Verified: `docker compose build`
  succeeds and the image carries the fixtures" is worth more than "tested".
- **Constraints** that shaped the change. If three files had to move together
  or an intermediate state would have been broken, say so; otherwise someone
  will try to split it later.

## Which document to update

| You changed | Update |
|---|---|
| An MQTT topic, HTTP endpoint, or payload field | [`contracts/dock/v1`](../contracts/dock/v1/README.md) — schema **and** fixture, same commit |
| How the backend is run or configured | [`infrastructure/README.md`](../infrastructure/README.md) |
| A naming rule, lint setting, or tooling config | [Code Quality](code-quality.md) |
| Branching, commits, PRs, secrets handling | [Git Rules and Procedures](git-rules-and-procedures.md) |
| What the system must do | [Software Requirements](software-requirements.md) |
| Anything a first clone needs to get running | the root [`README.md`](../README.md) |

If a change touches behaviour and no document covers it, that is a gap worth
filling in the same PR, not a reason to skip documenting.

## The contract is the strict one

`contracts/dock/v1` is jointly owned by whoever owns the app and whoever owns
the service. A change there is a change to an interface two codebases depend
on:

- A new message shape needs its fixture in the same commit as its schema.
- Breaking changes — removing or renaming a field, narrowing a type, adding a
  required field, adding an enum case consumers switch over exhaustively —
  open `contracts/dock/v2`. They do not edit v1 in place.
- Additive, optional fields may land in v1.

## Keeping documents honest

A document that describes something the code does not do is worse than no
document, because it is believed.

- Write what is true **now**, not what is planned. Planned work is marked as
  such: `docs/testing.md` says the test target is a stub, because it is.
- When a safeguard does not fully solve the problem, say what it leaves open.
  The outstanding key rotation in
  [Git Rules and Procedures](git-rules-and-procedures.md) is recorded that way
  on purpose.
- Prune rather than accumulate. A superseded document should be deleted, not
  left to contradict its replacement — and any link to it fixed in the same
  commit, so the docs never contain a dead reference.

## Pull requests

One PR, one concern. The description says what changed and how it was
verified; reviewers should not have to run it to find out whether it works.
Link the issue with `Closes #N`.

## Release promotion procedures

When promoting changes from the `dev` integration branch to `main`:

1. **Verify integration**: Ensure all features and fixes targeted for the release have
   merged into `dev` and all CI checks are passing.
2. **Open a release PR**: Open a pull request from `dev` targeting `main`
   (e.g. titled `chore(release): vX.Y.Z`).
3. **Document release changes**:
   - Aggregate conventional commit messages since the previous tag to draft the release
     notes and changelog.
   - Detail any breaking changes, schema updates, or configuration adjustments.
   - Update any relevant release versions or documentation.
4. **Merge and tag**:
   - Merge the release PR into `main` after review approval.
   - Tag the release commit on `main` following [SemVer](https://semver.org/)
     (e.g. `git tag -a vX.Y.Z -m "Release vX.Y.Z"` and `git push origin vX.Y.Z`).
5. **Back-merge fixes**: If any hotfixes or release-specific adjustments were made
   directly on `main`, merge `main` back into `dev` immediately to maintain parity.