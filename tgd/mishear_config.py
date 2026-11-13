from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Sequence, Set, Tuple

from .models import (
    CONFIDENCE_LEVELS,
    DEFAULT_CONFIDENCE,
    DictionaryBundle,
    MishearRule,
    Person,
)
from .utils import compile_flags


def load_bundle(paths: Sequence[str]) -> DictionaryBundle:
    """Carga y fusiona capas de diccionario en orden de precedencia creciente.

    La ultima capa gana: una regla de dominio con el mismo `id` que una del motor
    la reemplaza por completo. Ningun error de formato interrumpe la carga; todo
    se acumula en `bundle.issues` para que el llamador lo reporte.
    """
    bundle = DictionaryBundle()
    by_id: Dict[str, MishearRule] = {}
    people_by_canonical: Dict[str, Person] = {}

    for path in paths:
        if not path:
            continue
        data, issues = _read_json(path)
        bundle.issues.extend(issues)
        if data is None:
            continue

        layer = str(data.get("layer") or _infer_layer(path))
        version = data.get("version", 1)
        if version < 2:
            bundle.issues.append(
                f"{path}: esquema v1 sin niveles de confianza; las reglas se tratan "
                f"como '{DEFAULT_CONFIDENCE}' (solo lint, nunca reemplazo automatico)."
            )

        for rule in _parse_rules(data, path, layer, bundle.issues):
            by_id[rule.id] = rule

        for person in _parse_people(data, path, bundle.issues):
            people_by_canonical[person.canonical] = person

        for marker in data.get("goodbyeMarkers", []) or []:
            if isinstance(marker, str) and marker.strip():
                bundle.goodbye_markers.append(marker.strip())

        # `allowEnglishTerms` es el nombre del esquema v1; `allowTerms` el de v2.
        for term in (data.get("allowTerms") or data.get("allowEnglishTerms") or []):
            if isinstance(term, str) and term.strip():
                bundle.allow_terms.add(term.strip().lower())

        for entry in data.get("glossary", []) or []:
            if isinstance(entry, dict) and entry.get("term"):
                bundle.glossary.append(entry)

    bundle.rules = list(by_id.values())
    bundle.people = list(people_by_canonical.values())
    return bundle


def _read_json(path: str) -> Tuple[Any, List[str]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, [f"No se encontro el diccionario: {path}"]
    except Exception as e:
        return None, [f"No se pudo leer el diccionario {path}: {e}"]

    if not isinstance(data, dict):
        return None, [f"Formato invalido en {path}: se esperaba un objeto JSON"]
    return data, []


def _infer_layer(path: str) -> str:
    return "domain" if "domain" in path.replace("\\", "/").lower() else "engine"


def _parse_rules(data: dict, path: str, layer: str, issues: List[str]) -> List[MishearRule]:
    raw = data.get("rules", [])
    if not isinstance(raw, list):
        issues.append(f"Formato invalido en {path}: 'rules' debe ser una lista")
        return []

    out: List[MishearRule] = []
    for idx, rule in enumerate(raw):
        if not isinstance(rule, dict):
            issues.append(f"{path}: regla #{idx} invalida (debe ser objeto)")
            continue
        if rule.get("enabled", True) is False:
            continue

        rule_id = str(rule.get("id", f"rule_{idx}"))
        pattern = rule.get("pattern")
        suggest = rule.get("suggest")
        if not isinstance(pattern, str) or not isinstance(suggest, str):
            issues.append(f"{path}: regla '{rule_id}' requiere 'pattern' y 'suggest' de tipo str")
            continue

        confidence = str(rule.get("confidence", DEFAULT_CONFIDENCE)).lower()
        if confidence not in CONFIDENCE_LEVELS:
            issues.append(
                f"{path}: regla '{rule_id}' declara confidence='{confidence}' "
                f"(validos: {', '.join(CONFIDENCE_LEVELS)}); se degrada a '{DEFAULT_CONFIDENCE}'"
            )
            confidence = DEFAULT_CONFIDENCE

        flags = rule.get("flags", [])
        if not isinstance(flags, list):
            flags = []
        try:
            rx = re.compile(pattern, compile_flags([str(x) for x in flags]))
        except Exception as e:
            issues.append(f"{path}: regla '{rule_id}' tiene un regex invalido '{pattern}' ({e})")
            continue

        out.append(
            MishearRule(
                id=rule_id,
                rx=rx,
                suggest=suggest,
                reason=str(rule.get("reason", "")),
                confidence=confidence,
                layer=layer,
            )
        )
    return out


def _parse_people(data: dict, path: str, issues: List[str]) -> List[Person]:
    raw = data.get("people", [])
    if not isinstance(raw, list):
        issues.append(f"Formato invalido en {path}: 'people' debe ser una lista")
        return []

    out: List[Person] = []
    for idx, person in enumerate(raw):
        if not isinstance(person, dict):
            issues.append(f"{path}: persona #{idx} invalida (debe ser objeto)")
            continue
        canonical = person.get("canonical")
        if not isinstance(canonical, str) or not canonical.strip():
            issues.append(f"{path}: persona #{idx} requiere 'canonical'")
            continue
        aliases = person.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        out.append(
            Person(
                canonical=canonical.strip(),
                display=str(person.get("display") or canonical).strip(),
                aliases=tuple(str(a).strip() for a in aliases if str(a).strip()),
                role=str(person.get("role", "")).strip(),
            )
        )
    return out


# --- Compatibilidad con la interfaz v1 -------------------------------------

def load_mishear_config(path: str) -> Tuple[List[MishearRule], List[str], Set[str], List[str]]:
    """Interfaz heredada del script original. Preferir `load_bundle`."""
    bundle = load_bundle([path])
    return bundle.rules, bundle.goodbye_markers, bundle.allow_terms, bundle.issues
