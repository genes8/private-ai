# Agent Definitions

## RAG / Document Agent
**Role:** Primary — answers user questions using retrieved document chunks.
**Framework:** LangGraph (Python)
**Model:** Qwen 3.5 9B via Ollama
**Owns:** `app/agents/`, `app/services/rag_pipeline.py`, `app/components/`
**Tool permissions:** query Qdrant (read-only), read `document_chunks` table

## Vision OCR Sub-agent
**Role:** Converts scanned PDF page images to text during ingestion.
**Model:** Qwen2.5-VL 7B via Ollama
**Invoked by:** `rag_pipeline.py` ingestion path only
**Tool permissions:** read temp image files, write extracted text

## Admin (no LLM)
**Role:** Manages documents, users, and audit logs via REST API.
**Owns:** `app/db/`, `scripts/`
**Tool permissions:** full DB read/write, filesystem read/write for `data/`
