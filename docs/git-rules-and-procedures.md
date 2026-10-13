# Git Rules and Procedures

Workflow and rules for contributing to AVP vROC.

## Branching Model

Git Flow with two permanent branches:

- `main` — production/release branch; reflects current release state, releases tagged from here.
- `dev` — integration branch; active development occurs here, feature branches merge into `dev`.

Feature branches are short-lived: branch from `dev`, merge back into `dev` via PR, then delete.
Neither `main` nor `dev` accepts direct pushes; contributors push freely to their own
feature branches.

## Branch Naming

Conventional-commit prefixes, kebab-case, short and imperative:

- `feat/<desc>` — new feature
- `fix/<desc>` — bug fix
- `docs/<desc>` — documentation
- `chore/<desc>` — build, dependencies, or maintenance (no user-facing change)
- `refactor/<desc>` — code change with no behavior change
- `test/<desc>` — tests

Example: `feat/add-telemetry-panel`.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): subject`.

- Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `build`, `ci`.
- Scope optional; subject imperative, lowercase, no trailing period.
- Example: `feat(telemetry): add attitude dial`.

### AI-Assisted Commits

Work done with an AI coding agent should indicate the tool used. You may use a
bracketed tag in the **subject line** (`[Claude]`, `[Codex]`) and/or a standard
`Co-Authored-By:` trailer in the commit body.

```text
fix(security): move the map API keys out of Info.plist [Claude]

Co-Authored-By: Claude <noreply@anthropic.com>
```

Attribution is not a disclaimer: the author is still accountable for the change,
and it is reviewed like any other.

## Pull Requests & Review

- One PR = one concern (a single issue).
- Track all work in an issue; open the PR as a draft and link the issue.
- Require at least 1 approving review before merge.
- Squash commits on merge.
- Delete the branch after merge (enable auto-delete).
- Title follows the branch prefix, e.g. `feat: add telemetry panel`. Use the PR
  template (`.github/PULL_REQUEST_TEMPLATE.md`) and `Closes #N` for the issue.

## Direct Pushes Forbidden (Honor System)

Because this private repository operates on a GitHub plan without automated branch protection
rules, GitHub will not technically reject a direct push. Instead, the team operates on an
honor system:

- **Never push directly to `dev` or `main`**: All features, bug fixes, and maintenance
  must arrive via Pull Request.
- **`dev` (default branch)**: Active integration branch. Target of daily feature and fix PRs.
- **`main` (release branch)**: Stable milestone branch. Target of release promotion PRs
  and emergency `hotfix/*` PRs.
- **PR required**: Every change to `dev` or `main` requires ≥1 approval and passing CI
  checks before merging.
- **Feature branches**: Push freely to your own feature branches; shared branches merge via PR.

## Merge & Release Flow

1. Branch `feat/*` (or `fix/*`, `chore/*`, `refactor/*`) off `dev`.
2. Open a draft PR targeting `dev`; link the issue.
3. After ≥1 approval and passing CI checks, squash-merge into `dev`.
4. Periodically, once `dev` has been tested and has accumulated changes for a release:
   - Open a release PR from `dev` into `main`.
   - After review and passing CI checks, merge into `main`.
   - Tag the release from `main` with [SemVer](https://semver.org/) (`vMAJOR.MINOR.PATCH`).
   - Conventional Commits enable an auto-generated changelog.
5. For emergency production fixes, branch `hotfix/*` off `main`, PR into `main`, and
   back-merge to `dev`.

## Branch Lifecycle

- Delete the branch after merge.
- Prune stale branches regularly: a branch with no open PR and no recent activity
  should be closed or deleted.

## Force-Push

- `git push --force-with-lease` is allowed only on your own feature branch.
- Never force-push `main` or `dev`.

## What Not to Commit

- Secrets: API keys, tokens, credentials. Never in source or `Info.plist`.
- Large binaries: videos, `.usdz`/`.usdc` models, archives. Use Git LFS or external
  storage.
- Build artifacts and generated files.
- OS junk: `.DS_Store`, `__MACOSX/` AppleDouble files.

## Secrets Handling

- Keys live outside the repo (git-ignored config or environment variables).
- For the visionOS app that means `apps/avp-vroc/Config/Secrets.xcconfig`: copy it
  from `Secrets.example.xcconfig` and fill it in. `Base.xcconfig` includes it
  optionally and `Info.plist` refers to the values as `$(MAPTILER_API_KEY)` and
  `$(OPENAIP_CLIENT_ID)`, so no key is ever written into a tracked file.
- If a secret is committed: rotate it immediately, remove it, and rewrite history if
  the value is reachable from any branch or tag.

### Outstanding

The MapTiler and OpenAIP keys were committed in plaintext in `Info.plist` before
2026-09-07 and remain reachable from `origin/dev`, `origin/docs/monorepo-design`
and the history of this branch. The safeguard above stops it recurring but does
not undo the exposure: **both keys still need rotating** at MapTiler and OpenAIP,
after which `Secrets.xcconfig` takes the new values.