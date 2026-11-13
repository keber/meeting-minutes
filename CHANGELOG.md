# Changelog

All notable changes to `meeting-minutes` will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.3.0] - 2026-10-14

### Changed

- **The minute is now executive-extended: one file, two parts.** Part 1 (Acta)
  carries the conclusions - executive summary, a topics-and-traceability table,
  decisions, risks, next steps - and reads in two minutes. Part 2 (Desarrollo)
  carries the evidence: discussion per topic, field inventories, technical
  resolutions, and the literal quote with timestamp behind each estimate.

  The two parts are deliberately **not** two resolutions of the same content. If
  Part 1 summarised Part 2, nobody would read the second and everything would be
  duplicated. The split is by kind of content, not by level of detail.

  Measured on the Sprint 11 corpus against the hand-written minute: Part 1 alone
  is 608 words against the original's 864, while carrying the same conclusions
  plus the traceability table. The executive layer got denser, not longer.

  Rationale for keeping the detail rather than capping length: the extra content
  was classified and found to be governance facts (the scope of a destructive
  data deletion, confirmed on the record), field inventories, and technical
  resolutions - exactly the material `rag-v1` is built from, and the raw input
  for feeding it back in v2. Only conversational colour was filler.

- **`## Trazabilidad` folded into `## Temas y trazabilidad`** in Part 1: one
  table that doubles as the topic index and the work-item mapping.

### Added

- **Step 5 now fetches `System.Description`**, not just the title. A meeting names
  a topic loosely while the work item carries acceptance criteria that were never
  said aloud. Verified against the corpus: the hand-written minute's "validate
  format **and uniqueness**; block if **duplicated**" has zero occurrences in the
  transcript and comes from one work item's description; "compatible" and
  "traceability" likewise come from another's. Detail taken from a work item is
  labelled `**Del work item (ID):**` so it is never mistaken for what was discussed.

---

## [0.2.0] - 2026-10-14

### Added

- **Segmentation (`--dump`).** New `tgd/segment.py` merges consecutive turns by
  the same speaker into topic blocks. On the Sprint 11 corpus this turns 685
  events into 188 blocks. `--dump-format json` keeps `lineStart`/`lineEnd` per
  block so a quote can be traced back to the raw transcript, and resolves speaker
  display names through the domain overlay. This is what Step 4 of the skill
  needs; until now it had no command behind it.
- **CLI guards** (`tests/test_cli.py`). No test imported `cli.py`, so a syntax
  error there passed the whole suite. These import the module, build the parser,
  and pin the defaults - `--fix` at `alta`, `--dump` at `text` - plus the legacy
  flag aliases.

### Fixed

- **Spoken lines detected as speakers.** `Gracias Carla` (no trailing period)
  passed every lexical test for a name: two capitalised words, no digits, no
  final punctuation. It entered the participant roster and, worse, `fix.py`
  treated it as metadata and skipped corrections on real speech. The fix is
  structural rather than lexical: in a Teams transcript a speaker header is
  followed by a **pure timestamp line** (`0 minutos 3 segundos0:03`), while spoken
  text follows a `Name + timestamp` header. New `is_pure_timestamp_line()`;
  `is_speaker_line()` now takes the following line and falls back to strict
  membership in the learned speaker set when it cannot verify the structure.

---

## [0.1.0] - 2026-10-14

First extraction of the standalone `transcript-gap-detector` script into a
distributable package, as a sibling of `@keber/qa-framework`.

### Added

- **Two-layer dictionary model.** `load_bundle([...])` merges an engine layer
  (Teams ASR artifacts, shipped with the package) with any number of project
  domain overlays. The last layer wins on a shared rule `id`.
- **Confidence levels** (`alta` / `media` / `baja`) on every rule, following the
  `Fuentes / Confianza / TODO` contract of `rag-v1/index.md`. Only `alta` is
  applied by `--fix`; the rest is reported with timestamp and context for human
  confirmation.
- **`people` entries** in the domain overlay, with `resolve_speaker()` and
  `find_person()`. The transcript spells names without accents and sometimes
  varies the spelling; the minute spells them correctly.
- **Ownership-aware install.** `init` and `upgrade` replace framework-owned files
  on every run and seed `qa/00-standards/minutes/domain.json` exactly once. A
  local edit to a framework-owned file is named in the output before being
  replaced, so it can be promoted upstream instead of vanishing.
- **`meeting-minutes` skill** (`skills/meeting-minutes/SKILL.md`) covering the
  full flow: validate, clean, report gaps, segment, cross-reference against Azure
  DevOps, write, declare sources.
- **Minute template** (`templates/minuta.md`) derived from 13 real minutes across
  two projects, plus a `## Trazabilidad` section and the sources/confidence/TODO
  footer.
- **CLI flags**: `--engine`, `--domain` (repeatable), `--no-engine`, `--fix`,
  `--min-confidence`, `--lint`, `--speakers`.
- Entry points `python -m tgd` and `meeting-minutes.py`.
- 24 tests: 15 Python (dictionary layers, confidence filtering, corpus
  regressions, speaker resolution) and 9 Node (ownership model, idempotence,
  dry-run, self-install guards).

### Fixed

- **`UnicodeEncodeError` on Windows.** The console defaults to cp1252 and crashed
  when printing the `Δ` of the gap analysis or any accented name. stdout and
  stderr are now reconfigured to UTF-8. Without this the tool only ran on a
  console already set to UTF-8.
- **Missing entry point.** `cli.py` defined `main()` but never invoked it, so
  `python -m tgd.cli` exited silently with status 0.
- **`folios` degraded to `follios`** in the Sprint 11 corpus. A domain rule now
  reverts it.
- **Dead lookahead** in the former `book_bug_except_booking` rule: `\bbook\b`
  already cannot match `booking`, since there is no word boundary between `k`
  and `i`.

### Changed

- `apply_mishear_fixes_to_lines()` takes `min_confidence` (default `alta`) and no
  longer mutates its input list.
- Rules previously applied unconditionally are now lint-only: `see you` ->
  `sí, obvio` and `book` -> `bug` are `baja`, being single-occurrence semantic
  leaps.
- A v1 dictionary with no declared confidence loads as `media`, reported in
  `bundle.issues`. An existing dictionary never starts auto-rewriting because the
  package was upgraded.
- Legacy flags (`--fix-known-mishears`, `--mishear-dict`, `--lint-mishear`,
  `--lint-meshear`) remain as hidden aliases.

### Removed

- `transcript-gap-detector.py`, replaced by `meeting-minutes.py` and
  `tgd/__main__.py`. The name no longer described the scope: gap detection became
  one step of the flow rather than its purpose.
