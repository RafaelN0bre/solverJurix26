---
pdf:
  titulo: "Formalização — Caso 003"
  subtitulo: "Responsabilidade do Estado por crime de foragido"
  autor: "Rafael Nobre"
  data: "2026-09-07"
  saida: "docs/formalização.pdf"
  remover: "andaime"
---

# Formalização — Caso 003

## Legenda

**Perspectivas**

```
RTE_ (Recorrente — Estado MT)          parte
RDO_ (Recorrido — Família da Vítima)   parte
MA_  (Marco Aurélio — relator)         adjudicador
EF_  (Edson Fachin)                    adjudicador
AM_  (Alexandre de Moraes)             adjudicador
```

**Regras** — camada da teoria

```
→    regra estrita
⇒    regra derrotável
```

**Ataques** — camada do grafo, derivados das conclusões

```
↣    Undermining     ataca premissa
⤅    Rebutting       ataca conclusão
⇏    Undercutting    ataca regra
```

---

## Átomos

**CIF — mecanismo causal de fato**

```
OmiEstatal   o Estado foi omisso na custódia do preso
RegFechado   o preso cumpria regime prisional fechado
FugaPreso    o detento fugiu do sistema prisional
Latrocinio   o foragido praticou roubo seguido de morte contra a vítima
MorteVitima  a vítima foi morta em decorrência de latrocínio
Danos        a família da vítima sofreu danos materiais e morais
```

**LRC — qualificações jurídicas e imputação**

```
LapsoTemporal         o crime foi praticado após três meses da fuga
FormacaoQuad          o crime foi praticado em concurso de agentes (quadrilha)
DeverEspec            o Estado tinha um dever específico de custódia sobre o preso
OmissaoGenerica       a omissão estatal qualifica-se como genérica diante do tempo e do concurso
AtoTerceiro           o crime praticado após a fuga é ato de terceiro (causa superveniente independente)
PremedAlvo            o crime contra alvo específico foi premeditado antes da fuga (RE 136.247)
SeqImediata           houve sequência lógica e imediata entre a fuga e o crime (RE 136.247)
ProvidenciasCabiveis  o Estado adotou as providências cabíveis para evitar a fuga
MeiosDisponiveis      o Estado teve meios materiais disponíveis para agir
```

`PremedAlvo` e `SeqImediata` estão no vocabulário e fora da base fática: são o
distinguishing do RE 136.247, que a teoria do acórdão usa e que estes autos não
realizam.

---

## CIF

### Inventário de regras

```
r0 : OmiEstatal               ⇒ FugaPreso    [RDO_]
r1 : OmiEstatal ∧ RegFechado  ⇒ FugaPreso    [MA_, EF_, AM_]
r2 : FugaPreso                ⇒ Latrocinio   [RDO_, MA_, EF_, RTE_, AM_]
r3 : Latrocinio               ⇒ MorteVitima  [RDO_, MA_, EF_, RTE_, AM_]
r4 : MorteVitima              ⇒ Danos        [RDO_, MA_, EF_, RTE_, AM_]
```

### Por perspectiva

**RDO_ (Recorrido)**

```
Premissas   OmiEstatal, RegFechado
Regras      r0, r2, r3, r4
```

**RTE_ (Recorrente)**

```
Premissas   —
Regras      r2, r3, r4
```

**MA_ (Marco Aurélio — relator)**

```
Premissas   OmiEstatal, RegFechado
Regras      r1, r2, r3, r4
```

**EF_ (Edson Fachin)**

```
Premissas   OmiEstatal, RegFechado
Regras      r1, r2, r3, r4
```

**AM_ (Alexandre de Moraes)**

```
Premissas   OmiEstatal
Regras      r1, r2, r3, r4
```

### Grafo de ataques

```
nenhum — a camada é puramente mecânica; toda a controvérsia passou à LRC

saída   caFa(OmiEstatal, Danos) = true
```

### Pontos sensíveis a preferência

```
nenhum — não há ataques nesta camada
```

---

## LRC

### Inventário de regras

```
dvesp_q0  : RegFechado                                 ⇒ DeverEspec               [RDO_, MA_, EF_]
suca_q3   : LapsoTemporal                              ⇒ AtoTerceiro              [RTE_]
u_corte   : LapsoTemporal                              ⇒ ¬suca_q3                 [AM_]
suca_q4   : Latrocinio ∧ LapsoTemporal ∧ FormacaoQuad  ⇒ AtoTerceiro              [AM_]
q_reab    : PremedAlvo ∧ SeqImediata                   ⇒ ¬suca_q4                 [AM_]
cf2lrc_q5 : CaFa_OmiEstatal_Danos                      ⇒ LeReCa_OmiEstatal_Danos  [RDO_, MA_, EF_]
sc_q6     : AtoTerceiro                                ⇒ ¬cf2lrc_q5               [RTE_, AM_]
dvpre_q8  : DeverEspec                                 ⇒ ¬sc_q6                   [MA_, EF_]
og_q9     : OmiEstatal ∧ LapsoTemporal ∧ FormacaoQuad  ⇒ OmissaoGenerica          [AM_]
og_q10    : OmissaoGenerica                            ⇒ ¬cf2lrc_q5               [AM_]
q11       : ¬ProvidenciasCabiveis                      ⇒ ¬suca_q3                 [EF_]
```

### Por perspectiva

**RDO_ (Recorrido)**

```
Premissas   OmiEstatal, RegFechado, Latrocinio
Regras      dvesp_q0, cf2lrc_q5
```

**RTE_ (Recorrente)**

```
Premissas   LapsoTemporal, Latrocinio
Regras      suca_q3, sc_q6
```

**MA_ (Marco Aurélio — relator)**

```
Premissas   OmiEstatal, RegFechado, Latrocinio
Regras      dvesp_q0, cf2lrc_q5, dvpre_q8
```

**EF_ (Edson Fachin)**

```
Premissas   OmiEstatal, RegFechado, Latrocinio, ¬ProvidenciasCabiveis
Regras      dvesp_q0, cf2lrc_q5, dvpre_q8, q11
```

**AM_ (Alexandre de Moraes)**

```
Premissas   OmiEstatal, LapsoTemporal, FormacaoQuad, Latrocinio
Regras      u_corte, suca_q4, q_reab, sc_q6, og_q9, og_q10
```

### Grafo de ataques

```
FASE DE ARGUMENTAÇÃO — partes

  RTE_    suca_q3 + sc_q6  ⇏  cf2lrc_q5   undercutting
                                          (prevalece por default dialético)

FASE DE DECISÃO — adjudicadores

  MA_     dvpre_q8         ⇏  sc_q6       undercutting
  EF_     dvpre_q8         ⇏  sc_q6       undercutting
          q11              ⇏  suca_q3     undercutting
  AM_     u_corte          ⇏  suca_q3     undercutting
          suca_q4 + sc_q6  ⇏  cf2lrc_q5   undercutting   (Caminho 1)
          og_q9 + og_q10   ⇏  cf2lrc_q5   undercutting   (Caminho 2)
          q_reab           ⇏  suca_q4     undercutting   (inerte neste caso)
```

### Pontos sensíveis a preferência

```
nenhum — todos os ataques são undercutting; a teoria é livre de pesos
```
