from __future__ import annotations

import argparse
import os
import re
import sys
from typing import List, Optional

from .analysis import analyze
from .fix import apply_mishear_fixes_to_lines, known_speakers_from_lines, resolve_speaker
from .lints import lint_mishear, lint_suspect_mishear
from .mishear_config import load_bundle
from .models import CONFIDENCE_LEVELS, DictionaryBundle
from .parser import extract_events
from .segment import blocks_to_json, blocks_to_text, build_blocks
from .utils import format_time

PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ENGINE = os.path.join(PACKAGE_ROOT, "data", "engine-artifacts.json")


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Limpia una transcripcion de Teams y reporta gaps y sospechas. "
            "Trabaja en dos capas: artefactos universales del motor de transcripcion "
            "y vocabulario de dominio del proyecto."
        )
    )
    ap.add_argument("input", help="Ruta del archivo .txt/.md con la transcripcion")

    layers = ap.add_argument_group("capas de diccionario")
    layers.add_argument(
        "--engine",
        default=DEFAULT_ENGINE,
        help="Diccionario del motor de transcripcion (default: data/engine-artifacts.json del paquete)",
    )
    layers.add_argument(
        "--domain",
        action="append",
        default=[],
        metavar="RUTA",
        help="Overlay de dominio del proyecto. Repetible; la ultima capa gana sobre el mismo id.",
    )
    layers.add_argument(
        "--no-engine",
        action="store_true",
        help="Omite la capa del motor y usa solo los overlays de dominio",
    )

    fixing = ap.add_argument_group("correccion")
    fixing.add_argument(
        "--fix",
        action="store_true",
        help="Escribe una copia corregida; el archivo original nunca se modifica",
    )
    fixing.add_argument(
        "--min-confidence",
        choices=CONFIDENCE_LEVELS,
        default="alta",
        help=(
            "Umbral de confianza para aplicar reglas con --fix (default: alta). "
            "Bajarlo reescribe la transcripcion con suposiciones: usar solo tras revisar el lint."
        ),
    )
    fixing.add_argument("--output", default=None, help="Ruta de salida (default: <input>.fixed.txt)")

    gaps = ap.add_argument_group("analisis de gaps")
    gaps.add_argument("--min-silence", type=int, default=10, help="Silencio normal en segundos (default 10)")
    gaps.add_argument("--suspicious-silence", type=int, default=30, help="Umbral de sospecha en segundos (default 30)")
    gaps.add_argument("--wps", type=float, default=2.2, help="Palabras por segundo estimadas (default 2.2)")
    gaps.add_argument("--factor", type=float, default=1.8, help="Tolerancia: delta > esperado*factor (default 1.8)")
    gaps.add_argument("--overhead", type=float, default=2.0, help="Segundos extra por cambio de turno (default 2.0)")
    gaps.add_argument("--show-prev-text", action="store_true", help="Muestra el texto previo al gap")

    linting = ap.add_argument_group("lint")
    linting.add_argument("--lint", action="store_true", help="Reporta reglas que no alcanzan el umbral de --fix")
    linting.add_argument("--lint-suspect", action="store_true", help="Heuristica: tokens en ingles fuera de contexto")
    linting.add_argument(
        "--lint-suspect-wordfreq",
        action="store_true",
        help="Refuerza --lint-suspect con wordfreq, si esta instalado (dependencia opcional)",
    )
    linting.add_argument("--lint-context", type=int, default=1, help="Eventos de contexto prev/next (default 1)")
    linting.add_argument("--lint-max", type=int, default=50, help="Maximo de hallazgos (default 50)")

    dump = ap.add_argument_group("segmentacion")
    dump.add_argument(
        "--dump",
        action="store_true",
        help="Agrupa los turnos consecutivos de cada hablante en bloques tematicos y los escribe a un archivo",
    )
    dump.add_argument(
        "--dump-format",
        choices=("text", "json"),
        default="text",
        help="Formato del dump (default: text). 'json' incluye el rango de lineas de cada bloque.",
    )
    dump.add_argument(
        "--dump-output",
        default=None,
        help="Ruta de salida del dump (default: <input>.blocks.txt o .blocks.json)",
    )

    report = ap.add_argument_group("reportes")
    report.add_argument("--speakers", action="store_true", help="Lista los hablantes detectados y su nombre resuelto")

    # Alias heredados del script original, para no romper comandos existentes.
    ap.add_argument("--fix-known-mishears", dest="fix", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--mishear-dict", dest="domain", action="append", help=argparse.SUPPRESS)
    ap.add_argument("--lint-mishear", dest="lint", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--lint-meshear", dest="lint", action="store_true", help=argparse.SUPPRESS)
    return ap


def _resolve_layers(args) -> List[str]:
    paths: List[str] = []
    if not args.no_engine:
        paths.append(args.engine)
    paths.extend(p for p in (args.domain or []) if p)
    return paths


def _print_bundle_summary(bundle: DictionaryBundle, paths: List[str]) -> None:
    print("== Diccionario ==")
    for p in paths:
        print(f"- capa: {p}")
    counts = {level: 0 for level in CONFIDENCE_LEVELS}
    for rule in bundle.rules:
        counts[rule.confidence] += 1
    detail = " | ".join(f"{lvl}: {counts[lvl]}" for lvl in CONFIDENCE_LEVELS)
    print(f"Reglas cargadas: {len(bundle.rules)} ({detail})")
    if bundle.people:
        print(f"Personas en el overlay: {len(bundle.people)}")
    if bundle.issues:
        print("Observaciones:")
        for issue in bundle.issues:
            print(f"- {issue}")
    print("")


def _force_utf8_stdout() -> None:
    """La consola de Windows usa cp1252 por defecto y revienta al imprimir
    'Delta', tildes o cualquier caracter fuera de ese mapa. El reporte es
    inherentemente UTF-8 (nombres en espanol, simbolos del analisis), asi que
    se fuerza la codificacion en vez de degradar el contenido."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: Optional[List[str]] = None) -> int:
    _force_utf8_stdout()
    args = build_arg_parser().parse_args(argv)

    with open(args.input, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    layer_paths = _resolve_layers(args)
    bundle = load_bundle(layer_paths)

    print(f"Archivo: {args.input}")
    print("")
    _print_bundle_summary(bundle, layer_paths)

    if not bundle.rules:
        print("Aviso: no hay reglas cargadas; la correccion y el lint no haran nada.")
        print("")

    if args.fix:
        known_speakers = known_speakers_from_lines(lines)
        fixed_lines, counts = apply_mishear_fixes_to_lines(
            lines,
            bundle.rules,
            known_speakers=known_speakers,
            min_confidence=args.min_confidence,
        )

        out_path = args.output
        if out_path is None:
            base, ext = os.path.splitext(args.input)
            out_path = base + ".fixed" + (ext or ".txt")

        with open(out_path, "w", encoding="utf-8", errors="replace") as f:
            f.writelines(fixed_lines)

        print("== Correccion ==")
        print(f"Umbral aplicado: {args.min_confidence}")
        print(f"Salida: {out_path}  (el original queda intacto)")
        print(f"Reemplazos aplicados: {sum(counts.values())}")
        for rid, n in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
            print(f"- {rid}: {n}")
        print("")

        lines = fixed_lines

    events = extract_events(lines)
    print(f"Eventos con timestamp: {len(events)}")
    if events:
        print(f"Duracion de la reunion: {format_time(events[-1].t)}")
    print("")

    if args.speakers:
        _report_speakers(events, bundle)

    if args.dump:
        _write_dump(events, bundle, args)

    gaps, issues = analyze(
        events,
        min_silence=args.min_silence,
        suspicious_silence=args.suspicious_silence,
        wps=args.wps,
        factor=args.factor,
        base_overhead=args.overhead,
    )

    if issues:
        print("== Observaciones ==")
        for x in issues:
            print("-", x)
        print("")

    print("== Gaps sospechosos ==")
    if not gaps:
        print("No se detectaron gaps con estos parametros.")
    for g in gaps:
        print("-", g)
        if args.show_prev_text:
            m = re.search(r"\(L(\d+)\)", g)
            if m:
                ev = next((e for e in events if e.line_no == int(m.group(1))), None)
                if ev and ev.text:
                    snippet = ev.text[:500] + ("..." if len(ev.text) > 500 else "")
                    print("  Texto previo:", snippet)
    print("")

    if args.lint:
        _report_lint(events, bundle, args)

    if args.lint_suspect:
        _report_lint_suspect(events, bundle, args)

    return 0


def _write_dump(events, bundle: DictionaryBundle, args) -> None:
    """Escribe la transcripcion segmentada. Es la entrada del paso de
    segmentacion de la skill: cada bloque conserva timestamp, hablante resuelto
    y rango de lineas, de modo que una cita siempre puede volver al original."""
    blocks = build_blocks(events, bundle.people)

    out_path = args.dump_output
    if out_path is None:
        base, _ = os.path.splitext(args.input)
        out_path = f"{base}.blocks.{'json' if args.dump_format == 'json' else 'txt'}"

    rendered = blocks_to_json(blocks) if args.dump_format == "json" else blocks_to_text(blocks)
    with open(out_path, "w", encoding="utf-8", errors="replace") as f:
        f.write(rendered + "\n")

    print("== Segmentacion ==")
    print(f"Bloques: {len(blocks)}  (desde {len(events)} eventos)")
    print(f"Salida: {out_path}")
    print("")


def _report_speakers(events, bundle: DictionaryBundle) -> None:
    print("== Hablantes ==")
    seen: List[str] = []
    for ev in events:
        if ev.speaker and ev.speaker not in seen:
            seen.append(ev.speaker)
    for name in seen:
        display = resolve_speaker(name, bundle.people)
        mark = "" if display == name else f"  ->  {display}"
        print(f"- {name}{mark}")
    print("")


def _report_lint(events, bundle: DictionaryBundle, args) -> None:
    """Reporta solo lo que --fix NO aplica: eso es lo que necesita confirmacion."""
    threshold = CONFIDENCE_LEVELS.index(args.min_confidence)
    pending = [r for r in bundle.rules if CONFIDENCE_LEVELS.index(r.confidence) > threshold]

    print(f"== Lint: reglas por debajo del umbral '{args.min_confidence}' ==")
    if not pending:
        print("No hay reglas pendientes de confirmacion.")
        print("")
        return

    findings = lint_mishear(
        events,
        window=max(0, args.lint_context),
        max_findings=max(1, args.lint_max),
        explicit_patterns=pending,
        goodbye_markers=bundle.goodbye_markers,
    )
    if not findings:
        print("Ninguna coincidio en esta transcripcion.")
    for f in findings:
        print(f)
        print("")
    print("")


def _report_lint_suspect(events, bundle: DictionaryBundle, args) -> None:
    if args.lint_suspect_wordfreq:
        try:
            import importlib

            importlib.import_module("wordfreq")
        except Exception:
            print("Aviso: --lint-suspect-wordfreq pedido pero 'wordfreq' no esta instalado.")
            print("      Es una dependencia opcional: pip install wordfreq")
            print("")

    findings = lint_suspect_mishear(
        events,
        window=max(0, args.lint_context),
        max_findings=max(1, args.lint_max),
        allow_english_terms=bundle.allow_terms,
        use_wordfreq=bool(args.lint_suspect_wordfreq),
    )
    print("== Lint heuristico (tokens en ingles fuera de contexto) ==")
    if not findings:
        print("No se detectaron sospechas con la heuristica actual.")
    for f in findings:
        print(f)
        print("")
    print("")


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
