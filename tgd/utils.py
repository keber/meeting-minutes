from __future__ import annotations

import re
import unicodedata
from typing import List, Tuple

from .models import Event


def format_time(seconds: int) -> str:
    """Convierte segundos a formato MM:SS user-friendly."""
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:2d}:{secs:02d}"


def clean_line(s: str) -> str:
    return s.replace("\ufeff", "").strip()


def words_count(s: str) -> int:
    return len(re.findall(r"\b\w+\b", s, flags=re.UNICODE))


def normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def strip_accents(s: str) -> str:
    """Quita diacriticos. La transcripcion de Teams entrega los nombres sin tildes,
    asi que la comparacion contra el diccionario de personas debe ignorarlas."""
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def fold(s: str) -> str:
    """Clave de comparacion insensible a mayusculas, tildes y espacios repetidos."""
    return strip_accents(normalize_text(s))


def make_context(events: List[Event], idx: int, window: int) -> str:
    start = max(0, idx - window)
    end = min(len(events), idx + window + 1)
    parts: List[str] = []
    for j in range(start, end):
        tag = "*" if j == idx else " "
        snippet = (events[j].text or "").strip()
        snippet = snippet.replace("\n", " ")
        if len(snippet) > 160:
            snippet = snippet[:160] + "..."
        parts.append(f"{tag} {format_time(events[j].t)} {events[j].speaker}: {snippet}")
    return "\n".join(parts)


def dedup_token(s: str) -> str:
    s = normalize_text(s)
    s = re.sub(r"[^\w\s]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def dedup_key(line_no: int, matched_text: str, suggestion: str) -> Tuple[int, str]:
    return (line_no, dedup_token(matched_text) + "->" + dedup_token(suggestion))


def compile_flags(flag_names: List[str]) -> int:
    flags = 0
    for name in flag_names:
        if not name:
            continue
        upper = name.upper()
        if upper == "IGNORECASE":
            flags |= re.IGNORECASE
        elif upper == "MULTILINE":
            flags |= re.MULTILINE
        elif upper == "DOTALL":
            flags |= re.DOTALL
    return flags
