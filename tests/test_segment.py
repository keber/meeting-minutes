"""Tests de la segmentacion en bloques tematicos (modo dump)."""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tgd.models import Event, Person
from tgd.segment import blocks_to_json, blocks_to_text, build_blocks

PEOPLE = [
    Person(canonical="Martin Nunez Saez", display="Martín Núñez Sáez", aliases=("Martin",), role="PO"),
    Person(canonical="Katia Rojas Vera", display="Katia Rojas Vera", aliases=("Catia Rojas Vera",), role="DEV"),
]


def ev(line_no, t, speaker, text):
    return Event(line_no=line_no, t=t, speaker=speaker, text=text)


class BuildBlocksTests(unittest.TestCase):
    def test_consecutive_turns_of_same_speaker_merge(self):
        events = [
            ev(10, 0, "Martin Nunez Saez", "Primera frase."),
            ev(14, 5, "Martin Nunez Saez", "Segunda frase."),
            ev(18, 9, "Katia Rojas Vera", "Respuesta."),
        ]
        blocks = build_blocks(events, PEOPLE)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].text, "Primera frase. Segunda frase.")
        self.assertEqual(blocks[1].text, "Respuesta.")

    def test_block_keeps_the_timestamp_of_its_first_turn(self):
        events = [
            ev(10, 7, "Martin Nunez Saez", "Arranca aca."),
            ev(14, 19, "Martin Nunez Saez", "Sigue."),
        ]
        blocks = build_blocks(events, PEOPLE)
        self.assertEqual(blocks[0].t, 7, "el timestamp del bloque es el de su primer turno")

    def test_line_range_spans_the_merged_turns(self):
        events = [
            ev(10, 0, "Martin Nunez Saez", "Uno."),
            ev(25, 5, "Martin Nunez Saez", "Dos."),
        ]
        blocks = build_blocks(events, PEOPLE)
        self.assertEqual((blocks[0].line_start, blocks[0].line_end), (10, 25))

    def test_events_without_text_are_skipped(self):
        events = [
            ev(10, 0, "Martin Nunez Saez", "Con texto."),
            ev(12, 3, "Katia Rojas Vera", "   "),
            ev(15, 6, "Martin Nunez Saez", "Mas texto."),
        ]
        blocks = build_blocks(events, PEOPLE)
        self.assertEqual(len(blocks), 1, "el turno vacio no corta el bloque ni genera uno propio")
        self.assertEqual(blocks[0].text, "Con texto. Mas texto.")

    def test_speaker_display_is_resolved_from_the_overlay(self):
        blocks = build_blocks([ev(10, 0, "Martin Nunez Saez", "Hola.")], PEOPLE)
        self.assertEqual(blocks[0].speaker, "Martin Nunez Saez", "se conserva el nombre crudo")
        self.assertEqual(blocks[0].display, "Martín Núñez Sáez", "y se agrega el resuelto")

    def test_unknown_speaker_keeps_its_raw_name(self):
        blocks = build_blocks([ev(10, 0, "Persona Desconocida", "Hola.")], PEOPLE)
        self.assertEqual(blocks[0].display, "Persona Desconocida")

    def test_no_events_gives_no_blocks(self):
        self.assertEqual(build_blocks([], PEOPLE), [])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.blocks = build_blocks(
            [
                ev(10, 63, "Martin Nunez Saez", "Dale unas 4 horas."),
                ev(20, 130, "Katia Rojas Vera", "Listo."),
            ],
            PEOPLE,
        )

    def test_text_render_carries_timestamp_and_display_name(self):
        out = blocks_to_text(self.blocks).splitlines()
        self.assertEqual(out[0], "[1:03] Martín Núñez Sáez: Dale unas 4 horas.")
        self.assertEqual(out[1], "[2:10] Katia Rojas Vera: Listo.")

    def test_json_render_is_parseable_and_keeps_both_names(self):
        data = json.loads(blocks_to_json(self.blocks))
        self.assertEqual(len(data["blocks"]), 2)
        first = data["blocks"][0]
        self.assertEqual(first["t"], 63)
        self.assertEqual(first["timestamp"], "1:03")
        self.assertEqual(first["speaker"], "Martin Nunez Saez")
        self.assertEqual(first["display"], "Martín Núñez Sáez")
        self.assertEqual(first["lineStart"], 10)
        self.assertEqual(data["blockCount"], 2)

    def test_json_is_utf8_not_escaped(self):
        """La skill lee esto; los nombres deben quedar legibles, no como \\uXXXX."""
        self.assertIn("Martín", blocks_to_json(self.blocks))


if __name__ == "__main__":
    unittest.main()
