#!/usr/bin/env python3
"""
Integration test for docling-graph pipeline.

Tests the full pipeline: PDF → Docling conversion → LLM extraction → graph.
Outputs: extracted models (JSON), text chunks, and Cypher statements.
Loads configuration from .env (see .env.example).

Usage:
    python scripts/test_integration.py
    python scripts/test_integration.py --source <pdf> --template <dotted.path>
"""

import argparse
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(description="Docling-Graph Integration Test")
    parser.add_argument("--source", default="scripts/tests/pdfs/igcse_biology_4ed_tr_chapter_1.pdf")
    parser.add_argument("--template", default="scripts.tests.templates.TeacherResourceChapter")
    parser.add_argument("--provider", default=None, help="Override LLM provider")
    parser.add_argument("--model", default=None, help="Override model ID")
    parser.add_argument("--output-dir", default="scripts/tests/output")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"❌ Source file not found: {source_path}")
        sys.exit(1)

    print("=" * 70)
    print("  Docling-Graph Integration Test")
    print("=" * 70)

    from docling_graph import PipelineConfig, run_pipeline
    from docling_graph.core.exporters.cypher_exporter import CypherExporter

    config = PipelineConfig(
        source=str(source_path),
        template=args.template,
        backend="llm",
        processing_mode="many-to-one",
        extraction_contract="direct",
        export_format="cypher",
        model_override=args.model,
        provider_override=args.provider,
        dump_to_disk=True,
        output_dir=args.output_dir,
        debug=args.debug,
    )

    print(f"\n📄 Source:     {config.source}")
    print(f"📋 Template:   {config.template}")
    print(f"🔧 Provider:   {config.provider_override or '(from .env)'}")
    print(f"🤖 Model:      {config.model_override or '(from .env)'}")
    print(f"📏 Max tokens:  {config.llm_overrides.generation.max_tokens or '(default)'}")
    print()

    start = time.time()
    try:
        print("🚀 Running pipeline...\n")
        context = run_pipeline(config)
        elapsed = time.time() - start

        # ── 1. Extracted Models ──────────────────────────────────────────
        models = context.extracted_models or []
        print(f"\n{'=' * 70}")
        print(f"  1. EXTRACTED MODELS  ({len(models)} model(s))")
        print(f"{'=' * 70}")
        for i, model in enumerate(models):
            model_dict = model.model_dump() if hasattr(model, "model_dump") else {}
            print(json.dumps(model_dict, indent=2, default=str, ensure_ascii=False))

        # ── 2. Text Chunks ───────────────────────────────────────────────
        print(f"\n{'=' * 70}")
        print(f"  2. TEXT CHUNKS")
        print(f"{'=' * 70}")
        if context.docling_document:
            from docling_graph.core.extractors.document_chunker import DocumentChunker
            chunker = DocumentChunker(
                chunk_max_tokens=config.chunk_max_tokens or 512,
                tokenizer_name="tiktoken",
            )
            chunks, stats = chunker.chunk_document_with_stats(context.docling_document)
            print(f"\n📦 {stats['total_chunks']} chunks "
                  f"(avg {stats.get('avg_tokens', 0):.0f} tokens, "
                  f"max {stats.get('max_tokens', 0)} tokens)\n")
            for idx, chunk in enumerate(chunks):
                preview = chunk[:200].replace("\n", " ")
                if len(chunk) > 200:
                    preview += "..."
                print(f"  [{idx:3d}] ({len(chunk):,} chars) {preview}")
        else:
            print("\n  ⚠️  No docling document — cannot generate chunks")

        # ── 3. Cypher Statements ─────────────────────────────────────────
        print(f"\n{'=' * 70}")
        print(f"  3. CYPHER STATEMENTS")
        print(f"{'=' * 70}")
        graph = context.knowledge_graph
        if graph and graph.number_of_nodes() > 0:
            # Generate Cypher to a temp file and read it back
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".cypher", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            CypherExporter().export(graph, tmp_path)
            cypher_text = tmp_path.read_text()
            tmp_path.unlink()

            print(f"\n// {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges\n")
            print(cypher_text)

            # Also note where the file was saved by the pipeline
            output_dirs = list(Path(args.output_dir).glob("*/docling_graph/graph.cypher"))
            if output_dirs:
                print(f"\n💾 Cypher file saved to: {output_dirs[-1]}")
        else:
            print("\n  ⚠️  No graph — cannot generate Cypher")

        # ── Summary ──────────────────────────────────────────────────────
        print(f"\n{'=' * 70}")
        has_models = len(models) > 0
        has_graph = graph is not None and graph.number_of_nodes() > 0
        if has_models and has_graph:
            print(f"  ✅ ALL CHECKS PASSED ({elapsed:.1f}s)")
        elif has_models:
            print(f"  ⚠️  Models extracted but graph empty ({elapsed:.1f}s)")
        else:
            print(f"  ❌ No models extracted ({elapsed:.1f}s)")
        print(f"{'=' * 70}")

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
