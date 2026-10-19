"""Renders the Arquitetura tab: the case's CIF/LRC blocks, the bridges
between them and the execution order, read from `case.json` itself. Consumes
the record via `cases.catalog`; appears in the live app and in the static
report.
"""

"""The case's architecture at a high level: the blocks, and what passes
between them.

Two layers, run in the ICAIL 2026 order `CIF → LRC`: what the first hands
the second enters as an **axiom** (equation 1: `CaFa(φ,ψ) ∈ K𝑛(LRC)`), not as
an attackable premise, and that is what fixes the boundary between
fact-finding and qualifying.

The drawing is generated from the record, not written by hand: each block's
rules, the literals that cross and the final verdict come from `case.json`
itself, so an out-of-date diagram is impossible.
"""
from typing import List

#: Geometry. One box per phase, stacked, with the labelled arrow in between.
BOX_W, BOX_H, GAP, PAD = 640, 96, 74, 16
LABEL_DX = 18


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _wrap(items: List[str], width: int = 74) -> List[str]:
    """A block's ids, wrapped into lines that fit inside the box."""
    lines, current = [], ""
    for item in items:
        candidate = f"{current}  {item}" if current else item
        if len(candidate) > width:
            lines.append(current)
            current = item
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or ["—"]


def _rule_ids(rules) -> List[str]:
    return [rule.rule.split(":", 1)[0].strip() for rule in rules]


def _phases(record) -> List[dict]:
    """The phases, in execution order, with what each hands to the next."""
    cif_ids = [meta.id for meta in record.rules_meta]
    cif = {
        "tag": "CIF",
        "title": "causa de fato",
        "sub": "o mecanismo: quem produziu o quê",
        "rules": cif_ids,
    }
    if record.lrc is None or not record.lrc.scheme_rules:
        return [cif]

    bridge_axioms = [a for a in record.lrc.knowledge_base.get("axioms", [])
                     if a.startswith(("CaFa_", "ButFor_"))]
    lrc_bridge = {
        "tag": "LRC",
        "title": "ponte e imputação",
        "sub": "a presunção de relevância e suas exceções",
        "rules": _rule_ids(record.lrc.scheme_rules),
    }
    cif["hands"] = bridge_axioms
    cif["hands_note"] = "equação (1) do ICAIL 2026"
    return [cif, lrc_bridge]


def _verdict(record) -> str:
    if record.lrc is None or not record.lrc.relevance:
        return ""
    parts = []
    for entry in record.lrc.relevance:
        mark = "reconhecida" if entry["justified"] else entry["status"]
        parts.append(f"{entry['target']} — {mark}")
    return "   ·   ".join(parts)


def render_architecture(record) -> str:
    """The architecture section: an SVG with one box per phase."""
    phases = _phases(record)
    order = " → ".join(phase["tag"] for phase in phases)
    height = PAD * 2 + len(phases) * BOX_H + (len(phases) - 1) * GAP + 52
    svg = [f'<svg viewBox="0 0 {BOX_W + PAD * 2} {height}" width="100%" '
           f'style="max-width:{BOX_W + PAD * 2}px" role="img" '
           f'aria-label="Arquitetura em camadas: {_esc(order)}">']
    svg.append('<defs><marker id="arch-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
               'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
               '<path d="M0,0 L10,5 L0,10 z" fill="var(--muted)"/></marker></defs>')

    y = PAD
    for index, phase in enumerate(phases, start=1):
        svg.append(
            f'<rect x="{PAD}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="10" '
            f'fill="var(--card)" stroke="var(--border)"/>'
        )
        svg.append(
            f'<text x="{PAD + 18}" y="{y + 28}" font-size="15" font-weight="600" '
            f'fill="var(--fg)">{index}. {_esc(phase["tag"])} — {_esc(phase["title"])}</text>'
        )
        svg.append(
            f'<text x="{PAD + 18}" y="{y + 48}" font-size="12" '
            f'fill="var(--muted)">{_esc(phase["sub"])}</text>'
        )
        for line_no, line in enumerate(_wrap(phase["rules"])):
            svg.append(
                f'<text x="{PAD + 18}" y="{y + 70 + line_no * 15}" font-size="11.5" '
                f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
                f'fill="var(--fg)">{_esc(line)}</text>'
            )
        y += BOX_H
        if index < len(phases):
            mid = PAD + 120
            svg.append(
                f'<line x1="{mid}" y1="{y}" x2="{mid}" y2="{y + GAP}" '
                f'stroke="var(--muted)" stroke-width="1.5" marker-end="url(#arch-arrow)"/>'
            )
            handed = phase.get("hands") or []
            shown = "  ".join(handed[:3]) + ("  …" if len(handed) > 3 else "")
            svg.append(
                f'<text x="{mid + LABEL_DX}" y="{y + 26}" font-size="11.5" '
                f'fill="var(--accent)">entra como axioma: '
                f'<tspan font-family="ui-monospace, SFMono-Regular, Menlo, monospace">'
                f'{_esc(shown) or "—"}</tspan></text>'
            )
            svg.append(
                f'<text x="{mid + LABEL_DX}" y="{y + 44}" font-size="11" '
                f'fill="var(--muted)">{_esc(phase.get("hands_note", ""))}</text>'
            )
            y += GAP
    verdict = _verdict(record)
    if verdict:
        svg.append(
            f'<text x="{PAD + 18}" y="{y + 32}" font-size="12" fill="var(--muted)">'
            f'saída: <tspan font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'fill="var(--fg)">{_esc(verdict)}</tspan></text>'
        )
    svg.append("</svg>")

    lead = (
        "A ordem do ICAIL 2026: o mecanismo causal resolve, e cada "
        "<code>CaFa(φ,ψ)</code> justificado entra na camada de relevância "
        "como <strong>axioma</strong> (equação 1), não como premissa: axioma "
        "não sofre undermining, e é isso que impede a camada de relevância de "
        "relitigar o que a causa de fato decidiu."
    )
    return f"""
<section class="architecture">
  <h3>Arquitetura — {_esc(order)}</h3>
  <p class="lead">{lead}</p>
  {''.join(svg)}
</section>
"""
