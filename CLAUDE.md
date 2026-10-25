# Slothshot

Local-first desktop app that sorts the screenshots piling up on a computer while nobody is
using it. An open-weight vision model (via a bundled Ollama) reads each screenshot and
suggests a name, category and description; everything runs on the user's own machine.

- `api/` FastAPI (Python 3.12, uv, SQLModel/SQLite), `prompts/` for versioned prompts
- `web/` Nuxt 4 SPA (`ssr: false`), `desktop/` Electron shell bundling Ollama and the api
- `docs/` DECISIONS.md and BENCHMARKS.md; `samples/` synthetic fixtures (committed) plus the
  maintainer's real captures (local only, never committed)

## Commands
- api (`cd api`): `uv sync`; `uv run ruff check .`, `ruff format .`, `mypy .`, `pytest -q`;
  run with `uv run python -m app` and the `SLOTHSHOT_*` vars (`.env.example`)
- web / desktop (`cd web`, `cd desktop`): `npm install`, `npm run lint`, `npm run typecheck`,
  `npm test`. Also `npm run dev` (web, port 3000), `npm run generate` (the SPA the shell
  loads), `npm run build` and `npm start` (desktop)
- Installer for this OS: `npm run dist` (same steps as CI; `-- --from <step>` resumes,
  `--list` shows them). Steps in `scripts/steps.mjs`, pinned versions in `scripts/versions.json`
- CI (`.github/workflows/`): `checks.yml` gates every PR; `build.yml` builds installers
  (release PRs into master, manual, or a develop PR labelled `ci-build`); `release.yml`
  makes a DRAFT release on a `v*` tag

## Git: GitFlow, no stacked PRs
- `master` is production. `develop` is integration. Never commit to either directly.
- One `feature/<name>` per build step, created from the latest `develop`.
  PR base is always `develop` (`release/*` and `hotfix/*` target `master`).
- Never branch from another feature branch. Never open a PR against anything else.
- Sequence: `git checkout develop && git pull`, branch, small commits, checks pass, push,
  `gh pr create --base develop`, `gh pr merge --merge --delete-branch`, then the next step.
- PR body: what changed, why, how tested, whether DECISIONS.md was updated.

## Workflow
- Lint + typecheck + tests must pass before each commit. Conventional Commits.
- Log every technical decision (and why) in `docs/DECISIONS.md` when made or changed.
- Check the official docs for Ollama, Nuxt, Electron, electron-builder, PyInstaller and
  GitHub Actions instead of guessing flags or APIs. If something isn't documented, say so.
- Ask before installing anything globally or touching files outside the repo.
- Never run the organizer against real screenshot folders: copy `samples/` to a temp folder.

## Non-negotiables
- Never use a branch named "main". Production is `master`.
- No closed-model APIs or cloud inference. The only network access is model downloads the
  user approved. No analytics, telemetry, or logging of image contents or extracted text.
- **Never delete a user's file.** Duplicates and expired items move to Review; nothing else.
- Every file change is journaled before it happens and is undoable (file, run, everything).
- The model in use always comes from local settings, never a hardcoded tag.
- Resource budget: whole app ≤ 4 GB peak on a 16 GB machine, Ollama + model ≤ 3 GB. One image
  at a time, downscaled before inference, cached by content hash, model unloaded after a run.
- Sensitive screenshots are sorted, but their text is not indexed unless the user allows it.

## Gotchas
- macOS screenshot filenames contain **U+202F** (narrow no-break space) before `a.m.`/`p.m.`.
  Shell globs and the renamer must round-trip it; it is not a normal space.
- `nuxt generate` leaves `web/dist` as an **absolute-path symlink** to `.output/public`. A
  `dist/` pattern does not match a symlink, so `.gitignore` uses `dist` without the slash.
- In development Ollama runs natively on macOS (Apple GPU), not in Docker. The packaged app
  uses only its bundled Ollama, never a system one.
- Ollama pull progress is reported per layer: sum bytes across layers, never move the bar back.
- The perceptual hash is taken **before** downscaling, so retuning `SLOTHSHOT_MAX_IMAGE_PX`
  cannot invalidate hashes already stored.
- Screenshots are keyed by SHA-256 of their bytes, not by path, so a file the user moves is
  still recognised and never analysed twice.
- Hard-killing the api leaves Ollama's `llama-server` running: stop the process tree.
- Machine specs and local model tags live in `CLAUDE.local.md` (gitignored).
