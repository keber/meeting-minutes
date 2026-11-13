---
name: meeting-minutes
description: >
  Turns a raw Teams meeting transcript into a reviewable minute document.
  Cleans domain-term ASR corruption, reports transcription gaps, and proposes a
  traceability mapping between discussed topics and Azure DevOps work items so a
  human can confirm it without replaying the recording.
  Use when asked to write a minute, generate a minuta, process a meeting
  transcript, summarize a planning meeting, or map a transcript to sprint work
  items.
  Requires a Teams transcript file. The ADO cross-reference requires
  @keber/ado-qa configured with a PAT in env vars; without it the skill still
  produces the minute and marks traceability as TODO.
---

# Skill: Meeting Minutes

**Input**: a raw Teams transcript (`.txt`/`.md`) copied from the meeting recording
**Output**: a minute document following `templates/minuta.md`, plus a traceability proposal
**Optional input**: Azure DevOps sprint work items, planning deck, planning email

> **Core rule**: never invent content. Anything not derivable from the declared
> sources is marked `TODO`, never guessed. This mirrors the contract in
> `rag-v1/index.md`: every artifact declares Fuentes / Confianza / TODO.

---

## Inputs Required

1. The transcript file path (ask if not given).
2. Project context from `qa/qa-framework.config.json` -> `project.name`, `conventions.locale`.
3. Domain overlay: the project's `domain.json` (see `data/domain.example.json` for its shape).
   If the project has none, run with the engine layer alone and say so in the output.
4. Sprint number (ask if not inferable from the filename or the transcript).
5. ADO sprint work items, if ADO is configured.

---

## Process

### Step 1 - Validate the input

Confirm the file is a Teams transcript: speaker blocks with duplicated headers and a
concatenated timestamp (`0 minutos 3 segundos0:03`). Report line count and the last
timestamp - that timestamp is the meeting duration and goes in the header.

If the transcript already carries manual `[Task NNNNN]` / `[Issue NNNNN]` markers,
treat them as confirmed traceability and skip the matching in Step 5 for those topics.

### Step 2 - Clean the transcript

Run `tgd` with both dictionary layers:

```
python -m tgd.cli <transcript> --fix --engine data/engine-artifacts.json --domain <project domain.json>
```

- `confidence: alta` rules are applied and written to `<input>.fixed.txt`.
- `confidence: media` and `baja` rules are reported only. Present them as a short list
  for confirmation; apply one only if the user confirms it.
- The original file is never modified.

This step is not cosmetic. Corrupted domain terms (`buging`, `stalking`, `Cuba`) are the
exact keywords Step 5 matches on, so skipping it degrades traceability.

### Step 3 - Report gaps

Run the gap analysis and list suspicious silences. Each gap is a span where the recording
lost content, so any topic near one may be incomplete. Carry these into the final `TODO`
line rather than silently ignoring them.

### Step 4 - Segment into topics

```
python -m tgd <transcript> --domain <project domain.json> --dump --dump-format json
```

This merges consecutive turns by the same speaker into blocks, writing
`<input>.blocks.json`. On the Sprint 11 corpus that turns 685 events into 188
blocks - a meeting becomes readable in one pass. Each block carries its start
timestamp, the raw and resolved speaker names, and `lineStart`/`lineEnd`, so any
quote can be traced back to the original transcript.

Read that file and group the blocks into topics. For each topic record:
- start timestamp
- the participants who spoke in it
- a one-line topic label in the meeting's own vocabulary
- any explicit effort figure said aloud (e.g. `"4 horas."`)

Do not merge unrelated topics to make the list shorter, and do not split one topic
because it spans several speakers.

### Step 5 - Cross-reference against Azure DevOps

Skip this step when ADO is not configured; mark traceability `TODO` and continue.

1. Fetch the sprint work items via `@keber/ado-qa`: `System.Id`, `System.Title`,
   `System.WorkItemType`, `System.AssignedTo`, `System.State` and
   **`System.Description`**.

   The description matters as much as the title. A meeting names a topic loosely
   ("la validación del contenedor") while the work item carries the acceptance
   criteria that were never said out loud - for example, that the system also
   checks uniqueness and blocks a duplicate with an error message. Use it to
   complete the topic in Part 2, labelled as coming from the work item so it is
   never confused with what was discussed.
2. For each topic block from Step 4, propose the matching work item **from that closed
   set only**. This is an assignment problem against a known list, not open extraction.
3. Assign a confidence per match:
   - **Alta**: the topic names the work item's subject explicitly, or the transcript
     carries the ID marker.
   - **Media**: the topic clearly matches the work item's domain but the wording differs.
   - **Baja**: plausible but ambiguous between two or more items.
4. Record the literal transcript quote that justifies each match, with its timestamp.
5. List sprint work items that no topic matched, and topics that matched no work item.

Never write an ADO title from memory or from the conversation - use `System.Title`
verbatim. A `Baja` match is a proposal, not a fact: it goes in the table with its
confidence, and the heading stays without an ID until the user confirms it.

### Step 6 - Write the minute

Fill `templates/minuta.md`. The minute has two parts, and they are **not two
resolutions of the same content**: Part 1 is the conclusions, Part 2 is the
evidence behind them. If Part 1 summarises Part 2, nobody reads the second and
everything is duplicated.

**Part 1 - Acta.** Written for someone who was in the meeting. One line per item,
no narration. It must be readable in two minutes.

- **Resumen ejecutivo**: one paragraph. What was agreed and with what focus.
  Do not enumerate the topics - the table does that.
- **Temas y trazabilidad**: one row per topic, in the order they were discussed:
  number, topic, work item, effort, confidence, timestamp. Effort is the figure
  said aloud; the literal quote behind it belongs in Part 2. Close with the total
  declared in the meeting, if any, and with the sprint work items nobody mentioned.
- **Decisiones y acuerdos**: flat list, one line each, the decided part in bold.
  Only what was agreed, not what was discussed.
- **Riesgos**: typed bold label - `**Riesgo:**`, `**Bloqueo:**`, `**Dependencia:**`.
  One line each.
- **Próximos pasos**: ordered list, infinitive verb first, one line per step.

**Part 2 - Desarrollo.** Written for someone who was not there: an audit months
later, a tester writing cases, and the project's knowledge base. Detail belongs
here, and only here.

- One `###` per topic, with the work item ID in parentheses when confirmed.
  Bullets, never tables.
- Keep what Part 1 cannot carry: field and screen inventories, technical
  resolutions (if someone asked and it was answered, record the answer, not the
  question), the literal quote with timestamp behind each estimate.
- Detail taken from the work item's `System.Description` goes here under a
  `**Del work item (ID):**` label, so it is never mistaken for what was discussed.
- What does not belong: conversational colour with no bearing on a decision.
- **Glosario breve**: only terms present in this minute and already defined in the
  domain overlay. A new term is listed as `- **Término:** TODO`.

No checkboxes anywhere. Separate `##` blocks with `---`.

Resolve participant names through the overlay's `people` entries so accents and
preferred spellings are restored. Participants are those who **spoke**: someone who
attended silently will not appear, so flag that in `TODO` when the attendee list is known
to be larger.

The minute is written in the project's locale (`conventions.locale`), not in English.

### Step 7 - Declare sources and confidence

Fill the footer: the transcript filename, any deck or email used, the ADO query, the
overall confidence, and every unresolved item - unmatched topics, gaps from Step 3,
sections that needed external input that was unavailable.

---

## Outputs

| Artifact | Location |
|---|---|
| Cleaned transcript | `<input>.fixed.txt` (alongside the input) |
| Minute document | project convention, e.g. `qa/02-test-plans/historical/sprint-{N}/` |
| Traceability proposal | `## Temas y trazabilidad` table in Part 1 of the minute |

---

## Quality gates before marking complete

- No section contains content that cannot be traced to a declared source.
- Every effort figure in the minute appears literally in the transcript.
- Every ADO ID in a heading has an `Alta` match or a manual marker behind it.
- The traceability table lists unmatched work items and unmatched topics.
- The footer declares Fuentes, Confianza and TODO - none of them empty by default.
- The original transcript file is unmodified.
