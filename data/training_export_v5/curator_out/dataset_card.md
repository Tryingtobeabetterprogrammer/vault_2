# Dataset Card: curatorkit_run

## Summary

- **Run timestamp**: 2026-11-09T10:59:49.013983Z
- **Wall clock time**: 0.2s
- **Pipeline config hash**: `c9e09ffcb20d5722`

## Source Documents

  - Unknown

## Pipeline Stages

| Step | Input | Passed | Recovered | Rejected | Forward |
|------|-------|--------|-----------|----------|---------|
| JSONLReader | 720 | 720 | — | 0 | 720 |
| SchemaGate | 720 | 720 | 0 | 0 | 720 |
| ExactDeduplicator | 720 | 720 | — | — | 720 |
| TextCleaner | 720 | 720 | — | — | 720 |
| MessagesExporter | — | 720 | — | — | 720 |

## Gate Pass Rates and Rejection Breakdown

- **JSONLReader**: 720/0 passed (N/A), 0 rejected
- **SchemaGate**: 720/720 passed (100.0%), 0 rejected


**Rejection reasons:**
  - None

## Deduplication

  - exact_duplicates_removed: 0

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
