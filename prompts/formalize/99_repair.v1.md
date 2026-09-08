---
id: repair
version: 1
model: gemini-2.5-pro
temperature: 0
description: Corrige a saída de um estágio que foi rejeitada pela validação determinística.
---
A saída que você produziu para o estágio `{{stage}}` foi rejeitada pela
validação automática. A validação roda o parser e o solver ASPIC+ de verdade,
então os erros abaixo são fatos sobre a saída, não opiniões.

## Erros encontrados

{{errors}}

## Sua saída anterior

```json
{{previous_output}}
```

## O que fazer

Corrija **apenas** o que os erros apontam, preservando todo o resto da saída
anterior — inclusive as glosas, a evidência e os ids de dossiê já atribuídos.
Não reescreva o modelo do zero, não renomeie códigos que não foram apontados e
não remova conteúdo correto para "simplificar".

Responda com o JSON corrigido **completo** do estágio, no mesmo formato exigido
originalmente, dentro do campo `corrected_json` (como string JSON), e liste em
`changes_pt` o que você mudou, uma linha por mudança.

## Instruções originais do estágio

{{original_prompt}}
