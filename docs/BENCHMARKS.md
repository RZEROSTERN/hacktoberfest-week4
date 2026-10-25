# Benchmarks

## Model spike — 24 October 2026

**Verdict: no model meets all four targets.** The spike stopped and put the options to the
maintainer, who chose to ship a recommended list rather than bend one of the targets:

- **`qwen3-vl:2b-instruct` at 768px is the default.** It is the only configuration that fits
  the 3 GB memory budget (2.86 GB), it missed no sensitive screenshot, and it downloads in
  1.9 GB. It ships at 75% category accuracy, below the 85% target.
- **`gemma4:e4b` is offered in the wizard as the more accurate option**, labelled with the
  memory it needs (~4.8 GB). Users with headroom can pick it for 89% accuracy.
- **`gemma4:e2b` is not offered at all.** See below.

This is what the first-launch wizard was already designed to do: present recommended models
with their size, the RAM they need and their license. The resource promise stays true for
anyone who takes the default, and the accuracy is available to anyone who chooses to pay for
it in memory.

### Setup

| | |
| --- | --- |
| Machine | MacBook Pro M2 Pro, 16 GB, macOS 27 (`arm64`) |
| Engine | Ollama 0.35.1, installed natively (not Docker) |
| Images | `samples/synthetic/` — 28 generated screenshots, all ten categories |
| Prompt | `api/prompts/analyze.v1.txt` |
| Call | `/api/chat`, `format` = the `Analysis` JSON schema, `think: false`, `temperature: 0` |
| Script | `spike/benchmark.py` — re-runnable on any machine with Ollama |

Targets, from the build order: **≤ 10 s** per screenshot, **≤ 3 GB** peak for Ollama + model,
**≥ 85%** category accuracy, and **no sensitive screenshot missed**.

### Results

| Model | px | s/shot (median) | s/shot (mean) | Peak RAM | Category | Sensitive missed | False alarms | Meets targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `qwen3-vl:2b-instruct` | 768 | 3.63 | 3.80 | **2.86 GB** | 75% (21/28) | **0** | 0 | no — accuracy |
| `qwen3-vl:2b-instruct` | 1024 | 3.55 | 3.67 | 3.35 GB | 75% (21/28) | **0** | 0 | no — memory, accuracy |
| `gemma4:e2b` | 768 | 3.03 | 3.47 | 4.50 GB | 71% (20/28) | 1 | 0 | no — memory, accuracy, **safety** |
| `gemma4:e2b` | 1024 | 3.42 | 3.55 | 4.57 GB | 68% (19/28) | 1 | 0 | no — memory, accuracy, **safety** |
| `gemma4:e4b` | 768 | 5.24 | 5.98 | 4.78 GB | **89%** (25/28) | **0** | 2 | no — memory |
| `gemma4:e4b` | 1024 | 5.10 | 5.65 | 5.67 GB | **89%** (25/28) | **0** | 2 | no — memory |

No run produced an unparseable answer: **0 skipped, 0 retries** across all 168 inferences. The
schema-constrained call plus `think: false` held every model to valid JSON.

### Download size and license

| Model | Download | Parameters | Quantisation | License |
| --- | --- | --- | --- | --- |
| `qwen3-vl:2b-instruct` | 1.9 GB | 2B | Q4_K_M | Apache 2.0 |
| `gemma4:e2b` | 4.6 GB | ~5B effective | Q4_K_M | Gemma Terms of Use |
| `gemma4:e4b` | 6.6 GB | 7.5B | Q4_K_M | Apache 2.0 (per `ollama show`) |

### Filename quality (spot check)

Slugs were good from every model and are not the differentiator. Samples from
`qwen3-vl:2b-instruct`: `northgate-market-grocery-receipt`, `casa-miranda-receipt`,
`payment-details-checkout-form`. None needed the retry path, and none required the slug
validator to salvage an extension or stray punctuation.

### A measurement error worth recording

The first run reported `gemma4:e4b` peaking at 4.34 GB at 768px but 3.11 GB at 1024px. Memory
cannot fall when the image grows. With `keep_alive` at 30 s, each model's first run overlapped
the previous model still unloading, so whichever size ran first absorbed the other model's
memory. The same artefact made 1024px look twice as fast as 768px.

`spike/benchmark.py` now sends the documented `keep_alive: 0` unload and polls `/api/ps` until
the engine is idle before every run. The table above is from the isolated measurement, where
memory rises with image size for all three models, as it should.

### What the numbers mean

**Speed is not a constraint.** Every model ran at 3–6 s against a 10 s budget. There is roughly
6 s of headroom per screenshot to spend on a longer prompt or a second pass.

**The trade-off is memory against accuracy.** Exactly one configuration fits the memory budget
(`qwen3-vl:2b-instruct` at 768px, 2.86 GB) and exactly one model meets the accuracy gate
(`gemma4:e4b`, 89%). No configuration does both.

**`gemma4:e2b` is out.** It is the worst on every axis and it is the only model that **missed a
sensitive screenshot** (the bank balance). That is the one gate that is a safety property, not a
quality metric, so a model that fails it is not a candidate at any size.

**Part of the accuracy gap is the labels, not the models.** Of `qwen3-vl`'s seven category
misses, four are on the four invented "sensitive" fixtures, which were filed under `other`
because the ten-category list has no bucket for a password manager, a checkout form or a
banking screen. The model answered `document` for the checkout form and the bank balance —
defensible readings that the scoring counts as wrong. Two more are an order confirmation and an
email thread read as `document`, also defensible.

The same caveat runs the other way for `gemma4:e4b`: both of its "false alarms" are the grocery
receipt, which it flagged sensitive because the receipt shows `VISA ending 0000`. Flagging a
receipt that displays part of a card number is arguably the correct behaviour, and the label
saying otherwise is the weaker claim.

**What is unambiguous:** `qwen3-vl:2b-instruct` flagged all four sensitive screenshots correctly
at both sizes, and `gemma4:e4b` did too. The safety-critical signal is reliable on both.
`gemma4:e4b`'s remaining genuine weakness is memes, which it calls `other` at both sizes.

### Re-running this elsewhere

```sh
cd spike
uv run --project ../api python benchmark.py                      # all models, 768 and 1024
uv run --project ../api python benchmark.py --models qwen3-vl:2b-instruct --sizes 768
uv run --project ../api python benchmark.py --set real           # local only, not committed
```

Results are written to `spike/results/<host>-<set>-<timestamp>.json` with every per-image row,
so the Mint and Windows numbers can be compared against this table directly.

> Linux Mint (Intel, no dedicated GPU) and Windows 11 (Ryzen 9) figures: **not yet measured.**

### Why 768px is the shipped default

Both candidate models scored **identically at 768 and 1024** (75% and 89% respectively), while
768 used less memory in every case and was no slower. There is no accuracy to be bought by
sending bigger images to these models, so `SLOTHSHOT_MAX_IMAGE_PX` defaults to 768.

### Still open

The 85% accuracy target is not met by the default. Two cheap avenues were identified but not
taken, because the spike had already run long:

1. **The scoring labels need work.** Four of the default model's seven misses are on fixtures
   filed under `other` for want of a better bucket, and the model's `document` answers are
   defensible. Re-labelling those honestly would move the number without touching the model.
2. **There are ~6 seconds of unused headroom per screenshot.** The prompt gives no tie-breaking
   guidance between `document` and the more specific categories, which is exactly where the
   misses cluster (`other -> document` 6 times, `receipt -> document` 3 times).

---

## Indexing pipeline — 24 October 2026

A full pass over the 28 fixtures with `qwen3-vl:2b-instruct` at 768px, on the development Mac,
against a temporary copy of the folder (never a real screenshot folder).

| | |
| --- | --- |
| Files on disk | 28 |
| Rows created by the scan | **27** — the byte-identical copy collapsed at the content hash |
| Sent to the model | **26** — the half-size copy was caught by the perceptual hash |
| Duplicates found | 1 near, 1 exact |
| Skipped | 0 |
| Scan (walk + SHA-256 of 28 files) | 0.02 s |
| Analysis | 101.8 s total, **3.92 s per image** |
| Files changed on disk | **0** |

The model is asked exactly once per unique image. Both duplicate mechanisms fire where they
should: identical bytes never reach the image loader at all, and a resave at a different size
is settled by the difference hash without the model.

All four images imitating sensitive content were flagged, and all four stored `null` for their
extracted text, which is the privacy rule holding in a real run rather than only in a unit test.

### Duplicate threshold

`DUPLICATE_DISTANCE = 4`, calibrated rather than guessed:

| Measurement | Distance |
| --- | --- |
| Exact copy, and a half-size resave | **0** |
| Closest non-duplicate pair, fixtures | 7 |
| Closest non-duplicate pair, real captures (two dashboard cards 5 s apart, same layout) | 8 |

4 sits in the gap with margin on both sides.

---

## Organize and undo — 24 October 2026

A full sort and a full undo over the 28 fixtures, on a temporary copy of the folder, with
SHA-256 taken of every file before and after.

| | |
| --- | --- |
| Files before | 28, flat in one folder |
| Moved | **28** |
| Filed into category folders | 25 |
| Sent to Review | **3** — one exact duplicate, one resized duplicate, one expired boarding pass |
| Files after organizing | 28 |
| Files lost | **0** |
| Files restored by undo | **28** |
| Byte-for-byte identical to the start | **yes** |
| Empty Slothshot folders left behind | none |
| Journal rows | 40, all marked undone |
| Analysis kept after undo | 28 rows, so a re-run costs no model calls |

### Two defects this run caught

**One file was left unmanaged.** The first run moved 27 of 28 files. `content_hash` was a
unique column, so a second file with identical bytes never got its own row: it was untracked,
and therefore never sent to Review. A row now identifies a *file* and the hash identifies its
*content*, which is the distinction that was missing. The second copy still costs no model call
— the perceptual hash settles it at distance 0.

**Date prefixes were a day ahead.** Capture times are stored in UTC and the filename was built
from the UTC date, so an evening screenshot west of Greenwich was filed under tomorrow. The
prefix is now the user's own local date. A test pins it with a Mexico City evening whose UTC
date has already rolled over.

---

## Morning card and search — 24 October 2026

A full sort of the 28 fixtures, then the card and a handful of searches.

| Card | |
| --- | --- |
| Sorted | 28 |
| Skipped | 0 |
| Duplicates waiting in Review | 2 |
| Expired waiting in Review | 1 |
| Space deleting those by hand would free | 62 KB |
| Indexed | 28 |

| Query | Hits | Matched on |
| --- | --- | --- |
| `receipt` | 3 | description |
| `password` | 1 | description |
| `booking` | 1 | description |
| `traceback` | 1 | **stored text** |
| `482913` | **0** | — |

That last row is the one that matters. `482913` is the verification code shown in the
sensitive SMS fixture, and the model read it correctly — it is simply not in the index to be
found. All four sensitive rows store `null` for their text.

The screenshot is still findable: searching `password` returns the vault screenshot by its
description. Being unable to find a sensitive screenshot *at all* would be its own failure.

---

## Resource budget — 25 October 2026

A full run of the 28 fixtures through the real api process, with `qwen3-vl:2b-instruct` at
768px, sampling resident memory every 250 ms. MacBook Pro M2 Pro, 16 GB.

| | Peak RSS | Budget |
| --- | --- | --- |
| api (FastAPI + Pillow) | 0.09 GB | — |
| **Ollama + model** | **2.71 GB** | **3.00 GB** ✓ |
| api + Ollama + model | 2.76 GB | — |
| Ollama once the run ended | **0.02 GB** | model released ✓ |

The run sorted 28 files in 139 s, 26 of them through the model and 2 settled as duplicates.

**The model is released, not merely scheduled for release.** Ollama drops from 2.71 GB to
0.02 GB as soon as the run finishes, rather than after the keep-alive expires.

**Electron is not in these numbers.** The shell is measured against the whole-app 4 GB budget
in step 9, on the packaged build, because an unpackaged Electron in development is not the
thing a user runs. On these figures the shell has roughly 1.2 GB of headroom before the
budget is at risk.

### The measurement was wrong the first time

The first run reported **0.03 GB** for Ollama, which is impossible for a 1.9 GB model. Ollama's
own process holds almost nothing: the model lives in a child process named **`llama-server`**,
and `"llama-server"` does not contain the substring `"ollama"`. The script matched only the
latter.

Direct inspection with a model loaded:

```
   8991  rss=  0.02 GB  name='ollama'
  72693  rss=  2.15 GB  name='llama-server'
```

`spike/benchmark.py` always matched both; the mistake was in the newer script. Any future
measurement that matches on process name has to match both, or it reports a number that looks
like a triumph and is a bug.
