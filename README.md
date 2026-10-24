# Slothshot

Sorts the screenshots piling up on your computer while you are not using it.
Entirely offline, on Windows, macOS and Linux.

Screenshots hold private chats, bank details and passwords, so Slothshot never
uploads anything. A local open-weight vision model, run through a bundled
Ollama, reads each screenshot and suggests a name, a category and a one-line
description. Files are renamed and moved; nothing is ever deleted, and every
change can be undone.

> Early development. The full README, with screenshots, install instructions
> per platform and real benchmark numbers, arrives in step 10 of the build.

## Layout

| Path | What it is |
| --- | --- |
| `api/` | FastAPI service: scanning, hashing, model analysis, the index and the journal |
| `web/` | Nuxt SPA, served by the desktop shell |
| `desktop/` | Electron shell: bundles Ollama and the api, runs the scheduler, lives in the tray |
| `samples/` | Test screenshots and their expected labels (the real set is not in version control) |
| `docs/` | `DECISIONS.md`, `BENCHMARKS.md` |

## Commands

```sh
# api
cd api && uv sync && uv run ruff check . && uv run mypy . && uv run pytest -q
cd api && uv run python -m app                 # needs the SLOTHSHOT_* variables; see .env.example

# web
cd web && npm install && npm run lint && npm run typecheck && npm test
cd web && npm run dev                          # http://localhost:3000

# desktop
cd desktop && npm install && npm run lint && npm run typecheck && npm test
cd desktop && npm start
```

## Branching

`master` is production and `develop` is integration; neither takes a direct
commit. Each build step is one `feature/<name>` branch off the latest
`develop`, one pull request based on `develop`, merged before the next step
starts. There are no stacked pull requests, and there is no branch named
`main`.

## License

MIT. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
