"""Render an `ArgumentationFramework`'s argument graph as Graphviz DOT/SVG/PDF.

This is a pure presentation layer on top of `aspic.solver`: it does not
change how arguments, attacks or defeats are computed, it only renders the
already-computed structure (Definitions 2.6, 2.8, 2.10) plus each argument's
grounded-extension status (Section 2.1) as a picture.

Rendering shells out to the system `dot` binary (Graphviz) rather than
adding a Python Graphviz binding as a project dependency -- the DOT
language is simple enough to build as a string, and `subprocess` is stdlib.
"""
import shutil
import subprocess

from pathlib import Path
from typing import Dict, Set

from .solver import Argument, ArgumentationFramework

ATTACK_STYLE = {
    "undercut": {"color": "#d17a00", "style": "dashed", "abbrev": "UC"},
    "rebut": {"color": "#c0392b", "style": "solid", "abbrev": "RB"},
    "undermine": {"color": "#7030a0", "style": "dotted", "abbrev": "UM"},
}

STATUS_STYLE = {
    "IN": {"fillcolor": "#d9f2d9", "color": "#2e7d32"},
    "OUT": {"fillcolor": "#f6d6d6", "color": "#b71c1c"},
    "UNDEC": {"fillcolor": "#eeeeee", "color": "#757575"},
}


def argument_status(af: ArgumentationFramework, extension: Set[str]) -> Dict[str, str]:
    """Grounded-labeling status of every argument (mirrors `_is_defended`'s
    notion of defeat, but exposed as a 3-way IN/OUT/UNDEC label instead of a
    single "is it in the extension" boolean):

    - IN: the argument is in the grounded extension.
    - OUT: not IN, but some IN argument defeats it.
    - UNDEC: neither IN nor OUT (e.g. caught in an unresolved cycle).
    """
    status: Dict[str, str] = {}
    for arg_id in af.arguments:
        if arg_id in extension:
            status[arg_id] = "IN"
            continue
        defeated_by_in = any(
            d.attack.target_id == arg_id and d.attack.attacker_id in extension
            for d in af.defeats
        )
        status[arg_id] = "OUT" if defeated_by_in else "UNDEC"
    return status


def _dot_escape(text: str) -> str:
    """Escape a plain-text string for embedding in a quoted DOT attribute.

    Only quotes are escaped, not backslashes: callers that need Graphviz's
    own label control sequences (`\\n`, `\\l`, ...) build those directly
    into the string, and none of this module's source text (rule ids,
    literal names, attack descriptions) ever contains a literal backslash
    of its own.
    """
    return text.replace('"', '\\"')


def _argument_label(arg: Argument) -> str:
    premises = ", ".join(sorted(arg.premises)) or "∅"
    rule_ids = arg.strict_rules + arg.defeasible_rules
    if rule_ids:
        rules = ",".join(rule_ids)
        return f"{arg.id}\\n[{premises}]\\n{rules} ⊢ {arg.conclusion}"
    return f"{arg.id}\\n{arg.conclusion} (premise)"


def to_dot(af: ArgumentationFramework, extension: Set[str], *,
           include_atomic: bool = True, title: str = "") -> str:
    """Build the Graphviz DOT source for `af`'s argument graph.

    One node per `Argument` (colored by IN/OUT/UNDEC status, Definition
    2.6/Section 2.1), one edge per `Attack` (styled by attack type --
    undercut/rebut/undermine -- and bolded if the attack succeeded as a
    `Defeat`, Definitions 2.8/2.10/2.11), plus a legend cluster listing the
    case's rules so the figure is self-explanatory without the source code.
    """
    status = argument_status(af, extension)
    successful_attacks = {id(d.attack) for d in af.defeats}

    lines = ["digraph ArgumentGraph {", '  rankdir="TB";', '  fontname="Helvetica";',
             '  node [fontname="Helvetica", fontsize=11];',
             '  edge [fontname="Helvetica", fontsize=10];']
    if title:
        lines.append(f'  labelloc="t"; label="{_dot_escape(title)}"; fontsize=16;')

    for arg in af.arguments.values():
        if not include_atomic and arg.is_atomic:
            continue
        style = STATUS_STYLE[status[arg.id]]
        shape = "ellipse" if arg.is_atomic else "box"
        label = _argument_label(arg)
        css_class = f'argnode status-{status[arg.id]} arg-{arg.id}'
        lines.append(
            f'  "{arg.id}" [shape={shape}, style="filled,rounded", '
            f'fillcolor="{style["fillcolor"]}", color="{style["color"]}", '
            f'label="{_dot_escape(label)}", tooltip="{_dot_escape(label)}", '
            f'class="{css_class}"];'
        )

    for attack in af.attacks:
        target = af.arguments[attack.target_subargument_id]
        if not include_atomic and target.is_atomic and target.id != attack.target_id:
            continue
        style = ATTACK_STYLE[attack.attack_type]
        is_defeat = id(attack) in successful_attacks
        label = style["abbrev"]
        if attack.attack_type == "undercut":
            label += f"({attack.rule_id})"
        penwidth = 2.2 if is_defeat else 1.0
        color = style["color"] if is_defeat else "#bbbbbb"
        edge_style = style["style"] if is_defeat else "dotted"
        note = "" if is_defeat else " -- attack failed, not a defeat"
        css_class = (
            f'argedge type-{attack.attack_type} '
            f'{"defeat" if is_defeat else "failed-attack"} '
            f'from-{attack.attacker_id} to-{attack.target_id}'
        )
        lines.append(
            f'  "{attack.attacker_id}" -> "{attack.target_id}" '
            f'[label="{label}", color="{color}", style="{edge_style}", '
            f'penwidth={penwidth}, tooltip="{_dot_escape(str(attack) + note)}", '
            f'class="{css_class}"];'
        )

    lines.append(_rules_legend(af))
    lines.append("}")
    return "\n".join(lines)


def _rules_legend(af: ArgumentationFramework) -> str:
    rows = []
    for rule in af.strict_rules.values():
        rows.append(_dot_escape(str(rule)))
    for rule in af.defeasible_rules.values():
        rows.append(_dot_escape(str(rule)))
    body = "\\l".join(rows) + "\\l" if rows else "(no rules)\\l"
    return (
        '  subgraph cluster_legend {\n'
        '    label="Rules"; fontsize=11; style="dashed"; color="#999999";\n'
        f'    legend [shape=box, style="filled", fillcolor="#fbfbfb", '
        f'fontsize=10, label="{body}"];\n'
        "  }"
    )


def render_to_string(dot_source: str, fmt: str = "svg") -> str:
    """Run `dot -T<fmt>` over `dot_source` and return its stdout as text."""
    dot_bin = shutil.which("dot")
    if dot_bin is None:
        raise RuntimeError(
            "Graphviz 'dot' executable not found on PATH. Install Graphviz "
            "(e.g. `brew install graphviz`) to render argument graphs."
        )
    result = subprocess.run(
        [dot_bin, f"-T{fmt}"], input=dot_source, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dot failed (exit {result.returncode}): {result.stderr}")
    return result.stdout


def render_to_file(dot_source: str, out_path: Path, fmt: str = "svg") -> None:
    """Render `dot_source` to `out_path` in format `fmt` (svg, pdf, ...)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt in ("pdf", "png"):
        # Binary formats: run in bytes mode throughout, never decode as text.
        dot_bin = shutil.which("dot")
        if dot_bin is None:
            raise RuntimeError(
                "Graphviz 'dot' executable not found on PATH. Install Graphviz "
                "(e.g. `brew install graphviz`) to render argument graphs."
            )
        result = subprocess.run(
            [dot_bin, f"-T{fmt}"], input=dot_source.encode("utf-8"), capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"dot failed (exit {result.returncode}): {result.stderr.decode()}")
        out_path.write_bytes(result.stdout)
    else:
        content = render_to_string(dot_source, fmt=fmt)
        out_path.write_text(content, encoding="utf-8")
