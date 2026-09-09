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

**CIF — fatos e eventos**

```
OmiEstatal            o Estado foi omisso na custódia do preso
RegFechado            o preso cumpria regime prisional fechado
FugaPreso             o detento fugiu do sistema prisional
LapsoTemporal         o crime foi praticado após 3 meses da fuga
FormacaoQuad          o crime foi praticado em concurso de agentes (quadrilha)
Latrocinio            a quadrilha praticou roubo seguido de morte contra a vítima
MorteVitima           a vítima foi morta em decorrência de latrocínio
Danos                 a família da vítima sofreu danos materiais e morais
ProvidenciasCabiveis  o Estado adotou as providências cabíveis
MeiosDisponiveis      o Estado teve meios disponíveis para agir
```

**LRC — qualificações jurídicas**

```
DeverEspec            o Estado tinha um dever específico de custódia sobre o preso
DeverGener            o Estado tinha um dever genérico de segurança pública
AtoTerceiro           o crime praticado após a fuga é ato de terceiro
```

---

## CIF

### Inventário de regras

```
r0 : OmiEstatal                   ⇒ FugaPreso      [RDO_]
r1 : OmiEstatal ∧ RegFechado      ⇒ FugaPreso      [MA_, EF_]
r2 : FugaPreso                    ⇒ Latrocinio     [RDO_, MA_, EF_]
r3 : Latrocinio                   ⇒ MorteVitima    [RDO_, MA_, EF_, RTE_, AM_]
r4 : MorteVitima                  ⇒ Danos          [RDO_, MA_, EF_, RTE_, AM_]
r5 : LapsoTemporal                ⇒ ¬r2            [RTE_]
r6 : LapsoTemporal ∧ FormacaoQuad ⇒ Latrocinio     [AM_]
r7 : LapsoTemporal ∧ FormacaoQuad ⇒ ¬r2            [AM_]
r8 : ¬ProvidenciasCabiveis        ⇒ ¬r5            [EF_]
```

### Por perspectiva

**RDO_ (Recorrido)**

```
Premissas   OmiEstatal, RegFechado
Regras      r0, r2, r3, r4
```

**RTE_ (Recorrente)**

```
Premissas   FugaPreso, LapsoTemporal, Latrocinio
Regras      r3, r4, r5
```

**MA_ (Marco Aurélio — relator)**

```
Premissas   OmiEstatal, RegFechado
Regras      r1, r2, r3, r4
```

**EF_ (Edson Fachin)**

```
Premissas   OmiEstatal, RegFechado, ¬ProvidenciasCabiveis, ¬MeiosDisponiveis
Regras      r1, r2, r3, r4, r8
```

**AM_ (Alexandre de Moraes)**

```
Premissas   OmiEstatal, FugaPreso, LapsoTemporal, FormacaoQuad
Regras      r3, r4, r6, r7
```

### Grafo de ataques

```
FASE DE ARGUMENTAÇÃO — partes

  RTE_    r5  ⇏  r2        undercutting

FASE DE DECISÃO — adjudicadores

  MA_     —
  EF_     r8  ⇏  r5        undercutting
  AM_     r7  ⇏  r2        undercutting
```

### Pontos sensíveis a preferência

```
nenhum — todos os ataques do CIF são undercutting
```

---

## LRC

### Inventário de regras

```
q0 : RegFechado                                 ⇒ DeverEspec                 [EF_]
q1 : LapsoTemporal ∧ FormacaoQuad               ⇒ DeverGener                 [EF_]
q2 : DeverGener                                 ⇒ ¬DeverEspec                [EF_]
q3 : Latrocinio ∧ LapsoTemporal                 ⇒ DeverGener                 [EF_]
q4 : Latrocinio ∧ LapsoTemporal ∧ FormacaoQuad  ⇒ AtoTerceiro                [AM_]
q5 : caFa(OmiEstatal, Danos)                    ⇒ leReCa(OmiEstatal, Danos)  [RDO_, MA_, EF_]
q6 : AtoTerceiro                                ⇒ ¬q5                        [RTE_, AM_]
q7 : OmiEstatal ∧ ¬DeverEspec                   ⇒ ¬q5                        [EF_]
q8 : DeverEspec                                 ⇒ ¬q6                        [EF_]
```

### Por perspectiva

**RDO_ (Recorrido)**

```
Premissas   —
Regras      q5
```

**RTE_ (Recorrente)**

```
Premissas   —
Regras      q6
```

**MA_ (Marco Aurélio — relator)**

```
Premissas   AtoTerceiro
Regras      q5
```

**EF_ (Edson Fachin)**

```
Premissas   —
Regras      q0, q1, q2, q3, q5, q7, q8
```

**AM_ (Alexandre de Moraes)**

```
Premissas   —
Regras      q4, q6
```

### Grafo de ataques

```
FASE DE ARGUMENTAÇÃO — partes

  RTE_    q6  ⇏  q5        undercutting

FASE DE DECISÃO — adjudicadores

  MA_     —
  EF_     q2  ⤅  q0        rebutting
          q7  ⇏  q5        undercutting
          q8  ⇏  q6        undercutting
  AM_     q6  ⇏  q5        undercutting
```

### Estratificação

```
L1   q5            presunção de relevância
L2   q6, q7        defesas
L3   q8            exceção da exceção
```

### Pontos sensíveis a preferência

```
⟨q0, q2⟩   DeverEspec × ¬DeverEspec        rebutting — único ponto ativo
```
