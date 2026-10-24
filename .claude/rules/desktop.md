---
paths:
  - "desktop/**"
---

# Desktop rules

- Window security is not negotiable: `contextIsolation: true`, `sandbox: true`,
  `nodeIntegration: false`, `webviewTag: false`. The preload exposes exactly one value, the api
  base, and nothing else is added to it without a reason written down in DECISIONS.md.
- Navigation, new windows and permissions are all allow-listed. `will-navigate` refuses anything
  that is not the app's own origin or the local api; `setWindowOpenHandler` always returns `deny`
  and opens only the allow-listed external host in the user's browser; the permission handler
  denies everything.
- The `app://` handler resolves every request under the web root and refuses anything that escapes
  it. Unknown paths fall back to `index.html` so client-side routing survives a reload.
- **Only the bundled Ollama is ever used.** Never fall back to a system-wide Ollama, never use a
  port it might already hold. Both the api and Ollama bind to 127.0.0.1 on ports picked at start.
- The engines get a scrubbed environment (`env.ts`): a user's own `OLLAMA_*` or `SLOTHSHOT_*`
  settings must not leak in. Ollama is held to `OLLAMA_MAX_LOADED_MODELS=1`,
  `OLLAMA_NUM_PARALLEL=1`, a short `OLLAMA_KEEP_ALIVE`, and `OLLAMA_NO_CLOUD=1`.
- The api and Ollama run at below-normal priority (`priority.ts`). Never raise priority; a failure
  to lower it is logged as a count and ignored, not treated as fatal.
- A run only starts when the machine is idle or inside the user's window, pauses when the user
  comes back, when the machine goes on battery, or when the window closes, and resumes later.
  Use Electron's `powerMonitor` and `powerSaveBlocker` APIs; check the docs per platform rather
  than assuming an event fires everywhere.
- Quitting stops the whole process tree, not just the direct children: process groups on macOS and
  Linux, `taskkill /T /F` on Windows, plus the folder sweep for helpers Windows orphaned. A pid is
  checked against the program recorded for it before anything is killed, so a recycled pid is never
  someone else's process.
- Never write outside the app's own `userData` directory and the folders the user chose to watch.
