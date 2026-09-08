#!/usr/bin/env python3
"""Re-executa o solver sobre um caso já formalizado, sem chamar o LLM.

    uv run python scripts/run_translated.py            # todos os casos
    uv run python scripts/run_translated.py case-005   # um caso

Reconstrói os dois frameworks a partir de `data/translated/<caso>/case.json`,
recalcula os vereditos, regrava `case.json` e `validation.json` e imprime a
tabela solver × corte. É o laço barato para iterar depois de editar o solver ou
de ajustar um `case.json` à mão -- e o jeito de detectar que uma mudança no
solver alterou o resultado de uma formalização já publicada.
"""
import argparse
import json
import logging
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from formalize import build  # noqa: E402
from formalize.cli import print_report  # noqa: E402
from formalize.pipeline import DEFAULT_OUT_DIR, _update_index  # noqa: E402
from formalize.schema import FormalizedCase  # noqa: E402
from formalize.validate import validate_case  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case_id", nargs="*", help="Ids de caso (padrão: todos).")
    parser.add_argument("--dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--check", action="store_true",
                        help="Não regrava nada; sai com 1 se houver erro de validação.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("ASPIC+").setLevel(logging.WARNING)

    files = sorted(args.dir.glob("*/case.json"))
    if args.case_id:
        wanted = set(args.case_id)
        files = [f for f in files if f.parent.name in wanted]
    if not files:
        print(f"Nenhum caso formalizado em {args.dir}.", file=sys.stderr)
        return 1

    failures = 0
    for case_file in files:
        case = FormalizedCase.model_validate_json(case_file.read_text(encoding="utf-8"))
        print(f"\n=== {case.case.id} — {case.case.title} ===")
        annotated = build.annotate(case)
        report = validate_case(annotated)
        print_report(report)
        if not args.check:
            case_file.write_text(
                json.dumps(annotated.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8")
            (case_file.parent / "validation.json").write_text(
                json.dumps(report.as_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8")
        if not report.ok:
            failures += 1
    if not args.check:
        _update_index(args.dir)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
