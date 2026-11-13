from __future__ import annotations

import re
from typing import List, Tuple

from .models import Event
from .utils import format_time, words_count


def analyze(
    events: List[Event],
    min_silence: int,
    suspicious_silence: int,
    wps: float,
    factor: float,
    base_overhead: float,
) -> Tuple[List[str], List[str]]:
    gaps: List[str] = []
    issues: List[str] = []

    if len(events) < 2:
        issues.append("No hay suficientes eventos con timestamp para analizar.")
        return gaps, issues

    for prev, cur in zip(events, events[1:]):
        delta = cur.t - prev.t
        if delta < 0:
            issues.append(
                f"RETROCESO: {format_time(prev.t)} (L{prev.line_no}) -> {format_time(cur.t)} (L{cur.line_no}) | "
                f"Δ={delta}s ({format_time(abs(delta))} hacia atrás)"
            )
            continue

        wc = words_count(prev.text)
        expected = base_overhead + (wc / wps if wps > 0 else 0)

        if delta >= suspicious_silence and delta > expected * factor:
            gaps.append(
                f"GAP SOSPECHOSO: {format_time(prev.t)} -> {format_time(cur.t)} | "
                f"Δ={delta}s ({format_time(delta)}) | "
                f"prev_words={wc} | expected≈{expected:.1f}s | "
                f"prev_speaker='{prev.speaker}' (L{prev.line_no})"
            )
        elif delta > min_silence:
            pass

    return gaps, issues
