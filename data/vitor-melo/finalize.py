import json, re

d = json.load(open('consolidacao.json'))
PERSPS = ["Recorrente","Recorrido","Marco Aurélio","Edson Fachin","Alexandre de Moraes"]

def limpa(orients):
    out=[]
    for o in orients:
        if o.startswith('RESPOSTA PARA CONSOLIDAÇÃO'): continue
        if re.match(r'^7\.\d\.', o): continue
        if o.strip().lower().startswith('orientação para a'): continue
        if o.strip().lower().startswith('utilize uma ou mais expressões'): continue
        out.append(o)
    return out

secoes=[]
for s in d['secoes']:
    tit = s['titulo']
    if tit == 'DIVERGÊNCIAS':
        # 7.1 campo livre
        idx72 = next(i for i,o in enumerate(s['orientacoes']) if o.startswith('7.2'))
        o71 = s['orientacoes'][:idx72]
        o72 = s['orientacoes'][idx72:]
        cmd72 = next((o for o in o72 if o.lower().startswith('considere')), '')
        secoes.append({
            "id": "7.1", "titulo": "DIVERGÊNCIAS — Pontos de divergência",
            "tipo": "campo_livre",
            "comando": s['comando'],
            "vocabulario_minimo": [],
            "orientacoes": limpa(o71),
            "resposta_consolidada": "",
            "status": "pendente"
        })
        secoes.append({
            "id": "7.2", "titulo": "DIVERGÊNCIAS — Posturas",
            "tipo": "tabela_por_perspectiva",
            "comando": cmd72,
            "vocabulario_minimo": s['vocabulario_minimo'],
            "orientacoes": limpa([o for o in o72 if not o.lower().startswith('considere')]),
            "consolidacao_por_perspectiva": {l['perspectiva']: l['consolidacao'] for l in s['tabelas'][0]['linhas']},
            "consolidacao_itens_por_perspectiva": {l['perspectiva']: l['consolidacao_itens'] for l in s['tabelas'][0]['linhas']},
            "anotacoes_por_perspectiva": {l['perspectiva']: l['anotacoes'] for l in s['tabelas'][0]['linhas']},
        })
        continue

    if s['tabelas']:
        cons = {l['perspectiva']: l['consolidacao'] for l in s['tabelas'][0]['linhas']}
        cons_it = {l['perspectiva']: l['consolidacao_itens'] for l in s['tabelas'][0]['linhas']}
        secoes.append({
            "id": str(s['id']), "titulo": tit,
            "tipo": "tabela_por_perspectiva",
            "comando": s['comando'],
            "vocabulario_minimo": s['vocabulario_minimo'],
            "orientacoes": limpa(s['orientacoes']),
            "consolidacao_por_perspectiva": cons,
            "consolidacao_itens_por_perspectiva": cons_it,
            "anotacoes_por_perspectiva": {l['perspectiva']: l['anotacoes'] for l in s['tabelas'][0]['linhas']},
        })
    else:
        secoes.append({
            "id": str(s['id']), "titulo": tit,
            "tipo": "campo_livre",
            "comando": s['comando'],
            "vocabulario_minimo": s['vocabulario_minimo'],
            "orientacoes": limpa(s['orientacoes']),
            "resposta_consolidada": "",
            "status": "pendente"
        })

# lista plana de preenchimentos
preench=[]
for s in secoes:
    if s['tipo']=='tabela_por_perspectiva':
        for p in PERSPS:
            v = s['consolidacao_por_perspectiva'].get(p,'')
            preench.append({
                "secao_id": s['id'], "secao": s['titulo'], "perspectiva": p,
                "coluna": "Consolidação",
                "valor": v,
                "valor_itens": s['consolidacao_itens_por_perspectiva'].get(p,[]),
                "status": "preenchido" if v.strip() else "vazio_no_documento_de_origem"
            })
    else:
        preench.append({
            "secao_id": s['id'], "secao": s['titulo'], "perspectiva": None,
            "coluna": "RESPOSTA PARA CONSOLIDAÇÃO (campo livre)",
            "valor": s.get('resposta_consolidada',''),
            "status": "vazio_no_documento_de_origem"
        })

out = {
    "documento_origem": d['documento'],
    "arquivo": "data/vitor-melo/Vítor - Documento de Consolidação de Anotação Jurídica.docx",
    "anotadores": d['anotadores'],
    "perspectivas": PERSPS,
    "coluna_alvo": "Consolidação",
    "secoes": secoes,
    "preenchimentos": preench,
    "resumo": {
        "total_celulas": len(preench),
        "preenchidas": sum(1 for p in preench if p['status']=='preenchido'),
        "vazias": sum(1 for p in preench if p['status']!='preenchido'),
    }
}
json.dump(out, open('consolidacao_final.json','w'), ensure_ascii=False, indent=2)
print(json.dumps(out['resumo'], ensure_ascii=False))
for p in preench:
    if p['status']!='preenchido':
        print('VAZIO:', p['secao_id'], p['secao'], '|', p['perspectiva'])
