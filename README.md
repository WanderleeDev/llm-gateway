# LLM Gateway

A small FastAPI service that exposes an **OpenAI-compatible** Chat Completions API and
forwards requests to [Ollama](https://ollama.com).

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
- A default **`reasoning_effort`** that stops thinking models from burning the token budget
  before they answer.

It does not try to be a full OpenAI implementation. There are no embeddings, images or legacy
completions endpoints — only chat and models.

## Features

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /v1/chat/completions` | Bearer | Streaming and non-streaming |
| `GET /v1/models` | Bearer | Only the models allowed by config |
| `GET /health` | — | Liveness probe |
| `GET /docs`, `GET /` | — | Public HTML usage guide, rendered with Jinja2 |

Unknown request fields (`temperature`, `tool_choice`, `top_p`, …) are forwarded to Ollama
untouched, so clients do not need a gateway-specific schema.

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
| `ALLOWED_MODELS` | `lfm2.5:8b` | Models clients may request, comma-separated |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Upstream base URL (the compose file overrides it) |
| `MAX_CONCURRENT` | `2` | Generations in flight at the same time |
| `QUEUE_TIMEOUT` | `30` | Seconds a request may wait for a slot before `429` |
| `UPSTREAM_TIMEOUT` | `300` | Upstream read timeout, in seconds |
| `DEFAULT_REASONING_EFFORT` | `none` | Injected only when the client omits it |

## Deployment

The whole stack is one Docker Compose project:

- `ollama` — the model server, with a named volume for model weights.
- `ollama-init` — a one-shot service that pulls the configured model into that volume.
  On redeploys the pull is an instant no-op.
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

When the client does not send `reasoning_effort`, the gateway injects
`DEFAULT_REASONING_EFFORT` (default: `none`). This turns off Ollama's thinking before it
consumes the token budget — a trivial prompt once cost 3877 tokens of pure reasoning.

- A value sent by the client always wins over the default.
- An empty string (only reachable through a local `.env`) injects nothing and leaves Ollama's
  native behaviour untouched. In Docker Compose an empty value resolves to `none`, because
  Compose v2 cannot distinguish "unset" from "empty".

> Not every model honours the option. `lfm2.5:8b` (LFM2.5-8B-A1B) ignores it and keeps
> reasoning anyway; for that model, cap the budget with a generous `max_tokens` instead.

## Tests

```bash
uv run pytest
```

The suite fakes Ollama with an `httpx` transport, so it needs no model and no network. It
covers auth, concurrency (including slot release when a stream fails), streaming, error
mapping and the usage page.

## License

MIT — see [LICENSE](LICENSE).
