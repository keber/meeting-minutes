# meeting-minutes

> Turns a raw Teams meeting transcript into a reviewable minute, with a traceability
> proposal against Azure DevOps work items.
> Current version: **v0.3.0**

---

## What problem this solves

Writing a planning minute from a Teams transcript used to require replaying the
recording to annotate `[Task NNNNN]` markers by hand, because the meeting rarely
names a work item ID or its literal title out loud.

This package replaces that replay with a reviewable table: each detected topic is
matched against the sprint's work items, with a timestamp and the literal quote
that justifies the match. Verification becomes checking a handful of rows instead
of re-listening to the whole meeting.

---

## Install

```bash
npm install @keber/meeting-minutes
npx meeting-minutes init
```

`init` installs:

| Path | Ownership |
|---|---|
| `.github/skills/meeting-minutes/SKILL.md` | framework-owned - replaced on every upgrade |
| `.github/skills/meeting-minutes/templates/minuta.md` | framework-owned |
| `.claude/commands/meeting-minutes.md` | framework-owned (thin wrapper over the skill) |
| `qa/00-standards/minutes/domain.json` | **user-owned - seeded once, never overwritten** |

Run `npx meeting-minutes upgrade` after a version bump. It refreshes the
framework-owned files, reports any local edit it replaced, and never touches the
domain overlay.

---

## The two dictionary layers

Transcript cleanup is split by who owns the vocabulary:

- **Engine layer** (`data/engine-artifacts.json`, shipped here): artifacts of the
  Teams ASR itself in Spanish - `yeah` for `ya`, `to town` for `chao`. Universal
  across projects.
- **Domain layer** (`qa/00-standards/minutes/domain.json`, per project): the
  business vocabulary the ASR destroys - `buging` for `booking`, `Cuba` for `QA`,
  `stalking` for `stacking`.

The domain layer carries the value. On the Sprint 10 corpus the engine layer only
removed filler, while the domain layer fixed four terms that change meaning - one
of them turning *"not published in Cuba"* into *"not published in QA"*.

It also carries the leverage: corrupted domain terms are exactly the keywords the
Azure DevOps matching runs on, so a missing overlay degrades traceability.

See `data/domain.example.json` for a filled reference.

### Confidence levels

Every rule declares `alta`, `media` or `baja`, following the contract in
`rag-v1/index.md`.

| Level | Behaviour |
|---|---|
| `alta` | Applied by `--fix` |
| `media` | Lint only - reported with timestamp and context for confirmation |
| `baja` | Lint only - speculative or semantically lossy |

A v1 dictionary with no declared confidence degrades to `media`, so an old
dictionary never starts rewriting transcripts just because the package was
updated.

**Validation**: against the hand-corrected Sprint 10 transcript, the automated
output differs on 3 lines out of 19 changes - and those 3 are exactly the rules
classified `baja`. The deterministic corrections reproduce in full; the
speculative ones wait for a human.

---

## Usage

```bash
# Clean + report, writing <input>.fixed.txt (the original is never modified)
python -m tgd "Transcripción Planning Sprint 11.txt" \
  --domain qa/00-standards/minutes/domain.json \
  --fix

# Review what --fix deliberately held back
python -m tgd "Transcripción Planning Sprint 11.txt" \
  --domain qa/00-standards/minutes/domain.json \
  --lint

# Detected speakers and their resolved display names
python -m tgd "Transcripción Planning Sprint 11.txt" \
  --domain qa/00-standards/minutes/domain.json \
  --speakers

# Segment into topic blocks, for the minute and for the ADO matching
python -m tgd "Transcripción Planning Sprint 11.txt" \
  --domain qa/00-standards/minutes/domain.json \
  --dump --dump-format json
```

Then run the skill (`/meeting-minutes` in Claude Code) to produce the minute.

### Segmentation

Teams emits one event per speaking turn, so a 26-minute meeting leaves ~700 of
them, most one word long (`"ya."`, `"Sí."`). `--dump` merges consecutive turns by
the same speaker: on the Sprint 11 corpus, 685 events become 188 blocks.

The JSON form keeps `lineStart`/`lineEnd` alongside each block, so a quote used to
justify a work-item match can always be traced back to the raw transcript.

### Gap detection

Beyond cleanup, the tool flags suspicious silences - spans where the recording
lost content. Any topic near one may be incomplete, so those spans are carried
into the minute's `TODO` line rather than passing unnoticed.

---

## Requirements

- Node >= 20 (install and upgrade)
- Python 3 (transcript processing) - **standard library only**
- `wordfreq` is optional, and only sharpens `--lint-suspect`
- `@keber/ado-qa` is an optional peer dependency; without it the minute is still
  produced and traceability is marked `TODO`

---

## Tests

```bash
node --test tests/*.test.js          # ownership model
python -m unittest discover -s tests # dictionary layers and corrections
```
