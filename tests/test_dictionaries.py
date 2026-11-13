"""Tests para la carga en dos capas del diccionario y el filtrado por confianza."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tgd.fix import apply_mishear_fixes_to_lines, resolve_speaker
from tgd.mishear_config import load_bundle

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(REPO_ROOT, "data", "engine-artifacts.json")
DOMAIN_EXAMPLE = os.path.join(REPO_ROOT, "data", "domain.example.json")


def write_tmp(payload: dict) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


class LoadBundleTests(unittest.TestCase):
    def test_engine_layer_loads_with_declared_confidences(self):
        bundle = load_bundle([ENGINE])
        self.assertEqual(bundle.issues, [])
        by_id = {r.id: r for r in bundle.rules}
        self.assertEqual(by_id["yeah_ya"].confidence, "alta")
        self.assertEqual(by_id["see_you_si_obvio"].confidence, "baja")
        self.assertEqual(by_id["yeah_ya"].layer, "engine")

    def test_domain_layer_merges_on_top_of_engine(self):
        bundle = load_bundle([ENGINE, DOMAIN_EXAMPLE])
        ids = {r.id for r in bundle.rules}
        self.assertIn("yeah_ya", ids)          # del motor
        self.assertIn("buging_booking", ids)   # del dominio
        domain_rules = [r for r in bundle.rules if r.layer == "domain"]
        self.assertTrue(all(r.confidence == "alta" for r in domain_rules))

    def test_domain_rule_overrides_engine_rule_with_same_id(self):
        override = write_tmp({
            "version": 2,
            "layer": "domain",
            "rules": [{
                "id": "yeah_ya",
                "pattern": r"\byeah\b",
                "suggest": "sip",
                "confidence": "baja",
                "reason": "override de proyecto",
            }],
        })
        try:
            bundle = load_bundle([ENGINE, override])
            matches = [r for r in bundle.rules if r.id == "yeah_ya"]
            self.assertEqual(len(matches), 1, "el id no debe duplicarse entre capas")
            self.assertEqual(matches[0].suggest, "sip")
            self.assertEqual(matches[0].confidence, "baja")
        finally:
            os.unlink(override)

    def test_v1_schema_defaults_to_lint_only(self):
        """Un diccionario viejo sin 'confidence' no debe aplicarse automaticamente."""
        legacy = write_tmp({
            "version": 1,
            "rules": [{"id": "legacy", "pattern": r"\bfoo\b", "suggest": "bar"}],
        })
        try:
            bundle = load_bundle([legacy])
            self.assertEqual(bundle.rules[0].confidence, "media")
            self.assertTrue(any("v1" in i or "confidence" in i for i in bundle.issues))
        finally:
            os.unlink(legacy)

    def test_invalid_regex_is_reported_not_raised(self):
        broken = write_tmp({
            "version": 2,
            "rules": [{"id": "roto", "pattern": "([", "suggest": "x", "confidence": "alta"}],
        })
        try:
            bundle = load_bundle([broken])
            self.assertEqual(bundle.rules, [])
            self.assertTrue(bundle.issues)
        finally:
            os.unlink(broken)

    def test_people_are_loaded_from_domain_layer(self):
        bundle = load_bundle([ENGINE, DOMAIN_EXAMPLE])
        self.assertTrue(bundle.people)
        katia = next(p for p in bundle.people if p.display.startswith("Katia"))
        self.assertIn("Catia Rojas Vera", katia.aliases)
        self.assertEqual(katia.role, "DEV")

    def test_missing_file_is_reported_not_raised(self):
        bundle = load_bundle([os.path.join(REPO_ROOT, "data", "no-existe.json")])
        self.assertEqual(bundle.rules, [])
        self.assertTrue(bundle.issues)


class ConfidenceFilterTests(unittest.TestCase):
    def setUp(self):
        self.bundle = load_bundle([ENGINE, DOMAIN_EXAMPLE])

    def test_fix_applies_only_alta(self):
        lines = [
            "Yeah.\n",                                   # alta  -> se aplica
            "See you.\n",                                # baja  -> NO se aplica
            "cuando se cancela el buging, entonces.\n",  # alta  -> se aplica
            "Después en el stalking nave.\n",            # alta  -> se aplica
        ]
        fixed, counts = apply_mishear_fixes_to_lines(
            lines, self.bundle.rules, known_speakers=set(), min_confidence="alta"
        )
        self.assertEqual(fixed[0], "ya.\n")
        self.assertEqual(fixed[1], "See you.\n")
        self.assertIn("booking", fixed[2])
        self.assertIn("stacking", fixed[3])
        self.assertNotIn("see_you_si_obvio", counts)

    def test_domain_corrections_match_the_sprint_10_corpus(self):
        """Regresion contra los cambios reales verificados en el Sprint 10."""
        lines = [
            "no tenemos publicado todavía en Cuba como para revisar.\n",
            "se habiliten los ETA de cada uno de ellos y un ED de general quedando.\n",
        ]
        fixed, _ = apply_mishear_fixes_to_lines(
            lines, self.bundle.rules, known_speakers=set(), min_confidence="alta"
        )
        self.assertIn("en QA como para revisar", fixed[0])
        self.assertIn("y un ETD general", fixed[1])

    def test_follios_regression_is_corrected(self):
        """El corpus degrado 'folios PT' a 'follios PT'; la capa de dominio lo revierte."""
        lines = ["¿existencia follios PT no sería la que se centraliza todo ya?\n"]
        fixed, _ = apply_mishear_fixes_to_lines(
            lines, self.bundle.rules, known_speakers=set(), min_confidence="alta"
        )
        self.assertIn("folios PT", fixed[0])
        self.assertNotIn("follios", fixed[0])

    def test_metadata_lines_are_never_rewritten(self):
        lines = [
            "F\n",
            "Martin Nunez Saez\n",
            "0 minutos 3 segundos0:03\n",
            "Yeah.\n",
        ]
        fixed, _ = apply_mishear_fixes_to_lines(
            lines,
            self.bundle.rules,
            known_speakers={"Martin Nunez Saez"},
            min_confidence="alta",
        )
        self.assertEqual(fixed[:3], lines[:3])
        self.assertEqual(fixed[3], "ya.\n")

    def test_original_lines_are_not_mutated(self):
        lines = ["Yeah.\n"]
        original = list(lines)
        apply_mishear_fixes_to_lines(
            lines, self.bundle.rules, known_speakers=set(), min_confidence="alta"
        )
        self.assertEqual(lines, original)


class SpeakerResolutionTests(unittest.TestCase):
    def setUp(self):
        self.people = load_bundle([ENGINE, DOMAIN_EXAMPLE]).people

    def test_canonical_name_resolves_to_display_with_accents(self):
        self.assertEqual(
            resolve_speaker("Martin Nunez Saez", self.people),
            "Martín Núñez Sáez",
        )

    def test_alias_resolves_to_display(self):
        self.assertEqual(
            resolve_speaker("Catia Rojas Vera", self.people),
            "Katia Rojas Vera",
        )

    def test_unknown_speaker_is_returned_untouched(self):
        self.assertEqual(resolve_speaker("Persona Desconocida", self.people), "Persona Desconocida")



class SpeakerDetectionTests(unittest.TestCase):
    """El formato de Teams distingue estructuralmente un nombre de un texto hablado:
    la linea de hablante va seguida de un timestamp puro ('0 minutos 3 segundos0:03'),
    nunca de otra cabecera 'Nombre + timestamp'."""

    def test_spoken_line_that_looks_like_a_name_is_not_a_speaker(self):
        from tgd.parser import build_known_speakers

        lines = [
            "F\n",
            "\n",
            "Joaquin Ignacio De la Fuente Lagos\n",
            "0 minutos 3 segundos0:03\n",
            "Joaquin Ignacio De la Fuente Lagos 0 minutos 3 segundos\n",
            "Hola a todos.\n",
            "Joaquin Ignacio De la Fuente Lagos 32 minutos 47 segundos\n",
            "Gracias Carla\n",
            "Joaquin Ignacio De la Fuente Lagos 32 minutos 51 segundos\n",
            "Que les vaya bien, chao chao.\n",
        ]
        speakers = build_known_speakers(lines, min_count=1)
        self.assertIn("Joaquin Ignacio De la Fuente Lagos", speakers)
        self.assertNotIn("Gracias Carla", speakers, "un texto hablado no es un hablante")

    def test_spoken_line_still_gets_corrected(self):
        """Si se la toma por metadata, deja de corregirse: ese es el dano real."""
        from tgd.parser import build_known_speakers

        lines = [
            "Joaquin Ignacio De la Fuente Lagos\n",
            "0 minutos 3 segundos0:03\n",
            "Joaquin Ignacio De la Fuente Lagos 0 minutos 3 segundos\n",
            "Gracias Carla\n",
            "Yeah.\n",
        ]
        bundle = load_bundle([ENGINE])
        fixed, _ = apply_mishear_fixes_to_lines(
            lines,
            bundle.rules,
            known_speakers=build_known_speakers(lines, min_count=1),
            min_confidence="alta",
        )
        self.assertEqual(fixed[4], "ya.\n")
        self.assertEqual(fixed[0], lines[0], "la cabecera de hablante se preserva")

if __name__ == "__main__":
    unittest.main()
