# Clinical Doc Assist

A Python starter project for building an agentic clinical documentation
assistant. It uses the official OpenAI Python SDK as the transport, points that
client at DeepSeek's OpenAI-compatible API, and implements a tool-calling loop
that is easy to replace with your own application logic.

This is a development scaffold, not a production medical device. Drafted notes
must be reviewed by a qualified clinician.

## What is included

- OpenAI SDK client configured for DeepSeek
- A bounded Chat Completions tool-calling loop
- A clinical-documentation system prompt that is easy to customize
- Example deterministic tools for BMI and note templates
- Interactive and one-shot command-line interfaces
- Typed configuration loaded from `.env`
- Unit tests for the agent loop and tools

See [CHANGELOG.md](CHANGELOG.md) for notable changes.

## Quick start

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Put your DeepSeek API key in `.env`, then run:

```powershell
clinical-doc-assist "Draft a SOAP note from these observations: adult patient reports a sore throat for two days; temperature 37.8 C; no shortness of breath."
```

Run without a prompt for an interactive session:

```powershell
clinical-doc-assist
```

Inside the interactive session, use `/reset` to clear conversation history and
`/exit` to quit.

If the generated console script is blocked by a local execution policy, run the
same CLI as a module or invoke the package entry point:

```powershell
python -m clinical_doc_assist
```

`uv` users can instead run `uv sync --extra dev` followed by
`uv run clinical-doc-assist`.

## Test without an API key

```powershell
pytest
ruff check .
```

## Configuration

The application requires `DEEPSEEK_API_KEY`. It does not fall back to
`OPENAI_API_KEY`, which prevents an OpenAI credential from being sent to a
different API provider by accident.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | required | DeepSeek API credential |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible API root |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Tool-capable model identifier |
| `AGENT_MAX_STEPS` | `8` | Maximum model/tool rounds per user turn |

DeepSeek exposes an OpenAI-compatible Chat Completions endpoint. It does not
provide OpenAI's Responses API, so this project intentionally calls
`client.chat.completions.create(...)` through the `OpenAI` class. The
`deepseek-chat` default is the safe starting point for tool calling.

## Add your own tools

Add a `Tool` to `build_default_tools()` in
[`src/clinical_doc_assist/tools.py`](src/clinical_doc_assist/tools.py). A tool
needs:

1. A stable `name`.
2. A description that tells the model when to use it.
3. A JSON Schema for its arguments.
4. A synchronous handler that returns JSON-serializable data.

Keep tools narrowly scoped and deterministic where possible. Do not expose raw
database access, arbitrary code execution, or PHI-containing logs to the model.
Real patient-data integrations should add authentication, authorization,
audit logging, redaction, and encrypted persistence outside this starter.

To change the model's behavior, edit `DEFAULT_SYSTEM_PROMPT` in
[`src/clinical_doc_assist/agent.py`](src/clinical_doc_assist/agent.py).

## Development

```powershell
pytest
ruff check .
```

The tests do not call the network and do not need an API key.

## API references

- [OpenAI function calling guide](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Python SDK](https://developers.openai.com/api/docs/libraries)
- [DeepSeek API documentation](https://api-docs.deepseek.com/)
