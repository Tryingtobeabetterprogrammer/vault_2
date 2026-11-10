# Dataset Card: curatorkit_run

## Summary

- **Run timestamp**: 2026-11-09T08:50:04.991252Z
- **Wall clock time**: 0.0s
- **Pipeline config hash**: `fc1993f061c94d4a`

## Source Documents

  - Unknown

## Pipeline Stages

| Step | Input | Passed | Recovered | Rejected | Forward |
|------|-------|--------|-----------|----------|---------|
| JSONLReader | 144 | 144 | — | 0 | 144 |
| SchemaGate | 144 | 144 | 0 | 0 | 144 |
| ExactDeduplicator | 144 | 26 | — | — | 26 |
| TextCleaner | 26 | 26 | — | — | 26 |
| AlpacaExporter | — | 26 | — | — | 26 |

## Gate Pass Rates and Rejection Breakdown

- **JSONLReader**: 144/0 passed (N/A), 0 rejected
- **SchemaGate**: 144/144 passed (100.0%), 0 rejected


**Rejection reasons:**
  - None

## Deduplication

  - exact_duplicates_removed: 118

## Known Limitations

- No MinHash deduplication applied.
- Table extraction requires `extract_tables: true` on the PDF reader and MinerU with GPU support. Disabled by default.
- Token counting uses a whitespace tokenizer by default. For exact LLM context window
  enforcement, enable `use_tiktoken: true` in the SchemaGate config.
- Both within-run (MinHash/Diversity) and cross-run (EmbeddingDeduplicator) deduplication
  are available. Cross-run dedup persists an embedding index across runs; use
  `embedding_reset_index: true` to start fresh.

## Reproduction

```bash
pip install curatorkit
curatorkit run pipeline.yaml --output-dir ./out/
```

## Tool Versions

- **curatorkit**: 0.1.21
- **python**: 3.11.9
