# LLM Gateway

A small FastAPI service that exposes an **OpenAI-compatible** Chat Completions and Embeddings
API and forwards requests to [Ollama](https://ollama.com).

**This gateway powers the AI chat on [wanderlee.site](https://www.wanderlee.site).**
Live usage docs: <https://llm.wanderlee.site/docs>

## Why this exists

Ollama's API is built for a trusted local network: no authentication, no limit on concurrent
generations, no request budget. Exposing it directly to a website is a bad idea. This gateway
sits in front of it and adds only what a public deployment actually needs:

- **API-key authentication** (`Authorization: Bearer <key>`), compared in constant time.
- A **concurrency limiter** so one box does not melt: extra requests wait in a bounded queue
  and then receive `429 rate_limit_exceeded` instead of piling up until the upstream dies.
- **OpenAI-shaped errors**, so official SDKs handle failures the way they expect.
- A default **`reasoning_effort`** that is configurable per deployment, so you decide whether
  every client that does not ask pays for thinking. It matches OpenAI out of the box.

It does not try to be a full OpenAI implementation. There are no images or legacy completions
endpoints — only chat, embeddings and models.

## Features

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /v1/chat/completions` | Bearer | Streaming and non-streaming |
| `POST /v1/embeddings` | Bearer | OpenAI shape, forwarded to Ollama |
| `GET /v1/models` | Bearer | Chat and embedding models allowed by config |
| `GET /health` | — | Liveness probe |
| `GET /docs`, `GET /` | — | Public HTML usage guide, rendered with Jinja2 |

Unknown request fields (`temperature`, `tool_choice`, `top_p`, …) are forwarded to Ollama
untouched, so clients do not need a gateway-specific schema.

### Chat request fields

| Field | Type | Notes |
|---|---|---|
| `model` | string | Required; must be one of `ALLOWED_MODELS` |
| `messages` | array | Required; `developer` is forwarded upstream as `system` |
| `max_tokens` | integer | Optional cap; without it the model stops on its own |
| `stream` | boolean | SSE instead of a single JSON body |
| `think` | boolean | Thinking on/off for this request; overrides the default |
| `temperature`, `top_p`, `tools`, `tool_choice`, … | any | Forwarded to Ollama untouched |

## Quick start

```bash
uv sync --all-groups
cp .env.example .env          # set your keys
uv run pytest
uv run uvicorn app.main:create_app --factory --port 8000
```

The gateway **fails closed**: it refuses to start when `GATEWAY_API_KEYS` is empty.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GATEWAY_API_KEYS` | — (required) | One or more keys, comma-separated |
| `ALLOWED_MODELS` | `llama3.2:3b` | Chat models clients may request, comma-separated |
| `ALLOWED_EMBEDDING_MODELS` | *(empty)* | Embedding models clients may request, comma-separated |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Upstream base URL (the compose file overrides it) |
| `MAX_CONCURRENT` | `2` | Generations in flight at the same time |
| `QUEUE_TIMEOUT` | `30` | Seconds a request may wait for a slot before `429` |
| `UPSTREAM_TIMEOUT` | `300` | Upstream read timeout, in seconds |
| `DEFAULT_REASONING_EFFORT` | `medium` | Injected only when the client omits both `think` and `reasoning_effort` |

## Deployment

The whole stack is one Docker Compose project:

- `ollama` — the model server, with a named volume for model weights.
- `ollama-init` — a one-shot service that pulls the chat model into that volume
  (`OLLAMA_CHAT_MODEL` picks a different one; it must match `ALLOWED_MODELS`).
- `ollama-init-embed` — a one-shot service that pulls the embedding model. `ollama pull`
  accepts a single model per invocation, so each family gets its own service. On redeploys
  both pulls are instant no-ops.
- `gateway` — this app. It publishes no ports.

```bash
docker compose up -d --build
```

Only `gateway` needs to be reachable from the outside. Put it behind any reverse proxy that
terminates TLS and forwards to port `8000`, and set `GATEWAY_API_KEYS` in the environment or
in a `.env` file next to the compose file. A host-level Ollama installation stays untouched:
the compose project uses its own volume and its own process.

> **Do not point `OLLAMA_URL` at `localhost` inside a container.** The compose file already
> defaults to the internal service DNS name (`http://ollama:11434`). Inside a container,
> `localhost` is the container itself, so the gateway would call its own port and return
> `502`. The `localhost` value is only useful for local development against a host Ollama on
> `127.0.0.1:11434`.

## Default reasoning effort

When the client sends neither `reasoning_effort` nor `think`, the gateway injects
`DEFAULT_REASONING_EFFORT` (default: `medium`). That mirrors OpenAI, whose reasoning models
think unless told otherwise — so a client that wants the fast path has to ask for it.

Thinking is not free on a small box. Measured on `qwen3.5:4b`, same trivial prompt:

| Setting | Completion tokens | Latency |
|---|---|---|
| `think: false` | 2 | 0.33 s |
| `think: true` | ~120 | 11–15 s |

With `MAX_CONCURRENT=2` that gap is capacity, not just cost. Set
`DEFAULT_REASONING_EFFORT=none` to make the fast path the default instead.

### Asking for thinking per request

Ollama's native `think` switch is accepted, so a client does not have to know about
`reasoning_effort`:

| `think` | Sent upstream as | Effect |
|---|---|---|
| `false` | `reasoning_effort: "none"` | thinking off |
| `true` | nothing | thinking on — the model's own default |
| omitted | `DEFAULT_REASONING_EFFORT` | the configured default |

`think` is a boolean on purpose. The configured model publishes `thinking.values: [false, true]`,
so it has no named levels to pick, and accepting `think: "low"` would promise something Ollama
cannot deliver — it is rejected with `400`. A client that does need a level, on a model that
publishes them, can send `reasoning_effort` itself.

`think` itself is never forwarded — it does not exist on `/v1/chat/completions`. Sending
`reasoning_effort` or the nested `reasoning.effort` directly also works; the default is not
injected on top of either.

```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $GATEWAY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3.5:4b", "messages": [{"role": "user", "content": "hello"}], "think": false, "max_tokens": 200}'
```

```python
r = client.chat.completions.create(
    model="qwen3.5:4b",
    messages=[{"role": "user", "content": "hello"}],
    max_tokens=200,
    extra_body={"think": False},
)
msg = r.choices[0].message
print(msg.content)
print(msg.model_extra.get("reasoning"))   # None when thinking was off
```

The OpenAI SDK does not know `think`, so it travels in `extra_body`; `reasoning` is not part of
the OpenAI schema either, so it is read from `model_extra`.

- A value sent by the client always wins over the default.
- An empty string (only reachable through a local `.env`) injects nothing and leaves Ollama's
  native behaviour untouched. In Docker Compose an empty value resolves to `medium`, because
  Compose v2 cannot distinguish "unset" from "empty".

> `think` exists only on Ollama's native `/api/chat`. On the OpenAI-compatible endpoint this
> gateway calls, the real field is `reasoning_effort` (or `reasoning.effort`), which Ollama maps
> onto its internal `think`. The gateway translates the native switch for convenience, but a
> client talking to Ollama directly must use the OpenAI field: `think: false` sent straight to
> `/v1` is an unknown key and is ignored. Verified on `qwen3.5:4b`: `think: false` directly on
> `/v1` produced 184 reasoning tokens; the same flag on `/api/chat` produced 2.

> Not every model honours the option. `qwen3.5:4b` does. It is boolean-only — `/api/show`
> reports `thinking.values: [false, true]` — so `low`, `medium` and `high` all mean "on";
> named levels only differ on models that publish them. The model this replaced,
> `lfm2.5:8b` (LFM2.5-8B-A1B), ignored the option and kept reasoning anyway; for a model
> like that, cap the budget with a generous `max_tokens` instead.

## Embeddings

`POST /v1/embeddings` is a thin proxy. Ollama already serves the endpoint with the OpenAI
shape, so the gateway enforces `ALLOWED_EMBEDDING_MODELS` and forwards the body; nothing is
translated.

- `input` accepts a string or a list of strings. Token IDs are rejected with `400`, because
  Ollama does not support them and would refuse the request anyway.
- `dimensions` truncates the vector, so a 1024-wide model can serve a 256-wide index.
- Chat and embedding models are separate allowlists: `qwen3.5:4b` is rejected by
  `/v1/embeddings` even though it is a valid chat model.
- The model must be pulled into the compose volume first; `ollama-init-embed` does that on
  deploy (`OLLAMA_EMBEDDING_MODEL` picks a different one).

## Tests

```bash
uv run pytest
```

The suite fakes Ollama with an `httpx` transport, so it needs no model and no network. It
covers auth, concurrency (including slot release when a stream fails), streaming, error
mapping and the usage page.

## License

MIT — see [LICENSE](LICENSE).
