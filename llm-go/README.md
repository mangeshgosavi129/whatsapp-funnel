# llm-go

Go port of the Python `llm/` module with matching architecture:

- `config` → env loading and runtime config.
- `schemas` → typed pipeline input/output contracts.
- `apihelpers` → OpenAI-compatible chat completion helper + JSON extraction.
- `prompts` → memory and generate prompts.
- `utils` → enum normalization + CTA prompt formatting.
- `knowledge` → ingestion and hybrid (vector + keyword with RRF) retrieval.
- `steps/generate` → unified observe/decide/respond step.
- `steps/memory` → rolling summary archivist step.
- `pipeline` → orchestration for RAG + generate + followup.

This module is intentionally a one-to-one functional translation rather than a redesign.
