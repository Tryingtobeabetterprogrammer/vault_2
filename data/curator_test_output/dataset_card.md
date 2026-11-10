# Dataset Card: curatorkit_run

## Summary

- **Run timestamp**: 2026-11-09T08:27:08.410771Z
- **Wall clock time**: 0.0s
- **Pipeline config hash**: `126eedf94c890c1e`

## Source Documents

  - Unknown

## Pipeline Stages

| Step | Input | Passed | Recovered | Rejected | Forward |
|------|-------|--------|-----------|----------|---------|
| JSONLReader | 3 | 3 | — | 0 | 3 |
| SchemaGate | 3 | 3 | 0 | 0 | 3 |
| ExactDeduplicator | 3 | 2 | — | — | 2 |
| TextCleaner | 2 | 2 | — | — | 2 |
| AlpacaExporter | — | 2 | — | — | 2 |
| MessagesExporter | — | 2 | — | — | 2 |

## Gate Pass Rates and Rejection Breakdown

- **JSONLReader**: 3/0 passed (N/A), 0 rejected
- **SchemaGate**: 3/3 passed (100.0%), 0 rejected


**Rejection reasons:**
  - None

## Deduplication

  - exact_duplicates_removed: 1

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
