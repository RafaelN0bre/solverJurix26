# Auditoria — ICAIL 2026 × camada de relevância jurídica

Artigo auditado: Pisano, Prakken & Sartor, *From Cause-in-Fact to Legally Relevant
Cause through Argumentation*, ICAIL 2026 (`docs/papers/ICAIL2026causation.pdf`,
10 páginas, lido integralmente).
Implementação de referência dos autores:
`~/.claude/knowledge/jurix26/repos/tuProlog--arg2p-kt/causality-solver/`.
Nossa implementação: `src/aspic/lrc.py`, `src/formalize/bridge.py`,
`src/formalize/schema.py`, `src/aspic/solver.py`, `data/translated/case-003-final/case.json`.

Suíte no estado auditado: `VIRTUAL_ENV= uv run pytest -q` → **286 passed, 1 xfailed**.

---

## Resumo

O núcleo está fiel. Os sete esquemas do artigo (equações 2 a 8) estão todos
presentes em `src/aspic/lrc.py:26-34`, com a numeração correta, e os cinco casos
trabalhados do artigo (Kingston, Watson, R v Jordan, Berry, Yania + leucemia)
reproduzem os vereditos publicados quando alimentados com as bases de
conhecimento exatas do artigo — rodado abaixo. A pergunta 1 tem resposta
tranquilizadora: o artigo usa `CaFa` para **NESS**, e é isso que
`src/formalize/bridge.py:57-65` faz. Não há predicado trocado.

Há, porém, **cinco divergências confirmadas por execução**, das quais duas
mudam veredito:

1. **`CaFa` entra em K_p e não em K_n.** A equação (1) do artigo põe
   `CaFa(φ,ψ) ∈ 𝒦ₙ(LRC)` — **axioma**. `src/formalize/schema.py:299-307` põe em
   `premises` e força `axioms: []`. Consequência rodada: um argumento por
   `¬CaFa_A_B` *undermina* a ponte e derruba `LeReCa_A_B`, o que no artigo é
   estruturalmente impossível. Mesmo teoria, vereditos opostos.
2. **`relevance_report` reporta defesas que não venceram, e não vê defesas que
   venceram.** Reporta `blocked_by` para alvos que sequer têm argumento (é
   exatamente o que acontece em `case-003-final`), e devolve `blocked_by: []`
   quando a defesa vence por *rebut* ou por *undermine* em vez de *undercut*.
   Três contraexemplos mínimos rodados.
3. **`SupersedingCause` está declarado unário** (`src/aspic/lrc.py:66-68`); no
   artigo é ternário, `SupersedingCause(χ, φ, ψ)` (eqs. 4 e 5). A instanciação
   fiel `SupersedingCause_Ma_Ga_Ig` é mal-parseada como aridade 1.
4. **A numeração "regra 9" de `dvesp` colide com a equação (9) do artigo**
   (`CF2LRCBis`, seção 6, causalidade adequada). Colisão literal.
5. **Em `case-003-final` a ponte está morta**: nenhuma das quatro premissas
   `CaFa_*`/`ButFor_*` é consumida por regra alguma, e a única que seria
   (`CaFa_OmiEstatal_Danos`) não existe na base. A camada de relevância do caso
   principal não toca no resultado da camada de causa de fato.

Quanto às três extensões (`dvesp`/`dvgen`/`dvpre`): são **evitáveis**. Reproduzi
o veredito do caso 003 usando **só os esquemas 2-8**, delegando a questão do
dever a um módulo separado — que é literalmente o que o artigo prescreve
("the issue of whether the omission is obligatory can be modelled in another
problem solving module", §6). O que torna as extensões *necessárias hoje* não é
uma limitação dos esquemas do artigo, e sim uma limitação nossa:
`PreferenceModel.argument_strength` (`src/aspic/preferences.py:198-204`) devolve
`None` para argumento de premissa nua, de modo que `Obl` e `¬Obl` como premissas
ordinárias em conflito ficam **incomparáveis para sempre**. Rodado.

---

## Tabela esquema/definição → implementação → veredito

| Artigo | Enunciado exato do artigo | Nossa implementação | Veredito |
|---|---|---|---|
| Def. 3.4 NESS Cause | ∃ D∈𝒢(AF_CT) com Conc(D)=φ; A com Conc(A)=ψ; explicação E de A; L⊆ℒ com ¬φ∈L; B∈AF_CT+L com L⊆Sub(B), B ataca C∈E, B rotulado *in* ou *und* | `solver.py:685-722` `ness_cause` | **Parcial** — não exige que o atacante seja *in*/*und*; testa queda de assinatura do conjunto-suporte. (Divergência da camada CIF, já mapeada em `maps/tuProlog--arg2p-kt.md`; fora do escopo desta auditoria.) |
| Def. 3.5 But-for Cause | (a) ∃ argumento para ψ em 𝒢(AF_CT); (b) nenhum em 𝒢(AF_CT+{¬φ}) | `solver.py:724-751` `but_for` | **Fiel** — idêntico a `checkButFor` (`CausalitySolver.kt:202-214`) |
| Eq. (1) ponte `oi(…)` | φ é NESS cause de ψ ⇒ `CaFa(φ,ψ) ∈ 𝒦ₙ(LRC)` | `bridge.py:57-65` + `schema.py:299-307` | **Divergente** — predicado certo (NESS→CaFa ✔), conjunto errado (K_p em vez de K_n). Ver D-1 |
| — | `ButFor(χ,ψ)` também é insumo da LRC (aparece no 𝒦 de Watson, e é antecedente de SuCa) | `bridge.py:63-64` | **Fiel** |
| Eq. (2) `CF2LRC(φ,ψ)` | `CaFa(φ,ψ) ⇒ LeReCa(φ,ψ)` | `lrc.py:27` `cf2lrc` ("regra 2") | **Fiel** |
| Eq. (3) `NWO(φ,ψ,χ)` | `CaFa(χ,ψ), χ≠φ, ¬Tortious(χ) ⇒ ¬CF2LRC(φ,ψ)` | `lrc.py:28` `nwo` ("regra 3"); instância em `test_legally_relevant_causes_2026.py:137` | **Fiel com ressalva** — a instância omite `χ≠φ` e o `CaFa(φ,ψ)` que a referência acrescenta (`Listing 2`, `nwo(Y,Z,X) : cafa(X,Z), cafa(Y,Z), prolog(X\=Y), -tortious(X)`). Ver S-1 |
| Eq. (4) `SC(φ,ψ,χ)` | `SupersedingCause(χ,φ,ψ) ⇒ ¬CF2LRC(φ,ψ)` | `lrc.py:29` `sc` ("regra 4") | **Fiel na estrutura**, aridade errada no vocabulário. Ver D-3 |
| Eq. (5) `SuCa(φ,ψ,χ)` | `CaFa(φ,ψ), CaFa(χ,ψ), χ≠φ, After(χ,φ), Unexpected(χ), ButFor(χ,ψ) ⇒ SupersedingCause(χ,φ,ψ)` — **seis** antecedentes | `lrc.py:30` `suca` ("regra 5"); instância em `test_…2026.py:184-185` (5 antecedentes); instância em `case.json:512,523` (**2 e 3** antecedentes) | **Divergente no caso 003** — ver D-5 e §extensões |
| Eq. (6) `NoFor(φ,ψ)` | `¬Foreseeable(φ,ψ) ⇒ ¬CF2LRC(φ,ψ)` | `lrc.py:31` `nofor` ("regra 6"); instância em `test_…2026.py:271` | **Fiel** |
| Eq. (7) `RPL(φ,ψ)` | `ForeseeableRisk(φ,χ), Playout(χ,ψ) ⇒ ¬NoFor(φ,ψ)` | `lrc.py:32` `rpl` ("regra 7"); instância em `test_…2026.py:276-277` | **Fiel** — inclusive a exceção-da-exceção dispara quando `Playout` se verifica (rodado) |
| Eq. (8) `UnOm(φ,ψ)` | `Om(φ), ¬Obl(¬φ) ⇒ ¬CF2LRC(φ,ψ)` | `lrc.py:33` `unom` ("regra 8"); instância em `test_…2026.py:307` | **Fiel nos testes**; **divergente no caso 003** (`case.json:559`) — ver D-5 |
| Eq. (9) `CF2LRCBis(φ,ψ)` | `CaFa(φ,ψ), CausesNormally(φ,ψ) ⇒ LeReCa(φ,ψ)` (causalidade adequada, §6) | **ausente**; o número 9 está ocupado por `dvesp` (`lrc.py:48`) | **Colisão** — ver D-4 |
| §6 `IncreasesProbability` | substituto de `CausesNormally` | ausente de `ALL_PREDICATES` (`lrc.py:61-77`) | Lacuna menor (o artigo só esboça) |
| §2 Def. 2.2 K_n / K_p | axiomas × premissas ordinárias | `schema.py:306` força `axioms: []` | **Divergente** — ver D-1 |
| §7.2 estratificação presunção→defesa→exceção-da-exceção | `cf2lrc` ← `nofor` ← `rpl` | preservada nos testes; ver §Estratificação | **Fiel nos testes, distorcida no caso 003** |

### Os cinco casos trabalhados do artigo, rodados com a base do artigo

```
 Kingston LeReCa_DeFi_De         just=False blockers=['nwo']
 Kingston LeReCa_UnFi_De         just=True  blockers=[]
 Watson   LeReCa_Ga_Ig           just=False blockers=['sc']
 Watson   LeReCa_Ma_Ig           just=True  blockers=[]
 Berry    LeReCa_PlSp_In         just=False blockers=['nofor']
 Berry    LeReCa_TrFa_In         just=True  blockers=[]
 Yania    LeReCa_notYaHe_BiDi    just=False blockers=['unom']
 Leucemia LeReCa_notPaCo_ChDi    just=True  blockers=[]
 Berry+RPL LeReCa_PlSp_In        just=True  blockers=[]
```

Todos batem com o artigo. Com a base **exata** de Kingston (incluindo
`DeFi ≠ UnFi`) o framework produz **7 argumentos**, que é o número que o artigo
anuncia ("Instantiating the theory yields seven arguments"); com a base do nosso
teste (`test_…2026.py:124-127`, sem a desigualdade) produz 6. Veredito idêntico.

---

## Divergências confirmadas

### D-1 · `CaFa` entra como premissa ordinária, não como axioma

- **Artigo diz:** eq. (1), `oi(…) : φ is a NESS cause of ψ relative to AF_CT ⇒ CaFa(φ,ψ) ∈ 𝒦ₙ(LRC)`. `𝒦ₙ` são os **axiomas** (Def. 2.2). Axioma não pode ser *undermined* (Def. 2.5).
- **Referência faz:** `f1 :=> cafa(defi, de).` — em Arg2P, `:=>` sobre corpo vazio é o veredito da ponte, entregue pela regra de bridge `oi(Y,Z) :- check(Y,Z), prolog(causality::ness(X,Y,Z)) => cafa(Y,Z)` (Listing 3), não por uma premissa questionável.
- **Nós fazemos:** `src/formalize/schema.py:299-307` — tudo vai para `"premises"`, e `"axioms"` é literalmente `[]`.
- **Contraexemplo rodado:**

```
CaFa em K_p (nosso)   ataques=[('A0','A3','rebut'),('A3','A0','undermine'),('A3','A2','undermine')] | LeReCa justificado=False
CaFa em K_n (artigo)  ataques=[('A0','A3','rebut')]                                                 | LeReCa justificado=True
```

  Mesma teoria (`cf2lrc_A: CaFa_A_B => LeReCa_A_B`, `und_A: Exc => ¬CaFa_A_B`),
  vereditos opostos, decididos só pela colocação da premissa da ponte.
- **Impacto: alto.** Abre uma via de ataque que o artigo fecha por construção:
  a camada de relevância pode *revogar* o veredito da camada de causa de fato,
  que é exatamente a fronteira de determinismo que `bridge.py:1-15` diz existir
  para impedir. Correção de uma linha (`"axioms": bridged_premises`).

### D-2 · `relevance_report` erra nos dois sentidos

`src/aspic/lrc.py:158-201` lê apenas *undercuts aceitos* cuja conclusão é
`¬<id de regra>` para uma regra cujo consequente é o alvo.

**D-2a — reporta bloqueador fantasma.** Se o alvo nunca teve argumento (porque a
premissa `CaFa_*` não existe), o relatório ainda lista as defesas:

```
any arg for LeReCa_A_B? False
REPORT: [{"target":"LeReCa_A_B","justified":false,
          "blocked_by":[{"undercut_rule":"cf2lrc_A","attacker":"A1",
                         "attacker_rules":["nwo_A"],"scheme":"nwo", …}]}]
```

Não é hipótese: é o que `case-003-final` publica. Rodado sobre o caso real:

```
--- report AS SHIPPED ---
 target LeReCa_OmiEstatal_Danos justified False
   blocked_by sc   ['sc_q6','suca_q4']
   blocked_by unom ['dvgen_q1','dvgen_q2','unom_q7']
   blocked_by sc   ['sc_q6','suca_q3']

LeReCa_OmiEstatal_Danos is conclusion of ANY argument? False
```

Isto é, `case.json:585-620` afirma que a pretensão foi derrubada por causa
superveniente e por omissão sem dever, quando na verdade ela **nunca chegou a
existir**. (O `modelling_notes_pt` do próprio caso, `case.json:722`, descreve
corretamente o fenômeno — o relatório é que o contradiz.)

**D-2b — não vê defesa que vence por rebut.** O artigo chama de defesa qualquer
coisa que impeça a relevância; nada obriga a ser undercut, e agora que há
preferências (`src/aspic/preferences.py`) o rebut decide:

```
CE-1 defeats: [('A3','A2','rebut')]
CE-1 justified: ['CaFa_A_B','Exc','¬LeReCa_A_B']
CE-1 REPORT: [{"target":"LeReCa_A_B","justified":false,"blocked_by":[]}]
```

`¬LeReCa_A_B` está **justificado** — a defesa venceu, limpa — e o relatório diz
"não justificado, bloqueado por nada".

**D-2c — nem defesa por undermine.**

```
CE-3 attacks: [('A0','A3','rebut'),('A3','A0','undermine'),('A3','A2','undermine')]
CE-3 justified: ['Exc']
CE-3 REPORT: [{"target":"LeReCa_A_B","justified":false,"blocked_by":[]}]
```

- **Impacto: alto para a leitura, nulo para o veredito.** O campo `justified`
  está sempre certo; `blocked_by` é que é simultaneamente falso-positivo e
  falso-negativo. É o campo que a interface mostra ao jurista.
- **Correção mínima:** distinguir três estados — *sem argumento para o alvo* /
  *derrotado por undercut* (com o esquema) / *derrotado por rebut ou undermine*
  (com o argumento vencedor) — em vez de um `blocked_by` só.

### D-3 · `SupersedingCause` declarado unário; no artigo é ternário

- **Artigo diz:** eq. (4) `SC(φ,ψ,χ) : SupersedingCause(χ,φ,ψ) ⇒ ¬CF2LRC(φ,ψ)`;
  eq. (5) conclui `SupersedingCause(χ,φ,ψ)`. Aridade **3**.
- **Nós fazemos:** `src/aspic/lrc.py:66-68` lista `"SupersedingCause"` em
  `UNARY_PREDICATES`. Os testes escrevem `SupersedingCause_Ma`,
  `SupersedingCause_AdAn` (`test_…2026.py:185,188,223,225`).
- **Contraexemplo rodado:**

```
ternary parse: ('SupersedingCause', ['Ma_Ga_Ig'])   # deveria ser ['Ma','Ga','Ig']
binary  parse: ('SupersedingCause', ['Ma'])
After parse  : ('After', ['Ma','Ga'])               # binário, correto
```

- **Impacto: médio.** Não muda veredito (a instanciação por id de regra já fixa
  φ e ψ), mas quebra a glosa em `formalize.build._render_lrc_literal` para
  qualquer formalização que escreva o predicado como o artigo escreve, e
  impede que dois superveniências sobre efeitos distintos se distingam.

### D-4 · A numeração "regra 9" colide com a equação (9) do artigo

- **Artigo diz:** §6, eq. **(9)**:
  `CF2LRCBis(φ,ψ) : CaFa(φ,ψ), CausesNormally(φ,ψ) ⇒ LeReCa(φ,ψ)` — o esquema da
  *causalidade adequada*, alternativa ao `CF2LRC`.
- **Nós fazemos:** `src/aspic/lrc.py:48` chama `dvesp` de "regra 9", `:49`
  `dvgen` de "regra 10", `:50` `dvpre` de "regra 11".
- **Impacto: baixo, mas é erro de citação.** O comentário de `lrc.py:45-46`
  afirma "são numeradas a partir de 2-8 do artigo, para que o leitor veja de
  relance quais vêm dele" — e a numeração escolhida faz exatamente o contrário
  na primeira posição. `dvesp` deveria ser 10, ou (melhor) as extensões deveriam
  usar rótulo sem número (`E1`/`E2`/`E3`).

### D-5 · Em `case-003-final` a ponte está desconectada e os esquemas 5 e 8 estão desidratados

**A ponte não é consumida.** Rodado:

```
LRC premises: ['CaFa_LapsoTemp_Danos','CaFa_FormacaoQuad_Danos','CaFa_Latrocinio_Danos',
               'ButFor_Latrocinio_Danos','OmiEstatal','RegFechado','LapsoTemp','FormacaoQuad','Latrocinio']
CaFa_OmiEstatal_Danos present in KB? False
bridged premises NEVER used by any rule: ['ButFor_Latrocinio_Danos','CaFa_FormacaoQuad_Danos',
                                          'CaFa_LapsoTemp_Danos','CaFa_Latrocinio_Danos']
```

As quatro premissas que a ponte produz são inertes; a única regra que consumiria
uma delas, `cf2lrc_q5` (`case.json:534`), pede `CaFa_OmiEstatal_Danos`, que o
solver recusou:

```
  ness(OmiEstatal,Danos)=False  but_for=False
  ness(FugaPreso,Danos)=False   but_for=False
  ness(Latrocinio,Danos)=True   but_for=True
bridge premises recomputed: ['CaFa_LapsoTemp_Danos','CaFa_FormacaoQuad_Danos','CaFa_Latrocinio_Danos','ButFor_Latrocinio_Danos']
lereca targets: ['LeReCa_LapsoTemp_Danos','LeReCa_FormacaoQuad_Danos','LeReCa_Latrocinio_Danos']
case targets   : ['LeReCa_OmiEstatal_Danos']
```

O conjunto de alvos que a ponte licencia é **disjunto** do alvo que o caso
declara (`case.json:581-583`). Na arquitetura do artigo isso não é modelável: o
módulo LRC só decide relevância de causas de fato, e `LeReCa(φ,ψ)` sem
`CaFa(φ,ψ)` não tem esquema que o derive.

**Vocabulário LRC ausente.** Rodado sobre a teoria do caso:

```
literais FORA da linguagem LRC: ['AtoTerceiro','DeverEspec','DeverGener','FormacaoQuad',
                                 'LapsoTemp','Latrocinio','OmiEstatal','RegFechado','¬DeverEspec']
Om_* presente? False | Obl_* presente? False | SupersedingCause_* presente? False
```

Consequências por esquema:

- **`suca_q3`/`suca_q4` (`case.json:512,523`)** têm 2 e 3 antecedentes contra os
  **6** da eq. (5). Faltam `CaFa(φ,ψ)`, `CaFa(χ,ψ)`, `χ≠φ`, `Unexpected(χ)`,
  `ButFor(χ,ψ)` — e `CaFa_Latrocinio_Danos` e `ButFor_Latrocinio_Danos`, que
  são exatamente dois desses antecedentes, **estão na base e não são usados**.
  `LapsoTemp` faz as vezes de `After(χ,φ)`; concluem `AtoTerceiro` em vez de
  `SupersedingCause(χ,φ,ψ)`.
- **`unom_q7` (`case.json:559`)** é `OmiEstatal AND ¬DeverEspec => ¬cf2lrc_q5`
  contra `Om(φ), ¬Obl(¬φ)` da eq. (8): o predicado `Om` sumiu (o átomo
  `OmiEstatal` acumula "é a causa" e "é uma omissão"), e `Obl(¬φ)` virou
  `DeverEspec`.

- **Impacto: alto para a tese.** O caso principal é apresentado como aplicação
  da camada do artigo, e nele a camada do artigo não recebe nada da camada de
  causa de fato nem usa o vocabulário do artigo. O `modelling_notes_pt`
  (`case.json:722`) já registra a causa (a ruptura foi posta nas duas camadas ao
  mesmo tempo, r7 e q6/q7), o que atenua muito a gravidade: é escolha de
  modelagem documentada, não defeito oculto. Mas o bloco `relevance` publicado
  não reflete essa nota (D-2a).

---

## As três extensões nossas (dvesp/dvgen/dvpre): justificadas ou evitáveis?

**Veredito: evitáveis, e a razão de existirem é uma lacuna nossa, não do artigo.**

### Poderiam ter sido expressas com 2-8?

**Sim.** Reconstruí o caso 003 com **apenas** `cf2lrc`, `suca`, `sc` e `unom`,
delegando a questão do dever a um módulo separado — que é o que o artigo manda
fazer, §6: *"the issue of whether the omission is obligatory can be modelled in
another problem solving module, which needs to consider that legal systems may
regulate in different ways obligations to prevent harm."*

```
=== VARIANTE C: modulo separado decide o dever (como o artigo prescreve) ===
 modulo do dever decide: ['¬Obl_notOmiEstatal']
 justified: False
 blocked_by schemes: ['sc', 'unom']
 TODOS os esquemas usados vem do artigo: ['cf2lrc', 'sc', 'suca', 'unom']
```

Mesmo veredito do caso publicado, mesmas duas defesas, com as **mesmas
dimensões e pesos** ⟨dever 4, intervenção 5, autonomia 5⟩ — só que operando
dentro do módulo do dever, onde `d0: RegFechado => Obl_notOmiEstatal` e
`d1: LapsoTemp AND FormacaoQuad => ¬Obl_notOmiEstatal` são regras derrotáveis
normais e portanto perfilháveis.

E `dvpre`, especificamente, existe só para tapar um buraco que nós mesmos
abrimos. `dvpre_q8: DeverEspec => ¬sc_q6` (`case.json:570`) é uma
exceção-à-defesa; o artigo tem exatamente uma (`RPL`, eq. 7) e ela ataca
`NoFor`, não `SC`. Contra `SC` o caminho do artigo é negar um dos seis
antecedentes de `SuCa` — tipicamente `Unexpected(χ)` — e `suca_q3/q4` largaram
justamente esse antecedente. Restaurando-o, a tese do relator vira um rebut
normal sobre `Unexpected`, e a mesma máquina de preferências produz os dois
desfechos:

```
 dever=12.0 vs interv=5 -> LeReCa justificado? True  | blockers []
 dever=3.0  vs interv=5 -> LeReCa justificado? False | blockers ['sc']
```

Sem `dvpre`, sem `dvesp`, sem `dvgen`.

### `Obl` como conclusão em vez de premissa: extensão legítima ou distorção?

**É legítima em espírito e distorcida na execução.** O artigo trata `Obl` como
premissa ligada/desligada *dentro* do módulo LRC precisamente porque delega a
decisão a **outro** módulo; ele não afirma que a questão do dever seja
indecidível, afirma que ela não é da alçada do LRC. Transformá-la em conclusão
de argumento é o mesmo movimento — o que se perde é a modularidade: em vez de
um segundo framework, `dvesp`/`dvgen` inlineiam o módulo do dever dentro do LRC,
onde ele passa a competir com os esquemas doutrinários no mesmo grafo.

O que de fato *força* essa inlineação é uma limitação de
`src/aspic/preferences.py`. `argument_strength` (`:198-204`) só pontua
`argument.defeasible_rules`; argumento de premissa nua não tem nenhuma, logo
vale `None`, logo é **incomparável com qualquer coisa**. Rodado:

```
=== VARIANTE A: paper-faithful, Obl/¬Obl como premissas ordinarias ===
 attacks: [('A1','A3','undermine'),('A1','A5','undermine'),('A3','A1','undermine'),('A5','A4','undercut')]
 justified: ['CaFa_OmiEstatal_Danos','Om_OmiEstatal']
 report: [{'target':'LeReCa_OmiEstatal_Danos','justified':False,'blocked_by':[]}]
 strengths: None None -> incomparable
```

Com `Obl_notOmiEstatal` e `¬Obl_notOmiEstatal` como premissas ordinárias em
conflito — a forma do artigo — os dois argumentos ficam UNDEC para sempre e a
camada não responde nada. O ASPIC+ do artigo tem ordenação sobre 𝒦ₚ (Def. 2.11);
o nosso `PreferenceModel` não. **As extensões são um contorno dessa ausência.**

### A numeração 9/10/11 é defensável?

**Não.** Colide com a eq. (9) do artigo (`CF2LRCBis`) — ver D-4.

### `dvgen` em `DEFENCE_SCHEMES` faz sentido?

**A pergunta é acadêmica: `DEFENCE_SCHEMES` é código morto.**

```
$ grep -rn "DEFENCE_SCHEMES" src tests scripts docs | grep -v src/aspic/lrc.py
(nada)
```

Nenhum consumidor. Como documentação, a inclusão é internamente coerente:
`suca` também está lá e também não undercuta nada (conclui
`SupersedingCause`, que é o que `sc` consome); `dvgen` conclui `¬DeverEspec`,
que é o que `unom_q7` consome. Mesmo papel, mesma classificação. E `dvpre` está
corretamente **fora**, como `rpl`, por ser exceção-à-exceção. Não há incoerência
— há um conjunto que ninguém lê.

---

## Suspeitas não confirmadas

**NÃO CONFIRMADA — predicado da ponte trocado (NESS ↔ but-for).** Era a hipótese
mais grave da pauta. A eq. (1) do artigo diz textualmente *"φ is a NESS cause of
ψ relative to AF_CT ⇒ CaFa(φ,ψ) ∈ 𝒦ₙ(LRC)"*, e a Listing 3 confirma
(`oi(Y,Z) :- check(Y,Z), prolog(causality::ness(X,Y,Z)) => cafa(Y,Z)` — `ness`,
não `but_for`). `src/formalize/bridge.py:61-64` emite `cafa_literal` sob
`if fact.ness` e `but_for_literal` sob `if fact.but_for`. Correto. `ButFor` é
predicado próprio e independente, insumo do `SuCa` (eq. 5) e presente no 𝒦 de
Watson — também correto.

**NÃO CONFIRMADA — `but_for` que não seja `ness`.** 1.355 pares varridos em
todas as teorias de `data/translated/*/case.json` (camadas CIF e LRC) mais a
biblioteca `aspic.examples`, e 102.228 pares em 4.000 teorias aleatórias
(4.024 casos com `but_for` verdadeiro): **zero violações**. Estruturalmente
também se sustenta: toda explicação contém o próprio argumento
(`solver.py:646`), logo o argumento por ψ está em `support_set(ψ)`; se ψ perde
todos os argumentos justificados, aquela assinatura não sobrevive e `ness_cause`
retorna `True`. **Ressalva:** o artigo **não afirma** essa direção. Ele afirma
só a falha da recíproca — *"Clearly, a NESS cause φ may not be a but-for cause
in cases of overdetermination"*. A frase de `solver.py:733-737` ("Consequently
every but-for cause is a NESS cause") é inferência nossa, verdadeira na nossa
implementação, mas não citável como tese do artigo.

**NÃO CONFIRMADA — atribuição errada de esquema em `relevance_report`.** O laço
de `lrc.py:187-188` sobrescreve (`scheme = scheme_of(used) or scheme`), ficando
com o **último** esquema da lista de regras do argumento, e não com a regra topo.
Tentei produzir divergência e não consegui: `defeasible_rules` está em ordem de
derivação, então o último elemento *é* a regra topo.

```
argument rule list (unsorted): ['rpl_A','nwo_A'] | top rule? nwo_A
scheme reported: nwo
```

Correto por acidente. Fica como fragilidade (basta a ordem mudar), não como
divergência.

**NÃO CONFIRMADA — `scheme_of` confundir `sc` com `suca`.** O casamento por
prefixo mais longo (`lrc.py:111-114`) protege: `scheme_of('suca_q3')` →
`'suca'`, `scheme_of('sc_q6')` → `'sc'`.

**Fora do escopo, registrado:** `tests/test_relevance.py` **não é** teste da
camada de relevância jurídica. É teste da noção de *explicação/conjunto-suporte*
(Def. 3.3, Exemplos 3.1 e 3.2), da camada de causa de fato. O nome engana.

---

## Estratificação (presunção → defesas → exceção da exceção)

**Preservada nos testes do artigo, distorcida no caso 003.**

Nos testes, a torre de três andares funciona e foi rodada: `cf2lrc_PlSp` (andar
1, presunção) ← `nofor_PlSp` (andar 2, defesa) ← `rpl_PlSp` (andar 3, exceção da
exceção). Com `¬Playout_SpCo_In` o andar 3 não dispara e o alvo cai
(`blockers=['nofor']`); com `Playout_SpCo_In` ele dispara e o alvo se sustenta
(`Berry+RPL … just=True blockers=[]`). É exatamente a §5 do artigo.

Em `case-003-final` a topologia dos três andares existe:

- andar 1 — `cf2lrc_q5` (`case.json:534`);
- andar 2 — `sc_q6` (`:547`) e `unom_q7` (`:559`), ambos concluindo `¬cf2lrc_q5`;
- andar 3 — `dvpre_q8: DeverEspec => ¬sc_q6` (`:570`).

Mas o andar 1 está vazio (D-5: sem `CaFa_OmiEstatal_Danos`, `cf2lrc_q5` nunca
constrói argumento), e o andar 3 morre antes de agir. Rodado:

```
justified: ['AtoTerceiro','ButFor_Latrocinio_Danos','CaFa_FormacaoQuad_Danos','CaFa_LapsoTemp_Danos',
            'CaFa_Latrocinio_Danos','DeverGener','FormacaoQuad','LapsoTemp','Latrocinio','OmiEstatal',
            'RegFechado','¬DeverEspec','¬cf2lrc_q5']
```

`¬sc_q6` é conclusão de argumento construído mas **não** justificada, porque
`DeverEspec` perde o rebut para `¬DeverEspec`:

```
{'attacker':'A11','attacker_conclusion':'¬DeverEspec','attacker_rules':['dvgen_q1'],'attacker_strength':10.0,
 'target':'A9','target_conclusion':'DeverEspec','target_rules':['dvesp_q0'],'target_strength':4.0,
 'type':'rebut','attack_succeeded':True,'explanation_pt':'A11 (10) prevalece sobre A9 (4) por weakest'}
```

Esse é o **único** conflito que a preferência resolve na camada, e é exatamente
o que `case.json:716` descreve. A estratificação, portanto, está corretamente
*montada* e nunca é *exercida*: a camada de causa de fato já havia resolvido o
caso (`¬r2` justificado, `ness(OmiEstatal,Danos)=False`), o que o próprio
`modelling_notes_pt` (`case.json:722`) reconhece.

Nota lateral: o `notes_pt` de `case.json:716` fala do conflito "⟨q0, q2⟩", mas o
`resolved_conflicts` atribui a força do lado vencedor a `dvgen_q1` (a regra
perfilhada; `dvgen_q2` não tem perfil). O par ⟨`dvesp_q0`, `dvgen_q2`⟩ é o do
rebut; ⟨`dvesp_q0`, `dvgen_q1`⟩ é o da comparação de força. Imprecisão de
redação, sem efeito.

---

## O que está fiel

- **A ponte usa o predicado certo.** NESS → `CaFa`, but-for → `ButFor`
  (`bridge.py:57-65`), conforme a eq. (1) e a Listing 3. Nenhum predicado
  trocado.
- **Os sete esquemas do artigo estão todos presentes e com a numeração certa**
  (`lrc.py:26-34`): 2=`cf2lrc`, 3=`nwo`, 4=`sc`, 5=`suca`, 6=`nofor`, 7=`rpl`,
  8=`unom`. As glosas em português descrevem corretamente os antecedentes de
  cada um.
- **Os cinco casos trabalhados do artigo reproduzem os vereditos publicados**
  (Kingston, Watson, R v Jordan, Berry, Yania, mais o contraste da leucemia),
  e com a base exata do artigo Kingston dá os **sete argumentos** anunciados.
- **`but_for` é uma transcrição exata da Def. 3.5** e do `checkButFor` da
  referência (`solver.py:724-751` × `CausalitySolver.kt:202-214`): ψ justificado
  antes, nenhum argumento *in* para ψ depois da intervenção `{¬φ}`.
- **A exceção-da-exceção funciona.** `rpl` undercuta `nofor` e reinstala
  `cf2lrc` quando o risco se concretiza — o mecanismo mais delicado da §5, e ele
  passa.
- **`Om`, `Obl`, `Tortious`, `Unexpected` estão corretamente unários**;
  `After`, `Foreseeable`, `ForeseeableRisk`, `Playout`, `CaFa`, `ButFor`,
  `LeReCa` corretamente binários (`lrc.py:61-68`). Só `SupersedingCause` erra.
- **`split_lrc_literal` resolve a ambiguidade de prefixo** que o vocabulário do
  artigo cria: `ForeseeableRisk_X_Y` não vira `Foreseeable` + `Risk_X`
  (`lrc.py:128`), e `scheme_of` não confunde `sc` com `suca` (`lrc.py:111`).
- **A convenção `¬PaCo → notPaCo`** cobre o caso da omissão do artigo
  (`CaFa(¬YaHe, BiDi)`, `CaFa(¬PaCo, ChDi)`), com ida e volta testada.
- **A fronteira de determinismo é real**: `bridge.evaluate` (`bridge.py:157-180`)
  roda o solver para cada par, e `premises()` só emite `CaFa_*` sob `fact.ness`
  — nenhum LLM pode inventar uma causa de fato. `test_lrc_bridge.py:66-79`
  cobre a recusa.
- **`but_for ⊆ ness` vale em 100% dos 103.583 pares testados** (repositório +
  aleatórios), coerente com a assimetria que o artigo descreve.
- **A suíte está verde**: 286 passed, 1 xfailed.
