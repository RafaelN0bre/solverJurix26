import json, sys
src, dst, autor = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(src))

L = []
for s in d['secoes']:
    if s['tipo'] != 'tabela_por_perspectiva':
        continue
    L.append(f"\n### {s['id']}. {s['titulo']}\n")
    for p in d['perspectivas']:
        itens = [i for i in s.get('consolidacao_itens_por_perspectiva', {}).get(p, []) if i.strip()]
        if not itens:
            L.append(f"- **{p}** → *(VAZIO — não preencher, apenas reportar)*")
        elif len(itens) == 1:
            L.append(f"- **{p}** → `{itens[0]}`")
        else:
            L.append(f"- **{p}** → lista de {len(itens)} itens, um por linha (bullets):")
            for it in itens:
                L.append(f"    - `{it}`")
valores = "\n".join(L)

livres = [s for s in d['secoes'] if s['tipo'] == 'campo_livre']
livres_txt = "\n".join(
    f"- **{s['id']}. {s['titulo']}** → *(VAZIO no documento de origem — não preencher, apenas reportar)*"
    for s in livres)

prompt = f"""# Prompt — preencher a coluna "Consolidação" ({autor})

Você é um assistente de transcrição de dados. Sua tarefa é **copiar** valores já
prontos para as células corretas de um documento. Você **não** redige, resume,
interpreta nem melhora nenhum texto.

## Contexto

O documento anexado é um "Documento de Consolidação de Anotação Jurídica" sobre o
caso de responsabilidade civil do Estado por crime cometido por detento foragido.
Ele contém várias seções; em cada uma há uma tabela com estas colunas:

| PERSPECTIVA | Izabela | Vítor | Andressa | **Consolidação** |

As linhas da tabela são sempre as cinco perspectivas, nesta ordem:
Recorrente, Recorrido, Marco Aurélio, Edson Fachin, Alexandre de Moraes.

## Tarefa

Preencha **exclusivamente** a última coluna (**Consolidação** / **Consolidado**)
de cada tabela, usando os valores da lista "VALORES A INSERIR" abaixo.

Para cada valor: localize a **seção** pelo título e, dentro dela, a **linha** pela
perspectiva; escreva o valor na célula da coluna Consolidação dessa linha.

## Regras obrigatórias

1. **Transcrição literal.** Copie o valor exatamente como está, incluindo
   pontuação, parênteses e maiúsculas. Não reescreva, não resuma, não expanda,
   não corrija estilo, não traduza.
2. **Preserve o formato de lista.** Quando o valor estiver marcado como "lista de
   N itens", escreva cada item em uma linha própria dentro da mesma célula
   (bullets), na ordem indicada. Não junte os itens em uma frase corrida.
3. **Uma célula por par (seção, perspectiva).** Não replique um valor em outra
   linha nem em outra seção.
4. **Não altere mais nada.** As colunas Izabela, Vítor e Andressa, os títulos, os
   comandos, os vocabulários mínimos e a formatação do documento permanecem
   intactos.
5. **Células marcadas como VAZIO ficam vazias.** Não invente conteúdo, não deduza
   a partir das outras colunas, não copie de outra perspectiva.
6. **Se uma seção ou perspectiva não existir no documento**, não crie linha nem
   seção nova — apenas registre a pendência no relatório final.
7. Ao terminar, produza um **relatório** com: (a) quantas células foram
   preenchidas; (b) a lista das células deixadas em branco; (c) qualquer seção ou
   linha que você não conseguiu localizar.

## VALORES A INSERIR
{valores}

## Campos livres (fora das tabelas)
{livres_txt}

## Saída esperada

1. O documento com a coluna Consolidação preenchida.
2. O relatório final descrito na regra 7.

Não escreva nenhum comentário, justificativa ou análise jurídica além disso.
"""
open(dst, 'w').write(prompt)
print(f"escrito: {dst}")
