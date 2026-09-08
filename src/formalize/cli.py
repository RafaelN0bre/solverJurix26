"""Command line for the formalization pipeline.

    uv run python scripts/translate_dossier.py --input data/<anotador>/<caso>.json
    uv run python scripts/translate_dossier.py --all --dry-run
    uv run python scripts/run_translated.py case-005

`--dry-run` renders every prompt and the normalized brief without calling the
model -- the cheap way to review a prompt edit before spending tokens.
"""
import argparse
import logging
import os
import sys

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .gemini import GeminiClient
from .pipeline import DEFAULT_OUT_DIR, formalize_dossier
from .stages import StageError
from .validate import ValidationReport

AGREEMENT_GLYPH = {"match": "OK ", "mismatch": "DIV", "indefinido": " ? "}


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv is a declared dependency
        return
    load_dotenv()


def _parse_prompt_versions(values: Optional[Sequence[str]]) -> Dict[str, int]:
    versions: Dict[str, int] = {}
    for item in values or []:
        stage, _, version = item.partition("=")
        if not version.isdigit():
            raise SystemExit(f"--prompt-version espera 'estagio=N', recebeu {item!r}")
        versions[stage.strip()] = int(version)
    return versions


def discover_dossiers(data_dir: Path, out_dir: Path) -> List[Path]:
    """Every dossier JSON under `data_dir`, skipping the pipeline's own output."""
    out_dir = out_dir.resolve()
    found = []
    for path in sorted(data_dir.rglob("*.json")):
        if out_dir in path.resolve().parents or path.resolve() == out_dir:
            continue
        found.append(path)
    return found


def print_comparison(report: ValidationReport, stream=sys.stdout) -> None:
    """The solver-vs-court table, as the terminal version of what the
    interface shows in the formalization fiche."""
    if not report.comparison:
        print("Nenhuma pergunta causal avaliada.", file=stream)
        return
    print("\nSolver × decisão da corte", file=stream)
    print(f"{'':4} {'φ':<14} {'ψ':<14} {'NESS':<5} {'but-for':<8} "
          f"{'relev.':<7} {'corte':<13}", file=stream)
    for row in report.comparison:
        def mark(value):
            return "—" if value is None else ("sim" if value else "não")
        print(
            f"{AGREEMENT_GLYPH.get(row['agreement'], '   '):4} "
            f"{row['phi']:<14} {row['psi']:<14} {mark(row['ness']):<5} "
            f"{mark(row['but_for']):<8} "
            f"{mark(row['legally_relevant']):<7} {row['court_verdict']:<13}",
            file=stream,
        )
    counts = report.summary.get("agreement", {})
    rate = report.summary.get("agreement_rate")
    print(
        f"\nConcordância: {counts.get('match', 0)} de "
        f"{counts.get('match', 0) + counts.get('mismatch', 0)} perguntas decididas"
        + (f" ({rate:.0%})" if rate is not None else "")
        + f"; {counts.get('indefinido', 0)} não decidida(s) pela corte.",
        file=stream,
    )


def print_report(report: ValidationReport, stream=sys.stdout) -> None:
    for warning in report.warnings:
        print(f"aviso  {warning.render()[2:]}", file=stream)
    for error in report.errors:
        print(f"ERRO   {error.render()[2:]}", file=stream)
    print_comparison(report, stream)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="translate_dossier",
        description="Formaliza dossiês anotados como frameworks ASPIC+ executáveis.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", "-i", type=Path, help="Arquivo JSON do dossiê.")
    source.add_argument("--all", action="store_true",
                        help="Processa todos os dossiês encontrados em --data-dir.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"),
                        help="Onde procurar dossiês com --all (padrão: data).")
    parser.add_argument("--out", "-o", type=Path, default=DEFAULT_OUT_DIR,
                        help=f"Diretório de saída (padrão: {DEFAULT_OUT_DIR}).")
    parser.add_argument("--model", help="Força um modelo em todos os estágios, "
                        "acima do `model:` declarado em cada prompt.")
    parser.add_argument("--prompt-version", action="append", metavar="ESTAGIO=N",
                        help="Fixa a versão de um prompt, ex.: --prompt-version rules=2.")
    parser.add_argument("--prompts-dir", type=Path,
                        help="Diretório alternativo de prompts.")
    parser.add_argument("--max-repairs", type=int, default=2,
                        help="Tentativas de reparo por estágio (padrão: 2).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Renderiza brief e prompts sem chamar o modelo.")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignora o cache de respostas em disco.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Log em DEBUG.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    _load_env()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    # The solver logs one line per framework it builds; the counterfactual
    # tests build dozens, which would bury the pipeline's own output.
    logging.getLogger("ASPIC+").setLevel(logging.WARNING)

    versions = _parse_prompt_versions(args.prompt_version)
    targets = ([args.input] if args.input
               else discover_dossiers(args.data_dir, args.out))
    if not targets:
        print(f"Nenhum dossiê encontrado em {args.data_dir}.", file=sys.stderr)
        return 1

    client = None
    if not args.dry_run:
        client = GeminiClient(
            model_override=args.model,
            default_model=os.environ.get("GEMINI_MODEL"),
            use_cache=not args.no_cache,
        )

    failures = 0
    for path in targets:
        print(f"\n=== {path} ===")
        try:
            result = formalize_dossier(
                path,
                client=client,
                out_dir=args.out,
                prompt_versions=versions,
                prompts_dir=args.prompts_dir,
                max_repairs=args.max_repairs,
                dry_run=args.dry_run,
            )
        except StageError as exc:
            failures += 1
            print(f"FALHA no estágio {exc.stage}:\n{exc}", file=sys.stderr)
            continue
        except Exception as exc:  # noqa: BLE001 - one bad dossier must not stop the batch
            failures += 1
            print(f"FALHA: {exc}", file=sys.stderr)
            continue

        if result.dry_run:
            print(f"Brief e prompts escritos em {result.run_dir}")
            continue

        print(f"Caso formalizado: {result.case.case.id} "
              f"({len(result.case.atoms)} átomos, {len(result.case.rules_meta)} regras, "
              f"{len(result.case.queries)} perguntas)")
        print(f"Artefatos: {result.run_dir}")
        if result.usage:
            print("Tokens: " + ", ".join(f"{k}={v}" for k, v in sorted(result.usage.items())))
        print_report(result.report)
        if not result.report.ok:
            failures += 1

    return 1 if failures else 0
