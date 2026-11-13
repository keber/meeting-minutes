"""Tests del parser de transcripciones de Teams.

Los casos vienen de dos corpus con forma distinta: el proyecto de exportacion escribe los
nombres capitalizados ("Joaquin Ignacio De la Fuente Lagos") y el proyecto de planta
en mayusculas ("TOMAS ESTEBAN ROJO PARDO"). El parser tiene que servir a los
dos sin que el proyecto tenga que configurarlo.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tgd.parser import (
    build_known_speakers,
    extract_events,
    is_name_like,
    is_pure_timestamp_line,
    parse_timestamp,
)


class NameDetectionTests(unittest.TestCase):
    def test_capitalised_name_is_a_name(self):
        self.assertTrue(is_name_like("Joaquin Ignacio De la Fuente Lagos"))

    def test_uppercase_name_is_a_name(self):
        """El proyecto de planta transcribe los nombres en mayusculas."""
        self.assertTrue(is_name_like("TOMAS ESTEBAN ROJO PARDO"))
        self.assertTrue(is_name_like("DANIELA PAZ OLIVARES MENA"))

    def test_connectors_still_count(self):
        self.assertTrue(is_name_like("Joaquin De la Fuente"))

    def test_sentence_is_not_a_name(self):
        self.assertFalse(is_name_like("Eso es borrar la base de datos"))
        self.assertFalse(is_name_like("Sí, exacto"))

    def test_line_with_digits_is_not_a_name(self):
        self.assertFalse(is_name_like("TOMAS ESTEBAN ROJO PARDO 0 minutos 7 segundos"))


class SpokenClockTimeTests(unittest.TestCase):
    """Una hora dicha en voz alta no es un timestamp de la reunion."""

    LINE = "todos todos entraron a las 7:30 casi todos Mira cambió el minuto pero no no"

    def test_spoken_time_inside_a_sentence_is_not_a_timestamp(self):
        self.assertIsNone(parse_timestamp(self.LINE))

    def test_the_word_minuto_alone_does_not_authorise_a_timestamp(self):
        """El guard aceptaba cualquier linea que contuviera 'minuto'."""
        self.assertIsNone(parse_timestamp("Claro, casi por 1 minuto nomás, eran las 7:30 recién"))

    def test_teams_pure_timestamp_still_parses(self):
        self.assertEqual(parse_timestamp("0 minutos 3 segundos0:03"), 3)
        self.assertEqual(parse_timestamp("2 minutos2:00"), 120)
        self.assertEqual(parse_timestamp("3:49"), 229)

    def test_teams_speaker_header_still_parses(self):
        self.assertEqual(
            parse_timestamp("TOMAS ESTEBAN ROJO PARDO 0 minutos 7 segundos"), 7
        )

    def test_pure_timestamp_line_detection(self):
        self.assertTrue(is_pure_timestamp_line("0 minutos 3 segundos0:03"))
        self.assertFalse(is_pure_timestamp_line("TOMAS ESTEBAN ROJO PARDO 0 minutos 7 segundos"))


class UppercaseCorpusTests(unittest.TestCase):
    """Bloque con la forma del corpus del proyecto de planta (nombres ficticios)."""

    LINES = [
        "Transcripción Proyecto Planta nuevas funcionalidades\n",
        "\n",
        "T\n",
        "\n",
        "TOMAS ESTEBAN ROJO PARDO\n",
        "0 minutos 7 segundos0:07\n",
        "TOMAS ESTEBAN ROJO PARDO 0 minutos 7 segundos\n",
        "Le voy a visitar.\n",
        "D\n",
        "\n",
        "DANIELA PAZ OLIVARES MENA\n",
        "0 minutos 20 segundos0:20\n",
        "DANIELA PAZ OLIVARES MENA 0 minutos 20 segundos\n",
        "Mhm.\n",
    ]

    def test_uppercase_speakers_are_learned(self):
        speakers = build_known_speakers(self.LINES, min_count=1)
        self.assertIn("TOMAS ESTEBAN ROJO PARDO", speakers)
        self.assertIn("DANIELA PAZ OLIVARES MENA", speakers)

    def test_the_name_line_does_not_leak_into_the_spoken_text(self):
        events = extract_events(self.LINES)
        joined = " ".join(e.text for e in events)
        self.assertNotIn("DANIELA PAZ OLIVARES MENA", joined)
        self.assertIn("Le voy a visitar.", joined)

    def test_no_time_travel_in_a_clean_block(self):
        events = extract_events(self.LINES)
        times = [e.t for e in events]
        self.assertEqual(times, sorted(times), "los timestamps no pueden retroceder")


if __name__ == "__main__":
    unittest.main()
