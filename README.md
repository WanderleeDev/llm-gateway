# LLM Gateway

Gateway FastAPI compatible con la API de OpenAI que reenvía a Ollama del host.

## Desarrollo

```bash
uv sync --all-groups
cp .env.example .env          # ajusta las keys
uv run pytest
uv run uvicorn app.main:create_app --factory --port 8000
```

## Despliegue (Dokploy)

Dokploy construye la imagen con el `Dockerfile` y usa `docker-compose.yml`. El proyecto
encapsula a **Ollama** como service (`ollama/ollama:0.40.6` + volumen `ollama-data`), y un
service one-shot `ollama-init` trae el modelo `lfm2.5:8b` (LFM2.5-8B-A1B) desde el registro
público de Ollama; el gateway lo alcanza por DNS interno (`OLLAMA_URL=http://ollama:11434`,
default del compose). En redeploys el pull es no-op. El Ollama del host (systemd, loopback)
queda intocado para CLI/benchs locales.
El gateway no public ports: el dominio se configura en Dokploy (service `gateway`,
puerto `8000`) y la exposición la gobierna Traefik; el acceso está protegido por
`GATEWAY_API_KEYS`.
Variables obligatorias en el panel de Dokploy:

- `GATEWAY_API_KEYS`: una o más keys separadas por comas.

Opcionales: `ALLOWED_MODELS` (default `lfm2.5:8b`), `OLLAMA_URL`, `MAX_CONCURRENT`,
`QUEUE_TIMEOUT`, `UPSTREAM_TIMEOUT`, `DEFAULT_REASONING_EFFORT`.

> `OLLAMA_URL`: **no la setees en Dokploy**. El compose ya usa el service interno
> `http://ollama:11434` como default. Setearla a `http://localhost:11434` hace que el
> gateway se llame a sí mismo (en un contenedor, `localhost` es el propio contenedor) y
> devuelva 502. Solo es útil en dev local, contra el Ollama del host.

El dominio se configura en Dokploy apuntando al servicio `gateway`, puerto `8000`.

## Uso

El gateway sirve una **doc de uso** en HTML (renderizada con Jinja2), pública y sin auth,
que se arma con la configuración vigente (URL base del request, modelos habilitados y effort
por defecto):

- `GET /docs` y `GET /`: ejemplos de cURL, del SDK de OpenAI y de streaming.

Endpoints de API: `POST /v1/chat/completions` y `GET /v1/models` (ambos con
`Authorization: Bearer <key>`), más `GET /health` sin auth.

## Razonamiento por defecto

Cuando el cliente no manda `reasoning_effort`, el gateway inyecta `DEFAULT_REASONING_EFFORT`
(defecto: `none`), que cierra el thinking de Ollama antes de que queme el presupuesto de
tokens. Puesta a `""` (solo vía .env local) no inyecta nada y deja el comportamiento nativo
de Ollama; en Dokploy un valor vacío resuelve a `none`. El valor que envíe el cliente
siempre manda sobre el default.

> Nota: la opción se respeta a nivel de Ollama, pero no todos los modelos la honran. El LFM 8B
> (`lfm2.5:8b`) la ignora y sigue razonando igual; para él el presupuesto se cubre con
> `max_tokens` holgado.
