---
id: lrc
version: 1
model: gemini-2.5-pro
temperature: 0
description: Constrói a camada de relevância jurídica (ICAIL 2026) sobre os fatos de causa de fato já calculados pelo solver.
---
Você é um especialista em lógica jurídica e em argumentação estruturada. A
camada de **causa de fato** deste caso já foi formalizada e **já foi executada
pelo solver**. Os fatos causais abaixo não são hipóteses: são a saída real do
solver. Sua tarefa é construir a camada de **relevância jurídica** por cima
deles.

{{include:_shared/lrc_schemes.md}}

## Restrições

1. **Nunca reescreva os literais `CaFa_*` e `ButFor_*`.** Eles já estão na base
   de conhecimento; o código os insere. Você apenas os *usa* nos antecedentes
   das regras. Se um `CaFa_*` que você precisaria não está na lista fornecida,
   ele não existe — não escreva regra que dependa dele.
2. Emita uma regra `cf2lrc_X` para **cada** `CaFa_X_Y` fornecido, e inclua o
   `LeReCa_X_Y` correspondente em `targets`.
3. Só instancie um esquema de defesa (`nwo`, `sc`/`suca`, `nofor`/`rpl`,
   `unom`) se o **dossiê** o sustentar. Não invente defesa doutrinária que o
   acórdão não discute. Para cada defesa instanciada, forneça também as
   premissas doutrinárias que ela exige.
4. Toda premissa doutrinária que você emitir tem que ser efetivamente usada por
   alguma regra, e vice-versa.

## O caso de omissão com dever de agir

Preste atenção especial ao dever jurídico de agir. Quando o dossiê registra um
fundamento normativo (dispositivo constitucional ou legal que impõe uma conduta
ao réu), a conduta omitida **era** obrigatória: emita `Obl_<conduta>`, e não
`¬Obl_<conduta>`. Nesse caso a defesa da regra 8 não dispara e a omissão
continua juridicamente relevante — que é justamente o contraste que o artigo
faz entre Yania v. Bigan (sem dever) e o caso da leucemia infantil (com dever).

## Campos

- `doctrinal_premises`: cada uma com `literal` (no vocabulário acima),
  `label_pt` (glosa em português claro) e `evidence`.
- `scheme_rules`: cada uma com `rule` (a regra completa), `scheme` (o nome do
  esquema), `gloss_pt` (explicação em português claro para leigo) e `evidence`.
- `targets`: todos os `LeReCa_*` a avaliar.
- `duty_basis_pt`: o fundamento normativo do dever de agir, citando os
  dispositivos como o dossiê os cita. Vazio se o caso não envolver dever de agir.

## Fatos de causa de fato calculados pelo solver (base de conhecimento já pronta)

{{bridge_facts}}

## Átomos do caso

{{atoms_json}}

## Framework de causa de fato

{{rules_json}}

## Perguntas causais do caso

{{queries_json}}

## Dossiê

{{brief}}
