# Screenshots & demo GIF (a gerar)

Estes arquivos são o único item pendente do DoD do Sprint 5 — não dá pra gerar no
container da instância (sem browser/DISPLAY). O Marco gera na máquina dele rodando
o app (`LLM_BACKEND=local` no backend + `npm run dev` no `ui/`) e captura a tela.

Colocar aqui, com estes nomes exatos (o `ui/README.md` e o README raiz referenciam):

| Arquivo | Conteúdo |
| --- | --- |
| `01-chat-empty.png` | Sessão recém-criada, chat vazio, inspector zerado. |
| `02-chat-with-memory.png` | História com 5+ turnos, narração contextualizada. |
| `03-memory-inspector.png` | Aba de personagens/locais populada (o "wow" do produto). |
| `04-compare-split-screen.png` | Modal "Comparar com/sem memória" — contraste lado a lado (o print principal). |
| `../demo.gif` | 15-20s: criar sessão → 3+ turnos → memória populando → botão comparar → split-screen. |

### Roteiro de captura sugerido

1. Backend: `LLM_BACKEND=local poetry run uvicorn api.main:app --port 8000` (1º request ~72s).
2. Frontend: `cd ui && npm run dev` → http://localhost:3000.
3. Nova sessão → escrever **5+ turnos** (aí a reflection do turno 5 popula personagens/locais).
4. Print 03 com o inspector cheio.
5. Clicar **"Comparar com/sem memória"** → print 04 do split-screen.
6. Gravar o GIF do fluxo 3→5 (ex.: `peek`, `licecap` ou `ffmpeg -f x11grab`).

Enquanto não existirem, os links de imagem nos READMEs ficam quebrados de propósito
— é o marcador do blocker.
