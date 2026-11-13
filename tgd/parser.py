from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional, Set

from .models import Event
from .utils import clean_line


# Detecta timestamps en Teams:
# - "3 minutos 49 segundos"
# - "0 minutos 3 segundos0:03" (pegado)
# - "2 minutos2:00" (pegado, sin frontera de palabra)
# - "3:49" o "12:34" (mm:ss)
RE_MIN_SEC = re.compile(r"(?P<m>\d{1,3})\s*minuto[s]?\s*(?P<s>\d{1,2})\s*segundo[s]?", re.IGNORECASE)
# Sin \b inicial: en "2 minutos2:00" no hay frontera de palabra entre la 's' y el '2'.
RE_MMSS = re.compile(r"(?<!\d)(?P<m>\d{1,3}):(?P<s>\d{2})(?!\d)")

# Líneas que suelen ser "ruido" en copia/pega
RE_HEADER_DATE = re.compile(r"^\s*\d{1,2}-\d{1,2}-\d{4}\s+\d{1,2}:\d{2}\s*$", re.IGNORECASE)

# Heurísticas de nombres (Chile-friendly): soporta conectores como "De la" y nombres compuestos.
CONNECTORS = {"de", "del", "la", "las", "los", "y", "da", "do", "dos"}
RE_NAME_WORD = re.compile(r"^(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,})$")


def parse_timestamp(line: str, context_has_speaker: bool = False) -> Optional[int]:
    """Extrae timestamp REAL de metadata de Teams.

    Para reducir falsos positivos (menciones de horas en conversación),
    prioriza 'X minutos Y segundos' y acepta MM:SS solo con contexto.
    """
    m1 = RE_MIN_SEC.search(line)
    if m1:
        mm = int(m1.group("m"))
        ss = int(m1.group("s"))
        return mm * 60 + ss

    m2 = RE_MMSS.search(line)
    if m2 and not line[m2.end():].strip():
        # Solo cuenta si el timestamp CIERRA la linea. Una hora dicha en voz alta
        # ("todos entraron a las 7:30 casi todos") lleva texto detras, y tomarla
        # por metadata hace retroceder la reunion y crea un hablante fantasma.
        return int(m2.group("m")) * 60 + int(m2.group("s"))

    return None


def is_name_like(line: str) -> bool:
    """Detecta si una línea parece un nombre completo (no texto conversacional)."""
    if not line or RE_HEADER_DATE.match(line):
        return False
    if len(line) < 3:
        return False
    if re.search(r"\d", line):
        return False
    if re.search(r"[.!?;:]$", line):
        return False

    words = line.split()
    if len(words) < 2:
        return False

    good = 0
    for w in words:
        wl = w.lower()
        if wl in CONNECTORS:
            good += 1
            continue
        if RE_NAME_WORD.match(w):
            good += 1

    return (good / len(words)) >= 0.8


def is_pure_timestamp_line(line: str) -> bool:
    """Línea que es SOLO un timestamp, como '0 minutos 3 segundos0:03'.

    Se distingue de la cabecera 'Nombre 0 minutos 3 segundos', que lleva texto
    antes del número.
    """
    positions = []
    m1 = RE_MIN_SEC.search(line)
    if m1:
        positions.append(m1.start())
    m2 = RE_MMSS.search(line)
    if m2:
        positions.append(m2.start())
    if not positions:
        return False
    return not line[: min(positions)].strip()


def _next_non_empty(lines: List[str], start: int) -> Optional[str]:
    for raw in lines[start:]:
        line = clean_line(raw)
        if line:
            return line
    return None


def build_known_speakers(lines: List[str], min_count: int = 2) -> Set[str]:
    """Aprende speakers por frecuencia a partir de líneas name-like.

    Parecer un nombre no alcanza: una frase hablada como 'Gracias Carla' pasa
    todas las pruebas lexicas (dos palabras capitalizadas, sin digitos, sin
    puntuacion final). Teams las separa estructuralmente — la cabecera de
    hablante va seguida de un timestamp puro, el texto hablado no — asi que esa
    es la condicion que se exige.
    """
    counts = Counter()
    for idx, raw in enumerate(lines):
        line = clean_line(raw)
        if not line:
            continue
        if RE_HEADER_DATE.match(line) or line.lower().startswith("transcripción"):
            continue
        if len(line) <= 3 and line.isalpha():
            continue
        if not is_name_like(line):
            continue
        following = _next_non_empty(lines, idx + 1)
        if following is not None and is_pure_timestamp_line(following):
            counts[line] += 1
    return {name for name, c in counts.items() if c >= min_count}


def is_speaker_line(
    line: str,
    known_speakers: Set[str],
    *,
    following: Optional[str] = None,
) -> bool:
    """Un nombre conocido siempre lo es. Uno desconocido requiere la estructura
    de Teams: cabecera seguida de timestamp puro. Sin `following` no hay como
    verificarlo, asi que se exige pertenecer al set aprendido."""
    if line in known_speakers:
        return True
    if following is None:
        return False
    return is_name_like(line) and is_pure_timestamp_line(following)


# Back-compat
def likely_speaker_line(line: str) -> bool:
    return is_name_like(line)


def extract_events(lines: List[str]) -> List[Event]:
    events: List[Event] = []
    known_speakers = build_known_speakers(lines, min_count=2)
    current_speaker = ""
    current_t: Optional[int] = None
    buffer_text: List[str] = []

    def flush(prev_line_no: int):
        nonlocal current_t, current_speaker, buffer_text
        if current_t is None:
            buffer_text = []
            return
        text = " ".join([t for t in buffer_text if t]).strip()
        events.append(
            Event(
                line_no=prev_line_no,
                t=current_t,
                speaker=current_speaker.strip() or "(sin speaker)",
                text=text,
            )
        )
        buffer_text = []

    for i, raw in enumerate(lines, start=1):
        line = clean_line(raw)
        if not line:
            continue
        if RE_HEADER_DATE.match(line) or line.lower().startswith("transcripción"):
            continue

        following = _next_non_empty(lines, i)
        is_header = is_speaker_line(line, known_speakers, following=following)
        has_speaker_context = bool(is_header or (current_speaker != "" and current_speaker in line))
        t = parse_timestamp(line, context_has_speaker=has_speaker_context)

        if len(line) == 1 and line.isalpha():
            continue

        if t is None and is_header:
            if current_t is not None and any(x.strip() for x in buffer_text):
                flush(i - 1)
            current_speaker = line
            continue

        if t is not None:
            flush(i - 1)
            current_t = t

            speaker_guess = line
            cut_positions = []
            m_ms = RE_MIN_SEC.search(line)
            if m_ms:
                cut_positions.append(m_ms.start())
            m_mms = RE_MMSS.search(line)
            if m_mms:
                cut_positions.append(m_mms.start())
            if cut_positions:
                speaker_guess = line[: min(cut_positions)].strip()

            if speaker_guess and len(speaker_guess.split()) >= 2 and not re.search(r"\d", speaker_guess):
                current_speaker = speaker_guess

            continue

        if current_speaker and current_speaker in line and (RE_MIN_SEC.search(line) or RE_MMSS.search(line)):
            continue

        buffer_text.append(line)

    flush(len(lines))
    # Mantener eventos aunque el texto esté vacío evita perder timestamps intermedios.
    return [e for e in events if e.t is not None]
