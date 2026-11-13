from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
import re


# Niveles de confianza, heredados del contrato de rag-v1/index.md.
# Solo "alta" se aplica automaticamente; el resto se reporta para confirmacion.
CONFIDENCE_LEVELS = ("alta", "media", "baja")
DEFAULT_CONFIDENCE = "media"


@dataclass
class Event:
    line_no: int
    t: int  # seconds
    speaker: str
    text: str


@dataclass(frozen=True)
class MishearRule:
    id: str
    rx: re.Pattern
    suggest: str
    reason: str
    confidence: str = DEFAULT_CONFIDENCE
    layer: str = "engine"


@dataclass(frozen=True)
class Person:
    canonical: str
    display: str
    aliases: tuple = ()
    role: str = ""


@dataclass
class DictionaryBundle:
    """Resultado de fusionar las capas de diccionario (motor + dominio)."""

    rules: List[MishearRule] = field(default_factory=list)
    goodbye_markers: List[str] = field(default_factory=list)
    allow_terms: set = field(default_factory=set)
    people: List[Person] = field(default_factory=list)
    glossary: List[dict] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

    def rules_at_least(self, min_confidence: str) -> List[MishearRule]:
        """Reglas cuyo nivel de confianza alcanza el umbral pedido."""
        threshold = CONFIDENCE_LEVELS.index(min_confidence)
        return [r for r in self.rules if CONFIDENCE_LEVELS.index(r.confidence) <= threshold]
