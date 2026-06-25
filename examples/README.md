# Examples

## quickstart.py

A minimal end-to-end app built on the Apeiron toolkit. It:

1. Authenticates to Azure OpenAI via cached browser / `az login` (no API key needed).
2. Runs a single-shot completion through `LLMCaller` (`gpt-4.1`, `provider=OPENAI`).
3. Routes the same question to **Claude via the GitHub Copilot SDK**
   (`claude-sonnet-4.5`, `provider=COPILOT`).
4. Parses a structured ```` ```answer ... ``` ```` block out of each response via a `Prompt`.
5. Prints token usage / cost for the OpenAI call.

### Run

```bash
python examples/quickstart.py
python examples/quickstart.py --question "Name 3 prime numbers."
python examples/quickstart.py --no-copilot          # skip the Claude/Copilot call
```

### Prerequisites

- A populated `.env` (at minimum `AZURE_OPENAI_ENDPOINT`; see `.env.example`).
- `az login` once (or the cached browser login flow will open a browser on first run).
- For the Copilot/Claude call: the GitHub Copilot CLI + `copilot` SDK on PATH
  (`pip install -e .[copilot]`).

### Example output

```
=== gpt-4.1 (provider=OPENAI) ===
raw: ```answer
Paris
```
parsed answer block: Paris
Prompt tokens: 46, Completion tokens: 8, Cached prompt tokens: 0, Cost: 0.0002 USD

=== claude-sonnet-4.5 (provider=COPILOT) ===
raw: ```answer
Paris
```
parsed answer block: Paris
```

> Note: the Copilot/Claude path now supports **tool-calling** (see
> `tool_calling.py`). The OpenAI and Databricks paths support function calling too.

## tool_calling.py

Demonstrates **Claude calling Apeiron functions via the GitHub Copilot SDK**. It
registers two `Function`s (a calculator and a mock weather lookup), asks a
question that needs both, and lets the Copilot SDK run the full tool loop
internally (model -> tool -> model -> ... -> final answer).

```bash
python examples/tool_calling.py
python examples/tool_calling.py --question "What is 8 * 47?"
```

Unlike the OpenAI completion path -- which returns an unresolved `TOOL_CALL`
message for an external agent loop to execute -- the Copilot path executes the
linked functions itself and returns the model's final answer. The resolved calls
are recorded on `msg.extra['copilot_tool_calls']` for replay/observability.

### Example output

```
=== tools invoked by the model (2) ===
  - multiply({'a': 23, 'b': 19}) -> ok
  - get_weather({'city': 'Paris'}) -> ok

=== parsed answer block ===
23 multiplied by 19 equals 437.
The weather in Paris is 21C and sunny.
```

## end_to_end_app.py

A complete end-to-end application: a multi-tool **concierge agent** built on the
toolkit's high-level `Agent`, which gives ONE unified API across providers. It
registers three tools (`calculate` via a safe ast evaluator, `get_weather`,
`word_count`) and answers a batch of tasks.

```bash
python examples/end_to_end_app.py
python examples/end_to_end_app.py --compare           # also run gpt-4.1 (OpenAI)
python examples/end_to_end_app.py --ask "What is 144 / 12?"
```

The same `Agent.call()` drives both providers:

- **Claude via Copilot** -- the Copilot SDK resolves tool calls internally; the
  Agent receives the final answer in one step.
- **gpt-4.1 via OpenAI** -- the Agent runs the loop externally (call -> execute
  the linked function -> feed the result back -> repeat) until a final answer.

### Example output

```
>>> [claude-sonnet-4.5] What is 23 multiplied by 19, and what's the weather in Paris?
    answer: 23 multiplied by 19 equals 437. The weather in Paris is 21C and sunny.
    tools : calculate({'expression': '23 * 19'}), get_weather({'city': 'Paris'})

>>> [gpt-4.1] What is 23 multiplied by 19, and what's the weather in Paris?
    answer: 23 multiplied by 19 is 437. The current weather in Paris is 21C and sunny.
    tools : calculate({'expression': '23 * 19'}), get_weather({'city': 'Paris'})
    cost  : Prompt tokens: 374, Completion tokens: 27, Cost: 0.0010 USD
```
