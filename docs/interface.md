# A interface: ler e conferir um caso sem programar

```bash
uv run python scripts/run_app.py        # http://127.0.0.1:8000/
ASPIC_APP_PORT=8010 uv run python scripts/run_app.py   # se a 8000 estiver ocupada
```

A página é uma bancada de trabalho: à esquerda, todos os casos; à direita, o
caso selecionado em cinco abas. Nada aqui exige ler código ou notação lógica —
a notação ASPIC+ existe, mas fica sempre atrás de um "Ver representação
técnica".

O endereço acompanha a navegação (`#/case-005/conferencia`), então uma aba
específica de um caso específico pode ser enviada por link.

## Os símbolos se explicam sozinhos

Os códigos formais (`CrimeLatroc`, `r4`, `¬r0`, `CaFa_FugaPreso_MorteVitima`)
aparecem sublinhados por pontinhos onde quer que surjam — nas tabelas da ficha,
na nota técnica de cada cartão de argumento, na camada de relevância jurídica.
**Passar o mouse (ou dar Tab até eles) mostra a leitura em português corrido.**
Nos nós do grafo, o mesmo texto entra na dica nativa do navegador, junto do
rótulo técnico. `Esc` fecha a dica.

Quem preferir a lista completa em vez de consultar um a um encontra a mesma
informação na tabela **Vocabulário do caso**, no fim da aba Análise.

## Panorama

O acervo inteiro numa tela: quantos casos existem, quantos vieram de dossiê
anotado e quantos são os casos de referência dos artigos, com que frequência o
framework termina onde a corte terminou, e **quais dossiês já foram anotados mas
ainda não passaram pelo pipeline**.

A tabela traz, por caso, o número de átomos e regras, quantas perguntas causais
foram testadas, a barra de acordo com a corte, se há camada de relevância
jurídica, o resultado das checagens automáticas e se o dossiê de origem está no
disco.

## Análise — o que se concluiu, e por quê

Em português corrente:

- a **conclusão principal** e quais fatos foram (ou não) reconhecidos como
  causa;
- os **argumentos construídos**, um cartão por leitura, com o selo
  *Aceito / Rejeitado / Indeterminado*. Quando várias linhas de raciocínio
  levam à mesma conclusão, elas viram um cartão só, que informa quantos
  caminhos existem e como cada um terminou — a conclusão se sustenta se
  *algum* caminho se sustenta;
- as **disputas**: quem contesta o quê, com que fundamento, e se a contestação
  prevaleceu. É esta tabela, e não a ordem dos argumentos, que decide o
  resultado;
- o **vocabulário do caso**: o que cada símbolo do grafo significa e qual o seu
  papel (fato alegado, fato assentado, elo derivado, resultado a explicar);
- a **comparação causal** — o teste NESS, a causa de fato da Definição 4.3 e o
  "não fosse por" da Definição 3.5, cada um como uma pergunta em português;
- a **relevância jurídica** (ICAIL 2026), quando o caso tem essa camada.

## Perspectivas — o julgamento como disputa

O framework único responde o que a corte decidiu. Esta aba responde outra
coisa: **quem sustentou o quê, e em que movimento o caso virou**. Segue a
divisão de Prakken, *A Formal Model of Adjudication Dialogues* (2008): as
partes constroem o grafo na fase de argumentação, e o adjudicador decide na
fase de decisão — movendo argumentos, não atribuindo pesos. O silêncio dele
também é decisão: uma regra que nenhum voto ataca foi endossada.

**O mapa de adjudicação.** Cada elipse é uma regra, desenhada dentro da caixa
de quem a move; as caixas se agrupam em ADJUDICADORES, PARTES e
INCONTROVERSO. Seta vermelha cheia é ataque (a regra afasta a apontada); seta
cinza tracejada é apoio (a conclusão de uma alimenta o antecedente da outra).
Elipse vermelha é regra afastada. O mapa cobre as **duas camadas** — sem isso
um tribunal que decide o caso inteiro por defesa doutrinária apareceria como
não tendo participado do julgamento.

**Fase de argumentação.** As duas partes primeiro, depois cada julgador na
ordem do processo, com o que as regras novas mudaram nos vereditos causais. A
coluna interessante não é a do resultado — é a última: um voto convergente que
abre uma segunda rota para o mesmo elo *enfraquece* o caso contrafactual da
conclusão que ele apoia (a causa deixa de ser "não fosse por" e continua sendo
causa NESS).

**Fase de decisão.** A camada de relevância jurídica admitida um julgador por
vez, a partir da presunção geral. A linha destacada como **ponto de virada** é
o movimento em que uma pretensão que sobreviveu aos fatos deixa de sobreviver
ao direito.

**Fatores em disputa.** Cada fato declara para que lado pesa
(`responsabilizacao`, `exclusao`, `neutro`) e que ponto abstrato instancia —
a noção de *factor* do CATO. Dois fatos de lados opostos sob o mesmo ponto
abstrato **se anulam**, e cada anulação é uma questão que o acórdão disputou,
com as duas respostas que recebeu. A balança conta fatores por leitura; é
contagem e não peso, porque nem o CATO nem este quadro somam fatores — quem
vence continua sendo decidido pelo solver.

Os esquemas de precedente do CATO (CS1–CS4, distinguishing, substituição) não
estão implementados: todos exigem um caso paradigma com resultado conhecido, e
este acervo não tem corpus de precedentes. Ver `src/aspic/factors.py`.

Uma defesa sem autor identificado entra em todos os passos e por isso nunca
aparece como movimento — a aba diz quantas são, porque um traço liso demais
costuma ser sinal disso, e não de um julgamento sem disputa.

## Dossiê — a leitura humana do acórdão

O que o anotador registrou, antes de qualquer formalização: síntese do caso,
reconstrução de cada perspectiva (recorrente, recorrido, cada voto, posição
final), pontos de divergência com o que cada lado sustenta, unidades causais, e
os trechos literais marcados no PDF.

Cada campo mostra, recolhidos, os trechos do acórdão que o anotador vinculou a
ele. No fim, os trechos aparecem agrupados por página, e cada um diz em quantos
campos foi usado — **um trecho marcado que não foi vinculado a nada é
sinalizado**, porque costuma indicar anotação interrompida.

Quando o arquivo do dossiê não está no repositório, a aba mostra o **brief**
daquela execução: o dossiê já normalizado, que é exatamente o texto que o
modelo leu. Fica dito na tela que se trata do brief, e não do original.

## Formalização — de onde veio cada peça

A ficha de formalização: a tabela solver × decisão da corte, o catálogo de
átomos (código, significado, tipo, status, papel, quem sustenta) ao lado do
trecho que sustenta cada um, as regras com sua leitura em português e sua
evidência, a camada de relevância jurídica separando premissas de ponte
(calculadas pelo solver) das doutrinárias (extraídas do acórdão), as notas de
modelagem, os pontos em aberto e a proveniência completa — modelo, arquivos de
prompt e seus hashes, id da execução.

## Conferência — quanto essa tradução merece confiança

Quatro perguntas, com números:

1. **O framework chegou onde a corte chegou?** Placar de coincidências e, para
   cada divergência, as duas leituras lado a lado. Divergência é achado, não
   defeito: aponta a regra a revisar.
2. **A formalização usou o dossiê?** Quantos dos trechos marcados foram
   citados, quantos registros do dossiê foram aproveitados, e a lista do que
   ficou de fora — com o texto do trecho, para dar para julgar se a omissão
   importa.
3. **Dá para rastrear tudo até o acórdão?** Quais átomos, regras e perguntas
   entraram sem citar nenhum trecho.
4. **Passa nas checagens automáticas?** O relatório determinístico de
   `formalize.validate` (gramática das regras, códigos, literais existentes,
   rebuts mútuos sem undercut, coerência da camada LRC).

Fecha com as **execuções do pipeline**: modelo, número de chamadas, quantos
reparos foram necessários (etapas reenviadas ao modelo depois de reprovar nas
checagens) e o custo em tokens. Muitos reparos significam prompt frágil.

## De onde a interface lê

| O que | Onde |
|---|---|
| Dossiês anotados | `data/<anotador>/*.json` (`ASPIC_DOSSIER_ROOT` sobrescreve) |
| Formalizações | `data/translated/<caso>/case.json` (`ASPIC_TRANSLATED_DIR` sobrescreve) |
| Checagens | `data/translated/<caso>/validation.json` |
| Execuções e briefs | `data/translated/<caso>/runs/<run-id>/` |
| Casos dos artigos | `src/aspic/examples.py` |

Tudo é relido do disco a cada requisição: rodar o pipeline com a aplicação no ar
faz a nova formalização aparecer no próximo clique.

## Para auditar fora do navegador

- `GET /api/cases` — o acervo e quais abas cada caso tem.
- `GET /api/cases/{id}/raw` — o `case.json` e o `validation.json`.
- `GET /api/cases/{id}/coverage` — os números da Conferência em JSON.
- `GET /api/cases/{id}/glossary` — `{símbolo: leitura}`, o mesmo mapa que
  alimenta as dicas de hover.
- `GET /api/cases/{id}/perspectives` — o mapa de adjudicação e os dois traços.
