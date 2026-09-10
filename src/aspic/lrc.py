"""Vocabulary and helpers for the legally-relevant-causation (LRC) layer of

    Pisano, Prakken & Sartor. "From Cause-in-Fact to Legally Relevant Cause
    through Argumentation." ICAIL 2026 (docs/papers/ICAIL2026causation.pdf).

The paper builds legal relevance as a *second* argumentation framework whose
knowledge base is the output of the cause-in-fact (CIF) evaluation: literals
`CaFa(phi, psi)` / `ButFor(phi, psi)` become premises, and rule schemes 2-8
derive `LeReCa(phi, psi)` or undercut it via one of the doctrinal defences.

`tests/test_legally_relevant_causes_2026.py` already hand-feeds exactly this
vocabulary for the paper's five worked examples; this module turns the naming
convention used there into code, so the formalization pipeline
(`formalize.bridge`) can derive the bridge premises from the solver instead of
asking an LLM to restate them.

Naming convention (taken verbatim from the tests): a literal becomes an
identifier fragment by dropping the negation sign and prefixing "not", so
`¬PaCo` -> `notPaCo` and `CaFa(¬PaCo, ChDi)` -> `CaFa_notPaCo_ChDi`.

O vocabulário
-------------

Doze predicados, e a divisão entre eles não é decorativa — ela diz **de onde
cada literal pode vir**, que é a fronteira de determinismo que este pipeline
existe para manter.

**Factuais — saída do solver, nunca de uma pessoa.**

``CaFa(φ, ψ)``
    φ é causa de fato de ψ. Escrita por `formalize.bridge` a partir de
    `ArgumentationFramework.ness_cause`. É a ponte entre as duas camadas: a
    segunda só raciocina sobre causas que a primeira reconheceu, e é isso que
    impede uma formalização de alegar relevância jurídica para algo que o
    teste contrafactual nunca estabeleceu.

``ButFor(φ, ψ)``
    sem φ, ψ não teria ocorrido de jeito nenhum (Def. 3.5). Estritamente mais
    forte que ``CaFa``: toda causa but-for é causa de fato, e a recíproca
    falha sob sobredeterminação e preempção. Entra como antecedente da
    caracterização da causa superveniente — o evento interposto só desloca a
    causa anterior se ele próprio for indispensável ao dano.

**Conclusão — o que a camada existe para decidir.**

``LeReCa(φ, ψ)``
    φ é causa de ψ que o direito imputa. A regra 2 a presume de ``CaFa``, e
    as regras 3, 4, 6 e 8 a afastam por *undercut* sobre essa presunção.

**Doutrinários — leitura do acórdão.**

``After(χ, φ)``
    o evento χ ocorreu depois de φ. Antecedente da regra 5: um evento que não
    é posterior não interrompe coisa nenhuma.

``Unexpected(χ)``
    χ era altamente inesperado. É o que separa uma causa superveniente de um
    desdobramento normal do que já estava em curso — sem isto, todo elo
    intermediário romperia o nexo.

``Tortious(χ)``
    χ é conduta ilícita. Aparece **negado** na regra 3: a defesa do "não
    estaria melhor" exige que a causa paralela seja *lícita*. Apontar uma
    causa paralela ilícita não desculpa ninguém — desculparia os dois.

``Foreseeable(φ, ψ)``
    ψ era previsível a partir de φ. Também aparece negado, na regra 6: é a
    *im*previsibilidade que afasta a relevância.

``ForeseeableRisk(φ, χ)`` e ``Playout(χ, ψ)``
    o par da regra 7, a exceção da exceção. O que se alega previsível não é o
    dano exato, é o **risco**: ``ForeseeableRisk`` diz que χ é um risco
    previsível de φ, ``Playout`` diz que o dano ψ é a concretização desse
    risco. Juntos desfazem a alegação de imprevisibilidade — o dano é
    justamente aquilo de que o risco era o risco.

``Om(φ)`` e ``Obl(¬φ)``
    o par da regra 8. ``Om`` diz que a conduta é uma *omissão*; sem isso a
    regra não se aplica, porque ela é sobre não fazer, não sobre fazer mal.
    Repare no argumento de ``Obl``: o artigo escreve ``¬Obl(¬φ)``, porque φ é
    a omissão e o dever recai sobre a **conduta omitida**, que é o
    complemento dela.

**Derivado — o único que a camada conclui em vez de receber pronto.**

``SupersedingCause(χ, φ, ψ)``
    χ é causa superveniente que rompe o nexo entre φ e ψ. A regra 5 o conclui
    (de ``CaFa``, ``ButFor``, ``After`` e ``Unexpected``) e a regra 4 o
    consome. É por isso que ele é o único predicado com regra dos dois lados.

    **Aridade.** O artigo o escreve com três argumentos (eqs. 4 e 5). Este
    repositório sempre escreveu a forma abreviada ``SupersedingCause_χ``,
    deixando φ e ψ implícitos na regra que consome o literal. As duas são
    aceitas por `split_lrc_literal`, e `PREDICATES` declara a do artigo
    primeiro; ver `docs/auditoria-icail2026.md`, D-3.

A tabela executável está em `PREDICATES`, e `predicate_reference()` a devolve
pronta para renderizar — de propósito, para que a explicação que o leitor vê
e o registro que o parser usa não possam divergir.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .solver import ArgumentationFramework

#: Rule-id prefixes of the paper's schemes, mapped to a plain-Portuguese name.
SCHEMES: Dict[str, str] = {
    "cf2lrc": "Esquema geral (regra 2): uma causa de fato é, presumidamente, causa juridicamente relevante.",
    "nwo": "Exceção do \"não estaria melhor\" / no-worse-off (regra 3): existe uma causa paralela não ilícita que teria produzido o mesmo dano.",
    "sc": "Causa superveniente (regra 4): um evento posterior interrompe o nexo de relevância jurídica.",
    "suca": "Caracterização da causa superveniente (regra 5): evento posterior, necessário e inesperado.",
    "nofor": "Imprevisibilidade (regra 6): o efeito não era previsível a partir da causa.",
    "rpl": "Concretização do risco / risk playout (regra 7): o efeito é a realização de um risco previsível da causa, o que afasta a imprevisibilidade.",
    "unom": "Omissão sem dever de agir (regra 8): a conduta omitida não era juridicamente obrigatória.",
}

#: Schemes the paper does not have, added for judgments that dispute the
#: *nature of the duty to act* rather than the causal mechanism. The ICAIL
#: 2026 module has a single on/off `Obl` premise, which is enough for its own
#: examples and not enough for a case whose whole ratio is that a duty of
#: custody degraded into a generic duty of public security over three months:
#: there, whether `Obl` holds is itself the conclusion of an argument, and the
#: conflict between the two answers is a *rebut* with no undercut on either
#: side -- the one place a preference has to decide (`aspic.preferences`).
#:
#: They are numbered on from the paper's 2-8 so a reader can see at a glance
#: which schemes come from it and which do not.
EXTENSION_SCHEMES: Dict[str, str] = {
    "dvesp": "Dever específico (regra 9, extensão): a condição concreta da custódia gera dever específico de agir, e não mero dever genérico.",
    "dvgen": "Dever genérico (regra 10, extensão): o lapso temporal e a atuação autônoma de terceiros degradam o dever específico em dever genérico de segurança pública, afastando aquele.",
    "dvpre": "Prevalência do dever específico (regra 11, extensão): subsistindo o dever específico de custódia, a defesa do ato de terceiro não se sustenta.",
    "u_corte": "Undercut ex officio (regra 12, extensão): a corte recusa a formulação da parte — o lapso temporal isolado não caracteriza ato de terceiro.",
    "q_reab": "Reabilitação por imediatidade (regra 13, extensão): premeditação contra alvo certo e sequência imediata entre a fuga e o crime afastam a caracterização do ato de terceiro.",
    "og": "Omissão genérica (regra 14, extensão): decorrido o tempo e interposta a deliberação autônoma de terceiros, a omissão estatal qualifica-se como genérica e não sustenta imputação.",
    "q11": "Ônus das cautelas (regra 15, extensão): não demonstradas as providências cabíveis, a alegação de ato de terceiro deduzida pela parte não se sustenta.",
}
SCHEMES.update(EXTENSION_SCHEMES)

#: Defence schemes: those that (directly or indirectly) block legal relevance.
#: `dvgen` is one: it does not undercut `cf2lrc` itself, it removes the duty
#: that `unom` needs to be absent, which is the same blocking move one step
#: earlier.
DEFENCE_SCHEMES: Set[str] = {"nwo", "sc", "suca", "nofor", "unom", "dvgen", "og"}

# ----------------------------------------------------------------------
# The vocabulary
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Predicate:
    """One predicate of the legal-relevance language.

    `arities` lists the argument counts a literal of this predicate may have,
    the paper's canonical one first. More than one entry means the repository
    also writes an abbreviated form -- see `SupersedingCause`.
    """
    name: str
    arities: Tuple[int, ...]
    roles: Tuple[str, ...]
    label_pt: str
    reading_pt: str
    source: str

    @property
    def arity(self) -> int:
        """A aridade canônica, a do artigo."""
        return self.arities[0]


#: Every predicate of the layer, with what each argument position means.
#:
#: Two families, and the difference decides where a literal may come from:
#:
#: * **factuais** (`CaFa`, `ButFor`) -- saída do solver da camada de causa de
#:   fato, escritas por `formalize.bridge` e nunca por uma pessoa. São a
#:   ponte entre as duas camadas: a segunda só raciocina sobre causas que a
#:   primeira reconheceu;
#: * **doutrinárias** (todas as demais) -- leitura do acórdão. Dizem o que o
#:   direito qualifica: houve dever de agir, o evento era inesperado, a
#:   conduta era ilícita.
#:
#: `LeReCa` é a única *conclusão*: é o que a camada existe para decidir.
PREDICATES: Tuple[Predicate, ...] = (
    Predicate(
        "CaFa", (2,), ("φ", "ψ"), "causa de fato",
        "φ é causa de fato de ψ. Vem do solver (`ness_cause`), não do "
        "acórdão: é a premissa que liga as duas camadas, e sem ela a "
        "presunção de relevância não tem sobre o que operar.",
        "eq. (1), ponte"),
    Predicate(
        "ButFor", (2,), ("φ", "ψ"), "causa \"não fosse por\"",
        "sem φ, ψ não teria ocorrido de jeito nenhum. Mais forte que `CaFa`: "
        "toda causa but-for é causa de fato, não o contrário. Também vem do "
        "solver, e é antecedente da caracterização da causa superveniente.",
        "Def. 3.5"),
    Predicate(
        "LeReCa", (2,), ("φ", "ψ"), "causa juridicamente relevante",
        "φ é causa de ψ que o direito imputa. É a **conclusão** da camada — "
        "o que os esquemas 2 a 8 estabelecem ou afastam.",
        "eq. (2)"),
    Predicate(
        "After", (2,), ("χ", "φ"), "posterioridade",
        "o evento χ ocorreu depois de φ. Antecedente da caracterização da "
        "causa superveniente: um evento que não é posterior não interrompe "
        "nada.",
        "eq. (5)"),
    Predicate(
        "Foreseeable", (2,), ("φ", "ψ"), "previsibilidade",
        "ψ era previsível a partir de φ. Aparece **negado** na regra 6: o que "
        "afasta a relevância é a imprevisibilidade, não a previsibilidade.",
        "eq. (6)"),
    Predicate(
        "ForeseeableRisk", (2,), ("φ", "χ"), "risco previsível",
        "χ é um risco previsível de φ. Primeiro antecedente da concretização "
        "do risco — o que se alega previsível é o risco, não o dano exato.",
        "eq. (7)"),
    Predicate(
        "Playout", (2,), ("χ", "ψ"), "concretização do risco",
        "ψ é a realização do risco χ. Com `ForeseeableRisk`, desfaz a "
        "alegação de imprevisibilidade: o dano é justamente aquilo de que o "
        "risco era o risco.",
        "eq. (7)"),
    Predicate(
        "Om", (1,), ("φ",), "omissão",
        "a conduta φ é uma omissão. Sem isto a regra 8 não se aplica: ela é "
        "sobre não fazer, não sobre fazer mal.",
        "eq. (8)"),
    Predicate(
        "Obl", (1,), ("¬φ",), "dever de agir",
        "a conduta era juridicamente obrigatória. Note o argumento: a regra 8 "
        "escreve `¬Obl(¬φ)`, porque φ é a *omissão* e o dever recai sobre a "
        "conduta omitida, que é o complemento dela.",
        "eq. (8)"),
    Predicate(
        "Tortious", (1,), ("χ",), "ilicitude",
        "χ é conduta ilícita. Aparece negado na regra 3: a defesa do \"não "
        "estaria melhor\" exige que a causa paralela seja **lícita** — se "
        "fosse ilícita, apontá-la não desculparia ninguém.",
        "eq. (3)"),
    Predicate(
        "Unexpected", (1,), ("χ",), "evento inesperado",
        "χ era um evento altamente inesperado. É o que distingue uma causa "
        "superveniente de um desdobramento normal do que já estava em curso.",
        "eq. (5)"),
    Predicate(
        # O artigo escreve `SupersedingCause(χ, φ, ψ)` (eqs. 4 e 5): o evento
        # que rompe, a causa que ele desloca e o dano. Este repositório sempre
        # escreveu só `SupersedingCause_χ`, deixando φ e ψ implícitos na regra
        # que consome o literal. As duas formas são aceitas, e a do artigo vem
        # primeiro porque é a que um leitor do artigo espera.
        "SupersedingCause", (3, 1), ("χ", "φ", "ψ"), "causa superveniente",
        "χ é causa superveniente que rompe o nexo entre φ e ψ. Concluída pela "
        "regra 5 e consumida pela regra 4 — é o único predicado que a camada "
        "**deriva** em vez de receber pronto.",
        "eqs. (4) e (5)"),
)

PREDICATE_BY_NAME: Dict[str, Predicate] = {p.name: p for p in PREDICATES}

#: Predicates of the LRC language that take two arguments, e.g. `CaFa_X_Y`.
BINARY_PREDICATES: Tuple[str, ...] = tuple(
    p.name for p in PREDICATES if p.arity == 2)

#: Predicates of the LRC language that take one argument, e.g. `Om_X`.
UNARY_PREDICATES: Tuple[str, ...] = tuple(
    p.name for p in PREDICATES if p.arity == 1)

#: Predicates the paper writes with three arguments.
TERNARY_PREDICATES: Tuple[str, ...] = tuple(
    p.name for p in PREDICATES if p.arity == 3)

#: The layer reasons over legal *qualifications*, and a judgment may qualify
#: a plain fact of the cause-in-fact layer directly ("the closed regime is
#: what makes the duty specific"). Such a premise carries no LRC predicate
#: and is not a vocabulary error; `is_lrc_literal` still reports False for it,
#: which is the honest answer, and callers that need a reading fall back to
#: the case's own atom glosses (`formalize.build.lrc_atom_glosses`).

ALL_PREDICATES: Tuple[str, ...] = tuple(p.name for p in PREDICATES)


def atom_token(literal: str) -> str:
    """Identifier fragment for `literal`: `¬PaCo` -> `notPaCo`, `PaCo` -> `PaCo`."""
    return f"not{literal[1:]}" if literal.startswith("¬") else literal


def token_atom(token: str) -> str:
    """Inverse of `atom_token`: `notPaCo` -> `¬PaCo`, `PaCo` -> `PaCo`."""
    return f"¬{token[3:]}" if token.startswith("not") and len(token) > 3 else token


def cafa(phi: str, psi: str) -> str:
    """`CaFa(phi, psi)`: phi is a cause in fact (NESS cause) of psi."""
    return f"CaFa_{atom_token(phi)}_{atom_token(psi)}"


def but_for(phi: str, psi: str) -> str:
    """`ButFor(phi, psi)`: phi is a but-for cause of psi (Definition 3.5)."""
    return f"ButFor_{atom_token(phi)}_{atom_token(psi)}"


def lereca(phi: str, psi: str) -> str:
    """`LeReCa(phi, psi)`: phi is a legally relevant cause of psi."""
    return f"LeReCa_{atom_token(phi)}_{atom_token(psi)}"


def scheme_of(rule_id: str) -> Optional[str]:
    """The scheme a rule id belongs to, e.g. `cf2lrc_notAtTe` -> `cf2lrc`.

    Longest-prefix match, so `cf2lrc` is never mistaken for `cf` and the
    bare ids used in the paper's own examples (`cf2lrc`, `unom`) also match.
    """
    for scheme in sorted(SCHEMES, key=len, reverse=True):
        if rule_id == scheme or rule_id.startswith(f"{scheme}_"):
            return scheme
    return None


def is_lrc_literal(literal: str) -> bool:
    """True for literals of the LRC language (ignoring any negation sign)."""
    base = literal[1:] if literal.startswith("¬") else literal
    return any(base.startswith(f"{p}_") for p in ALL_PREDICATES)


def split_lrc_literal(literal: str) -> Optional[Tuple[str, List[str]]]:
    """`CaFa_notPaCo_ChDi` -> `("CaFa", ["¬PaCo", "ChDi"])`, or None if the
    literal is not in the LRC language.

    Longest-prefix match, so `ForeseeableRisk_X_Y` never parses as
    `Foreseeable` + `Risk_X`. A predicate may declare more than one arity
    (`Predicate.arities`) and each is tried in turn, the paper's canonical
    one first: `SupersedingCause` is ternary in equations 4 and 5, and this
    repository has always written the abbreviated unary form.
    """
    base = literal[1:] if literal.startswith("¬") else literal
    for predicate in sorted(ALL_PREDICATES, key=len, reverse=True):
        prefix = f"{predicate}_"
        if not base.startswith(prefix):
            continue
        rest = base[len(prefix):]
        for arity in PREDICATE_BY_NAME[predicate].arities:
            parts = rest.split("_", arity - 1) if arity > 1 else [rest]
            if len(parts) == arity and all(parts):
                return predicate, [token_atom(part) for part in parts]
        return None
    return None


def predicate_reference() -> List[Dict[str, object]]:
    """The vocabulary as data, for rendering.

    Kept here rather than in the view so that the reference a reader sees and
    the registry the parser uses cannot drift apart -- a documentation table
    typed out by hand is a table that goes stale on the first arity change.
    """
    return [
        {
            "name": p.name,
            "arity": p.arity,
            "arities": list(p.arities),
            "shape": f"{p.name}_" + "_".join(p.roles[:p.arity]),
            "roles": list(p.roles[:p.arity]),
            "label_pt": p.label_pt,
            "reading_pt": p.reading_pt,
            "source": p.source,
            "kind": ("factual" if p.name in ("CaFa", "ButFor")
                     else "conclusao" if p.name == "LeReCa"
                     else "derivado" if p.name == "SupersedingCause"
                     else "doutrinario"),
        }
        for p in PREDICATES
    ]


def build_framework(knowledge_base: Dict, causal_model: Dict,
                    preferences=None) -> ArgumentationFramework:
    """The LRC module as an ordinary ASPIC+ framework. Kept as a named
    function so callers read as the paper does ("a second framework whose
    knowledge base results from the cause-in-fact evaluation") rather than
    constructing a bare `ArgumentationFramework` and leaving the reader to
    infer which layer it belongs to.

    `preferences` is the same optional `aspic.preferences.PreferenceModel`
    the cause-in-fact layer takes. It matters more here: the paper's own
    schemes conflict by undercutting, which no preference touches, but a
    layer that also decides *which qualification holds* conflicts by
    rebutting, and there the ordering is what settles it."""
    return ArgumentationFramework(knowledge_base, causal_model,
                                  preferences=preferences)


def relevance_report(af: ArgumentationFramework, targets: List[str]) -> List[Dict]:
    """For each `LeReCa_*` target: whether it stands, and if not, why not.

    Three outcomes, not two, and the distinction is the whole point:

    * **reconhecida** -- the target is a justified conclusion;
    * **afastada** -- some argument for it was built and an accepted argument
      defeated it. `blocked_by` names them, with the doctrinal scheme;
    * **não formulada** -- *no argument for it exists at all*, because the
      rule that would derive it never fired. Nothing blocked it; the claim
      was never made.

    The third used to be reported as the second. `case-003-final` published
    `LeReCa_OmiEstatal_Danos` as blocked by `sc` and `unom` when in truth
    `cf2lrc_q5` had no antecedent -- the cause-in-fact layer had already
    denied `CaFa_OmiEstatal_Danos`, so the presumption never applied. Reading
    that record, one would credit the doctrinal defences with a result the
    facts had produced on their own. The defences *were* in the framework and
    *would* have blocked it; they just never got the chance.

    Blockers are read off the framework's own defeats rather than off rule
    syntax, so a defence that wins by **rebutting** or **undermining** counts
    too. The previous version only looked for accepted arguments concluding
    `¬<rule id>`, which is undercutting alone -- and undercutting is exactly
    what a preference cannot decide (`aspic.preferences`), so the layer went
    blind precisely where the weights do their work.
    """
    extension, _ = af.compute_grounded_extension()
    justified = af.justified_conclusions()

    def scheme_of_argument(argument) -> Optional[str]:
        scheme = None
        for used in argument.defeasible_rules + argument.strict_rules:
            scheme = scheme_of(used) or scheme
        return scheme

    report = []
    for target in targets:
        arguments = [arg for arg in af.arguments.values()
                     if arg.conclusion == target]
        blockers = []
        seen = set()
        for argument in arguments:
            if argument.id in extension:
                continue
            for defeat in af.defeats:
                attack = defeat.attack
                if attack.target_id != argument.id:
                    continue
                if attack.attacker_id not in extension:
                    continue
                key = (attack.attacker_id, argument.id, attack.attack_type)
                if key in seen:
                    continue
                seen.add(key)
                attacker = af.arguments[attack.attacker_id]
                scheme = scheme_of_argument(attacker)
                blockers.append({
                    "undercut_rule": attack.rule_id,
                    "attacker": attacker.id,
                    "attacker_rules": sorted(attacker.defeasible_rules
                                             + attacker.strict_rules),
                    "attacked_argument": argument.id,
                    "attack_type": attack.attack_type,
                    "scheme": scheme,
                    "scheme_pt": SCHEMES.get(scheme, "") if scheme else "",
                })
        if target in justified:
            status = "reconhecida"
        elif arguments:
            status = "afastada"
        else:
            status = "nao_formulada"
        report.append({
            "target": target,
            "justified": target in justified,
            "derivable": bool(arguments),
            "status": status,
            "blocked_by": blockers,
        })
    return report
