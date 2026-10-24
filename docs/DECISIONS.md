# Decisions

Every technical decision and why it was taken. Newest step last.

---

## Step 0 — Repository

### GitFlow with `master`, and no branch named `main`

`master` is production, `develop` is integration, every build step is one
`feature/*` branch with one pull request based on `develop`. No stacked
branches.

**Why:** the history has to read as a sequence of reviewable steps, and the
release workflow keys off `release/*` → `master`. GitHub creates empty
repositories expecting `main`; pushing `master` first makes it the default
branch, so `main` is never created at all.

The bootstrap commit is on `master` by necessity — a repository cannot have a
`develop` until something exists to branch from. Every change after it goes
through a pull request.

---

## Step 1 — Scaffold

### Reuse PostCall rather than start over

`api/`, `web/` and `desktop/` are adapted from the previous project rather than
written fresh: the Settings/env contract, the SQLite engine with WAL, the
`ApiError` code/params shape, the env allow-list, the navigation and permission
allow-lists, the sandboxed preload, and process-tree cleanup.

**Why:** time is the binding constraint. These pieces were already debugged on
three platforms. Code is copied, not depended on, so Slothshot stays a
standalone repository.

Dropped: transcription, proposal drafting, PDF export, the audio decoder,
`whisper-cli` and the bundled FFmpeg, with their layout and installer entries.

### Real screenshots stay out of version control

`samples/*` is ignored with negations for `samples/synthetic/` and
`samples/README.md`, rather than ignoring `samples/`.

**Why:** git cannot re-include a file underneath an excluded directory, so a
plain `samples/` would have made a committed fixture set impossible.

The maintainer's own captures hold personal data — one is a payment-processor
console showing a third party's customer email beside card BIN and last-four
fields. An app whose entire premise is that screenshots never leave the machine
cannot ship those in a public repository. The labelled real set stays local and
drives the spike; a generated synthetic set is committed and drives CI.

### `sensitive` and `pii` are separate fields

The expected-labels file records the specification's `sensitive` list
(passwords, card numbers, IDs, bank details, verification codes) apart from a
broader `pii` flag (names, emails, handles, locations).

**Why:** in the real sample set 2 of 24 images are sensitive but 8 carry
personal data. Collapsing the two would make the sensitive-flag metric measure
something other than what the model is asked for, and the question of whether an
email address should count can then be settled later without relabelling
anything.

### Difference hashing on Pillow alone, not `imagehash`

Near-duplicate detection uses a 64-bit dHash implemented in `api/app/images.py`.

**Why:** `imagehash` would pull numpy and scipy into the PyInstaller bundle for
one function, against a 1.5 GB installer ceiling in step 9. dHash is about ten
lines, needs no dependency beyond Pillow, and the tests show it survives a 2×
resize (hamming ≤ 6) while separating different images (> 6).

### The perceptual hash is taken before downscaling

`load_for_analysis` hashes the image at its original size, then downscales for
inference.

**Why:** otherwise retuning `max_image_px` during the spike would silently
invalidate every hash already stored, and duplicate detection would quietly
change meaning between runs. A test pins this.

### Screenshots are identified by content, not by path

The unique key is the SHA-256 of the file's bytes; the path is data that
changes.

**Why:** the app renames and moves files, and so does the user. Keying on
content means a file moved outside the app is still recognised and never
analysed twice, which is also what makes the cache honest.

### The journal is written before the operation, not after

A `Change` row is inserted before each file operation and marked `applied`
afterwards.

**Why:** undo has to be able to tell "this move never happened" from "this move
happened and was not recorded". Writing afterwards loses that distinction
exactly when it matters, after a crash mid-run. Undo can verify an unapplied row
against the filesystem instead of guessing.

### Background priority is below-normal, not idle

`desktop/src/priority.ts` uses `os.setPriority`, the one call that works on all
three platforms, and asks for `PRIORITY_BELOW_NORMAL`.

**Why:** Node maps the bottom of its range to Windows' `IDLE_PRIORITY_CLASS`,
where a run on a busy machine can be starved indefinitely rather than merely
yielding. Lowering priority needs no privileges; a failure leaves the app at
normal priority, which is a slower neighbour, not a broken one.

### Ollama's limits come from its own help output

`OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1` and
`OLLAMA_KEEP_ALIVE=30s`, read from `ollama serve --help` on 0.35.1.

**Why:** the rule against inventing flags. All three names were confirmed
against the installed binary rather than recalled. The short keep-alive is what
lets the model carry between screenshots in one run without holding memory
afterwards.

### English only: no vue-i18n

PostCall's translation layer and its seven locale files were not carried over.

**Why:** nothing in the specification asks for more than English, and the
layer's cost lands in exactly the hours the spike and the pipeline need.

### TypeScript `node16` resolution

`desktop/tsconfig.json` uses `module`/`moduleResolution: node16`, and the build
config sets `rootDir` explicitly.

**Why:** TypeScript 6 deprecates the old `node10` resolution and errors on it.
Without an explicit `rootDir` the output lands at `dist/src/main.js`, which does
not match `package.json`'s `main`.

### CI is split: fast checks now, installers later

`checks.yml` runs lint, typecheck and tests for all three parts on every pull
request. The installer matrix is deliberately not in this step.

**Why:** the checks gate can run today and catches the mistakes that actually
happen between steps. The installer workflow needs the `scripts/*.mjs` build
chain, which only becomes real in step 9 where it is exercised and where the
installer-size limit is checked — writing it now would mean shipping CI that has
never run. Pinned action SHAs and `permissions: contents: read` apply from the
start.

Integration tests are excluded in CI (`-m "not integration"`): they need a real
Ollama with a vision model, which no runner has and which would amount to cloud
inference.

---

## Step 2 — Project memory

### CLAUDE.md stays short; the detail lives in path-scoped rules

`CLAUDE.md` is ~60 lines of what cannot be read off the code: layout, commands, the GitFlow
sequence, the non-negotiables and the gotchas. Everything specific to one part goes in
`.claude/rules/{api,web,desktop,ci}.md`, each scoped with a `paths:` header.

**Why:** a long root file is read on every task whether or not it is relevant, and the parts
that matter get diluted. Scoped rules load when the files they govern are being worked on.
The rule is to record only what the code cannot say for itself — "never delete a user's file"
is not inferable from a codebase that currently has no delete call in it, so it is written
down.

### Two gotchas earned a place by costing time

macOS writes **U+202F**, a narrow no-break space, before `a.m.`/`p.m.` in screenshot
filenames. It is not a space, shell globs treat it as part of the name, and the renamer has to
round-trip it rather than normalise it.

`nuxt generate` leaves `web/dist` as an absolute-path symlink to `.output/public`. A `dist/`
pattern in `.gitignore` matches directories only, and git sees a symlink, so the link was
committed once before being caught. The pattern is now `dist`, without the slash.

### CLAUDE.local.md is not generated

It already exists, is gitignored, and already holds the machine specs. It is the maintainer's
own file and is left alone; the local model tags are appended once the spike has chosen them.

---

## Step 3 — Model spike

### No model met all four targets, so the app ships a list instead of a pick

Measured on the development Mac over 28 balanced fixtures: exactly one configuration fits the
memory budget (`qwen3-vl:2b-instruct` at 768px, 2.86 GB) and exactly one model meets the
accuracy gate (`gemma4:e4b`, 89%). None does both.

**Decision:** `qwen3-vl:2b-instruct` is the default and `gemma4:e4b` is offered in the wizard
with its memory cost stated.

**Why:** bending the memory budget would break the claim the product is built on, and bending
the accuracy target silently would hide a real limitation. A recommended list is what the
first-launch wizard was already specified to show — models with size, RAM needed and license —
so the honest answer fits the design that already existed. The default keeps the resource
promise; the accuracy is available to anyone who chooses to pay for it.

### `gemma4:e2b` is excluded outright

It was worst on every axis and it missed a sensitive screenshot.

**Why:** "no sensitive screenshot missed" is a safety property, not a quality score. A model
that fails it is not a candidate at any image size, so it is absent from the catalog rather
than listed with a warning. A test asserts it is not offered.

### 768px, not 1024px

**Why:** both models scored identically at the two sizes while 768 cost less memory and was no
slower. Nothing was bought by sending larger images.

### The first measurement was wrong, and the fix is in the script

Peak memory read lower at 1024px than at 768px, which is impossible. With `keep_alive` at 30s
each model's first run overlapped the previous model unloading, so whichever ran first absorbed
the other's memory.

**Why it matters beyond this run:** the numbers are meant to be reproduced on the Mint and
Windows machines. `spike/benchmark.py` now sends the documented `keep_alive: 0` unload and polls
`/api/ps` until the engine is idle before each run, so the same mistake cannot be repeated by
whoever runs it next.

### The accuracy gate partly measured the labels

Four of the default model's seven misses are fixtures filed under `other` because the
ten-category list has no bucket for a password manager or a checkout form; the model answered
`document`. Both of `gemma4:e4b`'s "false alarms" are a receipt showing `VISA ending 0000`,
where flagging it is arguably correct and the label is the weaker claim.

**Why this is recorded rather than quietly corrected:** re-labelling after seeing the results
is how a benchmark becomes a story about itself. The labels stand as they were written, the
caveat is published next to the number, and any re-labelling happens as its own change with its
own reasoning.

---

## Step 4 — Indexing pipeline

### The duplicate threshold was measured, not chosen

`DUPLICATE_DISTANCE = 4` over a 64-bit difference hash.

**Why that number:** genuine duplicates, including a half-size resave, measure 0. The closest
pair that is *not* a duplicate measures 7 across the fixtures and 8 across the real captures,
where the hardest case is two dashboard cards photographed five seconds apart with the same
layout and different numbers. 4 is the midpoint of an empty gap, so the threshold can drift in
either direction without changing any verdict. The measurements are in docs/BENCHMARKS.md.

### Duplicates are resolved oldest-first

Pending screenshots are analysed in capture-time order, so the earliest copy stays the original
and a later copy is the one sent to Review.

**Why:** the first implementation processed in path order, which made "which one is the
original" depend on filenames. A test caught it. The screenshot the user actually took should
be the one that keeps its place.

### Three gates before the model, in increasing cost

A file is dropped at the cheapest gate that can decide it: the folder walk skips Slothshot's own
output and anything that is not a readable image; the content hash settles exact duplicates
without opening the image; the perceptual hash settles near duplicates without the model.

**Why:** the model is the only expensive step, at about 4 seconds an image. In the end-to-end
run, 28 files on disk became 27 rows and 26 model calls.

### Scanning never re-analyses a file the user moved

The unique key is the content hash, and a rescan updates `current_path` in place.

**Why:** people rename and move screenshots, and Slothshot itself moves them. Keying on path
would re-analyse the same picture every time it moved, which is both slow and wrong. A test
renames a file between scans and asserts no new work and no second row, with `original_path`
still pointing where undo needs it.

### The api never logs what it sees

Progress is reported as counters on the `Run` row, not as log lines naming files.

**Why:** the product promise is that screenshot contents never leave the machine, and a log
file is a place they could leak to. Counting is enough to drive a progress bar.
