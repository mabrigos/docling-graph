# Copilot Instructions

## Project Overview

`docling-graph` converts documents (PDF, images, markdown, Office, HTML) into **Pydantic-validated objects** and builds **directed knowledge graphs** (NetworkX `DiGraph`) with explicit semantic relationships. Extraction is powered by LLMs via LiteLLM (OpenAI, Mistral, AWS Bedrock, Ollama, etc.) and optionally by Docling's vision models.

## Commands

```bash
# Setup
uv sync --extra dev

# Lint & format
uv run ruff format .
uv run ruff check .

# Type check
uv run mypy docling_graph

# Pre-commit (runs ruff + mypy)
uv run pre-commit run --all-files

# Run tests
python -m pytest scripts/test_integration.py -v
python -m pytest scripts/test_integration.py -k "test_name" -v
```

> Tests live in `scripts/`, not a `tests/` directory. Test fixtures and Pydantic templates are in `scripts/tests/`.

## Architecture

An 8-stage pipeline orchestrated by `pipeline/orchestrator.py`, passing a shared `PipelineContext` through each stage:

```
InputNormalization → TemplateLoading → Extraction → GraphConversion
  → Export → DoclingExport → Visualization → Cleanup
```

**Key layers:**
- `cli/` — Typer CLI (`docling-graph init`, `convert`, `inspect`)
- `pipeline/` — Orchestrator, stages, shared `PipelineContext`
- `core/extractors/` — Extraction strategies and contracts (direct / staged / delta)
- `core/converters/` — `GraphConverter`: Pydantic models → NetworkX `DiGraph`
- `core/exporters/` — CSV, Cypher (Neo4j), JSON, Docling export
- `llm_clients/` — LiteLLM wrapper with response parsing and schema normalization
- `config.py` — `PipelineConfig` is the single source of truth for all pipeline defaults
- `protocols.py` — Duck-typing interfaces (`LLMClientProtocol`, `TextExtractionBackendProtocol`, `ExtractorProtocol`)
- `exceptions.py` — Unified hierarchy rooted at `DoclingGraphError`

**Public API** (via `__init__.py`):
```python
from docling_graph import run_pipeline, PipelineContext
context = run_pipeline(config_dict)
graph = context.knowledge_graph   # networkx.DiGraph
models = context.extracted_models # list[BaseModel]
```

## Key Conventions

### Pydantic templates define the graph schema

User-supplied Pydantic models drive extraction AND graph structure. Two conventions control graph behavior via `model_config`:

```python
class Entity(BaseModel):
    model_config = {
        "is_entity": True,               # Becomes a graph node
        "graph_id_fields": ["name", "dob"]  # Deterministic node ID from these fields
    }
    name: str = Field(description="...")
    related: list[OtherEntity] = edge("RELATES_TO", description="...")

class Component(BaseModel):
    model_config = {"is_entity": False}  # Embedded in parent, not a node
```

The `edge()` helper (from `scripts/tests/templates.py`) wraps `Field` with `json_schema_extra={"edge_label": label}` and sets `default_factory=list`.

### Extraction contracts

| Contract | Behavior |
|----------|----------|
| `direct` | Single-pass full extraction |
| `staged` | 3-pass: catalog → identity fields → fill → edges |
| `delta` | Multi-pass incremental with semantic entity resolution (requires `spacy`, `rapidfuzz`) |

### Processing modes

- `one-to-one`: One LLM call per page/chunk
- `many-to-one`: Single consolidated call; falls back to multiple partial models (zero-data-loss policy) if consolidation fails

### Node IDs are deterministic

`NodeIDRegistry` generates stable IDs from `graph_id_fields`. Same content always yields the same node ID, enabling cross-document deduplication.

### Code style

- Line length: **100 characters**
- All functions require type annotations (MyPy strict mode: `disallow_untyped_defs = true`)
- Ruff rules include `ANN` (annotations), `B` (bugbear), `N` (naming), `UP` (pyupgrade), `C90` (complexity max 30)
- Use Protocols for new backend/client interfaces rather than ABCs

### Configuration hierarchy

CLI flags → environment variables → YAML config file → `PipelineConfig` defaults. The `.env.example` documents all supported env vars (provider, model, chunking, processing mode, etc.).
