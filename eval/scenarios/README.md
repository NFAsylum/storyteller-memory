# Cenários de avaliação

Cada cenário é um arquivo JSON que descreve uma história fixa (uma sequência de turnos)
e um conjunto de perguntas usadas para medir o quanto o sistema **lembra** dos fatos.
O harness (sprint seguinte) roda os turnos e, depois do turno indicado, faz as perguntas
e compara a resposta com o `ground_truth`.

Todo arquivo é validado contra o model `Scenario` de `eval/scenario.py` via
`load_scenario(path)` — JSON inválido, campo faltando ou categoria desconhecida param a
carga com um `ScenarioLoadError` claro.

## Formato

```json
{
  "id": "seed_01_traicao_castelo_aldrath",
  "scenes": [
    { "turn_id": 1, "user_input": "..." }
  ],
  "questions": [
    {
      "id": "q1",
      "asked_after_turn": 5,
      "category": "recall_factual",
      "question": "Quem é a cavaleira leal ao rei?",
      "ground_truth": "Aria",
      "acceptable_variants": ["a cavaleira Aria"]
    }
  ]
}
```

### Campos

| Campo | Onde | Significado |
|---|---|---|
| `id` | scenario | Identificador único do cenário (kebab/snake case). |
| `scenes[].turn_id` | scene | Ordem do turno (1, 2, 3, ...). |
| `scenes[].user_input` | scene | A ação/entrada do usuário naquele turno. |
| `questions[].id` | question | Identificador da pergunta dentro do cenário (`q1`, `q2`, ...). |
| `questions[].asked_after_turn` | question | Depois de qual turno a pergunta é feita. |
| `questions[].category` | question | Uma das 5: `recall_factual`, `character_consistency`, `relation_evolution`, `world_state`, `controlled_forgetting`. |
| `questions[].question` | question | O texto da pergunta. |
| `questions[].ground_truth` | question | A resposta canônica esperada. |
| `questions[].acceptable_variants` | question | Formas alternativas aceitas (opcional; default `[]`). |

`extra="forbid"`: qualquer campo a mais no JSON é rejeitado — evita typo silencioso.

## Como escrever um cenário novo

1. Crie `eval/scenarios/seed_NN.json` (ou dentro de `full/` para os cenários do Sprint 3).
2. Escreva de **5 a N cenas** contando uma história com fatos concretos (nomes próprios,
   lugares, objetos, relações) — são esses fatos que as perguntas vão cobrar.
3. Para cada pergunta, garanta que o `ground_truth` **aparece explicitamente numa cena**;
   se o fato não foi estabelecido, a pergunta não é justa.
4. Use `acceptable_variants` para formas equivalentes ("Aria" vs "a cavaleira Aria"),
   evitando que o judge marque errado uma resposta correta escrita de outro jeito.
5. Mantenha `ground_truth` curto e específico (uma entidade/frase), não uma frase longa.
6. Valide antes de commitar:

   ```bash
   poetry run python -c "from eval.scenario import load_scenario; load_scenario('eval/scenarios/seed_NN.json')"
   ```

## Cenários seed atuais

| Arquivo | História | Cenas | Perguntas |
|---|---|---|---|
| `seed_01.json` | Traição no castelo de Aldrath (Aria, rei Doran, Vex) | 5 | 10 recall_factual |
| `seed_02.json` | Caravana no deserto de Khareth (Seline, Tarek, Nima) | 5 | 10 recall_factual |
| `seed_03.json` | Aprendiz e o autômato de cobre (Bram, Orin, Tock) | 5 | 10 recall_factual |
