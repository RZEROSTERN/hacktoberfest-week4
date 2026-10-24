# Samples

Two sets, for two different jobs.

## `synthetic/` — committed, drives CI and the spike's score

Generated screenshots with known labels, covering all ten categories, plus the
duplicate cases the real set has none of (an exact copy, a resized copy) and
images that imitate sensitive content without containing any. Built in step 3.

The model spike's accuracy gates are measured against this set, because it is
balanced. A set that is two-thirds `other` makes "85% correct" a number a
do-nothing model could almost reach.

## The real captures — local only, never committed

The maintainer's own screenshots, with `expected-labels.json` beside them. They
are excluded by `.gitignore` and stay on the development machine.

**Why they are not here:** they contain personal data — among them a
payment-processor console showing a third party's customer email next to card
BIN and last-four fields. Slothshot exists so that screenshots like these never
leave the machine they were taken on; publishing them to make a test fixture
would contradict the product.

They are still the better test of whether the thing works on real input, so the
spike reports its numbers on them as a spot check alongside the gated score on
`synthetic/`.

### `expected-labels.json`

One entry per file, hand-labelled by reading each image once. Descriptions are
neutral summaries: no extracted text, email address, URL or figure from any
image is reproduced, following the same rule the api follows at run time.

Fields: `kind` (screenshot, photo, video), `category`, `sensitive` (strictly the
specification's list: passwords, card numbers, IDs, bank details, verification
codes), `pii` (personal data that is not on that list), `expiry`
(`none`/`past`/`future`/`ambiguous`), `dup_group` and a `note`.

Every `dup_group` in the real set is a **negative** case: files that share a
visual template but are different content and must not be merged. Two
metric cards taken five seconds apart, and two show pages from the same
streaming app, are exactly the traps a careless hamming threshold falls into.
