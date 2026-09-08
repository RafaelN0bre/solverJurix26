#!/usr/bin/env python3
"""Consolida as três consolidações dos anotadores numa só.

    uv run python scripts/build_consolidacao_main.py
    uv run python scripts/build_consolidacao_main.py --dry-run   # só mostra o prompt
    uv run python scripts/build_consolidacao_main.py --no-cache  # ignora o cache em disco

Lê `data/<anotador>/consolidacao.json` — um por anotador, cada um com a sua
proposta de consolidação das mesmas 8 seções × 5 perspectivas — e grava
`data/consolidacao-main.json` com uma célula canônica por par, dizendo quais
anotadores a sustentam, se a divergência era de conteúdo ou só de redação, e
por que a escolha foi essa.

Existe porque o pipeline antes escolhia *uma* das três anotações por acidente
de ordenação alfabética (`aspic.catalog.dossier_paths` ficava com a da
Andressa), e as outras duas não entravam em lugar nenhum.
"""
import argparse
import json
import logging
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

from formalize import consolidate  # noqa: E402
from formalize.gemini import GeminiClient  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=consolidate.DEFAULT_DATA_ROOT)
    parser.add_argument("--out", type=Path, default=consolidate.DEFAULT_OUTPUT)
    parser.add_argument("--model", default=None, help="Sobrescreve o modelo do prompt.")
    parser.add_argument("--version", type=int, default=None, help="Versão do prompt.")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Renderiza e imprime o prompt, sem chamar o modelo.")
    args = parser.parse_args(argv)

    load_dotenv(REPO_ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    documents = consolidate.load_consolidations(args.root)
    if not documents:
        print(f"Nenhum {consolidate.CONSOLIDATION_FILE} em {args.root}/*/", file=sys.stderr)
        return 1
    material = consolidate.cells(documents)
    divergentes = sum(1 for c in material if c.divergem)
    print(f"{len(documents)} anotador(es): {', '.join(sorted(documents))}")
    print(f"{len(material)} células — {divergentes} com propostas divergentes, "
          f"{sum(1 for c in material if c.vazia)} vazias nas três.")

    if args.dry_run:
        print("\n" + "=" * 70)
        print(consolidate.build_prompt(material, version=args.version).text)
        return 0

    client = GeminiClient(model_override=args.model, use_cache=not args.no_cache)
    record, problemas = consolidate.build(client, root=args.root, version=args.version)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGravado {args.out.relative_to(REPO_ROOT)}")

    resumo = record["resumo"]
    print(f"  {resumo['celulas']} células; "
          f"{resumo['divergencia_substantiva']} com divergência substantiva.")
    for entrada in record["celulas"]:
        if entrada["divergencia_substantiva"]:
            onde = f"§{entrada['secao_id']} {entrada['secao']}"
            if entrada["perspectiva"]:
                onde += f" / {entrada['perspectiva']}"
            print(f"    ⚠ {onde}: {entrada['justificativa']}")

    if problemas:
        print("\nProblemas na resposta do modelo:", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
