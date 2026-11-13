"""Segmentacion de una transcripcion en bloques tematicos.

Teams emite un evento por turno de habla, asi que una reunion de 26 minutos deja
~700 eventos, la mayoria de una palabra ("ya.", "Si."). Agrupar los turnos
consecutivos de un mismo hablante reduce eso a una lista legible sin perder
timestamps ni la posicion en el archivo original: 1233 lineas -> 188 bloques en
el corpus del Sprint 11.

Es la entrada del paso de segmentacion de la skill, y lo que hace posible
proponer un mapeo tema -> work item con una cita y un timestamp detras.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Sequence

from .models import Event, Person
from .utils import format_time


@dataclass
class Block:
    t: int
    speaker: str
    display: str
    turns: List[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0

    @property
    def text(self) -> str:
        return " ".join(self.turns)


def _resolve(name: str, people: Sequence[Person]) -> str:
    # Import local para no crear un ciclo fix <-> segment.
    from .fix import resolve_speaker

    return resolve_speaker(name, people)


def build_blocks(events: Sequence[Event], people: Sequence[Person] = ()) -> List[Block]:
    """Agrupa turnos consecutivos del mismo hablante.

    Los eventos sin texto se descartan antes de agrupar: son timestamps
    intermedios que el parser conserva a proposito, y cortarian un bloque en dos
    sin aportar contenido.
    """
    blocks: List[Block] = []

    for ev in events:
        text = (ev.text or "").strip()
        if not text:
            continue

        if blocks and blocks[-1].speaker == ev.speaker:
            blocks[-1].turns.append(text)
            blocks[-1].line_end = ev.line_no
            continue

        blocks.append(
            Block(
                t=ev.t,
                speaker=ev.speaker,
                display=_resolve(ev.speaker, people),
                turns=[text],
                line_start=ev.line_no,
                line_end=ev.line_no,
            )
        )

    return blocks


def blocks_to_text(blocks: Sequence[Block]) -> str:
    return "\n".join(f"[{format_time(b.t).strip()}] {b.display}: {b.text}" for b in blocks)


def blocks_to_json(blocks: Sequence[Block]) -> str:
    payload = {
        "blockCount": len(blocks),
        "blocks": [
            {
                "t": b.t,
                "timestamp": format_time(b.t).strip(),
                "speaker": b.speaker,
                "display": b.display,
                "lineStart": b.line_start,
                "lineEnd": b.line_end,
                "text": b.text,
            }
            for b in blocks
        ],
    }
    # ensure_ascii=False: la skill lee esto y los nombres deben quedar legibles.
    return json.dumps(payload, ensure_ascii=False, indent=2)
