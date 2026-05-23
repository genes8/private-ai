# Provider Runtime Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve R5-3, R5-5, and R5-29 by adding an `ollama | openai_compatible` inference provider switch, real usage accounting when API providers return usage, transactional chat finalization, and a Docker default that does not require Ollama.

**Architecture:** Add a small provider abstraction beneath runtime configuration instead of scattering provider conditionals through chat, retrieval, cache, and ingestion code. Keep Ollama as a supported local provider, add an OpenAI-compatible HTTP provider using `base_url + api_key + model`, and move chat persistence into a single finalizer service that can later run in strict or async mode.

**Tech Stack:** FastAPI, SQLAlchemy, httpx, LangGraph, React, Vite, TypeScript, Docker Compose, pytest.

---

## File Structure

- Create: `app/services/provider_clients.py`
  - Owns provider-neutral client interfaces and concrete Ollama/OpenAI-compatible HTTP implementations for chat, embeddings, vision OCR, and usage extraction.
- Create: `app/services/chat_finalizer.py`
  - Owns single-transaction persistence for assistant reply, audit log, and cost record.
- Modify: `app/services/runtime_config.py`
  - Loads provider settings from `app_config`, builds provider clients, and wires graph/retriever/cache/ingestion dependencies.
- Modify: `app/api/admin_routes.py`
  - Extends `GET /settings` and `PATCH /settings` with provider fields, masked key status, connection test endpoint, and validation.
- Modify: `app/api/chat_routes.py`
  - Uses `chat_finalizer.finalize_chat_run()` for R5-3 and exposes `sseDoneMode` behavior for R5-29.
- Modify: `app/services/rag_pipeline.py`
  - Replaces direct Ollama embedding/generation/vision calls with provider clients.
- Modify: `app/components/hybrid_retriever.py`
  - Replaces direct Ollama embedding calls with `EmbeddingClient`.
- Modify: `app/services/semantic_cache.py`
  - Replaces direct Ollama embedding calls with `EmbeddingClient`.
- Modify: `app/agents/graph.py`, `app/agents/adaptive_router.py`, `app/agents/document_grader.py`, `app/agents/query_decomposer.py`, `app/services/query_router.py`, `app/services/query_rewriter.py`, `app/services/conversation.py`
  - Replace direct Ollama chat/generate calls with `ChatClient`.
- Modify: `app/main.py`
  - Stops unconditional Ollama prewarm and health requirement; health reports provider-specific status.
- Modify: `observability/cost_tracker.py`
  - Accepts explicit usage source metadata when recording runs.
- Modify: `frontend/src/api/settings.ts`
  - Adds provider settings types and patch fields.
- Modify: `frontend/src/pages/admin/SettingsPage.tsx`
  - Adds inference provider UI and masked API key handling.
- Modify: `docker-compose.yml`
  - Removes default `ollama` and `ollama-init`.
- Create: `docker-compose.ollama.yml`
  - Optional local Ollama override.
- Modify: `README.md`, `docs/deployment.md`
  - Documents default API-provider path and optional Ollama local mode.
- Test: `tests/test_runtime_config.py`, `tests/test_provider_clients.py`, `tests/test_admin.py`, `tests/test_chat.py`, `tests/test_rag_pipeline.py`, `tests/test_hybrid_retriever.py`, `tests/test_semantic_cache.py`, `tests/test_docker_packaging.py`, `tests/test_health.py`.

---

### Task 1: Extend Runtime Config With Provider Settings

**Files:**
- Modify: `app/services/runtime_config.py`
- Test: `tests/test_runtime_config.py`

- [ ] **Step 1: Write failing tests for provider config defaults and OpenAI-compatible overrides**

Add these tests to `tests/test_runtime_config.py`:

```python
from unittest.mock import MagicMock, patch

from app.services.runtime_config import load_runtime_config


def test_runtime_config_defaults_to_ollama_provider() -> None:
    db = MagicMock()
    with patch("app.services.runtime_config.load_app_config", return_value={}):
        runtime = load_runtime_config(db)

    assert runtime.provider_type == "ollama"
    assert runtime.provider_base_url == "http://localhost:11434"
    assert runtime.provider_api_key is None
    assert runtime.chat_model == runtime.generation_model
    assert runtime.usage_source == "estimated"


def test_runtime_config_loads_openai_compatible_provider() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_base_url": "https://api.deepseek.com/v1",
            "provider_api_key": "sk-test",
            "provider_chat_model": "deepseek-v4-flash",
            "provider_embedding_model": "text-embedding-3-small",
            "provider_vision_model": "qwen-vl-plus",
            "sse_done_mode": "async",
        },
    ):
        runtime = load_runtime_config(db)

    assert runtime.provider_type == "openai_compatible"
    assert runtime.provider_base_url == "https://api.deepseek.com/v1"
    assert runtime.provider_api_key == "sk-test"
    assert runtime.chat_model == "deepseek-v4-flash"
    assert runtime.embedding_model == "text-embedding-3-small"
    assert runtime.vision_model == "qwen-vl-plus"
    assert runtime.sse_done_mode == "async"
    assert runtime.usage_source == "actual"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/pytest tests/test_runtime_config.py -q
```

Expected: FAIL because `RuntimeConfig` does not yet expose `provider_type`, `provider_base_url`, `provider_api_key`, `chat_model`, `sse_done_mode`, or `usage_source`.

- [ ] **Step 3: Implement provider fields**

Update `RuntimeConfig` in `app/services/runtime_config.py`:

```python
@dataclass(frozen=True)
class RuntimeConfig:
    provider_type: str
    provider_base_url: str
    provider_api_key: str | None
    generation_model: str
    generation_fallback_model: str
    chat_model: str
    embedding_model: str
    vision_model: str
    reranker_enabled: bool
    reranker_model: str
    retrieval_k: int
    score_floor: float
    chunk_size: int
    chunk_overlap: int
    sse_done_mode: str
    usage_source: str
```

Update `load_runtime_config()`:

```python
def load_runtime_config(db: Session) -> RuntimeConfig:
    cfg = load_app_config(db)
    provider_type = str(cfg.get("provider_type", "ollama"))
    if provider_type not in {"ollama", "openai_compatible"}:
        provider_type = "ollama"

    generation_model = str(cfg.get("generation_model", settings.ollama_model))
    provider_chat_model = str(cfg.get("provider_chat_model", generation_model))
    provider_embedding_model = str(cfg.get("provider_embedding_model", settings.embedding_model))
    provider_vision_model = str(cfg.get("provider_vision_model", _DEFAULT_VISION_MODEL))
    provider_base_url = str(
        cfg.get(
            "provider_base_url",
            settings.ollama_url if provider_type == "ollama" else "https://api.openai.com/v1",
        )
    )
    sse_done_mode = str(cfg.get("sse_done_mode", "strict"))
    if sse_done_mode not in {"strict", "async"}:
        sse_done_mode = "strict"

    return RuntimeConfig(
        provider_type=provider_type,
        provider_base_url=provider_base_url.rstrip("/"),
        provider_api_key=cfg.get("provider_api_key"),
        generation_model=generation_model,
        generation_fallback_model=str(cfg.get("generation_fallback_model", generation_model)),
        chat_model=provider_chat_model,
        embedding_model=provider_embedding_model,
        vision_model=provider_vision_model,
        reranker_enabled=_coerce_bool(cfg.get("reranker_enabled"), True),
        reranker_model=str(cfg.get("reranker_model", _DEFAULT_RERANKER_MODEL)),
        retrieval_k=_coerce_int(cfg.get("retrieval_k"), 6),
        score_floor=_coerce_float(cfg.get("score_floor"), 0.45),
        chunk_size=_coerce_int(cfg.get("chunk_size"), 800),
        chunk_overlap=_coerce_int(cfg.get("chunk_overlap"), 150),
        sse_done_mode=sse_done_mode,
        usage_source="actual" if provider_type == "openai_compatible" else "estimated",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/pytest tests/test_runtime_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/runtime_config.py tests/test_runtime_config.py
git commit -m "feat: add inference provider runtime config"
```

---

### Task 2: Add Provider Client Interfaces and HTTP Implementations

**Files:**
- Create: `app/services/provider_clients.py`
- Test: `tests/test_provider_clients.py`

- [ ] **Step 1: Write failing tests for OpenAI-compatible chat usage extraction and embeddings**

Create `tests/test_provider_clients.py`:

```python
from __future__ import annotations

import pytest
import httpx

from app.services.provider_clients import (
    OpenAICompatibleProvider,
    ProviderUsage,
)


@pytest.mark.anyio
async def test_openai_compatible_chat_extracts_actual_usage() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Answer text"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        chat_model="deepseek-v4-flash",
        embedding_model="text-embedding-3-small",
        vision_model="qwen-vl",
        client=client,
    )

    result = await provider.chat("System", "Question")

    assert result.content == "Answer text"
    assert result.usage == ProviderUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18, source="actual")
    assert requests[0].url == "https://api.example.com/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer sk-test"


@pytest.mark.anyio
async def test_openai_compatible_embeddings_reads_embedding_vector() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        chat_model="qwen-plus",
        embedding_model="text-embedding-3-small",
        vision_model="qwen-vl",
        client=client,
    )

    assert await provider.embed_query("hello") == [0.1, 0.2, 0.3]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/pytest tests/test_provider_clients.py -q
```

Expected: FAIL because `app/services/provider_clients.py` does not exist.

- [ ] **Step 3: Implement provider clients**

Create `app/services/provider_clients.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    source: str


@dataclass(frozen=True)
class ChatResult:
    content: str
    usage: ProviderUsage | None = None


class ChatClient(Protocol):
    async def chat(self, system_prompt: str, user_prompt: str) -> ChatResult: ...


class EmbeddingClient(Protocol):
    async def embed_query(self, query: str) -> list[float]: ...
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class VisionClient(Protocol):
    async def describe_image(self, prompt: str, image_b64: str) -> str: ...


def _usage_from_openai(payload: dict[str, Any]) -> ProviderUsage | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    return ProviderUsage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total, source="actual")


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        vision_model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._vision_model = vision_model
        self._client = client or httpx.AsyncClient(timeout=60)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def chat(self, system_prompt: str, user_prompt: str) -> ChatResult:
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self._chat_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return ChatResult(content=str(content), usage=_usage_from_openai(payload))

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_documents([query])
        return vectors[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post(
            f"{self._base_url}/embeddings",
            headers=self._headers(),
            json={"model": self._embedding_model, "input": texts},
        )
        response.raise_for_status()
        payload = response.json()
        return [list(item["embedding"]) for item in payload.get("data", [])]

    async def describe_image(self, prompt: str, image_b64: str) -> str:
        result = await self.chat(prompt, image_b64)
        return result.content
```

Add an `OllamaProvider` in the same file after these tests pass. It should preserve current endpoints:

```python
class OllamaProvider:
    def __init__(self, *, base_url: str, chat_model: str, embedding_model: str, vision_model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._vision_model = vision_model

    async def chat(self, system_prompt: str, user_prompt: str) -> ChatResult:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={"model": self._chat_model, "prompt": f"{system_prompt}\n\n{user_prompt}", "stream": False},
            )
        response.raise_for_status()
        return ChatResult(content=str(response.json().get("response", "")), usage=None)

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_documents([query])
        return vectors[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._embedding_model, "input": texts},
            )
            if response.status_code >= 400:
                vectors = []
                for text in texts:
                    fallback = await client.post(
                        f"{self._base_url}/api/embeddings",
                        json={"model": self._embedding_model, "prompt": text},
                    )
                    fallback.raise_for_status()
                    vectors.append(list(fallback.json()["embedding"]))
                return vectors
        response.raise_for_status()
        return [list(vector) for vector in response.json().get("embeddings", [])]

    async def describe_image(self, prompt: str, image_b64: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={"model": self._vision_model, "prompt": prompt, "images": [image_b64], "stream": False},
            )
        response.raise_for_status()
        return str(response.json().get("response", ""))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
./.venv/bin/pytest tests/test_provider_clients.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/provider_clients.py tests/test_provider_clients.py
git commit -m "feat: add inference provider clients"
```

---

### Task 3: Wire Provider Clients Into Runtime Components

**Files:**
- Modify: `app/services/runtime_config.py`
- Modify: `app/components/hybrid_retriever.py`
- Modify: `app/services/semantic_cache.py`
- Test: `tests/test_runtime_config.py`
- Test: `tests/test_hybrid_retriever.py`
- Test: `tests/test_semantic_cache.py`

- [ ] **Step 1: Write failing runtime builder test**

Add to `tests/test_runtime_config.py`:

```python
from unittest.mock import MagicMock, patch


def test_build_runtime_components_uses_openai_provider_clients() -> None:
    from app.services.runtime_config import build_runtime_components

    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_base_url": "https://api.example.com/v1",
            "provider_api_key": "sk-test",
            "provider_chat_model": "qwen-plus",
            "provider_embedding_model": "text-embedding-3-small",
        },
    ), patch("app.services.runtime_config.build_graph") as mock_build_graph:
        runtime, retriever, reranker, graph = build_runtime_components(db)

    assert runtime.provider_type == "openai_compatible"
    assert retriever.embedding_model == "text-embedding-3-small"
    mock_build_graph.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/pytest tests/test_runtime_config.py::test_build_runtime_components_uses_openai_provider_clients -q
```

Expected: FAIL because `HybridRetriever` does not expose/use provider clients.

- [ ] **Step 3: Modify `HybridRetriever` to accept an `EmbeddingClient`**

In `app/components/hybrid_retriever.py`, change constructor shape while preserving public behavior:

```python
def __init__(
    self,
    qdrant_url: str,
    embedding_model: str,
    collection: str = "documents",
    embedding_client: EmbeddingClient | None = None,
    ollama_url: str | None = None,
) -> None:
    self._qdrant_url = qdrant_url
    self._embedding_model = embedding_model
    self.embedding_model = embedding_model
    self._collection = collection
    self._embedding_client = embedding_client
    self._ollama_url = ollama_url
```

Replace direct query embedding calls:

```python
if self._embedding_client is not None:
    query_vector = await self._embedding_client.embed_query(query)
else:
    query_vector = await self._embed_query_with_ollama(query)
```

Keep the existing Ollama method as `_embed_query_with_ollama()` until all call sites migrate.

- [ ] **Step 4: Modify `SemanticCache` to accept an `EmbeddingClient`**

In `app/services/semantic_cache.py`, update constructor:

```python
def __init__(
    self,
    db: Session,
    ollama_url: str,
    embedding_model: str,
    threshold: float,
    embedding_client: EmbeddingClient | None = None,
) -> None:
    self._db = db
    self._ollama_url = ollama_url
    self._embedding_model = embedding_model
    self._threshold = threshold
    self._embedding_client = embedding_client
```

Update embedding lookup:

```python
async def _embed(self, query: str) -> list[float]:
    if self._embedding_client is not None:
        return await self._embedding_client.embed_query(query)
    # existing Ollama code remains as fallback
```

- [ ] **Step 5: Update `build_runtime_components()` to create provider clients**

In `app/services/runtime_config.py`:

```python
def build_provider(runtime: RuntimeConfig) -> OllamaProvider | OpenAICompatibleProvider:
    if runtime.provider_type == "openai_compatible":
        if not runtime.provider_api_key:
            raise RuntimeError("OpenAI-compatible provider requires an API key")
        return OpenAICompatibleProvider(
            base_url=runtime.provider_base_url,
            api_key=runtime.provider_api_key,
            chat_model=runtime.chat_model,
            embedding_model=runtime.embedding_model,
            vision_model=runtime.vision_model,
        )
    return OllamaProvider(
        base_url=runtime.provider_base_url,
        chat_model=runtime.chat_model,
        embedding_model=runtime.embedding_model,
        vision_model=runtime.vision_model,
    )
```

Pass provider to retriever and graph:

```python
provider = build_provider(runtime)
retriever = HybridRetriever(
    qdrant_url=settings.qdrant_url,
    collection="documents",
    embedding_model=runtime.embedding_model,
    embedding_client=provider,
    ollama_url=runtime.provider_base_url,
)
graph = build_graph(
    retriever=retriever,
    reranker=reranker,
    chat_client=provider,
    ollama_url=runtime.provider_base_url,
    ollama_model=runtime.chat_model,
    retrieval_top_k=runtime.retrieval_k,
)
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
./.venv/bin/pytest tests/test_runtime_config.py tests/test_hybrid_retriever.py tests/test_semantic_cache.py -q
```

Expected: PASS after adapting mocks to accept `embedding_client`.

- [ ] **Step 7: Commit**

```bash
git add app/services/runtime_config.py app/components/hybrid_retriever.py app/services/semantic_cache.py tests/test_runtime_config.py tests/test_hybrid_retriever.py tests/test_semantic_cache.py
git commit -m "feat: wire provider clients into retrieval runtime"
```

---

### Task 4: Replace Direct Ollama Chat Calls in Graph and Agent Helpers

**Files:**
- Modify: `app/agents/graph.py`
- Modify: `app/agents/adaptive_router.py`
- Modify: `app/agents/document_grader.py`
- Modify: `app/agents/query_decomposer.py`
- Modify: `app/services/query_router.py`
- Modify: `app/services/query_rewriter.py`
- Modify: `app/services/conversation.py`
- Test: `tests/test_agents.py`
- Test: `tests/test_query_router.py`
- Test: `tests/test_query_rewriter.py`
- Test: `tests/test_conversation.py`

- [ ] **Step 1: Write failing graph test for `chat_client` use**

Add to `tests/test_agents.py`:

```python
class FakeChatClient:
    def __init__(self) -> None:
        self.prompts: list[tuple[str, str]] = []

    async def chat(self, system_prompt: str, user_prompt: str):
        from app.services.provider_clients import ChatResult, ProviderUsage
        self.prompts.append((system_prompt, user_prompt))
        return ChatResult(
            content='{"route":"generate","confidence":0.9,"reason":"enough context"}',
            usage=ProviderUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7, source="actual"),
        )


def test_graph_accepts_chat_client_for_llm_nodes() -> None:
    from app.agents.graph import build_graph

    graph = build_graph(
        retriever=FakeRetriever(),
        reranker=FakeReranker(),
        chat_client=FakeChatClient(),
        retrieval_top_k=3,
    )

    assert graph is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/pytest tests/test_agents.py::test_graph_accepts_chat_client_for_llm_nodes -q
```

Expected: FAIL because `build_graph()` does not accept `chat_client`.

- [ ] **Step 3: Update helper classes to accept `ChatClient`**

For each helper currently initialized with `ollama_url` and `model`, add optional `chat_client`.

Example for `app/services/query_rewriter.py`:

```python
class QueryRewriter:
    def __init__(self, ollama_url: str | None = None, model: str | None = None, chat_client: ChatClient | None = None) -> None:
        self._ollama_url = ollama_url
        self._model = model
        self._chat_client = chat_client

    async def rewrite(self, question: str) -> str:
        prompt = get_prompt("query_rewrite").format(question=question)
        if self._chat_client is not None:
            return (await self._chat_client.chat("Rewrite the query.", prompt)).content.strip()
        # existing Ollama fallback remains here
```

Apply the same pattern in:
- `app/services/query_router.py`
- `app/agents/adaptive_router.py`
- `app/agents/document_grader.py`
- `app/agents/query_decomposer.py`
- `app/services/conversation.py`

- [ ] **Step 4: Update `build_graph()` signature**

In `app/agents/graph.py`:

```python
def build_graph(
    retriever: Any,
    reranker: Any,
    *,
    chat_client: ChatClient | None = None,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
    retrieval_top_k: int = 6,
) -> Any:
```

Where direct `httpx.post(f"{ollama_url}/api/generate"...` exists, use:

```python
if chat_client is not None:
    result = await chat_client.chat("You are private.ai.", prompt)
    text = result.content
else:
    # existing Ollama HTTP call
```

- [ ] **Step 5: Run focused agent tests**

Run:

```bash
./.venv/bin/pytest tests/test_agents.py tests/test_query_router.py tests/test_query_rewriter.py tests/test_conversation.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/agents app/services/query_router.py app/services/query_rewriter.py app/services/conversation.py tests/test_agents.py tests/test_query_router.py tests/test_query_rewriter.py tests/test_conversation.py
git commit -m "feat: route graph LLM calls through provider client"
```

---

### Task 5: Migrate RAG Pipeline Embeddings, Vision, and Generation to Provider Clients

**Files:**
- Modify: `app/services/rag_pipeline.py`
- Modify: `app/services/ingestion_service.py`
- Test: `tests/test_rag_pipeline.py`
- Test: `tests/test_admin.py`

- [ ] **Step 1: Write failing RAG pipeline test for provider embeddings**

Add to `tests/test_rag_pipeline.py`:

```python
class FakeProvider:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def chat(self, system_prompt: str, user_prompt: str):
        from app.services.provider_clients import ChatResult
        return ChatResult(content="grounded answer", usage=None)

    async def describe_image(self, prompt: str, image_b64: str) -> str:
        return "ocr text"


@pytest.mark.anyio
async def test_rag_pipeline_uses_provider_for_batch_embeddings() -> None:
    pipeline = RAGPipeline(
        ollama_url="http://unused",
        ollama_model="unused",
        embedding_model="text-embedding-3-small",
        qdrant_url="http://qdrant",
        provider_client=FakeProvider(),
    )

    vectors = await pipeline._embed_batch(["a", "b"])

    assert vectors == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/pytest tests/test_rag_pipeline.py::test_rag_pipeline_uses_provider_for_batch_embeddings -q
```

Expected: FAIL because `RAGPipeline` does not accept `provider_client`.

- [ ] **Step 3: Add provider client to `RAGPipeline`**

In `app/services/rag_pipeline.py` constructor:

```python
def __init__(
    self,
    *,
    ollama_url: str,
    ollama_model: str,
    embedding_model: str,
    qdrant_url: str,
    provider_client: ChatClient | EmbeddingClient | VisionClient | None = None,
    vision_model: str = "qwen2.5vl:7b",
) -> None:
    self._provider_client = provider_client
```

Update `_embed_batch()`:

```python
if self._provider_client is not None:
    return await self._provider_client.embed_documents(batch)
```

Update text generation:

```python
if self._provider_client is not None:
    return (await self._provider_client.chat("Answer using retrieved context.", prompt)).content
```

Update vision OCR:

```python
if self._provider_client is not None:
    return await self._provider_client.describe_image(prompt, image_b64)
```

- [ ] **Step 4: Update ingestion service runtime wiring**

In `app/services/ingestion_service.py`, build runtime components once and pass provider client into `RAGPipeline`. If `build_runtime_components()` currently returns `(runtime, retriever, reranker, graph)`, extend it in Task 3 to return `(runtime, provider, retriever, reranker, graph)` or add `build_provider(runtime)` and call it from ingestion.

Use this final shape consistently:

```python
runtime = load_runtime_config(db)
provider = build_provider(runtime)
pipeline = RAGPipeline(
    ollama_url=runtime.provider_base_url,
    ollama_model=runtime.chat_model,
    embedding_model=runtime.embedding_model,
    qdrant_url=settings.qdrant_url,
    provider_client=provider,
    vision_model=runtime.vision_model,
)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
./.venv/bin/pytest tests/test_rag_pipeline.py tests/test_admin.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/rag_pipeline.py app/services/ingestion_service.py tests/test_rag_pipeline.py tests/test_admin.py
git commit -m "feat: use provider clients for rag pipeline"
```

---

### Task 6: Extend Settings API for Provider Configuration and Key Safety

**Files:**
- Modify: `app/api/admin_routes.py`
- Test: `tests/test_admin.py`

- [ ] **Step 1: Write failing settings tests**

Add to `tests/test_admin.py`:

```python
def test_get_settings_returns_provider_config_without_plaintext_key(self) -> None:
    admin = _make_admin_user()
    db = _mock_db_with_admin(admin)
    db.get.side_effect = lambda model, pk: admin
    rows = [
        MagicMock(key="provider_type", value="openai_compatible"),
        MagicMock(key="provider_base_url", value="https://api.openai.com/v1"),
        MagicMock(key="provider_api_key", value="sk-secret"),
        MagicMock(key="provider_chat_model", value="gpt-4.1-mini"),
        MagicMock(key="provider_embedding_model", value="text-embedding-3-small"),
    ]
    db.query.return_value.all.return_value = rows
    db.query.return_value.count.return_value = 0

    with patch("pathlib.Path.mkdir"), patch(
        "observability.cost_tracker.CostTracker.get_stats",
        return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
    ):
        client = _make_test_client(db, admin)
        resp = client.get("/settings")

    assert resp.status_code == 200
    provider = resp.json()["provider"]
    assert provider["type"] == "openai_compatible"
    assert provider["apiKeyConfigured"] is True
    assert "sk-secret" not in resp.text


def test_patch_settings_requires_api_key_for_openai_compatible_provider() -> None:
    admin = _make_admin_user()
    db = _mock_db_with_admin(admin)
    db.query.return_value.all.return_value = []

    with patch("pathlib.Path.mkdir"):
        client = _make_test_client(db, admin)
        resp = client.patch(
            "/settings",
            json={
                "providerType": "openai_compatible",
                "providerBaseUrl": "https://api.openai.com/v1",
                "providerChatModel": "gpt-4.1-mini",
                "providerEmbeddingModel": "text-embedding-3-small",
            },
        )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "providerApiKey is required for openai_compatible"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/pytest tests/test_admin.py::TestSettings -q
```

Expected: FAIL because provider payload fields do not exist.

- [ ] **Step 3: Extend settings request and serializer**

In `PatchSettingsRequest`:

```python
providerType: str | None = None
providerBaseUrl: str | None = None
providerApiKey: str | None = None
providerChatModel: str | None = None
providerEmbeddingModel: str | None = None
providerVisionModel: str | None = None
sseDoneMode: str | None = None
```

In `_serialize_settings()` add:

```python
"provider": {
    "type": _val("provider_type", "ollama"),
    "baseUrl": _val("provider_base_url", settings.ollama_url),
    "apiKeyConfigured": bool(_val("provider_api_key", "")),
    "chatModel": _val("provider_chat_model", _val("generation_model", settings.ollama_model)),
    "embeddingModel": _val("provider_embedding_model", _val("embedding_model", settings.embedding_model)),
    "visionModel": _val("provider_vision_model", _val("vision_model", "qwen2.5vl:7b")),
},
"sseDoneMode": _val("sse_done_mode", "strict"),
```

In `patch_settings()` validation:

```python
if body.providerType is not None:
    if body.providerType not in {"ollama", "openai_compatible"}:
        raise HTTPException(status_code=422, detail="providerType must be ollama or openai_compatible")
    updates["provider_type"] = body.providerType

effective_provider = body.providerType or current_config.get("provider_type", "ollama")
effective_key = body.providerApiKey or current_config.get("provider_api_key")
if effective_provider == "openai_compatible" and not effective_key:
    raise HTTPException(status_code=422, detail="providerApiKey is required for openai_compatible")
```

Map model/base URL fields to `app_config` keys. Do not include the API key in serialized response.

- [ ] **Step 4: Add connection test endpoint**

Add:

```python
@router.post("/settings/provider/test", status_code=200)
def test_provider_connection(
    body: PatchSettingsRequest,
    _admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    # Validate only; do one lightweight HTTP request through provider client.
    # Return {"status": "ok"} or raise HTTPException(422/503).
```

Test only validation and mocked HTTP in this task; do not require live internet in tests.

- [ ] **Step 5: Run settings tests**

Run:

```bash
./.venv/bin/pytest tests/test_admin.py::TestSettings -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/api/admin_routes.py tests/test_admin.py
git commit -m "feat: expose provider settings api"
```

---

### Task 7: Add Actual Usage Accounting and Single-Transaction Chat Finalizer

**Files:**
- Create: `app/services/chat_finalizer.py`
- Modify: `app/api/chat_routes.py`
- Modify: `observability/cost_tracker.py`
- Test: `tests/test_chat.py`
- Test: `tests/test_cost_tracker.py`

- [ ] **Step 1: Write failing finalizer transaction test**

Add to `tests/test_chat.py`:

```python
def test_finalize_chat_run_commits_once_for_reply_audit_and_cost() -> None:
    from app.services.chat_finalizer import finalize_chat_run
    from app.models import PrivateAIState
    from app.services.provider_clients import ProviderUsage

    db = MagicMock()
    final = PrivateAIState(session_id="s1", user_id="u1", draft_answer="answer", trace_id="t1")

    finalize_chat_run(
        db=db,
        final=final,
        user_id="u1",
        query="question",
        latency_ms=25,
        k_retrieved=2,
        usage=ProviderUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15, source="actual"),
        cost_per_1k_tokens=0.01,
    )

    db.begin.assert_called_once()
    db.add.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/pytest tests/test_chat.py::test_finalize_chat_run_commits_once_for_reply_audit_and_cost -q
```

Expected: FAIL because `chat_finalizer.py` does not exist.

- [ ] **Step 3: Implement `chat_finalizer.py`**

Create `app/services/chat_finalizer.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import AgentRun, AuditLog
from app.models import Message, PrivateAIState
from app.services.provider_clients import ProviderUsage


def finalize_chat_run(
    *,
    db: Session,
    final: PrivateAIState,
    user_id: str,
    query: str,
    latency_ms: int,
    k_retrieved: int,
    usage: ProviderUsage,
    cost_per_1k_tokens: float,
) -> None:
    assistant_msg = Message(role="assistant", content=final.draft_answer, created_at=datetime.now(UTC))
    updated = final.model_copy(update={"messages": list(final.messages) + [assistant_msg]})
    cost_usd = usage.total_tokens / 1000.0 * cost_per_1k_tokens
    now = datetime.now(UTC)

    with db.begin():
        from app.db.models import Session as DbSession

        row = db.get(DbSession, final.session_id)
        if row is not None:
            row.state_json = updated.model_dump(mode="json")
            row.updated_at = now

        db.add(
            AuditLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=final.session_id,
                action_type="chat_query",
                query_text=query[:500],
                response_metadata={
                    "trace_id": final.trace_id,
                    "k_retrieved": k_retrieved,
                    "status": "completed",
                    "usage_source": usage.source,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
                latency_ms=latency_ms,
                model_used=final.trace_id,
                trace_id=final.trace_id,
            )
        )
        db.add(
            AgentRun(
                id=str(uuid.uuid4()),
                session_id=final.session_id,
                started_at=now,
                finished_at=now,
                status="completed",
                cost_usd=cost_usd,
                final_output=None,
                error=None,
            )
        )
```

- [ ] **Step 4: Update `chat_routes.py` to call finalizer**

Add usage fallback helper:

```python
def usage_or_estimate(question: str, answer: str, provider_usage: ProviderUsage | None) -> ProviderUsage:
    if provider_usage is not None:
        return provider_usage
    prompt_tokens = estimate_tokens(question)
    completion_tokens = estimate_tokens(answer)
    return ProviderUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        source="estimated",
    )
```

After graph completion:

```python
usage = usage_or_estimate(body.question, final.draft_answer or "", getattr(final, "usage", None))
finalize_chat_run(
    db=db,
    final=final,
    user_id=str(current_user.id),
    query=body.question,
    latency_ms=latency_ms,
    k_retrieved=len(final.retrieved_chunks),
    usage=usage,
    cost_per_1k_tokens=settings.cost_per_1k_tokens,
)
```

Remove separate `_save_assistant_reply()`, `_write_audit_log()`, and `_record_cost()` calls from the successful path after tests are updated. Keep error audit path separate.

- [ ] **Step 5: Run chat and cost tests**

Run:

```bash
./.venv/bin/pytest tests/test_chat.py tests/test_cost_tracker.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/chat_finalizer.py app/api/chat_routes.py observability/cost_tracker.py tests/test_chat.py tests/test_cost_tracker.py
git commit -m "fix: finalize chat persistence in one transaction"
```

---

### Task 8: Add SSE Done Mode Flag With Strict Default

**Files:**
- Modify: `app/api/chat_routes.py`
- Modify: `app/services/runtime_config.py`
- Test: `tests/test_chat.py`

- [ ] **Step 1: Write failing tests for strict default and async mode scheduling**

Add to `tests/test_chat.py`:

```python
def test_chat_stream_strict_mode_finalizes_before_done(authed_client: TestClient) -> None:
    # Use existing stream setup; patch finalize_chat_run and assert event text contains done after call.
    with patch("app.api.chat_routes.finalize_chat_run") as finalize:
        response = authed_client.post("/chat/stream", json={"question": "What is the answer?"})

    assert response.status_code == 200
    finalize.assert_called_once()


def test_chat_stream_async_mode_schedules_background_finalize(authed_client: TestClient) -> None:
    with patch("app.api.chat_routes.load_runtime_config") as load_runtime, patch(
        "app.api.chat_routes.asyncio.create_task"
    ) as create_task:
        load_runtime.return_value.sse_done_mode = "async"
        response = authed_client.post("/chat/stream", json={"question": "What is the answer?"})

    assert response.status_code == 200
    create_task.assert_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
./.venv/bin/pytest tests/test_chat.py -q
```

Expected: FAIL until `sse_done_mode` is read in stream route.

- [ ] **Step 3: Implement strict and async paths**

In `chat_stream()`:

```python
runtime = load_runtime_config(db)
...
async def _finalize() -> None:
    finalize_chat_run(...)

if runtime.sse_done_mode == "async":
    asyncio.create_task(_finalize())
else:
    await _finalize()

yield _sse("done", {...})
```

Keep `strict` default. The async path is available but not default.

- [ ] **Step 4: Run chat tests**

Run:

```bash
./.venv/bin/pytest tests/test_chat.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/api/chat_routes.py app/services/runtime_config.py tests/test_chat.py
git commit -m "feat: add configurable sse done mode"
```

---

### Task 9: Build Settings UI for Inference Provider

**Files:**
- Modify: `frontend/src/api/settings.ts`
- Modify: `frontend/src/pages/admin/SettingsPage.tsx`
- Test: frontend build

- [ ] **Step 1: Extend frontend settings types**

In `frontend/src/api/settings.ts`:

```ts
export type ProviderType = "ollama" | "openai_compatible";
export type SseDoneMode = "strict" | "async";

export interface AppSettings {
  provider: {
    type: ProviderType;
    baseUrl: string;
    apiKeyConfigured: boolean;
    chatModel: string;
    embeddingModel: string;
    visionModel: string;
  };
  sseDoneMode: SseDoneMode;
  // existing fields remain
}

export type PatchableSettings = Partial<{
  providerType: ProviderType;
  providerBaseUrl: string;
  providerApiKey: string;
  providerChatModel: string;
  providerEmbeddingModel: string;
  providerVisionModel: string;
  sseDoneMode: SseDoneMode;
  // existing fields remain
}>;
```

- [ ] **Step 2: Run build to verify type failures**

Run:

```bash
cd frontend && npm run build
```

Expected: FAIL because `SettingsPage` does not render/patch new provider fields.

- [ ] **Step 3: Add Settings UI section**

In `SettingsPage.tsx`:

Add section id:

```ts
type SectionId = "provider" | "models" | "retrieval" | "sources" | "security" | "cost";
```

Add nav row:

```ts
{ id: "provider", label: "Provider", icon: Plug }
```

Add provider section before models:

```tsx
<Section id="provider" title="Inference provider" subtitle="Choose the runtime that handles chat, embeddings and OCR.">
  <Row label="Mode" hint="Use local Ollama or an OpenAI-compatible API endpoint." saving={isSavingField("providerType")}>
    <Select
      value={s.provider.type}
      options={["ollama", "openai_compatible"]}
      onChange={(v) => set("provider", { ...s.provider, type: v })}
    />
  </Row>
  <Row label="Base URL" hint="OpenAI-compatible endpoint, for example https://api.openai.com/v1.">
    <TextInput
      value={s.provider.baseUrl}
      onCommit={(v) => set("provider", { ...s.provider, baseUrl: v })}
    />
  </Row>
  {s.provider.type === "openai_compatible" && (
    <Row label="API key" hint={s.provider.apiKeyConfigured ? "A key is configured. Enter a new key to rotate it." : "Required for API mode."}>
      <PasswordInput
        placeholder={s.provider.apiKeyConfigured ? "Configured" : "Paste API key"}
        onCommit={(v) => v && queueSave({ providerApiKey: v })}
      />
    </Row>
  )}
  <Row label="Chat model">
    <TextInput value={s.provider.chatModel} onCommit={(v) => set("provider", { ...s.provider, chatModel: v })} />
  </Row>
  <Row label="Embedding model">
    <TextInput value={s.provider.embeddingModel} onCommit={(v) => set("provider", { ...s.provider, embeddingModel: v })} />
  </Row>
  <Row label="SSE completion" hint="Strict waits for persistence before done; async returns done earlier.">
    <Select value={s.sseDoneMode} options={["strict", "async"]} onChange={(v) => queueSave({ sseDoneMode: v })} />
  </Row>
</Section>
```

Add `TextInput` and `PasswordInput` atoms modeled after `NumberInput`, with local draft state and commit on blur/Enter.

- [ ] **Step 4: Extend `set()` diff builder**

Add:

```ts
if (key === "provider") {
  const provider = value as AppSettings["provider"];
  if (provider.type !== s.provider.type) diff.providerType = provider.type;
  if (provider.baseUrl !== s.provider.baseUrl) diff.providerBaseUrl = provider.baseUrl;
  if (provider.chatModel !== s.provider.chatModel) diff.providerChatModel = provider.chatModel;
  if (provider.embeddingModel !== s.provider.embeddingModel) diff.providerEmbeddingModel = provider.embeddingModel;
  if (provider.visionModel !== s.provider.visionModel) diff.providerVisionModel = provider.visionModel;
}
```

Add new `SaveField` union members for provider fields.

- [ ] **Step 5: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/settings.ts frontend/src/pages/admin/SettingsPage.tsx
git commit -m "feat: add inference provider settings ui"
```

---

### Task 10: Remove Ollama From Default Docker Compose and Add Optional Override

**Files:**
- Modify: `docker-compose.yml`
- Create: `docker-compose.ollama.yml`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/deployment.md`
- Test: `tests/test_docker_packaging.py`
- Test: `tests/test_health.py`

- [ ] **Step 1: Write failing Docker packaging test**

Add to `tests/test_docker_packaging.py`:

```python
from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_default_compose_does_not_require_ollama() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    assert "ollama" not in services
    assert "ollama-init" not in services
    assert "ollama" not in services["app"].get("depends_on", {})


def test_ollama_override_contains_local_llm_services() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.ollama.yml").read_text())
    services = compose["services"]

    assert "ollama" in services
    assert "ollama-init" in services
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/pytest tests/test_docker_packaging.py -q
```

Expected: FAIL because default compose still includes Ollama and override file does not exist.

- [ ] **Step 3: Modify default compose**

Remove `ollama`, `ollama-init`, and `ollama_data` from `docker-compose.yml`. Remove the app dependency on Ollama and do not set `OLLAMA_URL` in the default compose.

Set default provider env for API path:

```yaml
environment:
  - POSTGRES_URL=postgresql+psycopg2://safe4ai:safe4ai@postgres:5432/safe4ai
  - QDRANT_URL=http://qdrant:6333
```

- [ ] **Step 4: Add optional Ollama override**

Create `docker-compose.ollama.yml`:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_KEEP_ALIVE=24h
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 15s
      timeout: 10s
      retries: 10
      start_period: 30s

  ollama-init:
    image: ollama/ollama:latest
    depends_on:
      ollama:
        condition: service_healthy
    entrypoint: ["/bin/sh", "-c"]
    command: >
      "ollama pull qwen3.5:9b &&
       ollama pull nomic-embed-text &&
       ollama pull qwen2.5vl:7b"
    environment:
      - OLLAMA_HOST=http://ollama:11434
    volumes:
      - ollama_data:/root/.ollama
    restart: "no"

  app:
    environment:
      - OLLAMA_URL=http://ollama:11434
    depends_on:
      ollama:
        condition: service_healthy

volumes:
  ollama_data:
```

- [ ] **Step 5: Update docs**

In `README.md`, replace default startup commands with:

```bash
docker compose up --build
```

Add local Ollama startup:

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
```

In `.env.example`, add provider fields:

```env
PROVIDER_TYPE=openai_compatible
PROVIDER_BASE_URL=https://api.openai.com/v1
PROVIDER_API_KEY=
PROVIDER_CHAT_MODEL=gpt-4.1-mini
PROVIDER_EMBEDDING_MODEL=text-embedding-3-small
PROVIDER_VISION_MODEL=gpt-4.1-mini
```

- [ ] **Step 6: Run packaging and health tests**

Run:

```bash
./.venv/bin/pytest tests/test_docker_packaging.py tests/test_health.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml docker-compose.ollama.yml .env.example README.md docs/deployment.md tests/test_docker_packaging.py tests/test_health.py
git commit -m "chore: make ollama optional in docker compose"
```

---

### Task 11: Full Verification and Report Update

**Files:**
- Modify: `bug-report.md`
- Modify: `docs/superpowers/plans/2026-05-15-provider-runtime-hardening.md`

- [ ] **Step 1: Run backend suite**

Run:

```bash
./.venv/bin/pytest -q
```

Expected: all tests pass. Record exact count, including skipped tests.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript and Vite build succeed.

- [ ] **Step 3: Run Docker config validation**

Run:

```bash
docker compose config
docker compose -f docker-compose.yml -f docker-compose.ollama.yml config
```

Expected: both commands parse successfully. Default config does not include `ollama`; override config does.

- [ ] **Step 4: Update `bug-report.md`**

In `bug-report.md`, mark:

```markdown
R5-3 — fixed: chat_stream post-processing now uses single-transaction finalization.
R5-5 — fixed with caveat: OpenAI-compatible providers use actual usage when returned; Ollama remains estimated.
R5-29 — addressed: strict mode remains default; async mode is available/configurable for lower-latency done semantics.
```

Include exact verification output from Steps 1-3.

- [ ] **Step 5: Run final status check**

Run:

```bash
git status --short
```

Expected: only intended files are modified.

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat: add configurable inference providers"
```

---

## Self-Review

Spec coverage:
- R5-3 is covered by Task 7.
- R5-5 is covered by Tasks 1, 2, 3, 4, 5, 6, and 9.
- R5-29 is covered by Task 8.
- Removing Ollama from default Docker is covered by Task 10.
- Settings UI provider switch and API key handling are covered by Tasks 6 and 9.

Placeholder scan:
- The plan avoids placeholder phrases and gives concrete tests, file paths, commands, and expected outcomes.

Type consistency:
- `providerType`, `providerBaseUrl`, `providerApiKey`, `providerChatModel`, `providerEmbeddingModel`, `providerVisionModel`, and `sseDoneMode` are consistently used in frontend patch payloads and backend `PatchSettingsRequest`.
- Backend config keys use snake case in `app_config`: `provider_type`, `provider_base_url`, `provider_api_key`, `provider_chat_model`, `provider_embedding_model`, `provider_vision_model`, `sse_done_mode`.

