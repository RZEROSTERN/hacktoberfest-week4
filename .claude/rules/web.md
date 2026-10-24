---
paths:
  - "web/**"
---

# Web rules

- SPA only (`ssr: false`). No server routes, no server middleware, no runtime that assumes Node:
  the desktop shell loads the generated files over the `app://` scheme.
- The API base comes from the desktop preload (`window.desktop.apiBase`) when packaged and from
  `runtimeConfig.public.apiBase` otherwise. Never hardcode a URL or a port, and never read it from
  anywhere else.
- All API calls go through a composable (`useApi` and the per-feature composables built on it).
  No `$fetch` to the api scattered through components.
- **Every action that moves, renames or hides a file shows what will happen before it happens and
  how to undo it afterwards.** The first sort is a preview the user approves; after that, each run
  reports what it did with an undo next to it. Nothing is phrased as deletion, because nothing is
  deleted.
- Screenshots marked sensitive are shown as sorted like any other, but their extracted text is not
  displayed or searchable unless the user has turned that on, and the UI says why when it is not.
- Refusals from the api carry a stable `code`. Show the message for the code; never parse English
  text to decide what happened.
- Pure helpers live in `app/utils/` and stay free of the Nuxt runtime so they can be unit-tested
  directly. Components and composables are tested through those helpers rather than by mounting
  the whole app.
- `nuxt prepare` must have run before eslint works; `npm install` does it via `postinstall`.
- No raw screenshot content in any analytics, error report or console log. There are none of those
  anyway, and it stays that way.
