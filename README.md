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

Dokploy construye la imagen con el `Dockerfile` y usa `docker-compose.yml`. El servicio corre
en **host network mode** (`network_mode: host`): así llega al loopback de Ollama
(`OLLAMA_URL=http://localhost:11434`, sin tocar el bind de Ollama) y binda
`0.0.0.0:8000` en la VPS. La exposición pública la gobierna UFW; el acceso está
protegido por `GATEWAY_API_KEYS`. Es el mismo patrón de red que usa el proxy `oci_llm`.
Variables obligatorias en el panel de Dokploy:

- `GATEWAY_API_KEYS`: una o más keys separadas por comas.

Opcionales: `ALLOWED_MODELS`, `MAX_CONCURRENT`, `QUEUE_TIMEOUT`, `UPSTREAM_TIMEOUT`, `DEFAULT_REASONING_EFFORT`.

El dominio se configura en Dokploy apuntando al servicio `gateway`, puerto `8000`.

## Razonamiento por defecto

Cuando el cliente no manda `reasoning_effort`, el gateway inyecta `DEFAULT_REASONING_EFFORT`
(defecto: `none`), que cierra el thinking de Ollama antes de que queme el presupuesto de
tokens. Puesta a `""` (solo vía .env local) no inyecta nada y deja el comportamiento nativo
de Ollama; en Dokploy un valor vacío resuelve a `none`. El valor que envíe el cliente
siempre manda sobre el default.

> Nota: la opción se respeta a nivel de Ollama, pero no todos los modelos la honran. El LFM 8B
> (GGUF local) la ignora y sigue razonando igual; para él el presupuesto se cubre con
> `max_tokens` holgado.
