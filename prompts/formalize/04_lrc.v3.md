---
id: lrc
version: 3
model: gemini-2.5-pro
temperature: 0
description: Constrói a camada de relevância jurídica (ICAIL 2026) sobre os fatos já calculados pelo solver, atribuindo cada defesa à perspectiva que a move.
---
Você é um especialista em lógica jurídica e em argumentação estruturada. A
camada de **causa de fato** deste caso já foi formalizada e **já foi executada
pelo solver**. Os fatos causais abaixo não são hipóteses: são a saída real do
solver. Sua tarefa é construir a camada de **relevância jurídica** por cima
deles.

{{include:_shared/lrc_schemes.md}}

## ⚠️ As defesas doutrinárias chegam inteiras até aqui

A camada de causa de fato **não codifica mais** fato de terceiro, ausência de
dever de agir, imprevisibilidade nem causa paralela não ilícita. Ela responde
apenas o que aconteceu e por qual mecanismo.

Isso muda o peso desta etapa: se o acórdão rejeitou a pretensão por uma dessas
razões, é **aqui** que a rejeição tem que acontecer. Se você não instanciar a
defesa, o caso termina com o solver concordando com a parte que perdeu o
julgamento.

Percorra o dossiê procurando cada uma:

- **causa superveniente / fato de terceiro** → `suca` (a caracterização do
  evento posterior) **e** `sc` (o efeito sobre a causa anterior). São duas
  regras, não uma: sem `suca` o literal `SupersedingCause_*` não existe.
- **omissão sem dever de agir**, ou dever genérico onde se alegava específico
  → `unom`, com `Om_<causa>` e `¬Obl_<conduta>`.
- **resultado imprevisível** → `nofor`; e `rpl` quando o dano é a concretização
  de um risco que a conduta criou.
- **causa paralela não ilícita** que produziria o mesmo dano → `nwo`, com
  `¬Tortious_<causa>`.

## Restrições

1. **Nunca reescreva os literais `CaFa_*` e `ButFor_*`.** Eles já estão na base
   de conhecimento; o código os insere. Você apenas os *usa* nos antecedentes
   das regras. Se um `CaFa_*` que você precisaria não está na lista fornecida,
   ele não existe — não escreva regra que dependa dele.
2. Emita uma regra `cf2lrc_X` para **cada** `CaFa_X_Y` fornecido, e inclua o
   `LeReCa_X_Y` correspondente em `targets`.
3. Só instancie um esquema de defesa se o **dossiê** o sustentar. Não invente
   defesa doutrinária que o acórdão não discute. Para cada defesa instanciada,
   forneça também as premissas doutrinárias que ela exige.
4. Toda premissa doutrinária que você emitir tem que ser efetivamente usada por
   alguma regra, e vice-versa.

## O dever de agir

Preste atenção especial ao dever jurídico de agir. Quando o dossiê registra um
fundamento normativo (dispositivo constitucional ou legal que impõe uma conduta
ao réu), a conduta omitida **era** obrigatória: emita `Obl_<conduta>`, e não
`¬Obl_<conduta>`. Nesse caso a defesa da regra 8 não dispara e a omissão
continua juridicamente relevante — que é justamente o contraste que o artigo
faz entre Yania v. Bigan (sem dever) e o caso da leucemia infantil (com dever).

### Quando as perspectivas divergem sobre a natureza do dever

É o padrão dos casos de responsabilidade do Estado: um lado sustenta um dever
**específico** (custódia, guarda, assistência à saúde do preso) e o outro um
dever **genérico** (segurança pública). O dossiê registra isso como ponto de
divergência, com os lados nomeados. O que a corte acolheu decide qual premissa
você emite:

- prevaleceu o dever **específico** → `Obl_<conduta>`: a regra `unom` não
  dispara, e a omissão permanece juridicamente relevante;
- prevaleceu o dever **genérico** → `¬Obl_<conduta>`: a regra `unom` dispara, e
  a relevância jurídica da omissão cai.

Nos dois casos emita também `Om_<causa>` e a regra `unom_<causa>` — escrita
sempre com `¬Obl_` no antecedente, como manda o vocabulário acima. O que muda
entre os dois cenários é a premissa, nunca a regra.

## Átomos que o estágio 2 deixou para você

Estes átomos foram estabelecidos pelo estágio 1 mas **não** entraram no
framework de causa de fato, porque o estágio 2 os julgou pertinentes à
imputação e não ao mecanismo. Cada um deles tem que reaparecer aqui,
traduzido para o vocabulário doutrinário — se algum ficar sem tradução, o
fato que ele carrega desaparece da formalização inteira.

{{deferred_atoms}}

Exemplos da tradução esperada: um átomo "o crime foi praticado três meses após
a fuga" vira `After_<crime>_<fuga>`; "o crime foi praticado em concurso de
agentes", combinado com o anterior, sustenta `Unexpected_<crime>`; "o dever era
o genérico de segurança pública" vira `¬Obl_<conduta>`.

## ⚠️ Toda defesa tem um autor

Uma defesa doutrinária não é um fato do caso: é um **movimento de alguém**. O
recorrente invoca o fato de terceiro; o voto divergente sustenta que o dever
virou genérico; o relator não sustenta nem um nem outro. Registrar quem move
cada regra é o que permite reconstruir o julgamento como uma disputa, e não
como um resultado pronto.

Preencha `perspective` em **cada** regra de esquema e em **cada** premissa
doutrinária, com um destes valores:

`recorrente`, `recorrido`, `relator`, `voto_convergente`, `voto_divergente`,
`stf_final`, ou `comum`.

São **dois** campos, porque são duas perguntas diferentes — e confundi-las
apaga justamente o que interessa:

- `origin_perspective` — **quem levantou a tese**. Em geral uma parte
  (`recorrente`, `recorrido`). É a fase de argumentação.
- `perspective` — **quem decidiu por ela**. Uma defesa só bloqueia a
  relevância jurídica porque um julgador a acolheu; enquanto ela é só alegação
  de parte, é proposta, não decisão. É a fase de decisão.

Como escolher `perspective`:

- as regras `cf2lrc` são a **presunção geral** do artigo, que ninguém precisa
  invocar: use `comum`;
- toda defesa (`nwo`, `sc`, `suca`, `nofor`, `rpl`, `unom`) recebe o
  **primeiro julgador**, na ordem `relator` → `voto_convergente` →
  `voto_divergente` → `stf_final`, que a sustenta segundo os lados das
  divergências do dossiê. Primeiro julgador, não a posição final: se a
  divergência já acolheu a tese, é ali que o resultado vira, e `stf_final`
  apenas ratifica;
- se **nenhum julgador** sustenta a defesa — a parte alegou e a corte não
  acolheu —, use a própria parte. Ela vai aparecer no traço como um movimento
  que não decidiu nada, que é exatamente o que foi;
- uma premissa doutrinária herda os dois campos da regra que a consome.

Exemplo do padrão: se o recorrente alega fato de terceiro, o voto divergente
acolhe e a posição final ratifica, então `origin_perspective: recorrente` e
`perspective: voto_divergente`.

Este campo não muda o resultado do solver. Ele muda o que é possível
**perguntar** depois: em que movimento uma pretensão que sobreviveu aos fatos
deixa de sobreviver ao direito, e sobre as razões de quem esse ponto de virada
se apoia.

## Campos

- `doctrinal_premises`: cada uma com `literal` (no vocabulário acima),
  `label_pt` (glosa em português claro), `evidence`, `perspective` e
  `origin_perspective`.
- `scheme_rules`: cada uma com `rule` (a regra completa), `scheme` (o nome do
  esquema), `gloss_pt` (explicação em português claro para leigo), `evidence`,
  `perspective` e `origin_perspective`.
- `targets`: todos os `LeReCa_*` a avaliar.
- `duty_basis_pt`: o **dever discutido no caso**, com os dispositivos como o
  dossiê os cita — não apenas a cláusula genérica de responsabilidade civil.
  Se as perspectivas divergem sobre a natureza do dever, registre as duas
  leituras e diga qual prevaleceu. Vazio só se o caso não envolver dever de
  agir.

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
