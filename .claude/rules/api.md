---
paths:
  - "api/**"
---

# API rules

- Configuration only through pydantic-settings and `SLOTHSHOT_*` environment variables. Bind to
  127.0.0.1. Nothing may assume a fixed port, working directory, repo-relative path, model tag or
  the default Ollama URL: the api also runs as a packaged binary.
- Build every path with `pathlib`, never string concatenation, and open the database through
  `URL.create`, never an f-string URL: Windows paths have backslashes and user names can hold
  spaces, `#` or `%`.
- Runs on macOS, Windows and Linux: no `os.kill`, `killpg`, `getpgid` or `fork`; use `psutil`.
  Start programs with no console window on Windows.
- **Every file operation goes through the journal.** Write the `Change` row first, perform the
  operation, then mark it applied. Never move, rename or create anything outside this path, and
  never delete a user's file for any reason.
- Every model output is validated with Pydantic. On invalid output retry **once**, then mark the
  screenshot `skipped` with a reason and carry on. A bad answer never stops a run.
- Prompts live in `api/prompts/`, versioned by filename, never inline. They must work with any
  vision model, not only Gemma. Store the `prompt_version` and `model_tag` on each result, so a
  prompt or model change can be told apart from a model being wrong.
- Ollama calls use `format` = JSON schema, `think: false` and temperature 0. Model management uses
  only Ollama's documented endpoints; cloud models are refused by name and by `remote_host`.
- **One image at a time.** No concurrent inference, no batching. Downscale before sending.
- Results are cached by content hash: a file already analysed is never sent to the model again,
  whatever its path or name.
- **Never log image contents, extracted text, file names or folder paths**, at any level, including
  tracebacks and access logs. Count things instead of printing them.
- The extracted text of a screenshot flagged `sensitive` is not stored unless
  `index_sensitive_text` is on. Check the flag before writing, not before reading.
- Every refusal is `ApiError(status, code)`, never a bare `HTTPException`: the code and its English
  text live in `ERROR_MESSAGES` (`errors.py`), and values for the message go in as keyword
  arguments.
- Unit tests mock the model. Tests that need a real Ollama with a vision model are marked
  `integration` and are excluded in CI. Tests never read the maintainer's real screenshots: they
  generate their own images.
