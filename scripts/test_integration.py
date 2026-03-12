#!/usr/bin/env python3
"""
Integration test for docling-graph pipeline.

Tests the full pipeline: PDF → Docling conversion → LLM extraction → graph.
Loads configuration from .env (see .env.example).

Usage:
    python scripts/test_integration.py --source <pdf_path> --template <dotted.path.ClassName>

Examples:
    python scripts/test_integration.py \
        --source scripts/tests/sample.pdf \
        --template scripts.tests.templates.LessonPlan

    # With explicit overrides:
    python scripts/test_integration.py \
        --source scripts/tests/sample.pdf \
        --template scripts.tests.templates.LessonPlan \
        --provider bedrock \
        --model eu.anthropic.claude-sonnet-4-6
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(description="Docling-Graph Integration Test")
    parser.add_argument("--source", default="scripts/tests/pdfs/igcse_biology_4ed_tr_chapter_1.pdf", help="Path to PDF or document")
    parser.add_argument("--template", default="scripts.tests.templates.TeacherResourceChapter", help="Dotted path to Pydantic template class")
    parser.add_argument("--provider", default=None, help="Override LLM provider (e.g. bedrock)")
    parser.add_argument("--model", default=None, help="Override model ID")
    parser.add_argument("--output-dir", default="scripts/tests/output", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug artifacts")
    args = parser.parse_args()

    # Validate source exists
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"❌ Source file not found: {source_path}")
        print(f"   Place your test PDF in scripts/tests/ and try again.")
        sys.exit(1)

    print("=" * 60)
    print("  Docling-Graph Integration Test")
    print("=" * 60)

    # Load config from .env (PipelineConfig reads env vars automatically)
    from docling_graph import PipelineConfig, run_pipeline

    config = PipelineConfig(
        source=str(source_path),
        template=args.template,
        backend="llm",
        processing_mode="many-to-one",
        extraction_contract="direct",
        model_override=args.model,
        provider_override=args.provider,
        dump_to_disk=True,
        output_dir=args.output_dir,
        debug=args.debug,
    )

    # Display resolved config
    print(f"\n📄 Source:    {config.source}")
    print(f"📋 Template:  {config.template}")
    print(f"🔧 Provider:  {config.provider_override or '(from .env / config)'}")
    print(f"🤖 Model:     {config.model_override or '(from .env / config)'}")
    print(f"🌡️  Temp:      {config.llm_overrides.generation.temperature or '(default)'}")
    print(f"📏 Max tokens: {config.llm_overrides.generation.max_tokens or '(default)'}")
    print(f"📦 Chunk max:  {config.chunk_max_tokens or '(default 512)'}")
    print(f"📁 Output:    {config.output_dir}")
    print()

    # Run the pipeline
    start = time.time()
    try:
        print("🚀 Running pipeline...")
        context = run_pipeline(config)
        elapsed = time.time() - start

        # Validate results
        print(f"\n{'=' * 60}")
        print(f"  Results ({elapsed:.1f}s)")
        print(f"{'=' * 60}")

        # Check extracted models
        models = context.extracted_models or []
        print(f"\n📊 Extracted models: {len(models)}")
        if models:
            print(f"   ✅ Extraction successful")
            for i, model in enumerate(models):
                print(f"\n   Model {i + 1}:")
                model_dict = model.model_dump() if hasattr(model, "model_dump") else str(model)
                if isinstance(model_dict, dict):
                    for key, value in model_dict.items():
                        val_str = str(value)
                        if len(val_str) > 100:
                            val_str = val_str[:100] + "..."
                        print(f"     • {key}: {val_str}")
                else:
                    print(f"     {model_dict[:200]}")
        else:
            print(f"   ⚠️  No models extracted")

        # Check graph
        graph = context.knowledge_graph
        if graph:
            nodes = graph.number_of_nodes()
            edges = graph.number_of_edges()
            print(f"\n🔗 Knowledge graph: {nodes} nodes, {edges} edges")
            if nodes > 0:
                print(f"   ✅ Graph generation successful")
            else:
                print(f"   ⚠️  Graph is empty")
        else:
            print(f"\n🔗 Knowledge graph: None")
            print(f"   ⚠️  No graph generated")

        # Check graph metadata
        if context.graph_metadata:
            print(f"\n📈 Graph metadata:")
            print(f"     Nodes: {context.graph_metadata.node_count}")
            print(f"     Edges: {context.graph_metadata.edge_count}")

        # Check docling document
        if context.docling_document:
            print(f"\n📝 Docling document: available")
        else:
            print(f"\n📝 Docling document: not available")

        # Summary
        print(f"\n{'=' * 60}")
        has_models = len(models) > 0
        has_graph = graph is not None and graph.number_of_nodes() > 0
        if has_models and has_graph:
            print(f"  ✅ ALL CHECKS PASSED ({elapsed:.1f}s)")
        elif has_models:
            print(f"  ⚠️  PARTIAL: Models extracted but graph empty ({elapsed:.1f}s)")
        else:
            print(f"  ❌ FAILED: No models extracted ({elapsed:.1f}s)")
        print(f"{'=' * 60}")

        if not has_models:
            sys.exit(1)

    except Exception as e:
        elapsed = time.time() - start
        print(f"\n❌ Pipeline failed after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
