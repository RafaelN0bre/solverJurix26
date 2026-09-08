# jurix26

Solver ASPIC+ com detecção de causa de fato, e o pipeline que traduz dossiês anotados por
especialistas em frameworks executáveis. O repositório reproduz quatro artigos; o slug do projeto
na base de conhecimento é `jurix26` (o nome da pasta-mãe — o `basename` daqui é só `repo`).

## Base de conhecimento

Referências ingeridas via `/consume` vivem em `~/.claude/knowledge/jurix26/` (fora deste
repositório). Comece por `index.md`; `maps/*.md` indexa cada repositório clonado e `repos/*/`
tem o código completo — leia e grepe direto ali, não pare no mapa.

Consulte essa base **antes de planejar** (`/plan`, `/refine`, `/attack`): se já existe referência
sobre a área que vai ser desenhada, o desenho parte dela em vez de reinventar.

### Regra — artigo ingerido, repositório clonado junto

Quando um artigo entrar na base, **procure o repositório de código dele e clone**. Um artigo sem
a implementação de referência é metade da fonte; a outra metade decide as dúvidas de fidelidade
que o texto deixa em aberto. O procedimento completo (como extrair URLs de dentro do PDF, onde
procurar quando o artigo não linka nada, e o que registrar quando não houver repositório) está em
`~/.claude/knowledge/jurix26/index.md`, na seção "Regra permanente".

Foi assim que `tuProlog/arg2p-kt` entrou: uma URL de playground no rodapé do ICAIL 2026 levou ao
repositório dos próprios autores, cujo módulo `causality-solver/` é a implementação de referência
das definições que `src/aspic/solver.py` reimplementa em Python.

## As duas noções causais

Os artigos têm **duas**, e a implementação de referência dos autores confirma pelas assinaturas
dos primitivos (`causality-solver/.../CausalitySolver.kt`):

- **NESS** (`ness/3` lá; ICAIL 2025 Def. 4.3, renomeada "NESS Cause" na Def. 3.4 do ICAIL 2026) —
  a intervenção `¬φ` derruba alguma explicação de ψ.
- **but-for** (`but_for/2`; ICAIL 2026 Def. 3.5) — depois da intervenção, ψ deixa de ter
  **qualquer** argumento justificado. Estritamente mais forte que NESS.

Não existe uma terceira. Se aparecer um `is_cause` em algum lugar deste repositório, é resíduo de
nomenclatura: era o nome antigo do NESS.
