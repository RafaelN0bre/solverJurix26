# Prompt — preencher a coluna "Consolidação" (Izabela)

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

### 1. FATOS RELEVANTES

- **Recorrente** → lista de 5 itens, um por linha (bullets):
    - `Fuga do preso`
    - `Lapso temporal de 3 meses`
    - `Ato de terceiro`
    - `Morte da Vítima`
    - `Danos à vítima/familia`
- **Recorrido** → lista de 2 itens, um por linha (bullets):
    - `Fuga do preso`
    - `Danos à vítima/família`
- **Marco Aurélio** → lista de 6 itens, um por linha (bullets):
    - `Latrocínio`
    - `Regime prisional`
    - `Prática de crime`
    - `Morte da vítima`
    - `Dano`
    - `Ato de terceiro`
- **Edson Fachin** → *(VAZIO — não preencher, apenas reportar)*
- **Alexandre de Moraes** → *(VAZIO — não preencher, apenas reportar)*

### 2. CAUSAS FÁTICAS CANDIDATAS

- **Recorrente** → lista de 2 itens, um por linha (bullets):
    - `Prática de crime`
    - `Lapso temporal de 3 meses`
- **Recorrido** → `Fuga do preso`
- **Marco Aurélio** → `Fuga do preso`
- **Edson Fachin** → `Fuga do preso`
- **Alexandre de Moraes** → lista de 4 itens, um por linha (bullets):
    - `Fuga do preso`
    - `Prática de crime`
    - `Lapso temporal de 3 meses`
    - `Formação de quadrilha`

### 3. CAUSAS JURIDICAMENTE RELEVANTES

- **Recorrente** → `Ato de terceiro`
- **Recorrido** → lista de 2 itens, um por linha (bullets):
    - `Omissão estatal`
    - `Dever específico de custódia`
- **Marco Aurélio** → lista de 3 itens, um por linha (bullets):
    - `Omissão estatal`
    - `Dever específico de custódia`
    - `Nexo casual`
- **Edson Fachin** → lista de 2 itens, um por linha (bullets):
    - `Omissão estatal`
    - `Dever específico de custódia`
- **Alexandre de Moraes** → `Ato de terceiro`

### 4. TEORIA JURÍDICA

- **Recorrente** → `Responsabilidade objetiva`
- **Recorrido** → lista de 2 itens, um por linha (bullets):
    - `Responsabilidade objetiva`
    - `Ato de serviço`
- **Marco Aurélio** → lista de 2 itens, um por linha (bullets):
    - `Responsabilidade objetiva`
    - `Ato de serviço`
- **Edson Fachin** → lista de 2 itens, um por linha (bullets):
    - `Responsabilidade objetiva`
    - `Omissão própria`
- **Alexandre de Moraes** → lista de 2 itens, um por linha (bullets):
    - `Responsabilidade objetiva`
    - `Teoria do dano direto e imediato`

### 5. NEXO CAUSAL

- **Recorrente** → lista de 2 itens, um por linha (bullets):
    - `Interrupção do nexo causal`
    - `Novo nexo causal`
- **Recorrido** → lista de 2 itens, um por linha (bullets):
    - `Nexo causal`
    - `Nexo causal direto`
- **Marco Aurélio** → lista de 2 itens, um por linha (bullets):
    - `Nexo causal`
    - `Nexo causal direto`
- **Edson Fachin** → lista de 2 itens, um por linha (bullets):
    - `Nexo causal`
    - `Nexo causal direto`
- **Alexandre de Moraes** → lista de 2 itens, um por linha (bullets):
    - `Interrupção do nexo causal`
    - `Novo nexo causal`

### 7.2. DIVERGÊNCIAS — Posturas

- **Recorrente** → lista de 3 itens, um por linha (bullets):
    - `Ausência de responsabilidade do Estado`
    - `Ato de terceiro como causa do resultado`
    - `Rompimento do nexo causal`
- **Recorrido** → lista de 3 itens, um por linha (bullets):
    - `Responsabilidade do Estado`
    - `Responsabilidade por omissão específica`
    - `Manutenção do nexo causal`
- **Marco Aurélio** → lista de 3 itens, um por linha (bullets):
    - `Responsabilidade do Estado`
    - `Responsabilidade por omissão específica`
    - `Manutenção do nexo causal`
- **Edson Fachin** → lista de 3 itens, um por linha (bullets):
    - `Responsabilidade do Estado`
    - `Responsabilidade por omissão específica`
    - `Manutenção do nexo causal`
- **Alexandre de Moraes** → lista de 3 itens, um por linha (bullets):
    - `Ausência de responsabilidade do Estado`
    - `Ato de terceiro como causa do resultado`
    - `Rompimento do nexo causal`

## Campos livres (fora das tabelas)
- **6. CENÁRIOS CAUSAIS** → *(VAZIO no documento de origem — não preencher, apenas reportar)*
- **7.1. DIVERGÊNCIAS — Pontos de divergência** → *(VAZIO no documento de origem — não preencher, apenas reportar)*

## Saída esperada

1. O documento com a coluna Consolidação preenchida.
2. O relatório final descrito na regra 7.

Não escreva nenhum comentário, justificativa ou análise jurídica além disso.
