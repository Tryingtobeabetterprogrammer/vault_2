---
tags:
- curatorkit
configs:
- config_name: sft_messages
  default: true
  description: curatorkit sft_messages export, sha256 fef1a58e798cf38abbf303f8025ca7bd0c4ea9374e87346dc561d56c15256d54
  data_files:
  - split: train
    path: sft_messages.jsonl
---

# Dataset Card: curatorkit_run

## Summary

- **Run timestamp**: 2026-11-09T13:21:22.269057Z
- **Wall clock time**: 0.0s
- **Pipeline config hash**: `f087ef1404e03454`

## Source Documents

  - Unknown

## Pipeline Stages

| Step | Input | Passed | Recovered | Rejected | Forward |
|------|-------|--------|-----------|----------|---------|
| JSONLReader | 202 | 202 | — | 0 | 202 |
| SchemaGate | 202 | 202 | 0 | 0 | 202 |
| ExactDeduplicator | 202 | 5 | — | — | 5 |
| TextCleaner | 5 | 5 | — | — | 5 |
| MessagesExporter | — | 5 | — | — | 5 |

## Gate Pass Rates and Rejection Breakdown

- **JSONLReader**: 202/0 passed (N/A), 0 rejected
- **SchemaGate**: 202/202 passed (100.0%), 0 rejected


**Rejection reasons:**
  - None

## Deduplication

  - exact_duplicates_removed: 197

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

## Configs

Load one with `datasets.load_dataset("<this folder or Hub repo>", "<config>")`.

| Config | Splits (rows) | Columns |
|--------|---------------|---------|
| `sft_messages` | train (5) | `messages`: list of {role, content}; role is system, user or assistant |
