from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .models import CONFIDENCE_LEVELS, MishearRule, Person
from .parser import RE_HEADER_DATE, build_known_speakers, is_speaker_line, parse_timestamp
from .utils import clean_line, fold


def apply_mishear_fixes_to_lines(
    lines: Sequence[str],
    rules: Iterable[MishearRule],
    *,
    known_speakers: Set[str],
    min_confidence: str = "alta",
) -> Tuple[List[str], Dict[str, int]]:
    """Aplica reemplazos conservando la metadata de la transcripcion.

    Solo se aplican las reglas cuyo nivel de confianza alcanza `min_confidence`.
    Por defecto eso significa unicamente `alta`: el resto se reporta por lint y
    requiere confirmacion humana, porque reescribir el registro de una reunion
    con una suposicion es peor que dejar el texto crudo.

    Nunca modifica `lines`; devuelve una lista nueva.
    """
    applicable = _filter_by_confidence(rules, min_confidence)
    counts: Dict[str, int] = {}
    out: List[str] = []

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = clean_line(line)

        if not stripped or _is_metadata_line(stripped, known_speakers):
            out.append(raw)
            continue

        new_line = line
        for rule in applicable:
            new_line, n = rule.rx.subn(rule.suggest, new_line)
            if n:
                counts[rule.id] = counts.get(rule.id, 0) + n

        out.append(new_line + "\n" if raw.endswith("\n") else new_line)

    return out, counts


def _filter_by_confidence(rules: Iterable[MishearRule], min_confidence: str) -> List[MishearRule]:
    if min_confidence not in CONFIDENCE_LEVELS:
        raise ValueError(
            f"min_confidence invalido: {min_confidence!r} (validos: {', '.join(CONFIDENCE_LEVELS)})"
        )
    threshold = CONFIDENCE_LEVELS.index(min_confidence)
    return [r for r in rules if CONFIDENCE_LEVELS.index(r.confidence) <= threshold]


def _is_metadata_line(stripped: str, known_speakers: Set[str]) -> bool:
    """Cabeceras, iniciales de avatar, nombres de hablante y timestamps de Teams."""
    if RE_HEADER_DATE.match(stripped) or stripped.lower().startswith("transcripcion"):
        return True
    if stripped.lower().startswith("transcripción"):
        return True
    if len(stripped) <= 3 and stripped.isalpha():
        return True
    is_name = is_speaker_line(stripped, known_speakers)
    if is_name:
        return True
    return parse_timestamp(stripped, context_has_speaker=is_name) is not None


def known_speakers_from_lines(lines: Sequence[str]) -> Set[str]:
    return build_known_speakers(list(lines), min_count=2)


def resolve_speaker(name: str, people: Sequence[Person]) -> str:
    """Devuelve el nombre de visualizacion de un hablante.

    La transcripcion entrega los nombres sin tildes y a veces con variantes
    de escritura ('Catia' por 'Katia'), mientras que la minuta los escribe bien.
    Un nombre desconocido se devuelve intacto: no se adivina.
    """
    if not name:
        return name
    key = fold(name)
    for person in people:
        if key == fold(person.canonical) or key == fold(person.display):
            return person.display
        if any(key == fold(alias) for alias in person.aliases):
            return person.display
    return name


def find_person(name: str, people: Sequence[Person]) -> Optional[Person]:
    """Como `resolve_speaker`, pero devuelve la entrada completa (incluye el rol)."""
    if not name:
        return None
    key = fold(name)
    for person in people:
        if key in {fold(person.canonical), fold(person.display)}:
            return person
        if any(key == fold(alias) for alias in person.aliases):
            return person
    return None
