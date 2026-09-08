import json, re
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
root = ET.parse('docx/word/document.xml').getroot()
body = root.find(W+'body')

def para_text(p):
    parts=[]
    for node in p.iter():
        if node.tag == W+'t': parts.append(node.text or '')
        elif node.tag == W+'tab': parts.append(' ')
        elif node.tag == W+'br': parts.append('\n')
    return ''.join(parts)

def cell_items(tc):
    """Retorna a lista de itens (bullets/linhas) da célula, limpos."""
    items=[]
    for p in tc.findall(W+'p'):
        t = ' '.join(para_text(p).split())
        for piece in [t]:
            piece = piece.strip()
            # separador ' / ' usado no doc para listar itens
            for sub in re.split(r'\s*/\s*(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ_(])|\s+/\s*$', piece):
                sub = sub.strip().strip('/').strip()
                if sub and sub not in ('_____','_'):
                    items.append(sub)
    return items

def cell_text(tc):
    items = cell_items(tc)
    return ' / '.join(items)

# coleta blocos: parágrafos + tabelas em ordem
blocks=[]
for child in body:
    if child.tag == W+'p':
        blocks.append(('p', para_text(child).strip()))
    elif child.tag == W+'tbl':
        rows=[]
        for tr in child.findall(W+'tr'):
            rows.append([tc for tc in tr.findall(W+'tc')])
        blocks.append(('tbl', rows))

SECOES = ['FATOS RELEVANTES','CAUSAS FÁTICAS CANDIDATAS','CAUSAS JURIDICAMENTE RELEVANTES',
          'TEORIA JURÍDICA','NEXO CAUSAL','CENÁRIOS CAUSAIS','DIVERGÊNCIAS']

# indices dos títulos de seção
marks=[]
for i,(kind,val) in enumerate(blocks):
    if kind=='p' and val.strip() in SECOES:
        marks.append((i, val.strip().upper()))

doc = {
  "documento": "Andressa - Documento de Consolidação de Anotação Jurídica",
  "caso": "RE 608880 - responsabilidade civil do Estado por crime cometido por foragido",
  "anotadores": ["Izabela","Vítor","Andressa"],
  "coluna_alvo": "Consolidação",
  "secoes": []
}

for idx,(i,titulo) in enumerate(marks):
    fim = marks[idx+1][0] if idx+1 < len(marks) else len(blocks)
    trecho = blocks[i+1:fim]
    comando = ''
    vocab=[]
    orientacoes=[]
    tabelas=[]
    coletando_vocab=False
    for kind,val in trecho:
        if kind=='p':
            v = val.strip()
            if not v: continue
            if v.lower().startswith('vocabulário mínimo') or v.lower().startswith('orientação para a consolidação — vocabulário'):
                coletando_vocab=True; continue
            if v.lower().startswith('obs.') or v.lower().startswith('orientação'):
                coletando_vocab=False; orientacoes.append(v); continue
            if coletando_vocab and len(v) < 80 and not v.endswith('.'):
                vocab.append(v); continue
            coletando_vocab=False
            if not comando and v.lower().startswith('considere'):
                comando = v
            else:
                orientacoes.append(v)
        else:
            header = [para_text(p).strip() for tc in val[0] for p in tc.findall(W+'p')]
            linhas=[]
            for tr in val[1:]:
                cols = tr
                persp = cell_text(cols[0])
                linhas.append({
                    "perspectiva": persp,
                    "anotacoes": {
                        "Izabela": cell_items(cols[1]),
                        "Vítor": cell_items(cols[2]),
                        "Andressa": cell_items(cols[3]),
                    },
                    "consolidacao": cell_text(cols[4]) if len(cols)>4 else "",
                    "consolidacao_itens": cell_items(cols[4]) if len(cols)>4 else []
                })
            tabelas.append({"cabecalho": header, "linhas": linhas})

    doc["secoes"].append({
        "id": idx+1,
        "titulo": titulo,
        "comando": comando,
        "vocabulario_minimo": vocab,
        "orientacoes": orientacoes,
        "tabelas": tabelas,
        "campo_livre": any('campo livre' in o.lower() for o in orientacoes) or 'RESPOSTA PARA CONSOLIDAÇÃO (campo livre):' in [o for o in orientacoes]
    })

print(json.dumps(doc, ensure_ascii=False, indent=2))
