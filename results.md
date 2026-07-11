# Resultados — Storyteller

Backend: `local` (modelo local Qwen2.5-Coder-7B via llama-server).

## Sprint 3 — baseline

sprint 3 baseline (mem0 only): 27 of 30 recall (90%)
sprint 3 augmented (mem0 + reflection): 28 of 30 recall (93%)
delta: +3pp
Custo total: $0.0000

## Diagnóstico (delta < 5pp → escalado)

O gate do S3.5 (`delta < 5pp → escala`) disparou. O delta pequeno **não** é falha da
reflection — é **saturação do baseline** pela forma do eval:

- Cenários seed têm **5 turnos**; `RetrievalPolicy` pega **top-5 memórias** do mem0.
- Logo o baseline "mem0 only" recebe **todas as 5 memórias cruas** no contexto — que já
  contêm literalmente cada fato que as perguntas cobram. O modelo responde a partir da
  memória crua sozinha → baseline já em **90%**, deixando pouco teto pra reflection subir.
- A reflection agrega valor em **históricos longos** (muitos turnos), onde o top-5 cru
  **não cabe / fica ruidoso** e os fatos consolidados (world_state) passam a importar.
  Com 5 turnos, a memória crua basta.

**A infra funciona** (reflection real gerou JSON válido e populou world_state; medição
rodou fim-a-fim, custo $0 no modelo local). O que precisa mudar é o **eval**, pra ficar
discriminante — não a reflection em si.

Opções (decisão do humano — ver escalação):
1. Cenários mais longos (15-20 turnos) → top-5 cru não cobre tudo → delta da reflection aparece.
2. Reduzir `top_memories` do retrieval (ex: 2) → baseline não se apoia em toda a memória crua.
3. Adicionar baseline **sem memória** (LLM puro) → mede o número-manchete "memória vs nada"
   (o diferencial de portfólio), em vez de "mem0 vs mem0+reflection".
