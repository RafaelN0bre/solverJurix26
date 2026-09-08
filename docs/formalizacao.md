# Formalização de dossiês anotados → entrada do solver

Este documento descreve o processo que transforma um dossiê anotado por um
especialista (`data/<anotador>/*.json`) num framework de argumentação ASPIC+
executável (`data/translated/<caso>/case.json`), com rastreabilidade de cada
literal e de cada regra até o trecho do acórdão que os sustenta.

## Por que existe

O dossiê é texto livre estruturado em campos: reconstrução por perspectiva
(recorrente, recorrido, posição final da corte), pontos de divergência com o
apoio de cada lado, unidades causais, síntese e passagens do PDF ligadas a
campos específicos. O solver, por outro lado, consome premissas e regras numa
gramática estrita. A formalização é a ponte — e é ela, não o solver, que
concentra a dificuldade e o risco de erro.

O desenho segue duas escolhas centrais:

1. **O LLM só formaliza; quem raciocina é o solver.** Nenhum veredito causal é
   pedido ao modelo. As duas noções (a causa NESS da Definição 4.3, renomeada
   "NESS Cause" na Definição 3.4 do ICAIL 2026, e o "não fosse por" da
   Definição 3.5) são calculadas por `aspic.solver`, e a
   camada de relevância jurídica recebe do solver — não do modelo — os fatos
   `CaFa_*`/`ButFor_*` sobre os quais raciocina (`formalize.bridge`).
2. **O parser corrige o modelo.** Cada estágio passa por checagens
   determinísticas que rodam o parser e o solver de verdade
   (`formalize.validate`); os erros encontrados voltam ao modelo pelo prompt de
   reparo. Um caso só é publicado em `data/translated/` se passar.

## Duas noções causais, não três

Os artigos definem **duas**, e a implementação de referência dos autores
confirma pelas assinaturas dos primitivos que ela expõe
(`causality-solver/.../CausalitySolver.kt` em `tuProlog/arg2p-kt`, clonado em
`~/.claude/knowledge/jurix26/repos/`):

| Noção | Onde | O que testa |
|---|---|---|
| **causa NESS** | `ArgumentationFramework.ness_cause` (`ness/3` lá) | a intervenção `¬φ` quebra **alguma** explicação de ψ |
| **não fosse por** | `ArgumentationFramework.but_for` (`but_for/2`) | depois da intervenção, ψ perde **todos** os argumentos justificados |

Toda causa "não fosse por" é causa NESS; o inverso falha sob
sobredeterminação (Fairchild: cada exposição é causa NESS, nenhuma é
"não fosse por") e sob preempção (Double Shooting: remover o tiro de Bush
mata a única rota justificada, e mesmo assim a morte permanece, porque cai
junto o undercut que a rota de Dlugash sofria).

Houve por um tempo uma terceira coisa aqui: um `is_cause` — que **era** a
causa NESS, com nome que escondia isso — e um `is_ness_cause` dedutivo,
próprio, que não está em artigo nenhum. O segundo procurava φ dentro do
conjunto de premissas de um argumento, e por isso respondia "não" para
qualquer literal **derivado**: `Latrocinio` saía como não-causa quando a
resposta honesta era "este teste não se aplica". Os dois foram removidos. O
que sobrou de `aspic/ness.py` virou `aspic/sufficiency.py`, que **explica** um
veredito (quais conjuntos de condições são suficientes, quais membros são
necessários) sem pronunciá-lo.

### Divergência conhecida com a referência

`ness/3` dos autores não testa só a intervenção unitária `{¬φ}` — ele procura
uma intervenção entre três famílias (`generate_interventions/3`): o singleton,
o *undercut* de uma regra, e qualquer subconjunto das premissas não usadas que
contenha `¬φ`. Nós implementamos só a primeira. O efeito é que
**sub-reportamos causas**: todo positivo nosso é positivo lá, mas não o
contrário. `tests/test_reference_fidelity.py` porta os oráculos dos autores e
marca o caso divergente como `xfail` em vez de escondê-lo.

## Etapas

| # | Etapa | Como funciona |
|---|---|---|
| 0 | **Brief** | Determinístico (`formalize.dossier`). Normaliza o dossiê em markdown: descarta campos vazios e colunas de controle, resolve `source_links` em marcadores de evidência ao lado do campo que sustentam, e lista as passagens citáveis por id. |
| 1 | **Átomos** | LLM. Catálogo de literais: código, glosa em português, tipo, status, perspectivas, evidência, e quais entram como premissa. Define também o resultado a explicar. |
| 2 | **Regras** | LLM. Premissas + regras, usando **apenas** os códigos do estágio 1. É o prompt mais denso: contém o manual de modelagem (omissão, prova insuficiente, excludente, causa concorrente, preempção). |
| 3 | **Perguntas** | LLM. Os pares (φ, ψ) a testar e, para cada um, **o que a corte decidiu** e por quê. O modelo não prevê o resultado do solver. |
| 3b | **Ponte** | Determinístico (`formalize.bridge`). Roda o solver e emite `CaFa_<φ>_<ψ>` / `ButFor_<φ>_<ψ>` para os pares que ele reconheceu. |
| 4 | **Relevância jurídica** | LLM. Premissas doutrinárias (`Om_*`, `Obl_*`, `Unexpected_*`, …) e as regras dos esquemas 2–8 do ICAIL 2026, instanciadas sobre os fatos da ponte. |
| 5 | **Validação** | Determinístico. Checagens + a tabela solver × corte, gravada em `validation.json`. |

## A restrição de modelagem que decide o resultado

Por padrão o solver **não usa preferências**: `_is_weaker`
(`src/aspic/solver.py`) implementa a ordenação básica do artigo, em que dois
argumentos derrotáveis são incomparáveis. Um rebut mútuo, portanto, deixa os
dois lados **indecididos (UNDEC)** — ninguém vence.

Para o framework reproduzir "a corte afastou a alegação do recorrente", a
prevalência tem que ser modelada como **undercut** (`rN: Prova => ¬rM`), não
como rebut (`rN: Prova => ¬Literal`). Essa é a Regra nº 1 de
`prompts/formalize/_shared/grammar.md`, e a validação emite um aviso
(`rules.mutual_rebut`) sempre que encontra um rebut mútuo sem undercut. Ela
continua valendo para tudo o que o pipeline produz: nenhum estágio de LLM
escreve peso nenhum.

### A saída, quando o undercut não serve

Há um caso em que reescrever o rebut como undercut seria falsear o acórdão:
quando a razão de decidir é literalmente que **uma qualificação prevalece
sobre a outra**, e não que uma regra deixou de se aplicar. É o ⟨q0, q2⟩ de
`docs/formalizacao-caso003.md` — dever específico de custódia contra dever
genérico de segurança pública, duas regras concluindo literais
complementares, sem undercut de nenhum lado.

Para esses, um registro pode declarar `FormalizedCase.preferences`
(`src/aspic/preferences.py`): uma **tupla de eixos doutrinários com pesos**,
mais o perfil de cada regra dizendo que eixos ela invoca. A força de uma
regra é a soma ponderada; a de um argumento, a agregação dessas forças pelo
elo mais fraco (padrão), pelo último elo ou pela soma. `A ≺ B` quando os dois
têm força e a de A é estritamente menor.

Três limites, todos deliberados:

1. **Undercut nunca depende de preferência** (Definição 2.10 do ASPIC+): um
   peso não pode passar por cima da alegação de que uma regra não se aplica.
2. **A ordenação básica vem primeiro** e não é negociável — um argumento
   estrito e firme não fica mais fraco por nenhum número.
3. **É aditivo**: sem bloco de preferências, ou com regras que não invocam
   eixo nenhum, o comportamento é exatamente o de antes. Empate de força é
   incomparabilidade de novo, não vitória do primeiro.

Os pesos são dados do registro, não heurística do solver, e a aba **Pesos**
(`src/aspic/preference_view.py`) mostra, para quem for conferir: os eixos, o
perfil de cada regra, os conflitos que a ordenação decidiu, o mesmo caso
rodado *sem* os pesos, e o peso a partir do qual o resultado viraria.

## Qual camada resolve o quê

A divisão entre as duas camadas é a decisão de modelagem mais consequente do
pipeline, e a v1 dos prompts a deixava implícita. O teste, agora explícito em
`02_rules.v2.md`: leia a razão de decidir e pergunte se ela **nega que o fato
ocorreu ou que o mecanismo operou** (camada de causa de fato) ou se **aceita o
mecanismo e nega que o direito deva imputá-lo** (camada de relevância
jurídica).

| Tese do acórdão | Onde entra |
|---|---|
| fato de terceiro; causa superveniente | `suca` + `sc`, estágio 4 |
| ausência de dever de agir; dever genérico em vez de específico | `unom`, estágio 4 |
| resultado imprevisível | `nofor` / `rpl`, estágio 4 |
| causa paralela não ilícita | `nwo`, estágio 4 |
| prova insuficiente; laudo inconclusivo | undercut, estágio 2 |
| preempção fática | undercut, estágio 2 |

Codificar uma defesa doutrinária como undercut na camada de causa de fato tem
um custo que não é óbvio: ela **apaga a conduta do quadro causal**, a ponte não
emite `CaFa_<conduta>_<dano>`, e o estágio 4 fica sem nada sobre o que operar —
o dever de agir nunca chega a ser discutido. Foi o que aconteceu no case-003
com a v1 dos prompts, e o que a v2 corrige.

Corolário que o prompt precisa dizer em voz alta: tirando as defesas dali, **a
cadeia da parte que perdeu permanece aceita (IN) na camada de causa de fato**.
Isso é o esperado, não um defeito — quem a derruba é o estágio 4.

### Fatores: polaridade e ponto abstrato

`AtomOut` carrega `favors` (`responsabilizacao` / `exclusao` / `neutro`) e
`abstract_factor`, que são o `pFactor`/`dFactor` e o `parentFactor` do CATO
(Aleven & Ashley), na formalização ASPIC+ de Prakken, Wyner, Bench-Capon &
Atkinson (JLC 2015, em `docs/papers/`).

A polaridade é sobre a **questão de fundo**, não sobre a posição processual:
`recorrente` e `recorrido` trocam conforme quem recorreu — no case-003 o
recorrente é o Estado — enquanto "este fato empurra para a responsabilização?"
não troca. `favors` e `perspectives` respondem coisas diferentes: um fato que
pesa pela exclusão pode ser afirmado por todos, inclusive por quem perde com
ele.

O `abstract_factor` faz um trabalho preciso: dois fatos de lados opostos sob o
mesmo ponto abstrato **se anulam** (`cancels`, definição 20 do artigo), e é
assim que uma divergência do dossiê deixa de ser duas premissas soltas e passa
a ser uma questão controvertida. No case-003, `DeverEspec` × `DeverGener` sob
`NaturezaDoDever` é a divergência D1 do dossiê, finalmente expressa no modelo.

**O que não está implementado, e por quê.** Todo esquema de precedente do
artigo — CS1 e CS2 (decidir a partir de um paradigma), U1.1 e U2.1
(*distinguishing*), CS3 e CS4 (ênfase), e a relação `substitutes` — tem
`outcome(prec)` ou uma partição `curr × prec` entre as premissas. Precisam de
case base. Os dossiês não registram precedente nenhum e os dois casos
formalizados são de domínios sem relação, então implementá-los produziria
argumentos com aparência de *stare decisis* e sem nada por trás.

### Toda defesa tem um autor

`LrcRuleOut` e `LrcPremiseOut` carregam dois campos de perspectiva, porque são
duas perguntas: `origin_perspective` é quem **levantou** a tese (em geral uma
parte, na fase de argumentação) e `perspective` é quem **decidiu** por ela — o
primeiro julgador que a acolheu. Uma defesa só bloqueia relevância jurídica
porque um julgador a acolheu; enquanto é alegação de parte, é proposta.

Sem esses campos a camada de relevância jurídica fica anônima, e como é ela
que decide os casos de responsabilidade do Estado, o julgamento inteiro se
torna invisível para qualquer análise por perspectiva
(`aspic.perspectives.unattributed_lrc_rules` mede quanto sobrou sem autor).

### O dever não é decoração

Um átomo de `kind: dever` só está modelado se alguma regra o lê: ele entra como
antecedente da regra causal que habilita (`r0: OmisAtd AND DevAtdSaude =>
Agrav`). Dever declarado como premissa que nenhuma regra consome é erro
(`rules.duty_not_used`, com reparo); qualquer outra premissa inerte é aviso
(`rules.inert_premise`).

O efeito colateral de regras conjuntivas é que **todo antecedente vira causa de
fato**, o que faria a camada 4 perguntar se "o dever de custódia foi causa da
morte". Por isso `bridge.NON_CANDIDATE_KINDS` tira os átomos de `dever` e
`prova` da lista de candidatos a causa — sem tirá-los das regras, e sem tirar
do teste um literal sobre o qual o dossiê efetivamente pergunta.

## Prompts

Ficam em `prompts/formalize/`, um arquivo por estágio, versionados no nome:

```
prompts/formalize/
  01_atoms.v1.md      02_rules.v1.md      03_queries.v1.md
  04_lrc.v1.md        99_repair.v1.md
  02_rules.v2.md      03_queries.v2.md    04_lrc.v2.md
  _shared/grammar.md          # contrato da gramática (incluído em 02)
  _shared/lrc_schemes.md      # esquemas 2–8 do ICAIL 2026 (incluído em 04)
```

Cada arquivo tem um front-matter `---` com `model`, `temperature` e afins — de
modo que trocar um estágio para um modelo mais barato é uma edição de prompt, e
não uma mudança de código. O corpo puxa fragmentos com
`{{include:_shared/grammar}}` e recebe valores por `{{variavel}}`; um
placeholder não preenchido é erro, nunca prompt vazio.

**Para iterar**, copie `02_rules.v1.md` para `02_rules.v2.md` e edite: a v1
continua executável (`--prompt-version rules=1`) para comparação. O loader
sempre usa a maior versão por padrão.

Dois hashes são registrados por prompt: `template_sha256` (os arquivos de
origem, incluindo os includes) identifica a *versão do prompt* na proveniência;
`rendered_sha256` (o texto exato enviado) é a chave do cache.

## Artefatos

```
data/translated/
  index.json                          catálogo que a interface lê
  <caso>/case.json                    o registro canônico
  <caso>/validation.json              checagens + tabela solver × corte
  <caso>/runs/<run-id>/
    00_brief.md                       normalização determinística do dossiê
    01_atoms.json  02_rules.json  03_queries.json  04_lrc.json
    03b_bridge.json                   os fatos causais calculados pelo solver
    trace.jsonl                       1 linha por chamada: prompt, resposta, tokens
    run.json                          manifesto: modelo, prompts+hashes, hash da entrada
    case.json  validation.json        cópia do que foi publicado neste run
```

`case.json` guarda `knowledge_base` e `causal_model` **já no formato exato** que
`ArgumentationFramework` recebe — não há adaptador entre a formalização e o
solver. `expect_*` das perguntas guarda o que o solver calculou na hora, o que
faz `tests/test_translated_regression.py` detectar qualquer mudança no solver
que altere silenciosamente uma formalização já publicada.

## Uso

```bash
cp .env.example .env          # e preencher GEMINI_API_KEY
uv sync

# revisar prompts e brief sem gastar token
uv run python scripts/translate_dossier.py \
  --input data/izabela-melo/case-005-dossie-2026-08-24.json --dry-run

# execução real
uv run python scripts/translate_dossier.py \
  --input data/izabela-melo/case-005-dossie-2026-08-24.json

# iterar um prompt específico
uv run python scripts/translate_dossier.py --input <arquivo> --prompt-version rules=2

# re-rodar só o solver sobre um caso já formalizado (sem LLM)
uv run python scripts/run_translated.py case-005

# conferir na interface
uv run python scripts/run_app.py     # http://127.0.0.1:8000/
```

O cache em `.cache/formalize/` é chaveado pelo prompt renderizado + modelo +
schema, então iterar o estágio 4 não repaga os estágios 1–3. `--no-cache`
ignora.

## Na interface

Os casos formalizados aparecem na barra lateral ao lado dos cinco casos dos
artigos e passam pelos mesmos renderizadores. A interface está descrita em
detalhe em [`docs/interface.md`](interface.md); em resumo, cada caso tem cinco
abas — **Análise**, **Dossiê**, **Perspectivas**, **Formalização** e
**Conferência** — e há um **Panorama** com o acervo inteiro.

O que só existe para casos vindos de dossiê:

- **Relevância jurídica (ICAIL 2026)**, dentro da Análise — o segundo grafo,
  quais `LeReCa_*` sobrevivem e qual defesa doutrinária derrubou cada um que
  não sobreviveu.
- **Ficha de formalização** — cada átomo e cada regra ao lado do trecho do
  acórdão que os sustenta, a camada LRC separando premissas de ponte
  (calculadas) de premissas doutrinárias (extraídas), a tabela solver × corte, e
  a proveniência (modelo, arquivos de prompt e seus hashes, id do run).
- **Conferência** — a leitura quantitativa da tradução: acordo com a corte,
  cobertura das passagens marcadas, o que ficou sem rastro até o acórdão, as
  checagens determinísticas e o custo de cada execução.

Endpoints: `/api/cases`, `/api/overview`, `/api/cases/{id}`,
`/api/cases/{id}/dossier`, `/api/cases/{id}/formalization`,
`/api/cases/{id}/evaluation`, `/api/cases/{id}/coverage`,
`/api/cases/{id}/glossary`, `/api/cases/{id}/perspectives`,
`/api/cases/{id}/raw`.

## Quando solver e corte divergem

Divergência na tabela não é falha do código: é o achado. O caminho é abrir a
ficha, localizar a regra envolvida, e iterar o prompt correspondente. Três
causas cobrem quase tudo o que já apareceu:

1. **Undercut na camada errada** — uma defesa doutrinária escrita como ataque
   na camada de causa de fato. Sintoma: uma conduta que o acórdão discute
   longamente não é causa de fato de nada, e a camada de relevância jurídica
   fica vazia. Correção em `02_rules.v*.md`.
2. **Rebut onde deveria haver undercut** — os dois lados ficam UNDEC e ninguém
   vence. A validação avisa (`rules.mutual_rebut`).
3. **Rotulagem da pergunta** — `court_verdict` respondendo "a corte deu ganho
   de causa a quem invocou φ?" em vez de "a corte reconheceu φ como causa de
   ψ?". Sintoma fácil de ver na ficha: a `court_rationale_pt` diz "rompeu o
   nexo" e o veredito da mesma linha diz `acolhida`. Correção em
   `03_queries.v*.md`.

Uma taxa de concordância alta sobre poucas perguntas não é melhor do que uma
taxa média sobre muitas: leia sempre a coluna de cobertura da aba Conferência
junto com o placar.
