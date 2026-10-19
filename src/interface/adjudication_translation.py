"""Translates exported adjudication figures into English.
Consumes the DOT produced by `analysis.perspectives`; used by
`scripts.render_translated` before writing the standalone SVG and PDF.
"""

"""English presentation of the Case 003 adjudication map.

Translations apply to the generated figure, leaving the executable record
and live application's Portuguese presentation intact. Atom display names
follow the article's vocabulary. Rule identifiers and attack numbers remain
unchanged so the figure can be traced back to the case record.
"""
import html
import re
import textwrap

from interface.graph_export import _dot_escape


_GLOSSES = {
    "A omissão do Estado na custódia levou à fuga do preso.":
        "The State's omission in custody led to the prisoner's escape.",
    "A omissão do Estado sobre quem cumpria regime fechado — e portanto sob custódia estrita — levou à fuga.":
        "The State's omission concerning a prisoner under a closed regime, and thus strict custody, led to the escape.",
    "A fuga do detento levou ao latrocínio praticado contra a vítima.":
        "The prisoner's escape led to the robbery-homicide against the victim.",
    "O latrocínio resultou na morte da vítima.":
        "The robbery-homicide resulted in the victim's death.",
    "A morte da vítima causou danos materiais e morais à sua família.":
        "The victim's death caused material and moral damages to the family.",
    "Cumprindo o preso regime fechado, o dever do Estado sobre ele é específico de custódia, e não o dever difuso de segurança pública.":
        "A prisoner under a closed regime is subject to the State's specific duty of custody, rather than its general duty of public security.",
    "Alegação de parte: decorridos três meses, o crime é ato de terceiro. Vence na fase preliminar por default dialético — falta de réplica eficaz —, não por mérito dogmático.":
        "Party claim: after three months, the crime is a third-party act. It prevails in the preliminary phase by dialectical default, with no effective reply, rather than on doctrinal merits.",
    "A corte recusa expressamente a tese de que o tempo isolado rompe a causalidade: o mero lapso não autoriza, por si só, a caracterização do ato de terceiro.":
        "The court expressly rejects the claim that time alone breaks causation: elapsed time does not by itself establish a superseding third-party act.",
    "Ratio decidendi: o lapso temporal somado ao concurso de agentes superveniente e independente constitui ato de terceiro.":
        "Ratio decidendi: elapsed time together with subsequent, independent joint action constitutes a third-party act.",
    "Distinguishing do RE 136.247: houvesse premeditação contra alvo certo e sequência imediata entre a fuga e o crime, a caracterização do ato de terceiro não se sustentaria.":
        "Distinguishing RE 136.247: premeditation against a specific target and an immediate sequence between escape and crime would defeat the characterization as a third-party act.",
    "Sendo a omissão estatal causa de fato dos danos, presume-se que seja causa juridicamente relevante deles.":
        "If the State's omission is a cause in fact of the damages, it is presumed to be a legally relevant cause.",
    "Sendo o crime ato de terceiro, rompe-se o nexo de relevância jurídica entre a omissão e os danos.":
        "If the crime is a third-party act, it breaks the legally relevant causal connection between the omission and the damages.",
    "Subsistindo o dever específico de custódia, não se sustenta a defesa do ato de terceiro: o risco que se concretizou é exatamente o que o dever existia para conter.":
        "If the specific duty of custody stands, the third-party-act defence fails: the realized risk is precisely what that duty was intended to prevent.",
    "Decorrido o tempo e interposta a deliberação autônoma da quadrilha, a omissão estatal já não é específica àquele resultado: qualifica-se como genérica.":
        "After elapsed time and the gang's autonomous deliberation, the State's omission is no longer specific to that outcome: it is qualified as generic.",
    "Omissão genérica não é liame necessário nem determinante do resultado: não sustenta a presunção de relevância jurídica.":
        "Generic omission is neither a necessary nor a determining link to the outcome: it does not sustain the presumption of legal relevance.",
    "Não tendo o Estado demonstrado as providências cabíveis, não se sustenta a alegação de ato de terceiro deduzida por ele.":
        "Without evidence of due precautions by the State, its claim of a third-party act fails.",
}

_TEXT = {
    "Barra: aplicação da regra contestada.": "Bar: rule applicability challenged.",
    "Pontilhado: ataque potencial, sem argumento.": "Dotted: potential attack; no argument instantiated.",
    "Caso 003 — Responsabilidade do Estado por crime de foragido (formalização final, por votos)":
        "Case 003 — State liability for a fugitive's crime",
    "LEGENDA — OS ATAQUES E O DESFECHO": "LEGEND — ATTACKS AND OUTCOMES",
    "ADJUDICADORES": "ADJUDICATORS", "PARTES": "PARTIES",
    "INCONTROVERSO": "UNDISPUTED",
    "VOTO CONVERGENTE": "CONCURRING OPINION", "VOTO DIVERGENTE": "DISSENTING OPINION",
    "RELATOR": "REPORTING JUDGE", "RECORRENTE": "APPELLANT", "RECORRIDO": "RESPONDENT",
    "Voto convergente": "Concurring opinion", "Voto divergente": "Dissenting opinion",
    "Relator": "Reporting judge", "Recorrente": "Appellant", "Recorrido": "Respondent",
    "adota na decisão": "adopts during decision", "argumentação": "argumentation", "decisão": "decision",
    "prevalece na argumentação sem réplica das partes": "prevails unanswered during argumentation",
    "fora da base fática — nenhum argumento se constrói": "outside the factual base; no argument",
    "não subsiste: afastado na decisão": "defeated during decision",
    "sem receber resposta": "without a reply", "sai da extensão fundada": "leaves the grounded extension",
    "decisivo: afasta": "decisive: defeats", "prevalece: afasta": "prevails: defeats",
    "não afasta": "does not defeat", "inerte:": "inert:",
    " por ": " by ",
    "quem move": "mover", "lance": "move", "desfecho na extensão fundada": "outcome in the grounded extension",
    "nº": "No.",
    "elipse vermelha: lance afastado": "red ellipse: defeated move",
    "perspectivas por conta própria": "perspectives independently",
    "sustentado por N": "supported by N", "N vozes": "N voices",
    "todos os ataques do caso estão no mapa; argumentos individuais não são desenhados":
        "all case attacks are shown; individual arguments are not drawn",
    "ataque que subsiste": "Standing attack", "lance decisivo": "Decisive attack",
    "autor do ataque afastado": "Attacking move defeated", "ataque inerte": "Inert attack",
    "sustentação e ponte entre camadas": "Support / bridge",
    "ataque à perspectiva que também sustenta o lance": "Co-holder attack",
    "regra da camada jurídica": "Legal-relevance rule",
    "regra afastada": "Defeated rule", "camada de fato sem ataques": "Attack-free CIF layer",
    "regra sem argumento": "Uninstantiated rule", "N perspectivas independentes": "N independent perspectives",
    "causa(OmiEstatal)": "CaFa(StateOmis, Damages)",
    "relevante(OmiEstatal)": "LeReCa(StateOmis, Damages)",
    "Sustentada também por:": "Also supported by:", "Alimentada por": "Supported by",
    "Inerte: os antecedentes nunca foram satisfeitos.": "Inert: the antecedents were never satisfied.",
    "camada de causa de fato": "cause-in-fact layer", "cadeia causal até": "causal chain to",
    "nenhum ataque": "no attacks", "o resultado": "the outcome",
    "A camada de causa de fato não contém ataque nenhum; toda a controvérsia do caso é de imputação. As regras dela:":
        "The cause-in-fact layer contains no attacks; all controversy concerns legal attribution. Its rules:",
    "incontroversa": "undisputed",
    "sustenta": "supports", "lance(s)": "move(s)", "na caixa de outro titular": "in another holder's box",
    "move só regras sem ataque": "only makes attack-free moves", "sem movimento": "no move",
    "A causa de fato justificada na camada de fato entra como axioma no antecedente de":
        "The cause in fact justified in the factual layer enters as an axiom in the antecedent of",
    "ponte": "bridge", "ninguém": "nobody", "Desfecho:": "Outcome:",
    "atinge": "attacks", "que": "which", "também": "also",
    "vozes": "voices", "inerte": "inert", "afasta": "defeats", "adjudicação": "adjudication",
    "causa(": "cause(", "só-por(": "but-for(", "relevante(": "relevant(",
    "omissão(": "omission(", "dever(": "duty(", "ilícito(": "tortious(",
    "inesperado(": "unexpected(", "superveniente(": "superseding(",
    "previsível(": "foreseeable(", "risco(": "risk(", "concretiza(": "playout(",
    "OmiEstatal": "StateOmis", "RegFechado": "ClosedReg", "FugaPreso": "PrisEscape",
    "Latrocinio": "RobHomicide", "MorteVitima": "VictimDeath", "Danos": "Damages",
    "LapsoTemp": "TimeLapse", "FormacaoQuad": "GangForm", "DeverEspec": "SpecDuty",
    "AtoTerceiro": "ThirdParty", "OmissaoGen": "GenOmission", "PremedAlvo": "TargetPremed",
    "SeqImediata": "ImmedSeq", "ProvCabiveis": "DueMeasures", "MeiosDisp": "MeansAvail",
}


def translate_adjudication_dot(dot: str) -> str:
    """Translate the exported Case 003 figure's labels and SVG tooltips."""
    for source, target in sorted(_GLOSSES.items(), key=lambda item: -len(item[0])):
        dot = dot.replace(_dot_escape(source), _dot_escape(target))
    for source, target in sorted(_TEXT.items(), key=lambda item: -len(item[0])):
        source, target = _dot_escape(source), _dot_escape(target)
        if source.isalpha() and not source[0].isupper():
            dot = re.sub(r"(?:(?<![A-Za-zÀ-ÿ])|(?<=\\n))" + re.escape(source)
                         + r"(?![A-Za-zÀ-ÿ])", lambda _: target, dot)
        else:
            dot = dot.replace(source, target)
    # Translate complete sentences before wrapping, so a line break cannot
    # interrupt a phrase lookup. Only plain-text legend cells are wrapped.
    def wrap_cell(match):
        content = html.unescape(match.group(1))
        if len(content) <= 60:
            return match.group(0)
        width = 38 if "opinion" in content or "Reporting judge" in content else 60
        content = '<BR ALIGN="LEFT"/>'.join(
            html.escape(line) for line in textwrap.wrap(content, width))
        return f'<TD ALIGN="LEFT">{content}</TD>'

    return re.sub(r'<TD ALIGN="LEFT">([^<>]*)</TD>', wrap_cell, dot)
