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

---

## Step 5 — Organize and undo

### The safety guarantee is enforced by shape, not by care

`app/organize.py` contains exactly two filesystem operations: create a directory, and move a
file. There is no delete, no overwrite and no truncate anywhere in it. Destinations come from
`unique_path`, which counts up until it finds a free name.

**Why:** "never delete a user's file" is the kind of promise that erodes through a reasonable
looking special case. If the module has no way to express deleting, the promise cannot be
broken by accident. The single `rmdir` in the codebase lives in undo, applies only to a folder
Slothshot created, and only when it is already empty.

### The journal is written before the move, and undo is all-or-nothing

A `Change` row is committed before the file moves and marked applied afterwards. Undo checks
every change against the filesystem first and moves nothing unless all of them can be reversed.

**Why:** the error messages say "Nothing was changed", and a user rearranging thousands of
files has to be able to rely on that. A half-applied undo is worse than a refused one, because
the user no longer knows what state they are in. Tests assert that a blocked undo leaves both
the files and the journal untouched, so it stays undoable once the obstruction is cleared.

### A row is a file; the hash is its content

`content_hash` was originally unique, which quietly assumed no two files hold identical bytes.
They do, and the end-to-end run proved it: one of 28 files was left untracked and never reached
Review.

**Why the fix is not just dropping the constraint:** rescanning now matches by path first, then
follows a row whose file has moved, and only then creates a new row. That distinguishes the
three cases that were previously collapsed: the same file seen again, a file the user moved,
and a second copy living alongside the first. The copy still costs no model call, because the
perceptual hash settles it at distance 0.

### Expiry is decided conservatively, in code

The model returns `expiry_hint` in its own words. `app/expiry.py` turns that into a yes or no,
and only an unambiguous, fully specified date that is already past counts.

**Why:** a date without a year is not a date for this purpose. "delivery 2 dic" is exactly how
a boarding pass from last month becomes next year's. The asymmetry also matters: a stale
screenshot filed normally costs nothing, while one wrongly swept into Review costs the user a
search. The cautious default is "not expired".

### Filenames carry the user's date, not UTC

**Why:** capture times are stored in UTC, which is right for storage and wrong for a filename.
An evening screenshot in Mexico City was being filed under the following day. The prefix is now
the local date; a test pins it.

### CI caught a test that only passed where it was written

The first version of the local-date test built a Mexico City evening and asserted the
filename's date. It passed on the development Mac and failed on the runner, because
`astimezone()` with no argument uses *the machine's* zone: the same instant is the 24th at
UTC-6 and the 25th at UTC.

**The fix is in the signature.** `stem_for` now takes an optional `tz`, defaulting to the
machine's zone, which is the user's zone for a desktop app. The parameter exists so the
behaviour can be pinned without depending on where the test runs. The suite is now verified
under both `TZ=UTC` and `TZ=America/Mexico_City`, and a second test asserts the same instant
deliberately files under different days in different zones.

This is worth recording because the app is built on one machine and shipped to three
platforms in unknown timezones: a test that silently depends on the developer's locale is a
bug that ships.

### The date prefix also solves a Windows problem for free

A filename beginning with a digit can never collide with a Windows reserved device name (CON,
PRN, AUX, NUL, COM1), which would otherwise be reachable from a slug like "con".

---

## Step 6 — Morning card and search

### What is searchable is decided by what was stored

There is no "exclude sensitive" filter at query time. A sensitive screenshot has no
`extracted_text` row unless the user turned indexing on, so its contents cannot be matched
even by accident.

**Why not a filter:** a filter is a line of code someone can forget, reorder or route around
with a new query path. Absence is not. The end-to-end check searches for the exact code shown
in a sensitive fixture and gets nothing back, because there is nothing to match.

Descriptions remain searchable, deliberately. "A message with a one-time code" is how someone
finds the screenshot again, and is not the secret.

### LIKE, not FTS5

Matching is a case-insensitive `LIKE` per term, all terms required.

**Why:** SQLite's FTS5 ranks better but needs a second table kept in step with this one, and a
few thousand screenshots do not need it. The cost of being wrong is a slightly worse ordering,
not a wrong answer. `app/search.py` names the threshold where this should be revisited.

### The card reports Review from the index, not from the run

Counts come from what is sitting in Review now, not from what the most recent run put there.

**Why:** the card answers "what is waiting for me", and items from three nights ago are still
waiting. A per-run count would quietly drop them.

### The reclaimable figure is information, not an offer

The card says what deleting the Review items *by hand* would free.

**Why:** Slothshot never deletes anything, so a button there would be a promise the product
does not make. A test asserts the wording does not drift into offering it.

### One notification per run, and none for a quiet run

`RunAnnouncer` remembers the last run it announced, and `notificationFor` returns nothing when
a run sorted nothing.

**Why:** an app that works overnight becomes intolerable the moment it reports having had
nothing to do. A run that did nothing is still marked as seen, so a later poll does not
reconsider it. The notification text carries counts only, never a file name or a description.

---

## Step 7 — Scheduler and resource guard

### Conditions are polled, not subscribed to

The guard reads idleness and power state on a one-minute timer rather than listening for
Electron's `on-battery` and `on-ac` events.

**Why:** Electron documents those two events as **macOS and Windows only**. A Linux build that
waited for them would never notice the power state change, and the battery guard — one of the
two things that make this app a good neighbour — would silently do nothing on one of the three
platforms. `powerMonitor.onBatteryPower` and `getSystemIdleTime()` carry no platform
restriction, so reading them on a timer behaves the same everywhere.

### All the deciding is one pure function

`shouldRun(schedule, conditions)` takes a snapshot and returns a verdict. The loop in
`guard.ts` only reads the machine and calls the api.

**Why:** the rules are "overnight, while idle, while plugged in", and every one of those is
awkward to arrange on a real machine during a test. Separating the decision from the reading
means the overnight window that spans midnight, the idle threshold and the battery guard are
all tested directly, including the 23:00-to-07:00 wrap that is the most likely thing to get
wrong.

### Start-at-login is three different features

macOS and Windows go through `setLoginItemSettings`; Linux gets an XDG autostart `.desktop`
file written directly.

**Why:** Electron documents `setLoginItemSettings` for macOS and Windows only. The same docs
note that macOS login items want a signed and notarized app, and Slothshot is ad-hoc signed,
so the request can quietly not take effect there. `applyAutostart` therefore **reads the value
back** and returns what actually happened rather than what was asked for.

### A manual run outranks the schedule

"Sort now" clears a standing pause and starts a run whatever the guard would have decided.

**Why:** asking for something explicitly is a clear instruction, and an app that refused
because it was 3pm and the battery was at 80% would be obeying a rule rather than its user.
The guard still pauses that run if conditions turn against it, which is the behaviour the
resource budget actually cares about.

### A run pauses between images, never inside one

The pause flag is checked between screenshots, so the image in flight finishes and its result
is stored.

**Why:** stopping mid-file would leave a screenshot analysed but unrecorded, and the run would
redo it on resume. Pausing at a boundary means resuming is just "carry on with the queue", and
a test asserts the images analysed before the pause are not sent to the model a second time.

### The model is released the moment a run ends

`RunManager` unloads it in a `finally`, rather than waiting out the keep-alive.

**Why:** the model is roughly 2 GB resident. Holding that for another thirty seconds after the
work is done is the difference between a good neighbour and a bad one. The unload is
best-effort and its failure is ignored: the keep-alive will do it shortly anyway, and a run
that finished successfully must not be reported as failed over a cleanup call.

### Measuring Ollama means measuring `llama-server`

**Why this is written down:** the first memory measurement reported 0.03 GB for Ollama, which
is impossible for a 1.9 GB model. Ollama's own process holds almost nothing; the model lives
in a child process named `llama-server`, and `"llama-server"` does not contain the substring
`"ollama"`. Any future measurement that matches on the process name has to match both, or it
will report a number that looks like a triumph and is a bug.

---

## Step 9 — Cross-platform builds

### CI runs the repository's own scripts, and a test keeps them honest

`.github/workflows/build.yml` calls `node scripts/*.mjs`; `npm run dist` calls the same
scripts in the same order. `scripts/dist.test.mjs` parses the workflow and fails if the two
lists differ.

**Why:** the failure mode otherwise is a release built by steps nobody ever ran locally, or a
local build that passes while CI cannot. The same test file also enforces two rules from
`.claude/rules/ci.md` mechanically: every third-party action is pinned to a full commit SHA,
and no workflow targets a branch named `main`.

That second check caught its own author: the first version matched the bare word anywhere in
the file, and failed on the comment explaining the rule. It now matches branch references
(`branches: [...]`, `origin/main`, `refs/heads/main`) rather than prose.

### CUDA is left out so the installers fit

The Linux Ollama archive is 1.3 GB compressed and the Windows one 1.85 GiB unpacked, of which
the CUDA backends are about 1.3 GiB. `fetch-ollama.mjs` excludes `lib/ollama/cuda_*` and
`rocm*` and keeps Vulkan.

**Why Vulkan and not CUDA:** Ollama enables Vulkan by default when its backend is present, and
it runs on AMD, Intel and NVIDIA drivers, so one backend covers every machine this ships to.
Shipping CUDA would serve NVIDIA alone and put the installer past the 1.5 GB limit. The script
verifies its own exclusions and fails if a CUDA folder survived or if Vulkan is missing,
because a silent miss here is a 1.9 GB installer discovered at release time.

### The smoke test proves wiring, not inference

On each platform it checks that every bundled program starts, that the bundled Ollama serves
on loopback, that the PyInstaller api answers `/health`, that the api can reach that Ollama
across a process boundary, and that the model catalog survived bundling. It runs in a folder
whose name carries an accent, as a Windows user name may.

**Why it stops short of inference:** the smallest vision model is 1.9 GB. Pulling it onto
three runners every build would be slow, and it would mean running the product's own workload
on someone else's computer — the thing Slothshot exists to avoid. Inference is proven locally
instead, and those numbers are in BENCHMARKS.md. The decision was put to the maintainer rather
than taken quietly, because it trades CI coverage for principle and schedule.

### `GET /api/engine` exists because the smoke test needed it

Nothing in the api previously reported whether Ollama was reachable, so there was no way to
prove the two halves could talk after packaging.

**Why it is not throwaway:** the first-launch wizard needs exactly this — is the engine up,
what is installed, is the chosen model actually there, and what is recommended. It returns a
usable answer when the engine is down rather than failing, because "not running yet" is the
normal state on first launch.

### A bug the smoke test found immediately

It looked for the web app at `desktop/build/web`. Before packaging, the generated SPA is still
at `web/.output/public`; only electron-builder copies it into `resources/web`.

**Why this is worth recording:** the check was wrong for the pre-package case on every
platform, so it would have failed on all three runners at once, during the first full matrix
build, with the deadline close. Running the build locally before pushing it is what caught it.
