---
paths:
  - ".github/**"
---

# CI rules

- Pin every third-party action to a **full commit SHA** with the version in a comment, and read its
  inputs from its `action.yml` at that commit instead of recalling them.
- Minimal permissions: workflows are `contents: read`. Only the one job that creates the draft
  release gets `contents: write`, and nothing else does.
- Releases are **drafts only**. No step publishes, uses `--latest`, or edits a published release;
  the owner publishes by hand. A tag is only built if it matches the app versions and is on
  `master`.
- **Never reference a branch named "main".** Production is `master`. Workflows trigger on `master`,
  `develop` and `release/*` only.
- Workflows call the repository's own scripts (`scripts/*.mjs`) so CI and `npm run dist` cannot
  drift. Do not put build logic in YAML.
- Everything bundled is pinned with a checksum. A download that does not match is deleted, not
  used.
- No model ever runs in CI. Tests needing a real Ollama are marked `integration` and excluded
  (`-m "not integration"`): running them would mean inference on someone else's machine, which is
  the thing this product exists to avoid.
- No secret is needed to build, and none is added. The installers are unsigned on every platform.
- `workflow_dispatch` only works once a workflow is on `master`, so while developing one, ask for
  it with a label on a `develop` pull request. A push cancels the previous run of the same group.
- A failing job: read the failed step's log (`gh run view <id> --log-failed`), fix the cause, push
  once.
