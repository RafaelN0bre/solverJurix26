## Camada de relevância jurídica (ICAIL 2026) — vocabulário e esquemas

Esta é a **segunda** camada do artigo "From Cause-in-Fact to Legally Relevant
Cause through Argumentation" (Pisano, Prakken & Sartor, ICAIL 2026). Ela é um
framework de argumentação independente, cuja base de conhecimento recebe o
**resultado já calculado** da camada de causa de fato.

Ser causa de fato é condição **necessária, não suficiente**, da
responsabilidade: o esquema geral presume a relevância jurídica e cada defesa
doutrinária a derruba por undercut.

### Convenção de nomes

Um literal vira um pedaço de identificador perdendo o `¬` e ganhando o prefixo
`not`: `¬AtdTemp` vira `notAtdTemp`. Então `CaFa(¬AtdTemp, SeqIrr)` se escreve
`CaFa_notAtdTemp_SeqIrr`.

### Predicados

Já fornecidos (não reescreva, não invente):

- `CaFa_<causa>_<efeito>` — a causa é causa de fato (NESS) do efeito.
- `ButFor_<causa>_<efeito>` — a causa é causa "não fosse por" do efeito.

Que você deve fornecer, quando o acórdão os sustentar:

- `Om_<causa>` — a causa é uma **omissão** (conduta que deixou de ser praticada).
- `Obl_<conduta>` / `¬Obl_<conduta>` — a conduta omitida **era** (ou **não era**)
  juridicamente obrigatória. É aqui que entra o dever jurídico de agir.
- `Tortious_<causa>` / `¬Tortious_<causa>` — a causa é (ou não é) ilícita.
- `Unexpected_<evento>` — o evento era altamente inesperado.
- `After_<posterior>_<anterior>` — o primeiro ocorreu depois do segundo.
- `ForeseeableRisk_<causa>_<risco>` — o risco é previsível a partir da causa.
- `Playout_<risco>_<efeito>` — o efeito é a concretização daquele risco.
- `¬Foreseeable_<causa>_<efeito>` — o efeito não era previsível a partir da causa.

Conclusões:

- `LeReCa_<causa>_<efeito>` — a causa é **juridicamente relevante** para o efeito.
- `SupersedingCause_<evento>` — o evento é causa superveniente.

### Esquemas de regra (regras 2 a 8 do artigo)

Os identificadores das regras têm que começar pelo nome do esquema, seguido de
`_` e um sufixo que identifique a causa. Ex.: `cf2lrc_notAtdTemp`.

**Regra 2 — esquema geral (`cf2lrc`).** Toda causa de fato é presumidamente
causa juridicamente relevante. Emita uma destas para **cada** `CaFa_*` fornecido.

```
cf2lrc_X: CaFa_X_Y => LeReCa_X_Y
```

**Regra 3 — não estaria melhor / no-worse-off (`nwo`).** Existe uma causa
paralela não ilícita que sozinha já produziria o mesmo dano.

```
nwo_X: CaFa_Z_Y AND ¬Tortious_Z => ¬cf2lrc_X
```

**Regra 5 — caracterização da causa superveniente (`suca`).** Evento posterior,
necessário e inesperado.

```
suca_Z: CaFa_X_Y AND CaFa_Z_Y AND After_Z_X AND Unexpected_Z AND ButFor_Z_Y => SupersedingCause_Z
```

**Regra 4 — causa superveniente (`sc`).** A causa superveniente derruba a
relevância da causa anterior.

```
sc_X: SupersedingCause_Z => ¬cf2lrc_X
```

**Regra 6 — imprevisibilidade (`nofor`).** O efeito não era previsível.

```
nofor_X: ¬Foreseeable_X_Y => ¬cf2lrc_X
```

**Regra 7 — concretização do risco (`rpl`).** Se o efeito é a concretização de
um risco previsível da causa, a imprevisibilidade não se sustenta — este
esquema ataca a regra `nofor`, não a `cf2lrc`.

```
rpl_X: ForeseeableRisk_X_R AND Playout_R_Y => ¬nofor_X
```

**Regra 8 — omissão sem dever de agir (`unom`).** Uma omissão só é
juridicamente relevante se a conduta omitida era obrigatória.

```
unom_X: Om_X AND ¬Obl_A => ¬cf2lrc_X
```

Atenção ao sentido desta última: escreva a regra `unom` sempre com `¬Obl_A` no
antecedente. Se **existe** dever de agir, você fornece a premissa `Obl_A` (e não
`¬Obl_A`), o antecedente não é satisfeito, a regra não dispara, e a omissão
**permanece** juridicamente relevante. Se **não existe** dever, você fornece
`¬Obl_A`, a regra dispara e a relevância cai. Nos dois casos a regra `unom` é
escrita da mesma forma — o que muda é a premissa.
