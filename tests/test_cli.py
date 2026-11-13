"""Guardas de la CLI.

Existen porque un error de sintaxis en `cli.py` paso la suite completa sin que
nadie lo notara: ningun test lo importaba. Importar el modulo y construir el
parser es barato y cierra ese hueco.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tgd.cli import DEFAULT_ENGINE, build_arg_parser
from tgd.models import CONFIDENCE_LEVELS


class ArgParserTests(unittest.TestCase):
    def setUp(self):
        self.ap = build_arg_parser()

    def test_module_imports_and_parser_builds(self):
        self.assertIsNotNone(self.ap)

    def test_engine_layer_defaults_to_the_shipped_dictionary(self):
        self.assertTrue(os.path.exists(DEFAULT_ENGINE), "el diccionario del motor debe venir en el paquete")
        args = self.ap.parse_args(["t.txt"])
        self.assertEqual(args.engine, DEFAULT_ENGINE)

    def test_domain_is_repeatable(self):
        args = self.ap.parse_args(["t.txt", "--domain", "a.json", "--domain", "b.json"])
        self.assertEqual(args.domain, ["a.json", "b.json"])

    def test_fix_defaults_to_the_strictest_confidence(self):
        args = self.ap.parse_args(["t.txt", "--fix"])
        self.assertTrue(args.fix)
        self.assertEqual(args.min_confidence, "alta", "reescribir con suposiciones nunca es el default")

    def test_every_confidence_level_is_accepted(self):
        for level in CONFIDENCE_LEVELS:
            args = self.ap.parse_args(["t.txt", "--min-confidence", level])
            self.assertEqual(args.min_confidence, level)

    def test_dump_defaults_to_text(self):
        args = self.ap.parse_args(["t.txt", "--dump"])
        self.assertTrue(args.dump)
        self.assertEqual(args.dump_format, "text")
        self.assertIsNone(args.dump_output)

    def test_dump_accepts_json(self):
        args = self.ap.parse_args(["t.txt", "--dump", "--dump-format", "json"])
        self.assertEqual(args.dump_format, "json")

    def test_legacy_flags_still_map_to_the_new_ones(self):
        args = self.ap.parse_args(
            ["t.txt", "--fix-known-mishears", "--mishear-dict", "d.json", "--lint-mishear"]
        )
        self.assertTrue(args.fix, "--fix-known-mishears sigue activando --fix")
        self.assertIn("d.json", args.domain, "--mishear-dict sigue cargando una capa de dominio")
        self.assertTrue(args.lint, "--lint-mishear sigue activando --lint")


if __name__ == "__main__":
    unittest.main()
