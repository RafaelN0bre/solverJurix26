---
model: gemini-2.5-pro
temperature: 0.2
---

# Consolidação canônica do caso 003

Três especialistas anotaram o mesmo acórdão e, depois, cada um preencheu por
conta própria a coluna "Consolidação" do mesmo documento de trabalho. Você
recebe as três propostas, célula por célula, junto com as anotações cruas que
cada uma resume. Sua tarefa é produzir **uma** consolidação canônica.

Anotadores: {{anotadores}}. Células a consolidar: {{total_celulas}}.

## O que consolidar

O documento tem seções; cada seção tem um **comando** próprio (o que aquela
seção pede) e, quase sempre, um **vocabulário mínimo** — uma lista de
expressões que os anotadores foram instruídos a usar para uniformizar a
redação. Seções do tipo tabela têm uma linha por perspectiva (Recorrente,
Recorrido, Marco Aurélio, Edson Fachin, Alexandre de Moraes); seções de campo
livre têm uma resposta só.

Consolide **cada célula listada**, uma a uma. Nenhuma pode faltar e nenhuma
pode aparecer duas vezes.

## Regras

1. **Obedeça ao comando da seção.** Ele está em cada bloco. Se o comando pede
   fatos sem conclusão jurídica, uma proposta que traz conclusão jurídica é
   proposta que extrapolou — consolide o fato, não a conclusão.

2. **Prefira o vocabulário mínimo da seção.** Quando duas propostas dizem a
   mesma coisa com palavras diferentes e uma delas usa a expressão do
   vocabulário, use a do vocabulário. Quando nenhuma usa, mas o conteúdo
   corresponde a uma expressão da lista, traduza para ela. O vocabulário é
   sugestão, não camisa de força: se o conteúdo não couber em nenhuma
   expressão, escreva em português claro e objetivo.

3. **Não decida por maioria.** Duas redações do mesmo conteúdo não são dois
   votos, e uma leitura sustentada por um único anotador pode ser a correta —
   sobretudo quando ela é a única que respeita o comando da seção ou a única
   apoiada pelas anotações cruas. Decida pelo conteúdo e **diga por quê** em
   `justificativa`.

4. **Distinga divergência de redação de divergência de conteúdo.** Marque
   `divergencia_substantiva: true` **somente** quando as propostas discordarem
   sobre o que o acórdão diz — por exemplo, uma perspectiva a que um anotador
   atribui "ato de terceiro" e outro atribui "dever geral de segurança
   pública". Estilo, granularidade e ordem dos itens **não** são divergência
   substantiva.

5. **Não invente.** Se as três propostas estiverem vazias para uma célula,
   devolva `valor` vazio, `itens` vazio, `sustentada_por` vazio. Não deduza a
   partir de outra perspectiva, de outra seção ou das anotações cruas. Uma
   célula vazia é informação: quer dizer que ninguém se pronunciou ali.

6. **Não misture perspectivas.** O que o Recorrente sustenta não entra na
   linha do Recorrido, ainda que seja verdade sobre o caso.

7. **Registre o apoio.** `sustentada_por` lista os anotadores cuja proposta
   você adotou, no todo ou em substância. Se você reescreveu para o
   vocabulário mínimo mas o conteúdo é o de dois deles, os dois entram. Se a
   consolidação é sua e não corresponde a nenhuma, deixe a lista vazia e
   explique na justificativa.

8. **`itens` é a quebra de `valor`.** Quando a célula for uma lista (o caso
   comum nas seções de tabela), escreva `valor` com os itens separados por
   " / " e repita-os um a um em `itens`. Quando for texto corrido, `itens`
   fica vazio.

## Material

{{material}}

## Saída

Devolva um objeto com `celulas` (uma entrada por célula do material, na mesma
ordem) e `notas_gerais`. Em `notas_gerais`, escreva o que só se vê olhando o
conjunto: onde as divergências se concentram, que seções ficaram frágeis, o
que um revisor humano precisa olhar primeiro. Seja específico e curto.
