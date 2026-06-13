# vLLM OpenAI-Compatible Deployment Preset

Date: 2026-06-12
Audience: operators using vLLM as the chat provider

Safe4AI talks to vLLM through the existing OpenAI-compatible provider path.
This preset is a runbook for that generic interface; it does not make vLLM a
bundled runtime.

## Supported mode

Use vLLM for chat generation through the OpenAI-compatible provider. Keep
embeddings local through Ollama unless the vLLM deployment also exposes a
compatible embedding model and the customer has approved that data flow.

Recommended first deployment:

- `provider_type`: `openai_compatible`
- `provider_base_url`: `https://<vllm-host>/v1`
- `provider_chat_model`: model served by vLLM, for example
  `Qwen/Qwen2.5-7B-Instruct`
- `embedding_source`: `ollama`
- `embedding_model`: `nomic-embed-text`

## vLLM server contract

The vLLM endpoint must expose:

```text
GET /v1/models
POST /v1/chat/completions
```

The endpoint must be reachable from the Safe4AI backend container or Kubernetes
pod, and the TLS certificate must be trusted by that runtime.

## Safe4AI configuration

Configure through the admin provider settings UI or the `app_config` table.
The API key is required by the settings contract even if the vLLM proxy ignores
it; use a customer-approved placeholder only when the gateway permits it.

For hybrid local embeddings, keep:

```text
OLLAMA_URL=http://ollama:11434
EMBEDDING_MODEL=nomic-embed-text
```

## Smoke checks

From the Safe4AI runtime network:

```bash
curl -fsS https://<vllm-host>/v1/models \
  -H "Authorization: Bearer <provider-api-key>"
curl -fsS http://ollama:11434/api/tags
curl -fsS http://localhost:8000/health
```

Then ask one document-backed question and confirm:

- The answer is grounded in citations.
- Audit logs show the vLLM model name.
- No document content leaves the environment except prompts sent to the vLLM
  endpoint approved in the customer data-flow review.

## Limits

- Safe4AI does not manage vLLM scaling, GPU scheduling, model weights, or
  tokenizer compatibility.
- vLLM support is through the OpenAI-compatible interface only.
- If provider embeddings are enabled, the data-flow diagram and threat model
  must be updated before go-live.
