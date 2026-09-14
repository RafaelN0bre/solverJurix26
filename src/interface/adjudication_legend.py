"""Builds a compact graphical key inside the adjudication legend table.
Supplies HTML cells to `analysis.perspectives` and replaces their SVG
placeholders with vector arrows and ellipses during rendering.
"""

"""Inline samples of the diagram's visual vocabulary.

Graphviz lays out the table and reserves a small cell for each symbol.
The SVG renderer inserts vector samples using the diagram's shared edge
styles and node fills. Samples remain inside the table, independent of the
graph's rank spacing. PDF export converts that same completed SVG.
"""
import re
import xml.etree.ElementTree as ET


_SVG = "http://www.w3.org/2000/svg"
_SYMBOL = re.compile(r"@@(\d{2})@@")
_SAMPLES = (
    ("standing", "ataque que subsiste"),
    ("decisive", "lance decisivo"),
    ("neutralised", "autor do ataque afastado"),
    ("inert", "ataque inerte"),
    ("support", "sustentação e ponte entre camadas"),
    ("rule", "regra da camada jurídica"),
    ("defeated-rule", "regra afastada"),
    ("facts", "camada de fato sem ataques"),
    ("inert-rule", "regra sem argumento"),
    ("voices", "N perspectivas independentes"),
)


def legend_key_html() -> str:
    """Compact three-column key with reserved cells for vector symbols."""
    rows = []
    for offset in range(0, len(_SAMPLES), 3):
        cells = []
        for index in range(offset, min(offset + 3, len(_SAMPLES))):
            _, description = _SAMPLES[index]
            cells.append(
                '<TD ALIGN="LEFT"><TABLE BORDER="0" CELLBORDER="0" '
                'CELLSPACING="0" CELLPADDING="2"><TR>'
                '<TD WIDTH="34" HEIGHT="16" ALIGN="CENTER">'
                f'<FONT FACE="Courier" COLOR="#ffffff" POINT-SIZE="6">@@{index:02}@@</FONT>'
                '</TD><TD ALIGN="LEFT">'
                f'<FONT COLOR="#666666" POINT-SIZE="7">{description}</FONT>'
                '</TD></TR></TABLE></TD>')
        cells.extend('<TD></TD>' for _ in range(3 - len(cells)))
        rows.append('<TR>' + ''.join(cells) + '</TR>')
    return ('<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" '
            'CELLPADDING="1">' + ''.join(rows) + '</TABLE>')


def _symbol(kind, x, y):
    from analysis.perspectives import _ADJUDICATION_STYLES, _LANE_STYLE

    group = ET.Element(f"{{{_SVG}}}g", {"class": "legend-symbol " + kind})

    def add(tag, **attrs):
        return ET.SubElement(group, f"{{{_SVG}}}{tag}",
                             {key.replace('_', '-'): str(value) for key, value in attrs.items()})

    if kind in _ADJUDICATION_STYLES:
        color, style, pen, size, head = _ADJUDICATION_STYLES[kind]
        tip, base = x + 12, x + 12 - 10 * size
        path = add('path', d=f'M {x - 12},{y} L {base},{y}', fill='none',
                   stroke=color, stroke_width=pen)
        if style != 'solid':
            path.set('stroke-dasharray', '5,2' if style == 'dashed' else '1,5')
        if head == 'tee':
            add('path', d=f'M {base},{y} L {tip},{y}', fill='none', stroke=color,
                stroke_width=pen)
            add('path', d=f'M {tip},{y - 5 * size} L {tip},{y + 5 * size}',
                fill='none', stroke=color, stroke_width=pen)
        else:
            add('polygon', points=f'{tip},{y} {base},{y - 3.5 * size} {base},{y + 3.5 * size}',
                fill='none' if head == 'empty' else color, stroke=color, stroke_width=pen)
    else:
        defeated = kind == 'defeated-rule'
        ellipse = add('ellipse', cx=x, cy=y, rx=12, ry=6,
                      fill='#fdecea' if defeated else
                      '#ffffff' if kind == 'facts' else _LANE_STYLE['lrc']['fill'],
                      stroke='#c0392b' if defeated else '#999999' if kind == 'facts' else '#444444',
                      stroke_width=1.8 if defeated else 1.0)
        if kind == 'facts':
            ellipse.set('stroke-dasharray', '5,2')
        if kind in ('inert-rule', 'voices'):
            label = add('text', x=x, y=y + 1.5, text_anchor='middle',
                        font_family='Helvetica', font_size=4.5, fill='#222222')
            label.text = '(inert)' if kind == 'inert-rule' else '(N)'
    return group


def embed_legend_symbols(svg: str) -> str:
    """Insert small vector samples into the table cells laid out by Graphviz."""
    if not _SYMBOL.search(svg):
        return svg
    ET.register_namespace('', _SVG)
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    root = ET.fromstring(svg)
    for parent in root.iter():
        for index, node in enumerate(list(parent)):
            if node.tag != f'{{{_SVG}}}text':
                continue
            match = _SYMBOL.fullmatch(node.text or '')
            if match is None:
                continue
            kind = _SAMPLES[int(match.group(1))][0]
            # Courier at 6pt occupies 3.6pt per character; the marker has six.
            x = float(node.attrib['x']) + 10.8
            y = float(node.attrib['y']) - 2
            parent.remove(node)
            parent.insert(index, _symbol(kind, x, y))
    return ET.tostring(root, encoding='unicode')
