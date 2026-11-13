from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple

try:
    # wordfreq es pure-python y funciona bien en Windows.
    # Se usa como "spellcheck" probabilístico: si una palabra es mucho más frecuente en EN que en ES,
    # la tratamos como token EN potencial incluso si no está en la stoplist.
    from wordfreq import zipf_frequency  # type: ignore

    _HAS_WORDFREQ = True
except Exception:  # pragma: no cover
    zipf_frequency = None
    _HAS_WORDFREQ = False

from .models import Event, MishearRule
from .utils import dedup_key, format_time, make_context, normalize_text


def lint_suspect_mishear(
    events: List[Event],
    *,
    window: int = 1,
    max_findings: int = 50,
    allow_english_terms: Optional[Set[str]] = None,
    use_wordfreq: bool = False,
    wordfreq_en_min_zipf: float = 3.5,
    wordfreq_min_advantage: float = 1.5,
) -> List[str]:
    """Lint heurístico para posibles mishears."""
    allow = {"booking", "stacking"}
    if allow_english_terms:
        allow |= {t.lower() for t in allow_english_terms}

    english = {
        "about", "after", "again", "all", "also", "and", "any", "are", "around", "at",
        "be", "been", "but", "by",
        "can", "cant", "can't", "could",
        "did", "do", "does", "dont", "don't",
        "for", "from",
        "get", "go", "got",
        "had", "has", "have", "he", "her", "here", "him", "his", "how",
        "i", "if", "into", "is", "it", "its",
        "just",
        "like",
        "make", "more", "most", "my",
        "not", "now",
        "of", "off", "on", "one", "or", "our", "out", "over",
        "please",
        "see", "she", "so", "some",
        "than", "that", "the", "their", "them", "then", "there", "they", "this", "to", "too",
        "up", "us",
        "was", "we", "were", "what", "when", "where", "which", "who", "with", "would",
        "yeah", "yes", "you", "your",
        "internals",
    }

    spanish_markers = {
        "que", "de", "la", "el", "los", "las", "y", "o", "pero", "porque",
        "para", "con", "sin", "como", "ya", "sí", "si", "entonces", "igual",
        "tenemos", "vamos", "hay", "uno", "una",
    }

    findings: List[str] = []
    seen: Set[Tuple[int, str]] = set()

    for idx, ev in enumerate(events):
        txt_raw = (ev.text or "").strip()
        if not txt_raw:
            continue

        txt_norm = normalize_text(txt_raw)
        tokens = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ']+", txt_raw)

        english_hits: List[str] = []
        for tok in tokens:
            tl = tok.lower()
            try:
                tl.encode("ascii")
            except UnicodeEncodeError:
                continue
            if tl in allow:
                continue
            if tl in english:
                english_hits.append(tl)
                continue

            # Spellcheck-like (probabilístico) via wordfreq
            if use_wordfreq and _HAS_WORDFREQ and zipf_frequency is not None:
                en = float(zipf_frequency(tl, "en"))
                es = float(zipf_frequency(tl, "es"))
                if en >= wordfreq_en_min_zipf and (en - es) >= wordfreq_min_advantage:
                    english_hits.append(tl)
        if not english_hits:
            continue

        words = re.findall(r"\b\w+\b", txt_norm, flags=re.UNICODE)
        has_spanish_context = any(w in spanish_markers for w in words)

        total_words = max(1, len(words))
        ratio = len(set(english_hits)) / total_words
        is_short = len(words) <= 6

        should_flag = False
        reason_parts: List[str] = []
        distinct = sorted(set(english_hits))
        short_only = all(len(t) <= 2 for t in distinct)

        if has_spanish_context and ratio >= (0.20 if short_only else 0.12):
            should_flag = True
            reason_parts.append("mezcla ES + tokens EN")
        elif is_short and ratio >= 0.34:
            should_flag = True
            reason_parts.append("frase corta mayormente EN")
        elif ratio >= 0.5:
            should_flag = True
            reason_parts.append("alta densidad de EN")

        if not should_flag:
            continue

        key = (ev.line_no, ",".join(sorted(set(english_hits))))
        if key in seen:
            continue
        seen.add(key)

        ctx = make_context(events, idx, window)
        findings.append(
            "\n".join(
                [
                    f"POSIBLE MISHEAR (suspect) @ {format_time(ev.t)} ({ev.speaker}) [L{ev.line_no}]",
                    f"  Texto: {txt_raw}",
                    f"  Tokens EN detectados: {', '.join(sorted(set(english_hits)))}",
                    f"  Motivo: {', '.join(reason_parts)}",
                    "  Contexto:",
                    ctx,
                ]
            )
        )
        if len(findings) >= max_findings:
            return findings

    return findings


def lint_mishear(
    events: List[Event],
    *,
    window: int = 1,
    max_findings: int = 50,
    explicit_patterns: Optional[List[MishearRule]] = None,
    goodbye_markers: Optional[List[str]] = None,
) -> List[str]:
    findings: List[str] = []
    seen: Set[Tuple[int, str]] = set()

    if explicit_patterns is None:
        explicit_patterns = []
    if goodbye_markers is None:
        goodbye_markers = []

    for idx, ev in enumerate(events):
        if not ev.text:
            continue
        for rule in explicit_patterns:
            m = rule.rx.search(ev.text)
            if m:
                key = dedup_key(ev.line_no, m.group(0), rule.suggest)
                if key in seen:
                    continue
                seen.add(key)
                ctx = make_context(events, idx, window)
                findings.append(
                    "\n".join(
                        [
                            f"POSIBLE MISHEAR @ {format_time(ev.t)} ({ev.speaker}) [L{ev.line_no}]",
                            f"  Texto: {ev.text.strip()}",
                            f"  Sugerencia: {rule.suggest}",
                            f"  Motivo: {rule.reason}",
                            "  Contexto:",
                            ctx,
                        ]
                    )
                )
                if len(findings) >= max_findings:
                    return findings

    farewell_idxs: List[int] = []
    for idx, ev in enumerate(events):
        txt = normalize_text(ev.text or "")
        if any(m in txt for m in goodbye_markers):
            farewell_idxs.append(idx)

    if farewell_idxs:
        min_i = max(0, min(farewell_idxs) - 5)
        max_i = min(len(events) - 1, max(farewell_idxs) + 5)
        for idx in range(min_i, max_i + 1):
            ev = events[idx]
            txt = normalize_text(ev.text or "")
            if not txt:
                continue

            if txt in {"to town.", "to town", "tocho.", "tocho"}:
                suggestion = "chao" if "town" in txt else "chao chao"
                key = dedup_key(ev.line_no, txt, suggestion)
                if key in seen:
                    continue
                seen.add(key)
                ctx = make_context(events, idx, window)
                findings.append(
                    "\n".join(
                        [
                            f"POSIBLE MISHEAR @ {format_time(ev.t)} ({ev.speaker}) [L{ev.line_no}]",
                            f"  Texto: {ev.text.strip()}",
                            f"  Sugerencia: {suggestion}",
                            "  Motivo: Zona de despedida + token fonético raro",
                            "  Contexto:",
                            ctx,
                        ]
                    )
                )
                if len(findings) >= max_findings:
                    return findings

    return findings
