import re, sys
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
tree = ET.parse('docx/word/document.xml')
root = tree.getroot()
body = root.find(W+'body')

def para_text(p):
    parts=[]
    for node in p.iter():
        if node.tag == W+'t':
            parts.append(node.text or '')
        elif node.tag == W+'tab':
            parts.append('\t')
        elif node.tag == W+'br':
            parts.append('\n')
    return ''.join(parts)

def para_style(p):
    ppr = p.find(W+'pPr')
    if ppr is None: return ''
    st = ppr.find(W+'pStyle')
    if st is None: return ''
    return st.get(W+'val') or ''

out=[]
for child in body:
    if child.tag == W+'p':
        t = para_text(child).strip()
        s = para_style(child)
        out.append(f'[P:{s}] {t}')
    elif child.tag == W+'tbl':
        out.append('[TABLE]')
        for tr in child.findall(W+'tr'):
            cells=[]
            for tc in tr.findall(W+'tc'):
                ct = ' / '.join(para_text(p).strip() for p in tc.findall(W+'p'))
                cells.append(ct)
            out.append('  | ' + ' || '.join(cells))
        out.append('[/TABLE]')
print('\n'.join(out))
